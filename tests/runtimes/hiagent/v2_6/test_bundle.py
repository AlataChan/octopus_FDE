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


def test_zip_contains_index_and_workflow(sample_bundle):
    raw = sample_bundle.to_zip_bytes()
    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        names = zf.namelist()
    assert any(n.endswith("/index.yaml") for n in names)
    assert any("/workflow/" in n and n.endswith(".yaml") for n in names)


def test_zip_entries_under_bundle_name(sample_bundle):
    raw = sample_bundle.to_zip_bytes()
    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        names = zf.namelist()
    for n in names:
        assert n.startswith(sample_bundle.bundle_name + "/"), f"{n} not under bundle root"


def test_zip_entries_are_valid_yaml(sample_bundle):
    raw = sample_bundle.to_zip_bytes()
    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        for name in zf.namelist():
            if not name.endswith(".yaml"):
                continue
            text = zf.read(name).decode("utf-8")
            doc = yaml.safe_load(text)
            assert doc is not None, f"{name} parsed to None"


def test_index_yaml_has_required_top_level_fields(sample_bundle):
    raw = sample_bundle.to_zip_bytes()
    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        idx_path = next(n for n in zf.namelist() if n.endswith("/index.yaml"))
        idx = yaml.safe_load(zf.read(idx_path))
    assert idx["DLVersion"] == "0.0.1"
    assert idx["MainMeta"] == "Workflow"
    assert idx["MainMetaName"]
    assert idx["MainUniqueName"]
    assert idx["FromWorkspaceID"] == "d31pcnoboot936af1tsg"


def test_deterministic_two_compiles_same_inputs():
    """Equal bundles with equal names and file maps should render to identical zip bytes."""
    b1 = HiagentBundle(bundle_name="bn", files={"index.yaml": {"a": 1}})
    b2 = HiagentBundle(bundle_name="bn", files={"index.yaml": {"a": 1}})
    assert b1.to_zip_bytes() == b2.to_zip_bytes()
