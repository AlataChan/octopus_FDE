"""Design knowledge retrieval API routes."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from loom.fde_session.persona_brief import PersonaBrief  # noqa: TC001
from loom.registry.design_knowledge import DesignKnowledgeCard  # noqa: TC001
from loom.registry.templates import Target  # noqa: TC001
from loom.service.errors import not_found

router = APIRouter(prefix="/v1")


class DesignKnowledgeRetrieveRequest(BaseModel):
    intent: str | None = None
    scope: str | None = None
    target: Target | None = None
    persona_id: str | None = None
    persona_brief: PersonaBrief | None = None
    brief_draft: dict[str, Any] | None = None
    top_k: int = Field(default=5, ge=1, le=20)


class DesignKnowledgeRetrieveResponse(BaseModel):
    cards: list[DesignKnowledgeCard]
    missing_constraints: list[str] = Field(default_factory=list)
    clarifying_questions: list[str] = Field(default_factory=list)


@router.post("/design-knowledge/retrieve", response_model=DesignKnowledgeRetrieveResponse)
def retrieve_design_knowledge(
    body: DesignKnowledgeRetrieveRequest,
    request: Request,
) -> DesignKnowledgeRetrieveResponse:
    persona = body.persona_brief
    if body.persona_id:
        persona = request.app.state.persona_catalog.get(body.persona_id)
        if persona is None:
            raise not_found("persona not found")
    cards = request.app.state.design_knowledge_catalog.retrieve(
        intent=body.intent,
        scope=body.scope,
        target=body.target,
        persona=persona,
        brief_draft=body.brief_draft,
        top_k=body.top_k,
    )
    return DesignKnowledgeRetrieveResponse(
        cards=cards,
        missing_constraints=_missing_constraints(body),
        clarifying_questions=[],
    )


def _missing_constraints(body: DesignKnowledgeRetrieveRequest) -> list[str]:
    missing: list[str] = []
    if not body.scope:
        missing.append("scope")
    if not body.target:
        missing.append("target")
    if not body.persona_id and body.persona_brief is None:
        missing.append("persona")
    return missing
