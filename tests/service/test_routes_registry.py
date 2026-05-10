from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from loom.registry.models import WorkflowRecord
from loom.service.app import create_app
from loom.service.deps import Settings


def test_registry_routes_list_get_and_mark_deployed(tmp_path):
    settings = Settings(data_dir=tmp_path, app_env="dev", fernet_key=Fernet.generate_key().decode())
    app = create_app(settings=settings)
    rec = WorkflowRecord.new(
        session_id="11111111-1111-4111-8111-111111111111",
        artifact_id="22222222-2222-4222-8222-222222222222",
        artifact_name="demo.zip",
        artifact_kind="zip",
        artifact_sha256="a" * 64,
        ir_signature="b" * 64,
        ir_version="0.3",
        target="hiagent",
        mode="chat",
        binding_handle="test",
        compiler_version="test",
        created_by_actor="fde",
    )
    app.state.registry_store.create(rec)
    client = TestClient(app)

    rows = client.get("/v1/registry/workflows").json()
    assert rows[0]["workflow_id"] == str(rec.workflow_id)

    got = client.get(f"/v1/registry/workflows/{rec.workflow_id}").json()
    assert got["artifact_sha256"] == "a" * 64

    resp = client.post(
        f"/v1/registry/workflows/{rec.workflow_id}/deployed",
        json={"platform_app_id": "app_123", "deployment_note": "imported"},
    )
    assert resp.status_code == 200
    assert resp.json()["platform_app_id"] == "app_123"
