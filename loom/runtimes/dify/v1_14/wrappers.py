"""Synthesis wrappers for cells where pinned Dify lacks native IR semantics.

The list below is seeded by ADR 0002's cell table. Engineer: edit each wrapper
based on the conformance baseline; if the Dify version supports the cell
natively, the wrapper degenerates to a single emit.

The wrappers ARE the part most likely to change between Dify versions.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from loom.ir.models import AgentNode, HTTPNode, LoopNode, ParallelNode


def http(n: HTTPNode) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    base = {
        "id": n.id, "type": "http-request",
        "data": {
            "rationale": n.rationale,
            "method": n.method, "url": n.url,
            "headers": n.headers or {}, "body": n.body,
            "credential": n.credential,
            "timeout_s": n.timeout_s,
            "retry": n.retry.model_dump(exclude_none=True) if n.retry else None,
            "idempotency_key": n.idempotency_key,
        },
    }
    return [base], []


def loop(n: LoopNode) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    base = {
        "id": n.id, "type": "iteration",
        "data": {
            "rationale": n.rationale,
            "over": n.over, "as": n.as_,
            "max_iterations": n.max_iterations,
            "collect": n.collect,
            "body": [{"id": b.id, "type": b.type} for b in n.body],
        },
    }
    return [base], []


def parallel(n: ParallelNode) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    base = {
        "id": n.id, "type": "parallel",
        "data": {
            "rationale": n.rationale,
            "branches": {k: [{"id": b.id, "type": b.type} for b in v] for k, v in n.branches.items()},
            "merge_strategy": n.merge_strategy,
        },
    }
    return [base], []


def agent(n: AgentNode) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    base = {
        "id": n.id, "type": "agent",
        "data": {
            "rationale": n.rationale,
            "model": {"name": n.model},
            "tools": n.tools,
            "input_schema": n.input_schema,
            "output_schema": n.output_schema,
            "system_prompt": n.system_prompt,
            "budget": n.budget.model_dump(),
            "on_budget_exhausted": n.on_budget_exhausted,
            "fallback_edge": n.fallback_edge,
        },
    }
    return [base], []
