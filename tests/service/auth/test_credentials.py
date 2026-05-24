import json
import os
import stat
from datetime import UTC, datetime

import pytest

from loom.service.auth.credentials import (
    AUTH_FILENAME,
    AuthCredentialsError,
    AuthFileSchema,
    atomic_write_auth_file,
    load_auth_credentials,
)

PASSWORD_HASH = "scrypt$16384$8$1$MDEyMzQ1Njc4OWFiY2RlZg==$41uBuEIHgVau41v1q9BTZzisnSi/olB0DbA83e36fiY="


def _auth_doc(username: str = "admin") -> AuthFileSchema:
    now = datetime(2026, 5, 24, 13, 0, tzinfo=UTC)
    return AuthFileSchema(
        username=username,
        password_hash=PASSWORD_HASH,
        created_at=now,
        last_password_changed_at=now,
    )


def test_atomic_write_auth_file_creates_private_regular_file(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir(mode=0o700)

    path = atomic_write_auth_file(data_dir, _auth_doc())

    st = os.lstat(path)
    assert path == data_dir / AUTH_FILENAME
    assert stat.S_ISREG(st.st_mode)
    assert (st.st_mode & 0o777) == 0o600
    assert json.loads(path.read_text())["username"] == "admin"


def test_atomic_write_auth_file_refuses_existing_symlink_even_with_force(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir(mode=0o700)
    (data_dir / AUTH_FILENAME).symlink_to("/etc/passwd")

    with pytest.raises(AuthCredentialsError, match="refusing symlink"):
        atomic_write_auth_file(data_dir, _auth_doc(), force=True)


def test_atomic_write_auth_file_cleans_tmp_when_write_fails(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    data_dir.mkdir(mode=0o700)

    def fail_write(_fd, _payload):
        raise OSError("disk full")

    monkeypatch.setattr(os, "write", fail_write)

    with pytest.raises(AuthCredentialsError, match="failed to write"):
        atomic_write_auth_file(data_dir, _auth_doc())

    assert not list(data_dir.glob(".auth.json.tmp.*"))
    assert not (data_dir / AUTH_FILENAME).exists()


def test_load_auth_credentials_reads_file_fallback(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir(mode=0o700)
    atomic_write_auth_file(data_dir, _auth_doc("file-admin"))

    credentials = load_auth_credentials(data_dir=data_dir, env={}, app_env="prod")

    assert credentials is not None
    assert credentials.username == "file-admin"
    assert credentials.password_hash == PASSWORD_HASH
    assert credentials.source == "file"
    assert credentials.created_at is not None


def test_load_auth_credentials_env_wins_over_file_without_logging_username(tmp_path, caplog):
    data_dir = tmp_path / "data"
    data_dir.mkdir(mode=0o700)
    atomic_write_auth_file(data_dir, _auth_doc("file-admin"))
    caplog.set_level("INFO")

    credentials = load_auth_credentials(
        data_dir=data_dir,
        env={"LOOM_AUTH_USERNAME": "env-admin", "LOOM_AUTH_PASSWORD_HASH": PASSWORD_HASH},
        app_env="prod",
    )

    assert credentials is not None
    assert credentials.username == "env-admin"
    assert credentials.source == "env"
    assert "env-admin" not in caplog.text
    assert "file-admin" not in caplog.text


def test_load_auth_credentials_rejects_partial_env(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir(mode=0o700)

    with pytest.raises(AuthCredentialsError, match="both"):
        load_auth_credentials(data_dir=data_dir, env={"LOOM_AUTH_USERNAME": "admin"}, app_env="prod")


def test_load_auth_credentials_prod_rejects_loose_permissions(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir(mode=0o700)
    path = atomic_write_auth_file(data_dir, _auth_doc())
    path.chmod(0o644)

    with pytest.raises(AuthCredentialsError, match="mode 0600"):
        load_auth_credentials(data_dir=data_dir, env={}, app_env="prod")


def test_load_auth_credentials_dev_warns_on_loose_permissions(tmp_path, caplog):
    data_dir = tmp_path / "data"
    data_dir.mkdir(mode=0o700)
    path = atomic_write_auth_file(data_dir, _auth_doc())
    path.chmod(0o644)
    caplog.set_level("WARNING")

    credentials = load_auth_credentials(data_dir=data_dir, env={}, app_env="dev")

    assert credentials is not None
    assert "auth.json permissions" in caplog.text


def test_load_auth_credentials_rejects_symlink_even_with_env(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir(mode=0o700)
    (data_dir / AUTH_FILENAME).symlink_to("/etc/passwd")

    with pytest.raises(AuthCredentialsError, match="symlink"):
        load_auth_credentials(
            data_dir=data_dir,
            env={"LOOM_AUTH_USERNAME": "admin", "LOOM_AUTH_PASSWORD_HASH": PASSWORD_HASH},
            app_env="dev",
        )


def test_load_auth_credentials_rejects_invalid_schema(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir(mode=0o700)
    (data_dir / AUTH_FILENAME).write_text('{"schema_version":"2","username":"admin"}')
    (data_dir / AUTH_FILENAME).chmod(0o600)

    with pytest.raises(AuthCredentialsError, match=str(data_dir / AUTH_FILENAME)):
        load_auth_credentials(data_dir=data_dir, env={}, app_env="prod")
