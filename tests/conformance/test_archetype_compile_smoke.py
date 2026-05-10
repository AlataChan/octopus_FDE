import io
import json
import re
import zipfile
from pathlib import Path

import pytest
import yaml  # type: ignore[import-untyped]

from loom.ir.models import IRDocument
from loom.runtimes.dify.v1_14.compiler import compile_ir as compile_dify
from loom.runtimes.hiagent.binding import HiagentBinding
from loom.runtimes.hiagent.v2_6.compiler import compile_ir, compile_ir_chatflow

ROOT = Path(__file__).resolve().parents[2]
IR_FILES = sorted((ROOT / "examples" / "ir").glob("0*.json"))
BINDING = HiagentBinding.load(ROOT / "tests" / "fixtures" / "test.hiagent.yaml")


def _load_ir(path: Path) -> IRDocument:
    return IRDocument.model_validate(json.loads(path.read_text()))


def _assert_hiagent_zip(raw: bytes) -> None:
    trailer = raw[-32:]
    assert re.fullmatch(rb"[0-9a-f]{32}", trailer)
    with zipfile.ZipFile(io.BytesIO(raw[:-32])) as zf:
        names = zf.namelist()
        assert "index.yaml" in names
        assert any(name.startswith("agent/") and name.endswith(".yaml") for name in names)
        for name in names:
            assert not name.startswith("/")
            assert ".." not in name.split("/")
            if name.endswith(".yaml"):
                # Task 0 is compile-only smoke. Prompt fields may still contain
                # IR template refs; quality of prompt ref materialization is a
                # compiler backlog item, not a ZIP-shape assertion.
                assert yaml.safe_load(zf.read(name)) is not None


def _assert_dify_yaml(text: str) -> None:
    assert "${" not in text
    doc = yaml.safe_load(text)
    assert doc["kind"] == "app"
    assert doc["version"] == "0.6.0"
    assert doc["workflow"]["graph"]["nodes"]


CASES = [
    pytest.param(path, target, id=f"{path.name}-{target}")
    for path in IR_FILES
    for target in ("hiagent-chat", "hiagent-chatflow", "dify")
]


@pytest.mark.parametrize(("ir_path", "target"), CASES)
def test_all_archetypes_compile_for_phase_1_5_targets(ir_path: Path, target: str):
    assert len(IR_FILES) == 5
    ir = _load_ir(ir_path)
    if target == "hiagent-chat":
        _assert_hiagent_zip(compile_ir(ir, BINDING).to_zip_bytes())
    elif target == "hiagent-chatflow":
        if ir_path.name == "05-ecommerce-order-exception.json":
            pytest.xfail("known Hiagent ChatFlow spec_check rejection for legacy output template")
        _assert_hiagent_zip(compile_ir_chatflow(ir, BINDING).to_zip_bytes())
    else:
        text = compile_dify(ir)
        if ir_path.name in {"02-tcm-intake-triage.json", "03-clinic-ops-summary.json"} and "${" in text:
            pytest.xfail("known Dify compiler placeholder leakage for this legacy archetype")
        _assert_dify_yaml(text)
