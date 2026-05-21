from cryptography.fernet import Fernet

from loom.state.store import SessionStore


def test_create_session_inherits_actor_default_in_single_transaction(tmp_path):
    store = SessionStore(tmp_path / "sessions.db")
    fernet = Fernet(Fernet.generate_key())
    store.upsert_actor_llm_config(
        actor_id="single-user",
        provider="deepseek",
        base_url="https://api.deepseek.com/v1",
        model="deepseek-chat",
        api_key="sk-default",
        fernet=fernet,
    )

    def broken_audit(*_args, **_kwargs):
        raise RuntimeError("audit write failed")

    try:
        store.create_session_with_actor_defaults(
            actor_id="single-user",
            fernet=fernet,
            audit_writer=broken_audit,
        )
    except RuntimeError as exc:
        assert str(exc) == "audit write failed"
    else:
        raise AssertionError("expected audit failure")

    assert store.list_sessions(actor_id="single-user") == []

    session = store.create_session_with_actor_defaults(
        actor_id="single-user",
        fernet=fernet,
    )
    row = store.get_session(session.session_id, actor_id="single-user")
    assert row is not None
    assert row.state == "llm_config_set"
    assert row.llm_base_url == "https://api.deepseek.com/v1"
    assert row.llm_model == "deepseek-chat"
    assert row.llm_key_version == 1
    assert row.llm_api_key_encrypted is not None
    assert fernet.decrypt(row.llm_api_key_encrypted).decode() == "sk-default"


def test_put_actor_llm_config_without_api_key_preserves_existing(tmp_path):
    store = SessionStore(tmp_path / "sessions.db")
    fernet = Fernet(Fernet.generate_key())
    first = store.upsert_actor_llm_config(
        actor_id="single-user",
        provider="deepseek",
        base_url="https://api.deepseek.com/v1",
        model="deepseek-chat",
        api_key="sk-default",
        fernet=fernet,
    )

    updated = store.upsert_actor_llm_config(
        actor_id="single-user",
        provider="deepseek",
        base_url="https://api.deepseek.com/v1",
        model="deepseek-reasoner",
        api_key=None,
        fernet=fernet,
    )

    assert updated.llm_model == "deepseek-reasoner"
    assert updated.llm_key_version == first.llm_key_version
    assert updated.llm_api_key_encrypted == first.llm_api_key_encrypted
    assert fernet.decrypt(updated.llm_api_key_encrypted).decode() == "sk-default"


def test_put_actor_llm_config_rotates_key_increments_version_and_changes_ciphertext(tmp_path):
    store = SessionStore(tmp_path / "sessions.db")
    fernet = Fernet(Fernet.generate_key())
    row1 = store.upsert_actor_llm_config(
        actor_id="single-user",
        provider="deepseek",
        base_url="https://api.deepseek.com/v1",
        model="m1",
        api_key="sk-old",
        fernet=fernet,
    )

    row2 = store.upsert_actor_llm_config(
        actor_id="single-user",
        provider="deepseek",
        base_url="https://api.deepseek.com/v1",
        model="m1",
        api_key="sk-new",
        fernet=fernet,
    )

    assert row2.llm_key_version == row1.llm_key_version + 1
    assert row2.llm_api_key_encrypted != row1.llm_api_key_encrypted
    assert fernet.decrypt(row2.llm_api_key_encrypted) == b"sk-new"
