from loom.validator.errors import ValidationFailure, fmt_for_planner


def test_fmt_for_planner_human_readable():
    fs = [
        ValidationFailure(bucket="schema", detail="missing rationale", location="nodes[1]"),
        ValidationFailure(bucket="reference", detail="${miss.x} not produced", location="nodes[2].prompt"),
    ]
    s = fmt_for_planner(fs)
    assert "schema" in s
    assert "reference" in s
    assert "nodes[1]" in s
    assert "${miss.x}" in s
