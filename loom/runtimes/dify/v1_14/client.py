"""Thin Dify HTTP client used by the conformance harness and Phase 1+ Compiler.

Phase 0 only needs: health, import_dsl, export_dsl, publish, get_app.
We deliberately keep this small — the per-version Compiler module owns the
DSL emit logic; this module owns network only.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, cast

import httpx


@dataclass(frozen=True)
class DifyApp:
    id: str
    name: str
    draft_id: str | None = None


class DifyClient:
    def __init__(self, *, base_url: str, api_key: str, timeout: float = 30.0):
        self._client = httpx.Client(
            base_url=base_url.rstrip("/"),
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=timeout,
        )

    def close(self) -> None:
        self._client.close()

    def health(self) -> bool:
        r = self._client.get("/health")
        return r.status_code == 200

    def import_dsl(self, *, name: str, dsl_yaml: str) -> DifyApp:
        r = self._client.post(
            "/console/api/apps/import",
            json={"mode": "yaml", "name": name, "yaml_content": dsl_yaml},
        )
        r.raise_for_status()
        body = r.json()
        return DifyApp(id=body["app_id"], name=name, draft_id=body.get("draft_id"))

    def export_dsl(self, *, app_id: str) -> str:
        r = self._client.get(f"/console/api/apps/{app_id}/export")
        r.raise_for_status()
        return cast("str", r.json()["yaml_content"])

    def publish(self, *, app_id: str) -> None:
        r = self._client.post(f"/console/api/apps/{app_id}/publish")
        r.raise_for_status()

    def get_app(self, *, app_id: str) -> dict[str, Any]:
        r = self._client.get(f"/console/api/apps/{app_id}")
        r.raise_for_status()
        return cast("dict[str, Any]", r.json())
