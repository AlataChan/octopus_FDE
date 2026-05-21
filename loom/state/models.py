"""Pydantic row models for the session SQLite store."""
from __future__ import annotations

from datetime import datetime  # noqa: TC003
from typing import Literal
from uuid import UUID  # noqa: TC003

from pydantic import BaseModel, ConfigDict, Field

from loom.runtimes.warnings import CompileWarning


class SessionRow(BaseModel):
    model_config = ConfigDict(frozen=True)

    session_id: UUID
    actor_id: str
    state: str
    latest_ir_json: str | None = None
    latest_ir_sha256: str | None = None
    llm_api_key_encrypted: bytes | None = None
    llm_base_url: str | None = None
    llm_model: str | None = None
    llm_key_version: int | None = None
    created_at: datetime
    updated_at: datetime


class ActorLLMConfigRow(BaseModel):
    model_config = ConfigDict(frozen=True)

    actor_id: str
    llm_provider: str | None = None
    llm_base_url: str
    llm_model: str
    llm_api_key_encrypted: bytes
    llm_key_version: int
    created_at: datetime
    updated_at: datetime


class TurnRow(BaseModel):
    model_config = ConfigDict(frozen=True)

    turn_id: UUID
    session_id: UUID
    actor_id: str
    user_message: str
    planner_reply: str | None = None
    ir_before: str | None = None
    ir_after: str | None = None
    validation_errors: list[str]
    status: Literal["running", "succeeded", "failed"]
    created_at: datetime


class ArtifactRow(BaseModel):
    model_config = ConfigDict(frozen=True)

    artifact_id: UUID
    session_id: UUID
    workflow_id: UUID
    actor_id: str
    artifact_name: str
    artifact_kind: Literal["zip", "yaml"]
    artifact_path: str
    artifact_size: int
    sha256: str
    target: Literal["hiagent", "dify"]
    mode: str | None
    binding_handle: str
    compile_warnings: list[CompileWarning] = Field(default_factory=list)
    created_at: datetime
