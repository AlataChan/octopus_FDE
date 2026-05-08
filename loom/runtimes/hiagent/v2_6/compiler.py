"""IR v0.3 -> Hiagent v2.6 Agent config compiler.

The validated production path is TOP-signed API push. `compile_ir` returns an
in-memory agent bundle for inspection only; API payload helpers below are the
runtime path used by `loom hiagent push`.
"""
from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

from loom.runtimes.hiagent.v2_6.bundle import HiagentBundle
from loom.runtimes.hiagent.v2_6.ids import gen_id

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
    """Compile IR to an in-memory Hiagent v2.6 chat-mode Agent bundle.

    This is for inspection only. Production publish uses
    `build_agent_config_draft` + `build_agent_config_request` through the TOP
    API client.
    """
    agent_id = gen_id()
    bundle_name = _bundle_dirname(ir)
    safe_name = ir.metadata.name.replace(" ", "_")
    agent_filename = f"{safe_name}.yaml"

    agent_yaml = _build_agent_yaml(ir=ir, binding=binding, agent_id=agent_id)

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
    }

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
