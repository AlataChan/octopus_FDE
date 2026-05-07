"""Canonical Dify-AST hashing. PRD §6 — invariant under Dify import/export
normalization (whitespace, key order, default-stripping); changes only on
semantically meaningful edits.

The default-stripping list and the order-independent-compound list are
**owned by FDE** and **versioned with the IR schema**. When Dify changes its
import-path defaults, this module is the place we update. Update path:
1. Re-run scripts/round_trip_proof.py to confirm a new false-drift root cause.
2. Add the affected key/path here.
3. Bump CANONICAL_AST_VERSION.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, cast

import yaml  # type: ignore[import-untyped]

CANONICAL_AST_VERSION = "1"

# Top-level paths whose value Dify silently sets on import. Stripped before
# hashing. Keep aligned with the pinned Dify version (ADR 0002).
_STRIP_DEFAULTS: list[tuple[str, Any]] = [
    ("app.icon", ""),
    ("app.description", ""),
    ("workflow.graph.nodes", []),
    ("workflow.graph.edges", []),
]

# Lists whose order is not semantically significant. Sorted before hashing.
_ORDER_INVARIANT_LISTS: list[str] = [
    "workflow.nodes",
    "workflow.edges",
]


def canonical_dify_ast(yaml_text: str) -> dict[str, Any]:
    """Parse Dify DSL YAML to a canonical Python dict."""
    raw = yaml.safe_load(yaml_text) or {}
    return cast("dict[str, Any]", _canon(raw, path=""))


def canonical_dify_ast_hash(yaml_text: str) -> str:
    """SHA-256 of the canonical AST."""
    canon = canonical_dify_ast(yaml_text)
    payload = json.dumps(
        {"v": CANONICAL_AST_VERSION, "ast": canon},
        sort_keys=True, ensure_ascii=False, separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _canon(value: Any, *, path: str) -> Any:
    if isinstance(value, dict):
        # Strip defaults rooted here.
        for p, default in _STRIP_DEFAULTS:
            if _path_join(path, "") == "" and p.startswith(path):
                _strip_at(value, _suffix(p, path), default)
            elif p == path + "." + (path and "."):
                pass
        cleaned: dict[str, Any] = {}
        for k in sorted(value.keys()):
            child_path = _path_join(path, k)
            cleaned[k] = _canon(value[k], path=child_path)
        return cleaned
    if isinstance(value, list):
        rendered = [_canon(v, path=path) for v in value]
        if path in _ORDER_INVARIANT_LISTS:
            return sorted(
                rendered,
                key=lambda x: json.dumps(x, sort_keys=True, ensure_ascii=False),
            )
        return rendered
    return value


def _path_join(parent: str, child: str) -> str:
    return f"{parent}.{child}" if parent else child


def _suffix(full: str, prefix: str) -> str:
    if not prefix:
        return full
    return full[len(prefix) + 1:] if full.startswith(prefix + ".") else full


def _strip_at(node: dict[str, Any], rel_path: str, default: Any) -> None:
    parts = rel_path.split(".") if rel_path else []
    cur: Any = node
    parents: list[tuple[dict[str, Any], str]] = []
    for p in parts[:-1]:
        if not isinstance(cur, dict) or p not in cur:
            return
        parents.append((cur, p))
        cur = cur[p]
    if not parts:
        return
    last = parts[-1]
    if isinstance(cur, dict) and cur.get(last) == default:
        cur.pop(last, None)
        for parent, key in reversed(parents):
            child = parent.get(key)
            if isinstance(child, dict) and not child:
                parent.pop(key, None)
            else:
                break
