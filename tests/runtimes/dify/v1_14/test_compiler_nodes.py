import json
from pathlib import Path

from loom.ir.models import IRDocument
from loom.runtimes.dify.v1_14.compiler import compile_ir

ROOT = Path(__file__).resolve().parents[4]


def _load(name: str) -> IRDocument:
    return IRDocument.model_validate(json.loads((ROOT / "examples" / "ir" / name).read_text()))


def test_ecommerce_faq_emits_yaml():
    ir = _load("01-ecommerce-customer-faq.json")
    yaml_text, warnings = compile_ir(ir)
    assert warnings == []
    assert yaml_text.startswith("app:")
    assert "workflow:" in yaml_text
    assert "knowledge-retrieval" in yaml_text or "retrieval" in yaml_text
    assert "llm" in yaml_text


def test_ecommerce_order_exception_emits_yaml():
    ir = _load("05-ecommerce-order-exception.json")
    yaml_text, warnings = compile_ir(ir)
    assert warnings == []
    assert "code" in yaml_text
    assert "if-else" in yaml_text
