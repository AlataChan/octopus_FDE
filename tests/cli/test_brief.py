import json

from click.testing import CliRunner

from loom.cli.main import cli


def _json_from_output(output: str) -> dict:
    return json.loads(output)


def test_brief_missing_block_outputs_schema_and_returns_normal_branch() -> None:
    runner = CliRunner()

    result = runner.invoke(
        cli,
        ["brief", "--stdin", "--scope", "ecommerce/kb"],
        input="做一个客服 FAQ",
    )

    assert result.exit_code == 1
    payload = _json_from_output(result.stdout)
    assert payload["cli_schema_version"] == "1"
    assert payload["ready"] is False
    missing = {item["field_path"] for item in payload["missing_block"]}
    assert {"target_runtime", "trigger", "compliance_boundary"} <= missing
    stderr_payload = _json_from_output(result.stderr)
    assert stderr_payload["cli_schema_version"] == "1"
    assert len(stderr_payload["missing_block"]) >= 3


def test_brief_target_option_parses_but_still_reports_other_missing_fields() -> None:
    runner = CliRunner()

    result = runner.invoke(
        cli,
        ["brief", "--stdin", "--scope", "ecommerce/kb", "--target", "hiagent"],
        input="Build an ecommerce FAQ workflow with citation-backed answers.",
    )

    assert result.exit_code == 1
    payload = _json_from_output(result.stdout)
    assert payload["brief_draft"]["target_runtime"] == "hiagent"
    missing = {item["field_path"] for item in payload["missing_block"]}
    assert "target_runtime" not in missing
    assert {"trigger", "compliance_boundary"} <= missing


def test_brief_draft_json_can_reach_ready_path(tmp_path) -> None:
    draft = tmp_path / "draft.json"
    draft.write_text(json.dumps({
        "trigger": {"mode": "manual"},
        "compliance_boundary": {
            "pii_class_default": "low",
            "regulatory_tags": [],
            "geographies": [],
        },
        "success_criteria": "ok",
    }))
    runner = CliRunner()

    result = runner.invoke(
        cli,
        [
            "brief",
            "--stdin",
            "--scope",
            "ecommerce/kb",
            "--target",
            "hiagent",
            "--draft-json",
            str(draft),
        ],
        input="做客服",
    )

    assert result.exit_code == 0, result.output
    payload = _json_from_output(result.stdout)
    assert payload["cli_schema_version"] == "1"
    assert payload["ready"] is True
    assert payload["missing_block"] == []


def test_brief_secret_intent_returns_redacted_error_json() -> None:
    runner = CliRunner()

    result = runner.invoke(
        cli,
        ["brief", "--stdin", "--scope", "ecommerce/kb"],
        input="Authorization: Bearer abc1234567890abcdef",
    )

    assert result.exit_code == 2
    payload = _json_from_output(result.stderr)
    assert payload["cli_schema_version"] == "1"
    assert payload["error"] == "intent_redacted"
    assert payload["brief_draft"]["intent"] == "[REDACTED:potential_secret]"
    assert "abc1234567890abcdef" not in result.output


def test_brief_rejects_unknown_scope() -> None:
    runner = CliRunner()

    result = runner.invoke(
        cli,
        ["brief", "--stdin", "--scope", "unknown/scope"],
        input="做一个客服 FAQ",
    )

    assert result.exit_code == 2
    payload = _json_from_output(result.stderr)
    assert payload["cli_schema_version"] == "1"
    assert payload["error"] == "invalid_scope"
