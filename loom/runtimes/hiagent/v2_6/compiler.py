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
    # Customer Hiagent samples never use spaces in filenames; replace spaces
    # in IR's free-text name with underscores so Hiagent's import path
    # accepts the filename. Display names inside the YAML keep spaces.
    safe_name = ir.metadata.name.replace(" ", "_")
    workflow_filename = f"{safe_name}.yaml"
    agent_filename = f"{safe_name}.yaml"

    # Agent bundle (verified import format per user 2026-05-08): MainMeta=Agent,
    # ChatFlow wrapper agent calls our business workflow as a sub-step.
    agent_id = gen_id()
    agent_yaml = _build_agent_yaml(
        ir=ir,
        binding=binding,
        agent_id=agent_id,
        workflow_id=workflow_id,
    )

    index_yaml: dict[str, Any] = {
        "DLVersion": "0.0.1",
        "FromWorkspaceID": binding.workspace_id,
        "MainMeta": "Agent",
        "MainMetaName": ir.metadata.name,
        "MainUniqueName": agent_id,
    }

    files: dict[str, Any] = {
        "index.yaml": index_yaml,
        f"agent/{agent_filename}": agent_yaml,
        f"workflow/{workflow_filename}": workflow_yaml,
    }

    return HiagentBundle(bundle_name=bundle_name, files=files)


def _build_agent_yaml(
    *,
    ir: IRDocument,
    binding: HiagentBinding,
    agent_id: str,
    workflow_id: str,
) -> dict[str, Any]:
    """Build the ChatFlow-wrapper agent yaml that hosts our IR workflow.

    Mirrors the structure of customer's 小芸用户维修方案智能体 agent
    (which contains MetaType: Agent + AppConfig.ChatFlowDetail with a
    3-node Start->Workflow->End graph). The Workflow node calls our
    business workflow via WorkflowID.
    """
    chatflow_id = gen_id()
    start_code = gen_id()
    workflow_node_code = gen_id()
    end_code = gen_id()

    # Map IR inputs to ChatFlow start node InputSchema; pass through to workflow.
    start_input_schema = [
        {
            "Desc": p.description or "",
            "Name": p.name,
            "Required": p.required,
            "Type": _type_code(p.type),
        }
        for p in ir.inputs
    ]
    # Workflow node InputVariables: each maps to a Start node output.
    workflow_input_variables = [
        {
            "Name": p.name,
            "NodeCode": start_code,
            "Path": p.name,
            "RefType": "node_field",
        }
        for p in ir.inputs
    ]
    # Workflow node OutputSchema: mirror IR outputs.
    workflow_output_schema = [
        {
            "Name": p.name,
            "Required": p.required,
            "Type": _type_code(p.type),
        }
        for p in ir.outputs
    ]
    # End node OutputSchema: same shape.
    end_output_schema = [
        {
            "Desc": p.description or "",
            "Name": p.name,
            "Required": p.required,
            "Type": _type_code(p.type),
        }
        for p in ir.outputs
    ]

    chatflow_nodes = [
        {
            "Code": start_code,
            "Configs": {
                "Start": {
                    "InputSchema": start_input_schema,
                    "OutputSchema": start_input_schema,
                }
            },
            "Description": "User input.",
            "ErrorConfig": {"ErrorConfigType": "None"},
            "ID": gen_id(),
            "Layout": {"X": 0.0, "Y": 0.0},
            "Name": "Start",
            "Type": "Start",
        },
        {
            "Code": workflow_node_code,
            "Configs": {
                "Workflow": {
                    "Description": ir.metadata.description or "",
                    "Icon": "",
                    "InputSchema": [
                        {"Desc": s.get("Desc", ""), "Name": s["Name"], "Type": s["Type"]}
                        for s in start_input_schema
                    ],
                    "InputVariables": workflow_input_variables,
                    "Name": ir.metadata.name,
                    "OutputSchema": workflow_output_schema,
                    "WorkflowID": workflow_id,
                }
            },
            "Depends": [{"NodeCode": start_code}],
            "Description": ir.metadata.rationale,
            "ErrorConfig": {"ErrorConfigType": "None"},
            "ID": gen_id(),
            "Layout": {"X": 300.0, "Y": 0.0},
            "Name": ir.metadata.name,
            "Type": "Workflow",
        },
        {
            "Code": end_code,
            "Configs": {
                "End": {
                    "OutputSchema": end_output_schema,
                    "OutputType": "Content",
                    "StreamOutput": True,
                    "Template": _end_template_from_outputs(ir),
                }
            },
            "Depends": [{"NodeCode": workflow_node_code}],
            "Description": "Final output.",
            "ErrorConfig": {"ErrorConfigType": "None"},
            "ID": gen_id(),
            "Layout": {"X": 600.0, "Y": 0.0},
            "Name": "End",
            "Type": "End",
        },
    ]

    return {
        "AppConfig": {
            "AgentMode": "",
            "AppID": agent_id,
            "ChatFlowDetail": {
                "DLVersion": "v2",
                "Depends": {
                    "AppMap": {},
                    "DataSourceMap": {},
                    "DatabaseMap": {},
                    "KnowledgeMap": {},
                    "ModelMap": {},
                    "PluginMap": {},
                    "QADataSetMap": {},
                    "TermDatasetMap": {},
                    "ToolMap": {},
                    "WorkflowMap": {
                        workflow_id: {
                            "Desc": ir.metadata.description or "",
                            "ID": workflow_id,
                            "LogoPath": "",
                            "Name": ir.metadata.name,
                            "ResourceWorkspaceID": binding.workspace_id,
                        }
                    },
                },
                "Desc": "",
                "DisplayName": agent_id,
                "FlowType": "Agent",
                "ID": chatflow_id,
                "LogoPath": "",
                "MetaType": "Workflow",
                "Nodes": chatflow_nodes,
                "UniqueName": chatflow_id,
            },
            "MultiAgentConfig": None,
            "SingleAgentConfig": None,
            "WorkspaceID": binding.workspace_id,
        },
        "AppDepends": {
            "AppMap": {},
            "DataSourceMap": {},
            "DatabaseMap": {},
            "KnowledgeMap": {},
            "ModelMap": {},
            "PluginMap": {},
            "QADataSetMap": {},
            "TermDatasetMap": {},
            "ToolMap": {},
            "WorkflowMap": {
                workflow_id: {
                    "Desc": ir.metadata.description or "",
                    "ID": workflow_id,
                    "LogoPath": "",
                    "Name": ir.metadata.name,
                    "ResourceWorkspaceID": binding.workspace_id,
                    "SourceTypes": ["Agent"],
                }
            },
        },
        "AppInfo": {
            "AgentMode": "",
            "AppID": agent_id,
            "AppType": "Chat",
            "WorkspaceID": binding.workspace_id,
        },
        "DLVersion": "0.0.1",
        "Desc": ir.metadata.description or "",
        "DisplayName": ir.metadata.name,
        "LogoPath": "",
        "MetaType": "Agent",
        "UniqueName": agent_id,
        "UpdatedAt": int(time.time() * 1000),
        "VersionCode": gen_id(),
        "VersionName": "v1.0.0",
    }


def _type_code(ir_type: str) -> int:
    """Inline type-code mapping; ChatFlow Schema uses the same Hiagent codes."""
    mapping = {"string": 0, "number": 2, "boolean": 3, "json": 4, "null": 6}
    if ir_type in mapping:
        return mapping[ir_type]
    if ir_type.endswith("[]"):
        return 5
    return 0


def _end_template_from_outputs(ir: IRDocument) -> str:
    """Generate End node Template from IR outputs (Hiagent uses {{var}} mustache)."""
    lines = [f"{p.name}: {{{{{p.name}}}}}" for p in ir.outputs]
    return "\n".join(lines) if lines else "{{output}}"


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
    """Generate bundle dir name like '<workflow-name>_v1.0.0_<timestamp>'.

    Spaces in IR metadata.name are replaced with underscores; customer
    Hiagent samples never use spaces in directory or filenames, and
    Hiagent's importer can fail on space-containing filenames with a
    misleading 'No signature found after EOCD record' error.
    """
    ts = time.strftime("%Y%m%d%H%M%S")
    safe_name = ir.metadata.name.replace(" ", "_")
    return f"{safe_name}_v1.0.0_{ts}"
