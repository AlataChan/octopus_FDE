"""IR v0.3 -> Hiagent 2.6 workflow JSON.

Pure function. Programmatic emission. Per-node emission lives in
compiler_nodes.py; synthesis wrappers in wrappers.py [smaller than Dify's
because Hiagent natively handles more IR primitives].
"""
from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from loom.runtimes.hiagent.v2_6 import HIAGENT_VERSION
from loom.runtimes.hiagent.v2_6.compiler_nodes import emit_node

if TYPE_CHECKING:
    from loom.ir.models import IRDocument


def compile_ir(ir: IRDocument) -> str:
    """Return Hiagent workflow JSON [string]."""
    nodes_dsl: list[dict[str, Any]] = []
    edges_dsl: list[dict[str, Any]] = []

    for n in ir.nodes:
        node_dsls, extra_edges = emit_node(n)
        nodes_dsl.extend(node_dsls)
        edges_dsl.extend(extra_edges)
    for e in ir.edges:
        edges_dsl.append({"from": e.from_, "to": e.to})

    doc: dict[str, Any] = {
        "app": {
            "name": ir.metadata.name,
            "description": ir.metadata.description or "",
            "mode": "workflow",
            "loom": {
                "ir_version": ir.ir_version,
                "rationale": ir.metadata.rationale,
                "registry_version": ir.registry_ref.registry_version,
                "compiler_version": f"loom-hiagent-{HIAGENT_VERSION}",
            },
        },
        "workflow": {
            "nodes": nodes_dsl,
            "edges": edges_dsl,
        },
        "policy": ir.policy.model_dump(exclude_none=True) if ir.policy else {},
        "inputs": [p.model_dump() for p in ir.inputs],
        "outputs": [p.model_dump() for p in ir.outputs],
    }
    return json.dumps(doc, indent=2, ensure_ascii=False)
