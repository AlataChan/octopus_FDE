"""FastAPI application factory for the FDE web console backend."""
from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, cast

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from loom.archive.jsonl import ArchiveWriter
from loom.fde_session.clarify_engine import DeterministicClarifyEngine
from loom.planner.client import PlannerClient
from loom.planner.retry import plan as plan_intent
from loom.planner.types import IntentRequest
from loom.registry.store import WorkflowRegistryStore
from loom.registry.templates import TemplateCatalog
from loom.service.deps import Settings
from loom.service.routes.actor import router as actor_router
from loom.service.routes.health import router as health_router
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
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.state.settings = settings
    app.state.fernet = settings.fernet()
    app.state.session_store = SessionStore(settings.data_dir / "sessions.db")
    app.state.registry_store = WorkflowRegistryStore(settings.data_dir / "workflow_registry.db")
    app.state.archive_writer = ArchiveWriter(settings.data_dir)
    app.state.template_catalog = TemplateCatalog.load()
    app.state.planner = planner or _default_planner
    app.state.clarify_engine = clarify_engine or DeterministicClarifyEngine()
    app.include_router(health_router)
    app.include_router(actor_router)
    app.include_router(sessions_router)
    app.include_router(registry_router)
    app.include_router(templates_router)
    web_dist = Path(__file__).resolve().parents[2] / "web" / "dist"
    if web_dist.exists():
        app.mount("/", StaticFiles(directory=web_dist, html=True), name="web")
    return app


app = create_app()
