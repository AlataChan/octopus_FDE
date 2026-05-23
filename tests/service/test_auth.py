import json

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from loom.service.app import create_app
from loom.service.deps import Settings
from loom.service.routes.auth import AUTH_ARCHIVE_SESSION_ID

PASSWORD_HASH = "scrypt$16384$8$1$MDEyMzQ1Njc4OWFiY2RlZg==$41uBuEIHgVau41v1q9BTZzisnSi/olB0DbA83e36fiY="


def _settings(tmp_path, *, ttl_hours: int = 24) -> Settings:
    return Settings(
        data_dir=tmp_path / "data",
        app_env="dev",
        fernet_key=Fernet.generate_key().decode(),
        auth_username="admin",
        auth_password_hash=PASSWORD_HASH,
        auth_session_ttl_hours=ttl_hours,
        auth_disabled=False,
        instance_id="test-instance",
    )


def _client(tmp_path, *, ttl_hours: int = 24) -> TestClient:
    return TestClient(create_app(settings=_settings(tmp_path, ttl_hours=ttl_hours)))


def _login(client: TestClient, password: str = "secret"):
    return client.post(
        "/v1/auth/login",
        headers={"Origin": "http://testserver"},
        json={"username": "admin", "password": password},
    )


def test_auth_middleware_blocks_v1_routes_without_cookie(tmp_path):
    client = _client(tmp_path)

    assert client.get("/v1/health").status_code == 200
    response = client.get("/v1/sessions")

    assert response.status_code == 401
    assert response.json() == {"error": "not_authenticated"}


def test_login_cookie_allows_authenticated_session_access_and_logout(tmp_path):
    client = _client(tmp_path)

    login = _login(client)
    assert login.status_code == 200
    assert "fde_session=" in login.headers["set-cookie"]

    created = client.post("/v1/sessions", headers={"Origin": "http://testserver"}, json={})
    assert created.status_code == 200

    logout = client.post("/v1/auth/logout")
    assert logout.status_code == 200
    assert client.get("/v1/sessions").status_code == 401


def test_mutating_authenticated_requests_require_same_origin(tmp_path):
    client = _client(tmp_path)
    assert _login(client).status_code == 200

    blocked = client.post("/v1/sessions", json={})
    allowed = client.post("/v1/sessions", headers={"Origin": "http://testserver"}, json={})

    assert blocked.status_code == 403
    assert blocked.json() == {"error": "csrf_origin_mismatch"}
    assert allowed.status_code == 200


def test_login_failures_are_generic_and_rate_limited(tmp_path):
    client = _client(tmp_path)

    for _ in range(5):
        response = _login(client, password="wrong")
        assert response.status_code == 401
        assert response.json() == {"error": "invalid_credentials"}

    limited = _login(client, password="wrong")
    assert limited.status_code == 429
    assert limited.json() == {"error": "rate_limited"}


def test_expired_cookie_is_rejected(tmp_path):
    client = _client(tmp_path, ttl_hours=0)
    assert _login(client).status_code == 200

    response = client.get("/v1/sessions")

    assert response.status_code == 401


def test_auth_archive_events_use_hmac_and_instance_id(tmp_path):
    client = _client(tmp_path)

    assert _login(client).status_code == 200
    text = client.app.state.archive_writer.read_session_text(AUTH_ARCHIVE_SESSION_ID)
    events = [json.loads(line) for line in text.splitlines()]

    assert events[-1]["event_type"] == "auth.login_succeeded"
    payload = events[-1]["payload"]
    assert payload["instance_id"] == "test-instance"
    assert payload["username_hmac"]
    assert payload["client_ip_hmac"]
    assert "admin" not in text
    assert "secret" not in text
    assert "testclient" not in text


def test_prod_requires_auth_password_hash(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_ENV", "prod")
    monkeypatch.setenv("LOOM_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("LOOM_FERNET_KEY", Fernet.generate_key().decode())
    monkeypatch.setenv("LOOM_AUTH_USERNAME", "admin")
    monkeypatch.delenv("LOOM_AUTH_PASSWORD_HASH", raising=False)

    with pytest.raises(RuntimeError, match="LOOM_AUTH_PASSWORD_HASH"):
        Settings.from_env()


def test_low_scrypt_cost_is_rejected(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_ENV", "prod")
    monkeypatch.setenv("LOOM_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("LOOM_FERNET_KEY", Fernet.generate_key().decode())
    monkeypatch.setenv("LOOM_AUTH_USERNAME", "admin")
    monkeypatch.setenv("LOOM_AUTH_PASSWORD_HASH", PASSWORD_HASH.replace("16384", "1024", 1))

    with pytest.raises(RuntimeError, match="at least 16384"):
        Settings.from_env()


def test_web_concurrency_must_be_single_worker(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_ENV", "prod")
    monkeypatch.setenv("LOOM_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("LOOM_FERNET_KEY", Fernet.generate_key().decode())
    monkeypatch.setenv("LOOM_AUTH_USERNAME", "admin")
    monkeypatch.setenv("LOOM_AUTH_PASSWORD_HASH", PASSWORD_HASH)
    monkeypatch.setenv("WEB_CONCURRENCY", "2")

    with pytest.raises(RuntimeError, match="WEB_CONCURRENCY"):
        Settings.from_env()


def test_cors_wildcard_is_rejected(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_ENV", "dev")
    monkeypatch.setenv("LOOM_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("LOOM_CORS_ALLOW_ORIGINS", "*")

    with pytest.raises(RuntimeError, match="must not contain"):
        Settings.from_env()
