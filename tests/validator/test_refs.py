import pytest

from loom.validator.refs import RefParseError, VarRef, parse_refs


def test_simple_node_ref():
    refs = parse_refs("${retrieve.chunks}")
    assert refs == [VarRef(node_id="retrieve", path=("chunks",))]


def test_nested_field_ref():
    refs = parse_refs("hi ${a.b.c} bye")
    assert refs == [VarRef(node_id="a", path=("b", "c"))]


def test_array_index_ref():
    refs = parse_refs("${rerank.top_indices[0]}")
    assert refs == [VarRef(node_id="rerank", path=("top_indices", "[0]"))]


def test_input_ref():
    refs = parse_refs("Query: ${input.query}")
    assert refs == [VarRef(node_id="input", path=("query",))]


def test_loop_item_and_index():
    refs = parse_refs("${loop_main.item} at ${loop_main.index}")
    assert refs == [
        VarRef(node_id="loop_main", path=("item",)),
        VarRef(node_id="loop_main", path=("index",)),
    ]


def test_escaped_dollar_not_a_ref():
    refs = parse_refs("price is $${value}")
    assert refs == []


def test_multiple_refs_in_string():
    refs = parse_refs("${a.b} and ${c.d}")
    assert {r.node_id for r in refs} == {"a", "c"}


def test_unterminated_ref_rejected():
    with pytest.raises(RefParseError):
        parse_refs("${a.b")


def test_invalid_node_id_rejected():
    with pytest.raises(RefParseError):
        parse_refs("${1node.x}")  # leading digit


def test_empty_path_rejected():
    with pytest.raises(RefParseError):
        parse_refs("${node_only}")  # missing field
