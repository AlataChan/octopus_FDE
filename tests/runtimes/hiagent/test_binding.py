from pathlib import Path

import pytest

from loom.runtimes.hiagent.binding import HiagentBinding, HiagentBindingError


def test_load_minimal_binding(tmp_path: Path):
    p = tmp_path / "binding.yaml"
    p.write_text("""
customer: test
target: hiagent
workspace_id: d31pcnoboot936af1tsg
""")
    binding = HiagentBinding.load(p)
    assert binding.workspace_id == "d31pcnoboot936af1tsg"
    assert binding.dataset_id_map == {}
    assert binding.model_id_map == {}
    assert binding.rerank_model_id == ""
    assert binding.tool_id_map == {}


def test_load_full_binding(tmp_path: Path):
    p = tmp_path / "binding.yaml"
    p.write_text("""
customer: test
target: hiagent
target_version: "2.6"
workspace_id: d31pcnoboot936af1tsg
dataset_id_map:
  product_kb: d7jl0000shhcm7cr99hg
model_id_map:
  configured-small-model: d2vqg2mq64gt25bs9bvg
rerank_model_id: d2s17uicrg32144vrj9g
tool_id_map:
  web_search: d7tool00shhcm7cr99hg
""")
    binding = HiagentBinding.load(p)
    assert binding.resolve_dataset("product_kb") == "d7jl0000shhcm7cr99hg"
    assert binding.resolve_model("configured-small-model") == "d2vqg2mq64gt25bs9bvg"
    assert binding.rerank_model_id == "d2s17uicrg32144vrj9g"
    assert binding.resolve_tool("web_search") == "d7tool00shhcm7cr99hg"


def test_workspace_id_required(tmp_path: Path):
    p = tmp_path / "binding.yaml"
    p.write_text("customer: test\ntarget: hiagent\n")
    with pytest.raises(HiagentBindingError):
        HiagentBinding.load(p)


def test_target_must_be_hiagent(tmp_path: Path):
    p = tmp_path / "binding.yaml"
    p.write_text("customer: test\ntarget: dify\nworkspace_id: d31pcnoboot936af1tsg\n")
    with pytest.raises(HiagentBindingError):
        HiagentBinding.load(p)


def test_resolve_unbound_returns_empty():
    binding = HiagentBinding(customer="test", target="hiagent", workspace_id="d31pcnoboot936af1tsg")
    assert binding.resolve_dataset("foo") == ""


def test_resolve_bound_returns_id():
    binding = HiagentBinding(
        customer="test",
        target="hiagent",
        workspace_id="d31pcnoboot936af1tsg",
        dataset_id_map={"product_kb": "d7jl0000shhcm7cr99hg"},
    )
    assert binding.resolve_dataset("product_kb") == "d7jl0000shhcm7cr99hg"


def test_load_missing_file_raises_clear_error(tmp_path: Path):
    with pytest.raises(HiagentBindingError, match="binding file not found"):
        HiagentBinding.load(tmp_path / "missing.yaml")


def test_load_invalid_yaml_raises(tmp_path: Path):
    p = tmp_path / "binding.yaml"
    p.write_text("customer: [unterminated\n")
    with pytest.raises(HiagentBindingError, match="binding YAML parse error"):
        HiagentBinding.load(p)
