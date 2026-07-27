"""Persona API routes."""
from __future__ import annotations

from typing import TYPE_CHECKING, cast

from fastapi import APIRouter, Request

from loom.fde_session.persona_brief import PersonaBrief

if TYPE_CHECKING:
    from loom.registry.personas import PersonaCatalog

router = APIRouter(prefix="/v1")


@router.get("/personas", response_model=list[PersonaBrief])
def list_personas(request: Request) -> list[PersonaBrief]:
    catalog = cast("PersonaCatalog", request.app.state.persona_catalog)
    return catalog.list()
