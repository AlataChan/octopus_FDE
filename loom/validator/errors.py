"""Structured Validator errors.

The shape mirrors loom.planner.types.FailureRecord so the Planner can read
ValidationFailure objects directly into a corrective prompt.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from collections.abc import Iterable

Bucket = Literal["schema", "reference", "type_flow", "policy"]


@dataclass(frozen=True)
class ValidationFailure:
    bucket: Bucket
    detail: str
    location: str | None = None


def fmt_for_planner(failures: Iterable[ValidationFailure]) -> str:
    """Render failures as a numbered list the Planner can act on."""
    lines = []
    for i, f in enumerate(failures, 1):
        loc = f" at `{f.location}`" if f.location else ""
        lines.append(f"{i}. [{f.bucket}]{loc}: {f.detail}")
    return "\n".join(lines) if lines else "(no failures)"
