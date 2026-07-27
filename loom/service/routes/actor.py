"""Actor-scoped settings routes."""
from __future__ import annotations

from typing import TYPE_CHECKING, Annotated

from fastapi import APIRouter, Depends, Request, Response

from loom.service.deps import Actor, get_actor
from loom.service.errors import bad_request
from loom.service.models import ActorLLMConfigInput, ActorLLMConfigResponse

if TYPE_CHECKING:
    from loom.state.models import ActorLLMConfigRow

router = APIRouter(prefix="/v1")
ActorDep = Annotated[Actor, Depends(get_actor)]


@router.get("/actor/llm-config")
def get_actor_llm_config(request: Request, actor: ActorDep) -> ActorLLMConfigResponse:
    row = request.app.state.session_store.get_actor_llm_config(actor_id=actor.id)
    return _actor_llm_config_response(row)


@router.put("/actor/llm-config")
def put_actor_llm_config(
    body: ActorLLMConfigInput,
    request: Request,
    actor: ActorDep,
) -> ActorLLMConfigResponse:
    try:
        row = request.app.state.session_store.upsert_actor_llm_config(
            actor_id=actor.id,
            provider=body.provider,
            base_url=body.base_url,
            model=body.model,
            api_key=body.api_key,
            fernet=request.app.state.fernet,
        )
    except ValueError as e:
        raise bad_request(str(e)) from e
    return _actor_llm_config_response(row)


@router.delete("/actor/llm-config", status_code=204)
def delete_actor_llm_config(request: Request, actor: ActorDep) -> Response:
    request.app.state.session_store.delete_actor_llm_config(actor_id=actor.id)
    return Response(status_code=204)


def _actor_llm_config_response(row: ActorLLMConfigRow | None) -> ActorLLMConfigResponse:
    if row is None:
        return ActorLLMConfigResponse(
            provider=None,
            base_url=None,
            model=None,
            has_key=False,
            updated_at=None,
        )
    return ActorLLMConfigResponse(
        provider=row.llm_provider,
        base_url=row.llm_base_url,
        model=row.llm_model,
        has_key=True,
        updated_at=row.updated_at,
    )
