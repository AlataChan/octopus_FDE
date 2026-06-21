"""Persona API routes."""
from __future__ import annotations

from fastapi import APIRouter, Request

from loom.fde_session.persona_brief import PersonaBrief

router = APIRouter(prefix="/v1")


@router.get("/personas", response_model=list[PersonaBrief])
def list_personas(request: Request) -> list[PersonaBrief]:
    return request.app.state.persona_catalog.list()
