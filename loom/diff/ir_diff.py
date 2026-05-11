"""Semantic diff for IR JSON documents.

The console uses this compact change list for reviewer-facing iteration:
node and edge additions/removals, node rename/config changes, and changed
field paths only.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

JsonObj = Mapping[str, Any]


def diff_ir(before: JsonObj, after: JsonObj) -> dict[str, Any]:
    """Return a semantic change list between two IR-like JSON documents."""
    changes: list[dict[str, Any]] = []
    before_nodes = _node_map(before)
    after_nodes = _node_map(after)

    for node_id in sorted(before_nodes.keys() - after_nodes.keys()):
        changes.append({"scope": "node", "kind": "removed", "node_id": node_id})
    for node_id in sorted(after_nodes.keys() - before_nodes.keys()):
        changes.append({"scope": "node", "kind": "added", "node_id": node_id})

    for node_id in sorted(before_nodes.keys() & after_nodes.keys()):
        old = before_nodes[node_id]
        new = after_nodes[node_id]
        if _display_name(old) != _display_name(new):
            changes.append(
                {
                    "scope": "node",
                    "kind": "renamed",
                    "node_id": node_id,
                    "before": _display_name(old),
                    "after": _display_name(new),
                }
            )
        fields = _field_changes(
            _config_view(old),
            _config_view(new),
        )
        if fields:
            changes.append(
                {
                    "scope": "node",
                    "kind": "config-changed",
                    "node_id": node_id,
                    "fields": fields,
                }
            )

    before_edges = _edge_set(before)
    after_edges = _edge_set(after)
    for src, dst in sorted(before_edges - after_edges):
        changes.append({"scope": "edge", "kind": "removed", "from": src, "to": dst})
    for src, dst in sorted(after_edges - before_edges):
        changes.append({"scope": "edge", "kind": "added", "from": src, "to": dst})

    return {
        "changes": changes,
        "summary": {
            "nodes": sum(1 for c in changes if c["scope"] == "node"),
            "edges": sum(1 for c in changes if c["scope"] == "edge"),
            "total": len(changes),
        },
    }


def _node_map(doc: JsonObj) -> dict[str, dict[str, Any]]:
    nodes = doc.get("nodes", [])
    if not isinstance(nodes, list):
        return {}
    out: dict[str, dict[str, Any]] = {}
    for node in nodes:
        if isinstance(node, dict) and isinstance(node.get("id"), str):
            out[node["id"]] = node
    return out


def _edge_set(doc: JsonObj) -> set[tuple[str, str]]:
    edges = doc.get("edges", [])
    if not isinstance(edges, list):
        return set()
    out: set[tuple[str, str]] = set()
    for edge in edges:
        if not isinstance(edge, dict):
            continue
        src = edge.get("from") or edge.get("from_")
        dst = edge.get("to")
        if isinstance(src, str) and isinstance(dst, str):
            out.add((src, dst))
    return out


def _display_name(node: JsonObj) -> str | None:
    for key in ("name", "title", "label"):
        value = node.get(key)
        if isinstance(value, str):
            return value
    return None


def _config_view(node: JsonObj) -> dict[str, Any]:
    ignored = {"id", "name", "title", "label"}
    return {key: value for key, value in node.items() if key not in ignored}


def _field_changes(before: Any, after: Any, path: str = "") -> list[dict[str, Any]]:
    if before == after:
        return []
    if isinstance(before, dict) and isinstance(after, dict):
        changes: list[dict[str, Any]] = []
        for key in sorted(before.keys() | after.keys()):
            child_path = f"{path}.{key}" if path else str(key)
            if key not in before:
                changes.append({"path": child_path, "before": None, "after": after[key]})
            elif key not in after:
                changes.append({"path": child_path, "before": before[key], "after": None})
            else:
                changes.extend(_field_changes(before[key], after[key], child_path))
        return changes
    return [{"path": path, "before": before, "after": after}]
