import shutil
from datetime import UTC, datetime
from uuid import uuid4

from loom.registry.models import WorkflowRecord
from loom.registry.store import WorkflowRegistryStore


def _record() -> WorkflowRecord:
    now = datetime.now(UTC)
    return WorkflowRecord(
        workflow_id=uuid4(),
        session_id=uuid4(),
        artifact_id=uuid4(),
        artifact_name="demo.zip",
        artifact_kind="zip",
        artifact_sha256="a" * 64,
        ir_signature="b" * 64,
        ir_version="0.3",
        target="hiagent",
        mode="chatflow",
        binding_handle="test",
        compiler_version="test",
        created_by_actor="fde",
        compiled_at=now,
    )


def test_registry_crud_and_deployed_marker(tmp_path):
    store = WorkflowRegistryStore(tmp_path / "workflow_registry.db")
    rec = _record()
    store.create(rec)

    got = store.get(rec.workflow_id)
    assert got is not None
    assert got.artifact_sha256 == "a" * 64

    store.mark_deployed(
        rec.workflow_id,
        platform_app_id="app_123",
        deployment_note="manual import ok",
        deployed_by_actor="fde",
    )
    deployed = store.get(rec.workflow_id)
    assert deployed is not None
    assert deployed.platform_app_id == "app_123"
    assert deployed.deployed_by_actor == "fde"


def test_registry_db_is_portable_without_sessions_db(tmp_path):
    store = WorkflowRegistryStore(tmp_path / "workflow_registry.db")
    rec = _record()
    store.create(rec)

    copied = tmp_path / "portable.db"
    shutil.copyfile(store.db_path, copied)
    portable = WorkflowRegistryStore(copied)

    rows = portable.list()
    assert len(rows) == 1
    assert rows[0].workflow_id == rec.workflow_id
    assert rows[0].ir_signature == rec.ir_signature
    assert rows[0].artifact_sha256 == rec.artifact_sha256
