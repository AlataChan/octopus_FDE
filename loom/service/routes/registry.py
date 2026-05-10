"""Workflow registry API routes."""
from __future__ import annotations

from typing import Annotated, cast
from uuid import UUID  # noqa: TC003

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from loom.service.deps import Actor, get_actor
from loom.service.errors import not_found

router = APIRouter(prefix="/v1/registry/workflows")
ActorDep = Annotated[Actor, Depends(get_actor)]


class MarkDeployedRequest(BaseModel):
    platform_app_id: str | None = None
    deployment_note: str | None = None


@router.get("")
def list_workflows(
    request: Request,
    actor: ActorDep,
    target: str | None = None,
    binding: str | None = None,
) -> list[dict[str, object]]:
    del actor
    rows = request.app.state.registry_store.list(target=target, binding_handle=binding)
    return [row.model_dump(mode="json") for row in rows]


@router.get("/{workflow_id}")
def get_workflow(
    workflow_id: UUID,
    request: Request,
    actor: ActorDep,
) -> dict[str, object]:
    del actor
    row = request.app.state.registry_store.get(workflow_id)
    if row is None:
        raise not_found("workflow not found")
    return cast("dict[str, object]", row.model_dump(mode="json"))


@router.post("/{workflow_id}/deployed")
def mark_deployed(
    workflow_id: UUID,
    body: MarkDeployedRequest,
    request: Request,
    actor: ActorDep,
) -> dict[str, object]:
    row = request.app.state.registry_store.mark_deployed(
        workflow_id,
        platform_app_id=body.platform_app_id,
        deployment_note=body.deployment_note,
        deployed_by_actor=actor.id,
    )
    # Registry deployment is a workflow-level event; append it to the linked session archive.
    request.app.state.archive_writer.append(
        row.session_id,
        actor_id=actor.id,
        event_type="registry.deployed",
        payload={
            "workflow_id": str(row.workflow_id),
            "platform_app_id": body.platform_app_id,
            "deployment_note": body.deployment_note,
            "deployed_by_actor": actor.id,
        },
    )
    return cast("dict[str, object]", row.model_dump(mode="json"))
