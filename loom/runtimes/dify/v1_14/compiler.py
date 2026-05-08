"""IR v0.3 -> Dify 1.14 DSL.

Pure function. Programmatic emission [PRD §8: not via templates - too brittle].
Per-node emission lives in compiler_nodes.py; synthesis wrappers in wrappers.py.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

import yaml  # type: ignore[import-untyped]

from loom.runtimes.dify.v1_14 import DIFY_VERSION
from loom.runtimes.dify.v1_14.compiler_nodes import emit_node

if TYPE_CHECKING:
    from loom.ir.models import IRDocument


def compile_ir(ir: IRDocument) -> str:
    """Return Dify DSL YAML."""
    nodes_dsl: list[dict[str, Any]] = []
    edges_dsl: list[dict[str, Any]] = []

    for n in ir.nodes:
        node_dsls, extra_edges = emit_node(n)
        nodes_dsl.extend(node_dsls)
        edges_dsl.extend(extra_edges)
    for e in ir.edges:
        edges_dsl.append({"from": e.from_, "to": e.to})

    doc = {
        "app": {
            "name": ir.metadata.name,
            "description": ir.metadata.description or "",
            "mode": "workflow",
            "loom": {
                "ir_version": ir.ir_version,
                "rationale": ir.metadata.rationale,
                "registry_version": ir.registry_ref.registry_version,
                "compiler_version": f"loom-dify-{DIFY_VERSION}",
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
    return cast("str", yaml.safe_dump(doc, sort_keys=False, allow_unicode=True))
