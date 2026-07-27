from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from loom.registry.models import WorkflowRecord
from loom.service.app import create_app
from loom.service.deps import Settings


def test_registry_routes_list_get_and_mark_deployed(tmp_path):
    settings = Settings(data_dir=tmp_path, app_env="dev", fernet_key=Fernet.generate_key().decode())
    app = create_app(settings=settings)
    session = app.state.session_store.create_session(actor_id="single-user")
    artifact = app.state.session_store.create_artifact(
        session.session_id,
        actor_id="single-user",
        workflow_id="33333333-3333-4333-8333-333333333333",
        artifact_name="demo.zip",
        artifact_kind="zip",
        artifact_path="sessions/demo/artifacts/demo.zip",
        artifact_size=42,
        sha256="a" * 64,
        target="hiagent",
        mode="chat",
        binding_handle="test",
    )
    rec = WorkflowRecord.new(
        session_id=str(session.session_id),
        artifact_id=str(artifact.artifact_id),
        artifact_name="demo.zip",
        artifact_kind="zip",
        artifact_sha256="a" * 64,
        ir_signature="b" * 64,
        ir_version="0.3",
        target="hiagent",
        mode="chat",
        binding_handle="test",
        compiler_version="test",
        created_by_actor="single-user",
    )
    app.state.registry_store.create(rec)
    client = TestClient(app)

    rows = client.get("/v1/registry/workflows").json()
    assert rows[0]["workflow_id"] == str(rec.workflow_id)

    got = client.get(f"/v1/registry/workflows/{rec.workflow_id}").json()
    assert got["registry_row"]["artifact_sha256"] == "a" * 64
    assert got["artifact"] == {
        "id": str(artifact.artifact_id),
        "name": "demo.zip",
        "kind": "zip",
        "sha256": "a" * 64,
        "size": 42,
        "downloaded_at": None,
    }

    resp = client.post(
        f"/v1/registry/workflows/{rec.workflow_id}/deployed",
        json={"platform_app_id": "app_123", "deployment_note": "imported"},
    )
    assert resp.status_code == 200
    assert resp.json()["platform_app_id"] == "app_123"


def _create_workflow_for_actor(app, actor_id: str) -> WorkflowRecord:
    session = app.state.session_store.create_session(actor_id=actor_id)
    artifact = app.state.session_store.create_artifact(
        session.session_id,
        actor_id=actor_id,
        workflow_id="44444444-4444-4444-8444-444444444444",
        artifact_name="owner-only.zip",
        artifact_kind="zip",
        artifact_path="sessions/owner-only/artifacts/owner-only.zip",
        artifact_size=7,
        sha256="c" * 64,
        target="hiagent",
        mode="chat",
        binding_handle="test",
    )
    rec = WorkflowRecord.new(
        session_id=str(session.session_id),
        artifact_id=str(artifact.artifact_id),
        artifact_name="owner-only.zip",
        artifact_kind="zip",
        artifact_sha256="c" * 64,
        ir_signature="d" * 64,
        ir_version="0.3",
        target="hiagent",
        mode="chat",
        binding_handle="test",
        compiler_version="test",
        created_by_actor=actor_id,
    )
    app.state.registry_store.create(rec)
    return rec


def test_registry_routes_reject_cross_actor_list_get_and_deploy(tmp_path):
    settings = Settings(data_dir=tmp_path, app_env="dev", fernet_key=Fernet.generate_key().decode())
    app = create_app(settings=settings)
    rec = _create_workflow_for_actor(app, "owner-actor")
    client = TestClient(app)
    intruder_headers = {"X-Actor-Id": "intruder-actor"}

    rows = client.get("/v1/registry/workflows", headers=intruder_headers).json()
    assert rows == []

    got = client.get(f"/v1/registry/workflows/{rec.workflow_id}", headers=intruder_headers)
    assert got.status_code == 404

    deployed = client.post(
        f"/v1/registry/workflows/{rec.workflow_id}/deployed",
        json={"platform_app_id": "hijacked", "deployment_note": "cross-actor attempt"},
        headers=intruder_headers,
    )
    assert deployed.status_code == 404

    owner_headers = {"X-Actor-Id": "owner-actor"}
    owner_rows = client.get("/v1/registry/workflows", headers=owner_headers).json()
    assert [row["workflow_id"] for row in owner_rows] == [str(rec.workflow_id)]

    owner_got = client.get(f"/v1/registry/workflows/{rec.workflow_id}", headers=owner_headers)
    assert owner_got.status_code == 200
    assert owner_got.json()["registry_row"]["platform_app_id"] is None

    owner_deployed = client.post(
        f"/v1/registry/workflows/{rec.workflow_id}/deployed",
        json={"platform_app_id": "app_456", "deployment_note": "owner deploy"},
        headers=owner_headers,
    )
    assert owner_deployed.status_code == 200
    assert owner_deployed.json()["platform_app_id"] == "app_456"
