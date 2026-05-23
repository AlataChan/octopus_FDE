"""Service settings and dependency helpers."""
from __future__ import annotations

import logging
import os
import socket
from base64 import urlsafe_b64decode
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from fastapi import HTTPException, Request

from loom.service.auth.password import ScryptPasswordError, validate_scrypt_hash

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class Actor:
    id: str = "single-user"
    role: str = "fde"


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    app_env: str = "dev"
    fernet_key: str | None = None
    binding_dir: Path = Path("config/customers")
    audit_max_retention_days: int = 365
    auth_username: str | None = None
    auth_password_hash: str | None = None
    auth_session_ttl_hours: int = 24
    auth_disabled: bool = True
    auth_cookie_insecure_ok: bool = False
    trusted_proxy: bool = False
    cors_allow_origins: tuple[str, ...] = ()
    instance_id: str = field(default_factory=socket.gethostname)

    @classmethod
    def from_env(cls) -> Settings:
        app_env = os.environ.get("APP_ENV", "prod")
        key = os.environ.get("LOOM_FERNET_KEY")
        if app_env != "dev" and not key:
            raise RuntimeError("LOOM_FERNET_KEY is required when APP_ENV is prod or unset")
        if app_env == "dev" and not key:
            key = Fernet.generate_key().decode("ascii")
            LOGGER.warning("LOOM_FERNET_KEY missing in dev; using an ephemeral per-process key")
        auth_username = os.environ.get("LOOM_AUTH_USERNAME")
        auth_password_hash = os.environ.get("LOOM_AUTH_PASSWORD_HASH")
        auth_disabled_env = os.environ.get("LOOM_AUTH_DISABLED")
        auth_disabled = (
            _parse_bool(auth_disabled_env)
            if auth_disabled_env is not None
            else app_env == "dev" and (not auth_username or not auth_password_hash)
        )
        if app_env != "dev" and auth_disabled:
            raise RuntimeError("LOOM_AUTH_DISABLED is only allowed when APP_ENV=dev")
        auth_cookie_insecure_ok = _parse_bool(os.environ.get("LOOM_AUTH_COOKIE_INSECURE_OK", "false"))
        if app_env != "dev" and auth_cookie_insecure_ok:
            LOGGER.warning(
                "SECURITY WARNING: LOOM_AUTH_COOKIE_INSECURE_OK=true disables Secure cookies; "
                "use only for local HTTP debugging and never on public deployments"
            )
        if not auth_disabled:
            if not auth_username:
                raise RuntimeError("LOOM_AUTH_USERNAME is required when authentication is enabled")
            if not auth_password_hash:
                raise RuntimeError("LOOM_AUTH_PASSWORD_HASH is required when authentication is enabled")
            try:
                validate_scrypt_hash(auth_password_hash)
            except ScryptPasswordError as e:
                raise RuntimeError(str(e)) from e
        web_concurrency = int(os.environ.get("WEB_CONCURRENCY", "1"))
        if web_concurrency > 1:
            raise RuntimeError("WEB_CONCURRENCY must be 1; in-memory auth sessions are single-worker only")
        cors_allow_origins = _parse_origins(os.environ.get("LOOM_CORS_ALLOW_ORIGINS", ""))
        return cls(
            data_dir=Path(os.environ.get("LOOM_DATA_DIR", ".loom-data")),
            app_env=app_env,
            fernet_key=key,
            binding_dir=Path(os.environ.get("LOOM_BINDING_DIR", "config/customers")),
            audit_max_retention_days=int(os.environ.get("LOOM_AUDIT_MAX_RETENTION_DAYS", "365")),
            auth_username=auth_username,
            auth_password_hash=auth_password_hash,
            auth_session_ttl_hours=int(os.environ.get("LOOM_AUTH_SESSION_TTL_HOURS", "24")),
            auth_disabled=auth_disabled,
            auth_cookie_insecure_ok=auth_cookie_insecure_ok,
            trusted_proxy=_parse_bool(os.environ.get("LOOM_TRUSTED_PROXY", "false")),
            cors_allow_origins=cors_allow_origins,
            instance_id=os.environ.get("LOOM_INSTANCE_ID") or socket.gethostname(),
        )

    def ensure_data_dir(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(self.data_dir, 0o700)

    def fernet(self) -> Fernet:
        key = self.fernet_key
        if not key:
            if self.app_env == "dev":
                key = Fernet.generate_key().decode("ascii")
            else:
                raise RuntimeError("LOOM_FERNET_KEY is required")
        return Fernet(key.encode("ascii"))

    def archive_hmac_key(self) -> bytes:
        key = self.fernet_key
        if not key:
            if self.app_env == "dev":
                key = Fernet.generate_key().decode("ascii")
            else:
                raise RuntimeError("LOOM_FERNET_KEY is required")
        raw = urlsafe_b64decode(key.encode("ascii"))
        return HKDF(
            algorithm=hashes.SHA256(),
            length=32,
            salt=None,
            info=b"loom-archive-hmac-v1",
        ).derive(raw)


def _parse_bool(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _parse_origins(raw: str) -> tuple[str, ...]:
    return tuple(_validate_origin(origin.strip()) for origin in raw.split(",") if origin.strip())


def _validate_origin(raw: str) -> str:
    if raw == "*":
        raise RuntimeError("LOOM_CORS_ALLOW_ORIGINS must not contain '*'")
    parsed = urlparse(raw)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise RuntimeError("LOOM_CORS_ALLOW_ORIGINS must contain full http(s) origins")
    if parsed.path not in {"", "/"} or parsed.params or parsed.query or parsed.fragment:
        raise RuntimeError("LOOM_CORS_ALLOW_ORIGINS must contain origins without paths")
    origin = f"{parsed.scheme.lower()}://{parsed.hostname.lower()}"
    if parsed.port is not None:
        origin = f"{origin}:{parsed.port}"
    return origin


def get_actor(request: Request) -> Actor:
    actor = getattr(request.state, "actor", None)
    if isinstance(actor, Actor):
        return actor
    settings: Settings = request.app.state.settings
    if settings.auth_disabled:
        return Actor(id=request.headers.get("X-Actor-Id") or "single-user", role="fde")
    raise HTTPException(status_code=401, detail="not_authenticated")
