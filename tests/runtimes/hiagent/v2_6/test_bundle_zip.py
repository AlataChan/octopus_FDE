import hashlib
import io
import json
import re
import zipfile
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]

from loom.ir.models import IRDocument
from loom.runtimes.hiagent.binding import HiagentBinding
from loom.runtimes.hiagent.v2_6.compiler import compile_ir

ROOT = Path(__file__).resolve().parents[4]


def _load_ir(name: str = "01-ecommerce-customer-faq.json") -> IRDocument:
    return IRDocument.model_validate(json.loads((ROOT / "examples" / "ir" / name).read_text()))


def _test_binding() -> HiagentBinding:
    return HiagentBinding.load(ROOT / "tests" / "fixtures" / "test.hiagent.yaml")


def _zip_payload(raw: bytes) -> bytes:
    return raw[:-32]


def _zip_trailer(raw: bytes) -> str:
    return raw[-32:].decode("ascii")


def _zip_names(raw: bytes) -> list[str]:
    with zipfile.ZipFile(io.BytesIO(_zip_payload(raw))) as zf:
        return zf.namelist()


def _zip_yaml(raw: bytes, path: str) -> dict[str, Any]:
    with zipfile.ZipFile(io.BytesIO(_zip_payload(raw))) as zf:
        return yaml.safe_load(zf.read(path))


def test_zip_format_hard_rules():
    bundle = compile_ir(_load_ir(), _test_binding())
    raw = bundle.to_zip_bytes()

    names = _zip_names(raw)
    assert names
    for name in names:
        assert not name.startswith(bundle.bundle_name + "/")
        assert not name.startswith("/")
        assert "\\" not in name
        assert name.endswith(".yaml") or name.startswith("asset/upload/full/")

    assert re.fullmatch(r"[0-9a-f]{32}", _zip_trailer(raw))
    assert hashlib.md5(_zip_payload(raw)).hexdigest() == _zip_trailer(raw)


def test_zip_contains_index_agent_model_and_knowledge_sidecars():
    raw = compile_ir(_load_ir(), _test_binding()).to_zip_bytes()
    names = _zip_names(raw)

    assert "index.yaml" in names
    assert "agent/Ecommerce Customer FAQ.yaml" in names
    assert "model/configured-small-model.yaml" in names
    assert "model/configured-planner-model.yaml" in names
    assert "knowledge/product_kb.yaml" in names
    assert "knowledge/policy_kb.yaml" in names


def test_zip_sidecar_yaml_matches_depends_names():
    raw = compile_ir(_load_ir(), _test_binding()).to_zip_bytes()
    agent = _zip_yaml(raw, "agent/Ecommerce Customer FAQ.yaml")

    for model_id, entry in agent["AppDepends"]["ModelMap"].items():
        model = _zip_yaml(raw, f"model/{entry['Name']}.yaml")
        assert model["UniqueName"] == model_id
        assert model["DisplayName"] == entry["Name"]

    for dataset_id, entry in agent["AppDepends"]["KnowledgeMap"].items():
        knowledge = _zip_yaml(raw, f"knowledge/{entry['Name']}.yaml")
        assert knowledge["UniqueName"] == dataset_id
        assert knowledge["data"]["XID"] == dataset_id
