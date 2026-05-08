"""Workflow brief models for FDE sessions."""
from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

TypeName = Literal[
    "string", "number", "boolean", "null", "json",
    "string[]", "number[]", "json[]",
    "chunks", "file", "any",
]

Identifier = Annotated[str, StringConstraints(pattern=r"^[a-zA-Z_][a-zA-Z0-9_]*$")]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class TriggerSpec(_Strict):
    mode: Literal["manual", "schedule", "webhook"]
    schedule_cron: str | None = None
    webhook_path: str | None = None

    @model_validator(mode="after")
    def _mode_requires_detail(self) -> TriggerSpec:
        if self.mode == "schedule" and not self.schedule_cron:
            raise ValueError("schedule trigger requires schedule_cron")
        if self.mode == "webhook" and not self.webhook_path:
            raise ValueError("webhook trigger requires webhook_path")
        return self


class InputSpec(_Strict):
    name: Identifier
    type: TypeName
    required: bool = False
    description: str | None = None


class DataSourceRef(_Strict):
    handle: Annotated[str, StringConstraints(min_length=1)]
    kind: Literal["dataset", "kb", "table", "api"]


class CredentialBindingRef(_Strict):
    handle: Annotated[str, StringConstraints(min_length=1)]
    scheme: Literal["bearer", "oauth2", "api_key", "none"]
    allowed_hosts: list[str] | None = None


class ApprovalPoint(_Strict):
    stage: Annotated[str, StringConstraints(min_length=1)]
    reviewer_role: Annotated[str, StringConstraints(min_length=1)]
    blocking: bool = True


class ComplianceBoundary(_Strict):
    pii_class_default: Literal["none", "low", "medium", "high"]
    regulatory_tags: list[str] = Field(default_factory=list)
    geographies: list[str] = Field(default_factory=list)


class WorkflowBrief(_Strict):
    workflow_id: str | None = None
    title: Annotated[str, StringConstraints(min_length=1, max_length=200)]
    intent: Annotated[str, StringConstraints(min_length=1)]
    trigger: TriggerSpec | None = None
    inputs: list[InputSpec] = Field(default_factory=list)
    data_sources: list[DataSourceRef] = Field(default_factory=list)
    tools: list[str] = Field(default_factory=list)
    credentials: list[CredentialBindingRef] = Field(default_factory=list)
    approval_points: list[ApprovalPoint] = Field(default_factory=list)
    success_criteria: str = ""
    compliance_boundary: ComplianceBoundary
    known_edits: list[str] = Field(default_factory=list)
