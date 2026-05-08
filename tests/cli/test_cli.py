import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from loom.cli.main import cli

ROOT = Path(__file__).resolve().parents[2]


def test_validate_passes_for_clean_archetype():
    src = ROOT / "examples" / "ir" / "01-ecommerce-customer-faq.json"
    runner = CliRunner()
    result = runner.invoke(cli, ["validate", str(src), "--scope", "ecommerce/kb"])
    assert result.exit_code == 0, result.output


def test_validate_fails_on_missing_rationale(tmp_path):
    src = json.loads((ROOT / "examples" / "ir" / "01-ecommerce-customer-faq.json").read_text())
    del src["nodes"][1]["rationale"]
    p = tmp_path / "bad.json"
    p.write_text(json.dumps(src))
    runner = CliRunner()
    result = runner.invoke(cli, ["validate", str(p), "--scope", "ecommerce/kb"])
    assert result.exit_code != 0
    assert "schema" in result.output


@pytest.mark.skip(reason="ADR 0024 Hiagent compile now requires --binding; Sub-task C rewires CLI")
def test_compile_to_hiagent_writes_json(tmp_path):
    src = ROOT / "examples" / "ir" / "01-ecommerce-customer-faq.json"
    out = tmp_path / "out.hiagent.json"
    runner = CliRunner()
    result = runner.invoke(cli, ["compile", str(src), "--target", "hiagent", "--out", str(out)])
    assert result.exit_code == 0, result.output
    assert out.exists()
    text = out.read_text()
    # Hiagent emits JSON; "app" key must be present
    assert '"app"' in text


def test_compile_to_dify_writes_yaml(tmp_path):
    src = ROOT / "examples" / "ir" / "01-ecommerce-customer-faq.json"
    out = tmp_path / "out.dify.yaml"
    runner = CliRunner()
    result = runner.invoke(cli, ["compile", str(src), "--target", "dify", "--out", str(out)])
    assert result.exit_code == 0, result.output
    assert out.exists()
    text = out.read_text()
    # Dify emits YAML; top-level "app:" key
    assert "app:" in text


def test_plan_with_mocked_planner_writes_ir(tmp_path):
    """Plan command path: read IntentRequest JSON, invoke planner, write IR JSON.

    Mocks loom.planner.retry.plan so no LLM call happens.
    """
    intent_file = tmp_path / "intent.json"
    intent_file.write_text(json.dumps({
        "intent": "Build an ecommerce customer-FAQ workflow.",
        "scope": "ecommerce/kb",
        "target": "hiagent",
        "max_retries": 3,
    }))
    out_file = tmp_path / "plan-out.json"

    # Build a fake successful PlannerResult by mocking the plan function
    from loom.ir.models import IRDocument
    fake_ir = IRDocument.model_validate(json.loads(
        (ROOT / "examples" / "ir" / "01-ecommerce-customer-faq.json").read_text()))
    fake_result = MagicMock(
        ok=True, attempts=1, ir=fake_ir, cost_usd=0.05, latency_s=0.5,
        failures=[],
    )
    with patch("loom.cli.commands.plan.plan_intent", return_value=fake_result):
        runner = CliRunner()
        result = runner.invoke(cli, ["plan", str(intent_file), "--out", str(out_file)])
    assert result.exit_code == 0, result.output
    assert out_file.exists()
    written = json.loads(out_file.read_text())
    assert written["ir_version"] == "0.3"
