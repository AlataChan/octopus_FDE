import json
from pathlib import Path
from typing import Any

import pytest

from loom.ir.models import IRDocument
from loom.runtimes.hiagent.binding import HiagentBinding
from loom.runtimes.hiagent.v2_6.bundle import HiagentBundle
from loom.runtimes.hiagent.v2_6.compiler import compile_ir

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
    return IRDocument.model_validate(json.loads(
        (ROOT / "examples" / "ir" / "01-ecommerce-customer-faq.json").read_text()
    ))


def _workflow(bundle: HiagentBundle) -> dict[str, Any]:
    workflow_files = bundle.workflow_files()
    assert len(workflow_files) == 1
    return workflow_files[0][1]


def test_compile_archetype_01_returns_bundle(faq_ir: IRDocument, minimal_binding: HiagentBinding):
    assert isinstance(compile_ir(faq_ir, minimal_binding), HiagentBundle)


def test_bundle_has_index_and_workflow(faq_ir: IRDocument, minimal_binding: HiagentBinding):
    bundle = compile_ir(faq_ir, minimal_binding)
    assert "index.yaml" in bundle.files
    assert any(p.startswith("workflow/") and p.endswith(".yaml") for p in bundle.files)


def test_bundle_index_has_required_fields(faq_ir: IRDocument, minimal_binding: HiagentBinding):
    index = compile_ir(faq_ir, minimal_binding).index
    assert index["DLVersion"] == "0.0.1"
    assert index["FromWorkspaceID"] == minimal_binding.workspace_id
    assert index["MainMeta"] == "Agent"
    assert index["MainMetaName"] == faq_ir.metadata.name
    assert index["MainUniqueName"]


def test_bundle_has_agent_yaml(faq_ir: IRDocument, minimal_binding: HiagentBinding):
    """Agent bundle must include agent/<n>.yaml with ChatFlow wrapper."""
    bundle = compile_ir(faq_ir, minimal_binding)
    agent_paths = [p for p in bundle.files if p.startswith("agent/")]
    assert len(agent_paths) == 1, f"expected 1 agent yaml, got {agent_paths}"
    agent_yaml = bundle.files[agent_paths[0]]
    assert agent_yaml["MetaType"] == "Agent"
    assert "ChatFlowDetail" in agent_yaml["AppConfig"]
    chatflow = agent_yaml["AppConfig"]["ChatFlowDetail"]
    assert chatflow["MetaType"] == "Workflow"
    assert chatflow["FlowType"] == "Agent"
    # 3 nodes: Start -> Workflow -> End
    types = [n["Type"] for n in chatflow["Nodes"]]
    assert types == ["Start", "Workflow", "End"]


def test_workflow_yaml_has_dlversion_v2(faq_ir: IRDocument, minimal_binding: HiagentBinding):
    assert _workflow(compile_ir(faq_ir, minimal_binding))["DLVersion"] == "v2"


def test_workflow_yaml_has_metatype_workflow(faq_ir: IRDocument, minimal_binding: HiagentBinding):
    assert _workflow(compile_ir(faq_ir, minimal_binding))["MetaType"] == "Workflow"


def test_workflow_yaml_workspace_id_matches_binding(
    faq_ir: IRDocument,
    minimal_binding: HiagentBinding,
):
    assert _workflow(compile_ir(faq_ir, minimal_binding))["WorkspaceID"] == minimal_binding.workspace_id


def test_all_nodes_have_layout_and_code_and_id(faq_ir: IRDocument, minimal_binding: HiagentBinding):
    nodes = _workflow(compile_ir(faq_ir, minimal_binding))["Nodes"]
    for node in nodes:
        assert node["Code"]
        assert node["ID"]
        assert set(node["Layout"]) == {"X", "Y"}


def test_node_codes_are_unique(faq_ir: IRDocument, minimal_binding: HiagentBinding):
    nodes = _workflow(compile_ir(faq_ir, minimal_binding))["Nodes"]
    codes = [n["Code"] for n in nodes]
    assert len(codes) == len(set(codes))


def test_depends_link_destination_to_source(faq_ir: IRDocument, minimal_binding: HiagentBinding):
    nodes = _workflow(compile_ir(faq_ir, minimal_binding))["Nodes"]
    by_type = {n["Type"]: n for n in nodes}
    retrieve = by_type["KnowledgeBase"]
    start = by_type["Start"]
    assert retrieve["Depends"] == [{"NodeCode": start["Code"]}]


def test_compile_with_unbound_kb_emits_empty_knowledge_map(
    faq_ir: IRDocument,
    minimal_binding: HiagentBinding,
):
    workflow = _workflow(compile_ir(faq_ir, minimal_binding))
    assert workflow["Depends"]["KnowledgeMap"] == {}


def test_compile_with_bound_kb_populates_knowledge_map(faq_ir: IRDocument):
    kb_id = "d7jl0000shhcm7cr99hg"
    binding = HiagentBinding(
        customer="test",
        target="hiagent",
        workspace_id="d31pcnoboot936af1tsg",
        dataset_id_map={"product_kb": kb_id},
    )
    workflow = _workflow(compile_ir(faq_ir, binding))
    assert workflow["Depends"]["KnowledgeMap"][kb_id]["ID"] == kb_id
