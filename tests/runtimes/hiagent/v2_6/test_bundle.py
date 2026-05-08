import io
import json
import zipfile
from pathlib import Path

import pytest
import yaml

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


def test_to_zip_bytes_returns_bytes(sample_bundle):
    out = sample_bundle.to_zip_bytes()
    assert isinstance(out, bytes)
    assert len(out) > 0


def test_zip_contains_single_workflow_yaml_at_root(sample_bundle):
    """Hiagent's workflow-import format: ONE yaml at zip root, no subdirs."""
    raw = sample_bundle.to_zip_bytes()
    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        names = zf.namelist()
    assert len(names) == 1, f"expected single entry, got {names}"
    assert names[0].endswith(".yaml"), names[0]
    assert "/" not in names[0], "expected root-level yaml, got nested path"


def test_zip_entry_is_workflow_yaml_with_required_fields(sample_bundle):
    """The single yaml entry must be a complete workflow document."""
    raw = sample_bundle.to_zip_bytes()
    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        name = zf.namelist()[0]
        doc = yaml.safe_load(zf.read(name))
    # Hiagent workflow yaml top-level fields
    assert doc["DLVersion"] == "v2"
    assert doc["MetaType"] == "Workflow"
    assert doc["FlowType"] == "Workflow"
    assert doc["DisplayName"]
    assert doc["ID"]
    assert isinstance(doc["Nodes"], list)
    assert "Depends" in doc
    assert "WorkspaceID" in doc


def test_zip_entry_name_matches_workflow_displayname(sample_bundle):
    """Hiagent's exported zip names the entry '<DisplayName>-<ts>.yaml'."""
    raw = sample_bundle.to_zip_bytes()
    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        name = zf.namelist()[0]
    # IR archetype 01 has metadata.name = "Ecommerce Customer FAQ"
    assert "Ecommerce" in name and "FAQ" in name
    assert name.endswith(".yaml")


def test_zip_entry_filename_decodes_unicode():
    """Workflows with non-ASCII DisplayName must produce zip entries readable by UTF-8 parsers."""
    workflow_doc = {
        "DLVersion": "v2",
        "MetaType": "Workflow",
        "FlowType": "Workflow",
        "DisplayName": "小芸维修专家",   # non-ASCII; verifies UTF-8 flag autosets
        "ID": "abc",
        "Nodes": [],
        "Depends": {},
        "WorkspaceID": "ws",
    }
    b = HiagentBundle(
        bundle_name="bn_20260508_120000",
        files={"index.yaml": {}, "workflow/small.yaml": workflow_doc},
    )
    raw = b.to_zip_bytes()
    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        info = zf.infolist()[0]
        # Python zipfile auto-sets UTF-8 flag for non-ASCII; for ASCII names
        # the flag is harmless to omit (CP437 == ASCII for ASCII bytes).
        assert info.filename.startswith("小芸维修专家")
        assert info.flag_bits & 0x800, "UTF-8 flag should auto-set for non-ASCII filenames"


def test_to_zip_bytes_raises_when_no_workflow():
    """Bundle with only index.yaml (no workflow) cannot be zipped — that's an App-bundle which is out of scope."""
    b = HiagentBundle(bundle_name="bn", files={"index.yaml": {"a": 1}})
    with pytest.raises(ValueError, match="no workflow yaml"):
        b.to_zip_bytes()


def test_deterministic_two_compiles_same_inputs():
    """Equal bundles with equal names and file maps should render to identical zip bytes."""
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
    assert b1.to_zip_bytes() == b2.to_zip_bytes()
