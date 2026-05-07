import copy
import json
from pathlib import Path

from loom.ir.canonicalize import canonical_ir, canonical_ir_hash

ROOT = Path(__file__).resolve().parents[2]


def _ecommerce_faq():
    return json.loads((ROOT / "examples" / "ir" / "01-ecommerce-customer-faq.json").read_text())


def test_canonical_form_is_idempotent():
    doc = _ecommerce_faq()
    once = canonical_ir(doc)
    twice = canonical_ir(once)
    assert once == twice


def test_canonical_form_strips_default_data_flag_on_edges():
    doc = _ecommerce_faq()
    for e in doc["edges"]:
        e["data"] = True  # explicit default
    out = canonical_ir(doc)
    for e in out["edges"]:
        assert "data" not in e


def test_canonical_form_keys_are_sorted():
    out = canonical_ir(_ecommerce_faq())
    keys = list(out.keys())
    assert keys == sorted(keys)


def test_rationale_preserved_verbatim():
    doc = _ecommerce_faq()
    rationale = doc["nodes"][0]["rationale"]
    out = canonical_ir(doc)
    out_node = next(n for n in out["nodes"] if n["id"] == doc["nodes"][0]["id"])
    assert out_node["rationale"] == rationale


def test_parallel_branches_sorted_by_canonical_id():
    """Order-independent compounds get sorted in canonical form."""
    # Construct a minimal IR with parallel and assert branches dict comes out sorted.
    doc = {
        "ir_version": "0.3",
        "metadata": {"name": "p", "owner": "o", "rationale": "p"},
        "registry_ref": {"registry_version": "sha:0000000",
                          "tools": [], "datasets": [], "credentials": []},
        "policy": {},
        "inputs": [], "outputs": [],
        "nodes": [
            {"id": "start", "type": "trigger", "mode": "manual", "rationale": "r"},
            {
                "id": "p", "type": "parallel", "rationale": "fan-out",
                "branches": {
                    "z": [{"id": "z1", "type": "code", "rationale": "r",
                            "language": "python", "source": "pass"}],
                    "a": [{"id": "a1", "type": "code", "rationale": "r",
                            "language": "python", "source": "pass"}],
                },
                "merge_strategy": "concat",
            },
            {"id": "out", "type": "output", "rationale": "r",
             "bindings": {"x": "${start.y}"}},
        ],
        "edges": [{"from": "start", "to": "p"}, {"from": "p", "to": "out"}],
    }
    out = canonical_ir(doc)
    par = next(n for n in out["nodes"] if n["id"] == "p")
    assert list(par["branches"].keys()) == ["a", "z"]


def test_two_equivalent_irs_hash_equal():
    a = _ecommerce_faq()
    b = copy.deepcopy(a)
    # Add a default that should be stripped:
    for e in b["edges"]:
        e["data"] = True
    assert canonical_ir_hash(a) == canonical_ir_hash(b)


def test_semantic_difference_changes_hash():
    a = _ecommerce_faq()
    b = copy.deepcopy(a)
    b["nodes"][0]["rationale"] = "different rationale on purpose"
    assert canonical_ir_hash(a) != canonical_ir_hash(b)
