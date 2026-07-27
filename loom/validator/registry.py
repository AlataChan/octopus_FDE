"""FDE registry: handles + ACLs + scope filtering.

Phase 1 ships a single in-tree v1 registry. Phase 2A introduces the git-backed
versioned registry per PRD §8.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

_REGISTRY_ROOT = Path(__file__).resolve().parents[2] / "registry"


class RegistryEntryNotFound(KeyError):
    pass


def content_sha(raw: dict[str, Any]) -> str:
    """Digest the registry's actual handle content — never the self-reported
    "version" field, which lives in the same mutable file it's meant to pin.
    """
    payload = {k: v for k, v in raw.items() if k != "version"}
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return "sha:" + hashlib.sha256(canonical).hexdigest()[:40]


@dataclass(frozen=True)
class ToolEntry:
    handle: str
    description: str
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    side_effects: bool
    scopes: tuple[str, ...]


@dataclass(frozen=True)
class DatasetEntry:
    handle: str
    description: str
    scopes: tuple[str, ...]


@dataclass(frozen=True)
class CredentialEntry:
    handle: str
    description: str
    vault_path: str
    scopes: tuple[str, ...]
    # ADR 0003: HTTP-node auth bindings, not secret-value storage. Empty
    # allowed_hosts means "authorize no host" (fail closed) rather than
    # implicitly trusting a credential the registry hasn't fully described.
    auth_scheme: str = ""
    allowed_hosts: tuple[str, ...] = ()
    placement: str = ""
    require_tls: bool = True


@dataclass(frozen=True)
class Registry:
    version: str
    tools: dict[str, ToolEntry] = field(default_factory=dict)
    datasets: dict[str, DatasetEntry] = field(default_factory=dict)
    credentials: dict[str, CredentialEntry] = field(default_factory=dict)

    @staticmethod
    @lru_cache(maxsize=8)
    def load(version: str) -> Registry:
        path = _REGISTRY_ROOT / version / "registry.json"
        raw = json.loads(path.read_text())
        tools = {t["handle"]: ToolEntry(
            handle=t["handle"], description=t["description"],
            input_schema=t["input_schema"], output_schema=t["output_schema"],
            side_effects=t.get("side_effects", False),
            scopes=tuple(t.get("scopes", [])),
        ) for t in raw.get("tools", [])}
        datasets = {d["handle"]: DatasetEntry(
            handle=d["handle"], description=d["description"],
            scopes=tuple(d.get("scopes", [])),
        ) for d in raw.get("datasets", [])}
        credentials = {c["handle"]: CredentialEntry(
            handle=c["handle"], description=c["description"],
            vault_path=c["vault_path"], scopes=tuple(c.get("scopes", [])),
            auth_scheme=c.get("auth_scheme", ""),
            allowed_hosts=tuple(c.get("allowed_hosts", [])),
            placement=c.get("placement", ""),
            require_tls=c.get("require_tls", True),
        ) for c in raw.get("credentials", [])}
        return Registry(
            version=content_sha(raw),
            tools=tools, datasets=datasets, credentials=credentials,
        )

    def resolve_tool(self, handle: str, *, scope: str) -> ToolEntry:
        entry = self.tools.get(handle)
        if entry is None or scope not in entry.scopes:
            raise RegistryEntryNotFound(
                f"tool {handle!r} not in registry or out of scope {scope!r}"
            )
        return entry

    def resolve_dataset(self, handle: str, *, scope: str) -> DatasetEntry:
        entry = self.datasets.get(handle)
        if entry is None or scope not in entry.scopes:
            raise RegistryEntryNotFound(
                f"dataset {handle!r} not in registry or out of scope {scope!r}"
            )
        return entry

    def resolve_credential(self, handle: str, *, scope: str) -> CredentialEntry:
        entry = self.credentials.get(handle)
        if entry is None or scope not in entry.scopes:
            raise RegistryEntryNotFound(
                f"credential {handle!r} not in registry or out of scope {scope!r}"
            )
        return entry
