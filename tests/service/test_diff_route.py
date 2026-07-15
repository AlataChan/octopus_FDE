import json
from pathlib import Path

from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from loom.fde_session.brief import ComplianceBoundary, DataSourceRef, TriggerSpec, WorkflowBriefDraft
from loom.fde_session.clarify_engine import ClarifyEngineResult, FakeClarifyEngine
from loom.ir.models import IRDocument
from loom.service.app import create_app
from loom.service.deps import Settings

ROOT = Path(__file__).resolve().parents[2]


def _sample_ir() -> dict:
    return json.loads((ROOT / "examples" / "ir" / "01-ecommerce-customer-faq.json").read_text())


def _complete_draft() -> WorkflowBriefDraft:
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
        target_runtime="hiagent",
        scope="ecommerce/kb",
        known_edits=["Initial build."],
    )


def _client(tmp_path, planner, clarify_engine=None) -> TestClient:
    bindings = tmp_path / "bindings"
    bindings.mkdir()
    (bindings / "test.hiagent.yaml").write_text((ROOT / "tests" / "fixtures" / "test.hiagent.yaml").read_text())
    settings = Settings(
        data_dir=tmp_path / "data",
        app_env="dev",
        fernet_key=Fernet.generate_key().decode(),
        binding_dir=bindings,
    )
    return TestClient(create_app(settings=settings, planner=planner, clarify_engine=clarify_engine))


def test_diff_route_uses_turn_snapshots(tmp_path):
    first = _sample_ir()
    second = json.loads(json.dumps(first))
    second["nodes"][1]["top_k"] = 5
    second["nodes"].append(
        {
            "id": "format_answer",
            "type": "code",
            "language": "python",
            "source": "return {'answer': inputs['answer']}",
            "inputs": {"answer": "${answer.answer}"},
            "rationale": "Format answer payload.",
        }
    )
    second["edges"].append({"from": "answer", "to": "format_answer"})
    calls = iter([IRDocument.model_validate(first), IRDocument.model_validate(second)])

    def planner(**kwargs):
        return next(calls)

    clarify_engine = FakeClarifyEngine([
        ClarifyEngineResult(intent_update=_complete_draft().model_dump(mode="json"), next_action="ready"),
        ClarifyEngineResult(intent_update=_complete_draft().model_dump(mode="json"), next_action="ready"),
    ])
    client = _client(tmp_path, planner, clarify_engine=clarify_engine)
    sid = client.post("/v1/sessions", json={}).json()["session_id"]
    client.patch(
        f"/v1/sessions/{sid}/llm-config",
        json={"api_key": "sk-test", "base_url": "https://api.example.com/v1", "model": "deepseek-v4-flash"},
    )
    review_a = client.post(f"/v1/sessions/{sid}/turns", json={"user_message": "first"}).json()
    assert review_a["kind"] == "brief_review"
    turn_a = client.post(f"/v1/sessions/{sid}/turns", json={"user_message": "确认生成"}).json()
    assert turn_a["kind"] == "plan"
    turn_b = client.post(f"/v1/sessions/{sid}/turns", json={"user_message": "retrieve top_k 5"}).json()
    assert turn_b["kind"] == "plan"

    response = client.get(
        f"/v1/sessions/{sid}/ir/diff",
        params={"from_turn": turn_a["turn_id"], "to_turn": turn_b["turn_id"]},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["from"] == turn_a["turn_id"]
    assert payload["to"] == turn_b["turn_id"]
    assert any(c["kind"] == "added" and c["node_id"] == "format_answer" for c in payload["changes"])
    retrieve = next(c for c in payload["changes"] if c.get("node_id") == "retrieve")
    assert retrieve["fields"] == [{"path": "top_k", "before": 20, "after": 5}]


def test_diff_route_rejects_turns_outside_session(tmp_path):
    ir = IRDocument.model_validate(_sample_ir())
    clarify_engine = FakeClarifyEngine([
        ClarifyEngineResult(intent_update=_complete_draft().model_dump(mode="json"), next_action="ready"),
        ClarifyEngineResult(intent_update=_complete_draft().model_dump(mode="json"), next_action="ready"),
    ])
    client = _client(tmp_path, planner=lambda **kwargs: ir, clarify_engine=clarify_engine)
    sid_a = client.post("/v1/sessions", json={}).json()["session_id"]
    sid_b = client.post("/v1/sessions", json={}).json()["session_id"]
    for sid in [sid_a, sid_b]:
        client.patch(
            f"/v1/sessions/{sid}/llm-config",
            json={"api_key": "sk-test", "base_url": "https://api.example.com/v1", "model": "deepseek-v4-flash"},
        )
    client.post(f"/v1/sessions/{sid_a}/turns", json={"user_message": "a"})
    turn_a = client.post(f"/v1/sessions/{sid_a}/turns", json={"user_message": "确认生成"}).json()
    client.post(f"/v1/sessions/{sid_b}/turns", json={"user_message": "b"})
    turn_b = client.post(f"/v1/sessions/{sid_b}/turns", json={"user_message": "确认生成"}).json()

    response = client.get(
        f"/v1/sessions/{sid_a}/ir/diff",
        params={"from_turn": turn_a["turn_id"], "to_turn": turn_b["turn_id"]},
    )

    assert response.status_code == 404


def test_diff_route_returns_empty_diff_for_turns_without_ir_snapshots(tmp_path):
    clarify_engine = FakeClarifyEngine([
        ClarifyEngineResult(
            question={
                "text": "请补充业务目标。",
                "field_path": "intent_clarification",
                "allow_freeform": True,
                "severity": "block",
            },
            next_action="ask",
        ),
        ClarifyEngineResult(
            question={
                "text": "请选择运行平台。",
                "field_path": "target_runtime",
                "options": [{"label": "HiAgent", "value": "hiagent"}],
                "allow_freeform": False,
                "severity": "block",
            },
            next_action="ask",
        ),
    ])
    client = _client(tmp_path, planner=lambda **_kwargs: IRDocument.model_validate(_sample_ir()), clarify_engine=clarify_engine)
    sid = client.post("/v1/sessions", json={}).json()["session_id"]
    first = client.post(f"/v1/sessions/{sid}/turns", json={"user_message": "我要一个客服 FAQ"}).json()
    second = client.post(f"/v1/sessions/{sid}/turns", json={"user_message": "补充一点"}).json()

    response = client.get(
        f"/v1/sessions/{sid}/ir/diff",
        params={"from_turn": first["turn_id"], "to_turn": second["turn_id"]},
    )

    assert response.status_code == 200
    assert response.json() == {
        "from": first["turn_id"],
        "to": second["turn_id"],
        "changes": [],
        "summary": {"nodes": 0, "edges": 0, "total": 0},
    }
