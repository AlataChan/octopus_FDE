"""SQLite repository for sessions, turns, and artifacts."""
from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path  # noqa: TC003
from typing import Callable, Literal
from uuid import UUID, uuid4

from cryptography.fernet import Fernet  # noqa: TC002

from loom.state.models import ActorLLMConfigRow, ArtifactRow, SessionRow, TurnRow
from loom.state.sm import SessionState, transition
from loom.runtimes.warnings import CompileWarning

AuditEventWriter = Callable[[UUID, list[tuple[str, dict[str, object]]]], None]


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

    def create_session_with_actor_defaults(
        self,
        *,
        actor_id: str,
        fernet: Fernet,
        audit_writer: AuditEventWriter | None = None,
    ) -> SessionRow:
        del fernet  # actor defaults are already encrypted with the same service key.
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
            events: list[tuple[str, dict[str, object]]] = [
                ("session.created", {"actor_id": actor_id})
            ]
            defaults = self._get_actor_llm_config_con(con, actor_id=actor_id)
            if defaults is not None:
                state = transition(SessionState.INIT.value, "llm_config_set").value
                con.execute(
                    """
                    UPDATE sessions
                    SET state = ?, llm_api_key_encrypted = ?, llm_base_url = ?,
                        llm_model = ?, llm_key_version = ?, updated_at = ?
                    WHERE session_id = ? AND actor_id = ?
                    """,
                    (
                        state,
                        defaults.llm_api_key_encrypted,
                        defaults.llm_base_url,
                        defaults.llm_model,
                        defaults.llm_key_version,
                        now,
                        str(sid),
                        actor_id,
                    ),
                )
                events.append((
                    "llm_config_inherited",
                    {
                        "source": "actor_default",
                        "provider": defaults.llm_provider,
                        "model": defaults.llm_model,
                    },
                ))
            if audit_writer is not None:
                audit_writer(sid, events)
            row = con.execute(
                "SELECT * FROM sessions WHERE session_id = ? AND actor_id = ?",
                (str(sid), actor_id),
            ).fetchone()
        assert row is not None
        return _session_row(row)

    def get_actor_llm_config(self, *, actor_id: str) -> ActorLLMConfigRow | None:
        with self._connect() as con:
            return self._get_actor_llm_config_con(con, actor_id=actor_id)

    def upsert_actor_llm_config(
        self,
        *,
        actor_id: str,
        provider: str | None,
        base_url: str,
        model: str,
        api_key: str | None,
        fernet: Fernet,
    ) -> ActorLLMConfigRow:
        now = _now()
        with self._connect() as con:
            existing = self._get_actor_llm_config_con(con, actor_id=actor_id)
            has_new_key = bool(api_key)
            if existing is None and not has_new_key:
                raise ValueError("api_key_required_for_initial_setup")
            if existing is None:
                encrypted = fernet.encrypt(str(api_key).encode("utf-8"))
                con.execute(
                    """
                    INSERT INTO actor_llm_config (
                        actor_id, llm_provider, llm_base_url, llm_model,
                        llm_api_key_encrypted, llm_key_version, created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, 1, ?, ?)
                    """,
                    (actor_id, provider, base_url, model, encrypted, now, now),
                )
            elif has_new_key:
                encrypted = fernet.encrypt(str(api_key).encode("utf-8"))
                con.execute(
                    """
                    UPDATE actor_llm_config
                    SET llm_provider = ?, llm_base_url = ?, llm_model = ?,
                        llm_api_key_encrypted = ?, llm_key_version = ?, updated_at = ?
                    WHERE actor_id = ?
                    """,
                    (
                        provider,
                        base_url,
                        model,
                        encrypted,
                        existing.llm_key_version + 1,
                        now,
                        actor_id,
                    ),
                )
            else:
                con.execute(
                    """
                    UPDATE actor_llm_config
                    SET llm_provider = ?, llm_base_url = ?, llm_model = ?, updated_at = ?
                    WHERE actor_id = ?
                    """,
                    (provider, base_url, model, now, actor_id),
                )
            row = self._get_actor_llm_config_con(con, actor_id=actor_id)
        assert row is not None
        return row

    def delete_actor_llm_config(self, *, actor_id: str) -> None:
        with self._connect() as con:
            con.execute("DELETE FROM actor_llm_config WHERE actor_id = ?", (actor_id,))

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

    def update_session_title(
        self,
        session_id: UUID | str,
        *,
        actor_id: str,
        title: str | None,
    ) -> SessionRow:
        self.require_session(session_id, actor_id=actor_id)
        with self._connect() as con:
            con.execute(
                """
                UPDATE sessions
                SET title = ?, updated_at = ?
                WHERE session_id = ? AND actor_id = ?
                """,
                (title, _now(), str(session_id), actor_id),
            )
        row = self.get_session(session_id, actor_id=actor_id)
        assert row is not None
        return row

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
        # 模板初始化的 session 直接落到 validated（无 LLM key），此时配置/更新
        # LLM key 不应再触发 INIT → LLM_CONFIG_SET 跃迁。其他非 INIT 状态（已生成
        # IR 后回头换 key）同理保持 state 不变。
        state = (
            transition(session.state, "llm_config_set").value
            if session.state == "init"
            else session.state
        )
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

    def update_session_planning_context(
        self,
        session_id: UUID | str,
        *,
        actor_id: str,
        target_runtime: Literal["hiagent", "dify"] | None,
        scope: str | None,
    ) -> SessionRow:
        self.require_session(session_id, actor_id=actor_id)
        with self._connect() as con:
            con.execute(
                """
                UPDATE sessions
                SET target_runtime = ?, scope = ?, updated_at = ?
                WHERE session_id = ? AND actor_id = ?
                """,
                (target_runtime, scope, _now(), str(session_id), actor_id),
            )
        row = self.get_session(session_id, actor_id=actor_id)
        assert row is not None
        return row

    def create_turn(
        self,
        session_id: UUID | str,
        *,
        actor_id: str,
        user_message: str,
        ir_before: str | None,
    ) -> TurnRow:
        self.require_session(session_id, actor_id=actor_id)
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
        self.require_turn(turn_id, actor_id=actor_id)
        with self._connect() as con:
            con.execute(
                """
                UPDATE turns
                SET status = 'failed', planner_reply = ?, validation_errors = ?
                WHERE turn_id = ? AND actor_id = ?
                """,
                (error_kind, json.dumps(validation_errors), str(turn_id), actor_id),
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
        compile_warnings: list[CompileWarning] | None = None,
    ) -> ArtifactRow:
        artifact_id = uuid4()
        now = _now()
        with self._connect() as con:
            con.execute(
                """
                INSERT INTO artifacts (
                    artifact_id, session_id, workflow_id, actor_id, artifact_name,
                    artifact_kind, artifact_path, artifact_size, sha256, target,
                    mode, binding_handle, compile_warnings_json, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    json.dumps([asdict(w) for w in compile_warnings or []], ensure_ascii=False),
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
                    title TEXT,
                    llm_api_key_encrypted BLOB,
                    llm_base_url TEXT,
                    llm_model TEXT,
                    llm_key_version INTEGER,
                    target_runtime TEXT,
                    scope TEXT,
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
                    compile_warnings_json TEXT NOT NULL DEFAULT '[]',
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS actor_llm_config (
                    actor_id TEXT PRIMARY KEY,
                    llm_provider TEXT,
                    llm_base_url TEXT NOT NULL,
                    llm_model TEXT NOT NULL,
                    llm_api_key_encrypted BLOB NOT NULL,
                    llm_key_version INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                """
            )
            columns = {row["name"] for row in con.execute("PRAGMA table_info(artifacts)").fetchall()}
            if "compile_warnings_json" not in columns:
                con.execute("ALTER TABLE artifacts ADD COLUMN compile_warnings_json TEXT NOT NULL DEFAULT '[]'")
            session_columns = {row["name"] for row in con.execute("PRAGMA table_info(sessions)").fetchall()}
            if "title" not in session_columns:
                con.execute("ALTER TABLE sessions ADD COLUMN title TEXT")
            if "target_runtime" not in session_columns:
                con.execute("ALTER TABLE sessions ADD COLUMN target_runtime TEXT")
            if "scope" not in session_columns:
                con.execute("ALTER TABLE sessions ADD COLUMN scope TEXT")

    @staticmethod
    def _get_actor_llm_config_con(
        con: sqlite3.Connection,
        *,
        actor_id: str,
    ) -> ActorLLMConfigRow | None:
        row = con.execute(
            "SELECT * FROM actor_llm_config WHERE actor_id = ?",
            (actor_id,),
        ).fetchone()
        return _actor_llm_config_row(row) if row else None


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _session_row(row: sqlite3.Row) -> SessionRow:
    return SessionRow(
        session_id=UUID(row["session_id"]),
        actor_id=row["actor_id"],
        state=row["state"],
        latest_ir_json=row["latest_ir_json"],
        latest_ir_sha256=row["latest_ir_sha256"],
        title=row["title"] if "title" in row.keys() else None,
        llm_api_key_encrypted=row["llm_api_key_encrypted"],
        llm_base_url=row["llm_base_url"],
        llm_model=row["llm_model"],
        llm_key_version=row["llm_key_version"],
        target_runtime=row["target_runtime"] if "target_runtime" in row.keys() else None,
        scope=row["scope"] if "scope" in row.keys() else None,
        created_at=datetime.fromisoformat(row["created_at"]),
        updated_at=datetime.fromisoformat(row["updated_at"]),
    )


def _actor_llm_config_row(row: sqlite3.Row) -> ActorLLMConfigRow:
    return ActorLLMConfigRow(
        actor_id=row["actor_id"],
        llm_provider=row["llm_provider"],
        llm_base_url=row["llm_base_url"],
        llm_model=row["llm_model"],
        llm_api_key_encrypted=row["llm_api_key_encrypted"],
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
    warnings_raw = row["compile_warnings_json"] if "compile_warnings_json" in row.keys() else "[]"
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
        compile_warnings=[
            CompileWarning(**item)
            for item in json.loads(warnings_raw or "[]")
        ],
        created_at=datetime.fromisoformat(row["created_at"]),
    )
