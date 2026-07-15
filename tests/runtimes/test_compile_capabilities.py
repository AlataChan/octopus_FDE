from __future__ import annotations

from typing import Any

import pytest
import yaml

from loom.ir.models import IRDocument
from loom.runtimes import base as runtime_base
from loom.runtimes.dify.adapter import DifyAdapter
from loom.runtimes.dify.v1_14.compiler import compile_ir as compile_dify
from loom.runtimes.hiagent.adapter import HiagentAdapter
from loom.runtimes.hiagent.binding import HiagentBinding


def _doc(node: dict[str, Any]) -> IRDocument:
    return IRDocument.model_validate({
        "ir_version": "0.3",
        "metadata": {
            "name": "Capability Test",
            "owner": "tests",
            "rationale": "Verify unsupported runtime semantics fail closed.",
        },
        "registry_ref": {
            "registry_version": "sha:0000000",
            "tools": [],
            "datasets": [],
            "credentials": [],
        },
        "policy": {},
        "inputs": [{"name": "query", "type": "string", "required": True}],
        "outputs": [{"name": "answer", "type": "string"}],
        "nodes": [node],
        "edges": [],
    })


@pytest.fixture
def binding() -> HiagentBinding:
    return HiagentBinding(
        customer="test",
        target="hiagent",
        workspace_id="workspace-test",
        model_id_map={"bound-model": "model-id"},
    )


def _compile(target: str, ir: IRDocument, binding: HiagentBinding) -> object:
    context_type = getattr(runtime_base, "CompileContext")
    if target == "dify":
        return DifyAdapter().compile(
            ir,
            context=context_type(binding="preview", mode="chatflow", actor="fde", tenant="tenant-a"),
        )
    return HiagentAdapter().compile(
        ir,
        context=context_type(binding=binding, mode="chatflow", actor="fde", tenant="tenant-a"),
    )


@pytest.mark.parametrize("target", ["dify", "hiagent"])
@pytest.mark.parametrize(
    ("construct", "node"),
    [
        (
            "loop.bounded",
            {
                "id": "loop",
                "type": "loop",
                "rationale": "Bounded loop.",
                "over": "${input.query}",
                "as": "item",
                "body": [],
                "max_iterations": 3,
            },
        ),
        (
            "parallel.fanout_merge",
            {
                "id": "parallel",
                "type": "parallel",
                "rationale": "Parallel work.",
                "branches": {"a": [], "b": []},
                "merge_strategy": "object_merge",
            },
        ),
        (
            "agent.budget_schema_fallback",
            {
                "id": "agent",
                "type": "agent",
                "rationale": "Tool-using agent.",
                "model": "bound-model",
                "tools": ["lookup"],
                "input_schema": {"type": "object"},
                "output_schema": {"type": "object"},
                "budget": {
                    "max_iterations": 3,
                    "max_tokens": 2000,
                    "max_wall_clock_s": 60,
                },
                "on_budget_exhausted": "fail",
            },
        ),
        (
            "http.credential",
            {
                "id": "http",
                "type": "http",
                "rationale": "Authenticated call.",
                "method": "GET",
                "url": "https://example.test",
                "credential": "orders-api",
            },
        ),
        (
            "http.retry",
            {
                "id": "http",
                "type": "http",
                "rationale": "Retried call.",
                "method": "GET",
                "url": "https://example.test",
                "retry": {"max_attempts": 3, "backoff": "exponential"},
            },
        ),
        (
            "http.idempotency_key",
            {
                "id": "http",
                "type": "http",
                "rationale": "Idempotent call.",
                "method": "POST",
                "url": "https://example.test",
                "idempotency_key": "${input.query}",
            },
        ),
    ],
)
def test_compilers_reject_unverified_semantics(
    target: str,
    construct: str,
    node: dict[str, Any],
    binding: HiagentBinding,
):
    error_type = getattr(runtime_base, "UnsupportedConstruct")

    with pytest.raises(error_type) as raised:
        _compile(target, _doc(node), binding)

    assert raised.value.target == target
    assert raised.value.construct == construct
    assert raised.value.node_id == node["id"]
    assert raised.value.reason
    assert raised.value.remediation


@pytest.mark.parametrize(
    ("target", "expression", "construct"),
    [
        ("dify", "risk_score(${input.query}) > 0.8", "condition.complex_expression"),
        (
            "dify",
            "${input.query} == 'review' && ${input.query} != 'safe'",
            "condition.complex_expression",
        ),
        ("hiagent", "${input.query} == 'review'", "condition.rule"),
    ],
)
def test_compilers_reject_unverified_rule_conditions(
    target: str,
    expression: str,
    construct: str,
    binding: HiagentBinding,
):
    ir = _doc({
        "id": "route",
        "type": "condition",
        "rationale": "Risk route.",
        "branches": [{"when": expression, "next": "review"}],
        "default": "done",
    })
    error_type = getattr(runtime_base, "UnsupportedConstruct")

    with pytest.raises(error_type) as raised:
        _compile(target, ir, binding)

    assert raised.value.construct == construct


def test_dify_preserves_requested_llm_model_name():
    ir = _doc({
        "id": "answer",
        "type": "llm",
        "rationale": "Answer.",
        "model": "gpt-4.1-mini",
        "prompt": "${input.query}",
    })

    text, _warnings = compile_dify(ir)
    node = yaml.safe_load(text)["workflow"]["graph"]["nodes"][0]

    assert node["data"]["model"]["name"] == "gpt-4.1-mini"


def test_hiagent_adapter_rejects_unbound_model(binding: HiagentBinding):
    ir = _doc({
        "id": "answer",
        "type": "llm",
        "rationale": "Answer.",
        "model": "missing-model",
        "prompt": "${input.query}",
    })
    context_type = getattr(runtime_base, "CompileContext")
    error_type = getattr(runtime_base, "UnsupportedConstruct")

    with pytest.raises(error_type) as raised:
        HiagentAdapter().compile(
            ir,
            context=context_type(binding=binding, mode="chatflow", actor="fde", tenant="tenant-a"),
        )

    assert raised.value.construct == "llm.model_binding"


def test_adapters_generate_redlines_from_capability_matrix():
    dify = "\n".join(DifyAdapter().redlines())
    hiagent = "\n".join(HiagentAdapter().redlines())

    for construct in ("loop.bounded", "parallel.fanout_merge", "agent.budget_schema_fallback"):
        assert construct in dify
        assert construct in hiagent
    assert "condition.complex_expression" in dify
    assert "condition.rule" in hiagent
    assert "http.credential" in dify
    assert "http.credential" in hiagent


def test_hiagent_adapter_uses_compile_context_mode_and_binding(binding: HiagentBinding):
    ir = _doc({
        "id": "start",
        "type": "trigger",
        "rationale": "Start.",
        "mode": "manual",
    })
    context_type = getattr(runtime_base, "CompileContext")

    bundle, _warnings = HiagentAdapter().compile(
        ir,
        context=context_type(binding=binding, mode="chatflow", actor="fde", tenant="tenant-a"),
    )

    agent = next(content for path, content in bundle.files.items() if path.startswith("agent/"))
    assert agent["AppInfo"]["AppType"] == "ChatFlow"


@pytest.mark.parametrize("adapter", [DifyAdapter(), HiagentAdapter()])
def test_unimplemented_lifecycle_operations_are_structured(adapter: object):
    error_type = getattr(runtime_base, "UnsupportedRuntimeOperation")

    with pytest.raises(error_type) as raised:
        adapter.reverse({})  # type: ignore[attr-defined]

    assert raised.value.target == adapter.target  # type: ignore[attr-defined]
    assert raised.value.operation == "reverse"
