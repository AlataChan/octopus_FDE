from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from loom.service.app import create_app
from loom.service.deps import Settings


def _client(tmp_path) -> TestClient:
    settings = Settings(
        data_dir=tmp_path / "data",
        app_env="dev",
        fernet_key=Fernet.generate_key().decode(),
    )
    return TestClient(create_app(settings=settings))


def test_personas_route_returns_public_persona_briefs(tmp_path):
    client = _client(tmp_path)

    rows = client.get("/v1/personas").json()

    assert {row["persona_id"] for row in rows} >= {
        "ecommerce-operator",
        "ecommerce-cs-lead",
        "tcm-clinic-operator",
    }
    assert rows[0]["reviewer"]["role"]
    assert rows[0]["compliance_boundary"]["pii_class_default"]


def test_design_knowledge_route_returns_structured_cards(tmp_path):
    client = _client(tmp_path)

    response = client.post(
        "/v1/design-knowledge/retrieve",
        json={
            "intent": "build a rag knowledge base answer workflow",
            "scope": "ecommerce/kb",
            "target": "dify",
            "persona_id": "ecommerce-operator",
            "brief_draft": {"goal": "answer product policy questions"},
            "top_k": 3,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert set(payload) == {"cards", "missing_constraints", "clarifying_questions"}
    assert 1 <= len(payload["cards"]) <= 3
    card = payload["cards"][0]
    assert card["source_template_ids"] == ["knowledge-retrieval-rag"]
    assert "ecommerce/kb" in card["scopes"]
    assert "dify" in card["compile_targets"]
    assert card["node_signature"]
    assert "registry_handles" in card
    assert "ir" not in card


def test_design_knowledge_route_rejects_unknown_persona_id(tmp_path):
    client = _client(tmp_path)

    response = client.post(
        "/v1/design-knowledge/retrieve",
        json={"intent": "faq", "persona_id": "missing-persona", "top_k": 2},
    )

    assert response.status_code == 404
