"""Types crossing the Planner boundary."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from loom.fde_session.persona_brief import PersonaBrief  # noqa: TC001
from loom.ir.models import IRDocument  # noqa: TC001


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class IntentRequest(_Strict):
    """An Author's request to plan a workflow.

    `scope` filters the registry (per PRD §4 "How the Planner gets context").
    `persona_brief` (NEW per ADR 0023) shapes the Planner system prompt — drives the
    clarification policy, registry scope filtering, and informs the Planner about
    compliance boundaries. In Phase 1 (IR v0.3) the Persona Brief does NOT write
    structured fields into the IR; it influences the Planner's natural-language
    reasoning. Phase 3.1's IR v0.4 bump (ADR 0022) adds `metadata.compliance_class`
    and `output_schema.<field>.pii_class` overrides which the Planner will then emit
    structurally. Until v0.4, Persona-driven compliance signals live in node
    `rationale` text + `clarify.py` blocking-question policy + scope filtering, NOT
    as a typed IR field.

    `target` selects the runtime; defaults to "hiagent" (primary). The Planner's
    output IR is runtime-agnostic, but knowing the target lets the Planner avoid
    suggesting node features that the chosen runtime cannot honor (consulted via
    each adapter's `redlines()` method on the RuntimeAdapter contract from ADR 0015).
    """
    intent: str = Field(min_length=1)
    scope: str = Field(min_length=1)
    persona_brief: PersonaBrief | None = None
    target: Literal["hiagent", "dify"] = "hiagent"
    max_retries: int = Field(ge=0, le=5, default=3)
    extra_context: dict[str, Any] | None = None


FailureBucket = Literal[
    # Planner-side (PRD §10 failure taxonomy 1–4):
    "schema", "reference", "type_flow", "policy",
    # Compiler/Deployer-side (5–8):
    "compile", "deploy", "reverse_compile", "registry_acl",
    # Runtime (9–10):
    "semantic_conformance", "platform",
    # Human:
    "human_review_rejection",
]


class FailureRecord(_Strict):
    bucket: FailureBucket
    detail: str
    location: str | None = None  # e.g., "nodes[2].rationale" — from Validator


class PlannerResult(_Strict):
    """The Planner's verdict for one IntentRequest."""
    ir: IRDocument | None
    attempts: int
    ok: bool
    failures: list[FailureRecord] = Field(default_factory=list)
    cost_usd: float
    latency_s: float
