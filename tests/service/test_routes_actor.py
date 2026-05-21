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


def test_get_actor_llm_config_returns_200_with_has_key_false_when_absent(tmp_path):
    client = _client(tmp_path)
    response = client.get("/v1/actor/llm-config")

    assert response.status_code == 200
    assert response.json() == {
        "provider": None,
        "base_url": None,
        "model": None,
        "has_key": False,
        "updated_at": None,
    }


def test_get_actor_llm_config_never_leaks_key_material(tmp_path):
    client = _client(tmp_path)
    client.put(
        "/v1/actor/llm-config",
        json={
            "provider": "deepseek",
            "base_url": "https://api.deepseek.com/v1",
            "model": "deepseek-chat",
            "api_key": "sk-secret",
        },
    )

    response = client.get("/v1/actor/llm-config")
    payload = response.json()

    assert response.status_code == 200
    assert set(payload) == {"provider", "base_url", "model", "has_key", "updated_at"}
    assert [key for key in payload if "key" in key and key != "has_key"] == []
    assert "sk-secret" not in response.text
    assert payload["has_key"] is True


def test_put_actor_llm_config_initial_without_key_rejects(tmp_path):
    client = _client(tmp_path)
    response = client.put(
        "/v1/actor/llm-config",
        json={
            "provider": "deepseek",
            "base_url": "https://api.deepseek.com/v1",
            "model": "deepseek-chat",
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"]["error"] == "api_key_required_for_initial_setup"


def test_put_actor_llm_config_without_api_key_preserves_existing(tmp_path):
    client = _client(tmp_path)
    client.put(
        "/v1/actor/llm-config",
        json={
            "provider": "deepseek",
            "base_url": "https://api.deepseek.com/v1",
            "model": "deepseek-chat",
            "api_key": "sk-secret",
        },
    )
    store = client.app.state.session_store
    before = store.get_actor_llm_config(actor_id="single-user")
    assert before is not None

    response = client.put(
        "/v1/actor/llm-config",
        json={
            "provider": "deepseek",
            "base_url": "https://api.deepseek.com/v1",
            "model": "deepseek-reasoner",
        },
    )
    after = store.get_actor_llm_config(actor_id="single-user")

    assert response.status_code == 200
    assert after is not None
    assert after.llm_model == "deepseek-reasoner"
    assert after.llm_api_key_encrypted == before.llm_api_key_encrypted
    assert after.llm_key_version == before.llm_key_version


def test_delete_actor_llm_config_does_not_affect_existing_sessions(tmp_path):
    def planner(*, llm_config, **_kwargs):
        assert llm_config["api_key"] == "sk-default"
        return _sample_ir()

    client = _client(tmp_path, planner=planner)
    client.put(
        "/v1/actor/llm-config",
        json={
            "provider": "deepseek",
            "base_url": "https://api.deepseek.com/v1",
            "model": "deepseek-chat",
            "api_key": "sk-default",
        },
    )
    created = client.post("/v1/sessions", json={}).json()
    assert created["state"] == "llm_config_set"
    archive = client.get(f"/v1/archive/sessions/{created['session_id']}").text
    assert "session.created" in archive
    assert "llm_config_inherited" in archive

    deleted = client.delete("/v1/actor/llm-config")
    assert deleted.status_code == 204
    assert client.get("/v1/actor/llm-config").json()["has_key"] is False

    turn = client.post(
        f"/v1/sessions/{created['session_id']}/turns",
        json={"user_message": "build faq"},
    )
    assert turn.status_code == 200
    assert turn.json()["status"] == "succeeded"


def test_template_seeded_session_can_override_llm_key_after_inherit(tmp_path):
    client = _client(tmp_path)
    client.put(
        "/v1/actor/llm-config",
        json={
            "provider": "deepseek",
            "base_url": "https://api.deepseek.com/v1",
            "model": "deepseek-chat",
            "api_key": "sk-default",
        },
    )
    created = client.post(
        "/v1/sessions",
        json={"template_id": "knowledge-retrieval-rag", "scope": "ecommerce/kb"},
    ).json()
    sid = created["session_id"]

    assert created["state"] == "validated"
    response = client.patch(
        f"/v1/sessions/{sid}/llm-config",
        json={"api_key": "sk-override", "base_url": "https://api.example.com/v1", "model": "override-model"},
    )
    row = client.app.state.session_store.get_session(sid, actor_id="single-user")

    assert response.status_code == 200
    assert row is not None
    assert row.state == "validated"
    assert client.app.state.fernet.decrypt(row.llm_api_key_encrypted).decode() == "sk-override"
