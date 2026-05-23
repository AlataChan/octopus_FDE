"""Local single-user authentication helpers."""
from __future__ import annotations

from loom.service.auth.password import (
    DUMMY_SCRYPT_HASH,
    ScryptPasswordError,
    validate_scrypt_hash,
    verify_password,
)
from loom.service.auth.proxy import client_ip
from loom.service.auth.ratelimit import LoginRateLimiter
from loom.service.auth.sessions import AuthSessionInfo, AuthSessionStore

__all__ = [
    "AuthSessionInfo",
    "AuthSessionStore",
    "DUMMY_SCRYPT_HASH",
    "LoginRateLimiter",
    "ScryptPasswordError",
    "client_ip",
    "validate_scrypt_hash",
    "verify_password",
]
