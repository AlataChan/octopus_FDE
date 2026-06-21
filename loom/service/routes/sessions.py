"""Session, turn, compile, artifact, binding, and archive routes."""
from __future__ import annotations

import hashlib
import json
import re
import sys
from collections.abc import Callable
from dataclasses import asdict
from pathlib import Path
from typing import Annotated, Any, Literal, cast
from urllib.parse import quote
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, Field

from loom.diff.ir_diff import diff_ir
from loom.fde_session.brief import WorkflowBriefDraft
from loom.fde_session.clarify_engine import (
    ClarifyQuestion,
    QUESTIONNAIRE_AFTER_ROUNDS,
    next_blocking_questions,
)
from loom.fde_session.edit_intent import parse_edit_intent
from loom.fde_session.redaction import has_potential_secret, redact_draft, redact_text
from loom.ir.canonicalize import canonical_ir_hash
from loom.ir.models import IRDocument
from loom.registry.models import WorkflowRecord
from loom.runtimes.dify.v1_14.compiler import compile_ir as compile_dify
from loom.runtimes.hiagent.binding import HiagentBinding
from loom.runtimes.hiagent.v2_6.compiler import compile_ir, compile_ir_chatflow
from loom.runtimes.warnings import CompileWarning
from loom.service.deps import Actor, get_actor
from loom.service.errors import bad_request, conflict, not_found
from loom.service.models import SessionDetail, SessionPatchInput, SessionSummary
from loom.state.models import SessionRow, TurnRow
from loom.validator.validate import validate

router = APIRouter(prefix="/v1")
ActorDep = Annotated[Actor, Depends(get_actor)]
CLIENT_PLANNER_ERROR = "planner_error"
REDACTED_SECRET_USER_MESSAGE = "[REDACTED:potential_secret]"
BRIEF_REVIEW_REPLY = "Please review the workflow brief and confirm when it is ready to generate."


class CreateSessionRequest(BaseModel):
    template_id: str | None = None
    scope: str | None = None


class LLMConfigRequest(BaseModel):
    api_key: str = Field(min_length=1)
    base_url: str = Field(min_length=1)
    model: str = Field(min_length=1)


class TurnRequest(BaseModel):
    user_message: str = Field(min_length=1)


class CompileRequest(BaseModel):
    target: Literal["hiagent", "dify"]
    mode: Literal["chat", "chatflow"] | None = None
    binding: str = "test"


@router.get("/sessions")
def list_sessions(request: Request, actor: ActorDep) -> list[SessionSummary]:
    return [
        _session_summary_response(row, request, actor.id)
        for row in request.app.state.session_store.list_sessions(actor_id=actor.id)
    ]


@router.post("/sessions")
def create_session(
    body: CreateSessionRequest,
    request: Request,
    actor: ActorDep,
) -> dict[str, object]:
    actor_id = actor.id
    session = request.app.state.session_store.create_session_with_actor_defaults(
        actor_id=actor_id,
        fernet=request.app.state.fernet,
        audit_writer=_session_audit_writer(request, actor_id),
        self_design=body.template_id is None,
    )
    if body.template_id:
        session = _seed_session_from_template(
            request,
            session.session_id,
            actor_id=actor_id,
            template_id=body.template_id,
            scope=body.scope,
        )
    return {"session_id": str(session.session_id), "state": session.state}


@router.get("/sessions/{session_id}")
def get_session(
    session_id: UUID,
    request: Request,
    actor: ActorDep,
) -> SessionDetail:
    session = request.app.state.session_store.get_session(session_id, actor_id=actor.id)
    if session is None:
        raise not_found("session not found")
    return _session_detail_response(session, request, actor.id)


@router.patch("/sessions/{session_id}")
def patch_session(
    session_id: UUID,
    body: SessionPatchInput,
    request: Request,
    actor: ActorDep,
) -> SessionDetail:
    session = request.app.state.session_store.get_session(session_id, actor_id=actor.id)
    if session is None:
        raise not_found("session not found")
    if "title" in body.model_fields_set:
        session = request.app.state.session_store.update_session_title(
            session_id,
            actor_id=actor.id,
            title=body.title,
        )
    return _session_detail_response(session, request, actor.id)


@router.delete("/sessions/{session_id}", status_code=204)
def delete_session(
    session_id: UUID,
    request: Request,
    actor: ActorDep,
) -> Response:
    deleted = request.app.state.session_store.delete_session(session_id, actor_id=actor.id)
    if not deleted:
        raise not_found("session not found")
    request.app.state.archive_writer.append(
        session_id,
        actor_id=actor.id,
        event_type="session.deleted",
        payload={},
    )
    return Response(status_code=204)


@router.patch("/sessions/{session_id}/llm-config")
def set_llm_config(
    session_id: UUID,
    body: LLMConfigRequest,
    request: Request,
    actor: ActorDep,
) -> dict[str, object]:
    try:
        request.app.state.session_store.set_llm_config(
            session_id,
            actor_id=actor.id,
            api_key=body.api_key,
            base_url=body.base_url,
            model=body.model,
            fernet=request.app.state.fernet,
        )
    except KeyError as e:
        raise not_found("session not found") from e
    request.app.state.archive_writer.append(
        session_id,
        actor_id=actor.id,
        event_type="session.llm_config_set",
        payload={"model": body.model},
    )
    return {"ok": True, "model": body.model}


@router.post("/sessions/{session_id}/turns")
def create_turn(
    session_id: UUID,
    body: TurnRequest,
    request: Request,
    actor: ActorDep,
) -> dict[str, object]:
    store = request.app.state.session_store
    session = store.get_session(session_id, actor_id=actor.id)
    if session is None:
        raise not_found("session not found")
    previous_turns = store.list_turns(session_id, actor_id=actor.id)
    last_turn = previous_turns[-1] if previous_turns else None
    loaded_draft_before = _load_draft(session.brief_draft)
    brief_before = _draft_json(loaded_draft_before) if loaded_draft_before else None
    if has_potential_secret(body.user_message):
        turn = store.create_turn(
            session_id,
            actor_id=actor.id,
            user_message=REDACTED_SECRET_USER_MESSAGE,
            ir_before=session.latest_ir_json,
            kind="clarify",
            brief_before=brief_before,
        )
        _archive_turn_started(request, session_id, actor.id, turn, body.user_message)
        return _handle_clarify_turn(
            request=request,
            actor=actor,
            session=session,
            turn=turn,
            user_message=body.user_message,
            last_turn=last_turn,
        )
    turn = store.create_turn(
        session_id,
        actor_id=actor.id,
        user_message=body.user_message,
        ir_before=session.latest_ir_json,
        brief_before=brief_before,
    )
    _archive_turn_started(request, session_id, actor.id, turn, body.user_message)
    if _is_brief_review_confirmation(last_turn, body.user_message):
        draft = _load_draft(session.brief_draft) or _load_draft(last_turn.brief_after if last_turn else None)
        if draft is not None:
            return _finish_plan_from_draft(
                request=request,
                actor=actor,
                session=session,
                turn=turn,
                draft=draft,
                brief_before_json=brief_before,
            )
    if _should_run_clarify(session, body.user_message):
        return _handle_clarify_turn(
            request=request,
            actor=actor,
            session=session,
            turn=turn,
            user_message=body.user_message,
            last_turn=last_turn,
        )
    try:
        ir = request.app.state.planner(
            user_message=body.user_message,
            session=session,
            target=_session_target_runtime(session),
            scope=_session_scope(session),
            llm_config={
                "api_key": request.app.state.fernet.decrypt(session.llm_api_key_encrypted).decode("utf-8")
                if session.llm_api_key_encrypted
                else "",
                "base_url": session.llm_base_url,
                "model": session.llm_model,
            },
        )
        ir_doc = IRDocument.model_validate(ir) if isinstance(ir, dict) else ir
        ir_json = json.dumps(
            ir_doc.model_dump(by_alias=True, exclude_none=True),
            ensure_ascii=False,
            sort_keys=True,
        )
        failures = validate(
            json.loads(ir_json),
            scope=_session_scope(session),
            audit_max_retention_days=request.app.state.settings.audit_max_retention_days,
        )
        if failures:
            raise ValueError("; ".join(f.detail for f in failures))
        row = store.finish_turn_succeeded(
            turn.turn_id,
            actor_id=actor.id,
            planner_reply="IR generated",
            ir_after=ir_json,
        )
        request.app.state.archive_writer.append(
            session_id,
            actor_id=actor.id,
            event_type="turn.succeeded",
            payload={
                "turn_id": str(turn.turn_id),
                "ir_after_sha256": _sha256_text(ir_json),
                "validation_status": "ok",
            },
        )
        return _turn_response(row)
    except Exception as e:  # noqa: BLE001 - service records planner/validation failures
        row = store.finish_turn_failed(
            turn.turn_id,
            actor_id=actor.id,
            error_kind=CLIENT_PLANNER_ERROR,
            validation_errors=[CLIENT_PLANNER_ERROR],
            error_correlation_id=_error_correlation_id(),
        )
        _archive_planner_failure(request, session_id, actor.id, turn.turn_id, e, row.error_correlation_id)
        return _turn_response(row)


@router.get("/sessions/{session_id}/turns")
def list_turns(
    session_id: UUID,
    request: Request,
    actor: ActorDep,
) -> list[dict[str, object]]:
    return [
        _turn_response(row)
        for row in request.app.state.session_store.list_turns(session_id, actor_id=actor.id)
    ]


@router.get("/sessions/{session_id}/ir")
def get_ir(
    session_id: UUID,
    request: Request,
    actor: ActorDep,
) -> dict[str, object]:
    session = request.app.state.session_store.get_session(session_id, actor_id=actor.id)
    if session is None:
        raise not_found("session not found")
    doc = json.loads(session.latest_ir_json) if session.latest_ir_json else None
    failures = (
        validate(
            doc,
            scope=_session_scope(session),
            audit_max_retention_days=request.app.state.settings.audit_max_retention_days,
        )
        if doc
        else []
    )
    return {
        "ir": doc,
        "latest_ir_sha256": session.latest_ir_sha256,
        "validator_status": "ok" if not failures else "failed",
        "validation_errors": [
            {"bucket": f.bucket, "detail": f.detail, "location": f.location}
            for f in failures
        ],
    }


@router.get("/sessions/{session_id}/ir/diff")
def get_ir_diff(
    session_id: UUID,
    from_turn: UUID,
    to_turn: UUID,
    request: Request,
    actor: ActorDep,
) -> dict[str, object]:
    store = request.app.state.session_store
    before = store.get_turn(from_turn, actor_id=actor.id)
    after = store.get_turn(to_turn, actor_id=actor.id)
    if before is None or after is None or before.session_id != session_id or after.session_id != session_id:
        raise not_found("turn not found")
    before_snapshot = _turn_snapshot(before)
    after_snapshot = _turn_snapshot(after)
    if before_snapshot is None or after_snapshot is None:
        raise not_found("turn snapshot not found")
    payload = diff_ir(json.loads(before_snapshot), json.loads(after_snapshot))
    return {"from": str(from_turn), "to": str(to_turn), **payload}


@router.post("/sessions/{session_id}/compile")
def compile_session(
    session_id: UUID,
    body: CompileRequest,
    request: Request,
    actor: ActorDep,
) -> dict[str, object]:
    session = request.app.state.session_store.get_session(session_id, actor_id=actor.id)
    if session is None:
        raise not_found("session not found")
    if session.state == "init":
        raise conflict("session must have validated IR before compile")
    if not session.latest_ir_json:
        raise conflict("session has no accepted IR")
    _ensure_template_target_supported(request, session_id, actor.id, body.target)
    ir = IRDocument.model_validate_json(session.latest_ir_json)
    artifact_bytes, artifact_name, artifact_kind, compile_warnings = _compile_artifact(
        ir,
        target=body.target,
        mode=body.mode,
        binding_handle=body.binding,
        binding_dir=request.app.state.settings.binding_dir,
    )
    digest = hashlib.sha256(artifact_bytes).hexdigest()
    workflow_id = uuid4()
    artifact_id = uuid4()
    ext = "zip" if artifact_kind == "zip" else "yaml"
    rel_path = Path("sessions") / str(session_id) / "artifacts" / f"{artifact_id}.{ext}"
    abs_path = request.app.state.settings.data_dir / rel_path
    abs_path.parent.mkdir(parents=True, exist_ok=True)
    abs_path.write_bytes(artifact_bytes)
    artifact = request.app.state.session_store.create_artifact(
        session_id,
        actor_id=actor.id,
        workflow_id=workflow_id,
        artifact_name=artifact_name,
        artifact_kind=artifact_kind,
        artifact_path=str(rel_path),
        artifact_size=len(artifact_bytes),
        sha256=digest,
        target=body.target,
        mode=body.mode,
        binding_handle=body.binding,
        compile_warnings=compile_warnings,
    )
    # Preserve the generated artifact UUID in the on-disk filename; update DB row path via direct rewrite.
    final_rel_path = Path("sessions") / str(session_id) / "artifacts" / f"{artifact.artifact_id}.{ext}"
    final_abs_path = request.app.state.settings.data_dir / final_rel_path
    abs_path.replace(final_abs_path)
    _rewrite_artifact_path(request.app.state.session_store, artifact.artifact_id, str(final_rel_path))
    artifact = request.app.state.session_store.get_artifact(session_id, artifact.artifact_id, actor_id=actor.id)
    assert artifact is not None
    record = WorkflowRecord.new(
        session_id=str(session_id),
        artifact_id=str(artifact.artifact_id),
        artifact_name=artifact_name,
        artifact_kind=artifact_kind,
        artifact_sha256=digest,
        ir_signature=canonical_ir_hash(json.loads(session.latest_ir_json)),
        ir_version=ir.ir_version,
        target=body.target,
        mode=body.mode,
        binding_handle=body.binding,
        compiler_version="phase2-m1",
        created_by_actor=actor.id,
    )
    object.__setattr__(record, "workflow_id", workflow_id)
    request.app.state.registry_store.create(record)
    request.app.state.archive_writer.append(
        session_id,
        actor_id=actor.id,
        event_type="compile.produced",
        payload={
            "workflow_id": str(workflow_id),
            "target": body.target,
            "mode": body.mode,
            "binding_handle": body.binding,
            "artifact_id": str(artifact.artifact_id),
            "artifact_sha256": digest,
            "artifact_size": len(artifact_bytes),
            "compiler_version": "phase2-m1",
            "ir_version": ir.ir_version,
            "compile_warnings": [asdict(w) for w in compile_warnings],
        },
    )
    return {
        "artifact_id": str(artifact.artifact_id),
        "workflow_id": str(workflow_id),
        "artifact_name": artifact_name,
        "artifact_size": len(artifact_bytes),
        "sha256": digest,
        "compile_warnings": [asdict(w) for w in compile_warnings],
    }


@router.get("/sessions/{session_id}/artifacts")
def list_artifacts(
    session_id: UUID,
    request: Request,
    actor: ActorDep,
) -> list[dict[str, object]]:
    return [
        row.model_dump(mode="json")
        for row in request.app.state.session_store.list_artifacts(session_id, actor_id=actor.id)
    ]


@router.get("/sessions/{session_id}/artifacts/{artifact_id}")
def download_artifact(
    session_id: UUID,
    artifact_id: UUID,
    request: Request,
    actor: ActorDep,
) -> Response:
    artifact = request.app.state.session_store.get_artifact(session_id, artifact_id, actor_id=actor.id)
    if artifact is None:
        raise not_found("artifact not found")
    path = request.app.state.settings.data_dir / artifact.artifact_path
    raw = path.read_bytes()
    request.app.state.session_store.mark_downloaded(session_id, actor_id=actor.id)
    request.app.state.archive_writer.append(
        session_id,
        actor_id=actor.id,
        event_type="artifact.downloaded",
        payload={"artifact_id": str(artifact.artifact_id), "artifact_sha256": artifact.sha256},
    )
    media_type = "application/zip" if artifact.artifact_kind == "zip" else "application/x-yaml"
    return Response(
        content=raw,
        media_type=media_type,
        headers={"content-disposition": _content_disposition(artifact.artifact_name)},
    )


def _content_disposition(filename: str) -> str:
    # RFC 5987: HTTP headers must be latin-1; non-ASCII filenames need a percent-encoded
    # filename* alongside an ASCII fallback so old + new browsers both pick a sane name.
    ascii_fallback = filename.encode("ascii", "ignore").decode("ascii").replace('"', "").strip()
    if not ascii_fallback or ascii_fallback.startswith("."):
        ascii_fallback = f"artifact{ascii_fallback}"
    encoded = quote(filename, safe="")
    return f'attachment; filename="{ascii_fallback}"; filename*=UTF-8\'\'{encoded}'


def _session_audit_writer(request: Request, actor_id: str) -> Callable[[UUID, list[tuple[str, dict[str, object]]]], None]:
    def write(session_id: UUID, events: list[tuple[str, dict[str, object]]]) -> None:
        for event_type, payload in events:
            request.app.state.archive_writer.append(
                session_id,
                actor_id=actor_id,
                event_type=cast(Any, event_type),
                payload=payload,
            )

    return write


def _archive_turn_started(request: Request, session_id: UUID, actor_id: str, turn: TurnRow, user_message: str) -> None:
    request.app.state.archive_writer.append(
        session_id,
        actor_id=actor_id,
        event_type="turn.started",
        payload={"turn_id": str(turn.turn_id), "user_message_sha256": _sha256_text(user_message)},
    )


def _error_correlation_id() -> str:
    return uuid4().hex


def _archive_planner_failure(
    request: Request,
    session_id: UUID,
    actor_id: str,
    turn_id: UUID,
    error: Exception,
    correlation_id: str | None,
) -> None:
    message = str(error)
    print(f"planner_error correlation_id={correlation_id} message={message}", file=sys.stderr)
    request.app.state.archive_writer.append(
        session_id,
        actor_id=actor_id,
        event_type="turn.failed",
        payload={
            "turn_id": str(turn_id),
            "error_kind": CLIENT_PLANNER_ERROR,
            "error_correlation_id": correlation_id,
            "error_message_sha256": _sha256_text(message),
        },
    )


def _handle_clarify_turn(
    *,
    request: Request,
    actor: Actor,
    session: SessionRow,
    turn: TurnRow,
    user_message: str,
    last_turn: TurnRow | None,
) -> dict[str, object]:
    store = request.app.state.session_store
    draft_before = _load_draft(session.brief_draft)
    brief_before_json = _draft_json(draft_before) if draft_before else None
    round_index = session.clarify_round + 1
    request.app.state.archive_writer.append(
        session.session_id,
        actor_id=actor.id,
        event_type="turn.clarify_started",
        payload={
            "turn_id": str(turn.turn_id),
            "round_index": round_index,
            "user_message_sha256": _sha256_text(user_message),
            "draft_before_sha256": _sha256_text(brief_before_json) if brief_before_json else None,
        },
    )
    if has_potential_secret(user_message):
        draft_after = redact_draft(draft_before or WorkflowBriefDraft(title="Self-Design workflow", intent=""))
        question = ClarifyQuestion(
            text="Please refer to the credential by handle name instead of pasting raw secrets.",
            field_path="credentials",
            options=None,
            allow_freeform=True,
            severity="block",
        )
        return _finish_clarify_response(
            request=request,
            actor=actor,
            session=session,
            turn=turn,
            kind="clarify",
            question_payload=question.model_dump(mode="json"),
            draft_before_json=brief_before_json,
            draft_after=draft_after,
            clarify_round=round_index,
        )

    stale_response = _stale_turn_reference_response(
        request=request,
        actor=actor,
        session=session,
        turn=turn,
        user_message=user_message,
        last_turn=last_turn,
        draft_before=draft_before,
        brief_before_json=brief_before_json,
    )
    if stale_response is not None:
        return stale_response

    pending_fields = _pending_field_paths(last_turn)
    result = request.app.state.clarify_engine.step(
        brief=draft_before,
        user_message=user_message,
        round_index=session.clarify_round,
        pending_field_paths=pending_fields,
    )
    draft_after = redact_draft(_merge_draft(draft_before, result.intent_update))
    block_questions = next_blocking_questions(draft_after)
    if result.next_action == "ready" and not block_questions:
        return _finish_brief_review_response(
            request=request,
            actor=actor,
            session=session,
            turn=turn,
            draft=draft_after,
            brief_before_json=brief_before_json,
        )

    if session.clarify_round >= QUESTIONNAIRE_AFTER_ROUNDS and block_questions:
        payload: dict[str, object] = {"questions": [q.model_dump(mode="json") for q in block_questions]}
        request.app.state.archive_writer.append(
            session.session_id,
            actor_id=actor.id,
            event_type="turn.questionnaire_emitted",
            payload={
                "turn_id": str(turn.turn_id),
                "missing_fields": [q.field_path for q in block_questions],
                "draft_snapshot_sha256": _sha256_text(_draft_json(draft_after)),
            },
        )
        return _finish_clarify_response(
            request=request,
            actor=actor,
            session=session,
            turn=turn,
            kind="questionnaire",
            question_payload=payload,
            draft_before_json=brief_before_json,
            draft_after=draft_after,
            clarify_round=session.clarify_round,
        )

    question = block_questions[0] if block_questions else result.question
    assert question is not None
    return _finish_clarify_response(
        request=request,
        actor=actor,
        session=session,
        turn=turn,
        kind="clarify",
        question_payload=question.model_dump(mode="json"),
        draft_before_json=brief_before_json,
        draft_after=draft_after,
        clarify_round=round_index,
    )


def _finish_clarify_response(
    *,
    request: Request,
    actor: Actor,
    session: SessionRow,
    turn: TurnRow,
    kind: Literal["clarify", "questionnaire"],
    question_payload: dict[str, object],
    draft_before_json: str | None,
    draft_after: WorkflowBriefDraft,
    clarify_round: int,
) -> dict[str, object]:
    draft_after_json = _draft_json(draft_after)
    row = request.app.state.session_store.finish_turn_clarify(
        turn.turn_id,
        actor_id=actor.id,
        kind=kind,
        planner_reply=_question_text(question_payload),
        clarify_question=json.dumps(question_payload, ensure_ascii=False, sort_keys=True),
        brief_before=draft_before_json,
        brief_after=draft_after_json,
        clarify_round=clarify_round,
        target_runtime=draft_after.target_runtime,
        scope=draft_after.scope,
    )
    options_count = _options_count(question_payload)
    request.app.state.archive_writer.append(
        session.session_id,
        actor_id=actor.id,
        event_type="turn.clarify_replied",
        payload={
            "turn_id": str(turn.turn_id),
            "round_index": clarify_round,
            "ask_field_path": _question_field_path(question_payload),
            "options_count": options_count,
            "draft_after_sha256": _sha256_text(draft_after_json),
            "gate_pass": False,
        },
    )
    response = _turn_response(row)
    response["clarify_round"] = clarify_round
    return response


def _finish_brief_review_response(
    *,
    request: Request,
    actor: Actor,
    session: SessionRow,
    turn: TurnRow,
    draft: WorkflowBriefDraft,
    brief_before_json: str | None,
) -> dict[str, object]:
    draft_json = _draft_json(draft)
    row = request.app.state.session_store.finish_turn_brief_review(
        turn.turn_id,
        actor_id=actor.id,
        planner_reply=BRIEF_REVIEW_REPLY,
        brief_before=brief_before_json,
        brief_after=draft_json,
        target_runtime=draft.target_runtime,
        scope=draft.scope,
    )
    request.app.state.archive_writer.append(
        session.session_id,
        actor_id=actor.id,
        event_type="turn.clarify_replied",
        payload={
            "turn_id": str(turn.turn_id),
            "ask_field_path": None,
            "options_count": 0,
            "draft_after_sha256": _sha256_text(draft_json),
            "gate_pass": True,
            "review_required": True,
        },
    )
    response = _turn_response(row)
    response["clarify_round"] = 0
    return response


def _finish_plan_from_draft(
    *,
    request: Request,
    actor: Actor,
    session: SessionRow,
    turn: TurnRow,
    draft: WorkflowBriefDraft,
    brief_before_json: str | None,
) -> dict[str, object]:
    del brief_before_json
    draft_json = _draft_json(draft)
    request.app.state.session_store.update_session_brief_state(
        session.session_id,
        actor_id=actor.id,
        brief_draft=draft_json,
        clarify_round=0,
        target_runtime=draft.target_runtime,
        scope=draft.scope,
    )
    try:
        ir = request.app.state.planner(
            user_message=_draft_to_planner_message(draft),
            session=session,
            target=cast(Literal["hiagent", "dify"], draft.target_runtime),
            scope=draft.scope or _session_scope(session),
            llm_config={
                "api_key": request.app.state.fernet.decrypt(session.llm_api_key_encrypted).decode("utf-8")
                if session.llm_api_key_encrypted
                else "",
                "base_url": session.llm_base_url,
                "model": session.llm_model,
            },
        )
        ir_doc = IRDocument.model_validate(ir) if isinstance(ir, dict) else ir
        ir_json = json.dumps(
            ir_doc.model_dump(by_alias=True, exclude_none=True),
            ensure_ascii=False,
            sort_keys=True,
        )
        failures = validate(
            json.loads(ir_json),
            scope=draft.scope or _session_scope(session),
            audit_max_retention_days=request.app.state.settings.audit_max_retention_days,
        )
        if failures:
            raise ValueError("; ".join(f.detail for f in failures))
        row = request.app.state.session_store.finish_turn_succeeded(
            turn.turn_id,
            actor_id=actor.id,
            planner_reply="IR generated",
            ir_after=ir_json,
            brief_after=draft_json,
        )
        request.app.state.archive_writer.append(
            session.session_id,
            actor_id=actor.id,
            event_type="turn.clarify_replied",
            payload={
                "turn_id": str(turn.turn_id),
                "round_index": session.clarify_round,
                "ask_field_path": None,
                "options_count": 0,
                "draft_after_sha256": _sha256_text(draft_json),
                "gate_pass": True,
            },
        )
        request.app.state.archive_writer.append(
            session.session_id,
            actor_id=actor.id,
            event_type="turn.succeeded",
            payload={
                "turn_id": str(turn.turn_id),
                "ir_after_sha256": _sha256_text(ir_json),
                "validation_status": "ok",
            },
        )
        return _turn_response(row)
    except Exception as e:  # noqa: BLE001 - service records planner/validation failures
        row = request.app.state.session_store.finish_turn_failed(
            turn.turn_id,
            actor_id=actor.id,
            error_kind=CLIENT_PLANNER_ERROR,
            validation_errors=[CLIENT_PLANNER_ERROR],
            error_correlation_id=_error_correlation_id(),
        )
        _archive_planner_failure(request, session.session_id, actor.id, turn.turn_id, e, row.error_correlation_id)
        return _turn_response(row)


def _should_run_clarify(session: SessionRow, user_message: str) -> bool:
    """仅 self-design 会话进入澄清状态机。
    模板会话已由模板种子写入 IR，不应被二次澄清拦截。
    brief_draft 只作为审计/恢复快照，不再承担路由判定。
    这样避免模板路径和 self-design 路径因 IR/brief 状态混淆。
    """
    if session.latest_ir_json and _looks_like_post_ir_edit(user_message):
        return False
    return session.self_design


def _is_brief_review_confirmation(last_turn: TurnRow | None, user_message: str) -> bool:
    if last_turn is None or last_turn.kind != "brief_review":
        return False
    text = user_message.strip().lower()
    if not text:
        return False
    confirmation_tokens = ("confirm", "confirmed", "确认", "生成", "继续")
    return any(token in text for token in confirmation_tokens)


def _looks_like_post_ir_edit(user_message: str) -> bool:
    parsed = parse_edit_intent(user_message)
    if getattr(parsed, "kind", "") != "mark_unrecognized":
        return True
    return bool(
        re.search(
            r"\b(change|modify|threshold|retry|top[_ -]?k|manual\s+review)\b|改|修改|阈值",
            user_message,
            re.I,
        )
    )


def _stale_turn_reference_response(
    *,
    request: Request,
    actor: Actor,
    session: SessionRow,
    turn: TurnRow,
    user_message: str,
    last_turn: TurnRow | None,
    draft_before: WorkflowBriefDraft | None,
    brief_before_json: str | None,
) -> dict[str, object] | None:
    referenced_turn_id = _referenced_turn_id(user_message)
    if referenced_turn_id is None or last_turn is None or referenced_turn_id == str(last_turn.turn_id):
        return None
    draft_after = _load_draft(last_turn.brief_after) or draft_before
    if last_turn.kind == "brief_review" and draft_after is not None:
        return _finish_brief_review_response(
            request=request,
            actor=actor,
            session=session,
            turn=turn,
            draft=draft_after,
            brief_before_json=brief_before_json,
        )
    if last_turn.kind not in {"clarify", "questionnaire"} or not last_turn.clarify_question:
        return None
    question_payload = json.loads(last_turn.clarify_question)
    return _finish_clarify_response(
        request=request,
        actor=actor,
        session=session,
        turn=turn,
        kind=cast(Literal["clarify", "questionnaire"], last_turn.kind),
        question_payload=question_payload,
        draft_before_json=brief_before_json,
        draft_after=draft_after or WorkflowBriefDraft(title="Self-Design workflow", intent=""),
        clarify_round=session.clarify_round,
    )


def _referenced_turn_id(user_message: str) -> str | None:
    match = re.search(r"\bturn_id=([0-9a-fA-F-]{32,36})\b", user_message)
    if not match:
        return None
    raw = match.group(1)
    try:
        return str(UUID(raw))
    except ValueError:
        return raw


def _load_draft(raw: str | None) -> WorkflowBriefDraft | None:
    if not raw:
        return None
    return WorkflowBriefDraft.model_validate_json(raw)


def _merge_draft(brief: WorkflowBriefDraft | None, patch: dict[str, object]) -> WorkflowBriefDraft:
    data = brief.model_dump(mode="python") if brief else {}
    for key, value in patch.items():
        if value is not None:
            data[key] = _redact_patch_value(value)
    return WorkflowBriefDraft.model_validate(data)


def _redact_patch_value(value: object) -> object:
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, list):
        return [_redact_patch_value(item) for item in value]
    if isinstance(value, dict):
        return {key: _redact_patch_value(item) for key, item in value.items()}
    return value


def _draft_json(draft: WorkflowBriefDraft) -> str:
    redacted = redact_draft(draft)
    return json.dumps(redacted.model_dump(mode="json", exclude_none=True), ensure_ascii=False, sort_keys=True)


def _draft_to_planner_message(draft: WorkflowBriefDraft) -> str:
    return "\n\n".join([
        redact_text(draft.intent or ""),
        "# Workflow brief draft",
        _draft_json(draft),
    ]).strip()


def _pending_field_paths(last_turn: TurnRow | None) -> list[str]:
    if last_turn is None or not last_turn.clarify_question:
        return []
    payload = json.loads(last_turn.clarify_question)
    if "questions" in payload:
        return [str(item["field_path"]) for item in payload["questions"] if "field_path" in item]
    field_path = payload.get("field_path")
    return [str(field_path)] if field_path else []


def _question_text(payload: dict[str, object]) -> str:
    if "questions" in payload:
        return "Please answer the remaining clarification questions."
    return str(payload.get("text") or "Please clarify the workflow requirements.")


def _question_field_path(payload: dict[str, object]) -> str | None:
    if "questions" in payload:
        return "questionnaire"
    value = payload.get("field_path")
    return str(value) if value is not None else None


def _options_count(payload: dict[str, object]) -> int:
    questions = payload.get("questions")
    if isinstance(questions, list):
        total = 0
        for item in questions:
            if isinstance(item, dict):
                options = item.get("options")
                if isinstance(options, list):
                    total += len(options)
        return total
    options = payload.get("options")
    return len(options) if isinstance(options, list) else 0


@router.get("/bindings")
def list_bindings(request: Request, actor: ActorDep) -> list[dict[str, str]]:
    del actor
    binding_dir: Path = request.app.state.settings.binding_dir
    if not binding_dir.exists():
        return []
    rows: list[dict[str, str]] = []
    suffixes = {
        ".dify.yaml": "dify",
        ".hiagent.yaml": "hiagent",
    }
    for path in sorted(binding_dir.glob("*.yaml")):
        for suffix, target in suffixes.items():
            if path.name.endswith(suffix):
                handle = path.name.removesuffix(suffix)
                rows.append({"handle": handle, "target": target, "display_name": handle})
                break
    return sorted(rows, key=lambda row: (row["handle"], row["target"]))


@router.get("/archive/sessions/{session_id}")
def get_archive(
    session_id: UUID,
    request: Request,
    actor: ActorDep,
) -> Response:
    # Actor filter is enforced by session lookup before archive disclosure.
    if request.app.state.session_store.get_session(session_id, actor_id=actor.id) is None:
        raise not_found("session not found")
    return Response(
        content=request.app.state.archive_writer.read_session_text(session_id),
        media_type="application/x-ndjson",
    )


def _compile_artifact(
    ir: IRDocument,
    *,
    target: Literal["hiagent", "dify"],
    mode: Literal["chat", "chatflow"] | None,
    binding_handle: str,
    binding_dir: Path,
) -> tuple[bytes, str, Literal["zip", "yaml"], list[CompileWarning]]:
    if target == "dify":
        text, warnings = compile_dify(ir)
        return text.encode("utf-8"), f"{ir.metadata.name}.yaml", "yaml", warnings
    binding_path = binding_dir / f"{binding_handle}.hiagent.yaml"
    if not binding_path.exists():
        raise bad_request(f"binding not found: {binding_handle}")
    binding = HiagentBinding.load(binding_path)
    bundle, warnings = compile_ir_chatflow(ir, binding) if mode == "chatflow" else compile_ir(ir, binding)
    return bundle.to_zip_bytes(), f"{ir.metadata.name}.zip", "zip", warnings


def _seed_session_from_template(
    request: Request,
    session_id: UUID,
    *,
    actor_id: str,
    template_id: str,
    scope: str | None,
) -> SessionRow:
    catalog = request.app.state.template_catalog
    record = catalog.get(template_id)
    if record is None:
        raise bad_request(f"template not found: {template_id}")
    selected_scope = scope or record.entry.scopes[0]
    if selected_scope not in record.entry.scopes:
        raise bad_request(f"template {template_id} is not available for scope {selected_scope}")
    selected_target = cast(Literal["hiagent", "dify"], record.entry.compile_targets[0])
    request.app.state.session_store.update_session_planning_context(
        session_id,
        actor_id=actor_id,
        target_runtime=selected_target,
        scope=selected_scope,
        self_design=False,
    )
    failures = validate(
        record.ir,
        scope=selected_scope,
        audit_max_retention_days=request.app.state.settings.audit_max_retention_days,
    )
    if failures:
        details = "; ".join(f.detail for f in failures)
        raise bad_request(f"template {template_id} failed validation: {details}")
    ir_json = json.dumps(record.ir, ensure_ascii=False, sort_keys=True)
    turn = request.app.state.session_store.create_turn(
        session_id,
        actor_id=actor_id,
        user_message=f"template:{template_id}",
        ir_before=None,
    )
    row = request.app.state.session_store.finish_turn_succeeded(
        turn.turn_id,
        actor_id=actor_id,
        planner_reply=(
            f"已从模板「{record.entry.name.zh}」初始化 / "
            f"Seeded from template '{record.entry.name.en}'"
        ),
        ir_after=ir_json,
    )
    request.app.state.archive_writer.append(
        session_id,
        actor_id=actor_id,
        event_type="template_seeded",
        payload={"template_id": template_id, "ir_sha": _sha256_text(ir_json), "turn_id": str(row.turn_id)},
    )
    seeded = request.app.state.session_store.get_session(session_id, actor_id=actor_id)
    assert seeded is not None
    return cast(SessionRow, seeded)


def _ensure_template_target_supported(
    request: Request,
    session_id: UUID,
    actor_id: str,
    target: Literal["hiagent", "dify"],
) -> None:
    for turn in request.app.state.session_store.list_turns(session_id, actor_id=actor_id):
        if not turn.user_message.startswith("template:"):
            continue
        template_id = turn.user_message.removeprefix("template:")
        record = request.app.state.template_catalog.get(template_id)
        if record is not None and target not in record.entry.compile_targets:
            raise bad_request(f"template {template_id} does not support compile target {target}")
        return


def _turn_response(row: Any) -> dict[str, object]:
    clarify_question = json.loads(row.clarify_question) if getattr(row, "clarify_question", None) else None
    brief_after = json.loads(row.brief_after) if getattr(row, "brief_after", None) else None
    return {
        "turn_id": str(row.turn_id),
        "status": row.status,
        "planner_reply": row.planner_reply,
        "errors": row.validation_errors,
        "ir_diff": None,
        "kind": getattr(row, "kind", "plan"),
        "clarify_question": clarify_question,
        "brief_after": brief_after,
        "clarify_round": getattr(row, "clarify_round", None),
        "error_correlation_id": getattr(row, "error_correlation_id", None),
    }


def _session_target_runtime(row: SessionRow) -> Literal["hiagent", "dify"]:
    return row.target_runtime or "hiagent"


def _session_scope(row: SessionRow) -> str:
    return row.scope or "ecommerce/kb"


def _session_summary_response(row: SessionRow, request: Request, actor_id: str) -> SessionSummary:
    turns = request.app.state.session_store.list_turns(row.session_id, actor_id=actor_id)
    return SessionSummary(
        session_id=str(row.session_id),
        state=row.state,
        latest_ir_sha256=row.latest_ir_sha256,
        created_at=row.created_at,
        updated_at=row.updated_at,
        display_title=_to_session_display(row, turns, request.app.state.template_catalog),
    )


def _session_detail_response(row: SessionRow, request: Request, actor_id: str) -> SessionDetail:
    artifacts = [
        artifact.model_dump(mode="json")
        for artifact in request.app.state.session_store.list_artifacts(row.session_id, actor_id=actor_id)
    ]
    return SessionDetail(
        session_id=str(row.session_id),
        actor_id=row.actor_id,
        state=row.state,
        latest_ir_json=row.latest_ir_json,
        latest_ir_sha256=row.latest_ir_sha256,
        title=row.title,
        llm_base_url=row.llm_base_url,
        llm_model=row.llm_model,
        llm_key_version=row.llm_key_version,
        created_at=row.created_at,
        updated_at=row.updated_at,
        artifacts=artifacts,
        display_title=_to_session_display(
            row,
            request.app.state.session_store.list_turns(row.session_id, actor_id=actor_id),
            request.app.state.template_catalog,
        ),
    )


def _to_session_display(row: SessionRow, turns: list[TurnRow], catalog: Any) -> str:
    if row.title and row.title.strip():
        return row.title.strip()
    if turns:
        first_message = turns[0].user_message.strip()
        if first_message.startswith("template:"):
            template_id = first_message.removeprefix("template:").strip()
            record = catalog.get(template_id) if catalog is not None else None
            if record is not None:
                return str(record.entry.name.zh or record.entry.name.en)
            return f"Session {str(row.session_id)[:8]}"
        if first_message:
            return first_message[:24]
    return f"Session {str(row.session_id)[:8]}"


def _turn_snapshot(row: Any) -> str | None:
    return cast("str | None", row.ir_after or row.ir_before)


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _rewrite_artifact_path(store: Any, artifact_id: UUID, path: str) -> None:
    with store._connect() as con:  # noqa: SLF001 - internal repair to preserve public store API
        con.execute("UPDATE artifacts SET artifact_path = ? WHERE artifact_id = ?", (path, str(artifact_id)))
