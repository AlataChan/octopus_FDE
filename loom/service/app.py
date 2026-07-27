"""FastAPI application factory for the FDE web console backend."""
from __future__ import annotations

import asyncio
from collections.abc import Callable
from contextlib import suppress
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, cast
from urllib.parse import urlparse

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from loom.archive.jsonl import ArchiveWriter
from loom.archive.writer import InstanceArchiveWriter
from loom.fde_session.clarify_engine import DeterministicClarifyEngine
from loom.planner.client import PlannerClient
from loom.planner.retry import plan as plan_intent
from loom.planner.types import IntentRequest
from loom.registry.design_knowledge import DesignKnowledgeCatalog
from loom.registry.personas import PersonaCatalog
from loom.registry.store import WorkflowRegistryStore
from loom.registry.templates import TemplateCatalog
from loom.service.auth import AuthSessionStore, LoginRateLimiter
from loom.service.deps import Settings
from loom.service.routes.actor import router as actor_router
from loom.service.routes.auth import AUTH_ARCHIVE_SESSION_ID
from loom.service.routes.auth import router as auth_router
from loom.service.routes.design_knowledge import router as design_knowledge_router
from loom.service.routes.health import router as health_router
from loom.service.routes.personas import router as personas_router
from loom.service.routes.registry import router as registry_router
from loom.service.routes.sessions import router as sessions_router
from loom.service.routes.templates import router as templates_router
from loom.state.store import SessionStore

PlannerCallable = Callable[..., Any]

if TYPE_CHECKING:
    from loom.ir.models import IRDocument


def _default_planner(**kwargs: object) -> IRDocument:
    user_message = str(kwargs["user_message"])
    scope = str(kwargs.get("scope") or "ecommerce/kb")
    target = kwargs.get("target") or "hiagent"
    if target not in {"hiagent", "dify"}:
        raise RuntimeError(f"unsupported target runtime: {target}")
    target_runtime = cast(Literal["hiagent", "dify"], target)
    llm_config = kwargs["llm_config"]
    if not isinstance(llm_config, dict):
        raise RuntimeError("planner llm_config missing")
    api_key = str(llm_config.get("api_key") or "")
    if not api_key:
        raise RuntimeError("session LLM API key is not configured")
    client = PlannerClient(
        api_key=api_key,
        base_url=str(llm_config.get("base_url") or ""),
        model=str(llm_config.get("model") or ""),
    )
    result = plan_intent(
        IntentRequest(intent=user_message, scope=scope, target=target_runtime),
        client=client,
    )
    if not result.ok or result.ir is None:
        details = "; ".join(f.detail for f in result.failures) or "planner failed"
        raise RuntimeError(details)
    return result.ir


def create_app(
    *,
    settings: Settings | None = None,
    planner: PlannerCallable | None = None,
    clarify_engine: Any | None = None,
) -> FastAPI:
    settings = settings or Settings.from_env()
    settings.ensure_data_dir()
    app = FastAPI(title="FDE Web Console API", version="0.1.0")
    if settings.cors_allow_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=list(settings.cors_allow_origins),
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    app.state.settings = settings
    app.state.fernet = settings.fernet()
    app.state.session_store = SessionStore(settings.data_dir / "sessions.db")
    app.state.registry_store = WorkflowRegistryStore(settings.data_dir / "workflow_registry.db")
    app.state.archive_writer = InstanceArchiveWriter(
        ArchiveWriter(settings.data_dir),
        instance_id=settings.instance_id,
        hmac_key=settings.archive_hmac_key(),
    )
    app.state.auth_store = AuthSessionStore(ttl_hours=settings.auth_session_ttl_hours)
    app.state.auth_rate_limiter = LoginRateLimiter()
    app.state.template_catalog = TemplateCatalog.load()
    app.state.persona_catalog = PersonaCatalog.load()
    app.state.design_knowledge_catalog = DesignKnowledgeCatalog.from_template_catalog(app.state.template_catalog)
    app.state.planner = planner or _default_planner
    app.state.clarify_engine = clarify_engine or DeterministicClarifyEngine()
    _install_auth_middleware(app, settings)
    _install_auth_cleanup(app)
    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(actor_router)
    app.include_router(sessions_router)
    app.include_router(registry_router)
    app.include_router(templates_router)
    app.include_router(personas_router)
    app.include_router(design_knowledge_router)
    web_dist = Path(__file__).resolve().parents[2] / "web" / "dist"
    if web_dist.exists():
        _install_spa_routes(app, web_dist)
    return app


def _install_spa_routes(app: FastAPI, web_dist: Path) -> None:
    """Serve the React SPA with client-side routing fallback.

    `StaticFiles(html=True)` only auto-serves index.html for directory paths
    (`/`), so client-side routes like `/login` would 404. We mount /assets for
    bundled assets, then register a catch-all that serves a literal file if it
    exists under web/dist, else falls back to index.html for the SPA router.
    Routes registered earlier (`/v1/*`, `/health`) match first because Starlette
    evaluates in registration order.
    """
    assets_dir = web_dist / "assets"
    if assets_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="web-assets")

    index_html = web_dist / "index.html"

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa_fallback(full_path: str):  # type: ignore[no-untyped-def]
        # Defensive: never serve SPA for API namespaces (router should have matched).
        if full_path.startswith(("v1/", "v1")) or full_path == "health":
            raise HTTPException(status_code=404, detail="Not Found")
        if full_path:
            candidate = (web_dist / full_path).resolve()
            try:
                candidate.relative_to(web_dist.resolve())
            except ValueError:
                # Path traversal attempt.
                raise HTTPException(status_code=404, detail="Not Found")
            if candidate.is_file():
                return FileResponse(candidate)
        if not index_html.is_file():
            raise HTTPException(status_code=404, detail="Not Found")
        return FileResponse(index_html)


def _install_auth_middleware(app: FastAPI, settings: Settings) -> None:
    @app.middleware("http")
    async def auth_middleware(request, call_next):  # type: ignore[no-untyped-def]
        path = request.url.path
        if _is_exempt_path(path):
            return await call_next(request)
        if not path.startswith("/v1"):
            return await call_next(request)
        if settings.auth_disabled:
            from loom.service.deps import Actor

            request.state.actor = Actor(id=request.headers.get("X-Actor-Id") or "single-user", role="fde")
            return await call_next(request)
        if request.method in {"POST", "PATCH", "PUT", "DELETE"} and not _origin_ok(request, settings):
            return JSONResponse({"error": "csrf_origin_mismatch"}, status_code=403)
        token = request.cookies.get("fde_session")
        info = request.app.state.auth_store.validate(token)
        _archive_expired_sessions(request)
        if info is None:
            return JSONResponse({"error": "not_authenticated"}, status_code=401)
        from loom.service.deps import Actor

        request.state.actor = Actor(id=info.username, role="fde")
        request.state.auth_session_info = info
        return await call_next(request)


def _is_exempt_path(path: str) -> bool:
    return path in {"/v1/health", "/v1/auth/login", "/v1/auth/logout", "/health"}


def _origin_ok(request: Any, settings: Settings) -> bool:
    raw_origin = request.headers.get("Origin") or request.headers.get("Referer")
    if not raw_origin:
        return False
    request_origin = _origin_from_parts(
        scheme=str(request.url.scheme),
        host=request.url.hostname,
        port=request.url.port,
    )
    header_origin = _origin_from_header(raw_origin)
    if request_origin is None or header_origin is None:
        return False
    allowed_origins = {
        normalized
        for origin in settings.cors_allow_origins
        if (normalized := _origin_from_header(origin)) is not None
    }
    return header_origin in {request_origin, *allowed_origins}


def _origin_from_header(raw_origin: str) -> str | None:
    parsed = urlparse(raw_origin)
    try:
        return _origin_from_parts(scheme=parsed.scheme, host=parsed.hostname, port=parsed.port)
    except ValueError:
        return None


def _origin_from_parts(*, scheme: str, host: str | None, port: int | None) -> str | None:
    normalized_scheme = scheme.lower()
    if normalized_scheme not in {"http", "https"} or not host:
        return None
    normalized_port = port or (443 if normalized_scheme == "https" else 80)
    return f"{normalized_scheme}://{host.lower()}:{normalized_port}"


def _install_auth_cleanup(app: FastAPI) -> None:
    async def cleanup_loop() -> None:
        while True:
            await asyncio.sleep(300)
            for info in app.state.auth_store.cleanup_expired():
                _archive_session_expired(app, info.username)

    async def startup() -> None:
        app.state.auth_cleanup_task = asyncio.create_task(cleanup_loop())

    async def shutdown() -> None:
        task = getattr(app.state, "auth_cleanup_task", None)
        if task is not None:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task

    app.router.on_startup.append(startup)
    app.router.on_shutdown.append(shutdown)


def _archive_expired_sessions(request: Any) -> None:
    for info in request.app.state.auth_store.drain_expired():
        _archive_session_expired(request.app, info.username)


def _archive_session_expired(app: FastAPI, username: str) -> None:
    app.state.archive_writer.append(
        AUTH_ARCHIVE_SESSION_ID,
        actor_id="auth",
        event_type="auth.session_expired",
        payload={
            "username_hmac": app.state.archive_writer.hmac_text(username),
            "ttl_hours": app.state.settings.auth_session_ttl_hours,
        },
    )


app = create_app()
