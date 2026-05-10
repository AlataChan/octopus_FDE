import json
from pathlib import Path
from typing import Any

import pytest

from loom.ir.models import IRDocument
from loom.runtimes.hiagent.binding import HiagentBinding
from loom.runtimes.hiagent.v2_6.bundle import HiagentBundle
from loom.runtimes.hiagent.v2_6.compiler import (
    build_agent_config_request,
    build_chatflow_config_draft,
    build_chatflow_workflow_snapshot,
    compile_ir,
    compile_ir_chatflow,
)

ROOT = Path(__file__).resolve().parents[4]


@pytest.fixture
def minimal_binding() -> HiagentBinding:
    return HiagentBinding(
        customer="test",
        target="hiagent",
        workspace_id="d31pcnoboot936af1tsg",
    )


@pytest.fixture
def bound_binding() -> HiagentBinding:
    return HiagentBinding.load(ROOT / "tests" / "fixtures" / "test.hiagent.yaml")


@pytest.fixture
def faq_ir() -> IRDocument:
    return IRDocument.model_validate(
        json.loads((ROOT / "examples" / "ir" / "01-ecommerce-customer-faq.json").read_text())
    )


def _agent(bundle: HiagentBundle) -> dict[str, Any]:
    agent_files = [(p, c) for p, c in bundle.files.items() if p.startswith("agent/")]
    assert len(agent_files) == 1
    return agent_files[0][1]


def _agent_path(bundle: HiagentBundle) -> str:
    agent_files = [(p, c) for p, c in bundle.files.items() if p.startswith("agent/")]
    assert len(agent_files) == 1
    return agent_files[0][0]


def test_compile_archetype_01_returns_bundle(faq_ir: IRDocument, minimal_binding: HiagentBinding):
    assert isinstance(compile_ir(faq_ir, minimal_binding), HiagentBundle)


def test_bundle_has_index_and_single_agent_only(faq_ir: IRDocument, minimal_binding: HiagentBinding):
    bundle = compile_ir(faq_ir, minimal_binding)
    assert "index.yaml" in bundle.files
    assert any(p.startswith("agent/") and p.endswith(".yaml") for p in bundle.files)
    assert not any(p.startswith("workflow/") for p in bundle.files)
    assert not any(p.startswith("knowledge/") for p in bundle.files)
    assert not any(p.startswith("model/") for p in bundle.files)
    assert not any(p.startswith("asset/") for p in bundle.files)


def test_bundle_index_has_required_fields(faq_ir: IRDocument, minimal_binding: HiagentBinding):
    bundle = compile_ir(faq_ir, minimal_binding)
    index = bundle.index
    agent = _agent(bundle)
    assert index["DLVersion"] == "0.0.1"
    assert index["FromWorkspaceID"] == minimal_binding.workspace_id
    assert index["MainMeta"] == "Agent"
    assert index["MainMetaName"] == faq_ir.metadata.name
    assert index["MainUniqueName"]
    assert f"agent/{index['MainMetaName']}.yaml" in bundle.files
    assert index["MainUniqueName"] == agent["UniqueName"] == agent["AppConfig"]["AppID"]


@pytest.mark.parametrize("name", ["Foo Bar Baz", "电商 客服 FAQ"])
def test_agent_filename_preserves_metadata_name_verbatim(
    minimal_binding: HiagentBinding,
    name: str,
):
    ir = IRDocument.model_validate(
        json.loads((ROOT / "examples" / "ir" / "01-ecommerce-customer-faq.json").read_text())
    )
    data = ir.model_dump(by_alias=True)
    data["metadata"]["name"] = name
    renamed = IRDocument.model_validate(data)

    bundle = compile_ir(renamed, minimal_binding)

    assert f"agent/{name}.yaml" in bundle.files
    assert bundle.index["MainMetaName"] == name
    assert f"agent/{name.replace(' ', '_')}.yaml" not in bundle.files


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


def test_model_sidecar_emitted_when_bound(
    faq_ir: IRDocument,
    bound_binding: HiagentBinding,
):
    bundle = compile_ir(faq_ir, bound_binding)
    agent = _agent(bundle)

    for model_id, entry in agent["AppDepends"]["ModelMap"].items():
        path = f"model/{entry['Name']}.yaml"
        assert path in bundle.files
        assert bundle.files[path]["UniqueName"] == model_id


def test_no_sidecar_emitted_when_unbound(
    faq_ir: IRDocument,
    minimal_binding: HiagentBinding,
):
    bundle = compile_ir(faq_ir, minimal_binding)
    agent = _agent(bundle)

    assert agent["AppDepends"]["ModelMap"] == {}
    assert not any(path.startswith("model/") for path in bundle.files)


def test_build_chatflow_config_draft_includes_all_ir_nodes(
    faq_ir: IRDocument,
    minimal_binding: HiagentBinding,
):
    detail = build_chatflow_config_draft(faq_ir, minimal_binding)
    assert len(detail["Nodes"]) == len(faq_ir.nodes)
    assert {n["Type"] for n in detail["Nodes"]} >= {"Start", "Knowledge", "LLM", "End"}
    assert all("_ir_id" not in n for n in detail["Nodes"])
    assert all("Depends" in n for n in detail["Nodes"])
    assert all("ErrorConfig" in n for n in detail["Nodes"])


def test_chatflow_detail_has_metatype_workflow_inside(
    faq_ir: IRDocument,
    minimal_binding: HiagentBinding,
):
    detail = build_chatflow_config_draft(faq_ir, minimal_binding)
    assert detail["DLVersion"] == "v2"
    assert detail["FlowType"] == "Agent"
    assert detail["MetaType"] == "Workflow"
    assert detail["WorkspaceID"] == minimal_binding.workspace_id
    assert detail["WorkflowID"] == detail["ID"]


def test_chatflow_workflow_snapshot_derives_links_from_depends(
    faq_ir: IRDocument,
    minimal_binding: HiagentBinding,
):
    detail = build_chatflow_config_draft(
        faq_ir,
        minimal_binding,
        workflow_id="workflow_123",
    )
    snapshot = build_chatflow_workflow_snapshot(detail)
    assert snapshot["Nodes"] == detail["Nodes"]
    assert len(snapshot["Links"]) == len(faq_ir.edges)
    assert all(set(link) == {"From", "To"} for link in snapshot["Links"])
    assert all(link["From"]["NodeCode"] for link in snapshot["Links"])
    assert all(link["To"]["NodeCode"] for link in snapshot["Links"])


def test_chatflow_shape(faq_ir: IRDocument, bound_binding: HiagentBinding):
    bundle = compile_ir_chatflow(faq_ir, bound_binding)
    agent = _agent(bundle)

    assert _agent_path(bundle) == f"agent/{faq_ir.metadata.name}.yaml"
    assert agent["AppConfig"]["AgentMode"] == ""
    assert agent["AppInfo"]["AgentMode"] == ""
    assert agent["AppInfo"]["AppType"] == "ChatFlow"
    detail = agent["AppConfig"]["ChatFlowDetail"]
    single = agent["AppConfig"]["SingleAgentConfig"]
    assert detail["Nodes"]
    assert single["ChatFlowConfig"]["WorkflowID"] == detail["ID"]
    assert single["ModelID"] == ""
    assert single["KnowledgeIDs"] == []
    assert single["ToolIDs"] == []
    assert single["WorkflowIDs"] == []


def test_chatflow_start_canonical_schema(
    faq_ir: IRDocument,
    bound_binding: HiagentBinding,
):
    detail = _agent(compile_ir_chatflow(faq_ir, bound_binding))["AppConfig"]["ChatFlowDetail"]
    start = next(node for node in detail["Nodes"] if node["Type"] == "Start")
    config = start["Configs"]["Start"]

    for schema_name in ("InputSchema", "OutputSchema"):
        schema = config[schema_name]
        assert [item["Name"] for item in schema] == ["query", "files", "chat_histories"]
        assert [item["Type"] for item in schema] == [0, 11, 9]
        files = schema[1]
        assert files["SubParameters"] == [
            {"Desc": "文件名", "Name": "name", "Required": True, "Type": 0},
            {"Desc": "文件链接", "Name": "url", "Required": True, "Type": 0},
        ]
        histories = schema[2]
        history_files = next(item for item in histories["SubParameters"] if item["Name"] == "files")
        assert history_files["SubParameters"] == files["SubParameters"]


def test_chatflow_knowledge_field_types(
    faq_ir: IRDocument,
    bound_binding: HiagentBinding,
):
    detail = _agent(compile_ir_chatflow(faq_ir, bound_binding))["AppConfig"]["ChatFlowDetail"]
    knowledge_nodes = [node for node in detail["Nodes"] if node["Type"] == "Knowledge"]
    assert knowledge_nodes

    for node in knowledge_nodes:
        config = node["Configs"]["Knowledge"]
        assert node["Type"] == "Knowledge"
        assert config["RetrievalSearchMethod"] == 0
        assert isinstance(config["RetrievalSearchMethod"], int)
        assert isinstance(config["TopK"], int)
