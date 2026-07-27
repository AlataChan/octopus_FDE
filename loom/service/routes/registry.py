"""Workflow registry API routes."""
from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, cast
from uuid import UUID  # noqa: TC003

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from loom.service.deps import Actor, get_actor
from loom.service.errors import not_found

if TYPE_CHECKING:
    from loom.state.models import ArtifactRow

router = APIRouter(prefix="/v1/registry/workflows")
ActorDep = Annotated[Actor, Depends(get_actor)]

# Roles allowed to mark a workflow deployed, on top of the ownership check
# enforced by the store. Kept explicit so a future read-only role is excluded
# without further changes here (see ADR 0027).
DEPLOY_CAPABLE_ROLES = frozenset({"fde", "admin"})


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
    rows = request.app.state.registry_store.list(actor_id=actor.id, target=target, binding_handle=binding)
    return [row.model_dump(mode="json") for row in rows]


@router.get("/{workflow_id}")
def get_workflow(
    workflow_id: UUID,
    request: Request,
    actor: ActorDep,
) -> dict[str, object]:
    row = request.app.state.registry_store.get(workflow_id, actor_id=actor.id)
    if row is None:
        raise not_found("workflow not found")
    artifact = request.app.state.session_store.get_artifact(
        row.session_id,
        row.artifact_id,
        actor_id=actor.id,
    )
    return {
        "registry_row": cast("dict[str, object]", row.model_dump(mode="json")),
        "artifact": _artifact_summary(artifact) if artifact else None,
    }


@router.post("/{workflow_id}/deployed")
def mark_deployed(
    workflow_id: UUID,
    body: MarkDeployedRequest,
    request: Request,
    actor: ActorDep,
) -> dict[str, object]:
    if actor.role not in DEPLOY_CAPABLE_ROLES:
        raise not_found("workflow not found")
    try:
        row = request.app.state.registry_store.mark_deployed(
            workflow_id,
            platform_app_id=body.platform_app_id,
            deployment_note=body.deployment_note,
            deployed_by_actor=actor.id,
        )
    except KeyError as e:
        raise not_found("workflow not found") from e
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


def _artifact_summary(artifact: ArtifactRow) -> dict[str, object]:
    return {
        "id": str(artifact.artifact_id),
        "name": artifact.artifact_name,
        "kind": artifact.artifact_kind,
        "sha256": artifact.sha256,
        "size": artifact.artifact_size,
        "downloaded_at": None,
    }
