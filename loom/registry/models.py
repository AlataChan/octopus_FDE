"""Workflow registry models."""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


class WorkflowRecord(BaseModel):
    """Portable workflow baseline row stored in workflow_registry.db."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    workflow_id: UUID = Field(default_factory=uuid4)
    session_id: UUID
    artifact_id: UUID
    artifact_name: str
    artifact_kind: Literal["zip", "yaml"]
    artifact_sha256: str
    ir_signature: str
    ir_version: str
    target: Literal["hiagent", "dify"]
    mode: str | None = None
    binding_handle: str
    compiler_version: str
    created_by_actor: str
    compiled_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    platform_app_id: str | None = None
    deployment_note: str | None = None
    deployed_at: datetime | None = None
    deployed_by_actor: str | None = None

    @classmethod
    def new(
        cls,
        *,
        session_id: str,
        artifact_id: str,
        artifact_name: str,
        artifact_kind: Literal["zip", "yaml"],
        artifact_sha256: str,
        ir_signature: str,
        ir_version: str,
        target: Literal["hiagent", "dify"],
        mode: str | None,
        binding_handle: str,
        compiler_version: str,
        created_by_actor: str,
    ) -> WorkflowRecord:
        return cls(
            session_id=UUID(session_id),
            artifact_id=UUID(artifact_id),
            artifact_name=artifact_name,
            artifact_kind=artifact_kind,
            artifact_sha256=artifact_sha256,
            ir_signature=ir_signature,
            ir_version=ir_version,
            target=target,
            mode=mode,
            binding_handle=binding_handle,
            compiler_version=compiler_version,
            created_by_actor=created_by_actor,
        )
