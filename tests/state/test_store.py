from uuid import uuid4

from cryptography.fernet import Fernet

from loom.state.store import SessionStore


def test_store_initializes_wal_and_busy_timeout(tmp_path):
    store = SessionStore(tmp_path / "sessions.db")
    assert store.pragma("journal_mode").lower() == "wal"
    assert store.pragma("busy_timeout") == "5000"


def test_session_llm_key_is_encrypted(tmp_path):
    store = SessionStore(tmp_path / "sessions.db")
    fernet = Fernet(Fernet.generate_key())
    session = store.create_session(actor_id="fde")
    store.set_llm_config(
        session.session_id,
        actor_id="fde",
        api_key="sk-secret",
        base_url="https://api.example.com/v1",
        model="deepseek-v4-flash",
        fernet=fernet,
    )

    row = store.get_session(session.session_id, actor_id="fde")
    assert row is not None
    assert row.llm_api_key_encrypted is not None
    assert row.llm_api_key_encrypted != b"sk-secret"
    assert fernet.decrypt(row.llm_api_key_encrypted).decode() == "sk-secret"
    assert row.llm_key_version == 1


def test_failed_turn_does_not_advance_latest_ir(tmp_path):
    store = SessionStore(tmp_path / "sessions.db")
    session = store.create_session(actor_id="fde")
    fernet = Fernet(Fernet.generate_key())
    store.set_llm_config(
        session.session_id,
        actor_id="fde",
        api_key="sk-secret",
        base_url="https://api.example.com/v1",
        model="deepseek-v4-flash",
        fernet=fernet,
    )
    first_turn = store.create_turn(
        session.session_id,
        actor_id="fde",
        user_message="good edit",
        ir_before=None,
    )
    store.finish_turn_succeeded(
        first_turn.turn_id,
        actor_id="fde",
        planner_reply="ok",
        ir_after='{"ir_version":"0.3"}',
    )
    before = store.get_session(session.session_id, actor_id="fde")
    assert before is not None
    assert before.state == "validated"

    turn = store.create_turn(
        session.session_id,
        actor_id="fde",
        user_message="bad edit",
        ir_before=before.latest_ir_json,
    )
    store.finish_turn_failed(
        turn.turn_id,
        actor_id="fde",
        error_kind="planner_error",
        validation_errors=["boom"],
    )

    after = store.get_session(session.session_id, actor_id="fde")
    assert after is not None
    assert after.latest_ir_sha256 == before.latest_ir_sha256
    assert after.state == before.state


def test_artifact_lookup_requires_session_and_artifact_ids(tmp_path):
    store = SessionStore(tmp_path / "sessions.db")
    session = store.create_session(actor_id="fde")
    artifact = store.create_artifact(
        session.session_id,
        actor_id="fde",
        workflow_id=uuid4(),
        artifact_name="demo.zip",
        artifact_kind="zip",
        artifact_path="sessions/s/artifacts/a.zip",
        artifact_size=12,
        sha256="a" * 64,
        target="hiagent",
        mode="chat",
        binding_handle="test",
    )

    assert store.get_artifact(session.session_id, artifact.artifact_id, actor_id="fde") is not None
    assert store.get_artifact(uuid4(), artifact.artifact_id, actor_id="fde") is None
