import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from loom.ir.models import IRDocument

ROOT = Path(__file__).resolve().parents[2]


def test_load_ecommerce_faq_archetype_into_model():
    doc = json.loads((ROOT / "examples" / "ir" / "01-ecommerce-customer-faq.json").read_text())
    ir = IRDocument.model_validate(doc)
    assert ir.ir_version == "0.3"
    assert ir.metadata.rationale  # required in v0.3
    assert {n.id for n in ir.nodes} == {"start", "retrieve", "rerank", "answer", "out"}


def test_missing_rationale_rejected():
    doc = json.loads((ROOT / "examples" / "ir" / "01-ecommerce-customer-faq.json").read_text())
    del doc["metadata"]["rationale"]
    with pytest.raises(ValidationError):
        IRDocument.model_validate(doc)


def test_calendar_tag_registry_version_rejected():
    doc = json.loads((ROOT / "examples" / "ir" / "01-ecommerce-customer-faq.json").read_text())
    doc["registry_ref"]["registry_version"] = "2026-04-15"
    with pytest.raises(ValidationError):
        IRDocument.model_validate(doc)


def test_agent_budget_requires_wall_clock():
    doc = json.loads((ROOT / "examples" / "ir" / "01-ecommerce-customer-faq.json").read_text())
    del doc["policy"]["agent_budget"]["max_wall_clock_s"]
    with pytest.raises(ValidationError):
        IRDocument.model_validate(doc)
