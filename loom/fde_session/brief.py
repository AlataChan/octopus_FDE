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
    intent_clarifications: list[str] = Field(default_factory=list)
    known_edits: list[str] = Field(default_factory=list)


class WorkflowBriefDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    workflow_id: str | None = None
    title: str | None = None
    intent: str | None = None
    trigger: TriggerSpec | None = None
    inputs: list[InputSpec] = Field(default_factory=list)
    data_sources: list[DataSourceRef] = Field(default_factory=list)
    tools: list[str] = Field(default_factory=list)
    credentials: list[CredentialBindingRef] = Field(default_factory=list)
    approval_points: list[ApprovalPoint] = Field(default_factory=list)
    success_criteria: str = ""
    compliance_boundary: ComplianceBoundary | None = None
    intent_clarifications: list[str] = Field(default_factory=list)
    known_edits: list[str] = Field(default_factory=list)
    target_runtime: Literal["hiagent", "dify"] | None = None
    scope: str | None = None

    def to_strict(self) -> WorkflowBrief:
        missing = [
            field
            for field in ("title", "intent", "compliance_boundary")
            if getattr(self, field) in (None, "")
        ]
        if missing:
            raise ValueError(f"WorkflowBriefDraft missing required field(s): {', '.join(missing)}")
        title = self.title
        intent = self.intent
        compliance_boundary = self.compliance_boundary
        assert title is not None
        assert intent is not None
        assert compliance_boundary is not None
        return WorkflowBrief(
            workflow_id=self.workflow_id,
            title=title,
            intent=intent,
            trigger=self.trigger,
            inputs=self.inputs,
            data_sources=self.data_sources,
            tools=self.tools,
            credentials=self.credentials,
            approval_points=self.approval_points,
            success_criteria=self.success_criteria,
            compliance_boundary=compliance_boundary,
            intent_clarifications=self.intent_clarifications,
            known_edits=self.known_edits,
        )
