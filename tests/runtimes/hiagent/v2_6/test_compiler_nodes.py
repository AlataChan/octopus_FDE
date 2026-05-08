from typing import Any

import pytest

from loom.ir.models import IRDocument
from loom.runtimes.hiagent.binding import HiagentBinding
from loom.runtimes.hiagent.v2_6.compiler_nodes import emit_workflow_nodes
from loom.runtimes.hiagent.v2_6.ids import is_valid_id

CODE = "d7ji7kd4shhcm7cr99hg"


@pytest.fixture
def minimal_binding() -> HiagentBinding:
    return HiagentBinding(customer="test", target="hiagent", workspace_id="d31pcnoboot936af1tsg")


def _doc(
    nodes: list[dict[str, Any]],
    *,
    edges: list[dict[str, Any]] | None = None,
    inputs: list[dict[str, Any]] | None = None,
    outputs: list[dict[str, Any]] | None = None,
    datasets: list[str] | None = None,
) -> IRDocument:
    return IRDocument.model_validate({
        "ir_version": "0.3",
        "metadata": {
            "name": "Node Test",
            "owner": "tests",
            "rationale": "Exercise a single Hiagent node emission path.",
        },
        "registry_ref": {
            "registry_version": "sha:0000000",
            "tools": [],
            "datasets": datasets or [],
            "credentials": [],
        },
        "policy": {
            "default_timeout_s": 30,
            "default_retry": {"max_attempts": 2},
            "agent_budget": {"max_iterations": 5, "max_tokens": 8000, "max_wall_clock_s": 300},
        },
        "inputs": inputs or [{"name": "query", "type": "string", "required": True}],
        "outputs": outputs or [{"name": "answer", "type": "string", "required": False}],
        "nodes": nodes,
        "edges": edges or [],
    })


def _emit_one(ir: IRDocument, binding: HiagentBinding) -> dict[str, Any]:
    out = emit_workflow_nodes(
        ir,
        binding,
        node_code_map={ir.nodes[0].id: CODE},
        positions={ir.nodes[0].id: (0.0, 0.0)},
    )
    assert len(out) == 1
    return out[0]


def test_trigger_emits_start_node(minimal_binding: HiagentBinding):
    ir = _doc([{"id": "start", "type": "trigger", "mode": "manual", "rationale": "Start here."}])
    node = _emit_one(ir, minimal_binding)
    assert node["Type"] == "Start"
    assert "Start" in node["Configs"]
    assert node["Layout"] == {"X": 0.0, "Y": 0.0}
    assert node["Code"] == CODE
    assert is_valid_id(node["ID"])


def test_llm_emits_llm_node(minimal_binding: HiagentBinding):
    ir = _doc([{
        "id": "answer",
        "type": "llm",
        "rationale": "Generate answer.",
        "model": "configured-small-model",
        "system_prompt": "You answer briefly.",
        "prompt": "${input.query}",
        "temperature": 0,
        "output_schema": {"type": "object", "properties": {"answer": {"type": "string"}}},
    }])
    node = _emit_one(ir, minimal_binding)
    cfg = node["Configs"]["LLM"]
    assert node["Type"] == "LLM"
    assert cfg["SystemPrompt"] == "You answer briefly."
    assert cfg["Prompt"] == "${input.query}"
    assert cfg["ModelID"] == ""


def test_retrieval_emits_knowledge_base_with_empty_ids_when_unbound(minimal_binding: HiagentBinding):
    ir = _doc([{
        "id": "retrieve",
        "type": "retrieval",
        "rationale": "Find product facts.",
        "dataset": "product_kb",
        "query": "${input.query}",
    }], datasets=["product_kb"])
    node = _emit_one(ir, minimal_binding)
    assert node["Type"] == "KnowledgeBase"
    assert node["Configs"]["KnowledgeBase"]["KnowledgeIDs"] == []


def test_retrieval_uses_bound_kb_id():
    kb_id = "d7jl0000shhcm7cr99hg"
    binding = HiagentBinding(
        customer="test",
        target="hiagent",
        workspace_id="d31pcnoboot936af1tsg",
        dataset_id_map={"product_kb": kb_id},
    )
    ir = _doc([{
        "id": "retrieve",
        "type": "retrieval",
        "rationale": "Find product facts.",
        "dataset": "product_kb",
        "query": "${input.query}",
    }], datasets=["product_kb"])
    node = _emit_one(ir, binding)
    assert node["Configs"]["KnowledgeBase"]["KnowledgeIDs"] == [kb_id]


def test_http_emits_httprequest(minimal_binding: HiagentBinding):
    ir = _doc([{
        "id": "fetch",
        "type": "http",
        "rationale": "Call order API.",
        "method": "GET",
        "url": "https://example.test/orders/${input.query}",
    }])
    node = _emit_one(ir, minimal_binding)
    assert node["Type"] == "HTTPRequest"
    assert node["Configs"]["HTTPRequest"]["Method"] == "GET"
    assert node["Configs"]["HTTPRequest"]["URL"] == "https://example.test/orders/${input.query}"


def test_code_emits_code(minimal_binding: HiagentBinding):
    ir = _doc([{
        "id": "code",
        "type": "code",
        "rationale": "Normalize output.",
        "language": "python",
        "source": "return {'answer': 'ok'}",
    }])
    node = _emit_one(ir, minimal_binding)
    assert node["Type"] == "Code"
    assert node["Configs"]["Code"]["Language"] == "python"
    assert node["Configs"]["Code"]["Source"] == "return {'answer': 'ok'}"


def test_condition_emits_intent_with_intentions(minimal_binding: HiagentBinding):
    ir = _doc([{
        "id": "route",
        "type": "condition",
        "rationale": "Route by intent.",
        "branches": [
            {"when": "${answer.intent} == 'refund'", "next": "refund_out"},
            {"when": "${answer.intent} == 'shipping'", "next": "shipping_out"},
        ],
        "default": "general_out",
    }])
    node = _emit_one(ir, minimal_binding)
    cfg = node["Configs"]["Intent"]
    assert node["Type"] == "Intent"
    assert len(cfg["Intentions"]) == 2
    assert cfg["Intentions"][0]["Description"] == "${answer.intent} == 'refund'"


def test_loop_emits_loop(minimal_binding: HiagentBinding):
    ir = _doc([{
        "id": "loop",
        "type": "loop",
        "rationale": "Loop over items.",
        "over": "${input.items}",
        "as": "item",
        "body": [{"id": "body_out", "type": "output", "rationale": "Body output.", "bindings": {"answer": "${input.query}"}}],
        "max_iterations": 7,
    }])
    node = _emit_one(ir, minimal_binding)
    assert node["Type"] == "Loop"
    assert node["Configs"]["Loop"]["MaxIterations"] == 7


def test_output_emits_end(minimal_binding: HiagentBinding):
    ir = _doc([{
        "id": "end",
        "type": "output",
        "rationale": "Return answer.",
        "bindings": {"answer": "${answer.text}"},
    }], outputs=[{"name": "answer", "type": "string", "required": True}])
    node = _emit_one(ir, minimal_binding)
    assert node["Type"] == "End"
    assert len(node["Configs"]["End"]["OutputSchema"]) == len(ir.outputs)
