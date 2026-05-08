from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

PiiClass = Literal["none", "low", "medium", "high"]


class ReviewerSpec(BaseModel):
    role: str                                 # e.g. "cs_supervisor", "clinic_manager"
    decision_authority: list[str]             # e.g. ["publish", "refund_above_500_USD"]


class ComplianceBoundary(BaseModel):
    pii_class_default: PiiClass = "low"
    regulatory_tags: list[str] = []           # e.g. ["GDPR", "PIPL", "PIPL-medical"]
    geographies: list[str] = []               # e.g. ["CN", "EU", "US"]


class PersonaBrief(BaseModel):
    persona_id: str = Field(min_length=1)     # references registry/v1/personas/<persona_id>.yaml
    author_role: str
    vertical: str
    end_user: str
    reviewer: ReviewerSpec
    compliance_boundary: ComplianceBoundary
    success_criteria: str = Field(min_length=1, max_length=500)
