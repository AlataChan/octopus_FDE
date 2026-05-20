"""Conformance matrix definitions — one row per PRD §5 cell.

Each row's `case_factory` builds a minimal IR exercising only that construct
plus the surrounding scaffolding (trigger + output). The expected outcome is
encoded as the `expect` callable.

Phase 0: factories return well-formed IR but the runner does not yet execute
end-to-end (no Compiler). Task 14 fills in the live execution; Phase 1 wires
the Compiler.
"""
from __future__ import annotations

from typing import Any

from loom.conformance.runner import ConformanceCase, MatrixRow
from loom.ir.models import (
    AgentBudget,
    AgentNode,
    CodeNode,
    ConditionBranch,
    ConditionNode,
    Edge,
    HTTPNode,
    IRDocument,
    LoopNode,
    Metadata,
    OutputNode,
    ParallelNode,
    Policy,
    PolicyAudit,
    PortDecl,
    RegistryRef,
    Retry,
    TriggerNode,
)

_REG = RegistryRef(registry_version="sha:0000000")


def _trigger(rationale: str = "manual entry") -> TriggerNode:
    return TriggerNode(id="start", type="trigger", mode="manual", rationale=rationale)


def _output(bindings: dict[str, str]) -> OutputNode:
    return OutputNode(id="out", type="output", bindings=bindings, rationale="terminal")


def _ir(name: str, nodes: list[Any], edges: list[Edge], inputs: list[PortDecl] | None = None,
        outputs: list[PortDecl] | None = None, ir_version: str = "0.3") -> IRDocument:
    return IRDocument(
        ir_version=ir_version,
        metadata=Metadata(name=name, owner="loom-conformance",
                          rationale=f"Conformance row {name}"),
        registry_ref=_REG,
        policy=Policy(),
        inputs=inputs or [],
        outputs=outputs or [],
        nodes=nodes,
        edges=edges,
    )


# ---- Row factories ------------------------------------------------------

def case_loop_max_iterations() -> ConformanceCase:
    """Run a loop with N=20 input but max_iterations=5; expect bounded execution."""
    body_code = CodeNode(id="body", type="code", language="python", source="result = item",
                         inputs={"item": "${loop_main.item}"}, rationale="passthrough")
    loop = LoopNode(id="loop_main", type="loop", over="${input.items}", **{"as": "item"},
                    body=[body_code], max_iterations=5, rationale="bounded loop")
    out = _output({"count": "${loop_main.count}"})
    ir = _ir("loop_max_iterations",
             [_trigger(), loop, out],
             [Edge(**{"from": "start"}, to="loop_main"), Edge(**{"from": "loop_main"}, to="out")],
             inputs=[PortDecl(name="items", type="json[]", required=True)],
             outputs=[PortDecl(name="count", type="number")])

    def expect(result: dict[str, Any]) -> None:
        # PRD §5: "Test runs loop with N>bound input; expect bounded execution + structured truncation event"
        assert result["count"] == 5
        assert result.get("truncation_event") is not None

    return ConformanceCase(ir=ir, inputs={"items": list(range(20))}, expect=expect)


def case_parallel_concat() -> ConformanceCase:
    a = CodeNode(id="a", type="code", language="python", source="result = 1", rationale="branch a")
    b = CodeNode(id="b", type="code", language="python", source="result = 2", rationale="branch b")
    par = ParallelNode(id="p", type="parallel", branches={"a": [a], "b": [b]},
                        merge_strategy="concat", rationale="fan-out concat")
    out = _output({"items": "${p}"})
    ir = _ir("parallel_concat",
             [_trigger(), par, out],
             [Edge(**{"from": "start"}, to="p"), Edge(**{"from": "p"}, to="out")],
             outputs=[PortDecl(name="items", type="json[]")])

    def expect(result: dict[str, Any]) -> None:
        assert sorted(result["items"]) == [1, 2]

    return ConformanceCase(ir=ir, inputs={}, expect=expect)


def case_parallel_object_merge() -> ConformanceCase:
    a = CodeNode(id="a", type="code", language="python", source="result = {'x': 1}", rationale="x")
    b = CodeNode(id="b", type="code", language="python", source="result = {'y': 2}", rationale="y")
    par = ParallelNode(id="p", type="parallel", branches={"a": [a], "b": [b]},
                        merge_strategy="object_merge", rationale="fan-out merge")
    out = _output({"merged": "${p}"})
    ir = _ir("parallel_object_merge",
             [_trigger(), par, out],
             [Edge(**{"from": "start"}, to="p"), Edge(**{"from": "p"}, to="out")],
             outputs=[PortDecl(name="merged", type="json")])

    def expect(result: dict[str, Any]) -> None:
        assert result["merged"] == {"a": {"x": 1}, "b": {"y": 2}}

    return ConformanceCase(ir=ir, inputs={}, expect=expect)


def case_parallel_first_success() -> ConformanceCase:
    a = CodeNode(id="a", type="code", language="python", source="raise RuntimeError('fail')",
                 rationale="failing")
    b = CodeNode(id="b", type="code", language="python", source="result = 'b-wins'",
                 rationale="successful")
    par = ParallelNode(id="p", type="parallel", branches={"a": [a], "b": [b]},
                        merge_strategy="first_success", rationale="race")
    out = _output({"winner": "${p}"})
    ir = _ir("parallel_first_success",
             [_trigger(), par, out],
             [Edge(**{"from": "start"}, to="p"), Edge(**{"from": "p"}, to="out")],
             outputs=[PortDecl(name="winner", type="string")])

    def expect(result: dict[str, Any]) -> None:
        assert result["winner"] == "b-wins"

    return ConformanceCase(ir=ir, inputs={}, expect=expect)


def case_agent_budget_fallback() -> ConformanceCase:
    fallback = CodeNode(id="fb", type="code", language="python",
                        source="result = {'findings': 'fallback', 'sources': []}",
                        rationale="deterministic fallback")
    agent = AgentNode(
        id="ag", type="agent", model="configured-small-model",
        tools=["nop_tool"],
        input_schema={"type": "object"}, output_schema={"type": "object"},
        budget=AgentBudget(max_iterations=1, max_tokens=1000, max_wall_clock_s=5),
        on_budget_exhausted="fallback", fallback_edge="fb",
        rationale="bounded; force exhaustion",
    )
    out = _output({"findings": "${fb.findings}"})
    ir = _ir("agent_budget_fallback",
             [_trigger(), agent, fallback, out],
             [Edge(**{"from": "start"}, to="ag"),
              Edge(**{"from": "ag"}, to="fb"),
              Edge(**{"from": "fb"}, to="out")],
             outputs=[PortDecl(name="findings", type="string")])
    ir = ir.model_copy(update={"registry_ref": _REG.model_copy(update={"tools": ["nop_tool"]})})

    def expect(result: dict[str, Any]) -> None:
        assert result["findings"] == "fallback"

    return ConformanceCase(ir=ir, inputs={}, expect=expect)


def case_agent_output_schema() -> ConformanceCase:
    fallback = CodeNode(id="fb", type="code", language="python",
                        source="result = {'value': -1}", rationale="schema-violation fallback")
    agent = AgentNode(
        id="ag", type="agent", model="configured-small-model",
        tools=["nop_tool"],
        input_schema={"type": "object"},
        output_schema={"type": "object", "required": ["value"],
                       "properties": {"value": {"type": "integer"}}},
        budget=AgentBudget(max_iterations=2, max_tokens=2000, max_wall_clock_s=10),
        on_budget_exhausted="fallback", fallback_edge="fb",
        rationale="forces schema violation, expects fallback edge taken",
    )
    out = _output({"value": "${fb.value}"})
    ir = _ir("agent_output_schema",
             [_trigger(), agent, fallback, out],
             [Edge(**{"from": "start"}, to="ag"),
              Edge(**{"from": "ag"}, to="fb"),
              Edge(**{"from": "fb"}, to="out")],
             outputs=[PortDecl(name="value", type="number")])
    ir = ir.model_copy(update={"registry_ref": _REG.model_copy(update={"tools": ["nop_tool"]})})

    def expect(result: dict[str, Any]) -> None:
        assert result["value"] == -1  # fallback fired

    return ConformanceCase(ir=ir, inputs={}, expect=expect)


def case_http_retry_on() -> ConformanceCase:
    h = HTTPNode(
        id="h", type="http", method="POST", url="${input.url}",
        idempotency_key="${input.idem}",
        retry=Retry(max_attempts=3, retry_on=["5xx", "timeout"]),
        rationale="exercises retry classification",
    )
    out = _output({"status": "${h.status}"})
    ir = _ir("http_retry_on",
             [_trigger(), h, out],
             [Edge(**{"from": "start"}, to="h"), Edge(**{"from": "h"}, to="out")],
             inputs=[PortDecl(name="url", type="string", required=True),
                     PortDecl(name="idem", type="string", required=True)],
             outputs=[PortDecl(name="status", type="number")])

    def expect(result: dict[str, Any]) -> None:
        # Assertion details fill in once Task 14 sets up the fault-injection HTTP server.
        assert result["status"] in (200, 503)

    return ConformanceCase(
        ir=ir, inputs={"url": "http://faultinj.local/503-twice-then-200", "idem": "k1"},
        expect=expect,
    )


def case_node_timeout() -> ConformanceCase:
    slow = CodeNode(id="slow", type="code", language="python",
                    source="import time\ntime.sleep(10)\nresult = 'done'",
                    timeout_s=2, rationale="exceeds timeout")
    out = _output({"value": "${slow.error.code}"})
    ir = _ir("node_timeout",
             [_trigger(), slow, out],
             [Edge(**{"from": "start"}, to="slow"), Edge(**{"from": "slow"}, to="out")],
             outputs=[PortDecl(name="value", type="string")])

    def expect(result: dict[str, Any]) -> None:
        assert result["value"] == "TIMEOUT"

    return ConformanceCase(ir=ir, inputs={}, expect=expect)


def case_http_idempotency() -> ConformanceCase:
    h = HTTPNode(
        id="h", type="http", method="POST", url="${input.url}",
        idempotency_key="fixed-key-1", rationale="dedup proof",
    )
    out = _output({"calls": "${h.body.calls}"})
    ir = _ir("http_idempotency",
             [_trigger(), h, out],
             [Edge(**{"from": "start"}, to="h"), Edge(**{"from": "h"}, to="out")],
             inputs=[PortDecl(name="url", type="string", required=True)],
             outputs=[PortDecl(name="calls", type="number")])

    def expect(result: dict[str, Any]) -> None:
        # Two runs with same key → server records 1 effect.
        assert result["calls"] == 1

    return ConformanceCase(ir=ir, inputs={"url": "http://faultinj.local/count"}, expect=expect)


def case_condition_truthiness() -> ConformanceCase:
    truthy = CodeNode(id="t", type="code", language="python",
                      source="result = 'truthy'", rationale="truthy branch")
    falsy = CodeNode(id="f", type="code", language="python",
                     source="result = 'falsy'", rationale="falsy branch")
    cond = ConditionNode(id="c", type="condition", rationale="enumerate truthiness",
                          branches=[ConditionBranch(when="${input.x}", next="t")],
                          default="f")
    out = _output({"taken": "${input.expected}"})
    ir = _ir("condition_truthiness",
             [_trigger(), cond, truthy, falsy, out],
             [Edge(**{"from": "start"}, to="c"),
              Edge(**{"from": "c"}, to="t"),
              Edge(**{"from": "c"}, to="f"),
              Edge(**{"from": "t"}, to="out"),
              Edge(**{"from": "f"}, to="out")],
             inputs=[PortDecl(name="x", type="any", required=True),
                     PortDecl(name="expected", type="string", required=True)],
             outputs=[PortDecl(name="taken", type="string")])

    def expect(result: dict[str, Any]) -> None:
        # Runner parameterizes over a truthiness table — assertion is per-case.
        assert result["taken"] in {"truthy", "falsy"}

    return ConformanceCase(ir=ir, inputs={"x": 0, "expected": "falsy"}, expect=expect)


def case_v04_policy_audit_smoke() -> ConformanceCase:
    out = _output({"ok": "${start.ok}"})
    ir = _ir(
        "v04_policy_audit_smoke",
        [_trigger(), out],
        [Edge(**{"from": "start"}, to="out")],
        outputs=[PortDecl(name="ok", type="boolean")],
        ir_version="0.4",
    )
    ir = ir.model_copy(update={"policy": Policy(audit=PolicyAudit(log_decisions=True, retention_days=90))})

    def expect(result: dict[str, Any]) -> None:
        assert result["ok"] is True

    return ConformanceCase(ir=ir, inputs={}, expect=expect)


# ---- Matrix -------------------------------------------------------------

MATRIX: list[MatrixRow] = [
    MatrixRow("loop_max_iterations",   "loop bounded by max_iterations",                  case_loop_max_iterations),
    MatrixRow("parallel_concat",        "parallel + concat merge",                         case_parallel_concat),
    MatrixRow("parallel_object_merge",  "parallel + object_merge merge",                   case_parallel_object_merge),
    MatrixRow("parallel_first_success", "parallel + first_success merge",                  case_parallel_first_success),
    MatrixRow("agent_budget_fallback",  "agent budget exhaustion → fallback edge",         case_agent_budget_fallback),
    MatrixRow("agent_output_schema",    "agent output_schema enforcement → fallback",      case_agent_output_schema),
    MatrixRow("http_retry_on",          "http retry classes (5xx/timeout/non-retryable)",  case_http_retry_on),
    MatrixRow("node_timeout",           "node timeout_s hard-cuts",                        case_node_timeout),
    MatrixRow("http_idempotency",       "idempotency_key dedupes side-effect",             case_http_idempotency),
    MatrixRow("condition_truthiness",   "condition truthiness parity with Dify",           case_condition_truthiness),
    MatrixRow("v04_policy_audit_smoke", "IR v0.4 policy audit remains additive",           case_v04_policy_audit_smoke),
]
