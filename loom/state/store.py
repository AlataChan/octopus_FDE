"""SQLite repository for sessions, turns, and artifacts."""
from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path  # noqa: TC003
from typing import Literal
from uuid import UUID, uuid4

from cryptography.fernet import Fernet  # noqa: TC002

from loom.state.models import ArtifactRow, SessionRow, TurnRow
from loom.state.sm import SessionState, transition


class SessionStore:
    """Small sqlite3 store with WAL and UUID-addressed artifacts."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init()

    def pragma(self, name: str) -> str:
        with self._connect() as con:
            row = con.execute(f"PRAGMA {name}").fetchone()
        return str(row[0])

    def create_session(self, *, actor_id: str) -> SessionRow:
        now = _now()
        sid = uuid4()
        with self._connect() as con:
            con.execute(
                """
                INSERT INTO sessions (session_id, actor_id, state, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (str(sid), actor_id, SessionState.INIT.value, now, now),
            )
        row = self.get_session(sid, actor_id=actor_id)
        assert row is not None
        return row

    def list_sessions(self, *, actor_id: str) -> list[SessionRow]:
        with self._connect() as con:
            rows = con.execute(
                "SELECT * FROM sessions WHERE actor_id = ? ORDER BY created_at DESC",
                (actor_id,),
            ).fetchall()
        return [_session_row(row) for row in rows]

    def get_session(self, session_id: UUID | str, *, actor_id: str) -> SessionRow | None:
        with self._connect() as con:
            row = con.execute(
                "SELECT * FROM sessions WHERE session_id = ? AND actor_id = ?",
                (str(session_id), actor_id),
            ).fetchone()
        return _session_row(row) if row else None

    def set_llm_config(
        self,
        session_id: UUID | str,
        *,
        actor_id: str,
        api_key: str,
        base_url: str,
        model: str,
        fernet: Fernet,
    ) -> None:
        session = self.require_session(session_id, actor_id=actor_id)
        encrypted = fernet.encrypt(api_key.encode("utf-8"))
        state = transition(session.state, "llm_config_set").value
        with self._connect() as con:
            con.execute(
                """
                UPDATE sessions
                SET state = ?, llm_api_key_encrypted = ?, llm_base_url = ?,
                    llm_model = ?, llm_key_version = 1, updated_at = ?
                WHERE session_id = ? AND actor_id = ?
                """,
                (state, encrypted, base_url, model, _now(), str(session_id), actor_id),
            )

    def update_latest_ir(self, session_id: UUID | str, *, actor_id: str, ir_json: str) -> None:
        digest = hashlib.sha256(ir_json.encode("utf-8")).hexdigest()
        with self._connect() as con:
            con.execute(
                """
                UPDATE sessions
                SET latest_ir_json = ?, latest_ir_sha256 = ?, updated_at = ?
                WHERE session_id = ? AND actor_id = ?
                """,
                (ir_json, digest, _now(), str(session_id), actor_id),
            )

    def create_turn(
        self,
        session_id: UUID | str,
        *,
        actor_id: str,
        user_message: str,
        ir_before: str | None,
    ) -> TurnRow:
        session = self.require_session(session_id, actor_id=actor_id)
        new_state = transition(session.state, "turn_started").value
        turn_id = uuid4()
        now = _now()
        with self._connect() as con:
            con.execute(
                """
                INSERT INTO turns (
                    turn_id, session_id, actor_id, user_message, ir_before,
                    validation_errors, status, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, 'running', ?)
                """,
                (str(turn_id), str(session_id), actor_id, user_message, ir_before, "[]", now),
            )
            con.execute(
                "UPDATE sessions SET state = ?, updated_at = ? WHERE session_id = ? AND actor_id = ?",
                (new_state, now, str(session_id), actor_id),
            )
        row = self.get_turn(turn_id, actor_id=actor_id)
        assert row is not None
        return row

    def finish_turn_succeeded(
        self,
        turn_id: UUID | str,
        *,
        actor_id: str,
        planner_reply: str,
        ir_after: str,
    ) -> TurnRow:
        turn = self.require_turn(turn_id, actor_id=actor_id)
        digest = hashlib.sha256(ir_after.encode("utf-8")).hexdigest()
        now = _now()
        with self._connect() as con:
            con.execute(
                """
                UPDATE turns
                SET status = 'succeeded', planner_reply = ?, ir_after = ?, validation_errors = '[]'
                WHERE turn_id = ? AND actor_id = ?
                """,
                (planner_reply, ir_after, str(turn_id), actor_id),
            )
            con.execute(
                """
                UPDATE sessions
                SET state = ?, latest_ir_json = ?, latest_ir_sha256 = ?, updated_at = ?
                WHERE session_id = ? AND actor_id = ?
                """,
                (SessionState.VALIDATED.value, ir_after, digest, now, str(turn.session_id), actor_id),
            )
        row = self.get_turn(turn_id, actor_id=actor_id)
        assert row is not None
        return row

    def finish_turn_failed(
        self,
        turn_id: UUID | str,
        *,
        actor_id: str,
        error_kind: str,
        validation_errors: list[str],
    ) -> TurnRow:
        turn = self.require_turn(turn_id, actor_id=actor_id)
        now = _now()
        with self._connect() as con:
            con.execute(
                """
                UPDATE turns
                SET status = 'failed', planner_reply = ?, validation_errors = ?
                WHERE turn_id = ? AND actor_id = ?
                """,
                (error_kind, json.dumps(validation_errors), str(turn_id), actor_id),
            )
            con.execute(
                """
                UPDATE sessions
                SET state = ?, updated_at = ?
                WHERE session_id = ? AND actor_id = ?
                """,
                (SessionState.LLM_CONFIG_SET.value, now, str(turn.session_id), actor_id),
            )
        row = self.get_turn(turn_id, actor_id=actor_id)
        assert row is not None
        return row

    def list_turns(self, session_id: UUID | str, *, actor_id: str) -> list[TurnRow]:
        with self._connect() as con:
            rows = con.execute(
                "SELECT * FROM turns WHERE session_id = ? AND actor_id = ? ORDER BY created_at",
                (str(session_id), actor_id),
            ).fetchall()
        return [_turn_row(row) for row in rows]

    def get_turn(self, turn_id: UUID | str, *, actor_id: str) -> TurnRow | None:
        with self._connect() as con:
            row = con.execute(
                "SELECT * FROM turns WHERE turn_id = ? AND actor_id = ?",
                (str(turn_id), actor_id),
            ).fetchone()
        return _turn_row(row) if row else None

    def create_artifact(
        self,
        session_id: UUID | str,
        *,
        actor_id: str,
        workflow_id: UUID,
        artifact_name: str,
        artifact_kind: Literal["zip", "yaml"],
        artifact_path: str,
        artifact_size: int,
        sha256: str,
        target: Literal["hiagent", "dify"],
        mode: str | None,
        binding_handle: str,
    ) -> ArtifactRow:
        artifact_id = uuid4()
        now = _now()
        with self._connect() as con:
            con.execute(
                """
                INSERT INTO artifacts (
                    artifact_id, session_id, workflow_id, actor_id, artifact_name,
                    artifact_kind, artifact_path, artifact_size, sha256, target,
                    mode, binding_handle, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(artifact_id),
                    str(session_id),
                    str(workflow_id),
                    actor_id,
                    artifact_name,
                    artifact_kind,
                    artifact_path,
                    artifact_size,
                    sha256,
                    target,
                    mode,
                    binding_handle,
                    now,
                ),
            )
            con.execute(
                "UPDATE sessions SET state = ?, updated_at = ? WHERE session_id = ? AND actor_id = ?",
                (SessionState.COMPILED.value, now, str(session_id), actor_id),
            )
        row = self.get_artifact(session_id, artifact_id, actor_id=actor_id)
        assert row is not None
        return row

    def list_artifacts(self, session_id: UUID | str, *, actor_id: str) -> list[ArtifactRow]:
        with self._connect() as con:
            rows = con.execute(
                "SELECT * FROM artifacts WHERE session_id = ? AND actor_id = ? ORDER BY created_at DESC",
                (str(session_id), actor_id),
            ).fetchall()
        return [_artifact_row(row) for row in rows]

    def get_artifact(
        self,
        session_id: UUID | str,
        artifact_id: UUID | str,
        *,
        actor_id: str,
    ) -> ArtifactRow | None:
        with self._connect() as con:
            row = con.execute(
                """
                SELECT * FROM artifacts
                WHERE session_id = ? AND artifact_id = ? AND actor_id = ?
                """,
                (str(session_id), str(artifact_id), actor_id),
            ).fetchone()
        return _artifact_row(row) if row else None

    def mark_downloaded(self, session_id: UUID | str, *, actor_id: str) -> None:
        with self._connect() as con:
            con.execute(
                "UPDATE sessions SET state = ?, updated_at = ? WHERE session_id = ? AND actor_id = ?",
                (SessionState.DOWNLOADED.value, _now(), str(session_id), actor_id),
            )

    def require_session(self, session_id: UUID | str, *, actor_id: str) -> SessionRow:
        row = self.get_session(session_id, actor_id=actor_id)
        if row is None:
            raise KeyError(f"session not found: {session_id}")
        return row

    def require_turn(self, turn_id: UUID | str, *, actor_id: str) -> TurnRow:
        row = self.get_turn(turn_id, actor_id=actor_id)
        if row is None:
            raise KeyError(f"turn not found: {turn_id}")
        return row

    def _connect(self) -> sqlite3.Connection:
        con = sqlite3.connect(self.db_path)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA journal_mode=WAL")
        con.execute("PRAGMA busy_timeout=5000")
        return con

    def _init(self) -> None:
        with self._connect() as con:
            con.executescript(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    actor_id TEXT NOT NULL,
                    state TEXT NOT NULL,
                    latest_ir_json TEXT,
                    latest_ir_sha256 TEXT,
                    llm_api_key_encrypted BLOB,
                    llm_base_url TEXT,
                    llm_model TEXT,
                    llm_key_version INTEGER,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS turns (
                    turn_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    actor_id TEXT NOT NULL,
                    user_message TEXT NOT NULL,
                    planner_reply TEXT,
                    ir_before TEXT,
                    ir_after TEXT,
                    validation_errors TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS artifacts (
                    artifact_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    workflow_id TEXT NOT NULL,
                    actor_id TEXT NOT NULL,
                    artifact_name TEXT NOT NULL,
                    artifact_kind TEXT NOT NULL,
                    artifact_path TEXT NOT NULL,
                    artifact_size INTEGER NOT NULL,
                    sha256 TEXT NOT NULL,
                    target TEXT NOT NULL,
                    mode TEXT,
                    binding_handle TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                """
            )


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _session_row(row: sqlite3.Row) -> SessionRow:
    return SessionRow(
        session_id=UUID(row["session_id"]),
        actor_id=row["actor_id"],
        state=row["state"],
        latest_ir_json=row["latest_ir_json"],
        latest_ir_sha256=row["latest_ir_sha256"],
        llm_api_key_encrypted=row["llm_api_key_encrypted"],
        llm_base_url=row["llm_base_url"],
        llm_model=row["llm_model"],
        llm_key_version=row["llm_key_version"],
        created_at=datetime.fromisoformat(row["created_at"]),
        updated_at=datetime.fromisoformat(row["updated_at"]),
    )


def _turn_row(row: sqlite3.Row) -> TurnRow:
    return TurnRow(
        turn_id=UUID(row["turn_id"]),
        session_id=UUID(row["session_id"]),
        actor_id=row["actor_id"],
        user_message=row["user_message"],
        planner_reply=row["planner_reply"],
        ir_before=row["ir_before"],
        ir_after=row["ir_after"],
        validation_errors=json.loads(row["validation_errors"]),
        status=row["status"],
        created_at=datetime.fromisoformat(row["created_at"]),
    )


def _artifact_row(row: sqlite3.Row) -> ArtifactRow:
    return ArtifactRow(
        artifact_id=UUID(row["artifact_id"]),
        session_id=UUID(row["session_id"]),
        workflow_id=UUID(row["workflow_id"]),
        actor_id=row["actor_id"],
        artifact_name=row["artifact_name"],
        artifact_kind=row["artifact_kind"],
        artifact_path=row["artifact_path"],
        artifact_size=row["artifact_size"],
        sha256=row["sha256"],
        target=row["target"],
        mode=row["mode"],
        binding_handle=row["binding_handle"],
        created_at=datetime.fromisoformat(row["created_at"]),
    )
