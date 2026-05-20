"""Session, turn, compile, artifact, binding, and archive routes."""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from pathlib import Path
from typing import Annotated, Any, Literal, cast
from urllib.parse import quote
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, Field

from loom.diff.ir_diff import diff_ir
from loom.ir.canonicalize import canonical_ir_hash
from loom.ir.models import IRDocument
from loom.registry.models import WorkflowRecord
from loom.runtimes.dify.v1_14.compiler import compile_ir as compile_dify
from loom.runtimes.hiagent.binding import HiagentBinding
from loom.runtimes.hiagent.v2_6.compiler import compile_ir, compile_ir_chatflow
from loom.runtimes.warnings import CompileWarning
from loom.service.deps import Actor, get_actor
from loom.service.errors import bad_request, conflict, not_found
from loom.validator.validate import validate

router = APIRouter(prefix="/v1")
ActorDep = Annotated[Actor, Depends(get_actor)]


class CreateSessionRequest(BaseModel):
    actor: str | None = None


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
def list_sessions(request: Request, actor: ActorDep) -> list[dict[str, object]]:
    return [
        {
            "session_id": str(row.session_id),
            "state": row.state,
            "latest_ir_sha256": row.latest_ir_sha256,
            "created_at": row.created_at.isoformat(),
            "updated_at": row.updated_at.isoformat(),
        }
        for row in request.app.state.session_store.list_sessions(actor_id=actor.id)
    ]


@router.post("/sessions")
def create_session(
    body: CreateSessionRequest,
    request: Request,
    actor: ActorDep,
) -> dict[str, object]:
    actor_id = body.actor or actor.id
    session = request.app.state.session_store.create_session(actor_id=actor_id)
    request.app.state.archive_writer.append(
        session.session_id,
        actor_id=actor_id,
        event_type="session.created",
        payload={"actor_id": actor_id},
    )
    return {"session_id": str(session.session_id), "state": session.state}


@router.get("/sessions/{session_id}")
def get_session(
    session_id: UUID,
    request: Request,
    actor: ActorDep,
) -> dict[str, object]:
    session = request.app.state.session_store.get_session(session_id, actor_id=actor.id)
    if session is None:
        raise not_found("session not found")
    return {
        **session.model_dump(mode="json", exclude={"llm_api_key_encrypted"}),
        "artifacts": [
            artifact.model_dump(mode="json")
            for artifact in request.app.state.session_store.list_artifacts(session_id, actor_id=actor.id)
        ],
    }


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
    turn = store.create_turn(
        session_id,
        actor_id=actor.id,
        user_message=body.user_message,
        ir_before=session.latest_ir_json,
    )
    request.app.state.archive_writer.append(
        session_id,
        actor_id=actor.id,
        event_type="turn.started",
        payload={"turn_id": str(turn.turn_id), "user_message_sha256": _sha256_text(body.user_message)},
    )
    try:
        ir = request.app.state.planner(
            user_message=body.user_message,
            session=session,
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
            scope="ecommerce/kb",
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
            error_kind="planner_error",
            validation_errors=[str(e)],
        )
        request.app.state.archive_writer.append(
            session_id,
            actor_id=actor.id,
            event_type="turn.failed",
            payload={"turn_id": str(turn.turn_id), "error_kind": "planner_error"},
        )
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
            scope="ecommerce/kb",
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
    if not session.latest_ir_json:
        raise conflict("session has no accepted IR")
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


def _turn_response(row: Any) -> dict[str, object]:
    return {
        "turn_id": str(row.turn_id),
        "status": row.status,
        "planner_reply": row.planner_reply,
        "errors": row.validation_errors,
        "ir_diff": None,
    }


def _turn_snapshot(row: Any) -> str | None:
    return cast("str | None", row.ir_after or row.ir_before)


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _rewrite_artifact_path(store: Any, artifact_id: UUID, path: str) -> None:
    with store._connect() as con:  # noqa: SLF001 - internal repair to preserve public store API
        con.execute("UPDATE artifacts SET artifact_path = ? WHERE artifact_id = ?", (path, str(artifact_id)))
