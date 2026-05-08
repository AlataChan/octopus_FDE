import json
from pathlib import Path

from loom.ir.models import IRDocument
from loom.validator.policy import check_policy

ROOT = Path(__file__).resolve().parents[2]


def _ecommerce_faq():
    return IRDocument.model_validate(json.loads((ROOT / "examples" / "ir" / "01-ecommerce-customer-faq.json").read_text()))


def test_clean_archetype_has_no_policy_failures():
    failures = check_policy(_ecommerce_faq())
    assert failures == []


def test_node_timeout_cannot_exceed_workflow_default():
    ir = _ecommerce_faq().model_copy(update={
        "policy": _ecommerce_faq().policy.model_copy(update={"default_timeout_s": 10}),
    })
    # mutate one node to exceed default
    nodes = list(ir.nodes)
    nodes[1] = nodes[1].model_copy(update={"timeout_s": 30})  # retrieve.timeout_s = 30 > 10
    ir = ir.model_copy(update={"nodes": nodes})
    failures = check_policy(ir)
    assert any(f.bucket == "policy" and "timeout_s" in f.detail for f in failures)


def test_agent_fallback_requires_existing_node():
    # The `01-ecommerce-customer-faq` archetype has no agent. Build a minimal agent IR programmatically
    # in this test for clarity.
    from loom.ir.models import (
        AgentBudget,
        AgentNode,
        Edge,
        Metadata,
        OutputNode,
        Policy,
        PortDecl,
        RegistryRef,
        TriggerNode,
    )
    ir = IRDocument(
        ir_version="0.3",
        metadata=Metadata(name="agent-fb", owner="o", rationale="r"),
        registry_ref=RegistryRef(registry_version="sha:0000000", tools=["t1"]),
        policy=Policy(),
        inputs=[], outputs=[PortDecl(name="x", type="string")],
        nodes=[
            TriggerNode(id="s", type="trigger", mode="manual", rationale="r"),
            AgentNode(
                id="a", type="agent", model="m", tools=["t1"],
                input_schema={"type": "object"}, output_schema={"type": "object"},
                budget=AgentBudget(max_iterations=1, max_tokens=1000, max_wall_clock_s=5),
                on_budget_exhausted="fallback", fallback_edge="missing",
                rationale="r",
            ),
            OutputNode(id="o", type="output", bindings={"x": "${a.x}"}, rationale="r"),
        ],
        edges=[Edge(**{"from": "s"}, to="a"), Edge(**{"from": "a"}, to="o")],
    )
    failures = check_policy(ir)
    assert any("fallback_edge" in f.detail for f in failures)
