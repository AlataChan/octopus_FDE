"""IR v0.3 -> Hiagent v2.6 Agent bundle compiler.

The currently validated Hiagent import path is chat-mode Agent ZIP import:
root `index.yaml` + `agent/<name>.yaml` and optional model/knowledge sidecars.
Workflow import remains useful as a reference format, but this compiler now
emits a single-agent chat app because that is the confirmed customer-importable
shape.
"""
from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

from loom.runtimes.hiagent.v2_6.bundle import HiagentBundle
from loom.runtimes.hiagent.v2_6.ids import gen_id

if TYPE_CHECKING:
    from loom.ir.models import IRDocument
    from loom.runtimes.hiagent.binding import HiagentBinding


def compile_ir(ir: IRDocument, binding: HiagentBinding) -> HiagentBundle:
    """Compile IR to a Hiagent v2.6 chat-mode Agent bundle.

    The binding provides workspace_id [required] and optional KB/Model
    id mappings [missing entries become empty strings in the YAML].
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
    files.update(_build_knowledge_files(ir, binding))
    files.update(_build_model_files(ir, binding))

    return HiagentBundle(bundle_name=bundle_name, files=files)


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
                    "MaxTokens": ir.policy.agent_budget.max_tokens
                    if ir.policy and ir.policy.agent_budget
                    else 32768,
                    "ModelInteractiveMode": "direct",
                    "RagEnabled": bool(knowledge_ids),
                    "RagNum": 3,
                    "ReasoningMode": True,
                    "ReasoningSwitch": True,
                    "ReasoningSwitchType": "enabled",
                    "RoundsReserved": 3,
                    "Strategy": "function_call",
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


def _build_knowledge_files(ir: IRDocument, binding: HiagentBinding) -> dict[str, Any]:
    files: dict[str, Any] = {}
    now_ms = int(time.time() * 1000)
    for ds in ir.registry_ref.datasets:
        kb_id = binding.resolve_dataset(ds)
        if not kb_id:
            continue
        files[f"knowledge/{ds}.yaml"] = {
            "DLVersion": "v1.0.0",
            "Desc": "",
            "DisplayName": ds,
            "LogoPath": "",
            "MetaType": "kbs_dataset",
            "UniqueName": kb_id,
            "UpdatedAt": now_ms,
            "VersionCode": kb_id,
            "VersionName": "v1.0.0",
            "data": {
                "Name": ds,
                "WorkspaceID": binding.workspace_id,
                "XID": kb_id,
            },
        }
    return files


def _build_model_files(ir: IRDocument, binding: HiagentBinding) -> dict[str, Any]:
    files: dict[str, Any] = {}
    now_ms = int(time.time() * 1000)
    seen: set[str] = set()
    for n in ir.nodes:
        model_handle = getattr(n, "model", None)
        if not model_handle or model_handle in seen:
            continue
        seen.add(model_handle)
        model_id = binding.resolve_model(model_handle)
        if not model_id:
            continue
        files[f"model/{model_handle}.yaml"] = {
            "DLVersion": "0.0.1",
            "DeletedAt": None,
            "Desc": "",
            "DisplayName": model_handle,
            "Implement": "",
            "IsDefault": True,
            "IsPublic": True,
            "Key": model_handle,
            "LogoPath": "",
            "MetaType": "Model",
            "Source": "custom",
            "SourceTypes": ["Agent"],
            "TenantId": "",
            "Type": "text-generation",
            "UniqueName": model_id,
            "UpdatedAt": now_ms,
            "VersionCode": "",
            "VersionName": "",
        }
    return files


def _bundle_dirname(ir: IRDocument) -> str:
    """Generate bundle dir name like '<workflow-name>_v1.0.0_<timestamp>'.

    Spaces in IR metadata.name are replaced with underscores; customer
    Hiagent samples never use spaces in directory or filenames, and
    Hiagent's importer can fail on space-containing filenames with a
    misleading 'No signature found after EOCD record' error.
    """
    ts = time.strftime("%Y%m%d%H%M%S")
    safe_name = ir.metadata.name.replace(" ", "_")
    return f"{safe_name}_v1.0.0_{ts}"
