import json

from click.testing import CliRunner

from loom.cli.main import cli
from loom.fde_session.brief import ComplianceBoundary, TriggerSpec, WorkflowBriefDraft
from loom.fde_session.clarify_engine import ClarifyQuestion
from loom.state.store import SessionStore


def _json_from_output(output: str) -> dict:
    return json.loads(output)


def _store(tmp_path) -> SessionStore:
    return SessionStore(tmp_path / "data" / "sessions.db")


def _data_dir_arg(tmp_path) -> list[str]:
    return ["--data-dir", str(tmp_path / "data")]


def test_session_show_turns_json_uses_safe_field_subset(tmp_path) -> None:
    store = _store(tmp_path)
    session = store.create_session(actor_id="test", self_design=True)
    question = ClarifyQuestion(
        text="Which target runtime should this workflow compile to?",
        field_path="target_runtime",
        allow_freeform=False,
        severity="block",
    )
    turn = store.create_turn(
        session.session_id,
        actor_id="test",
        user_message="raw user message must not leak",
        ir_before='{"secret":"before"}',
        kind="clarify",
        brief_before='{"secret":"brief_before"}',
    )
    store.finish_turn_clarify(
        turn.turn_id,
        actor_id="test",
        kind="clarify",
        planner_reply="planner reply must not leak",
        clarify_question=question.model_dump_json(),
        brief_before='{"secret":"brief_before"}',
        brief_after='{"secret":"brief_after"}',
        clarify_round=1,
        target_runtime="hiagent",
        scope="ecommerce/kb",
    )
    runner = CliRunner()

    result = runner.invoke(
        cli,
        ["session", "show-turns", str(session.session_id), "--actor", "test", "--json", *_data_dir_arg(tmp_path)],
    )

    assert result.exit_code == 0, result.output
    payload = _json_from_output(result.stdout)
    assert payload["cli_schema_version"] == "1"
    assert payload["instance_id"]
    assert payload["session_id"] == str(session.session_id)
    assert payload["turns"] == [{
        "turn_id": str(turn.turn_id),
        "kind": "clarify",
        "status": "succeeded",
        "created_at": payload["turns"][0]["created_at"],
        "digest": "field=target_runtime sev=block",
    }]
    forbidden = {
        "user_message",
        "brief_before",
        "brief_after",
        "validation_errors",
        "planner_reply",
        "ir_after",
        "ir_before",
    }
    assert forbidden.isdisjoint(payload["turns"][0])
    text = result.output
    assert "raw user message" not in text
    assert "planner reply" not in text
    assert "brief_before" not in text


def test_session_show_turns_table_renders_digest(tmp_path) -> None:
    store = _store(tmp_path)
    session = store.create_session(actor_id="test", self_design=True)
    turn = store.create_turn(session.session_id, actor_id="test", user_message="build", ir_before=None)
    store.finish_turn_succeeded(
        turn.turn_id,
        actor_id="test",
        planner_reply="IR generated",
        ir_after='{"ir_version":"0.4"}',
    )
    runner = CliRunner()

    result = runner.invoke(
        cli,
        ["session", "show-turns", str(session.session_id), "--actor", "test", *_data_dir_arg(tmp_path)],
    )

    assert result.exit_code == 0, result.output
    assert "TURN_ID" in result.output
    assert "ir_ok" in result.output


def test_session_show_turns_does_not_modify_db_file(tmp_path) -> None:
    store = _store(tmp_path)
    session = store.create_session(actor_id="test", self_design=True)
    before = (tmp_path / "data" / "sessions.db").read_bytes()
    runner = CliRunner()

    result = runner.invoke(
        cli,
        ["session", "show-turns", str(session.session_id), "--actor", "test", "--json", *_data_dir_arg(tmp_path)],
    )

    assert result.exit_code == 0, result.output
    assert (tmp_path / "data" / "sessions.db").read_bytes() == before


def test_session_brief_outputs_redacted_snapshot(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("LOOM_INSTANCE_ID", "cli-session-test")
    store = _store(tmp_path)
    session = store.create_session(actor_id="test", self_design=True)
    draft = WorkflowBriefDraft(
        title="FAQ",
        intent="Answer FAQ",
        trigger=TriggerSpec(mode="manual"),
        compliance_boundary=ComplianceBoundary(
            pii_class_default="low",
            regulatory_tags=[],
            geographies=[],
        ),
        success_criteria="ok",
        target_runtime="hiagent",
        scope="ecommerce/kb",
    )
    store.update_session_brief_state(
        session.session_id,
        actor_id="test",
        brief_draft=draft.model_dump_json(exclude_none=True),
        clarify_round=2,
        target_runtime="hiagent",
        scope="ecommerce/kb",
    )
    runner = CliRunner()

    result = runner.invoke(
        cli,
        ["session", "brief", str(session.session_id), "--actor", "test", *_data_dir_arg(tmp_path)],
    )

    assert result.exit_code == 0, result.output
    payload = _json_from_output(result.stdout)
    assert payload["cli_schema_version"] == "1"
    assert payload["instance_id"] == "cli-session-test"
    assert payload["instance_id"]
    assert payload["session_id"] == str(session.session_id)
    assert payload["self_design"] is True
    assert payload["clarify_round"] == 2
    assert payload["target_runtime"] == "hiagent"
    assert payload["scope"] == "ecommerce/kb"
    assert payload["brief_draft"]["intent"] == "Answer FAQ"


def test_session_brief_empty_returns_schema_error(tmp_path) -> None:
    store = _store(tmp_path)
    session = store.create_session(actor_id="test", self_design=True)
    runner = CliRunner()

    result = runner.invoke(
        cli,
        ["session", "brief", str(session.session_id), "--actor", "test", *_data_dir_arg(tmp_path)],
    )

    assert result.exit_code == 1
    payload = _json_from_output(result.stderr)
    assert payload["cli_schema_version"] == "1"
    assert payload["error"] == "empty_brief"


def test_session_commands_enforce_actor_isolation(tmp_path) -> None:
    store = _store(tmp_path)
    session = store.create_session(actor_id="right", self_design=True)
    runner = CliRunner()

    show = runner.invoke(
        cli,
        ["session", "show-turns", str(session.session_id), "--actor", "wrong", "--json", *_data_dir_arg(tmp_path)],
    )
    brief = runner.invoke(
        cli,
        ["session", "brief", str(session.session_id), "--actor", "wrong", *_data_dir_arg(tmp_path)],
    )

    assert show.exit_code == 1
    assert _json_from_output(show.stderr)["error"] == "not_found"
    assert brief.exit_code == 1
    assert _json_from_output(brief.stderr)["error"] == "not_found"


def test_session_nonexistent_id_returns_invalid_input_exit(tmp_path) -> None:
    _store(tmp_path)
    runner = CliRunner()

    result = runner.invoke(
        cli,
        ["session", "show-turns", "00000000-0000-0000-0000-000000000000", "--actor", "test", "--json", *_data_dir_arg(tmp_path)],
    )

    assert result.exit_code == 2
    payload = _json_from_output(result.stderr)
    assert payload["cli_schema_version"] == "1"
    assert payload["error"] == "session_not_found"


def test_session_show_turns_missing_actor_returns_json_error(tmp_path) -> None:
    store = _store(tmp_path)
    session = store.create_session(actor_id="test", self_design=True)
    runner = CliRunner()

    result = runner.invoke(
        cli,
        ["session", "show-turns", str(session.session_id), "--json", *_data_dir_arg(tmp_path)],
    )

    assert result.exit_code == 2
    payload = _json_from_output(result.stderr)
    assert payload["cli_schema_version"] == "1"
    assert payload["error"] == "missing_option"
