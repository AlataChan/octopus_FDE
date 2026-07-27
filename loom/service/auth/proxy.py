"""Client IP extraction with explicit trusted-proxy opt-in."""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi import Request


def client_ip(request: Request, *, trusted_proxy: bool) -> str:
    if trusted_proxy:
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            first = forwarded_for.split(",", 1)[0].strip()
            if first:
                return first
    if request.client is None:
        return "unknown"
    return request.client.host
