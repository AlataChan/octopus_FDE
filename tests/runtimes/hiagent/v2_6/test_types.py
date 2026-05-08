import pytest

from loom.runtimes.hiagent.v2_6.types import UnmappableTypeError, to_hiagent_type_code


def test_string_zero():
    assert to_hiagent_type_code("string") == 0


def test_number_three():
    assert to_hiagent_type_code("number") == 3


def test_boolean_two():
    assert to_hiagent_type_code("boolean") == 2


def test_json_nine():
    assert to_hiagent_type_code("json") == 9


def test_array_five():
    assert to_hiagent_type_code("string[]") == 5
    assert to_hiagent_type_code("number[]") == 5
    assert to_hiagent_type_code("json[]") == 5


def test_null_six():
    assert to_hiagent_type_code("null") == 6


def test_compound_array_raises():
    with pytest.raises(UnmappableTypeError):
        to_hiagent_type_code("array<string>")


def test_compound_object_raises():
    with pytest.raises(UnmappableTypeError):
        to_hiagent_type_code("object<{a: string}>")


def test_unknown_raises():
    with pytest.raises(UnmappableTypeError):
        to_hiagent_type_code("weird")
