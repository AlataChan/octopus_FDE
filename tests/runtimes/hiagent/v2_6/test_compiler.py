import json
from pathlib import Path
from typing import Any

import pytest

from loom.ir.models import IRDocument
from loom.runtimes.hiagent.binding import HiagentBinding
from loom.runtimes.hiagent.v2_6.bundle import HiagentBundle
from loom.runtimes.hiagent.v2_6.compiler import build_agent_config_request, compile_ir

ROOT = Path(__file__).resolve().parents[4]


@pytest.fixture
def minimal_binding() -> HiagentBinding:
    return HiagentBinding(
        customer="test",
        target="hiagent",
        workspace_id="d31pcnoboot936af1tsg",
    )


@pytest.fixture
def faq_ir() -> IRDocument:
    return IRDocument.model_validate(
        json.loads((ROOT / "examples" / "ir" / "01-ecommerce-customer-faq.json").read_text())
    )


def _agent(bundle: HiagentBundle) -> dict[str, Any]:
    agent_files = [(p, c) for p, c in bundle.files.items() if p.startswith("agent/")]
    assert len(agent_files) == 1
    return agent_files[0][1]


def test_compile_archetype_01_returns_bundle(faq_ir: IRDocument, minimal_binding: HiagentBinding):
    assert isinstance(compile_ir(faq_ir, minimal_binding), HiagentBundle)


def test_bundle_has_index_and_single_agent_only(faq_ir: IRDocument, minimal_binding: HiagentBinding):
    bundle = compile_ir(faq_ir, minimal_binding)
    assert "index.yaml" in bundle.files
    assert any(p.startswith("agent/") and p.endswith(".yaml") for p in bundle.files)
    assert not any(p.startswith("workflow/") for p in bundle.files)


def test_bundle_has_complete_gold_style_folder_skeleton(
    faq_ir: IRDocument,
    minimal_binding: HiagentBinding,
):
    bundle = compile_ir(faq_ir, minimal_binding)
    assert any(p.startswith("agent/") for p in bundle.files)
    assert any(p.startswith("knowledge/") for p in bundle.files)
    assert any(p.startswith("model/") for p in bundle.files)
    assert any(p.startswith("asset/upload/full/") for p in bundle.files)


def test_asset_placeholder_is_binary(faq_ir: IRDocument, minimal_binding: HiagentBinding):
    bundle = compile_ir(faq_ir, minimal_binding)
    asset_paths = [p for p in bundle.files if p.startswith("asset/upload/full/")]
    assert len(asset_paths) == 1
    assert bundle.files[asset_paths[0]] == b"\x00"


def test_bundle_index_has_required_fields(faq_ir: IRDocument, minimal_binding: HiagentBinding):
    index = compile_ir(faq_ir, minimal_binding).index
    assert index["DLVersion"] == "0.0.1"
    assert index["FromWorkspaceID"] == minimal_binding.workspace_id
    assert index["MainMeta"] == "Agent"
    assert index["MainMetaName"] == faq_ir.metadata.name
    assert index["MainUniqueName"]


def test_agent_yaml_has_single_chat_mode(faq_ir: IRDocument, minimal_binding: HiagentBinding):
    agent = _agent(compile_ir(faq_ir, minimal_binding))
    assert agent["DLVersion"] == "0.0.1"
    assert agent["MetaType"] == "Agent"
    assert agent["AppInfo"]["AppType"] == "Chat"
    assert agent["AppInfo"]["AgentMode"] == "Single"
    assert agent["AppConfig"]["AgentMode"] == "Single"
    assert agent["AppConfig"]["ChatFlowDetail"] is None
    assert agent["AppConfig"]["SingleAgentConfig"]["WorkflowIDs"] == []


def test_agent_unique_name_matches_index(faq_ir: IRDocument, minimal_binding: HiagentBinding):
    bundle = compile_ir(faq_ir, minimal_binding)
    agent = _agent(bundle)
    assert agent["UniqueName"] == bundle.index["MainUniqueName"]


def test_single_agent_config_has_required_chat_defaults(
    faq_ir: IRDocument,
    minimal_binding: HiagentBinding,
):
    single = _agent(compile_ir(faq_ir, minimal_binding))["AppConfig"]["SingleAgentConfig"]
    advanced = single["ChatAdvancedConfig"]
    assert advanced["AdvancedReviewType"] == "unused"
    assert advanced["FeedbackTagConfig"]["Enabled"] is True
    assert advanced["OpeningConfig"]["OpeningEnabled"] is False
    assert advanced["UploadConfig"]["Enabled"] is False
    assert single["PromptConfig"] == {"PromptMode": "regex"}
    assert single["ModelConfig"]["Strategy"] == "react"
    assert single["KnowledgeConfig"]["TopK"] == 20


def test_api_agent_config_caps_max_tokens_for_hiagent_publish(
    faq_ir: IRDocument,
    minimal_binding: HiagentBinding,
):
    config = build_agent_config_request(faq_ir, minimal_binding)
    assert config["ModelConfig"]["MaxTokens"] == 4096


def test_compile_with_unbound_kb_has_empty_knowledge_refs(
    faq_ir: IRDocument,
    minimal_binding: HiagentBinding,
):
    agent = _agent(compile_ir(faq_ir, minimal_binding))
    single = agent["AppConfig"]["SingleAgentConfig"]
    assert single["KnowledgeIDs"] == []
    assert agent["AppDepends"]["KnowledgeMap"] == {}


def test_compile_with_bound_kb_populates_agent_knowledge_refs(faq_ir: IRDocument):
    kb_id = "d7jl0000shhcm7cr99hg"
    binding = HiagentBinding(
        customer="test",
        target="hiagent",
        workspace_id="d31pcnoboot936af1tsg",
        dataset_id_map={"product_kb": kb_id},
    )
    agent = _agent(compile_ir(faq_ir, binding))
    single = agent["AppConfig"]["SingleAgentConfig"]
    assert single["KnowledgeIDs"] == [kb_id]
    assert agent["AppDepends"]["KnowledgeMap"][kb_id]["ID"] == kb_id


def test_compile_with_bound_kb_emits_knowledge_sidecar(faq_ir: IRDocument):
    kb_id = "d7jl0000shhcm7cr99hg"
    binding = HiagentBinding(
        customer="test",
        target="hiagent",
        workspace_id="d31pcnoboot936af1tsg",
        dataset_id_map={"product_kb": kb_id},
    )
    bundle = compile_ir(faq_ir, binding)
    knowledge_paths = [p for p in bundle.files if p.startswith("knowledge/")]
    assert knowledge_paths == ["knowledge/product_kb.yaml"]
    assert bundle.files[knowledge_paths[0]]["UniqueName"] == kb_id


def test_compile_with_bound_model_populates_agent_model_refs(faq_ir: IRDocument):
    model_id = "d2s17uicrg32144vrj9g"
    binding = HiagentBinding(
        customer="test",
        target="hiagent",
        workspace_id="d31pcnoboot936af1tsg",
        model_id_map={"configured-planner-model": model_id},
    )
    agent = _agent(compile_ir(faq_ir, binding))
    single = agent["AppConfig"]["SingleAgentConfig"]
    assert single["ModelID"] == model_id
    assert agent["AppDepends"]["ModelMap"][model_id]["ID"] == model_id


def test_compile_with_bound_model_emits_model_sidecar(faq_ir: IRDocument):
    model_id = "d2s17uicrg32144vrj9g"
    binding = HiagentBinding(
        customer="test",
        target="hiagent",
        workspace_id="d31pcnoboot936af1tsg",
        model_id_map={"configured-planner-model": model_id},
    )
    bundle = compile_ir(faq_ir, binding)
    model_paths = [p for p in bundle.files if p.startswith("model/")]
    assert model_paths == ["model/configured-planner-model.yaml"]
    assert bundle.files[model_paths[0]]["UniqueName"] == model_id
