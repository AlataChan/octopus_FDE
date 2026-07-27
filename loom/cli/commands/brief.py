"""Headless Self-Design brief clarification probe."""
from __future__ import annotations

import json
import os
import socket
import sys
from pathlib import Path
from typing import Literal, NoReturn, cast

import click
from pydantic import ValidationError

from loom.fde_session.brief import WorkflowBriefDraft
from loom.fde_session.clarify import ClarifyQuestion, missing_fields
from loom.fde_session.redaction import has_potential_secret
from loom.validator.registry import Registry

CLI_SCHEMA_VERSION = "1"
REDACTED_SECRET_INTENT = "[REDACTED:potential_secret]"


@click.command(
    help=(
        "Dry-run Self-Design clarification. Exit 1 means missing blocking fields; "
        "exit 2 means invalid input."
    )
)
@click.argument("intent_file", required=False, type=click.Path(dir_okay=False, path_type=Path))
@click.option("--scope", required=False, help="Registry scope, for example ecommerce/kb or clinic/kb.")
@click.option("--target", help="Target runtime. Missing target is reported.")
@click.option("--draft-json", "draft_json_path", type=click.Path(dir_okay=False, path_type=Path))
@click.option("--json/--text", "json_output", default=True, show_default=True)
@click.option("--stdin", "read_stdin", is_flag=True, help="Read intent text from stdin; mutually exclusive with INTENT_FILE.")
def brief(
    intent_file: Path | None,
    scope: str,
    target: str | None,
    draft_json_path: Path | None,
    json_output: bool,
    read_stdin: bool,
) -> None:
    if intent_file is not None and read_stdin:
        _exit_error("invalid_input", "INTENT_FILE and --stdin are mutually exclusive")
    if intent_file is None and not read_stdin:
        _exit_error("invalid_input", "provide INTENT_FILE or --stdin")
    if scope is None:
        _exit_error("missing_option", "--scope is required")
    if target is not None and target not in {"hiagent", "dify"}:
        _exit_error("invalid_target", "--target must be one of: hiagent, dify")
    if not _scope_exists(scope):
        _exit_error("invalid_scope", f"scope {scope!r} is not present in registry v1")

    if read_stdin:
        intent = click.get_text_stream("stdin").read()
    else:
        assert intent_file is not None
        if not intent_file.is_file():
            _exit_error("input_not_found", str(intent_file))
        intent = intent_file.read_text()
    intent = intent.strip()
    if not intent:
        _exit_error("missing_intent", "intent text is required")
    if has_potential_secret(intent):
        _emit_json(
            {
                "cli_schema_version": CLI_SCHEMA_VERSION,
                "instance_id": _instance_id(),
                "error": "intent_redacted",
                "detail": "potential secret in intent",
                "brief_draft": {
                    "intent": REDACTED_SECRET_INTENT,
                    "scope": scope,
                    "target_runtime": target,
                },
            },
            err=True,
        )
        sys.exit(2)

    draft = _build_draft(
        intent=intent,
        scope=scope,
        target=cast("Literal['hiagent', 'dify'] | None", target),
        draft_json_path=draft_json_path,
    )
    questions = missing_fields(draft)
    missing_block = [_question_json(question) for question in questions if question.severity == "block"]
    missing_warn = [_question_json(question) for question in questions if question.severity == "warn"]
    payload = {
        "cli_schema_version": CLI_SCHEMA_VERSION,
        "instance_id": _instance_id(),
        "brief_draft": draft.model_dump(mode="json", exclude_none=False),
        "missing_block": missing_block,
        "missing_warn": missing_warn,
        "ready": not missing_block,
    }
    if json_output:
        _emit_json(payload)
    else:
        _emit_text(payload)
    if missing_block:
        _emit_json(
            {
                "cli_schema_version": CLI_SCHEMA_VERSION,
                "instance_id": _instance_id(),
                "missing_block": missing_block,
                "ready": False,
            },
            err=True,
        )
        sys.exit(1)


def _build_draft(
    *,
    intent: str,
    scope: str,
    target: Literal["hiagent", "dify"] | None,
    draft_json_path: Path | None,
) -> WorkflowBriefDraft:
    data: dict[str, object] = {}
    if draft_json_path is not None:
        if not draft_json_path.is_file():
            _exit_error("draft_json_not_found", str(draft_json_path))
        try:
            raw = json.loads(draft_json_path.read_text())
        except json.JSONDecodeError as e:
            _exit_error("invalid_draft_json", str(e))
        if not isinstance(raw, dict):
            _exit_error("invalid_draft_json", "draft JSON must be an object")
        data.update(raw)
    data["intent"] = intent
    data.setdefault("title", _title_from_intent(intent))
    data["scope"] = scope
    if target is not None:
        data["target_runtime"] = target
    try:
        return WorkflowBriefDraft.model_validate(data)
    except ValidationError as e:
        _exit_error("invalid_draft_json", e.errors()[0]["msg"])


def _scope_exists(scope: str) -> bool:
    reg = Registry.load("v1")
    return (
        any(scope in entry.scopes for entry in reg.tools.values())
        or any(scope in entry.scopes for entry in reg.datasets.values())
        or any(scope in entry.scopes for entry in reg.credentials.values())
    )


def _title_from_intent(intent: str) -> str:
    return intent[:80] if intent else "Self-Design workflow"


def _question_json(question: ClarifyQuestion) -> dict[str, str]:
    return {
        "field_path": question.field_path,
        "question": question.question,
        "severity": question.severity,
    }


def _emit_json(payload: dict[str, object], *, err: bool = False) -> None:
    click.echo(json.dumps(payload, ensure_ascii=False, indent=2), err=err)


def _emit_text(payload: dict[str, object]) -> None:
    click.echo(f"ready={str(payload['ready']).lower()}")
    for item in cast("list[dict[str, str]]", payload["missing_block"]):
        click.echo(f"block {item['field_path']}: {item['question']}")
    for item in cast("list[dict[str, str]]", payload["missing_warn"]):
        click.echo(f"warn {item['field_path']}: {item['question']}")


def _exit_error(error: str, detail: str) -> NoReturn:
    _emit_json(
        {
            "cli_schema_version": CLI_SCHEMA_VERSION,
            "instance_id": _instance_id(),
            "error": error,
            "detail": detail,
        },
        err=True,
    )
    sys.exit(2)


def _instance_id() -> str:
    return os.environ.get("LOOM_INSTANCE_ID") or socket.gethostname()
