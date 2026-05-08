"""Thin wrappers for Hiagent-native IR primitives.

Hiagent 2.6 handles the relevant MVP primitives directly, so wrappers mostly
degenerate to one workflow node while preserving the common compiler contract.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from loom.ir.models import AgentNode, HTTPNode, LoopNode, ParallelNode


def http(n: HTTPNode) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    base = {
        "id": n.id, "type": "HTTPRequest",
        "data": {
            "rationale": n.rationale,
            "method": n.method,
            "url": n.url,
            "headers": n.headers or {},
            "body": n.body,
            "credential": n.credential,
            "timeout_s": n.timeout_s,
            "retry": n.retry.model_dump(exclude_none=True) if n.retry else None,
            "idempotency_key": n.idempotency_key,
        },
    }
    return [base], []


def loop(n: LoopNode) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    from loom.runtimes.hiagent.v2_6.compiler_nodes import emit_node

    body_nodes: list[dict[str, Any]] = []
    body_edges: list[dict[str, Any]] = []
    for body_node in n.body:
        node_dsls, extra_edges = emit_node(body_node)
        body_nodes.extend(node_dsls)
        body_edges.extend(extra_edges)
    base = {
        "id": n.id, "type": "Loop",
        "data": {
            "rationale": n.rationale,
            "over": n.over,
            "as": n.as_,
            "max_iterations": n.max_iterations,
            "collect": n.collect,
            "timeout_s": n.timeout_s,
            "body": [{"id": b.id, "type": b.type} for b in n.body],
        },
    }
    return [base, *body_nodes], body_edges


def parallel(n: ParallelNode) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    from loom.runtimes.hiagent.v2_6.compiler_nodes import emit_node

    branch_nodes: list[dict[str, Any]] = []
    branch_edges: list[dict[str, Any]] = []
    for branch in n.branches.values():
        for branch_node in branch:
            node_dsls, extra_edges = emit_node(branch_node)
            branch_nodes.extend(node_dsls)
            branch_edges.extend(extra_edges)
    base = {
        "id": n.id, "type": "Parallel",
        "data": {
            "rationale": n.rationale,
            "branches": {k: [{"id": b.id, "type": b.type} for b in v] for k, v in n.branches.items()},
            "merge_strategy": n.merge_strategy,
            "branch_types": n.branch_types,
            "timeout_s": n.timeout_s,
        },
    }
    return [base, *branch_nodes], branch_edges


def agent(n: AgentNode) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    base = {
        "id": n.id, "type": "Agent",
        "data": {
            "rationale": n.rationale,
            "model": {"name": n.model},
            "tools": n.tools,
            "input_schema": n.input_schema,
            "output_schema": n.output_schema,
            "inputs": n.inputs or {},
            "system_prompt": n.system_prompt,
            "budget": n.budget.model_dump(),
            "on_budget_exhausted": n.on_budget_exhausted,
            "fallback_edge": n.fallback_edge,
            "timeout_s": n.timeout_s,
        },
    }
    return [base], []
