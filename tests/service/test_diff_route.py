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
    turn_a = client.post(f"/v1/sessions/{sid}/turns", json={"user_message": "first"}).json()
    turn_b = client.post(f"/v1/sessions/{sid}/turns", json={"user_message": "second"}).json()

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
    client = _client(tmp_path, planner=lambda **kwargs: ir)
    sid_a = client.post("/v1/sessions", json={}).json()["session_id"]
    sid_b = client.post("/v1/sessions", json={}).json()["session_id"]
    for sid in [sid_a, sid_b]:
        client.patch(
            f"/v1/sessions/{sid}/llm-config",
            json={"api_key": "sk-test", "base_url": "https://api.example.com/v1", "model": "deepseek-v4-flash"},
        )
    turn_a = client.post(f"/v1/sessions/{sid_a}/turns", json={"user_message": "a"}).json()
    turn_b = client.post(f"/v1/sessions/{sid_b}/turns", json={"user_message": "b"}).json()

    response = client.get(
        f"/v1/sessions/{sid_a}/ir/diff",
        params={"from_turn": turn_a["turn_id"], "to_turn": turn_b["turn_id"]},
    )

    assert response.status_code == 404
