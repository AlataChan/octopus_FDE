"""Hiagent server-style ID generator.

Hiagent IDs in customer samples follow ^[a-z0-9]{20}$ pattern, e.g.,
'd7ji7kd4shhcm7cr99hg'. We generate fresh client-side IDs when emitting
new nodes / workflows; self-hosted Hiagent accepts client-generated IDs
on fresh import [verified at first customer import per ADR 0024].
"""
from __future__ import annotations

import secrets

_ALPHABET = "abcdefghijklmnopqrstuvwxyz0123456789"


def gen_id() -> str:
    """Return a fresh 20-char lowercase alphanumeric ID."""
    return "".join(secrets.choice(_ALPHABET) for _ in range(20))


def is_valid_id(s: str) -> bool:
    """True if s matches Hiagent's ID pattern."""
    if len(s) != 20:
        return False
    return all(c in _ALPHABET for c in s)
