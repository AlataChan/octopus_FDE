"""IR v0.3 -> Dify 1.x DSL YAML.

Pure function. Emits the Dify app graph schema used by the 1.x UI import
flow: app metadata plus workflow.graph React Flow nodes/edges.
"""
from __future__ import annotations

from typing import Any, cast

import yaml  # type: ignore[import-untyped]

from loom.ir.models import IRDocument, TriggerNode
from loom.runtimes.dify.v1_14.compiler_nodes import (
    EmitContext,
    emit_edge,
    emit_node,
    output_type_by_node,
    source_handle_for_edge,
)
from loom.runtimes.dify.v1_14.layout import topological_layout


def compile_ir(ir: IRDocument) -> str:
    """Return Dify DSL YAML suitable for UI import."""
    node_id_map = {node.id: node.id for node in ir.nodes}
    start_node_id = _start_node_id(ir)
    positions = topological_layout(
        [node.id for node in ir.nodes],
        [(edge.from_, edge.to) for edge in ir.edges],
    )
    ctx = EmitContext(
        ir=ir,
        positions=positions,
        node_id_map=node_id_map,
        start_node_id=start_node_id,
    )

    nodes_dsl = [emit_node(node, ctx) for node in ir.nodes]
    node_types = output_type_by_node(nodes_dsl)
    source_nodes = {node.id: node for node in ir.nodes}
    edges_dsl = [
        emit_edge(
            source=edge.from_,
            target=edge.to,
            source_handle=source_handle_for_edge(source_nodes[edge.from_], edge.to),
            source_type=node_types[edge.from_],
            target_type=node_types[edge.to],
        )
        for edge in ir.edges
    ]

    doc: dict[str, Any] = {
        "app": {
            "name": ir.metadata.name,
            "description": ir.metadata.description or "",
            "mode": "workflow",
            "icon": "🤖",
            "icon_background": "#FFEAD5",
            "icon_type": "emoji",
            "use_icon_as_answer_icon": False,
        },
        "dependencies": [],
        "kind": "app",
        "version": "0.6.0",
        "workflow": {
            "conversation_variables": [],
            "environment_variables": [],
            "features": _features(),
            "graph": {
                "edges": edges_dsl,
                "nodes": nodes_dsl,
                "viewport": {"x": 0, "y": 0, "zoom": 0.7},
            },
            "rag_pipeline_variables": [],
        },
    }
    return cast("str", yaml.safe_dump(doc, sort_keys=False, allow_unicode=True))


def _start_node_id(ir: IRDocument) -> str:
    for node in ir.nodes:
        if isinstance(node, TriggerNode):
            return node.id
    return ir.nodes[0].id


def _features() -> dict[str, Any]:
    return {
        "file_upload": {"enabled": False},
        "text_to_speech": {"enabled": False, "language": "", "voice": ""},
        "opening_statement": "",
        "suggested_questions": [],
        "suggested_questions_after_answer": {"enabled": False},
        "speech_to_text": {"enabled": False},
        "retriever_resource": {"enabled": True},
        "sensitive_word_avoidance": {"enabled": False},
    }
