from loom.diff.ir_diff import diff_ir


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
        }
    ]


def _minimal(changes):
    out = []
    for change in changes:
        keys = ["scope", "kind", "node_id", "from", "to"]
        out.append({k: change[k] for k in keys if k in change})
    return out
