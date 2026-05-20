import json
import re
from pathlib import Path
from typing import Any

import pytest
import yaml

from loom.ir.models import IRDocument
from loom.runtimes.dify.v1_14.compiler import compile_ir

ROOT = Path(__file__).resolve().parents[4]
GOLD_SAMPLES = [
    ROOT / "程远帆（0416).yml",
    ROOT / "沈清禾（0416).yml",
]


def _load_ir(name: str) -> IRDocument:
    return IRDocument.model_validate(json.loads((ROOT / "examples" / "ir" / name).read_text()))


def _compile_doc(ir: IRDocument) -> dict[str, Any]:
    text, warnings = compile_ir(ir)
    assert warnings == []
    return yaml.safe_load(text)


def _branch_ir() -> IRDocument:
    return IRDocument.model_validate({
        "ir_version": "0.3",
        "metadata": {
            "name": "Dify Branch Test",
            "description": "Fixture for Dify selector emission.",
            "owner": "tests",
            "rationale": "Exercise condition, code, and end selector shapes.",
        },
        "registry_ref": {
            "registry_version": "sha:0000000",
            "tools": [],
            "datasets": [],
            "credentials": [],
        },
        "policy": {"default_timeout_s": 30},
        "inputs": [{"name": "query", "type": "string", "required": True}],
        "outputs": [{"name": "answer", "type": "string", "required": True}],
        "nodes": [
            {
                "id": "start",
                "type": "trigger",
                "mode": "manual",
                "rationale": "Accept user input.",
            },
            {
                "id": "rerank",
                "type": "llm",
                "model": "configured-small-model",
                "prompt": "${input.query}",
                "rationale": "Score confidence.",
                "output_schema": {
                    "type": "object",
                    "properties": {"confidence": {"type": "number"}},
                },
            },
            {
                "id": "answer",
                "type": "llm",
                "model": "configured-small-model",
                "prompt": "${input.query}",
                "rationale": "Draft answer.",
                "output_schema": {
                    "type": "object",
                    "properties": {"answer": {"type": "string"}},
                },
            },
            {
                "id": "route",
                "type": "condition",
                "rationale": "Route by confidence.",
                "branches": [{"when": "${rerank.confidence} < 0.5", "next": "fallback"}],
                "default": "out",
            },
            {
                "id": "fallback",
                "type": "code",
                "language": "python",
                "source": "return {'answer': answer}",
                "inputs": {"answer": "${answer}"},
                "rationale": "Fallback answer.",
                "output_schema": {
                    "type": "object",
                    "properties": {"answer": {"type": "string"}},
                },
            },
            {
                "id": "out",
                "type": "output",
                "rationale": "Return answer.",
                "bindings": {"answer": "${answer.answer}"},
            },
        ],
        "edges": [
            {"from": "start", "to": "rerank"},
            {"from": "rerank", "to": "answer"},
            {"from": "answer", "to": "route"},
            {"from": "route", "to": "fallback"},
            {"from": "route", "to": "out"},
        ],
    })


@pytest.mark.parametrize("path", GOLD_SAMPLES)
def test_gold_samples_use_dify_app_graph_shape(path: Path):
    if not path.exists():
        pytest.skip(f"local Dify gold sample missing: {path.name}")
    doc = yaml.safe_load(path.read_text())
    assert {"app", "dependencies", "kind", "version", "workflow"} <= set(doc)
    assert "graph" in doc["workflow"]
    assert doc["workflow"]["graph"]["nodes"]
    assert doc["workflow"]["graph"]["edges"]
    for node in doc["workflow"]["graph"]["nodes"]:
        assert node["type"] == "custom"
        assert "type" in node["data"]
        assert "position" in node
        assert "positionAbsolute" in node
        assert "width" in node
        assert "height" in node
    for edge in doc["workflow"]["graph"]["edges"]:
        assert edge["type"] == "custom"
        assert {"source", "target", "sourceHandle", "targetHandle", "data"} <= set(edge)


def test_ecommerce_faq_compiles_to_importable_dify_shape():
    ir = _load_ir("01-ecommerce-customer-faq.json")
    doc = _compile_doc(ir)
    assert set(doc) == {"app", "dependencies", "kind", "version", "workflow"}
    assert doc["kind"] == "app"
    assert doc["version"] == "0.6.0"
    assert doc["dependencies"] == []
    assert doc["app"]["mode"] == "workflow"
    assert "loom" not in doc["app"]
    assert "policy" not in doc
    assert "inputs" not in doc
    assert "outputs" not in doc
    graph = doc["workflow"]["graph"]
    assert len(graph["nodes"]) >= len(ir.nodes)
    _assert_graph_shape(graph)


def test_compiled_yaml_has_no_raw_ir_template_refs():
    text, warnings = compile_ir(_load_ir("01-ecommerce-customer-faq.json"))
    assert warnings == []
    assert not re.search(r"\$\{[^}]+\}", text)
    assert "{{#" in text


def test_prompt_refs_use_dify_template_syntax():
    doc = _compile_doc(_load_ir("01-ecommerce-customer-faq.json"))
    llm_nodes = [
        node for node in doc["workflow"]["graph"]["nodes"]
        if node["data"]["type"] == "llm"
    ]
    assert llm_nodes
    prompt_texts = [
        prompt["text"]
        for node in llm_nodes
        for prompt in node["data"]["prompt_template"]
    ]
    assert any("{{#sys.query#}}" in text for text in prompt_texts)
    assert any("{{#retrieve.chunks#}}" in text for text in prompt_texts)
    assert all("${" not in text for text in prompt_texts)


def test_condition_code_and_end_nodes_have_selector_shapes():
    doc = _compile_doc(_branch_ir())
    graph = doc["workflow"]["graph"]
    condition = next(node for node in graph["nodes"] if node["data"]["type"] == "if-else")
    assert condition["data"]["cases"][0]["case_id"] == "true"
    assert condition["data"]["cases"][0]["conditions"][0]["variable_selector"] == [
        "rerank",
        "confidence",
    ]
    code = next(node for node in graph["nodes"] if node["data"]["type"] == "code")
    assert code["data"]["variables"][0]["value_selector"] == ["answer"]
    end = next(node for node in graph["nodes"] if node["data"]["type"] == "end")
    assert end["data"]["outputs"][0]["value_selector"] == ["answer", "answer"]
    _assert_graph_shape(graph)


def _assert_graph_shape(graph: dict[str, Any]) -> None:
    for node in graph["nodes"]:
        assert node["type"] == "custom"
        assert "type" in node["data"]
        assert isinstance(node["position"]["x"], float | int)
        assert isinstance(node["position"]["y"], float | int)
        assert node["positionAbsolute"] == node["position"]
        assert node["width"] == 242
        assert "height" in node
        assert node["sourcePosition"] == "right"
        assert node["targetPosition"] == "left"
    node_types = {node["id"]: node["data"]["type"] for node in graph["nodes"]}
    for edge in graph["edges"]:
        assert edge["type"] == "custom"
        assert edge["targetHandle"] == "target"
        assert edge["data"]["sourceType"] == node_types[edge["source"]]
        assert edge["data"]["targetType"] == node_types[edge["target"]]
