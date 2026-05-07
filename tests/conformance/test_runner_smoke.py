from loom.conformance.matrix import MATRIX
from loom.conformance.runner import ConformanceCase


def test_matrix_covers_all_prd_cells():
    expected = {
        "loop_max_iterations",
        "parallel_concat",
        "parallel_object_merge",
        "parallel_first_success",
        "agent_budget_fallback",
        "agent_output_schema",
        "http_retry_on",
        "node_timeout",
        "http_idempotency",
        "condition_truthiness",
    }
    actual = {row.id for row in MATRIX}
    assert actual == expected


def test_every_row_has_runnable_case():
    for row in MATRIX:
        case = row.case_factory()
        assert isinstance(case, ConformanceCase)
        assert case.ir.metadata.name == row.id  # convention: name == row id
