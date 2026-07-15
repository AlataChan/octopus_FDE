import copy
import json
from pathlib import Path

from loom.diff.ir_diff import diff_ir
from loom.ir.models import IRDocument

ROOT = Path(__file__).resolve().parents[2]


def _load_example(name: str) -> dict:
    return json.loads((ROOT / "examples" / "ir" / name).read_text())


def _node(doc: dict, node_id: str) -> dict:
    return next(n for n in doc["nodes"] if n["id"] == node_id)


def _minimal(changes):
    out = []
    for change in changes:
        keys = ["scope", "kind", "node_id", "from", "to"]
        out.append({k: change[k] for k in keys if k in change})
    return out


def _guardrail_base() -> dict:
    """Minimal but schema-real ir_version 0.4 document (validated below)."""
    doc = {
        "ir_version": "0.4",
        "metadata": {"name": "Guardrail Test", "owner": "sec-team", "rationale": "Exercises governance diff coverage."},
        "registry_ref": {"registry_version": "sha:0000000", "tools": [], "datasets": [], "credentials": ["svc_a"]},
        "policy": {
            "default_timeout_s": 30,
            "guardrails": {"input_filters": ["pii"], "output_filters": [], "custom_patterns": []},
            "audit": {"log_inputs": False, "log_decisions": True, "retention_days": 90},
        },
        "inputs": [{"name": "query", "type": "string", "required": True}],
        "outputs": [{"name": "answer", "type": "string"}],
        "nodes": [
            {"id": "start", "type": "trigger", "mode": "manual", "rationale": "entry"},
            {"id": "call", "type": "http", "method": "GET", "url": "${input.query}",
             "credential": "svc_a", "rationale": "call"},
            {"id": "out", "type": "output", "bindings": {"answer": "${call.body}"}, "rationale": "bind"},
        ],
        "edges": [{"from": "start", "to": "call"}, {"from": "call", "to": "out"}],
    }
    IRDocument.model_validate(doc)  # fail fast if the fixture drifts from the real schema
    return doc


def test_diff_ir_reports_node_add_remove_rename_and_config_fields():
    before = {
        "nodes": [
            {"id": "start", "type": "trigger", "title": "Start", "mode": "manual"},
            {"id": "llm", "type": "llm", "title": "Answer", "model": "small", "temperature": 0.1},
            {"id": "old", "type": "code", "source": "return a"},
        ],
        "edges": [{"from": "start", "to": "llm"}, {"from": "llm", "to": "old"}],
    }
    after = {
        "nodes": [
            {"id": "start", "type": "trigger", "title": "Start", "mode": "manual"},
            {"id": "llm", "type": "llm", "title": "Final answer", "model": "small", "temperature": 0.3},
            {"id": "new", "type": "output", "bindings": {"answer": "${llm.raw_output}"}},
        ],
        "edges": [{"from": "start", "to": "llm"}, {"from": "llm", "to": "new"}],
    }

    result = diff_ir(before, after)

    changes = result["changes"]
    assert {"scope": "node", "kind": "removed", "node_id": "old"} in _minimal(changes)
    assert {"scope": "node", "kind": "added", "node_id": "new"} in _minimal(changes)
    assert {"scope": "node", "kind": "renamed", "node_id": "llm"} in _minimal(changes)
    config = next(c for c in changes if c["scope"] == "node" and c["kind"] == "config-changed")
    assert config["node_id"] == "llm"
    assert config["fields"] == [{"path": "temperature", "before": 0.1, "after": 0.3}]
    assert config["category"] == "config"
    assert config["risk"] == "low"
    assert {"scope": "edge", "kind": "removed", "from": "llm", "to": "old"} in _minimal(changes)
    assert {"scope": "edge", "kind": "added", "from": "llm", "to": "new"} in _minimal(changes)
    assert result["summary"]["total"] == 6


def test_diff_ir_omits_identical_fields_inside_nested_config():
    before = {"nodes": [{"id": "code", "type": "code", "config": {"a": 1, "b": 2}}], "edges": []}
    after = {"nodes": [{"id": "code", "type": "code", "config": {"a": 1, "b": 3}}], "edges": []}

    result = diff_ir(before, after)

    assert result["changes"] == [
        {
            "scope": "node",
            "kind": "config-changed",
            "node_id": "code",
            "fields": [{"path": "config.b", "before": 2, "after": 3}],
            "category": "config",
            "risk": "low",
        }
    ]


def test_diff_ir_is_a_no_op_for_explicit_vs_omitted_defaults():
    """Canonicalizing before diffing means default-vs-explicit is not drift."""
    before = _load_example("01-ecommerce-customer-faq.json")
    after = copy.deepcopy(before)
    for edge in after["edges"]:
        edge["data"] = True  # explicit default
    retrieve = _node(after, "retrieve")
    retrieve["rerank"] = False  # explicit default

    result = diff_ir(before, after)

    assert result["changes"] == []
    assert result["summary"]["total"] == 0
    assert result["hard_blocks"] == []


def test_diff_ir_flags_node_credential_swap_as_high_risk_and_masks_values():
    before = _load_example("03-clinic-ops-summary.json")
    after = copy.deepcopy(before)
    _node(after, "pull")["credential"] = "attacker_controlled_cred"

    result = diff_ir(before, after)

    config = next(
        c for c in result["changes"]
        if c["scope"] == "node" and c["node_id"] == "pull" and c["kind"] == "config-changed"
    )
    assert config["category"] == "credential"
    assert config["risk"] == "high"
    field = next(f for f in config["fields"] if f["path"] == "credential")
    assert field["before"] == "***"
    assert field["after"] == "***"
    dumped = json.dumps(result)
    assert "clinic_ops_api" not in dumped
    assert "attacker_controlled_cred" not in dumped
    assert config in result["hard_blocks"]


def test_diff_ir_flags_registry_ref_credentials_list_change_as_high_risk():
    before = _load_example("03-clinic-ops-summary.json")
    after = copy.deepcopy(before)
    after["registry_ref"]["credentials"] = ["clinic_ops_api"]  # dropped clinic_ops_webhook

    result = diff_ir(before, after)

    gov = next(c for c in result["changes"] if c["scope"] == "governance" and c["key"] == "registry_ref")
    assert gov["category"] == "credential"
    assert gov["risk"] == "high"


def test_diff_ir_flags_guardrail_removal_as_compliance_high_risk():
    before = _guardrail_base()
    after = copy.deepcopy(before)
    after["policy"]["guardrails"] = None

    result = diff_ir(before, after)

    gov = next(c for c in result["changes"] if c["scope"] == "governance" and c["key"] == "policy")
    assert gov["category"] == "compliance"
    assert gov["risk"] == "high"
    assert gov in result["hard_blocks"]


def test_diff_ir_flags_agent_budget_widened_high_but_narrowed_low():
    before = _load_example("04-tcm-followup.json")
    wider = copy.deepcopy(before)
    loop = _node(wider, "research_loop")
    agent = next(n for n in loop["body"] if n["id"] == "research_agent")
    agent["budget"]["max_tokens"] = 30000 * 4

    result = diff_ir(before, wider)
    config = next(
        c for c in result["changes"]
        if c["scope"] == "node" and c["node_id"] == "research_agent" and c["kind"] == "config-changed"
    )
    assert config["category"] == "policy"
    assert config["risk"] == "high"
    assert config["path"] == "research_loop.body"  # nested-node changes carry their ancestry

    narrower = copy.deepcopy(before)
    loop = _node(narrower, "research_loop")
    agent = next(n for n in loop["body"] if n["id"] == "research_agent")
    agent["budget"]["max_tokens"] = 1000

    result = diff_ir(before, narrower)
    config = next(
        c for c in result["changes"]
        if c["scope"] == "node" and c["node_id"] == "research_agent" and c["kind"] == "config-changed"
    )
    assert config["category"] == "policy"
    assert config["risk"] == "low"


def test_diff_ir_flags_edge_condition_change_as_control_high_risk():
    before = _guardrail_base()
    before["edges"][0]["when"] = "${input.query} != ''"
    after = copy.deepcopy(before)
    after["edges"][0]["when"] = "${input.query} == 'always'"

    result = diff_ir(before, after)

    edge_change = next(c for c in result["changes"] if c["scope"] == "edge" and c["kind"] == "changed")
    assert edge_change["from"] == "start"
    assert edge_change["to"] == "call"
    assert edge_change["category"] == "control"
    assert edge_change["risk"] == "high"
    assert edge_change["fields"] == [
        {"path": "when", "before": "${input.query} != ''", "after": "${input.query} == 'always'"}
    ]


def test_diff_ir_flags_edge_data_to_control_flip_as_high_risk():
    before = _guardrail_base()
    after = copy.deepcopy(before)
    after["edges"][0]["data"] = False

    result = diff_ir(before, after)

    edge_change = next(c for c in result["changes"] if c["scope"] == "edge" and c["kind"] == "changed")
    assert edge_change["category"] == "control"
    assert edge_change["risk"] == "high"
    assert edge_change["fields"] == [{"path": "data", "before": True, "after": False}]


def test_diff_ir_flags_condition_branch_change_as_control_high_risk():
    before = _load_example("02-tcm-intake-triage.json")
    after = copy.deepcopy(before)
    route = _node(after, "route")
    route["branches"][1]["when"] = "${extract.valid} == false"  # dropped the confidence guard

    result = diff_ir(before, after)

    config = next(
        c for c in result["changes"]
        if c["scope"] == "node" and c["node_id"] == "route" and c["kind"] == "config-changed"
    )
    assert config["category"] == "control"
    assert config["risk"] == "high"


def test_diff_ir_recurses_into_parallel_branch_nested_nodes():
    before = _load_example("05-ecommerce-order-exception.json")
    after = copy.deepcopy(before)
    parallel = _node(after, "analyze")
    urgency_node = parallel["branches"]["urgency"][0]
    urgency_node["temperature"] = 0.9

    result = diff_ir(before, after)

    config = next(
        c for c in result["changes"]
        if c["scope"] == "node" and c["node_id"] == "urgency_check" and c["kind"] == "config-changed"
    )
    assert config["path"] == "analyze.branches.urgency"


def test_diff_ir_flags_input_output_schema_changes_as_high_risk():
    before = _load_example("02-tcm-intake-triage.json")
    after = copy.deepcopy(before)
    after["outputs"].append({"name": "priority", "type": "string"})

    result = diff_ir(before, after)

    gov = next(c for c in result["changes"] if c["scope"] == "governance" and c["key"] == "outputs")
    assert gov["category"] == "schema"
    assert gov["risk"] == "high"
    assert gov["fields"] == [{"path": "[priority]", "before": None, "after": {"name": "priority", "type": "string"}}]


def test_diff_ir_truncates_oversized_string_values():
    before = {"nodes": [{"id": "code", "type": "code", "source": "a"}], "edges": []}
    huge = "x" * 5000
    after = {"nodes": [{"id": "code", "type": "code", "source": huge}], "edges": []}

    result = diff_ir(before, after)

    config = next(c for c in result["changes"] if c["scope"] == "node" and c["kind"] == "config-changed")
    field = config["fields"][0]
    assert len(field["after"]) < len(huge)
    assert field["after"].endswith("chars)")


def test_diff_ir_hard_blocks_matches_high_risk_changes_and_summary_counts():
    before = _load_example("03-clinic-ops-summary.json")
    after = copy.deepcopy(before)
    _node(after, "pull")["credential"] = "swapped"
    _node(after, "transform")["source"] = "return {}"  # low-risk, cosmetic

    result = diff_ir(before, after)

    high_risk = [c for c in result["changes"] if c.get("risk") == "high"]
    assert result["hard_blocks"] == high_risk
    assert result["summary"]["hard_blocks"] == len(high_risk)
    assert len(high_risk) == 1
    assert result["summary"]["total"] == len(result["changes"])
