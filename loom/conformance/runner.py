"""Conformance runner.

A `ConformanceCase` is a self-contained test: take an IR doc, compile it (Phase 1
will inject the real compiler — for Phase 0 a stub `compile_ir` is used and most
cases skip until Phase 1 lands), push to Dify, run with given inputs, assert the
expected outcome.

For Phase 0, the runner exists so the matrix shape is fixed. The actual
end-to-end execution is wired up in Task 14 (baseline run) and Phase 1.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable

    from loom.ir.models import IRDocument


@dataclass(frozen=True)
class ConformanceCase:
    """A single conformance test instance.

    `inputs`:  the inputs to pass when triggering the deployed Dify workflow.
    `expect`:  callable(run_result) -> None; raises on assertion failure.
    """
    ir: IRDocument
    inputs: dict[str, Any]
    expect: Callable[[dict[str, Any]], None]


@dataclass(frozen=True)
class MatrixRow:
    id: str  # stable id, e.g. "loop_max_iterations"
    description: str  # one-line PRD §5 cell
    case_factory: Callable[[], ConformanceCase]
