"""Pydantic response models for public service routes."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class ActorLLMConfigInput(BaseModel):
    provider: Literal["deepseek", "openai", "custom"] | None = None
    base_url: str = Field(min_length=1)
    model: str = Field(min_length=1)
    api_key: str | None = None


class ActorLLMConfigResponse(BaseModel):
    provider: str | None
    base_url: str | None
    model: str | None
    has_key: bool
    updated_at: datetime | None


class SessionSummary(BaseModel):
    session_id: str
    state: str
    latest_ir_sha256: str | None
    created_at: datetime
    updated_at: datetime
    display_title: str


class SessionDetail(SessionSummary):
    actor_id: str
    latest_ir_json: str | None
    title: str | None
    llm_base_url: str | None
    llm_model: str | None
    llm_key_version: int | None
    artifacts: list[dict[str, object]]


class SessionPatchInput(BaseModel):
    title: str | None = None

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str | None) -> str | None:
        if value is None:
            return None
        title = value.strip()
        if not 1 <= len(title) <= 80:
            raise ValueError("title must be 1-80 characters after trimming")
        if any(ord(ch) < 32 or ord(ch) == 127 for ch in title):
            raise ValueError("title must not contain control characters")
        if "<" in title or ">" in title:
            raise ValueError("title must not contain HTML")
        return title
