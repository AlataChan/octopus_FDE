import hashlib
import json
from pathlib import Path

from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from loom.ir.models import IRDocument
from loom.service.app import create_app
from loom.service.deps import Settings

ROOT = Path(__file__).resolve().parents[2]


def _sample_ir() -> IRDocument:
    return IRDocument.model_validate(
        json.loads((ROOT / "examples" / "ir" / "01-ecommerce-customer-faq.json").read_text())
    )


def _client(tmp_path, planner=None) -> TestClient:
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
    return TestClient(create_app(settings=settings, planner=planner))


def test_session_turn_compile_download_archive_and_registry_round_trip(tmp_path):
    ir = _sample_ir()

    def planner(*, user_message: str, **kwargs):
        assert user_message == "build faq"
        assert kwargs["target"] == "hiagent"
        assert kwargs["scope"] == "ecommerce/kb"
        return ir

    client = _client(tmp_path, planner=planner)
    session = client.post("/v1/sessions", json={}).json()
    sid = session["session_id"]

    llm = client.patch(
        f"/v1/sessions/{sid}/llm-config",
        json={"api_key": "sk-secret", "base_url": "https://api.example.com/v1", "model": "deepseek-v4-flash"},
    )
    assert llm.status_code == 200

    turn = client.post(f"/v1/sessions/{sid}/turns", json={"user_message": "build faq"}).json()
    assert turn["status"] == "succeeded"

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


def test_turn_failure_keeps_latest_ir_pointer(tmp_path):
    ir = _sample_ir()
    calls = {"n": 0}

    def planner(*, user_message: str, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            return ir
        raise RuntimeError("planner exploded")

    client = _client(tmp_path, planner=planner)
    sid = client.post("/v1/sessions", json={}).json()["session_id"]
    client.patch(
        f"/v1/sessions/{sid}/llm-config",
        json={"api_key": "sk-secret", "base_url": "https://api.example.com/v1", "model": "deepseek-v4-flash"},
    )
    client.post(f"/v1/sessions/{sid}/turns", json={"user_message": "ok"})
    before_session = client.get(f"/v1/sessions/{sid}").json()
    before = before_session["latest_ir_sha256"]
    assert before_session["state"] == "validated"

    failed = client.post(f"/v1/sessions/{sid}/turns", json={"user_message": "fail"}).json()
    after_session = client.get(f"/v1/sessions/{sid}").json()
    after = after_session["latest_ir_sha256"]
    assert failed["status"] == "failed"
    assert after == before
    assert after_session["state"] == before_session["state"]


def test_artifact_path_traversal_is_not_part_of_api(tmp_path):
    client = _client(tmp_path, planner=lambda **kwargs: _sample_ir())
    sid = client.post("/v1/sessions", json={}).json()["session_id"]
    resp = client.get(f"/v1/sessions/{sid}/artifacts/../../pyproject.toml")
    assert resp.status_code in {404, 422}


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


def test_download_artifact_with_non_ascii_filename(tmp_path):
    """artifact_name 含中文（planner 真实场景）下载不应 500，且 Content-Disposition 须遵循 RFC 5987 双形式。"""
    from urllib.parse import quote

    base_ir = _sample_ir()
    cn_name = "玉柴发动机维修保养咨询"
    cn_metadata = base_ir.metadata.model_copy(update={"name": cn_name})
    cn_ir = base_ir.model_copy(update={"metadata": cn_metadata})

    def planner(**_kwargs):
        return cn_ir

    client = _client(tmp_path, planner=planner)
    sid = client.post("/v1/sessions", json={}).json()["session_id"]
    client.patch(
        f"/v1/sessions/{sid}/llm-config",
        json={"api_key": "sk", "base_url": "https://x/v1", "model": "m"},
    )
    client.post(f"/v1/sessions/{sid}/turns", json={"user_message": "build"})
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
    archive = client.get(f"/v1/archive/sessions/{sid}").text
    assert "template_seeded" in archive


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
