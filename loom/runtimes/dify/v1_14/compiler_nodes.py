"""IR node emission for Dify 1.x DSL React Flow graphs."""
from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from typing import Any

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
from loom.runtimes.dify.v1_14.refs import parse_ref, to_dify_selector, to_dify_template_ref

DEFAULT_MODEL = {
    "provider": "langgenius/openai/openai",
    "name": "gpt-4o-mini",
    "mode": "chat",
}


@dataclass(frozen=True)
class EmitContext:
    ir: IRDocument
    positions: dict[str, dict[str, float]]
    node_id_map: dict[str, str]
    start_node_id: str


def emit_node(node: AnyNode, ctx: EmitContext) -> dict[str, Any]:
    if isinstance(node, TriggerNode):
        data = _start_data(ctx.ir.inputs)
        return _flow_node(node.id, data, ctx.positions[node.id], height=89)
    if isinstance(node, RetrievalNode):
        return _flow_node(node.id, _retrieval_data(node, ctx), ctx.positions[node.id])
    if isinstance(node, LLMNode):
        return _flow_node(node.id, _llm_data(node, ctx), ctx.positions[node.id], height=88)
    if isinstance(node, ConditionNode):
        return _flow_node(node.id, _condition_data(node, ctx), ctx.positions[node.id], height=124)
    if isinstance(node, CodeNode):
        return _flow_node(node.id, _code_data(node, ctx), ctx.positions[node.id])
    if isinstance(node, OutputNode):
        return _flow_node(node.id, _end_data(node, ctx), ctx.positions[node.id], height=90)
    if isinstance(node, HTTPNode):
        return _flow_node(node.id, _http_data(node, ctx), ctx.positions[node.id])
    if isinstance(node, (LoopNode, ParallelNode, AgentNode)):
        return _flow_node(node.id, _placeholder_code_data(node), ctx.positions[node.id])
    raise NotImplementedError(f"unhandled node type {type(node).__name__}")


def emit_edge(
    *,
    source: str,
    target: str,
    source_handle: str,
    source_type: str,
    target_type: str,
) -> dict[str, Any]:
    return {
        "id": f"{source}-{source_handle}-{target}-target",
        "source": source,
        "sourceHandle": source_handle,
        "target": target,
        "targetHandle": "target",
        "type": "custom",
        "zIndex": 0,
        "data": {
            "isInLoop": False,
            "sourceType": source_type,
            "targetType": target_type,
        },
    }


def _flow_node(
    node_id: str,
    data: dict[str, Any],
    position: dict[str, float],
    *,
    height: int = 90,
) -> dict[str, Any]:
    return {
        "id": node_id,
        "type": "custom",
        "data": data,
        "position": position,
        "positionAbsolute": dict(position),
        "height": height,
        "width": 242,
        "selected": False,
        "sourcePosition": "right",
        "targetPosition": "left",
    }


def _base_data(node_type: str, title: str) -> dict[str, Any]:
    return {"type": node_type, "title": title, "selected": False}


def _start_data(inputs: list[PortDecl]) -> dict[str, Any]:
    data = _base_data("start", "Start")
    data["variables"] = [
        {
            "variable": port.name,
            "label": port.name,
            "type": _input_widget_type(port.type),
            "required": port.required,
            "max_length": 256,
        }
        for port in inputs
    ]
    return data


def _retrieval_data(node: RetrievalNode, ctx: EmitContext) -> dict[str, Any]:
    data = _base_data("knowledge-retrieval", _title(node.rationale, "Knowledge Retrieval"))
    data.update({
        "dataset_ids": [node.dataset],
        "metadata_filtering_mode": "disabled",
        "metadata_model_config": {
            **DEFAULT_MODEL,
            "completion_params": {"temperature": 0.7},
        },
        "multiple_retrieval_config": {
            "top_k": node.top_k,
            "score_threshold": 0.2,
            "reranking_enable": False,
            "reranking_model": None,
        },
        "query_attachment_selector": [],
        "query_variable_selector": to_dify_selector(
            node.query,
            ctx.node_id_map,
            start_node_id=ctx.start_node_id,
        ),
        "retrieval_mode": "multiple",
    })
    return data


def _llm_data(node: LLMNode, ctx: EmitContext) -> dict[str, Any]:
    data = _base_data("llm", _title(node.rationale, "LLM"))
    prompt_template: list[dict[str, str]] = []
    if node.system_prompt:
        prompt_template.append({
            "id": _stable_uuid(f"{node.id}:system"),
            "role": "system",
            "text": to_dify_template_ref(node.system_prompt, ctx.node_id_map),
        })
    prompt_template.append({
        "id": _stable_uuid(f"{node.id}:user"),
        "role": "user",
        "text": to_dify_template_ref(node.prompt, ctx.node_id_map),
    })
    data.update({
        "context": {"enabled": False, "variable_selector": []},
        "memory": None,
        "model": {
            **DEFAULT_MODEL,
            "completion_params": {
                "temperature": node.temperature if node.temperature is not None else 0.7,
            },
        },
        "prompt_template": prompt_template,
        "vision": {"enabled": False},
    })
    return data


def _condition_data(node: ConditionNode, ctx: EmitContext) -> dict[str, Any]:
    data = _base_data("if-else", _title(node.rationale, "If/Else"))
    cases = []
    for index, branch in enumerate(node.branches):
        cases.append({
            "case_id": "true" if index == 0 else f"case_{index + 1}",
            "id": "true" if index == 0 else f"case_{index + 1}",
            "logical_operator": "and",
            "conditions": [_condition_from_expression(branch.when, ctx)],
        })
    data["cases"] = cases
    return data


def _code_data(node: CodeNode, ctx: EmitContext) -> dict[str, Any]:
    data = _base_data("code", _title(node.rationale, "Code"))
    inputs = node.inputs or {}
    data.update({
        "code": _code_source(node),
        "code_language": "python3" if node.language == "python" else "javascript",
        "variables": [
            {
                "variable": name,
                "value_selector": to_dify_selector(value, ctx.node_id_map, start_node_id=ctx.start_node_id),
                "value_type": "string",
            }
            for name, value in inputs.items()
        ],
        "outputs": _outputs_from_schema(node.output_schema),
    })
    return data


def _end_data(node: OutputNode, ctx: EmitContext) -> dict[str, Any]:
    data = _base_data("end", _title(node.rationale, "End"))
    data["outputs"] = [
        {
            "variable": name,
            "value_selector": to_dify_selector(value, ctx.node_id_map, start_node_id=ctx.start_node_id),
        }
        for name, value in node.bindings.items()
    ]
    return data


def _http_data(node: HTTPNode, ctx: EmitContext) -> dict[str, Any]:
    data = _base_data("http-request", _title(node.rationale, "HTTP Request"))
    data.update({
        "method": node.method,
        "url": to_dify_template_ref(node.url, ctx.node_id_map),
        "headers": {
            key: to_dify_template_ref(value, ctx.node_id_map)
            for key, value in (node.headers or {}).items()
        },
        "body": node.body,
        "timeout": node.timeout_s or 120,
    })
    return data


def _placeholder_code_data(node: LoopNode | ParallelNode | AgentNode) -> dict[str, Any]:
    data = _base_data("code", _title(node.rationale, f"{node.type} placeholder"))
    data.update({
        "code": (
            "def main() -> dict:\n"
            f"    return {{'result': 'TODO: replace Loom {node.type} placeholder in Dify UI'}}\n"
        ),
        "code_language": "python3",
        "variables": [],
        "outputs": {"result": {"type": "string", "children": None}},
    })
    return data


def _condition_from_expression(expr: str, ctx: EmitContext) -> dict[str, Any]:
    match = re.match(r"^\s*(\$\{[^}]+\})\s*(<=|>=|==|!=|<|>)\s*(.+?)\s*$", expr)
    if not match:
        return {
            "id": _stable_uuid(expr),
            "comparison_operator": "not empty",
            "value": "",
            "varType": "string",
            "variable_selector": [ctx.start_node_id, "query"],
        }
    ref, operator, raw_value = match.groups()
    value = raw_value.strip().strip("'\"")
    return {
        "id": _stable_uuid(expr),
        "comparison_operator": operator,
        "value": value,
        "varType": _var_type(value),
        "variable_selector": to_dify_selector(ref, ctx.node_id_map, start_node_id=ctx.start_node_id),
    }


def _code_source(node: CodeNode) -> str:
    if node.language != "python" or "def main(" in node.source:
        return node.source
    args = ", ".join((node.inputs or {}).keys())
    args = args or ""
    body = "\n".join(f"    {line}" if line else "" for line in node.source.strip().splitlines())
    return f"def main({args}) -> dict:\n{body or '    return {}'}\n"


def _outputs_from_schema(schema: dict[str, Any] | None) -> dict[str, Any]:
    if not schema:
        return {"result": {"type": "string", "children": None}}
    properties = schema.get("properties")
    if not isinstance(properties, dict):
        return {"result": {"type": _json_type(schema), "children": None}}
    return {
        str(name): {"type": _json_type(prop if isinstance(prop, dict) else {}), "children": None}
        for name, prop in properties.items()
    }


def _json_type(schema: dict[str, Any]) -> str:
    typ = schema.get("type")
    if typ == "integer":
        return "number"
    if typ in {"number", "boolean", "object", "array", "string"}:
        return str(typ)
    return "string"


def _input_widget_type(type_name: str) -> str:
    if type_name in {"string", "any"}:
        return "text-input"
    if type_name == "file":
        return "file"
    return "paragraph"


def _title(rationale: str, fallback: str) -> str:
    return (rationale[:30] or fallback).replace("\n", " ")


def _stable_uuid(value: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"loom:dify:{value}"))


def _var_type(value: str) -> str:
    try:
        float(value)
    except ValueError:
        return "string"
    return "number"


def output_type_by_node(nodes: list[dict[str, Any]]) -> dict[str, str]:
    return {str(node["id"]): str(node["data"]["type"]) for node in nodes}


def source_handle_for_edge(source_node: AnyNode, target_id: str) -> str:
    if isinstance(source_node, ConditionNode):
        if source_node.branches and source_node.branches[0].next == target_id:
            return "true"
        if source_node.default == target_id:
            return "false"
    return "source"


def ref_has_known_node(value: str, known_ids: set[str]) -> bool:
    parsed = parse_ref(value)
    return parsed is not None and parsed[0] in known_ids
