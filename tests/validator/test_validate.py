import json
from pathlib import Path

from loom.validator.validate import validate
from loom.validator.registry import Registry

ROOT = Path(__file__).resolve().parents[2]


def test_clean_ecommerce_faq_archetype_passes():
    doc = json.loads((ROOT / "examples" / "ir" / "01-ecommerce-customer-faq.json").read_text())
    failures = validate(doc, scope="ecommerce/kb")
    assert failures == [], failures


def test_missing_rationale_caught_as_schema_failure():
    doc = json.loads((ROOT / "examples" / "ir" / "01-ecommerce-customer-faq.json").read_text())
    del doc["nodes"][1]["rationale"]
    failures = validate(doc, scope="ecommerce/kb")
    assert any(f.bucket == "schema" for f in failures)


def test_unknown_var_ref_caught_as_reference_failure():
    doc = json.loads((ROOT / "examples" / "ir" / "01-ecommerce-customer-faq.json").read_text())
    # rerank prompt references ${nonexistent.x}
    doc["nodes"][2]["prompt"] = "Bad ref ${nonexistent.x}"
    failures = validate(doc, scope="ecommerce/kb")
    assert any(f.bucket == "reference" for f in failures)


def test_out_of_scope_dataset_caught_as_registry_failure():
    doc = json.loads((ROOT / "examples" / "ir" / "01-ecommerce-customer-faq.json").read_text())
    failures = validate(doc, scope="some-other-team/foo")
    # product_kb / policy_kb are scoped to ecommerce/kb — out-of-scope here
    assert any(f.bucket == "policy" or f.bucket == "reference" for f in failures), failures


def test_unknown_ir_version_returns_failure_instead_of_raising():
    doc = json.loads((ROOT / "examples" / "ir" / "01-ecommerce-customer-faq.json").read_text())
    doc["ir_version"] = "9.9"
    failures = validate(doc, scope="ecommerce/kb")
    assert failures == [failures[0]]
    assert failures[0].bucket == "schema"
    assert "9.9" in failures[0].detail


# ---------------------------------------------------------------------------
# Minimal fixture for graph/reference/registry tests that don't need the
# full ecommerce archetype.
# ---------------------------------------------------------------------------


def _minimal_doc() -> dict:
    return {
        "ir_version": "0.3",
        "metadata": {"name": "minimal", "owner": "o", "rationale": "r" * 10},
        "registry_ref": {
            "registry_version": Registry.load("v1").version,
            "tools": [], "datasets": [], "credentials": [],
        },
        "policy": {},
        "inputs": [{"name": "query", "type": "string", "required": True}],
        "outputs": [{"name": "answer", "type": "string"}],
        "nodes": [
            {"id": "start", "type": "trigger", "mode": "manual", "rationale": "r"},
            {
                "id": "reply", "type": "llm", "rationale": "r", "model": "m",
                "prompt": "Q: <untrusted>${input.query}</untrusted>",
                "output_schema": {"type": "object", "properties": {"answer": {"type": "string"}}},
            },
            {"id": "out", "type": "output", "rationale": "r", "bindings": {"answer": "${reply.answer}"}},
        ],
        "edges": [{"from": "start", "to": "reply"}, {"from": "reply", "to": "out"}],
    }


def test_minimal_doc_is_clean():
    failures = validate(_minimal_doc(), scope="ecommerce/kb")
    assert failures == [], failures


# ---------------------------------------------------------------------------
# H-1: graph structure — duplicate ids, dangling edges, reachability, cycles.
# ---------------------------------------------------------------------------


def test_duplicate_node_id_rejected():
    doc = _minimal_doc()
    doc["nodes"][1]["id"] = "start"  # collides with the trigger's id
    failures = validate(doc, scope="ecommerce/kb")
    assert any(f.bucket == "reference" and "duplicate node id" in f.detail for f in failures), failures


def test_edge_to_ghost_node_rejected():
    doc = _minimal_doc()
    doc["edges"].append({"from": "reply", "to": "does_not_exist"})
    failures = validate(doc, scope="ecommerce/kb")
    assert any(
        f.bucket == "reference" and "unknown node" in f.detail and "does_not_exist" in f.detail
        for f in failures
    ), failures


def test_condition_branch_to_ghost_node_rejected():
    doc = _minimal_doc()
    doc["nodes"].append({
        "id": "route", "type": "condition", "rationale": "r",
        "branches": [{"when": "${reply.answer} == 'x'", "next": "ghost_out"}],
        "default": "out",
    })
    doc["edges"].append({"from": "reply", "to": "route"})
    failures = validate(doc, scope="ecommerce/kb")
    assert any(
        f.bucket == "reference" and "unknown node" in f.detail and "ghost_out" in f.detail
        for f in failures
    ), failures


def test_missing_trigger_rejected():
    doc = _minimal_doc()
    doc["nodes"][0]["type"] = "output"
    doc["nodes"][0]["bindings"] = {"answer": "${reply.answer}"}
    del doc["nodes"][0]["mode"]
    failures = validate(doc, scope="ecommerce/kb")
    assert any(f.bucket == "reference" and "exactly one trigger node" in f.detail for f in failures), failures


def test_multiple_triggers_rejected():
    doc = _minimal_doc()
    doc["nodes"].append({"id": "start2", "type": "trigger", "mode": "manual", "rationale": "r"})
    failures = validate(doc, scope="ecommerce/kb")
    assert any(
        f.bucket == "reference" and "exactly one trigger node, found 2" in f.detail for f in failures
    ), failures


def test_missing_output_rejected():
    doc = _minimal_doc()
    doc["nodes"] = [n for n in doc["nodes"] if n["type"] != "output"]
    doc["edges"] = [e for e in doc["edges"] if e["to"] != "out"]
    failures = validate(doc, scope="ecommerce/kb")
    assert any(f.bucket == "reference" and "at least one output node" in f.detail for f in failures), failures


def test_unreachable_node_rejected():
    doc = _minimal_doc()
    doc["nodes"].append({
        "id": "orphan", "type": "llm", "rationale": "r", "model": "m",
        "prompt": "unused",
        "output_schema": {"type": "object", "properties": {"x": {"type": "string"}}},
    })
    failures = validate(doc, scope="ecommerce/kb")
    assert any(
        f.bucket == "reference" and "orphan" in f.detail and "not reachable" in f.detail for f in failures
    ), failures


def test_cycle_rejected():
    doc = _minimal_doc()
    # reply -> out -> back to reply: a real cycle, not a declared loop.
    doc["edges"].append({"from": "out", "to": "reply"})
    failures = validate(doc, scope="ecommerce/kb")
    assert any(f.bucket == "reference" and "cycle" in f.detail for f in failures), failures


# ---------------------------------------------------------------------------
# H-1: reference legality — upstream/forward references, field-path checks.
# ---------------------------------------------------------------------------


def test_forward_reference_to_downstream_node_rejected():
    doc = _minimal_doc()
    # "reply" (upstream of "out") illegally references "out"'s own binding.
    doc["nodes"][1]["prompt"] = "Q: ${out.answer}"
    failures = validate(doc, scope="ecommerce/kb")
    assert any(
        f.bucket == "reference" and "not produced upstream" in f.detail for f in failures
    ), failures


def test_reference_to_nonexistent_field_rejected():
    doc = _minimal_doc()
    doc["nodes"][2]["bindings"]["answer"] = "${reply.nonexistent_field}"
    failures = validate(doc, scope="ecommerce/kb")
    assert any(
        f.bucket == "type_flow" and "nonexistent_field" in f.detail for f in failures
    ), failures


def test_loop_body_sibling_reference_is_legal():
    """Mirrors the 04-tcm-followup archetype pattern: a body node may
    reference an earlier sibling with no top-level `edges` connecting them
    (loop bodies have no `edges` construct of their own)."""
    doc = _minimal_doc()
    doc["nodes"][1] = {
        "id": "research_loop", "type": "loop", "rationale": "r",
        "over": "${input.query}", "as": "item", "max_iterations": 3,
        "body": [
            {
                "id": "research_agent", "type": "llm", "rationale": "r", "model": "m",
                "prompt": "Q: <untrusted>${input.query}</untrusted>",
                "output_schema": {"type": "object", "properties": {"findings": {"type": "string"}}},
            },
            {
                "id": "normalize", "type": "code", "rationale": "r", "language": "python",
                "source": "return {'summary': finding}",
                "inputs": {"finding": "${research_agent.findings}"},
                "output_schema": {"type": "object", "properties": {"summary": {"type": "string"}}},
            },
        ],
    }
    doc["edges"] = [{"from": "start", "to": "research_loop"}, {"from": "research_loop", "to": "out"}]
    doc["nodes"][2]["bindings"]["answer"] = "${research_loop.collected}"
    failures = validate(doc, scope="ecommerce/kb")
    assert failures == [], failures


# ---------------------------------------------------------------------------
# H-8: registry pin verification + declared-usage cross-check.
# ---------------------------------------------------------------------------


def test_registry_pin_mismatch_rejected():
    doc = _minimal_doc()
    doc["registry_ref"]["registry_version"] = "sha:0000000"
    failures = validate(doc, scope="ecommerce/kb")
    assert any(
        f.bucket == "policy" and "does not match" in f.detail and "registry_ref.registry_version" in (f.location or "")
        for f in failures
    ), failures


def test_dataset_used_but_not_declared_in_registry_ref_rejected():
    doc = _minimal_doc()
    doc["nodes"][1] = {
        "id": "retrieve", "type": "retrieval", "rationale": "r",
        "dataset": "product_kb", "query": "<untrusted>${input.query}</untrusted>",
    }
    doc["edges"] = [{"from": "start", "to": "retrieve"}, {"from": "retrieve", "to": "out"}]
    doc["nodes"][2]["bindings"]["answer"] = "${retrieve.chunks}"
    # registry_ref.datasets deliberately left empty even though "retrieve" uses product_kb.
    failures = validate(doc, scope="ecommerce/kb")
    assert any(
        f.bucket == "policy" and "product_kb" in f.detail and "not declared in registry_ref.datasets" in f.detail
        for f in failures
    ), failures


def test_credential_used_but_not_declared_in_registry_ref_rejected():
    doc = _minimal_doc()
    doc["nodes"][1] = {
        "id": "call", "type": "http", "rationale": "r", "method": "GET",
        "url": "https://admin.shopify.com/orders", "credential": "shopify_api",
    }
    doc["edges"] = [{"from": "start", "to": "call"}, {"from": "call", "to": "out"}]
    doc["nodes"][2]["bindings"]["answer"] = "${call.body}"
    failures = validate(doc, scope="ecommerce/ops")
    assert any(
        f.bucket == "policy" and "shopify_api" in f.detail and "not declared in registry_ref.credentials" in f.detail
        for f in failures
    ), failures


# ---------------------------------------------------------------------------
# H-3: credentialed HTTP host allowlist / SSRF prevention.
# ---------------------------------------------------------------------------


def _http_doc(url: str, *, credential: str = "shopify_api") -> dict:
    doc = _minimal_doc()
    doc["registry_ref"]["credentials"] = [credential]
    doc["nodes"][1] = {
        "id": "call", "type": "http", "rationale": "r", "method": "GET",
        "url": url, "credential": credential,
    }
    doc["edges"] = [{"from": "start", "to": "call"}, {"from": "call", "to": "out"}]
    doc["nodes"][2]["bindings"]["answer"] = "${call.body}"
    return doc


def test_credentialed_http_fully_variable_url_rejected():
    doc = _http_doc("${input.url}")
    failures = validate(doc, scope="ecommerce/ops")
    assert any(
        f.bucket == "policy" and "static https" in f.detail for f in failures
    ), failures


def test_credentialed_http_host_not_allowlisted_rejected():
    doc = _http_doc("https://evil.example.com/steal")
    failures = validate(doc, scope="ecommerce/ops")
    assert any(
        f.bucket == "policy" and "evil.example.com" in f.detail and "allowed_hosts" in f.detail
        for f in failures
    ), failures


def test_credentialed_http_private_network_target_rejected():
    doc = _http_doc("http://169.254.169.254/latest/meta-data")
    failures = validate(doc, scope="ecommerce/ops")
    assert any(
        f.bucket == "policy" and "loopback/link-local/private" in f.detail for f in failures
    ), failures


def test_credentialed_http_allowlisted_host_passes():
    doc = _http_doc("https://admin.shopify.com/orders")
    failures = validate(doc, scope="ecommerce/ops")
    assert failures == [], failures
