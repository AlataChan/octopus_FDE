import copy
import json
from pathlib import Path

import yaml

from loom.ir.models import IRDocument
from loom.runtimes.dify.v1_14.ast import canonical_dify_ast_hash
from loom.runtimes.dify.v1_14.compiler import compile_ir

ROOT = Path(__file__).resolve().parents[2]


def _ecommerce_faq_ir() -> IRDocument:
    doc = json.loads((ROOT / "examples" / "ir" / "01-ecommerce-customer-faq.json").read_text())
    return IRDocument.model_validate(doc)


def _reversed_graph_lists(yaml_text: str) -> str:
    raw = yaml.safe_load(yaml_text)
    raw["workflow"]["graph"]["nodes"] = list(reversed(raw["workflow"]["graph"]["nodes"]))
    raw["workflow"]["graph"]["edges"] = list(reversed(raw["workflow"]["graph"]["edges"]))
    return yaml.safe_dump(raw, sort_keys=False, allow_unicode=True)


def test_whitespace_and_key_order_invariant():
    # Real Dify DSL nests React Flow nodes/edges under workflow.graph, not workflow.
    a = """
    app:
      name: x
      mode: workflow
    workflow:
      graph:
        nodes:
          - id: n1
            type: start
            data: {x: 1}
          - id: n2
            type: end
        edges: []
    """
    b = """
    app:
      mode: workflow
      name: x
    workflow:
      graph:
        edges: []
        nodes:
          - id: n2
            type: end
          - id: n1
            type: start
            data: {x: 1}
    """
    assert canonical_dify_ast_hash(a) == canonical_dify_ast_hash(b)


def test_semantic_change_changes_hash():
    a = "app: {name: x, mode: workflow}\nworkflow: {graph: {nodes: [{id: n1, type: start}], edges: []}}"
    b = "app: {name: x, mode: workflow}\nworkflow: {graph: {nodes: [{id: n1, type: end}], edges: []}}"  # type changed
    assert canonical_dify_ast_hash(a) != canonical_dify_ast_hash(b)


def test_dify_assigned_defaults_stripped():
    """Fields the Dify import path silently injects don't change the hash."""
    plain = "app: {name: x, mode: workflow}\nworkflow: {graph: {nodes: [], edges: []}}"
    with_default = (
        "app: {name: x, mode: workflow, icon: '', description: ''}\n"
        "workflow: {graph: {nodes: [], edges: []}}"
    )
    assert canonical_dify_ast_hash(plain) == canonical_dify_ast_hash(with_default)


def test_real_compiler_output_is_invariant_to_node_and_edge_reorder():
    """Round-trip proof against the actual compiler (not a hand-simplified AST)."""
    yaml_text, _warnings = compile_ir(_ecommerce_faq_ir())
    reordered = _reversed_graph_lists(yaml_text)
    assert yaml_text != reordered  # sanity: the fixture really did move
    assert canonical_dify_ast_hash(yaml_text) == canonical_dify_ast_hash(reordered)


def test_real_compiler_output_changes_hash_on_semantic_edit():
    """A real IR-level edit must still change the hash after canonicalizing."""
    ir = _ecommerce_faq_ir()
    before_yaml, _ = compile_ir(ir)

    doc = json.loads((ROOT / "examples" / "ir" / "01-ecommerce-customer-faq.json").read_text())
    edited = copy.deepcopy(doc)
    retrieve = next(n for n in edited["nodes"] if n["id"] == "retrieve")
    retrieve["dataset"] = "a_completely_different_dataset"
    after_yaml, _ = compile_ir(IRDocument.model_validate(edited))

    assert canonical_dify_ast_hash(before_yaml) != canonical_dify_ast_hash(after_yaml)
