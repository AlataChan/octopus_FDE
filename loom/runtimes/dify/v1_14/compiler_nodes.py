"""Per-node emit functions.

Returns (list[dict] dsl_nodes, list[dict] extra_edges) so a single IR node can
expand into multiple DSL nodes when a wrapper is needed.
"""
from __future__ import annotations

from typing import Any

from loom.ir.models import (
    AgentNode,
    AnyNode,
    CodeNode,
    ConditionNode,
    HTTPNode,
    LLMNode,
    LoopNode,
    OutputNode,
    ParallelNode,
    RetrievalNode,
    TriggerNode,
)
from loom.runtimes.dify.v1_14 import wrappers


def emit_node(n: AnyNode) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if isinstance(n, TriggerNode):
        return [_trigger(n)], []
    if isinstance(n, LLMNode):
        return [_llm(n)], []
    if isinstance(n, RetrievalNode):
        return [_retrieval(n)], []
    if isinstance(n, HTTPNode):
        return wrappers.http(n)  # may inject idempotency wrapper
    if isinstance(n, CodeNode):
        return [_code(n)], []
    if isinstance(n, ConditionNode):
        return [_condition(n)], []
    if isinstance(n, LoopNode):
        return wrappers.loop(n)  # may inject truncation-event sentinel
    if isinstance(n, ParallelNode):
        return wrappers.parallel(n)  # merge_strategy may need post-aggregator
    if isinstance(n, AgentNode):
        return wrappers.agent(n)  # output_schema validator + fallback edge
    if isinstance(n, OutputNode):
        return [_output(n)], []
    raise NotImplementedError(f"unhandled node type {type(n).__name__}")


def _trigger(n: TriggerNode) -> dict[str, Any]:
    base: dict[str, Any] = {"id": n.id, "type": "start", "data": {"rationale": n.rationale}}
    if n.mode == "schedule":
        base["data"]["schedule"] = n.schedule
    if n.mode == "webhook":
        base["data"]["webhook"] = n.webhook.model_dump() if n.webhook else {}
        base["data"]["trigger_protocol"] = "http"
    return base


def _llm(n: LLMNode) -> dict[str, Any]:
    return {
        "id": n.id, "type": "llm",
        "data": {
            "rationale": n.rationale,
            "model": {"name": n.model},
            "system_prompt": n.system_prompt,
            "prompt": n.prompt,
            "temperature": n.temperature,
            "max_tokens": n.max_tokens,
            "output_schema": n.output_schema,
        },
    }


def _retrieval(n: RetrievalNode) -> dict[str, Any]:
    return {
        "id": n.id, "type": "knowledge-retrieval",
        "data": {
            "rationale": n.rationale,
            "dataset_id": n.dataset,
            "query": n.query,
            "top_k": n.top_k,
            "rerank": n.rerank,
        },
    }


def _code(n: CodeNode) -> dict[str, Any]:
    return {
        "id": n.id, "type": "code",
        "data": {
            "rationale": n.rationale,
            "language": n.language,
            "source": n.source,
            "inputs": n.inputs or {},
            "output_schema": n.output_schema,
            "idempotency_key": n.idempotency_key,
        },
    }


def _condition(n: ConditionNode) -> dict[str, Any]:
    return {
        "id": n.id, "type": "if-else",
        "data": {
            "rationale": n.rationale,
            "branches": [b.model_dump() for b in n.branches],
            "default": n.default,
        },
    }


def _output(n: OutputNode) -> dict[str, Any]:
    return {
        "id": n.id,
        "type": "end",
        "data": {"rationale": n.rationale, "bindings": n.bindings},
    }
