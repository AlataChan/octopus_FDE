"""Standalone SQLite store for workflow registry rows.

No SQL joins with the sessions DB are allowed; session_id and artifact_id are
opaque links composed by service code.
"""
from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path  # noqa: TC003
from typing import Any
from uuid import UUID

from loom.registry.models import WorkflowRecord


class WorkflowRegistryStore:
    """SQLite repository for portable workflow baselines."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init()

    def create(self, record: WorkflowRecord) -> WorkflowRecord:
        data = _record_to_row(record)
        cols = ", ".join(data)
        placeholders = ", ".join("?" for _ in data)
        with self._connect() as con:
            con.execute(
                f"INSERT INTO workflow_records ({cols}) VALUES ({placeholders})",
                tuple(data.values()),
            )
        return record

    def list(
        self,
        *,
        actor_id: str,
        target: str | None = None,
        binding_handle: str | None = None,
    ) -> list[WorkflowRecord]:
        query = "SELECT * FROM workflow_records"
        filters: list[str] = ["created_by_actor = ?"]
        args: list[str] = [actor_id]
        if target:
            filters.append("target = ?")
            args.append(target)
        if binding_handle:
            filters.append("binding_handle = ?")
            args.append(binding_handle)
        query += " WHERE " + " AND ".join(filters)
        query += " ORDER BY compiled_at DESC"
        with self._connect() as con:
            rows = con.execute(query, args).fetchall()
        return [_row_to_record(row) for row in rows]

    def get(self, workflow_id: UUID | str, *, actor_id: str) -> WorkflowRecord | None:
        with self._connect() as con:
            row = con.execute(
                "SELECT * FROM workflow_records WHERE workflow_id = ? AND created_by_actor = ?",
                (str(workflow_id), actor_id),
            ).fetchone()
        return _row_to_record(row) if row else None

    def mark_deployed(
        self,
        workflow_id: UUID | str,
        *,
        platform_app_id: str | None,
        deployment_note: str | None,
        deployed_by_actor: str,
    ) -> WorkflowRecord:
        """Mark a workflow deployed. Only the owning actor may deploy their own workflow."""
        deployed_at = datetime.now(UTC).isoformat()
        with self._connect() as con:
            cur = con.execute(
                """
                UPDATE workflow_records
                SET platform_app_id = ?, deployment_note = ?, deployed_at = ?, deployed_by_actor = ?
                WHERE workflow_id = ? AND created_by_actor = ?
                """,
                (platform_app_id, deployment_note, deployed_at, deployed_by_actor, str(workflow_id), deployed_by_actor),
            )
            if cur.rowcount == 0:
                raise KeyError(f"workflow not found: {workflow_id}")
        record = self.get(workflow_id, actor_id=deployed_by_actor)
        if record is None:
            raise KeyError(f"workflow not found: {workflow_id}")
        return record

    def _connect(self) -> sqlite3.Connection:
        con = sqlite3.connect(self.db_path)
        con.row_factory = sqlite3.Row
        return con

    def _init(self) -> None:
        with self._connect() as con:
            con.execute(
                """
                CREATE TABLE IF NOT EXISTS workflow_records (
                    workflow_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    artifact_id TEXT NOT NULL,
                    artifact_name TEXT NOT NULL,
                    artifact_kind TEXT NOT NULL,
                    artifact_sha256 TEXT NOT NULL,
                    ir_signature TEXT NOT NULL,
                    ir_version TEXT NOT NULL,
                    target TEXT NOT NULL,
                    mode TEXT,
                    binding_handle TEXT NOT NULL,
                    compiler_version TEXT NOT NULL,
                    created_by_actor TEXT NOT NULL,
                    compiled_at TEXT NOT NULL,
                    platform_app_id TEXT,
                    deployment_note TEXT,
                    deployed_at TEXT,
                    deployed_by_actor TEXT
                )
                """
            )
            con.execute(
                "CREATE INDEX IF NOT EXISTS idx_workflow_records_owner ON workflow_records(created_by_actor)"
            )


def _record_to_row(record: WorkflowRecord) -> dict[str, Any]:
    data = record.model_dump()
    out: dict[str, Any] = {}
    for key, value in data.items():
        if isinstance(value, UUID):
            out[key] = str(value)
        elif isinstance(value, datetime):
            out[key] = value.isoformat()
        else:
            out[key] = value
    return out


def _row_to_record(row: sqlite3.Row) -> WorkflowRecord:
    data = dict(row)
    return WorkflowRecord(
        workflow_id=UUID(data["workflow_id"]),
        session_id=UUID(data["session_id"]),
        artifact_id=UUID(data["artifact_id"]),
        artifact_name=data["artifact_name"],
        artifact_kind=data["artifact_kind"],
        artifact_sha256=data["artifact_sha256"],
        ir_signature=data["ir_signature"],
        ir_version=data["ir_version"],
        target=data["target"],
        mode=data["mode"],
        binding_handle=data["binding_handle"],
        compiler_version=data["compiler_version"],
        created_by_actor=data["created_by_actor"],
        compiled_at=datetime.fromisoformat(data["compiled_at"]),
        platform_app_id=data["platform_app_id"],
        deployment_note=data["deployment_note"],
        deployed_at=datetime.fromisoformat(data["deployed_at"]) if data["deployed_at"] else None,
        deployed_by_actor=data["deployed_by_actor"],
    )
