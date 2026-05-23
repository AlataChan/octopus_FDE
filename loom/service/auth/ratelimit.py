"""Small in-memory login failure limiter."""
from __future__ import annotations

from collections import defaultdict, deque
from datetime import UTC, datetime, timedelta


class LoginRateLimiter:
    def __init__(self, *, max_failures: int = 5, window_seconds: int = 60, lock_seconds: int = 60):
        self.max_failures = max_failures
        self.window = timedelta(seconds=window_seconds)
        self.lock = timedelta(seconds=lock_seconds)
        self._failures: dict[str, deque[datetime]] = defaultdict(deque)
        self._locked_until: dict[str, datetime] = {}

    def is_limited(self, key: str) -> bool:
        now = _now()
        locked_until = self._locked_until.get(key)
        if locked_until is None:
            return False
        if locked_until <= now:
            self._locked_until.pop(key, None)
            self._failures.pop(key, None)
            return False
        return True

    def record_failure(self, key: str) -> None:
        now = _now()
        failures = self._failures[key]
        while failures and failures[0] <= now - self.window:
            failures.popleft()
        failures.append(now)
        if len(failures) >= self.max_failures:
            self._locked_until[key] = now + self.lock

    def reset(self, key: str) -> None:
        self._failures.pop(key, None)
        self._locked_until.pop(key, None)


def _now() -> datetime:
    return datetime.now(UTC)
