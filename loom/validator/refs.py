"""Variable-reference parser for IR strings.

Grammar (PRD §5):
    ref         := '${' identifier ('.' segment)+ '}'
    segment     := identifier | '[' digits ']'
    identifier  := [a-zA-Z_][a-zA-Z0-9_]*
    escape      := '$$' '{' ... '}'  # not a ref

A segment of '[i]' is preserved literally as the path entry "[i]" so the
typecheck layer can distinguish array index vs field access without a second
parse.
"""
from __future__ import annotations

import re
from dataclasses import dataclass


class RefParseError(ValueError):
    pass


@dataclass(frozen=True)
class VarRef:
    node_id: str
    path: tuple[str, ...]  # at least one segment


_IDENT = r"[a-zA-Z_][a-zA-Z0-9_]*"
_SEG = rf"(?:\.{_IDENT}|\[\d+\])"
_REF_RE = re.compile(rf"\$\{{({_IDENT})((?:{_SEG})+)\}}")
_ESCAPE_RE = re.compile(r"\$\$\{[^}]*\}")
_UNTERM_RE = re.compile(r"(?<!\$)\$\{[^}]*$")


def parse_refs(s: str) -> list[VarRef]:
    """Return all VarRefs in *s*. Empty list if none. Raise on syntax errors."""
    if _UNTERM_RE.search(s):
        raise RefParseError(f"unterminated reference in: {s!r}")

    # Mask escapes so they don't match.
    masked = _ESCAPE_RE.sub(lambda m: "X" * len(m.group(0)), s)

    # Quick syntactic check: any `${` that isn't matched by the ref regex is invalid.
    bare_dollars = [m.start() for m in re.finditer(r"(?<!\$)\$\{", masked)]
    matches = list(_REF_RE.finditer(masked))
    if len(bare_dollars) != len(matches):
        # Identify the first bad position.
        for pos in bare_dollars:
            if not any(m.start() == pos for m in matches):
                raise RefParseError(f"invalid reference at offset {pos} in {s!r}")

    out: list[VarRef] = []
    for m in matches:
        node_id = m.group(1)
        seg_text = m.group(2)
        segs = _split_segments(seg_text)
        if not segs:
            raise RefParseError(f"empty path in reference {m.group(0)!r}")
        out.append(VarRef(node_id=node_id, path=tuple(segs)))
    return out


def _split_segments(seg_text: str) -> list[str]:
    """'.b.c[0][1]' → ['b', 'c', '[0]', '[1]']"""
    segs: list[str] = []
    i = 0
    while i < len(seg_text):
        ch = seg_text[i]
        if ch == ".":
            j = i + 1
            while j < len(seg_text) and (seg_text[j].isalnum() or seg_text[j] == "_"):
                j += 1
            segs.append(seg_text[i + 1 : j])
            i = j
        elif ch == "[":
            j = seg_text.index("]", i) + 1
            segs.append(seg_text[i:j])  # keep brackets so callers can distinguish
            i = j
        else:
            raise RefParseError(f"unexpected segment char {ch!r}")
    return segs
