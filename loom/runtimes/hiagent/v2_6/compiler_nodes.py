"""Per-node emit functions for Hiagent 2.6 workflow JSON.

Returns (list[dict] dsl_nodes, list[dict] extra_edges) so a single IR node can
expand into multiple workflow nodes if a wrapper becomes necessary.
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
from loom.runtimes.hiagent.v2_6 import wrappers


def emit_node(n: AnyNode) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if isinstance(n, TriggerNode):
        nodes = [_trigger(n)]
        if n.mode == "webhook":
            nodes.append(_webhook_ingress(n))
        return nodes, []
    if isinstance(n, LLMNode):
        return [_llm(n)], []
    if isinstance(n, RetrievalNode):
        return [_retrieval(n)], []
    if isinstance(n, HTTPNode):
        return wrappers.http(n)
    if isinstance(n, CodeNode):
        return [_code(n)], []
    if isinstance(n, ConditionNode):
        return [_condition(n)], []
    if isinstance(n, LoopNode):
        return wrappers.loop(n)
    if isinstance(n, ParallelNode):
        return wrappers.parallel(n)
    if isinstance(n, AgentNode):
        return wrappers.agent(n)
    if isinstance(n, OutputNode):
        return [_output(n)], []
    raise NotImplementedError(f"unhandled node type {type(n).__name__}")


def _trigger(n: TriggerNode) -> dict[str, Any]:
    base: dict[str, Any] = {"id": n.id, "type": "Start", "data": {"rationale": n.rationale, "mode": n.mode}}
    if n.mode == "schedule":
        base["data"]["schedule"] = n.schedule
    if n.mode == "webhook":
        base["data"]["webhook"] = n.webhook.model_dump() if n.webhook else {}
        base["data"]["trigger_protocol"] = "http"
    return base


def _webhook_ingress(n: TriggerNode) -> dict[str, Any]:
    webhook = n.webhook.model_dump() if n.webhook else {}
    return {
        "id": f"{n.id}__webhook_ingress",
        "type": "HTTPRequest",
        "data": {
            "rationale": n.rationale,
            "direction": "ingress",
            "webhook": webhook,
        },
    }


def _llm(n: LLMNode) -> dict[str, Any]:
    return {
        "id": n.id, "type": "LLM",
        "data": {
            "rationale": n.rationale,
            "model": {"name": n.model},
            "system_prompt": n.system_prompt,
            "prompt": n.prompt,
            "temperature": n.temperature,
            "max_tokens": n.max_tokens,
            "output_schema": n.output_schema,
            "timeout_s": n.timeout_s,
            "retry": n.retry.model_dump(exclude_none=True) if n.retry else None,
        },
    }


def _retrieval(n: RetrievalNode) -> dict[str, Any]:
    return {
        "id": n.id, "type": "KnowledgeBase",
        "data": {
            "rationale": n.rationale,
            "dataset": n.dataset,
            "query": n.query,
            "top_k": n.top_k,
            "rerank": n.rerank,
            "timeout_s": n.timeout_s,
            "retry": n.retry.model_dump(exclude_none=True) if n.retry else None,
        },
    }


def _code(n: CodeNode) -> dict[str, Any]:
    return {
        "id": n.id, "type": "Code",
        "data": {
            "rationale": n.rationale,
            "language": n.language,
            "source": n.source,
            "inputs": n.inputs or {},
            "output_schema": n.output_schema,
            "timeout_s": n.timeout_s,
            "retry": n.retry.model_dump(exclude_none=True) if n.retry else None,
            "idempotency_key": n.idempotency_key,
        },
    }


def _condition(n: ConditionNode) -> dict[str, Any]:
    return {
        "id": n.id, "type": "Selector",
        "data": {
            "rationale": n.rationale,
            "branches": [b.model_dump() for b in n.branches],
            "default": n.default,
        },
    }


def _output(n: OutputNode) -> dict[str, Any]:
    return {
        "id": n.id,
        "type": "End",
        "data": {"rationale": n.rationale, "bindings": n.bindings},
    }
