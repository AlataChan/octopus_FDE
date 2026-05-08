import json
from pathlib import Path

import pytest

from loom.ir.models import IRDocument
from loom.runtimes.hiagent.binding import HiagentBinding
from loom.runtimes.hiagent.v2_6.bundle import HiagentBundle
from loom.runtimes.hiagent.v2_6.compiler import compile_ir

ROOT = Path(__file__).resolve().parents[4]


@pytest.fixture
def sample_bundle():
    ir = IRDocument.model_validate(
        json.loads((ROOT / "examples" / "ir" / "01-ecommerce-customer-faq.json").read_text())
    )
    binding = HiagentBinding(
        customer="test",
        target="hiagent",
        workspace_id="d31pcnoboot936af1tsg",
    )
    return compile_ir(ir, binding)


def test_to_workflow_json_returns_str(sample_bundle):
    out = sample_bundle.to_workflow_json()
    assert isinstance(out, str)
    assert len(out) > 0


def test_workflow_json_parses_as_valid_json(sample_bundle):
    out = sample_bundle.to_workflow_json()
    doc = json.loads(out)
    assert isinstance(doc, dict)


def test_workflow_json_has_hiagent_workflow_top_level_fields(sample_bundle):
    """Workflow-import JSON must have the Hiagent workflow document shape."""
    doc = json.loads(sample_bundle.to_workflow_json())
    assert doc["DLVersion"] == "v2"
    assert doc["MetaType"] == "Workflow"
    assert doc["FlowType"] == "Workflow"
    assert doc["DisplayName"]
    assert doc["ID"]
    assert isinstance(doc["Nodes"], list)
    assert "Depends" in doc
    assert "WorkspaceID" in doc


def test_workflow_json_workspace_id_matches_binding(sample_bundle):
    doc = json.loads(sample_bundle.to_workflow_json())
    assert doc["WorkspaceID"] == "d31pcnoboot936af1tsg"


def test_workflow_json_preserves_unicode():
    """Non-ASCII content (e.g., Chinese node names) must round-trip cleanly."""
    workflow_doc = {
        "DLVersion": "v2",
        "MetaType": "Workflow",
        "FlowType": "Workflow",
        "DisplayName": "小芸维修专家",
        "ID": "abc",
        "Nodes": [],
        "Depends": {},
        "WorkspaceID": "ws",
    }
    b = HiagentBundle(
        bundle_name="bn_20260508_120000",
        files={"index.yaml": {}, "workflow/x.yaml": workflow_doc},
    )
    out = b.to_workflow_json()
    assert "小芸维修专家" in out  # ensure_ascii=False keeps Chinese readable
    assert json.loads(out)["DisplayName"] == "小芸维修专家"


def test_to_workflow_json_raises_when_no_workflow():
    """Bundle with only index.yaml has no workflow content to serialize."""
    b = HiagentBundle(bundle_name="bn", files={"index.yaml": {"a": 1}})
    with pytest.raises(ValueError, match="no workflow"):
        b.to_workflow_json()


def test_deterministic_two_calls_same_inputs():
    """Equal bundle.files content -> identical JSON output."""
    workflow_doc = {
        "DLVersion": "v2",
        "MetaType": "Workflow",
        "FlowType": "Workflow",
        "DisplayName": "x",
        "ID": "abc",
        "Nodes": [],
        "Depends": {},
        "WorkspaceID": "ws",
    }
    files = {"index.yaml": {"DLVersion": "0.0.1"}, "workflow/x.yaml": workflow_doc}
    b1 = HiagentBundle(bundle_name="bn_20260508_120000", files=files)
    b2 = HiagentBundle(bundle_name="bn_20260508_120000", files=files)
    assert b1.to_workflow_json() == b2.to_workflow_json()
