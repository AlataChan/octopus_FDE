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


def test_templates_routes_return_whitelisted_public_payloads(tmp_path):
    client = _client(tmp_path)
    all_rows = client.get("/v1/templates").json()
    rows = client.get("/v1/templates?scope=ecommerce/kb&target=dify").json()

    assert len(all_rows) == 30
    assert rows
    assert all("dify" in row["compile_targets"] for row in rows)
    assert "_internal_source" not in rows[0]
    assert "_internal_pattern" not in rows[0]
    assert rows[0]["name"]["zh"]
    assert rows[0]["name"]["en"]


def test_template_detail_returns_ir_without_internal_catalog_fields(tmp_path):
    client = _client(tmp_path)
    detail = client.get("/v1/templates/knowledge-retrieval-rag").json()

    assert detail["id"] == "knowledge-retrieval-rag"
    assert detail["ir"]["ir_version"] == "0.4"
    assert "_internal_source" not in detail
    assert "_internal_pattern" not in detail
