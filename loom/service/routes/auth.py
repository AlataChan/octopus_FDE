"""Local cookie-session auth routes."""
from __future__ import annotations

from datetime import datetime  # noqa: TC003
from typing import TYPE_CHECKING, cast
from uuid import UUID

from fastapi import APIRouter, Request, Response
from pydantic import BaseModel, Field

from loom.service.auth import DUMMY_SCRYPT_HASH, client_ip, verify_password
from loom.service.deps import Actor  # noqa: TC001

if TYPE_CHECKING:
    from loom.archive.schema import ArchiveEventType
    from loom.service.deps import Settings

router = APIRouter(prefix="/v1/auth")
AUTH_ARCHIVE_SESSION_ID = UUID("00000000-0000-0000-0000-000000000000")
COOKIE_NAME = "fde_session"


class LoginRequest(BaseModel):
    username: str = Field(min_length=1)
    password: str = Field(min_length=1)


class AuthMeResponse(BaseModel):
    username: str
    expires_at: datetime | None = None


@router.post("/login")
def login(body: LoginRequest, request: Request, response: Response) -> dict[str, object]:
    settings: Settings = request.app.state.settings
    ip = client_ip(request, trusted_proxy=settings.trusted_proxy)
    ip_key = request.app.state.archive_writer.hmac_text(ip)
    username_hmac = request.app.state.archive_writer.hmac_text(body.username)

    if settings.auth_disabled:
        token, info = request.app.state.auth_store.create(username=body.username or "single-user")
        _set_cookie(response, token, settings)
        return {"ok": True, "username": info.username, "expires_at": info.expires_at.isoformat()}

    if request.app.state.auth_rate_limiter.is_limited(ip_key):
        verify_password(body.password, DUMMY_SCRYPT_HASH)
        _archive_auth(
            request,
            "auth.login_failed",
            {"username_hmac": username_hmac, "client_ip_hmac": ip_key, "reason": "rate_limited"},
        )
        response.status_code = 429
        return {"error": "rate_limited"}

    expected_username = settings.auth_username or ""
    password_hash = settings.auth_password_hash if body.username == expected_username else DUMMY_SCRYPT_HASH
    ok = verify_password(body.password, password_hash or DUMMY_SCRYPT_HASH)
    if body.username != expected_username or not ok:
        request.app.state.auth_rate_limiter.record_failure(ip_key)
        _archive_auth(
            request,
            "auth.login_failed",
            {"username_hmac": username_hmac, "client_ip_hmac": ip_key, "reason": "bad_credentials"},
        )
        response.status_code = 401
        return {"error": "invalid_credentials"}

    request.app.state.auth_rate_limiter.reset(ip_key)
    token, info = request.app.state.auth_store.create(username=expected_username)
    _set_cookie(response, token, settings)
    _archive_auth(
        request,
        "auth.login_succeeded",
        {"username_hmac": username_hmac, "client_ip_hmac": ip_key},
    )
    return {"ok": True, "username": info.username, "expires_at": info.expires_at.isoformat()}


@router.post("/logout")
def logout(request: Request, response: Response) -> dict[str, bool]:
    token = request.cookies.get(COOKIE_NAME)
    info = request.app.state.auth_store.revoke(token)
    if info is not None:
        _archive_auth(
            request,
            "auth.logout",
            {"username_hmac": request.app.state.archive_writer.hmac_text(info.username)},
        )
    _clear_cookie(response, request.app.state.settings)
    return {"ok": True}


@router.get("/me")
def me(request: Request) -> AuthMeResponse:
    actor: Actor = request.state.actor
    info = getattr(request.state, "auth_session_info", None)
    return AuthMeResponse(username=actor.id, expires_at=getattr(info, "expires_at", None))


def _set_cookie(response: Response, token: str, settings: Settings) -> None:
    response.set_cookie(
        COOKIE_NAME,
        token,
        httponly=True,
        secure=_cookie_secure(settings),
        samesite="lax",
        path="/v1",
        max_age=settings.auth_session_ttl_hours * 3600,
    )


def _clear_cookie(response: Response, settings: Settings) -> None:
    response.delete_cookie(
        COOKIE_NAME,
        httponly=True,
        secure=_cookie_secure(settings),
        samesite="lax",
        path="/v1",
    )


def _cookie_secure(settings: Settings) -> bool:
    return settings.app_env != "dev" and not settings.auth_cookie_insecure_ok


def _archive_auth(request: Request, event_type: str, payload: dict[str, object]) -> None:
    request.app.state.archive_writer.append(
        AUTH_ARCHIVE_SESSION_ID,
        actor_id="auth",
        event_type=cast("ArchiveEventType", event_type),
        payload=payload,
    )
