"""IR v0.3 -> Hiagent v2.6 bundle compiler.

Per ADR 0024. Pure function: takes IRDocument + HiagentBinding, returns
HiagentBundle. Bundle serialization to disk + zip is Sub-task C.

Pipeline:
  1. Generate fresh IDs [workflow Code+ID, per-node Code+ID]
  2. Translate IR var-refs to Hiagent's NodeCode/Path/RefType objects
  3. Emit one Hiagent node per IR node via compiler_nodes.emit_node
  4. Compute layout [topological + grid]
  5. Substitute KB / Model IDs from binding [empty if unbound]
  6. Assemble workflow YAML + index.yaml + dependent file stubs
"""
from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

from loom.runtimes.hiagent.v2_6.bundle import HiagentBundle
from loom.runtimes.hiagent.v2_6.compiler_nodes import emit_workflow_nodes
from loom.runtimes.hiagent.v2_6.ids import gen_id
from loom.runtimes.hiagent.v2_6.layout import topological_layout

if TYPE_CHECKING:
    from loom.ir.models import IRDocument
    from loom.runtimes.hiagent.binding import HiagentBinding


def compile_ir(ir: IRDocument, binding: HiagentBinding) -> HiagentBundle:
    """Compile IR to a Hiagent v2.6 bundle, ready for Sub-task C to zip+write.

    The binding provides workspace_id [required] and optional KB/Model
    id mappings [missing entries become empty strings in the YAML].
    """
    workflow_id = gen_id()

    node_code_map: dict[str, str] = {n.id: gen_id() for n in ir.nodes}

    edges = [(e.from_, e.to) for e in ir.edges]
    positions = topological_layout([n.id for n in ir.nodes], edges)

    nodes_dsl = emit_workflow_nodes(
        ir, binding, node_code_map=node_code_map, positions=positions
    )

    deps_by_dest: dict[str, list[dict[str, Any]]] = {}
    for src, dst in edges:
        deps_by_dest.setdefault(dst, []).append({
            "NodeCode": node_code_map[src],
        })
    for n_dsl in nodes_dsl:
        ir_id = n_dsl.pop("_ir_id")
        deps = deps_by_dest.get(ir_id, [])
        n_dsl["Depends"] = deps
        n_dsl.setdefault("ErrorConfig", {"ErrorConfigType": "None"})

    workflow_yaml: dict[str, Any] = {
        "DLVersion": "v2",
        "Depends": {
            "AppMap": {},
            "DataSourceMap": {},
            "DatabaseMap": {},
            "KnowledgeMap": _build_knowledge_map(ir, binding),
            "ModelMap": _build_model_map(ir, binding),
            "PluginMap": {},
            "QADataSetMap": {},
            "TermDatasetMap": {},
            "ToolMap": {},
            "WorkflowMap": {},
        },
        "Desc": ir.metadata.description or "",
        "DisplayName": ir.metadata.name,
        "FlowType": "Workflow",
        "ID": workflow_id,
        "LogoPath": "",
        "MetaType": "Workflow",
        "Nodes": nodes_dsl,
        "WorkspaceID": binding.workspace_id,
    }

    bundle_name = _bundle_dirname(ir, workflow_id)
    workflow_filename = f"{ir.metadata.name}.yaml"
    index_yaml: dict[str, Any] = {
        "DLVersion": "0.0.1",
        "FromWorkspaceID": binding.workspace_id,
        "MainMeta": "Workflow",
        "MainMetaName": ir.metadata.name,
        "MainUniqueName": workflow_id,
    }

    files: dict[str, Any] = {
        "index.yaml": index_yaml,
        f"workflow/{workflow_filename}": workflow_yaml,
    }

    return HiagentBundle(bundle_name=bundle_name, files=files)


def _build_knowledge_map(ir: IRDocument, binding: HiagentBinding) -> dict[str, dict[str, Any]]:
    """Build KnowledgeMap per Hiagent v2.6 schema; only includes datasets
    referenced by the IR. Datasets with no binding get an empty-id entry
    so the YAML structure is valid; customer wires in UI after import."""
    out: dict[str, dict[str, Any]] = {}
    for ds in ir.registry_ref.datasets:
        kb_id = binding.resolve_dataset(ds)
        if kb_id:
            out[kb_id] = {
                "Desc": "",
                "ID": kb_id,
                "LogoPath": "",
                "Name": ds,
                "ResourceWorkspaceID": binding.workspace_id,
            }
    return out


def _build_model_map(ir: IRDocument, binding: HiagentBinding) -> dict[str, dict[str, Any]]:
    """Build ModelMap; Hiagent uses model IDs at the workflow level.
    Same unbound handling as knowledge map."""
    out: dict[str, dict[str, Any]] = {}
    seen: set[str] = set()
    for n in ir.nodes:
        model_handle = getattr(n, "model", None)
        if not model_handle or model_handle in seen:
            continue
        seen.add(model_handle)
        model_id = binding.resolve_model(model_handle)
        if model_id:
            out[model_id] = {
                "Desc": "",
                "ID": model_id,
                "LogoPath": "",
                "Name": model_handle,
            }
    return out


def _bundle_dirname(ir: IRDocument, workflow_id: str) -> str:
    """Generate bundle dir name like '<workflow-name>_v1.0.0_<timestamp>'."""
    ts = time.strftime("%Y%m%d%H%M%S")
    return f"{ir.metadata.name}_v1.0.0_{ts}"
