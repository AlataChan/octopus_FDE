"""IR TypeName -> Hiagent numeric Type code mapping.

Per ADR 0024 §Type code table. Best-guess based on customer sample;
revised in-place at first real customer import.

Table:
   IR `string`                      -> 0
   IR `number`                      -> 3
   IR `boolean`                     -> 2
   IR `object` / `json`             -> 9
   IR `string[]` / `number[]` / `json[]` -> 5
   IR `null`                        -> 6
   IR `any` / `chunks` / `file`     -> 0  [string fallback]
"""
from __future__ import annotations


class UnmappableTypeError(ValueError):
    pass


_MAP = {
    "string": 0,
    "number": 3,
    "boolean": 2,
    "null": 6,
    "json": 9,
    "string[]": 5,
    "number[]": 5,
    "json[]": 5,
    "chunks": 0,
    "file": 0,
    "any": 0,
}


def to_hiagent_type_code(ir_type: str) -> int:
    """Return Hiagent Type code for the IR type name.

    Raises UnmappableTypeError for compound IR types [array<T>, object<{...}>,
    union<...>] that the v2.6 schema cannot express directly. Compounds must
    be flattened by the caller [validator owns this]; reaching this function
    with one is a compiler bug.
    """
    if ir_type in _MAP:
        return _MAP[ir_type]
    if ir_type.startswith(("array<", "object<", "union<")):
        raise UnmappableTypeError(
            f"compound IR type {ir_type!r} must be flattened before Hiagent emit"
        )
    raise UnmappableTypeError(f"unknown IR type {ir_type!r}")
