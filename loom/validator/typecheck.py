"""IR type-flow checker.

Implements PRD §5 type system:
 - primitives: string, number, boolean, null, json, file, any, chunks
 - compounds:  array<T>, object<{k: T, ...}>, union<T1 | T2 | ...>
 - branch narrowing on type-guard predicates
 - loop item typing
 - parallel merge typing (concat / object_merge / first_success)
 - explicit coercion only (no implicit string <-> number)
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from loom.validator.errors import ValidationFailure

if TYPE_CHECKING:
    from collections.abc import Iterable


class TypeMismatch(ValueError):
    pass


@dataclass(frozen=True)
class TypeExpr:
    name: str  # "string" | "number" | "array" | "object" | "union" | ...
    params: tuple[TypeExpr, ...] = ()
    # for object:
    fields: tuple[tuple[str, TypeExpr], ...] = ()


def _t(name: str, *params: TypeExpr) -> TypeExpr:
    return TypeExpr(name=name, params=tuple(params))


_PRIMITIVES = {"string", "number", "boolean", "null", "json", "file", "any", "chunks"}


def parse_type(s: str) -> TypeExpr:
    s = s.strip()
    if s in _PRIMITIVES:
        return _t(s)
    if s.endswith("[]"):
        # legacy short form (string[], number[], json[])
        return _t("array", parse_type(s[:-2]))
    if s.startswith("array<") and s.endswith(">"):
        return _t("array", parse_type(s[len("array<") : -1]))
    if s.startswith("union<") and s.endswith(">"):
        body = s[len("union<") : -1]
        members = [parse_type(p.strip()) for p in _split_top(body, "|")]
        return TypeExpr(name="union", params=tuple(members))
    if s.startswith("object<{") and s.endswith("}>"):
        body = s[len("object<{") : -2]
        fields: list[tuple[str, TypeExpr]] = []
        for piece in _split_top(body, ","):
            k, _, v = piece.partition(":")
            fields.append((k.strip(), parse_type(v.strip())))
        return TypeExpr(name="object", fields=tuple(fields))
    raise TypeMismatch(f"unparseable type {s!r}")


def _split_top(s: str, sep: str) -> list[str]:
    out: list[str] = []
    depth = 0
    buf: list[str] = []
    for ch in s:
        if ch in "<{(":
            depth += 1
        elif ch in ">})":
            depth -= 1
        if ch == sep and depth == 0:
            out.append("".join(buf))
            buf = []
        else:
            buf.append(ch)
    if buf:
        out.append("".join(buf))
    return out


@dataclass(frozen=True)
class NodeOutputs:
    """Map output-name -> type expression."""
    fields: dict[str, TypeExpr] = field(default_factory=dict)

    def get_path(self, path: tuple[str, ...]) -> TypeExpr:
        if not path:
            raise TypeMismatch("empty path")
        head, *rest = path
        cur = self.fields.get(head)
        if cur is None:
            raise TypeMismatch(f"output {head!r} not declared")
        for seg in rest:
            cur = _step(cur, seg)
        return cur


def _step(t: TypeExpr, seg: str) -> TypeExpr:
    # Array index "[i]"
    if re.fullmatch(r"\[\d+\]", seg):
        if t.name != "array":
            raise TypeMismatch(f"index {seg} on non-array {t.name}")
        return t.params[0]
    # Field
    if t.name == "object":
        for k, v in t.fields:
            if k == seg:
                return v
        raise TypeMismatch(f"field {seg!r} not on object")
    if t.name == "json" or t.name == "any":
        return t  # json/any propagate
    raise TypeMismatch(f"cannot step {seg!r} into {t.name}")


def typecheck_edge(src: NodeOutputs, *, ref_path: tuple[str, ...], expected: TypeExpr) -> None:
    actual = src.get_path(ref_path)
    if not _assignable(actual, expected):
        raise TypeMismatch(f"actual {actual.name} not assignable to expected {expected.name}")


def _assignable(a: TypeExpr, b: TypeExpr) -> bool:
    if b.name == "any" or a.name == "any":
        return True
    if a.name != b.name:
        return False
    if a.name == "array":
        return _assignable(a.params[0], b.params[0])
    if a.name == "object":
        bfields = dict(b.fields)
        return all(k in bfields and _assignable(v, bfields[k]) for k, v in a.fields)
    if a.name == "union":
        return all(any(_assignable(am, bm) for bm in b.params) for am in a.params)
    return True


_TYPE_GUARD_RE = re.compile(r"^\s*\$\{[^}]+\}\s*!=\s*null\s*$")


def narrow_branch(t: TypeExpr, *, predicate: str) -> TypeExpr:
    if t.name == "union" and _TYPE_GUARD_RE.match(predicate):
        non_null = [m for m in t.params if m.name != "null"]
        if len(non_null) == 1:
            return non_null[0]
        return TypeExpr(name="union", params=tuple(non_null))
    return t


def loop_item_type(over: TypeExpr) -> tuple[TypeExpr, TypeExpr]:
    if over.name != "array":
        raise TypeMismatch(f"loop over non-array {over.name}")
    return over.params[0], _t("number")


def parallel_merge_type(strategy: str, branches: Iterable[TypeExpr], *, branch_keys: list[str]) -> TypeExpr:
    branches = list(branches)
    if strategy == "concat":
        first = branches[0]
        if not all(_assignable(b, first) and _assignable(first, b) for b in branches[1:]):
            raise TypeMismatch("concat requires all branches to share a common type")
        return _t("array", first)
    if strategy == "object_merge":
        return TypeExpr(name="object", fields=tuple((k, b) for k, b in zip(branch_keys, branches, strict=False)))
    if strategy == "first_success":
        return TypeExpr(name="union", params=tuple(branches))
    raise TypeMismatch(f"unknown merge_strategy {strategy!r}")


def to_failure(e: TypeMismatch, *, location: str | None = None) -> ValidationFailure:
    return ValidationFailure(bucket="type_flow", detail=str(e), location=location)
