"""Template gallery API routes."""
from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Request
from pydantic import BaseModel

from loom.registry.templates import LocalizedText, Target, TemplateRecord
from loom.service.errors import not_found

router = APIRouter(prefix="/v1")


class PublicTemplate(BaseModel):
    id: str
    name: LocalizedText
    description: LocalizedText
    tags: list[str]
    scopes: list[str]
    compile_targets: list[Target]


class TemplateIRResponse(BaseModel):
    id: str
    name: LocalizedText
    description: LocalizedText
    tags: list[str]
    scopes: list[str]
    compile_targets: list[Target]
    ir: dict[str, Any]


@router.get("/templates", response_model=list[PublicTemplate])
def list_templates(
    request: Request,
    scope: str | None = None,
    target: Literal["hiagent", "dify"] | None = None,
) -> list[PublicTemplate]:
    catalog = request.app.state.template_catalog
    return [_public_template(row) for row in catalog.list(scope=scope, target=target)]


@router.get("/templates/{template_id}", response_model=TemplateIRResponse)
def get_template(template_id: str, request: Request) -> TemplateIRResponse:
    catalog = request.app.state.template_catalog
    row = catalog.get(template_id)
    if row is None:
        raise not_found("template not found")
    entry = row.entry
    return TemplateIRResponse(
        id=entry.id,
        name=entry.name,
        description=entry.description,
        tags=list(entry.tags),
        scopes=list(entry.scopes),
        compile_targets=list(entry.compile_targets),
        ir=row.ir,
    )


def _public_template(row: TemplateRecord) -> PublicTemplate:
    entry = row.entry
    return PublicTemplate(
        id=entry.id,
        name=entry.name,
        description=entry.description,
        tags=list(entry.tags),
        scopes=list(entry.scopes),
        compile_targets=list(entry.compile_targets),
    )
