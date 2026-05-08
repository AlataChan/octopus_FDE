import pytest

from loom.runtimes.hiagent.v2_6.layout import LayoutError, topological_layout


def test_linear_chain():
    assert topological_layout(["a", "b", "c"], [("a", "b"), ("b", "c")]) == {
        "a": (0.0, 0.0),
        "b": (300.0, 0.0),
        "c": (600.0, 0.0),
    }


def test_diamond():
    positions = topological_layout(
        ["a", "b", "c", "d"],
        [("a", "b"), ("a", "c"), ("b", "d"), ("c", "d")],
    )
    assert positions["a"] == (0.0, 0.0)
    assert positions["d"] == (600.0, 0.0)
    assert positions["b"][0] == positions["c"][0] == 300.0
    assert {positions["b"][1], positions["c"][1]} == {-100.0, 100.0}


def test_orphan_node():
    positions = topological_layout(["a", "b", "d"], [("a", "b")])
    assert positions["a"][0] == 0.0
    assert positions["d"][0] == 0.0
    assert positions["b"] == (300.0, 0.0)


def test_cycle_raises():
    with pytest.raises(LayoutError):
        topological_layout(["a", "b"], [("a", "b"), ("b", "a")])


def test_empty():
    assert topological_layout([], []) == {}
