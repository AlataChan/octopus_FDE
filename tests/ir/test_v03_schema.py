import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

SCHEMAS = Path(__file__).resolve().parents[2] / "schemas"


def load_schema():
    return json.loads((SCHEMAS / "ir-v0.3.schema.json").read_text())


def test_schema_is_valid_jsonschema():
    schema = load_schema()
    Draft202012Validator.check_schema(schema)


def test_ir_version_is_const_0_3():
    schema = load_schema()
    assert schema["properties"]["ir_version"] == {"const": "0.3"}


def test_metadata_requires_rationale():
    schema = load_schema()
    md = schema["$defs"]["Metadata"]
    assert "rationale" in md["required"]
    assert md["properties"]["rationale"]["minLength"] >= 1


def test_registry_version_is_sha_pattern():
    schema = load_schema()
    rv = schema["$defs"]["RegistryRef"]["properties"]["registry_version"]
    assert rv["pattern"] == r"^sha:[0-9a-f]{7,40}$"


def test_agent_budget_requires_max_wall_clock_s():
    schema = load_schema()
    ab = schema["$defs"]["AgentBudget"]
    assert "max_wall_clock_s" in ab["required"]
    assert ab["properties"]["max_wall_clock_s"]["minimum"] == 1
    assert ab["properties"]["max_wall_clock_s"]["maximum"] == 3600


def test_every_node_requires_rationale():
    schema = load_schema()
    for node_def in [
        "TriggerNode", "LLMNode", "RetrievalNode", "HTTPNode", "CodeNode",
        "ConditionNode", "LoopNode", "ParallelNode", "AgentNode", "OutputNode",
    ]:
        n = schema["$defs"][node_def]
        assert "rationale" in n["required"], f"{node_def} missing rationale in required"
        assert n["properties"]["rationale"]["minLength"] >= 1


def test_typename_includes_null():
    schema = load_schema()
    assert "null" in schema["$defs"]["TypeName"]["enum"]


def test_edge_has_optional_data_flag():
    schema = load_schema()
    edge = schema["$defs"]["Edge"]
    assert "data" in edge["properties"]
    assert edge["properties"]["data"]["type"] == "boolean"
    assert edge["properties"]["data"]["default"] is True


def test_minimal_v03_doc_validates():
    schema = load_schema()
    doc = {
        "ir_version": "0.3",
        "metadata": {
            "name": "smoke",
            "owner": "ops",
            "rationale": "smoke test",
        },
        "registry_ref": {
            "registry_version": "sha:0000000",
            "tools": [], "datasets": [], "credentials": [],
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
    Draft202012Validator(schema).validate(doc)


def test_doc_without_rationale_rejected():
    schema = load_schema()
    doc = {
        "ir_version": "0.3",
        "metadata": {"name": "smoke", "owner": "ops"},
        "registry_ref": {"registry_version": "sha:0000000"},
        "policy": {},
        "inputs": [], "outputs": [],
        "nodes": [{"id": "start", "type": "trigger", "mode": "manual"}],
        "edges": [],
    }
    with pytest.raises(Exception):
        Draft202012Validator(schema).validate(doc)
