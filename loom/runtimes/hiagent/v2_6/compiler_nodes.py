"""Per-node emit functions for Hiagent v2.6 bundle workflow YAML."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from loom.ir.models import (
    AgentNode,
    AnyNode,
    CodeNode,
    ConditionNode,
    HTTPNode,
    IRDocument,
    LLMNode,
    LoopNode,
    OutputNode,
    ParallelNode,
    PortDecl,
    RetrievalNode,
    TriggerNode,
)
from loom.runtimes.hiagent.v2_6.ids import gen_id
from loom.runtimes.hiagent.v2_6.types import to_hiagent_type_code
from loom.runtimes.hiagent.v2_6.varref import VarRefParseError, find_varrefs, parse_varref

if TYPE_CHECKING:
    from loom.runtimes.hiagent.binding import HiagentBinding


def emit_workflow_nodes(
    ir: IRDocument,
    binding: HiagentBinding,
    *,
    node_code_map: dict[str, str],
    positions: dict[str, tuple[float, float]],
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for n in ir.nodes:
        out.append(_emit_node(ir, n, binding, node_code_map, positions))
    return out


def _emit_node(
    ir: IRDocument,
    n: AnyNode,
    binding: HiagentBinding,
    node_code_map: dict[str, str],
    positions: dict[str, tuple[float, float]],
) -> dict[str, Any]:
    if isinstance(n, TriggerNode):
        return _trigger(ir, n, node_code_map, positions)
    if isinstance(n, LLMNode):
        return _llm(ir, n, binding, node_code_map, positions)
    if isinstance(n, RetrievalNode):
        return _retrieval(n, binding, node_code_map, positions)
    if isinstance(n, HTTPNode):
        return _http(n, node_code_map, positions)
    if isinstance(n, CodeNode):
        return _code(n, node_code_map, positions)
    if isinstance(n, ConditionNode):
        return _condition(n, binding, node_code_map, positions)
    if isinstance(n, LoopNode):
        return _loop(n, node_code_map, positions)
    if isinstance(n, ParallelNode):
        return _parallel(n, node_code_map, positions)
    if isinstance(n, AgentNode):
        return _agent(n, binding, node_code_map, positions)
    if isinstance(n, OutputNode):
        return _output(ir, n, node_code_map, positions)
    raise NotImplementedError(f"unhandled node type {type(n).__name__}")


def _base(
    n: AnyNode,
    type_name: str,
    node_code_map: dict[str, str],
    positions: dict[str, tuple[float, float]],
) -> dict[str, Any]:
    x, y = positions[n.id]
    return {
        "_ir_id": n.id,
        "Code": node_code_map[n.id],
        "ID": gen_id(),
        "Name": _name(n),
        "Description": n.rationale,
        "Type": type_name,
        "Layout": {"X": x, "Y": y},
        "Configs": {},
    }


def _name(n: AnyNode) -> str:
    return n.rationale[:30] or n.id


def _trigger(
    ir: IRDocument,
    n: TriggerNode,
    node_code_map: dict[str, str],
    positions: dict[str, tuple[float, float]],
) -> dict[str, Any]:
    out = _base(n, "Start", node_code_map, positions)
    out["Configs"]["Start"] = {
        "Mode": n.mode,
        "Schedule": n.schedule,
        "Webhook": n.webhook.model_dump() if n.webhook else None,
        "InputSchema": [_port_schema(p) for p in ir.inputs],
        "OutputSchema": [_port_schema(p) for p in ir.inputs],
    }
    return out


def _llm(
    ir: IRDocument,
    n: LLMNode,
    binding: HiagentBinding,
    node_code_map: dict[str, str],
    positions: dict[str, tuple[float, float]],
) -> dict[str, Any]:
    out = _base(n, "LLM", node_code_map, positions)
    model_id = binding.resolve_model(n.model)
    out["Configs"]["LLM"] = {
        "ModelID": model_id,
        "ModelName": n.model,
        "SystemPrompt": n.system_prompt or "",
        "Prompt": n.prompt,
        "Temperature": n.temperature if n.temperature is not None else 0.7,
        "MaxTokens": n.max_tokens or 4096,
        "OutputSchema": _json_schema_to_hiagent_schema(n.output_schema),
        "QueryVariable": _first_query_variable(n.prompt, node_code_map),
        "ReasoningMode": None,
        "ReasoningSwitch": None,
        "ReasoningSwitchType": None,
        "ReasoningEffortType": None,
        "Retries": n.retry.max_attempts if n.retry else 0,
        "TimeoutSeconds": int(n.timeout_s or ir.policy.default_timeout_s or 360),
    }
    return out


def _retrieval(
    n: RetrievalNode,
    binding: HiagentBinding,
    node_code_map: dict[str, str],
    positions: dict[str, tuple[float, float]],
) -> dict[str, Any]:
    out = _base(n, "KnowledgeBase", node_code_map, positions)
    kb_id = binding.resolve_dataset(n.dataset)
    out["Configs"]["KnowledgeBase"] = {
        "KnowledgeIDs": [kb_id] if kb_id else [],
        "TopK": n.top_k,
        "MatchType": "vector",
        "RerankID": binding.rerank_model_id,
        "RetrievalSearchMethod": "semantic",
        "Similarity": 0.0,
        "QueryVariable": _to_ref("query", n.query, node_code_map),
        "OutputSchema": [{"Name": "chunks", "Required": True, "Type": 5}],
    }
    return out


def _http(
    n: HTTPNode,
    node_code_map: dict[str, str],
    positions: dict[str, tuple[float, float]],
) -> dict[str, Any]:
    out = _base(n, "HTTPRequest", node_code_map, positions)
    out["Configs"]["HTTPRequest"] = {
        "Method": n.method,
        "URL": n.url,
        "Headers": n.headers or {},
        "Body": n.body,
        "IdempotencyKey": n.idempotency_key,
        "Retry": n.retry.model_dump(exclude_none=True) if n.retry else None,
        "OutputSchema": [{"Name": "response", "Required": True, "Type": 4}],
    }
    return out


def _code(
    n: CodeNode,
    node_code_map: dict[str, str],
    positions: dict[str, tuple[float, float]],
) -> dict[str, Any]:
    out = _base(n, "Code", node_code_map, positions)
    out["Configs"]["Code"] = {
        "Language": n.language,
        "Source": n.source,
        "InputVariables": [
            _to_ref(name, value, node_code_map)
            for name, value in (n.inputs or {}).items()
        ],
        "OutputSchema": _json_schema_to_hiagent_schema(n.output_schema),
    }
    return out


def _condition(
    n: ConditionNode,
    binding: HiagentBinding,
    node_code_map: dict[str, str],
    positions: dict[str, tuple[float, float]],
) -> dict[str, Any]:
    out = _base(n, "Intent", node_code_map, positions)
    model_name = "configured-small-model"
    model_id = binding.resolve_model(model_name)
    out["Configs"]["Intent"] = {
        "Intentions": [
            {"Name": f"class_{i}", "Description": b.when, "PortID": f"class_{i}"}
            for i, b in enumerate(n.branches)
        ],
        "MaxTokens": 4096,
        "ModelID": model_id,
        "ModelName": model_name,
        "OutputSchema": [
            {"Name": "classificationId", "Required": True, "Type": 1},
            {"Name": "classificationName", "Required": True, "Type": 0},
            {"Name": "reason", "Required": True, "Type": 0},
        ],
        "Temperature": 0.7,
    }
    return out


def _loop(
    n: LoopNode,
    node_code_map: dict[str, str],
    positions: dict[str, tuple[float, float]],
) -> dict[str, Any]:
    out = _base(n, "Loop", node_code_map, positions)
    out["Configs"]["Loop"] = {
        "LoopType": "Bounded",
        "MaxIterations": n.max_iterations,
        "InterVariables": [_to_ref(n.as_, n.over, node_code_map)],
        "Collect": n.collect,
    }
    return out


def _parallel(
    n: ParallelNode,
    node_code_map: dict[str, str],
    positions: dict[str, tuple[float, float]],
) -> dict[str, Any]:
    out = _base(n, "Code", node_code_map, positions)
    out["Description"] = (
        n.rationale + "\nTODO: parallel branches require VariableAggregator wrapper."
    )
    out["Configs"]["Code"] = {
        "Language": "python",
        "Source": "# TODO: parallel branches require VariableAggregator wrapper",
        "InputVariables": [],
        "OutputSchema": [
            {"Name": branch, "Required": False, "Type": 4}
            for branch in sorted(n.branches)
        ],
        "Branches": {
            branch: [{"id": child.id, "type": child.type} for child in children]
            for branch, children in n.branches.items()
        },
        "MergeStrategy": n.merge_strategy,
    }
    return out


def _agent(
    n: AgentNode,
    binding: HiagentBinding,
    node_code_map: dict[str, str],
    positions: dict[str, tuple[float, float]],
) -> dict[str, Any]:
    out = _base(n, "LLM", node_code_map, positions)
    model_id = binding.resolve_model(n.model)
    out["Configs"]["LLM"] = {
        "ModelID": model_id,
        "ModelName": n.model,
        "SystemPrompt": n.system_prompt or "",
        "Prompt": "",
        "ToolIDs": [binding.resolve_tool(t) for t in n.tools if binding.resolve_tool(t)],
        "InputSchema": _json_schema_to_hiagent_schema(n.input_schema),
        "OutputSchema": _json_schema_to_hiagent_schema(n.output_schema),
        "Budget": n.budget.model_dump(),
        "OnBudgetExhausted": n.on_budget_exhausted,
        "FallbackEdge": n.fallback_edge,
    }
    return out


def _output(
    ir: IRDocument,
    n: OutputNode,
    node_code_map: dict[str, str],
    positions: dict[str, tuple[float, float]],
) -> dict[str, Any]:
    out = _base(n, "End", node_code_map, positions)
    out["Configs"]["End"] = {
        "OutputType": "Content",
        "Template": _template_from_bindings(n.bindings),
        "OutputSchema": [_port_schema(p) for p in ir.outputs],
        "StreamOutput": True,
    }
    return out


def _port_schema(port: PortDecl) -> dict[str, Any]:
    return {
        "Name": port.name,
        "Desc": port.description or "",
        "Type": to_hiagent_type_code(port.type),
        "Required": port.required,
    }


def _json_schema_to_hiagent_schema(schema: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not schema:
        return []
    required = set(schema.get("required", []))
    properties = schema.get("properties")
    if isinstance(properties, dict):
        return [
            {
                "Name": name,
                "Required": name in required,
                "Type": _json_type_to_hiagent_type(prop if isinstance(prop, dict) else {}),
            }
            for name, prop in properties.items()
        ]
    return [{"Name": "output", "Required": True, "Type": _json_type_to_hiagent_type(schema)}]


def _json_type_to_hiagent_type(schema: dict[str, Any]) -> int:
    typ = schema.get("type")
    if typ == "integer":
        return 1
    if typ == "number":
        return 2
    if typ == "boolean":
        return 3
    if typ == "object":
        return 4
    if typ == "array":
        return 5
    if typ == "null":
        return 6
    return 0


def _first_query_variable(value: str, node_code_map: dict[str, str]) -> dict[str, Any] | None:
    refs = find_varrefs(value)
    if not refs:
        return None
    node_id, path = refs[0]
    return _ref_object("query", node_id, path, node_code_map)


def _to_ref(name: str, value: str, node_code_map: dict[str, str]) -> dict[str, Any]:
    try:
        node_id, path = parse_varref(value)
    except VarRefParseError:
        return {"Name": name, "NodeCode": "", "Path": value, "RefType": "const"}
    return _ref_object(name, node_id, path, node_code_map)


def _ref_object(
    name: str,
    node_id: str,
    path: str,
    node_code_map: dict[str, str],
) -> dict[str, Any]:
    if node_id == "input":
        return {"Name": name, "NodeCode": "", "Path": path, "RefType": "sys"}
    return {
        "Name": name,
        "NodeCode": node_code_map.get(node_id, ""),
        "Path": path,
        "RefType": "node_field",
    }


def _template_from_bindings(bindings: dict[str, str]) -> str:
    lines = []
    for name, value in bindings.items():
        lines.append(f"{name}: {value}")
    return "\n".join(lines)
