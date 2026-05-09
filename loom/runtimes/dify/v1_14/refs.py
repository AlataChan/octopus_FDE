"""Dify variable-reference helpers."""
from __future__ import annotations

import re

_REF_RE = re.compile(
    r"\$\{([a-zA-Z_][a-zA-Z0-9_]*)(?:\.([^}]+))?\}"
)
_EXACT_REF_RE = re.compile(
    r"^\$\{([a-zA-Z_][a-zA-Z0-9_]*)(?:\.([^}]+))?\}$"
)


def to_dify_template_ref(value: str, node_id_map: dict[str, str]) -> str:
    """Convert IR `${node.field}` refs embedded in text to Dify `{{#node.field#}}`."""

    def repl(match: re.Match[str]) -> str:
        node_id = match.group(1)
        path = match.group(2) or ""
        if node_id == "input":
            return "{{#sys." + path + "#}}"
        dify_node_id = node_id_map.get(node_id, node_id)
        return "{{#" + ".".join(part for part in [dify_node_id, path] if part) + "#}}"

    return _REF_RE.sub(repl, value)


def to_dify_selector(value: str, node_id_map: dict[str, str], *, start_node_id: str) -> list[str]:
    """Convert a single IR var-ref to a Dify selector path."""
    parsed = parse_ref(value)
    if parsed is None:
        return [value]
    node_id, path = parsed
    if node_id == "input":
        return [start_node_id, *path]
    return [node_id_map.get(node_id, node_id), *path]


def parse_ref(value: str) -> tuple[str, list[str]] | None:
    """Return `(node_id, path_segments)` for an exact `${...}` ref."""
    match = _EXACT_REF_RE.match(value.strip())
    if not match:
        return None
    path = match.group(2) or ""
    return match.group(1), [part for part in path.split(".") if part]
