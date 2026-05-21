"""Pydantic response models for public service routes."""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


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
