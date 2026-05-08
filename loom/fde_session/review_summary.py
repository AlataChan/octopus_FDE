"""Reviewer-facing summary models for FDE workflow changes."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class NodeChange(_Strict):
    node_id: str
    kind: Literal["added", "removed", "modified"]
    field_diffs: list[str] = Field(default_factory=list)


class CredentialChange(_Strict):
    handle: str
    kind: Literal["added", "removed", "scope_widened", "scope_narrowed"]


class ExternalCall(_Strict):
    node_id: str
    host: str
    method: str
    sensitivity: Literal["read", "write", "payment"]


class PolicyChange(_Strict):
    field: str
    before: Any
    after: Any


class ComplianceChange(_Strict):
    field: str
    before: Any
    after: Any


class ReviewSummary(_Strict):
    node_changes: list[NodeChange] = Field(default_factory=list)
    credential_access_changes: list[CredentialChange] = Field(default_factory=list)
    external_calls: list[ExternalCall] = Field(default_factory=list)
    policy_changes: list[PolicyChange] = Field(default_factory=list)
    compliance_changes: list[ComplianceChange] = Field(default_factory=list)
    reverse_compile_status: Literal["clean", "drift_detected", "blocked"]
