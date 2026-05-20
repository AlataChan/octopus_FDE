import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from loom.ir.models import IRDocument
from loom.ir.schema import load_schema, load_schema_for_doc

SCHEMAS = Path(__file__).resolve().parents[2] / "schemas"
FEW_SHOT = Path(__file__).resolve().parents[2] / "loom" / "planner" / "prompts" / "few_shot"


def _minimal_doc(version: str) -> dict:
    return {
        "ir_version": version,
        "metadata": {
            "name": "smoke",
            "owner": "ops",
            "rationale": "smoke test",
        },
        "registry_ref": {
            "registry_version": "sha:0000000",
            "tools": [],
            "datasets": [],
            "credentials": [],
        },
        "policy": {},
        "inputs": [],
        "outputs": [],
        "nodes": [
            {
                "id": "start",
                "type": "trigger",
                "mode": "manual",
                "rationale": "entry",
            },
            {
                "id": "out",
                "type": "output",
                "rationale": "terminal",
                "bindings": {"x": "${start.y}"},
            },
        ],
        "edges": [{"from": "start", "to": "out"}],
    }


@pytest.mark.parametrize("version", ["0.3", "0.4"])
def test_schema_versions_are_valid(version: str):
    schema = load_schema(version)
    Draft202012Validator.check_schema(schema)
    assert schema["properties"]["ir_version"] == {"const": version}


@pytest.mark.parametrize("version", ["0.3", "0.4"])
def test_schema_dispatch_validates_matching_version(version: str):
    doc = _minimal_doc(version)
    Draft202012Validator(load_schema_for_doc(doc)).validate(doc)
    assert IRDocument.model_validate(doc).ir_version == version


def test_v04_policy_fields_are_rejected_for_v03():
    doc = _minimal_doc("0.3")
    doc["policy"] = {"audit": {"log_decisions": True, "retention_days": 90}}
    with pytest.raises(Exception):
        Draft202012Validator(load_schema_for_doc(doc)).validate(doc)
    with pytest.raises(Exception):
        IRDocument.model_validate(doc)


def test_v04_policy_fields_are_accepted_for_v04():
    doc = _minimal_doc("0.4")
    doc["policy"] = {
        "guardrails": {
            "input_filters": ["pii"],
            "output_filters": ["medical_advice"],
            "custom_patterns": ["(?i)password"],
        },
        "escalation": {
            "confidence_min": 0.7,
            "confidence_from": "${judge.confidence}",
            "handoff_node": "out",
        },
        "audit": {"log_inputs": False, "log_decisions": True, "retention_days": 90},
    }
    Draft202012Validator(load_schema_for_doc(doc)).validate(doc)
    assert IRDocument.model_validate(doc).policy.audit is not None


@pytest.mark.parametrize("path", sorted(FEW_SHOT.glob("*.json")), ids=lambda p: p.name)
def test_existing_few_shots_remain_v03(path: Path):
    raw = json.loads(path.read_text())
    doc = raw["ir"]
    assert doc["ir_version"] == "0.3"
    Draft202012Validator(load_schema("0.3")).validate(doc)
    assert IRDocument.model_validate(doc).ir_version == "0.3"
