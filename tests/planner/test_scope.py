from loom.planner.scope import render_registry_block
from loom.validator.registry import Registry


def test_scope_filters_to_relevant_only():
    reg = Registry.load("v1")
    block = render_registry_block(reg, scope="clinic/kb")
    assert "clinic_kb" in block
    assert "clinic_system_api" not in block  # scoped to clinic/ops


def test_scope_with_no_matches_renders_empty_sections():
    reg = Registry.load("v1")
    block = render_registry_block(reg, scope="unknown-team/x")
    assert "Tools" in block and "Datasets" in block
    # No bulleted entries.
    assert "- `" not in block.split("### Tools")[1].split("### Datasets")[0]
