import copy
import json
from pathlib import Path
from typing import Any

from loom.ir.canonicalize import canonical_ir, canonical_ir_hash
from loom.ir.models import IRDocument

ROOT = Path(__file__).resolve().parents[2]


def _load_example(name: str) -> dict:
    return json.loads((ROOT / "examples" / "ir" / name).read_text())


def _ecommerce_faq():
    return _load_example("01-ecommerce-customer-faq.json")


def _nested_retrieval_loop_doc(*, top_k: int | None = None, rerank: bool | None = None) -> dict[str, Any]:
    """Minimal but schema-real doc with a RetrievalNode nested in a loop body."""
    lookup: dict[str, Any] = {
        "id": "lookup", "type": "retrieval", "rationale": "look up per-item context",
        "dataset": "kb", "query": "${item}",
    }
    if top_k is not None:
        lookup["top_k"] = top_k
    if rerank is not None:
        lookup["rerank"] = rerank
    doc = {
        "ir_version": "0.3",
        "metadata": {"name": "nested retrieval", "owner": "o",
                     "rationale": "regression fixture for nested default-strip dispatch"},
        "registry_ref": {"registry_version": "sha:0000000", "tools": [], "datasets": [], "credentials": []},
        "policy": {},
        "inputs": [], "outputs": [],
        "nodes": [
            {"id": "start", "type": "trigger", "mode": "manual", "rationale": "entry"},
            {
                "id": "loop", "type": "loop", "rationale": "iterate over items",
                "over": "${input.items}", "as": "item", "max_iterations": 3,
                "body": [lookup],
            },
            {"id": "out", "type": "output", "rationale": "bind", "bindings": {"x": "${loop}"}},
        ],
        "edges": [{"from": "start", "to": "loop"}, {"from": "loop", "to": "out"}],
    }
    IRDocument.model_validate(doc)  # fail fast if this fixture drifts from the real schema
    return doc


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


def test_retrieval_node_top_k_and_rerank_stripped_when_explicit_default():
    """Per-type strip rules must fire for top-level nodes, not just Edge."""
    doc = _ecommerce_faq()
    retrieve = next(n for n in doc["nodes"] if n["id"] == "retrieve")
    retrieve["top_k"] = 5
    retrieve["rerank"] = False
    out = canonical_ir(doc)
    out_retrieve = next(n for n in out["nodes"] if n["id"] == "retrieve")
    assert "top_k" not in out_retrieve
    assert "rerank" not in out_retrieve


def test_retrieval_node_hash_equal_for_explicit_vs_omitted_default():
    doc = _ecommerce_faq()
    retrieve = next(n for n in doc["nodes"] if n["id"] == "retrieve")
    retrieve["top_k"] = 5
    retrieve["rerank"] = False
    explicit_hash = canonical_ir_hash(doc)

    omitted = copy.deepcopy(doc)
    omitted_retrieve = next(n for n in omitted["nodes"] if n["id"] == "retrieve")
    del omitted_retrieve["top_k"]
    del omitted_retrieve["rerank"]
    assert canonical_ir_hash(omitted) == explicit_hash


def test_nested_retrieval_node_defaults_stripped_and_hash_matches_omitted():
    """The exact H-5 bug: a node under LoopNode.body was parented "Node", so
    RetrievalNode-specific strip rules never matched for nested nodes either.
    """
    explicit = _nested_retrieval_loop_doc(top_k=5, rerank=False)
    omitted = _nested_retrieval_loop_doc()
    assert canonical_ir_hash(explicit) == canonical_ir_hash(omitted)

    out = canonical_ir(explicit)
    nested_lookup = next(n for n in out["nodes"] if n["id"] == "loop")["body"][0]
    assert "top_k" not in nested_lookup
    assert "rerank" not in nested_lookup


def test_nested_retrieval_node_semantic_change_still_changes_hash():
    a = _nested_retrieval_loop_doc(top_k=10)
    b = _nested_retrieval_loop_doc(top_k=10)
    b["nodes"][1]["body"][0]["dataset"] = "other_kb"
    assert canonical_ir_hash(a) != canonical_ir_hash(b)


def test_reordering_top_level_nodes_and_edges_is_hash_invariant():
    """Top-level node/edge order carries no meaning — the edges graph does."""
    doc = _ecommerce_faq()
    reordered = copy.deepcopy(doc)
    reordered["nodes"] = list(reversed(reordered["nodes"]))
    reordered["edges"] = list(reversed(reordered["edges"]))
    assert canonical_ir_hash(doc) == canonical_ir_hash(reordered)


def test_reordering_loop_body_changes_hash():
    """Unlike top-level nodes, LoopNode.body order IS semantic (no separate
    edges list encodes intra-body sequencing) and must not be sorted away.
    """
    doc = _load_example("04-tcm-followup.json")
    reordered = copy.deepcopy(doc)
    loop = next(n for n in reordered["nodes"] if n["type"] == "loop")
    loop["body"] = list(reversed(loop["body"]))
    assert canonical_ir_hash(doc) != canonical_ir_hash(reordered)
