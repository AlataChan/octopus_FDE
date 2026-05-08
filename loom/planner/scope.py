"""Scope-based registry filtering for the Planner prompt."""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from loom.validator.registry import Registry


def render_registry_block(reg: Registry, *, scope: str) -> str:
    tools = sorted([t for t in reg.tools.values() if scope in t.scopes], key=lambda t: t.handle)
    datasets = sorted([d for d in reg.datasets.values() if scope in d.scopes], key=lambda d: d.handle)
    creds = sorted([c for c in reg.credentials.values() if scope in c.scopes], key=lambda c: c.handle)
    parts: list[str] = ["## Declared registry", f"Scope: `{scope}`", ""]
    parts.append("### Tools")
    for t in tools:
        side = " [side_effects]" if t.side_effects else ""
        parts.append(f"- `{t.handle}`{side}: {t.description}")
    parts.append("\n### Datasets")
    for d in datasets:
        parts.append(f"- `{d.handle}`: {d.description}")
    parts.append("\n### Credentials")
    for c in creds:
        parts.append(f"- `{c.handle}`: {c.description}")
    return "\n".join(parts)
