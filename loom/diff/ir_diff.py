"""Structured semantic diff for IR JSON documents.

The console uses this change list for reviewer-facing iteration. Diffing
happens over the canonical IR (loom.ir.canonicalize) so explicit-vs-omitted
defaults never show up as noise. Every change is classified with a
`category` (identity/registry/credential/policy/compliance/schema/control/
config) and a `risk` ("high"/"low") so security- and execution-semantics-
relevant edits — a dropped guardrail, a swapped credential, a widened agent
budget, a flipped data/control edge, a changed branch condition — surface
even when the top-level node/edge counts look unchanged. High-risk changes
are echoed in `hard_blocks` for a reviewer-facing "must look at this" list.
"""
from __future__ import annotations

from typing import Any

from loom.ir.canonicalize import canonical_ir, default_for

JsonObj = dict[str, Any]

_SENSITIVE_FIELD_NAMES = {
    "credential", "credentials", "credential_id",
    "secret", "token", "api_key", "password",
}
_MAX_STRING_CHARS = 200
_MAX_LIST_ITEMS = 20

_GOVERNANCE_DICT_KEYS = ("metadata", "registry_ref", "policy")
_GOVERNANCE_PORT_KEYS = ("inputs", "outputs")


def diff_ir(before: JsonObj, after: JsonObj) -> dict[str, Any]:
    """Return a structured, risk-classified change list between two IR documents."""
    before_canon = canonical_ir(before)
    after_canon = canonical_ir(after)

    changes: list[dict[str, Any]] = []
    changes.extend(_governance_changes(before_canon, after_canon))
    changes.extend(_diff_node_list(
        before_canon.get("nodes") or [],
        after_canon.get("nodes") or [],
        path="",
    ))
    changes.extend(_edge_changes(
        before_canon.get("edges") or [],
        after_canon.get("edges") or [],
    ))

    hard_blocks = [c for c in changes if c.get("risk") == "high"]
    return {
        "changes": changes,
        "hard_blocks": hard_blocks,
        "summary": {
            "nodes": sum(1 for c in changes if c["scope"] == "node"),
            "edges": sum(1 for c in changes if c["scope"] == "edge"),
            "governance": sum(1 for c in changes if c["scope"] == "governance"),
            "total": len(changes),
            "hard_blocks": len(hard_blocks),
        },
    }


# ---- node tree (top-level nodes + nested loop/parallel children) --------

def _diff_node_list(before_nodes: list[Any], after_nodes: list[Any], *, path: str) -> list[dict[str, Any]]:
    before_map = _node_map(before_nodes)
    after_map = _node_map(after_nodes)
    changes: list[dict[str, Any]] = []

    for node_id in sorted(before_map.keys() - after_map.keys()):
        changes.append(_node_entry("removed", node_id, path))
    for node_id in sorted(after_map.keys() - before_map.keys()):
        changes.append(_node_entry("added", node_id, path))

    for node_id in sorted(before_map.keys() & after_map.keys()):
        old, new = before_map[node_id], after_map[node_id]
        if _display_name(old) != _display_name(new):
            entry = _node_entry("renamed", node_id, path)
            entry["before"] = _display_name(old)
            entry["after"] = _display_name(new)
            changes.append(entry)
        changes.extend(_node_config_change(old, new, node_id, path))
        changes.extend(_nested_node_changes(old, new, node_id, path))

    return changes


def _node_map(nodes: list[Any]) -> dict[str, JsonObj]:
    out: dict[str, JsonObj] = {}
    for node in nodes:
        if isinstance(node, dict) and isinstance(node.get("id"), str):
            out[node["id"]] = node
    return out


def _node_entry(kind: str, node_id: str, path: str) -> dict[str, Any]:
    entry: dict[str, Any] = {"scope": "node", "kind": kind, "node_id": node_id}
    if path:
        entry["path"] = path
    return entry


def _node_config_change(old: JsonObj, new: JsonObj, node_id: str, path: str) -> list[dict[str, Any]]:
    node_type = new.get("type") or old.get("type")
    exclude = _nested_list_fields(node_type)
    fields = _field_changes(_config_view(old, exclude), _config_view(new, exclude))
    if not fields:
        return []
    category, risk = _classify_node_fields(node_type, fields)
    entry: dict[str, Any] = {
        "scope": "node",
        "kind": "config-changed",
        "node_id": node_id,
        "fields": [_display_field(f) for f in fields],
        "category": category,
        "risk": risk,
    }
    if path:
        entry["path"] = path
    return [entry]


def _nested_node_changes(old: JsonObj, new: JsonObj, node_id: str, path: str) -> list[dict[str, Any]]:
    node_type = new.get("type") or old.get("type")
    if node_type == "loop":
        old_body = old.get("body") if isinstance(old.get("body"), list) else []
        new_body = new.get("body") if isinstance(new.get("body"), list) else []
        return _diff_node_list(old_body, new_body, path=_join_path(path, node_id, "body"))
    if node_type == "parallel":
        old_branches = old.get("branches") if isinstance(old.get("branches"), dict) else {}
        new_branches = new.get("branches") if isinstance(new.get("branches"), dict) else {}
        changes: list[dict[str, Any]] = []
        for branch_key in sorted(set(old_branches) | set(new_branches)):
            old_branch = old_branches.get(branch_key)
            new_branch = new_branches.get(branch_key)
            old_branch = old_branch if isinstance(old_branch, list) else []
            new_branch = new_branch if isinstance(new_branch, list) else []
            branch_path = _join_path(path, node_id, "branches", branch_key)
            changes.extend(_diff_node_list(old_branch, new_branch, path=branch_path))
        return changes
    return []


def _nested_list_fields(node_type: str | None) -> set[str]:
    if node_type == "loop":
        return {"body"}
    if node_type == "parallel":
        return {"branches"}
    return set()


def _join_path(*parts: str) -> str:
    return ".".join(p for p in parts if p)


def _config_view(node: JsonObj, exclude: set[str] = frozenset()) -> dict[str, Any]:
    ignored = {"id", "name", "title", "label", *exclude}
    return {key: value for key, value in node.items() if key not in ignored}


def _classify_node_fields(node_type: str | None, fields: list[dict[str, Any]]) -> tuple[str, str]:
    paths = [f["path"] for f in fields]
    if any(p == "type" for p in paths):
        return "control", "high"
    if node_type == "http" and any(p == "credential" for p in paths):
        return "credential", "high"
    if node_type == "condition" and any(p.startswith("branches") for p in paths):
        return "control", "high"
    if node_type == "agent" and any(p.startswith("budget") for p in paths):
        return "policy", "high" if _budget_widened(fields, "budget") else "low"
    if node_type == "agent" and any(p == "tools" or p.startswith("tools") for p in paths):
        return "registry", "low"
    return "config", "low"


_BUDGET_NUMERIC_FIELDS = {"max_iterations", "max_tokens", "max_wall_clock_s"}


def _budget_widened(fields: list[dict[str, Any]], prefix: str) -> bool:
    for f in fields:
        path = f["path"]
        if not (path == prefix or path.startswith(prefix + ".")):
            continue
        leaf = path.rsplit(".", 1)[-1]
        if leaf not in _BUDGET_NUMERIC_FIELDS:
            continue
        before_v, after_v = f["before"], f["after"]
        if isinstance(before_v, (int, float)) and isinstance(after_v, (int, float)) and after_v > before_v:
            return True
    return False


def _display_name(node: JsonObj) -> str | None:
    for key in ("name", "title", "label"):
        value = node.get(key)
        if isinstance(value, str):
            return value
    return None


# ---- top-level governance fields -----------------------------------------

def _governance_changes(before: JsonObj, after: JsonObj) -> list[dict[str, Any]]:
    changes: list[dict[str, Any]] = []
    for key in _GOVERNANCE_DICT_KEYS:
        old_v, new_v = before.get(key), after.get(key)
        if old_v == new_v:
            continue
        old_d = old_v if isinstance(old_v, dict) else {}
        new_d = new_v if isinstance(new_v, dict) else {}
        fields = _field_changes(old_d, new_d)
        if not fields:
            continue
        changes.append(_governance_entry(key, fields))
    for key in _GOVERNANCE_PORT_KEYS:
        old_v, new_v = before.get(key), after.get(key)
        if old_v == new_v:
            continue
        old_l = old_v if isinstance(old_v, list) else []
        new_l = new_v if isinstance(new_v, list) else []
        fields = _keyed_list_diff(old_l, new_l, "name")
        if not fields:
            continue
        changes.append(_governance_entry(key, fields))
    return changes


def _governance_entry(key: str, fields: list[dict[str, Any]]) -> dict[str, Any]:
    category, risk = _classify_governance(key, fields)
    return {
        "scope": "governance",
        "kind": "changed",
        "key": key,
        "fields": [_display_field(f) for f in fields],
        "category": category,
        "risk": risk,
    }


def _classify_governance(key: str, fields: list[dict[str, Any]]) -> tuple[str, str]:
    paths = [f["path"] for f in fields]
    if key == "registry_ref":
        if any(p == "credentials" or p.startswith("credentials.") or p.startswith("credentials[") for p in paths):
            return "credential", "high"
        return "registry", "low"
    if key == "policy":
        if any(p.startswith("guardrails") or p.startswith("audit") for p in paths):
            return "compliance", "high"
        if any(p.startswith("escalation") for p in paths):
            return "compliance", "high"
        if any(p.startswith("agent_budget") for p in paths):
            return "policy", "high" if _budget_widened(fields, "agent_budget") else "low"
        return "policy", "low"
    if key in ("inputs", "outputs"):
        return "schema", "high"
    return "identity", "low"


def _keyed_list_diff(before_list: list[Any], after_list: list[Any], id_key: str) -> list[dict[str, Any]]:
    before_map = {
        item[id_key]: item for item in before_list
        if isinstance(item, dict) and isinstance(item.get(id_key), str)
    }
    after_map = {
        item[id_key]: item for item in after_list
        if isinstance(item, dict) and isinstance(item.get(id_key), str)
    }
    fields: list[dict[str, Any]] = []
    for key in sorted(before_map.keys() - after_map.keys()):
        fields.append({"path": f"[{key}]", "before": before_map[key], "after": None})
    for key in sorted(after_map.keys() - before_map.keys()):
        fields.append({"path": f"[{key}]", "before": None, "after": after_map[key]})
    for key in sorted(before_map.keys() & after_map.keys()):
        fields.extend(_field_changes(before_map[key], after_map[key], path=f"[{key}]"))
    return fields


# ---- edges: identity is (from, to); when/data are attributes, not identity

def _edge_changes(before_edges: list[Any], after_edges: list[Any]) -> list[dict[str, Any]]:
    before_map = _edge_map(before_edges)
    after_map = _edge_map(after_edges)
    changes: list[dict[str, Any]] = []

    for key in sorted(before_map.keys() - after_map.keys()):
        changes.append({"scope": "edge", "kind": "removed", "from": key[0], "to": key[1]})
    for key in sorted(after_map.keys() - before_map.keys()):
        changes.append({"scope": "edge", "kind": "added", "from": key[0], "to": key[1]})

    for key in sorted(before_map.keys() & after_map.keys()):
        old_e, new_e = before_map[key], after_map[key]
        fields: list[dict[str, Any]] = []
        old_when, new_when = old_e.get("when"), new_e.get("when")
        if old_when != new_when:
            fields.append({"path": "when", "before": old_when, "after": new_when})
        old_data, new_data = old_e.get("data", True), new_e.get("data", True)
        if old_data != new_data:
            fields.append({"path": "data", "before": old_data, "after": new_data})
        if not fields:
            continue
        changes.append({
            "scope": "edge",
            "kind": "changed",
            "from": key[0],
            "to": key[1],
            "fields": [_display_field(f) for f in fields],
            "category": "control",
            "risk": "high",
        })

    return changes


def _edge_map(edges: list[Any]) -> dict[tuple[str, str], JsonObj]:
    out: dict[tuple[str, str], JsonObj] = {}
    for edge in edges:
        if not isinstance(edge, dict):
            continue
        src = edge.get("from") or edge.get("from_")
        dst = edge.get("to")
        if isinstance(src, str) and isinstance(dst, str):
            out[(src, dst)] = edge
    return out


# ---- generic field diff + display masking --------------------------------

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


def _display_field(field: dict[str, Any]) -> dict[str, Any]:
    field = _resolve_stripped_default(field)
    leaf = field["path"].rsplit(".", 1)[-1].split("[", 1)[0]
    if leaf in _SENSITIVE_FIELD_NAMES:
        return {**field, "before": _mask(field["before"]), "after": _mask(field["after"])}
    return {**field, "before": _truncate(field["before"]), "after": _truncate(field["after"])}


def _resolve_stripped_default(field: dict[str, Any]) -> dict[str, Any]:
    """Fill in a canonicalization-stripped default instead of showing None.

    Diffing runs over the canonical IR (see `diff_ir`), so a field equal to
    its schema default on one side is simply absent there. Showing that as
    a bare `None` reads as "field removed"; showing the real default value
    is what a reviewer actually needs to see.
    """
    if field["before"] is not None and field["after"] is not None:
        return field
    path = field["path"]
    leaf = path.rsplit(".", 1)[-1].split("[", 1)[0]
    if leaf in ("top_k", "rerank"):
        kind = "RetrievalNode"
    elif path.endswith("retry.backoff"):
        kind = "Retry"
    elif leaf == "required" and "[" in path:
        kind = "PortDecl"
    else:
        return field
    has_default, default_value = default_for(kind, leaf)
    if not has_default:
        return field
    resolved = dict(field)
    if resolved["before"] is None:
        resolved["before"] = default_value
    if resolved["after"] is None:
        resolved["after"] = default_value
    return resolved


def _mask(value: Any) -> Any:
    return None if value is None else "***"


def _truncate(value: Any) -> Any:
    if isinstance(value, str) and len(value) > _MAX_STRING_CHARS:
        omitted = len(value) - _MAX_STRING_CHARS
        return f"{value[:_MAX_STRING_CHARS]}...(+{omitted} chars)"
    if isinstance(value, list) and len(value) > _MAX_LIST_ITEMS:
        omitted = len(value) - _MAX_LIST_ITEMS
        return [*value[:_MAX_LIST_ITEMS], f"...(+{omitted} more)"]
    return value
