"""IR v0.3 -> Hiagent v2.6 Agent config compiler.

The validated production path is TOP-signed API push. `compile_ir` returns an
in-memory agent bundle for inspection only; API payload helpers below are the
runtime path used by `loom hiagent push`.
"""
from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

from loom.runtimes.hiagent.spec_check import check_generated_chatflow_config
from loom.runtimes.hiagent.v2_6.bundle import HiagentBundle
from loom.runtimes.hiagent.v2_6.compiler_nodes import emit_workflow_nodes
from loom.runtimes.hiagent.v2_6.ids import gen_id
from loom.runtimes.hiagent.v2_6.layout import topological_layout

if TYPE_CHECKING:
    from loom.ir.models import IRDocument
    from loom.runtimes.hiagent.binding import HiagentBinding


_APP_CONFIG_DRAFT_KEYS = {
    "A2aAgentIDs",
    "AgentIDs",
    "ChatAdvancedConfig",
    "DatabaseIDs",
    "GraphConfig",
    "GraphIDs",
    "KnowledgeConfig",
    "KnowledgeIDs",
    "ModelConfig",
    "ModelID",
    "PrePrompt",
    "PromptConfig",
    "QADatasetConfig",
    "QADatasetIDs",
    "SummaryModelConfig",
    "SummaryModelID",
    "TerminologyConfig",
    "TerminologyIDs",
    "ToolIDs",
    "TriggerConfigs",
    "VariableConfigs",
    "WorkflowIDs",
}

_APP_CONFIG_REQUEST_KEYS = _APP_CONFIG_DRAFT_KEYS | {
    "Version",
    "VersionDescription",
}


def compile_ir(ir: IRDocument, binding: HiagentBinding) -> HiagentBundle:
    """Compile IR to a Hiagent v2.6 chat-mode Agent bundle.

    The ZIP import shape is documented in
    `docs/runtimes/hiagent/zip-import-format.md`.
    """
    agent_id = gen_id()
    bundle_name = _bundle_dirname(ir)
    agent_filename = f"{ir.metadata.name}.yaml"

    agent_yaml = _build_agent_yaml(ir=ir, binding=binding, agent_id=agent_id)

    index_yaml = _build_index_yaml(ir=ir, binding=binding, agent_id=agent_id)
    files: dict[str, Any] = {
        "index.yaml": index_yaml,
        f"agent/{agent_filename}": agent_yaml,
    }
    files.update(_build_sidecar_files(agent_yaml["AppDepends"], binding))

    return HiagentBundle(bundle_name=bundle_name, files=files)


def compile_ir_chatflow(ir: IRDocument, binding: HiagentBinding) -> HiagentBundle:
    """Compile IR to a Hiagent v2.6 ChatFlow Agent bundle.

    The ZIP import shape is documented in
    `docs/runtimes/hiagent/zip-import-format.md`.
    """
    agent_id = gen_id()
    bundle_name = _bundle_dirname(ir)
    agent_filename = f"{ir.metadata.name}.yaml"
    agent_yaml = _build_agent_yaml(ir=ir, binding=binding, agent_id=agent_id)
    chatflow_detail = build_chatflow_config_draft(ir, binding)
    single = agent_yaml["AppConfig"]["SingleAgentConfig"]
    single["ModelID"] = ""
    single["ModelName"] = ""
    single["KnowledgeIDs"] = []
    single["ToolIDs"] = []
    single["WorkflowIDs"] = []
    single["ChatFlowConfig"] = {
        "ChatAdvancedConfig": _chat_advanced_config(),
        "RoundsReserved": 23,
        "Version": "v1.0.0",
        "WorkflowID": chatflow_detail["ID"],
        "WorkflowPublishID": "",
    }
    agent_yaml["AppConfig"]["AgentMode"] = ""
    agent_yaml["AppConfig"]["ChatFlowDetail"] = chatflow_detail
    agent_yaml["AppInfo"]["AgentMode"] = ""
    agent_yaml["AppInfo"]["AppType"] = "ChatFlow"

    index_yaml = _build_index_yaml(ir=ir, binding=binding, agent_id=agent_id)
    files: dict[str, Any] = {
        "index.yaml": index_yaml,
        f"agent/{agent_filename}": agent_yaml,
    }
    files.update(_build_sidecar_files(agent_yaml["AppDepends"], binding))
    return HiagentBundle(bundle_name=bundle_name, files=files)


def build_agent_config_draft(ir: IRDocument, binding: HiagentBinding) -> dict[str, Any]:
    """Return API `app.AppConfigDraftRequest` shape for SaveAppConfigDraft."""
    agent_yaml = _build_agent_yaml(ir=ir, binding=binding, agent_id=gen_id())
    single = agent_yaml["AppConfig"]["SingleAgentConfig"]
    return {
        key: value
        for key, value in single.items()
        if key in _APP_CONFIG_DRAFT_KEYS
    }


def build_agent_config_request(ir: IRDocument, binding: HiagentBinding) -> dict[str, Any]:
    """Return API `app.AppConfigRequest` shape for PublishAppV2."""
    agent_yaml = _build_agent_yaml(ir=ir, binding=binding, agent_id=gen_id())
    single = agent_yaml["AppConfig"]["SingleAgentConfig"]
    return {
        key: value
        for key, value in single.items()
        if key in _APP_CONFIG_REQUEST_KEYS
    }


def build_chatflow_config_draft(
    ir: IRDocument,
    binding: HiagentBinding,
    *,
    workflow_id: str | None = None,
    workflow_publish_id: str = "",
) -> dict[str, Any]:
    """Return API `app.ChatFlowConfig` payload with the full IR graph inline.

    Exported Hiagent ChatFlow agents store the graph under
    `AppConfig.ChatFlowDetail`. The TOP API names the corresponding request
    field `ChatFlowConfig`; this helper returns that detail object so the CLI
    can call SaveChatFlowConfigDraft without collapsing the IR into a single
    chat prompt.
    """
    chatflow_id = workflow_id or gen_id()
    version_code = gen_id()
    now_ms = int(time.time() * 1000)
    update_time = time.strftime("%Y-%m-%d %H:%M:%S")
    node_code_map: dict[str, str] = {n.id: gen_id() for n in ir.nodes}
    edges = [(e.from_, e.to) for e in ir.edges]
    positions = topological_layout([n.id for n in ir.nodes], edges)
    nodes = emit_workflow_nodes(
        ir,
        binding,
        node_code_map=node_code_map,
        positions=positions,
    )
    _attach_depends_and_error_config(nodes, node_code_map=node_code_map, edges=edges)

    detail: dict[str, Any] = {
        "DLVersion": "v2",
        "Depends": _build_app_depends(ir, binding),
        "Desc": ir.metadata.description or "",
        "DisplayName": ir.metadata.name,
        "FlowType": "Agent",
        "ID": chatflow_id,
        "LogoPath": "",
        "MetaType": "Workflow",
        "Nodes": nodes,
        "UniqueName": chatflow_id,
        "WorkflowID": chatflow_id,
        "WorkflowPublishID": workflow_publish_id,
        "UpdatedAt": now_ms,
        "UpdateTime": update_time,
        "Version": "v1.0.0",
        "VersionCode": version_code,
        "VersionDescription": ir.metadata.description or "",
        "VersionName": version_code,
        "WorkspaceID": binding.workspace_id,
    }
    check_generated_chatflow_config(detail)
    return detail


def build_chatflow_workflow_snapshot(chatflow_config: dict[str, Any]) -> dict[str, Any]:
    """Return SaveWorkflow's `Nodes` + `Links` snapshot from ChatFlow detail."""
    nodes = chatflow_config["Nodes"]
    links: list[dict[str, Any]] = []
    for node in nodes:
        to_code = node["Code"]
        for dep in node.get("Depends", []):
            from_code = dep.get("NodeCode")
            if from_code:
                links.append({
                    "From": {"NodeCode": from_code},
                    "To": {"NodeCode": to_code},
                })
    return {"Nodes": nodes, "Links": links}


def _attach_depends_and_error_config(
    nodes: list[dict[str, Any]],
    *,
    node_code_map: dict[str, str],
    edges: list[tuple[str, str]],
) -> None:
    deps_by_dest: dict[str, list[dict[str, Any]]] = {}
    for src, dst in edges:
        deps_by_dest.setdefault(dst, []).append({"NodeCode": node_code_map[src]})
    for node in nodes:
        ir_id = node.pop("_ir_id")
        node["Depends"] = deps_by_dest.get(ir_id, [])
        node.setdefault("ErrorConfig", {"ErrorConfigType": "None"})


def _build_agent_yaml(
    *,
    ir: IRDocument,
    binding: HiagentBinding,
    agent_id: str,
) -> dict[str, Any]:
    """Build a chat-mode Agent YAML matching the importable samples."""
    app_depends = _build_app_depends(ir, binding)
    model_handle = _primary_model_handle(ir, binding)
    model_id = binding.resolve_model(model_handle) if model_handle else ""
    knowledge_ids = [
        binding.resolve_dataset(ds)
        for ds in ir.registry_ref.datasets
        if binding.resolve_dataset(ds)
    ]
    now_ms = int(time.time() * 1000)
    update_time = time.strftime("%Y-%m-%d %H:%M:%S")
    version_name = "v1.0.0"

    return {
        "AppConfig": {
            "AgentMode": "Single",
            "AppID": agent_id,
            "ChatFlowDetail": None,
            "MultiAgentConfig": None,
            "SingleAgentConfig": {
                "A2aAgentIDs": [],
                "AgentIDs": [],
                "ChatAdvancedConfig": _chat_advanced_config(),
                "DatabaseIDs": [],
                "GraphConfig": {
                    "MatchType": "force",
                    "SearchDepth": 3,
                    "SearchType": 2,
                    "TopK": 30,
                },
                "GraphIDs": [],
                "KnowledgeConfig": {
                    "ContextComponents": ["id", "video_metadata", "video_frames", "content"],
                    "MatchType": "force",
                    "RerankID": binding.rerank_model_id,
                    "RetrievalSearchMethod": 0,
                    "Similarity": 0.5,
                    "TopK": _primary_retrieval_top_k(ir),
                },
                "KnowledgeIDs": knowledge_ids,
                "ModelConfig": {
                    "CurrentTimeEnabled": False,
                    "IsAdvancedMode": False,
                    "MaxIterations": ir.policy.agent_budget.max_iterations
                    if ir.policy and ir.policy.agent_budget
                    else 10,
                    "MaxTokens": _hiagent_api_max_tokens(ir),
                    "ModelInteractiveMode": "direct",
                    "RagEnabled": bool(knowledge_ids),
                    "RagNum": 3,
                    "ReasoningMode": True,
                    "ReasoningSwitch": True,
                    "ReasoningSwitchType": "enabled",
                    "RoundsReserved": 3,
                    "Strategy": "react",
                    "Temperature": _primary_temperature(ir),
                    "TopP": 0.9,
                },
                "ModelID": model_id,
                "ModelName": model_handle,
                "PrePrompt": _pre_prompt(ir),
                "PromptConfig": {"PromptMode": "regex"},
                "QADatasetConfig": {
                    "MatchType": "force",
                    "RetrievalSearchMethod": 0,
                    "Similarity": 0.5,
                    "TopK": 1,
                },
                "QADatasetIDs": [],
                "SummaryModelID": "",
                "SummaryModelName": "",
                "TerminologyConfig": {
                    "MatchType": "force",
                    "RetrievalSearchMethod": 0,
                    "Similarity": 0.5,
                    "TopK": 3,
                },
                "TerminologyIDs": [],
                "ToolIDs": [
                    binding.resolve_tool(t)
                    for t in ir.registry_ref.tools
                    if binding.resolve_tool(t)
                ],
                "UpdateTime": update_time,
                "VariableConfigs": [],
                "Version": version_name,
                "VersionDescription": ir.metadata.description or "",
                "WorkflowIDs": [],
            },
            "WorkspaceID": binding.workspace_id,
        },
        "AppDepends": app_depends,
        "AppInfo": {
            "AgentMode": "Single",
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
        "UpdatedAt": now_ms,
        "VersionCode": gen_id(),
        "VersionName": version_name,
    }


def _chat_advanced_config() -> dict[str, Any]:
    return {
        "AdvancedReviewType": "unused",
        "FeedbackTagConfig": {
            "DislikeTags": [
                "没有帮助",
                "知识过时",
                "问题理解错误",
                "事实错误",
                "回答不准确",
                "内容有害/不健康",
                "前后回复不一致",
            ],
            "Enabled": True,
            "LikeTags": None,
        },
        "OpeningConfig": {"OpeningEnabled": False},
        "ReferenceEnabled": False,
        "ReviewEnabled": False,
        "SpeechInteractionConfig": {},
        "SuggestEnabled": False,
        "SuggestPromptConfig": {"Enabled": False, "Prompt": ""},
        "ThoughtLanguageConfig": {"Language": "zh"},
        "UploadConfig": {
            "Enabled": False,
            "UploadAudioAllowed": True,
            "UploadCompressedAllowed": False,
            "UploadDocumentAllowed": True,
            "UploadImageAllowed": True,
            "UploadOtherAllowed": False,
            "UploadVideoAllowed": True,
        },
    }


def _pre_prompt(ir: IRDocument) -> str:
    lines = [
        f"# {ir.metadata.name}",
        "",
        ir.metadata.description or "",
        "",
        "# Rationale",
        ir.metadata.rationale,
        "",
        "# Inputs",
    ]
    lines.extend(f"- {p.name}: {p.type}" for p in ir.inputs)
    lines.extend(["", "# Expected outputs"])
    lines.extend(f"- {p.name}: {p.type}" for p in ir.outputs)
    return "\n".join(lines).strip()


def _primary_retrieval_top_k(ir: IRDocument) -> int:
    for n in ir.nodes:
        if getattr(n, "type", None) == "retrieval":
            return int(getattr(n, "top_k", 30))
    return 30


def _primary_temperature(ir: IRDocument) -> float:
    for n in ir.nodes:
        temp = getattr(n, "temperature", None)
        if temp is not None:
            return float(temp)
    return 0.7


def _hiagent_api_max_tokens(ir: IRDocument) -> int:
    """Hiagent PublishAppV2 validates Chat ModelConfig.MaxTokens as 1..4096."""
    if ir.policy and ir.policy.agent_budget:
        return min(max(int(ir.policy.agent_budget.max_tokens), 1), 4096)
    return 4096


def _primary_model_handle(ir: IRDocument, binding: HiagentBinding) -> str:
    handles: list[str] = []
    for n in ir.nodes:
        model_handle = getattr(n, "model", None)
        if model_handle and model_handle not in handles:
            handles.append(model_handle)
    for h in handles:
        if binding.resolve_model(h):
            return h
    return handles[0] if handles else ""


def _build_app_depends(ir: IRDocument, binding: HiagentBinding) -> dict[str, Any]:
    return {
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
    }


def _build_index_yaml(
    *,
    ir: IRDocument,
    binding: HiagentBinding,
    agent_id: str,
) -> dict[str, Any]:
    return {
        "DLVersion": "0.0.1",
        "FromWorkspaceID": binding.workspace_id,
        "MainMeta": "Agent",
        "MainMetaName": ir.metadata.name,
        "MainUniqueName": agent_id,
    }


def _build_sidecar_files(
    app_depends: dict[str, Any],
    binding: HiagentBinding,
) -> dict[str, Any]:
    files: dict[str, Any] = {}
    model_map = app_depends.get("ModelMap")
    if isinstance(model_map, dict):
        for model_id, entry in model_map.items():
            if isinstance(model_id, str) and isinstance(entry, dict):
                name = str(entry["Name"])
                files[f"model/{name}.yaml"] = _build_model_sidecar(
                    model_id=model_id,
                    name=name,
                    binding=binding,
                )
    knowledge_map = app_depends.get("KnowledgeMap")
    if isinstance(knowledge_map, dict):
        for dataset_id, entry in knowledge_map.items():
            if isinstance(dataset_id, str) and isinstance(entry, dict):
                name = str(entry["Name"])
                files[f"knowledge/{name}.yaml"] = _build_knowledge_sidecar(
                    dataset_id=dataset_id,
                    name=name,
                    binding=binding,
                )
    return files


def _build_model_sidecar(
    *,
    model_id: str,
    name: str,
    binding: HiagentBinding,
) -> dict[str, Any]:
    # Model sidecar schema is tracked in docs/runtimes/hiagent/zip-import-format.md.
    # Current live samples accept TenantId=workspace_id. If a future sample proves
    # tenant and workspace diverge, add tenant_id to HiagentBinding and wire it here.
    return {
        "DLVersion": "0.0.1",
        "DeletedAt": None,
        "Desc": "",
        "DisplayName": name,
        "Implement": "custom",
        "IsDefault": False,
        "IsPublic": False,
        "Key": name,
        "LogoPath": "",
        "MetaType": "Model",
        "Source": "custom",
        "SourceTypes": ["Agent"],
        "TenantId": binding.workspace_id,
        "Type": "text-generation",
        "UniqueName": model_id,
        "UpdatedAt": int(time.time() * 1000),
        "VersionCode": "",
        "VersionName": "",
    }


def _build_knowledge_sidecar(
    *,
    dataset_id: str,
    name: str,
    binding: HiagentBinding,
) -> dict[str, Any]:
    return {
        "DLVersion": "v1.0.0",
        "Desc": "",
        "DisplayName": name,
        "LogoPath": "",
        "MetaType": "kbs_dataset",
        "UniqueName": dataset_id,
        "UpdatedAt": int(time.time() * 1000),
        "VersionCode": dataset_id,
        "VersionName": "v1.0.0",
        "data": {
            "Description": None,
            "DirectoryID": "default",
            "EmbeddingModelID": "",
            "IconSha256": "",
            "IndexingTechnique": 0,
            "Name": name,
            "RetrievalSearchMethod": 0,
            "SpaceType": 1,
            "TenantID": binding.workspace_id,
            "WorkspaceID": binding.workspace_id,
            "XID": dataset_id,
        },
    }


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
                "SourceTypes": ["SkillInfo"],
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
                "SourceTypes": ["Agent"],
            }
    return out


def _bundle_dirname(ir: IRDocument) -> str:
    """Generate an inspection bundle name like '<agent-name>_v1.0.0_<timestamp>'."""
    ts = time.strftime("%Y%m%d%H%M%S")
    safe_name = ir.metadata.name.replace(" ", "_")
    return f"{safe_name}_v1.0.0_{ts}"
