"""Hiagent ChatFlow node spec checks.

These checks encode docs/runtimes/hiagent/node-specs.md so node emission fails
early when a compiler change drifts from the live v2.6 API contract.
"""
from __future__ import annotations

import re
from collections.abc import Iterator, Mapping
from typing import Any, cast


class HiagentSpecError(ValueError):
    """Raised when emitted Hiagent ChatFlow nodes violate the codified spec."""


_INTENT_PORT_RE = re.compile(r"^(class\d{2}|class_other)$")
_START_FIELDS = {"query", "files", "chat_histories"}


def check_generated_chatflow_config(chatflow_config: Mapping[str, Any]) -> None:
    """Validate compiler-generated ChatFlow detail before API materialization."""
    nodes = _node_list(chatflow_config.get("Nodes"), "ChatFlowConfig.Nodes")
    for index, node in enumerate(nodes):
        _check_generated_node(node, f"Nodes[{index}]")


def check_materialized_chatflow_nodes(nodes_value: list[dict[str, object]]) -> None:
    """Validate server-materialized nodes immediately before SaveChatflow."""
    nodes = [cast("Mapping[str, Any]", node) for node in nodes_value]
    start_count = sum(1 for node in nodes if node.get("Type") == "Start")
    end_count = sum(1 for node in nodes if node.get("Type") == "End")
    if start_count != 1:
        raise HiagentSpecError(f"ChatFlow must contain exactly one Start node, got {start_count}")
    if end_count != 1:
        raise HiagentSpecError(f"ChatFlow must contain exactly one End node, got {end_count}")

    for index, node in enumerate(nodes):
        _check_no_sys_refs(node, f"Nodes[{index}]")
        _check_materialized_node(node, f"Nodes[{index}]")


def _check_generated_node(node: Mapping[str, Any], loc: str) -> None:
    type_name = _type_name(node, loc)
    if type_name == "KnowledgeBase":
        raise HiagentSpecError(f"{loc}.Type must be Knowledge, not KnowledgeBase")
    if type_name == "LLM":
        _check_llm(_config(node, loc, "LLM"))
    elif type_name == "Knowledge":
        _check_generated_knowledge(_config(node, loc, "Knowledge"))
    elif type_name == "Intent":
        _check_intent(_config(node, loc, "Intent"), require_query_variable=True)
    elif type_name == "End":
        _check_end(_config(node, loc, "End"), loc)


def _check_materialized_node(node: Mapping[str, Any], loc: str) -> None:
    type_name = _type_name(node, loc)
    if type_name == "Start":
        _check_start(_config(node, loc, "StartNode"))
    elif type_name == "LLM":
        _check_llm(_config(node, loc, "LLMNode"))
    elif type_name == "Knowledge":
        _check_materialized_knowledge(_config(node, loc, "KnowledgeNode"))
    elif type_name == "Intent":
        _check_intent(_config(node, loc, "IntentNode"), require_query_variable=True)
    elif type_name == "End":
        _check_end(_config(node, loc, "EndNode"), loc)


def _check_start(config: Mapping[str, Any]) -> None:
    for field_name in ("InputSchema", "OutputSchema"):
        raw_schema = config.get(field_name)
        if raw_schema is None:
            continue
        schema = _list(raw_schema, f"StartNode.{field_name}")
        names = {
            field.get("Name")
            for field in schema
            if isinstance(field, Mapping)
        }
        missing = _START_FIELDS - names
        if missing:
            raise HiagentSpecError(
                f"StartNode.{field_name} missing server default fields: {sorted(missing)}"
            )


def _check_llm(config: Mapping[str, Any]) -> None:
    schema = _list(config.get("OutputSchema"), "LLM.OutputSchema")
    for field in schema:
        if not isinstance(field, Mapping):
            continue
        if field.get("Name") == "raw_output" and _is_string_type(field.get("Type")):
            return
    raise HiagentSpecError("LLM OutputSchema must include raw_output: String")


def _check_generated_knowledge(config: Mapping[str, Any]) -> None:
    if "KnowledgeIDs" not in config:
        raise HiagentSpecError("Knowledge config requires KnowledgeIDs")
    similarity = float(config.get("Similarity") or 0)
    if similarity <= 0:
        raise HiagentSpecError("Knowledge Similarity/ScoreThreshold must be > 0")


def _check_materialized_knowledge(config: Mapping[str, Any]) -> None:
    knowledges = _list(config.get("Knowledges"), "KnowledgeNode.Knowledges")
    if not knowledges:
        raise HiagentSpecError("KnowledgeNode.Knowledges must be non-empty before save")
    score = float(config.get("ScoreThreshold") or 0)
    if score <= 0:
        raise HiagentSpecError("KnowledgeNode.ScoreThreshold must be > 0")


def _check_intent(config: Mapping[str, Any], *, require_query_variable: bool) -> None:
    if require_query_variable and not isinstance(config.get("QueryVariable"), Mapping):
        raise HiagentSpecError("Intent QueryVariable is required")
    intentions = _list(config.get("Intentions"), "Intent.Intentions")
    port_ids: list[str] = []
    for item in intentions:
        if not isinstance(item, Mapping):
            raise HiagentSpecError("Intent.Intentions entries must be mappings")
        port_id = item.get("PortID")
        if not isinstance(port_id, str) or not _INTENT_PORT_RE.match(port_id):
            raise HiagentSpecError(f"Intent PortID must be class01/class02/class_other, got {port_id!r}")
        port_ids.append(port_id)
    if "class_other" not in port_ids:
        raise HiagentSpecError("Intent must include class_other default branch")


def _check_end(config: Mapping[str, Any], loc: str) -> None:
    if config.get("OutputType") != "Variable":
        return
    refs = list(_iter_ref_dicts(config))
    if not refs:
        raise HiagentSpecError(f"{loc} OutputType=Variable requires node-field references")
    for ref in refs:
        if ref.get("RefType") == "node_field" and not ref.get("NodeCode"):
            raise HiagentSpecError(f"{loc} OutputType=Variable references require NodeCode")


def _check_no_sys_refs(value: Any, loc: str) -> None:
    if isinstance(value, Mapping):
        if value.get("RefType") == "sys":
            raise HiagentSpecError(f"{loc} contains RefType=sys; use Start node_field refs")
        for key, child in value.items():
            _check_no_sys_refs(child, f"{loc}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _check_no_sys_refs(child, f"{loc}[{index}]")


def _iter_ref_dicts(value: Any) -> Iterator[Mapping[str, Any]]:
    if isinstance(value, Mapping):
        if "RefType" in value or "NodeCode" in value:
            yield value
        for child in value.values():
            yield from _iter_ref_dicts(child)
    elif isinstance(value, list):
        for child in value:
            yield from _iter_ref_dicts(child)


def _type_name(node: Mapping[str, Any], loc: str) -> str:
    type_name = node.get("Type")
    if not isinstance(type_name, str) or not type_name:
        raise HiagentSpecError(f"{loc}.Type is required")
    return type_name


def _config(node: Mapping[str, Any], loc: str, key: str) -> Mapping[str, Any]:
    configs = node.get("Configs")
    if not isinstance(configs, Mapping):
        configs = node.get("NodeConfig")
    if not isinstance(configs, Mapping):
        raise HiagentSpecError(f"{loc} requires Configs/NodeConfig")
    value = configs.get(key)
    if not isinstance(value, Mapping):
        raise HiagentSpecError(f"{loc} requires {key} config")
    return value


def _node_list(value: Any, loc: str) -> list[Mapping[str, Any]]:
    raw = _list(value, loc)
    out: list[Mapping[str, Any]] = []
    for index, item in enumerate(raw):
        if not isinstance(item, Mapping):
            raise HiagentSpecError(f"{loc}[{index}] must be a mapping")
        out.append(item)
    return out


def _list(value: Any, loc: str) -> list[Any]:
    if not isinstance(value, list):
        raise HiagentSpecError(f"{loc} must be a list")
    return value


def _is_string_type(value: Any) -> bool:
    return value in {0, "0", "String", "string", "Str", "str"}
