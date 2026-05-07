from loom.runtimes.dify.v1_14.ast import canonical_dify_ast_hash


def test_whitespace_and_key_order_invariant():
    a = """
    app:
      name: x
      mode: workflow
    workflow:
      nodes:
        - id: n1
          type: start
          data: {x: 1}
        - id: n2
          type: end
    """
    b = """
    app:
      mode: workflow
      name: x
    workflow:
      nodes:
        - id: n2
          type: end
        - id: n1
          type: start
          data: {x: 1}
    """
    assert canonical_dify_ast_hash(a) == canonical_dify_ast_hash(b)


def test_semantic_change_changes_hash():
    a = "app: {name: x, mode: workflow}\nworkflow: {nodes: [{id: n1, type: start}]}"
    b = "app: {name: x, mode: workflow}\nworkflow: {nodes: [{id: n1, type: end}]}"  # type changed
    assert canonical_dify_ast_hash(a) != canonical_dify_ast_hash(b)


def test_dify_assigned_defaults_stripped():
    """Fields the Dify import path silently injects don't change the hash."""
    plain = "app: {name: x, mode: workflow}\nworkflow: {nodes: []}"
    with_default = (
        "app: {name: x, mode: workflow, icon: '', description: ''}\n"
        "workflow: {nodes: [], graph: {nodes: [], edges: []}}"
    )
    assert canonical_dify_ast_hash(plain) == canonical_dify_ast_hash(with_default)
