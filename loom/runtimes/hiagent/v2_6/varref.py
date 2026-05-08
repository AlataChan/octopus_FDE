"""IR variable reference parser.

IR uses string-form `${node_id.field}` / `${node_id.field.subfield}` /
`${node_id.field[0]}`. The Hiagent compiler converts these into structured
{NodeCode, Path, RefType} objects per ADR 0024 §Variable reference
translation. This module owns only the parse step; the per-node emit
functions in compiler_nodes.py construct the full reference object using
the consuming node's binding context.
"""
from __future__ import annotations

import re

_REF_RE = re.compile(
    r"^\$\{([a-zA-Z_][a-zA-Z0-9_]*)((?:\.[a-zA-Z_][a-zA-Z0-9_]*|\[\d+\])*)\}$"
)


class VarRefParseError(ValueError):
    pass


def parse_varref(s: str) -> tuple[str, str]:
    """Parse a single ${node_id.path} string into (node_id, dotted_path).

    Examples:
      '${rerank.confidence}' -> ('rerank', 'confidence')
      '${a.b.c}'             -> ('a', 'b.c')
      '${arr[0].x}'          -> ('arr', '[0].x')
      '${node}'              -> raises VarRefParseError [empty path not allowed]

    The returned dotted_path keeps brackets verbatim so the caller can
    distinguish array indexing from field access without a second parse.
    """
    s = s.strip()
    m = _REF_RE.match(s)
    if not m:
        raise VarRefParseError(f"not a valid var-ref: {s!r}")
    node_id, raw_segs = m.group(1), m.group(2)
    if not raw_segs:
        raise VarRefParseError(f"empty path in var-ref: {s!r}")
    # raw_segs starts with "." [field] or "[" [index]; normalize to dotted
    parts: list[str] = []
    i = 0
    while i < len(raw_segs):
        if raw_segs[i] == ".":
            j = i + 1
            while j < len(raw_segs) and (raw_segs[j].isalnum() or raw_segs[j] == "_"):
                j += 1
            parts.append(raw_segs[i + 1 : j])
            i = j
        elif raw_segs[i] == "[":
            j = raw_segs.index("]", i) + 1
            parts.append(raw_segs[i:j])
            i = j
        else:
            raise VarRefParseError(f"unexpected segment char {raw_segs[i]!r}")
    return node_id, ".".join(parts)


def is_varref(s: str) -> bool:
    """True if s is exactly one ${...} reference [no surrounding text]."""
    return bool(_REF_RE.match(s.strip()))


def find_varrefs(s: str) -> list[tuple[str, str]]:
    """Find every ${...} ref embedded in a larger string.

    Returns list of (node_id, dotted_path) tuples in document order.
    Used for things like LLM prompt strings that may contain multiple refs.
    """
    pattern = re.compile(
        r"\$\{([a-zA-Z_][a-zA-Z0-9_]*)((?:\.[a-zA-Z_][a-zA-Z0-9_]*|\[\d+\])*)\}"
    )
    out: list[tuple[str, str]] = []
    for m in pattern.finditer(s):
        node_id, raw_segs = m.group(1), m.group(2)
        if not raw_segs:
            continue
        # Reuse the same segment splitter as parse_varref by reconstructing
        full = "${" + node_id + raw_segs + "}"
        try:
            out.append(parse_varref(full))
        except VarRefParseError:
            continue
    return out
