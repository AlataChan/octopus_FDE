"""In-memory auth session store keyed by sha256(token)."""
from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta


@dataclass
class AuthSessionInfo:
    username: str
    created_at: datetime
    expires_at: datetime
    last_seen_at: datetime


class AuthSessionStore:
    def __init__(self, *, ttl_hours: int = 24):
        self.ttl = timedelta(hours=ttl_hours)
        self._sessions: dict[str, AuthSessionInfo] = {}
        self._expired: list[AuthSessionInfo] = []

    def create(self, *, username: str) -> tuple[str, AuthSessionInfo]:
        now = _now()
        token = secrets.token_urlsafe(32)
        info = AuthSessionInfo(
            username=username,
            created_at=now,
            expires_at=now + self.ttl,
            last_seen_at=now,
        )
        self._sessions[_token_key(token)] = info
        return token, info

    def validate(self, token: str | None) -> AuthSessionInfo | None:
        if not token:
            return None
        key = _token_key(token)
        info = self._sessions.get(key)
        if info is None:
            return None
        now = _now()
        if info.expires_at <= now:
            self._sessions.pop(key, None)
            self._expired.append(info)
            return None
        info.last_seen_at = now
        info.expires_at = now + self.ttl
        return info

    def revoke(self, token: str | None) -> AuthSessionInfo | None:
        if not token:
            return None
        return self._sessions.pop(_token_key(token), None)

    def cleanup_expired(self) -> list[AuthSessionInfo]:
        now = _now()
        expired: list[AuthSessionInfo] = []
        for key, info in list(self._sessions.items()):
            if info.expires_at <= now:
                expired.append(info)
                self._sessions.pop(key, None)
        self._expired.extend(expired)
        return expired

    def drain_expired(self) -> list[AuthSessionInfo]:
        expired = list(self._expired)
        self._expired.clear()
        return expired


def _token_key(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _now() -> datetime:
    return datetime.now(UTC)
