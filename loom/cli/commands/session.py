"""Offline session inspection commands."""
from __future__ import annotations

import json
import os
import sqlite3
import socket
import sys
from pathlib import Path
from typing import NoReturn
from uuid import UUID

import click

from loom.state.models import TurnRow
from loom.state.store import SessionStore

CLI_SCHEMA_VERSION = "1"


@click.group(help="Inspect stored sessions without starting the service.")
def session() -> None:
    pass


@session.command("show-turns", help="List safe turn metadata for a session.")
@click.argument("session_id")
@click.option("--data-dir", type=click.Path(path_type=Path), help="Data directory containing sessions.db.")
@click.option("--actor", required=False, help="Actor id to filter by; no implicit fallback.")
@click.option("--json/--table", "json_output", default=False, show_default=True)
def show_turns(session_id: str, data_dir: Path | None, actor: str | None, json_output: bool) -> None:
    actor = _require_actor(actor)
    db_path, store = _open_store(data_dir)
    _validate_session_id(session_id)
    session_row = store.get_session(session_id, actor_id=actor)
    if session_row is None:
        _exit_session_not_found(db_path, session_id, actor)
    turns = [_turn_summary(turn) for turn in store.list_turns(session_id, actor_id=actor)]
    if json_output:
        _emit_json({
            "cli_schema_version": CLI_SCHEMA_VERSION,
            "instance_id": _instance_id(),
            "session_id": session_id,
            "turns": turns,
        })
    else:
        _emit_table(turns)


@session.command("brief", help="Print the redacted brief draft for a session.")
@click.argument("session_id")
@click.option("--data-dir", type=click.Path(path_type=Path), help="Data directory containing sessions.db.")
@click.option("--actor", required=False, help="Actor id to filter by; no implicit fallback.")
def brief_cmd(session_id: str, data_dir: Path | None, actor: str | None) -> None:
    actor = _require_actor(actor)
    db_path, store = _open_store(data_dir)
    _validate_session_id(session_id)
    row = store.get_session(session_id, actor_id=actor)
    if row is None:
        _exit_session_not_found(db_path, session_id, actor)
    assert row is not None
    if not row.brief_draft:
        _exit_error("empty_brief", f"session {session_id} has no brief_draft", code=1)
    try:
        brief_draft = json.loads(row.brief_draft)
    except json.JSONDecodeError:
        _exit_error("invalid_brief", f"session {session_id} has invalid brief_draft JSON", code=2)
    _emit_json({
        "cli_schema_version": CLI_SCHEMA_VERSION,
        "instance_id": _instance_id(),
        "session_id": session_id,
        "self_design": row.self_design,
        "clarify_round": row.clarify_round,
        "target_runtime": row.target_runtime,
        "scope": row.scope,
        "brief_draft": brief_draft,
    })


def _open_store(data_dir: Path | None) -> tuple[Path, SessionStore]:
    root = data_dir or Path(os.environ.get("LOOM_DATA_DIR", ".loom-data"))
    db_path = root / "sessions.db"
    if not db_path.exists():
        _exit_error("session_not_found", f"sessions DB not found at {db_path}", code=2)
    return db_path, SessionStore.open_readonly(db_path)


def _require_actor(actor: str | None) -> str:
    if actor is None:
        _exit_error("missing_option", "--actor is required", code=2)
    return actor


def _validate_session_id(session_id: str) -> None:
    try:
        UUID(session_id)
    except ValueError:
        _exit_error("invalid_session_id", f"invalid session id: {session_id}", code=2)


def _exit_session_not_found(db_path: Path, session_id: str, actor: str) -> NoReturn:
    if _session_exists_any_actor(db_path, session_id):
        _exit_error("not_found", f"session {session_id} not found for actor {actor}", code=1)
    _exit_error("session_not_found", f"session {session_id} does not exist", code=2)


def _session_exists_any_actor(db_path: Path, session_id: str) -> bool:
    with sqlite3.connect(db_path) as con:
        row = con.execute("SELECT 1 FROM sessions WHERE session_id = ? LIMIT 1", (session_id,)).fetchone()
    return row is not None


def _turn_summary(turn: TurnRow) -> dict[str, str]:
    return {
        "turn_id": str(turn.turn_id),
        "kind": turn.kind,
        "status": turn.status,
        "created_at": turn.created_at.isoformat(),
        "digest": _turn_digest(turn),
    }


def _turn_digest(turn: TurnRow) -> str:
    if turn.kind == "clarify":
        payload = _parse_question(turn.clarify_question)
        field_path = str(payload.get("field_path") or "-")
        severity = str(payload.get("severity") or "-")
        return f"field={field_path} sev={severity}"
    if turn.kind == "questionnaire":
        payload = _parse_question(turn.clarify_question)
        questions = payload.get("questions")
        if isinstance(questions, list):
            return f"missing={len(questions)}"
        return "missing=0"
    if turn.status == "failed":
        return "ir_failed"
    if turn.ir_after:
        return "ir_ok"
    return "ir_pending"


def _parse_question(raw: str | None) -> dict[str, object]:
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _emit_table(rows: list[dict[str, str]]) -> None:
    table = [
        {
            "TURN_ID": row["turn_id"][:8],
            "KIND": row["kind"],
            "STATUS": row["status"],
            "CREATED": row["created_at"][:19].replace("T", " "),
            "DIGEST": row["digest"],
        }
        for row in rows
    ]
    headers = ["TURN_ID", "KIND", "STATUS", "CREATED", "DIGEST"]
    widths = {
        header: max(len(header), *(len(row[header]) for row in table)) if table else len(header)
        for header in headers
    }
    click.echo("  ".join(header.ljust(widths[header]) for header in headers))
    for row in table:
        click.echo("  ".join(row[header].ljust(widths[header]) for header in headers))


def _emit_json(payload: dict[str, object], *, err: bool = False) -> None:
    click.echo(json.dumps(payload, ensure_ascii=False, indent=2), err=err)


def _exit_error(error: str, detail: str, *, code: int) -> NoReturn:
    _emit_json(
        {
            "cli_schema_version": CLI_SCHEMA_VERSION,
            "instance_id": _instance_id(),
            "error": error,
            "detail": detail,
        },
        err=True,
    )
    sys.exit(code)


def _instance_id() -> str:
    return os.environ.get("LOOM_INSTANCE_ID") or socket.gethostname()
