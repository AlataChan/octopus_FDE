from uuid import uuid4

import pytest
from cryptography.fernet import Fernet

from loom.runtimes.warnings import CompileWarning
from loom.state.store import SessionStore, StaleSessionRevision


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


def test_readonly_store_can_read_but_rejects_write_apis(tmp_path):
    store = SessionStore(tmp_path / "sessions.db")
    session = store.create_session(actor_id="fde")

    readonly = SessionStore.open_readonly(tmp_path / "sessions.db")

    assert readonly.get_session(session.session_id, actor_id="fde") is not None
    with pytest.raises(RuntimeError, match="read-only"):
        readonly.create_session(actor_id="fde")


def test_set_llm_config_on_template_seeded_session_preserves_state(tmp_path):
    """模板初始化的 session（state=validated）必须允许再次设置 LLM key。"""
    store = SessionStore(tmp_path / "sessions.db")
    fernet = Fernet(Fernet.generate_key())
    session = store.create_session(actor_id="fde")
    turn = store.create_turn(session.session_id, actor_id="fde", user_message="template:rag", ir_before=None)
    store.finish_turn_succeeded(turn.turn_id, actor_id="fde", planner_reply="seeded", ir_after='{"ir_version":"0.4"}')
    assert store.get_session(session.session_id, actor_id="fde").state == "validated"

    store.set_llm_config(
        session.session_id,
        actor_id="fde",
        api_key="sk-deepseek",
        base_url="https://api.deepseek.com/v1",
        model="deepseek-chat",
        fernet=fernet,
    )

    row = store.get_session(session.session_id, actor_id="fde")
    assert row.state == "validated"
    assert fernet.decrypt(row.llm_api_key_encrypted).decode() == "sk-deepseek"


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


def test_concurrent_turn_completion_uses_session_revision_compare_and_swap(tmp_path):
    store = SessionStore(tmp_path / "sessions.db")
    session = store.create_session(actor_id="fde")
    store.update_latest_ir(session.session_id, actor_id="fde", ir_json='{"version": 1}')
    before = store.get_session(session.session_id, actor_id="fde")
    assert before is not None
    first = store.create_turn(
        session.session_id,
        actor_id="fde",
        user_message="edit retry",
        ir_before=before.latest_ir_json,
    )
    second = store.create_turn(
        session.session_id,
        actor_id="fde",
        user_message="edit top_k",
        ir_before=before.latest_ir_json,
    )

    store.finish_turn_succeeded(
        first.turn_id,
        actor_id="fde",
        planner_reply="ok",
        ir_after='{"version": 2, "retry": 4}',
    )
    with pytest.raises(StaleSessionRevision):
        store.finish_turn_succeeded(
            second.turn_id,
            actor_id="fde",
            planner_reply="ok",
            ir_after='{"version": 2, "top_k": 8}',
        )

    current = store.get_session(session.session_id, actor_id="fde")
    assert current is not None
    assert current.latest_ir_json == '{"version": 2, "retry": 4}'
    assert store.get_turn(first.turn_id, actor_id="fde").status == "succeeded"
    stale = store.get_turn(second.turn_id, actor_id="fde")
    assert stale is not None
    assert stale.status == "failed"
    assert stale.validation_errors == ["stale_session_revision"]


def test_create_turn_rejects_ir_snapshot_older_than_current_session(tmp_path):
    store = SessionStore(tmp_path / "sessions.db")
    session = store.create_session(actor_id="fde")
    store.update_latest_ir(session.session_id, actor_id="fde", ir_json='{"version": 1}')
    stale_snapshot = store.get_session(session.session_id, actor_id="fde")
    assert stale_snapshot is not None
    store.update_latest_ir(session.session_id, actor_id="fde", ir_json='{"version": 2}')

    with pytest.raises(StaleSessionRevision):
        store.create_turn(
            session.session_id,
            actor_id="fde",
            user_message="edit stale workflow",
            ir_before=stale_snapshot.latest_ir_json,
        )

    assert store.list_turns(session.session_id, actor_id="fde") == []


def test_create_turn_rejects_stale_planning_context_revision(tmp_path):
    store = SessionStore(tmp_path / "sessions.db")
    session = store.create_session(actor_id="fde", self_design=True)
    snapshot = store.get_session_with_revision(session.session_id, actor_id="fde")
    assert snapshot is not None
    stale_session, stale_revision = snapshot
    store.update_session_brief_state(
        session.session_id,
        actor_id="fde",
        brief_draft='{"scope":"tcm/clinic"}',
        clarify_round=1,
        target_runtime="dify",
        scope="tcm/clinic",
    )

    with pytest.raises(StaleSessionRevision):
        store.create_turn(
            session.session_id,
            actor_id="fde",
            user_message="plan with stale scope",
            ir_before=stale_session.latest_ir_json,
            expected_revision=stale_revision,
        )


def test_concurrent_clarify_turns_compare_and_swap_brief_state(tmp_path):
    store = SessionStore(tmp_path / "sessions.db")
    session = store.create_session(actor_id="fde", self_design=True)
    first = store.create_turn(
        session.session_id,
        actor_id="fde",
        user_message="first answer",
        ir_before=None,
        kind="clarify",
    )
    second = store.create_turn(
        session.session_id,
        actor_id="fde",
        user_message="second answer",
        ir_before=None,
        kind="clarify",
    )

    store.finish_turn_clarify(
        first.turn_id,
        actor_id="fde",
        kind="clarify",
        planner_reply="next",
        clarify_question='{"field_path":"scope"}',
        brief_before=None,
        brief_after='{"intent":"first"}',
        clarify_round=1,
        target_runtime="hiagent",
        scope="ecommerce/kb",
    )
    with pytest.raises(StaleSessionRevision):
        store.finish_turn_clarify(
            second.turn_id,
            actor_id="fde",
            kind="clarify",
            planner_reply="next",
            clarify_question='{"field_path":"scope"}',
            brief_before=None,
            brief_after='{"intent":"second"}',
            clarify_round=1,
            target_runtime="dify",
            scope="tcm/clinic",
        )

    current = store.get_session(session.session_id, actor_id="fde")
    assert current is not None
    assert current.brief_draft == '{"intent":"first"}'
    assert current.target_runtime == "hiagent"
    assert store.get_turn(second.turn_id, actor_id="fde").status == "failed"


def test_clarify_completion_makes_in_flight_plan_stale(tmp_path):
    store = SessionStore(tmp_path / "sessions.db")
    session = store.create_session(actor_id="fde", self_design=True)
    plan_turn = store.create_turn(
        session.session_id,
        actor_id="fde",
        user_message="generate",
        ir_before=None,
    )
    clarify_turn = store.create_turn(
        session.session_id,
        actor_id="fde",
        user_message="new scope",
        ir_before=None,
        kind="clarify",
    )
    store.finish_turn_clarify(
        clarify_turn.turn_id,
        actor_id="fde",
        kind="clarify",
        planner_reply="next",
        clarify_question='{"field_path":"scope"}',
        brief_before=None,
        brief_after='{"scope":"tcm/clinic"}',
        clarify_round=1,
        target_runtime="dify",
        scope="tcm/clinic",
    )

    with pytest.raises(StaleSessionRevision):
        store.finish_turn_succeeded(
            plan_turn.turn_id,
            actor_id="fde",
            planner_reply="old plan",
            ir_after='{"version": 1}',
        )

    current = store.get_session(session.session_id, actor_id="fde")
    assert current is not None
    assert current.latest_ir_json is None
    assert current.scope == "tcm/clinic"


def test_binding_grants_are_scoped_by_tenant_and_actor(tmp_path):
    store = SessionStore(tmp_path / "sessions.db")
    store.grant_binding_access(
        tenant_id="tenant-a",
        actor_id="alice",
        binding_handle="customer-prod",
    )

    assert store.binding_is_authorized(
        tenant_id="tenant-a",
        actor_id="alice",
        binding_handle="customer-prod",
    )
    assert not store.binding_is_authorized(
        tenant_id="tenant-a",
        actor_id="bob",
        binding_handle="customer-prod",
    )
    assert not store.binding_is_authorized(
        tenant_id="tenant-b",
        actor_id="alice",
        binding_handle="customer-prod",
    )


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
        compile_warnings=[
            CompileWarning(
                target="hiagent",
                node_id=None,
                field="policy.audit",
                message="audit metadata is informational",
                code="policy.audit.noop",
            )
        ],
    )

    stored = store.get_artifact(session.session_id, artifact.artifact_id, actor_id="fde")
    assert stored is not None
    assert stored.compile_warnings[0].code == "policy.audit.noop"
    assert store.get_artifact(uuid4(), artifact.artifact_id, actor_id="fde") is None


def test_delete_session_removes_session_turns_and_artifacts_for_actor_only(tmp_path):
    store = SessionStore(tmp_path / "sessions.db")
    session = store.create_session(actor_id="fde")
    turn = store.create_turn(
        session.session_id,
        actor_id="fde",
        user_message="build workflow",
        ir_before=None,
    )
    artifact = store.create_artifact(
        session.session_id,
        actor_id="fde",
        workflow_id=uuid4(),
        artifact_name="demo.zip",
        artifact_kind="zip",
        artifact_path="sessions/s/artifacts/a.zip",
        artifact_size=12,
        sha256="b" * 64,
        target="hiagent",
        mode="chat",
        binding_handle="test",
    )

    assert store.delete_session(session.session_id, actor_id="other") is False
    assert store.get_session(session.session_id, actor_id="fde") is not None
    assert store.get_turn(turn.turn_id, actor_id="fde") is not None
    assert store.get_artifact(session.session_id, artifact.artifact_id, actor_id="fde") is not None

    assert store.delete_session(session.session_id, actor_id="fde") is True

    assert store.get_session(session.session_id, actor_id="fde") is None
    assert store.list_turns(session.session_id, actor_id="fde") == []
    assert store.list_artifacts(session.session_id, actor_id="fde") == []
    assert store.delete_session(session.session_id, actor_id="fde") is False
