import pytest

from loom.validator.typecheck import (
    NodeOutputs,
    TypeMismatch,
    loop_item_type,
    narrow_branch,
    parallel_merge_type,
    parse_type,
    typecheck_edge,
)


def test_parse_primitives_and_compounds():
    assert parse_type("string").name == "string"
    arr = parse_type("array<string>")
    assert arr.name == "array" and arr.params[0].name == "string"
    obj = parse_type("object<{a: string, b: number}>")
    assert obj.name == "object"
    union = parse_type("union<string | null>")
    assert union.name == "union"


def test_typecheck_edge_pass():
    src_outs = NodeOutputs({"chunks": parse_type("string[]")})
    typecheck_edge(src_outs, ref_path=("chunks",), expected=parse_type("string[]"))


def test_typecheck_edge_fail():
    src_outs = NodeOutputs({"chunks": parse_type("string[]")})
    with pytest.raises(TypeMismatch):
        typecheck_edge(src_outs, ref_path=("chunks",), expected=parse_type("number"))


def test_narrow_branch_with_not_null_predicate():
    out = parse_type("union<string | null>")
    narrowed = narrow_branch(out, predicate="${x} != null")
    assert narrowed.name == "string"


def test_loop_item_over_array():
    item, idx = loop_item_type(parse_type("array<string>"))
    assert item.name == "string"
    assert idx.name == "number"


def test_parallel_merge_concat():
    branches = [parse_type("string"), parse_type("string")]
    out = parallel_merge_type("concat", branches, branch_keys=["a", "b"])
    assert out.name == "array"
    assert out.params[0].name == "string"


def test_parallel_merge_object_merge():
    branches = [parse_type("string"), parse_type("number")]
    out = parallel_merge_type("object_merge", branches, branch_keys=["a", "b"])
    assert out.name == "object"


def test_parallel_merge_first_success():
    branches = [parse_type("string"), parse_type("number")]
    out = parallel_merge_type("first_success", branches, branch_keys=["a", "b"])
    assert out.name == "union"


def test_concat_rejects_inconsistent_branches():
    branches = [parse_type("string"), parse_type("number")]
    with pytest.raises(TypeMismatch):
        parallel_merge_type("concat", branches, branch_keys=["a", "b"])
