"""FDE registry: handles + ACLs + scope filtering.

Phase 1 ships a single in-tree v1 registry. Phase 2A introduces the git-backed
versioned registry per PRD §8.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

_REGISTRY_ROOT = Path(__file__).resolve().parents[2] / "registry"


class RegistryEntryNotFound(KeyError):
    pass


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
        ) for c in raw.get("credentials", [])}
        return Registry(
            version=f"sha:{raw['version'][4:]}" if raw["version"].startswith("sha:")
            else "sha:0000000",
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
