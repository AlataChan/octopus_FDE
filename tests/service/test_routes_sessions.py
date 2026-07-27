import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier, Event

from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from loom.fde_session.brief import (
    ApprovalPoint,
    ComplianceBoundary,
    CredentialBindingRef,
    DataSourceRef,
    InputSpec,
    TriggerSpec,
    WorkflowBriefDraft,
)
from loom.fde_session.clarify_engine import ClarifyEngineResult, FakeClarifyEngine
from loom.ir.models import IRDocument
from loom.planner.client import CallResult
from loom.planner.retry import plan as plan_with_retries
from loom.planner.types import IntentRequest
from loom.service.app import create_app
from loom.service.deps import Settings

ROOT = Path(__file__).resolve().parents[2]


def _sample_ir() -> IRDocument:
    return IRDocument.model_validate(
        json.loads((ROOT / "examples" / "ir" / "01-ecommerce-customer-faq.json").read_text())
    )


def _complete_draft(*, target_runtime: str = "hiagent") -> WorkflowBriefDraft:
    return WorkflowBriefDraft(
        title="FAQ workflow",
        intent="Answer ecommerce FAQ questions from product KB with citations.",
        trigger=TriggerSpec(mode="manual"),
        data_sources=[DataSourceRef(handle="product_kb", kind="kb")],
        success_criteria="Answer with citations.",
        compliance_boundary=ComplianceBoundary(
            pii_class_default="low",
            regulatory_tags=[],
            geographies=["CN"],
        ),
        target_runtime=target_runtime,  # type: ignore[arg-type]
        scope="ecommerce/kb",
        known_edits=["Initial build."],
    )


def _client(tmp_path, planner=None, clarify_engine=None) -> TestClient:
    bindings = tmp_path / "bindings"
    bindings.mkdir()
    (bindings / "test.hiagent.yaml").write_text((ROOT / "tests" / "fixtures" / "test.hiagent.yaml").read_text())
    (bindings / "demo.dify.yaml").write_text("customer: demo\n")
    settings = Settings(
        data_dir=tmp_path / "data",
        app_env="dev",
        fernet_key=Fernet.generate_key().decode(),
        binding_dir=bindings,
    )
    client = TestClient(create_app(settings=settings, planner=planner, clarify_engine=clarify_engine))
    client.app.state.session_store.grant_binding_access(
        tenant_id=settings.instance_id,
        actor_id="single-user",
        binding_handle="test",
    )
    client.app.state.session_store.grant_binding_access(
        tenant_id=settings.instance_id,
        actor_id="single-user",
        binding_handle="demo",
    )
    return client


def test_session_turn_compile_download_archive_and_registry_round_trip(tmp_path):
    ir = _sample_ir()
    calls = {"planner": 0}

    def planner(*, user_message: str, **kwargs):
        calls["planner"] += 1
        assert "Answer ecommerce FAQ questions" in user_message
        assert kwargs["target"] == "hiagent"
        assert kwargs["scope"] == "ecommerce/kb"
        return ir

    clarify_engine = FakeClarifyEngine([
        ClarifyEngineResult(intent_update=_complete_draft().model_dump(mode="json"), next_action="ready"),
    ])
    client = _client(tmp_path, planner=planner, clarify_engine=clarify_engine)
    session = client.post("/v1/sessions", json={}).json()
    sid = session["session_id"]

    llm = client.patch(
        f"/v1/sessions/{sid}/llm-config",
        json={"api_key": "sk-secret", "base_url": "https://api.example.com/v1", "model": "deepseek-v4-flash"},
    )
    assert llm.status_code == 200

    review = client.post(f"/v1/sessions/{sid}/turns", json={"user_message": "build faq"}).json()
    assert review["status"] == "succeeded"
    assert review["kind"] == "brief_review"
    assert review["brief_after"]["target_runtime"] == "hiagent"
    assert calls["planner"] == 0

    turn = client.post(f"/v1/sessions/{sid}/turns", json={"user_message": "确认生成"}).json()
    assert turn["status"] == "succeeded"
    assert turn["kind"] == "plan"
    assert calls["planner"] == 1

    compiled = client.post(
        f"/v1/sessions/{sid}/compile",
        json={"target": "hiagent", "mode": "chatflow", "binding": "test"},
    ).json()
    artifact_id = compiled["artifact_id"]
    assert compiled["sha256"]
    assert compiled["workflow_id"]
    assert compiled["compile_warnings"] == []
    artifacts = client.get(f"/v1/sessions/{sid}/artifacts").json()
    assert artifacts[0]["compile_warnings"] == []

    downloaded = client.get(f"/v1/sessions/{sid}/artifacts/{artifact_id}")
    assert downloaded.status_code == 200
    assert hashlib.sha256(downloaded.content).hexdigest() == compiled["sha256"]

    registry_rows = client.get("/v1/registry/workflows").json()
    assert len(registry_rows) == 1
    assert registry_rows[0]["artifact_sha256"] == compiled["sha256"]
    assert registry_rows[0]["workflow_id"] == compiled["workflow_id"]

    archive = client.get(f"/v1/archive/sessions/{sid}").text
    assert "session.created" in archive
    assert "turn.succeeded" in archive
    assert "compile.produced" in archive
    assert "artifact.downloaded" in archive
    app = client.app
    events = app.state.archive_writer.validate_chain(sid)
    produced = next(e for e in events if e.event_type == "compile.produced")
    artifact_downloaded = next(e for e in events if e.event_type == "artifact.downloaded")
    assert produced.payload["artifact_sha256"] == registry_rows[0]["artifact_sha256"]
    assert artifact_downloaded.occurred_at > produced.occurred_at


def test_self_design_first_turn_returns_clarify_without_planning(tmp_path):
    def planner(**_kwargs):
        raise AssertionError("planner should not be called before clarification completes")

    client = _client(tmp_path, planner=planner)
    sid = client.post("/v1/sessions", json={}).json()["session_id"]
    turn = client.post(f"/v1/sessions/{sid}/turns", json={"user_message": "我要一个客服 FAQ"}).json()

    assert turn["status"] == "succeeded"
    assert turn["kind"] == "clarify"
    assert turn["clarify_question"]["field_path"] == "intent_clarification"
    assert "业务目标" in turn["clarify_question"]["text"]
    archive = client.get(f"/v1/archive/sessions/{sid}").text
    assert "turn.clarify_started" in archive
    assert "turn.clarify_replied" in archive
    assert "我要一个客服 FAQ" not in archive


def test_secret_like_turn_message_is_rejected_before_raw_text_is_persisted(tmp_path):
    client = _client(tmp_path, planner=lambda **_kwargs: _sample_ir())
    sid = client.post("/v1/sessions", json={}).json()["session_id"]
    raw_secret = "Authorization: Bearer abc1234567890abcdef"

    turn = client.post(f"/v1/sessions/{sid}/turns", json={"user_message": raw_secret}).json()

    assert turn["status"] == "succeeded"
    assert turn["kind"] == "clarify"
    assert turn["clarify_question"]["field_path"] == "credentials"
    rows = client.app.state.session_store.list_turns(sid, actor_id="single-user")
    assert rows[-1].user_message == "[REDACTED:potential_secret]"
    assert "Bearer" not in rows[-1].user_message
    assert "abc1234567890abcdef" not in rows[-1].user_message
    archive = client.get(f"/v1/archive/sessions/{sid}").text
    assert "turn.clarify_started" in archive
    assert "Bearer" not in archive
    assert "abc1234567890abcdef" not in archive


def test_planner_payload_block_returns_value_free_422_for_draft_intent(
    tmp_path,
    capsys,
):
    detected_value = "patient@clinic.cn"
    unsafe_draft = _complete_draft().model_copy(
        update={"intent": f"Send follow-ups to {detected_value}."}
    )
    calls = {"planner": 0}

    def planner(**_kwargs):
        calls["planner"] += 1
        return _sample_ir()

    clarify_engine = FakeClarifyEngine([
        ClarifyEngineResult(
            intent_update=unsafe_draft.model_dump(mode="json"),
            next_action="ready",
        ),
    ])
    client = _client(
        tmp_path,
        planner=planner,
        clarify_engine=clarify_engine,
    )
    sid = client.post("/v1/sessions", json={}).json()["session_id"]
    review = client.post(
        f"/v1/sessions/{sid}/turns",
        json={"user_message": "build follow-up workflow"},
    )
    assert review.status_code == 200
    assert review.json()["kind"] == "brief_review"

    response = client.post(
        f"/v1/sessions/{sid}/turns",
        json={"user_message": "confirm"},
    )

    assert response.status_code == 422
    assert response.json()["detail"] == {
        "error": "planner_payload_blocked",
        "field": "intent",
        "category": "email",
    }
    assert detected_value not in response.text
    assert calls["planner"] == 0
    captured = capsys.readouterr()
    assert detected_value not in captured.err
    assert "field=intent" in captured.err
    assert "category=email" in captured.err


def test_planner_payload_block_covers_planner_assisted_edit_path(tmp_path):
    calls = {"planner": 0}

    def planner(**_kwargs):
        calls["planner"] += 1
        return _sample_ir()

    client = _client(tmp_path, planner=planner)
    sid = client.post(
        "/v1/sessions",
        json={"template_id": "knowledge-retrieval-rag", "scope": "ecommerce/kb"},
    ).json()["session_id"]
    detected_value = "patient@clinic.cn"

    response = client.post(
        f"/v1/sessions/{sid}/turns",
        json={
            "user_message": (
                "manual review after retrieve reviewer ops "
                f"contact {detected_value}"
            )
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"] == {
        "error": "planner_payload_blocked",
        "field": "intent",
        "category": "email",
    }
    assert detected_value not in response.text
    assert calls["planner"] == 0


def test_clean_draft_planner_receives_allowlisted_outbound_string(tmp_path):
    captured = {}
    intent = "Answer TCM clinic FAQ from the approved knowledge base."
    draft = _complete_draft().model_copy(
        update={
            "workflow_id": "DROP-WORKFLOW-ID",
            "title": "DROP-TITLE",
            "intent": intent,
            "inputs": [
                InputSpec(
                    name="question",
                    type="string",
                    required=True,
                    description="DROP-INPUT-DESCRIPTION",
                )
            ],
            "tools": ["retrieve_tcm_knowledge"],
            "credentials": [
                CredentialBindingRef(
                    handle="tcm_api",
                    scheme="bearer",
                    allowed_hosts=["api.tcm.example"],
                )
            ],
            "approval_points": [
                ApprovalPoint(
                    stage="clinical_review",
                    reviewer_role="licensed_practitioner",
                )
            ],
            "success_criteria": "DROP-SUCCESS-CRITERIA",
            "intent_clarifications": ["DROP-INTENT-CLARIFICATION"],
            "known_edits": ["DROP-KNOWN-EDIT"],
        }
    )

    def planner(**kwargs):
        captured.update(kwargs)
        return _sample_ir()

    clarify_engine = FakeClarifyEngine([
        ClarifyEngineResult(
            intent_update=draft.model_dump(mode="json"),
            next_action="ready",
        ),
    ])
    client = _client(
        tmp_path,
        planner=planner,
        clarify_engine=clarify_engine,
    )
    sid = client.post("/v1/sessions", json={}).json()["session_id"]
    client.post(
        f"/v1/sessions/{sid}/turns",
        json={"user_message": "build clinic workflow"},
    )

    response = client.post(
        f"/v1/sessions/{sid}/turns",
        json={"user_message": "confirm"},
    )

    assert response.status_code == 200
    assert response.json()["kind"] == "plan"
    outbound = captured["user_message"]
    assert isinstance(outbound, str)
    assert outbound.startswith(intent + "\n\n# Workflow brief draft\n")
    for allowed_value in (
        '"target_runtime": "hiagent"',
        '"scope": "ecommerce/kb"',
        '"handle": "product_kb"',
        '"handle": "tcm_api"',
        '"stage": "clinical_review"',
        '"name": "question"',
        '"tools": ["retrieve_tcm_knowledge"]',
    ):
        assert allowed_value in outbound
    for dropped_value in (
        "DROP-WORKFLOW-ID",
        "DROP-TITLE",
        "DROP-INPUT-DESCRIPTION",
        "DROP-SUCCESS-CRITERIA",
        "DROP-INTENT-CLARIFICATION",
        "DROP-KNOWN-EDIT",
    ):
        assert dropped_value not in outbound


def test_self_design_fourth_turn_emits_questionnaire_when_still_blocked(tmp_path):
    client = _client(tmp_path, planner=lambda **_kwargs: _sample_ir())
    sid = client.post("/v1/sessions", json={}).json()["session_id"]

    first = client.post(f"/v1/sessions/{sid}/turns", json={"user_message": "我要一个客服 FAQ"}).json()
    assert first["kind"] == "clarify"
    second = client.post(f"/v1/sessions/{sid}/turns", json={"user_message": "hiagent"}).json()
    assert second["kind"] == "clarify"
    third = client.post(f"/v1/sessions/{sid}/turns", json={"user_message": "skip"}).json()
    assert third["kind"] == "clarify"
    fourth = client.post(f"/v1/sessions/{sid}/turns", json={"user_message": "skip again"}).json()

    assert fourth["kind"] == "questionnaire"
    assert len(fourth["clarify_question"]["questions"]) >= 1


def test_stale_clarify_turn_id_repeats_current_question_without_merging_answer(tmp_path):
    client = _client(tmp_path, planner=lambda **_kwargs: _sample_ir())
    sid = client.post("/v1/sessions", json={}).json()["session_id"]

    first = client.post(f"/v1/sessions/{sid}/turns", json={"user_message": "我要一个客服 FAQ"}).json()
    assert first["kind"] == "clarify"
    assert first["clarify_question"]["field_path"] == "intent_clarification"
    second = client.post(
        f"/v1/sessions/{sid}/turns",
        json={
            "user_message": (
                "面向跨境电商买家，处理订单取消和物流追踪，查 product_kb，"
                "人工审核高风险回复，成功标准是回答有来源。"
            )
        },
    ).json()
    assert second["kind"] == "clarify"
    assert second["clarify_question"]["field_path"] == "target_runtime"

    stale = client.post(
        f"/v1/sessions/{sid}/turns",
        json={"user_message": f"turn_id={first['turn_id']} hiagent"},
    ).json()

    assert stale["kind"] == "clarify"
    assert stale["clarify_question"]["field_path"] == "target_runtime"
    assert stale["clarify_round"] == second["clarify_round"]
    assert stale["brief_after"].get("target_runtime") is None


def test_ready_engine_without_target_runtime_is_overridden_by_gate(tmp_path):
    draft = _complete_draft().model_copy(update={"target_runtime": None})
    clarify_engine = FakeClarifyEngine([
        ClarifyEngineResult(intent_update=draft.model_dump(mode="json"), next_action="ready"),
    ])
    client = _client(tmp_path, planner=lambda **_kwargs: _sample_ir(), clarify_engine=clarify_engine)
    sid = client.post("/v1/sessions", json={}).json()["session_id"]

    turn = client.post(f"/v1/sessions/{sid}/turns", json={"user_message": "ready"}).json()

    assert turn["kind"] == "clarify"
    assert turn["clarify_question"]["field_path"] == "target_runtime"


def test_scripted_engine_asks_two_rounds_then_reviews_then_confirm_plans(tmp_path):
    ir = _sample_ir()
    calls = {"planner": 0}

    def planner(**_kwargs):
        calls["planner"] += 1
        return ir

    first_patch = WorkflowBriefDraft(
        title="FAQ workflow",
        intent="Answer ecommerce FAQ questions from product KB with citations.",
        target_runtime="hiagent",
        scope="ecommerce/kb",
        compliance_boundary=ComplianceBoundary(
            pii_class_default="low",
            regulatory_tags=[],
            geographies=["CN"],
        ),
    ).model_dump(mode="json")
    second_patch = WorkflowBriefDraft(
        title="FAQ workflow",
        intent="Answer ecommerce FAQ questions from product KB with citations.",
        trigger=TriggerSpec(mode="manual"),
        target_runtime="hiagent",
        scope="ecommerce/kb",
        compliance_boundary=ComplianceBoundary(
            pii_class_default="low",
            regulatory_tags=[],
            geographies=["CN"],
        ),
    ).model_dump(mode="json")
    clarify_engine = FakeClarifyEngine([
        ClarifyEngineResult(intent_update=first_patch, next_action="ask"),
        ClarifyEngineResult(intent_update=second_patch, next_action="ask"),
        ClarifyEngineResult(intent_update=_complete_draft().model_dump(mode="json"), next_action="ready"),
    ])
    client = _client(tmp_path, planner=planner, clarify_engine=clarify_engine)
    sid = client.post("/v1/sessions", json={}).json()["session_id"]

    one = client.post(f"/v1/sessions/{sid}/turns", json={"user_message": "build faq"}).json()
    two = client.post(f"/v1/sessions/{sid}/turns", json={"user_message": "manual"}).json()
    three = client.post(f"/v1/sessions/{sid}/turns", json={"user_message": "ready"}).json()

    assert one["kind"] == "clarify"
    assert two["kind"] == "clarify"
    assert three["kind"] == "brief_review"
    assert calls["planner"] == 0

    confirmed = client.post(f"/v1/sessions/{sid}/turns", json={"user_message": "confirm"}).json()

    assert confirmed["kind"] == "plan"
    assert calls["planner"] == 1


def test_questionnaire_submission_completes_to_brief_review_then_confirm_plans(tmp_path):
    client = _client(tmp_path, planner=lambda **_kwargs: _sample_ir())
    sid = client.post("/v1/sessions", json={}).json()["session_id"]

    client.post(f"/v1/sessions/{sid}/turns", json={"user_message": "我要一个客服 FAQ"})
    client.post(f"/v1/sessions/{sid}/turns", json={"user_message": "hiagent"})
    client.post(f"/v1/sessions/{sid}/turns", json={"user_message": "skip"})
    questionnaire = client.post(f"/v1/sessions/{sid}/turns", json={"user_message": "skip again"}).json()
    assert questionnaire["kind"] == "questionnaire"

    review = client.post(
        f"/v1/sessions/{sid}/turns",
        json={
            "user_message": (
                "scope=ecommerce/kb; compliance_boundary=low; trigger=manual; "
                "data_sources=product_kb; success_criteria=Answer with citations."
            )
        },
    ).json()

    assert review["kind"] == "brief_review"

    planned = client.post(f"/v1/sessions/{sid}/turns", json={"user_message": "继续"}).json()

    assert planned["kind"] == "plan"
    assert planned["status"] == "succeeded"


def test_self_design_post_ir_edit_patches_existing_ir_without_planner(tmp_path):
    calls = {"planner": 0}

    def planner(**_kwargs):
        calls["planner"] += 1
        return _sample_ir()

    client = _client(tmp_path, planner=planner)
    sid = client.post("/v1/sessions", json={}).json()["session_id"]
    ir_json = json.dumps(_sample_ir().model_dump(by_alias=True, exclude_none=True), ensure_ascii=False)
    client.app.state.session_store.update_latest_ir(sid, actor_id="single-user", ir_json=ir_json)

    turn = client.post(
        f"/v1/sessions/{sid}/turns",
        json={"user_message": "retriever top_k 8"},
    ).json()

    assert turn["kind"] == "plan"
    assert turn["status"] == "succeeded"
    assert turn["clarify_question"] is None
    assert calls["planner"] == 0
    updated = client.get(f"/v1/sessions/{sid}/ir").json()["ir"]
    assert len(updated["nodes"]) == len(_sample_ir().nodes)
    assert next(node for node in updated["nodes"] if node["id"] == "retrieve")["top_k"] == 8


def test_existing_ir_planner_edit_rejects_changes_outside_declared_scope(tmp_path):
    received_context = {}

    def planner(**kwargs):
        received_context.update(kwargs["extra_context"])
        ir = _sample_ir()
        metadata = ir.metadata.model_copy(update={"name": "unauthorized rewrite"})
        return ir.model_copy(update={"metadata": metadata})

    client = _client(tmp_path, planner=planner)
    sid = client.post(
        "/v1/sessions",
        json={"template_id": "knowledge-retrieval-rag", "scope": "ecommerce/kb"},
    ).json()["session_id"]
    before = client.get(f"/v1/sessions/{sid}").json()["latest_ir_sha256"]

    response = client.post(
        f"/v1/sessions/{sid}/turns",
        json={"user_message": "manual review after retrieve reviewer ops"},
    )

    assert response.status_code == 400
    assert "declared edit scope" in response.text
    assert client.get(f"/v1/sessions/{sid}").json()["latest_ir_sha256"] == before
    assert received_context["base_ir_sha256"] == before
    assert received_context["parsed_edit"]["kind"] == "add_manual_review_gate"
    assert received_context["workflow_brief"] is None
    assert received_context["allowed_change_fields"] == [
        "nodes.manual_review_after_retrieve",
        "edges",
    ]


def test_manual_review_edit_rejects_unrelated_edge_rewrite(tmp_path):
    def planner(**kwargs):
        raw = json.loads(json.dumps(kwargs["extra_context"]["current_ir"]))
        gate_id = "manual_review_after_retrieve"
        raw["nodes"].append(
            {
                "id": gate_id,
                "type": "code",
                "language": "python",
                "source": "raise RuntimeError('manual_review_required')",
                "rationale": "Blocking manual review gate requiring approval from ops.",
            }
        )
        outgoing = next(edge for edge in raw["edges"] if edge["from"] == "retrieve")
        raw["edges"].remove(outgoing)
        raw["edges"].extend(
            [
                {"from": "retrieve", "to": gate_id},
                {"from": gate_id, "to": outgoing["to"]},
            ]
        )
        next(edge for edge in raw["edges"] if edge["from"] == "start")["data"] = False
        return IRDocument.model_validate(raw)

    client = _client(tmp_path, planner=planner)
    sid = client.post(
        "/v1/sessions",
        json={"template_id": "knowledge-retrieval-rag", "scope": "ecommerce/kb"},
    ).json()["session_id"]
    before = client.get(f"/v1/sessions/{sid}").json()["latest_ir_sha256"]

    response = client.post(
        f"/v1/sessions/{sid}/turns",
        json={"user_message": "manual review after retrieve reviewer ops"},
    )

    assert response.status_code == 400
    assert "declared edit scope" in response.text
    assert client.get(f"/v1/sessions/{sid}").json()["latest_ir_sha256"] == before


def test_planner_retry_threads_extra_context_through_every_attempt():
    good = _sample_ir().model_dump(by_alias=True, exclude_none=True)
    bad = json.loads(json.dumps(good))
    del bad["nodes"][1]["rationale"]

    class FakeClient:
        def __init__(self):
            self.intents = []
            self.outputs = iter([bad, good])

        def call(self, **kwargs):
            self.intents.append(kwargs["intent"])
            return CallResult(
                ir_text=json.dumps(next(self.outputs)),
                cost_usd=0.0,
                latency_s=0.0,
            )

    fake = FakeClient()
    context = {
        "base_ir_sha256": "abc123",
        "allowed_change_fields": ["nodes.retrieve.top_k"],
        "current_ir": {"nodes": [{"id": "retrieve", "top_k": 20}]},
    }

    result = plan_with_retries(
        IntentRequest(
            intent="set retrieve top_k 8",
            scope="ecommerce/kb",
            max_retries=1,
            extra_context=context,
        ),
        client=fake,
    )

    assert result.ok
    assert len(fake.intents) == 2
    assert all("# Existing workflow context" in intent for intent in fake.intents)
    assert all('"base_ir_sha256": "abc123"' in intent for intent in fake.intents)


def test_turn_failure_keeps_latest_ir_pointer(tmp_path):
    ir = _sample_ir()
    calls = {"n": 0}

    def planner(*, user_message: str, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            return ir
        raise RuntimeError("planner exploded")

    clarify_engine = FakeClarifyEngine([
        ClarifyEngineResult(intent_update=_complete_draft().model_dump(mode="json"), next_action="ready"),
        ClarifyEngineResult(intent_update=_complete_draft().model_dump(mode="json"), next_action="ready"),
    ])
    client = _client(tmp_path, planner=planner, clarify_engine=clarify_engine)
    sid = client.post("/v1/sessions", json={}).json()["session_id"]
    client.patch(
        f"/v1/sessions/{sid}/llm-config",
        json={"api_key": "sk-secret", "base_url": "https://api.example.com/v1", "model": "deepseek-v4-flash"},
    )
    client.post(f"/v1/sessions/{sid}/turns", json={"user_message": "ok"})
    client.post(f"/v1/sessions/{sid}/turns", json={"user_message": "确认"})
    before_session = client.get(f"/v1/sessions/{sid}").json()
    before = before_session["latest_ir_sha256"]
    assert before_session["state"] == "validated"

    failed = client.post(
        f"/v1/sessions/{sid}/turns",
        json={"user_message": "manual review after retrieve reviewer ops"},
    ).json()
    after_session = client.get(f"/v1/sessions/{sid}").json()
    after = after_session["latest_ir_sha256"]
    assert failed["status"] == "failed"
    assert after == before
    assert after_session["state"] == before_session["state"]


def test_planner_exception_is_not_reflected_to_client_db_or_logs(tmp_path, capsys):
    secret_fragments = [
        "https://example.com/secret?token=xyz",
        "Authorization: Bearer top-secret-token",
        "-----BEGIN PRIVATE KEY-----",
    ]

    def planner(**_kwargs):
        raise RuntimeError("boom " + " ".join(secret_fragments))

    clarify_engine = FakeClarifyEngine([
        ClarifyEngineResult(intent_update=_complete_draft().model_dump(mode="json"), next_action="ready"),
    ])
    client = _client(tmp_path, planner=planner, clarify_engine=clarify_engine)
    sid = client.post("/v1/sessions", json={}).json()["session_id"]

    client.post(f"/v1/sessions/{sid}/turns", json={"user_message": "build"})
    turn = client.post(f"/v1/sessions/{sid}/turns", json={"user_message": "confirm"}).json()

    assert turn["status"] == "failed"
    assert turn["errors"] == ["planner_error"]
    assert turn["error_correlation_id"]
    assert "example.com" not in json.dumps(turn)
    assert "token=xyz" not in json.dumps(turn)
    rows = client.app.state.session_store.list_turns(sid, actor_id="single-user")
    assert rows[-1].validation_errors == ["planner_error"]
    assert rows[-1].error_correlation_id == turn["error_correlation_id"]
    stored = json.dumps(rows[-1].model_dump(mode="json"))
    assert "example.com" not in stored
    assert "token=xyz" not in stored
    archive = client.get(f"/v1/archive/sessions/{sid}").text
    assert "error_message_sha256" in archive
    assert rows[-1].error_correlation_id in archive
    assert "example.com" not in archive
    assert "token=xyz" not in archive
    captured = capsys.readouterr()
    for secret in secret_fragments:
        assert secret not in captured.err
    assert "error_code=planner_error" in captured.err
    assert "error_type=RuntimeError" in captured.err


def test_artifact_path_traversal_is_not_part_of_api(tmp_path):
    client = _client(tmp_path, planner=lambda **kwargs: _sample_ir())
    sid = client.post("/v1/sessions", json={}).json()["session_id"]
    resp = client.get(f"/v1/sessions/{sid}/artifacts/../../pyproject.toml")
    assert resp.status_code in {404, 422}


def test_compile_binding_rejects_path_traversal(tmp_path):
    client = _client(tmp_path)
    sid = client.post(
        "/v1/sessions",
        json={"template_id": "knowledge-retrieval-rag", "scope": "ecommerce/kb"},
    ).json()["session_id"]
    outside = tmp_path / "outside.hiagent.yaml"
    outside.write_text((ROOT / "tests" / "fixtures" / "test.hiagent.yaml").read_text())

    response = client.post(
        f"/v1/sessions/{sid}/compile",
        json={"target": "hiagent", "mode": "chatflow", "binding": "../outside"},
    )

    assert response.status_code in {400, 422}
    assert "binding" in response.text.lower()
    assert client.get(f"/v1/sessions/{sid}/artifacts").json() == []


def test_compile_binding_rejects_symlink(tmp_path):
    client = _client(tmp_path)
    sid = client.post(
        "/v1/sessions",
        json={"template_id": "knowledge-retrieval-rag", "scope": "ecommerce/kb"},
    ).json()["session_id"]
    outside = tmp_path / "outside.hiagent.yaml"
    outside.write_text((ROOT / "tests" / "fixtures" / "test.hiagent.yaml").read_text())
    (client.app.state.settings.binding_dir / "linked.hiagent.yaml").symlink_to(outside)

    response = client.post(
        f"/v1/sessions/{sid}/compile",
        json={"target": "hiagent", "mode": "chatflow", "binding": "linked"},
    )

    assert response.status_code == 400
    assert "binding" in response.text.lower()
    assert client.get(f"/v1/sessions/{sid}/artifacts").json() == []


def test_concurrent_turns_return_conflict_instead_of_losing_update(tmp_path):
    barrier = Barrier(2)

    def planner(*, extra_context: dict, **_kwargs):
        barrier.wait(timeout=5)
        raw = json.loads(json.dumps(extra_context["current_ir"]))
        contract = extra_context["manual_review_gate_contract"]
        review_id = contract["gate_id"]
        raw["nodes"].append(contract["gate_node"])
        original_edge = next(
            edge for edge in raw["edges"] if edge["from"] == contract["after_node_id"]
        )
        raw["edges"].remove(original_edge)
        raw["edges"].extend(
            [
                {"from": original_edge["from"], "to": review_id},
                {"from": review_id, "to": original_edge["to"]},
            ]
        )
        return IRDocument.model_validate(raw)

    client = _client(tmp_path, planner=planner)
    sid = client.post(
        "/v1/sessions",
        json={"template_id": "knowledge-retrieval-rag", "scope": "ecommerce/kb"},
    ).json()["session_id"]

    def submit(message: str):
        return client.post(f"/v1/sessions/{sid}/turns", json={"user_message": message})

    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(
            pool.map(
                submit,
                [
                    "manual review after retrieve reviewer alpha",
                    "manual review after retrieve reviewer beta",
                ],
            )
        )

    assert sorted(response.status_code for response in responses) == [200, 409]
    turns = client.app.state.session_store.list_turns(sid, actor_id="single-user")
    assert sum(turn.status == "succeeded" for turn in turns[-2:]) == 1
    assert sum(turn.status == "failed" for turn in turns[-2:]) == 1


def test_turn_creation_rejects_session_changed_after_route_read(tmp_path):
    client = _client(tmp_path, planner=lambda **_kwargs: _sample_ir())
    sid = client.post(
        "/v1/sessions",
        json={"template_id": "knowledge-retrieval-rag", "scope": "ecommerce/kb"},
    ).json()["session_id"]
    store = client.app.state.session_store
    original_create_turn = store.create_turn
    route_reached_create = Event()
    allow_create = Event()

    def delayed_create_turn(*args, **kwargs):
        route_reached_create.set()
        assert allow_create.wait(timeout=5)
        return original_create_turn(*args, **kwargs)

    store.create_turn = delayed_create_turn
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(
            client.post,
            f"/v1/sessions/{sid}/turns",
            json={"user_message": "retrieve top_k 8"},
        )
        assert route_reached_create.wait(timeout=5)
        current = store.get_session(sid, actor_id="single-user")
        assert current is not None and current.latest_ir_json is not None
        replacement = json.loads(current.latest_ir_json)
        next(node for node in replacement["nodes"] if node["id"] == "retrieve")["top_k"] = 6
        replacement_json = json.dumps(replacement, ensure_ascii=False, sort_keys=True)
        store.update_latest_ir(sid, actor_id="single-user", ir_json=replacement_json)
        allow_create.set()
        response = future.result(timeout=10)

    assert response.status_code == 409
    latest = client.get(f"/v1/sessions/{sid}/ir").json()["ir"]
    assert next(node for node in latest["nodes"] if node["id"] == "retrieve")["top_k"] == 6


def test_compile_rejects_init_session(tmp_path):
    client = _client(tmp_path)
    sid = client.post("/v1/sessions", json={}).json()["session_id"]
    resp = client.post(
        f"/v1/sessions/{sid}/compile",
        json={"target": "dify", "binding": "demo"},
    )
    assert resp.status_code == 409


def test_bindings_route_returns_handles_not_raw_yaml(tmp_path):
    client = _client(tmp_path)
    rows = client.get("/v1/bindings").json()
    assert rows == [
        {"handle": "demo", "target": "dify", "display_name": "demo"},
        {"handle": "test", "target": "hiagent", "display_name": "test"},
    ]
    assert "workspace_id" not in rows[0]


def test_binding_catalog_and_compile_are_actor_scoped(tmp_path):
    client = _client(tmp_path)
    headers = {"X-Actor-Id": "other-actor"}
    assert client.get("/v1/bindings", headers=headers).json() == []
    sid = client.post(
        "/v1/sessions",
        headers=headers,
        json={"template_id": "knowledge-retrieval-rag", "scope": "ecommerce/kb"},
    ).json()["session_id"]

    response = client.post(
        f"/v1/sessions/{sid}/compile",
        headers=headers,
        json={"target": "dify", "binding": "demo"},
    )

    assert response.status_code == 400
    assert "binding" in response.text.lower()


def test_download_artifact_with_non_ascii_filename(tmp_path):
    """artifact_name 含中文（planner 真实场景）下载不应 500，且 Content-Disposition 须遵循 RFC 5987 双形式。"""
    from urllib.parse import quote

    base_ir = _sample_ir()
    cn_name = "玉柴发动机维修保养咨询"
    cn_metadata = base_ir.metadata.model_copy(update={"name": cn_name})
    cn_ir = base_ir.model_copy(update={"metadata": cn_metadata})

    def planner(**_kwargs):
        return cn_ir

    clarify_engine = FakeClarifyEngine([
        ClarifyEngineResult(intent_update=_complete_draft().model_dump(mode="json"), next_action="ready"),
    ])
    client = _client(tmp_path, planner=planner, clarify_engine=clarify_engine)
    sid = client.post("/v1/sessions", json={}).json()["session_id"]
    client.patch(
        f"/v1/sessions/{sid}/llm-config",
        json={"api_key": "sk", "base_url": "https://x/v1", "model": "m"},
    )
    client.post(f"/v1/sessions/{sid}/turns", json={"user_message": "build"})
    client.post(f"/v1/sessions/{sid}/turns", json={"user_message": "确认"})
    compiled = client.post(
        f"/v1/sessions/{sid}/compile",
        json={"target": "dify", "binding": "demo"},
    ).json()

    resp = client.get(f"/v1/sessions/{sid}/artifacts/{compiled['artifact_id']}")
    assert resp.status_code == 200
    disposition = resp.headers["content-disposition"]
    assert 'filename="' in disposition  # ASCII fallback exists
    assert "filename*=UTF-8''" in disposition  # RFC 5987 form exists
    assert quote(f"{cn_name}.yaml", safe="") in disposition  # CN name percent-encoded
    # 全 ASCII 字符在 fallback 中没有中文残留
    fallback_start = disposition.index('filename="') + len('filename="')
    fallback_end = disposition.index('"', fallback_start)
    fallback = disposition[fallback_start:fallback_end]
    fallback.encode("ascii")  # 不抛即通过


def test_create_session_from_template_seeds_validated_ir_and_sentinel_turn(tmp_path):
    client = _client(tmp_path)
    created = client.post(
        "/v1/sessions",
        json={"template_id": "knowledge-retrieval-rag", "scope": "ecommerce/kb"},
    ).json()
    sid = created["session_id"]

    assert created["state"] == "validated"
    ir = client.get(f"/v1/sessions/{sid}/ir").json()
    assert ir["ir"]["ir_version"] == "0.4"
    turns = client.app.state.session_store.list_turns(sid, actor_id="single-user")
    assert turns[0].user_message == "template:knowledge-retrieval-rag"
    assert "Seeded from template" in (turns[0].planner_reply or "")
    row = client.app.state.session_store.get_session(sid, actor_id="single-user")
    assert row is not None
    assert row.target_runtime == "hiagent"
    assert row.scope == "ecommerce/kb"
    assert row.self_design is False
    archive = client.get(f"/v1/archive/sessions/{sid}").text
    assert "template_seeded" in archive


def test_template_session_unrecognized_follow_up_is_rejected_without_planner(tmp_path):
    calls = {"planner": 0}

    def planner(**_kwargs):
        calls["planner"] += 1
        return _sample_ir()

    client = _client(tmp_path, planner=planner)
    sid = client.post(
        "/v1/sessions",
        json={"template_id": "knowledge-retrieval-rag", "scope": "ecommerce/kb"},
    ).json()["session_id"]

    response = client.post(f"/v1/sessions/{sid}/turns", json={"user_message": "adjust it"})

    assert response.status_code == 400
    assert "not recognized" in response.text
    assert calls["planner"] == 0


def test_blank_session_is_marked_self_design_and_enters_clarify(tmp_path):
    client = _client(tmp_path, planner=lambda **_kwargs: _sample_ir())
    sid = client.post("/v1/sessions", json={}).json()["session_id"]
    row = client.app.state.session_store.get_session(sid, actor_id="single-user")
    assert row is not None
    assert row.self_design is True

    turn = client.post(f"/v1/sessions/{sid}/turns", json={"user_message": "build faq"}).json()

    assert turn["kind"] == "clarify"


def test_post_sessions_ignores_unknown_extra_actor_field(tmp_path):
    client = _client(tmp_path)
    created = client.post(
        "/v1/sessions",
        headers={"X-Actor-Id": "header-actor"},
        json={"actor": "evil"},
    ).json()

    assert client.app.state.session_store.get_session(created["session_id"], actor_id="header-actor") is not None
    assert client.app.state.session_store.get_session(created["session_id"], actor_id="evil") is None


def test_hiagent_only_template_rejects_dify_compile(tmp_path):
    client = _client(tmp_path)
    created = client.post(
        "/v1/sessions",
        json={"template_id": "tool-using-decision", "scope": "ecommerce/kb"},
    ).json()
    resp = client.post(
        f"/v1/sessions/{created['session_id']}/compile",
        json={"target": "dify", "binding": "demo"},
    )
    assert resp.status_code == 400
    assert "does not support compile target dify" in resp.text


def test_display_title_uses_user_title_when_set(tmp_path):
    client = _client(tmp_path)
    sid = client.post("/v1/sessions", json={}).json()["session_id"]

    patched = client.patch(f"/v1/sessions/{sid}", json={"title": "  我的流程  "})
    assert patched.status_code == 200
    assert patched.json()["title"] == "我的流程"
    assert patched.json()["display_title"] == "我的流程"

    detail = client.get(f"/v1/sessions/{sid}").json()
    assert detail["title"] == "我的流程"
    assert detail["display_title"] == "我的流程"
    listed = client.get("/v1/sessions").json()
    assert listed[0]["display_title"] == "我的流程"


def test_display_title_falls_back_to_template_name_for_seeded_session(tmp_path):
    client = _client(tmp_path)
    created = client.post(
        "/v1/sessions",
        json={"template_id": "knowledge-retrieval-rag", "scope": "ecommerce/kb"},
    ).json()
    sid = created["session_id"]

    detail = client.get(f"/v1/sessions/{sid}").json()
    assert detail["display_title"] == "知识检索（RAG）"
    listed = client.get("/v1/sessions").json()
    assert listed[0]["display_title"] == "知识检索（RAG）"


def test_display_title_falls_back_to_first_user_message_truncated(tmp_path):
    client = _client(tmp_path)
    sid = client.post("/v1/sessions", json={}).json()["session_id"]
    message = "  这是一个很长的用户消息用于测试标题截断🙂继续很多字  "
    client.app.state.session_store.create_turn(
        sid,
        actor_id="single-user",
        user_message=message,
        ir_before=None,
    )

    expected = message.strip()[:24]
    detail = client.get(f"/v1/sessions/{sid}").json()
    assert detail["display_title"] == expected


def test_display_title_falls_back_to_short_id(tmp_path):
    client = _client(tmp_path)
    sid = client.post("/v1/sessions", json={}).json()["session_id"]

    detail = client.get(f"/v1/sessions/{sid}").json()
    assert detail["display_title"] == f"Session {sid[:8]}"
    listed = client.get("/v1/sessions").json()
    assert listed[0]["display_title"] == f"Session {sid[:8]}"


def test_patch_session_title_persists_and_appears_in_display_title(tmp_path):
    client = _client(tmp_path)
    sid = client.post("/v1/sessions", json={}).json()["session_id"]

    resp = client.patch(f"/v1/sessions/{sid}", json={"title": "  TCM triage flow  "})

    assert resp.status_code == 200
    payload = resp.json()
    assert payload["title"] == "TCM triage flow"
    assert payload["display_title"] == "TCM triage flow"
    detail = client.get(f"/v1/sessions/{sid}").json()
    assert detail["title"] == "TCM triage flow"
    assert detail["display_title"] == "TCM triage flow"


def test_patch_session_title_null_clears_to_derivation(tmp_path):
    client = _client(tmp_path)
    sid = client.post("/v1/sessions", json={}).json()["session_id"]
    client.app.state.session_store.create_turn(
        sid,
        actor_id="single-user",
        user_message="derive from this message",
        ir_before=None,
    )
    assert client.patch(f"/v1/sessions/{sid}", json={"title": "custom"}).status_code == 200

    resp = client.patch(f"/v1/sessions/{sid}", json={"title": None})

    assert resp.status_code == 200
    payload = resp.json()
    assert payload["title"] is None
    assert payload["display_title"] == "derive from this message"


def test_patch_session_title_rejects_too_long(tmp_path):
    client = _client(tmp_path)
    sid = client.post("/v1/sessions", json={}).json()["session_id"]

    resp = client.patch(f"/v1/sessions/{sid}", json={"title": "x" * 81})

    assert resp.status_code == 422


def test_patch_session_title_rejects_control_characters(tmp_path):
    client = _client(tmp_path)
    sid = client.post("/v1/sessions", json={}).json()["session_id"]

    assert client.patch(f"/v1/sessions/{sid}", json={"title": "bad\nname"}).status_code == 422
    assert client.patch(f"/v1/sessions/{sid}", json={"title": "<b>bad</b>"}).status_code == 422


def test_delete_session_removes_it_from_history(tmp_path):
    client = _client(tmp_path)
    sid = client.post("/v1/sessions", json={}).json()["session_id"]
    client.app.state.session_store.create_turn(
        sid,
        actor_id="single-user",
        user_message="temporary test session",
        ir_before=None,
    )

    response = client.delete(f"/v1/sessions/{sid}")

    assert response.status_code == 204
    assert client.get(f"/v1/sessions/{sid}").status_code == 404
    assert all(row["session_id"] != sid for row in client.get("/v1/sessions").json())
    assert client.app.state.session_store.list_turns(sid, actor_id="single-user") == []
    assert "session.deleted" in client.app.state.archive_writer.read_session_text(sid)


def test_delete_session_returns_not_found_for_missing_session(tmp_path):
    client = _client(tmp_path)

    response = client.delete("/v1/sessions/00000000-0000-0000-0000-000000000000")

    assert response.status_code == 404
