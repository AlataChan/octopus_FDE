import pytest

from loom.runtimes.hiagent.v2_6.varref import (
    VarRefParseError,
    find_varrefs,
    is_varref,
    parse_varref,
)


def test_parse_simple():
    assert parse_varref("${a.b}") == ("a", "b")


def test_parse_nested():
    assert parse_varref("${a.b.c}") == ("a", "b.c")


def test_parse_array_index():
    assert parse_varref("${a.b[0]}") == ("a", "b.[0]")


def test_parse_only_index():
    assert parse_varref("${a[0]}") == ("a", "[0]")


def test_empty_path_rejected():
    with pytest.raises(VarRefParseError):
        parse_varref("${a}")


def test_invalid_id_rejected():
    with pytest.raises(VarRefParseError):
        parse_varref("${1abc.x}")


def test_is_varref_true():
    assert is_varref("${a.b}")


def test_is_varref_false_with_text():
    assert not is_varref("hi ${a.b} bye")


def test_find_varrefs_multiple():
    assert find_varrefs("${a.b} and ${c.d}") == [("a", "b"), ("c", "d")]


def test_find_varrefs_with_text():
    assert find_varrefs("Query: ${input.query}") == [("input", "query")]
