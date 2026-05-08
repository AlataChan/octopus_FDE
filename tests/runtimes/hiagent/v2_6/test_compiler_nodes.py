import json
from pathlib import Path

from loom.ir.models import IRDocument
from loom.runtimes.hiagent.v2_6.compiler import compile_ir

ROOT = Path(__file__).resolve().parents[4]


def _load(name: str) -> IRDocument:
    return IRDocument.model_validate(json.loads((ROOT / "examples" / "ir" / name).read_text()))


def test_ecommerce_faq_emits_workflow_json():
    ir = _load("01-ecommerce-customer-faq.json")
    text = compile_ir(ir)
    # JSON not YAML
    doc = json.loads(text)
    types = {n["type"] for n in doc["workflow"]["nodes"]}
    assert "Start" in types
    assert "KnowledgeBase" in types
    assert "LLM" in types
    assert "End" in types
    assert "edges" in doc["workflow"]


def test_ecommerce_order_exception_emits_workflow_json():
    ir = _load("05-ecommerce-order-exception.json")
    text = compile_ir(ir)
    doc = json.loads(text)
    types = {n["type"] for n in doc["workflow"]["nodes"]}
    assert "Start" in types
    assert "LLM" in types
    # Order-exception archetype uses HTTP/retrieval - at least one external call type
    assert "HTTPRequest" in types or "KnowledgeBase" in types
