import json
import os
import stat

from click.testing import CliRunner
from cryptography.fernet import Fernet

from loom.cli.commands import admin as admin_cmd
from loom.cli.main import cli
from loom.service.routes.auth import AUTH_ARCHIVE_SESSION_ID
from loom.service.auth.credentials import AUTH_FILENAME, read_auth_file
from loom.service.auth.password import verify_password


def _json_from_output(output: str) -> dict:
    return json.loads(output)


def _data_dir_arg(tmp_path) -> list[str]:
    return ["--data-dir", str(tmp_path / "data")]


def _set_audit_key(monkeypatch) -> None:
    monkeypatch.setenv("LOOM_FERNET_KEY", Fernet.generate_key().decode())


def test_admin_init_password_stdin_creates_private_auth_file(tmp_path, monkeypatch):
    _set_audit_key(monkeypatch)
    monkeypatch.delenv("LOOM_AUTH_USERNAME", raising=False)
    monkeypatch.delenv("LOOM_AUTH_PASSWORD_HASH", raising=False)
    runner = CliRunner()

    result = runner.invoke(
        cli,
        ["admin", "init", "--username", "admin", "--password-stdin", *_data_dir_arg(tmp_path)],
        input="Admin123456!\n",
    )

    auth_path = tmp_path / "data" / AUTH_FILENAME
    st = os.lstat(auth_path)
    doc = read_auth_file(data_dir=tmp_path / "data")
    assert result.exit_code == 0, result.output
    assert stat.S_ISREG(st.st_mode)
    assert (st.st_mode & 0o777) == 0o600
    assert doc.username == "admin"
    assert verify_password("Admin123456!", doc.password_hash)


def test_admin_init_rejects_weak_password(tmp_path, monkeypatch):
    _set_audit_key(monkeypatch)
    runner = CliRunner()

    result = runner.invoke(
        cli,
        ["admin", "init", "--username", "admin", "--password-stdin", *_data_dir_arg(tmp_path)],
        input="weak\n",
    )

    assert result.exit_code == 1
    assert "Password must be at least 10 characters" in result.stderr
    assert not (tmp_path / "data" / AUTH_FILENAME).exists()


def test_admin_init_rejects_empty_username(tmp_path, monkeypatch):
    _set_audit_key(monkeypatch)
    runner = CliRunner()

    result = runner.invoke(
        cli,
        ["admin", "init", "--username", "", "--password-stdin", *_data_dir_arg(tmp_path)],
        input="Admin123456!\n",
    )

    assert result.exit_code == 1
    assert "Username is required" in result.stderr
    assert not (tmp_path / "data" / AUTH_FILENAME).exists()


def test_admin_init_existing_file_requires_force(tmp_path, monkeypatch):
    _set_audit_key(monkeypatch)
    runner = CliRunner()
    first = runner.invoke(
        cli,
        ["admin", "init", "--username", "admin", "--password-stdin", *_data_dir_arg(tmp_path)],
        input="Admin123456!\n",
    )
    second = runner.invoke(
        cli,
        ["admin", "init", "--username", "admin", "--password-stdin", *_data_dir_arg(tmp_path)],
        input="Admin123456!\n",
    )
    forced = runner.invoke(
        cli,
        ["admin", "init", "--username", "admin2", "--password-stdin", "--force", *_data_dir_arg(tmp_path)],
        input="Admin123456!\n",
    )

    assert first.exit_code == 0
    assert second.exit_code == 1
    assert "reset-password" in second.stderr
    assert forced.exit_code == 0, forced.output
    assert read_auth_file(data_dir=tmp_path / "data").username == "admin2"


def test_admin_reset_password_requires_existing_auth_file(tmp_path, monkeypatch):
    _set_audit_key(monkeypatch)
    runner = CliRunner()

    result = runner.invoke(
        cli,
        ["admin", "reset-password", "--password-stdin", *_data_dir_arg(tmp_path)],
        input="Admin123456!\n",
    )

    assert result.exit_code == 1
    assert "loom admin init" in result.stderr


def test_admin_reset_password_preserves_username_and_changes_hash(tmp_path, monkeypatch):
    _set_audit_key(monkeypatch)
    runner = CliRunner()
    init = runner.invoke(
        cli,
        ["admin", "init", "--username", "admin", "--password-stdin", *_data_dir_arg(tmp_path)],
        input="Admin123456!\n",
    )
    before = read_auth_file(data_dir=tmp_path / "data")

    reset = runner.invoke(
        cli,
        ["admin", "reset-password", "--password-stdin", *_data_dir_arg(tmp_path)],
        input="NewAdmin123!\n",
    )
    after = read_auth_file(data_dir=tmp_path / "data")

    assert init.exit_code == 0
    assert reset.exit_code == 0, reset.output
    assert after.username == "admin"
    assert after.password_hash != before.password_hash
    assert verify_password("NewAdmin123!", after.password_hash)
    assert after.created_at == before.created_at


def test_admin_remove_renames_auth_file_to_timestamped_backup(tmp_path, monkeypatch):
    _set_audit_key(monkeypatch)
    runner = CliRunner()
    init = runner.invoke(
        cli,
        ["admin", "init", "--username", "admin", "--password-stdin", *_data_dir_arg(tmp_path)],
        input="Admin123456!\n",
    )

    removed = runner.invoke(cli, ["admin", "remove", "--confirm", *_data_dir_arg(tmp_path)])
    backups = list((tmp_path / "data").glob("auth.json.disabled.*"))

    assert init.exit_code == 0
    assert removed.exit_code == 0, removed.output
    assert not (tmp_path / "data" / AUTH_FILENAME).exists()
    assert len(backups) == 1
    assert backups[0].name in removed.output


def test_admin_show_json_uses_safe_field_subset(tmp_path, monkeypatch):
    _set_audit_key(monkeypatch)
    monkeypatch.delenv("LOOM_AUTH_USERNAME", raising=False)
    monkeypatch.delenv("LOOM_AUTH_PASSWORD_HASH", raising=False)
    runner = CliRunner()
    init = runner.invoke(
        cli,
        ["admin", "init", "--username", "admin", "--password-stdin", *_data_dir_arg(tmp_path)],
        input="Admin123456!\n",
    )

    result = runner.invoke(cli, ["admin", "show", "--json", *_data_dir_arg(tmp_path)])

    assert init.exit_code == 0
    assert result.exit_code == 0, result.output
    payload = _json_from_output(result.stdout)
    assert payload["cli_schema_version"] == "1"
    assert payload["username"] == "admin"
    assert payload["source"] == "file"
    assert payload["created_at"]
    assert "password_hash" not in payload
    assert "salt" not in result.output


def test_admin_show_missing_credentials_exits_one(tmp_path, monkeypatch):
    monkeypatch.delenv("LOOM_AUTH_USERNAME", raising=False)
    monkeypatch.delenv("LOOM_AUTH_PASSWORD_HASH", raising=False)
    runner = CliRunner()

    result = runner.invoke(cli, ["admin", "show", "--json", *_data_dir_arg(tmp_path)])

    assert result.exit_code == 1
    payload = _json_from_output(result.stderr)
    assert payload["error"] == "not_configured"


def test_admin_password_stdin_rejects_tty(tmp_path, monkeypatch):
    _set_audit_key(monkeypatch)
    monkeypatch.setattr(admin_cmd, "_stdin_is_tty", lambda: True)
    runner = CliRunner()

    result = runner.invoke(
        cli,
        ["admin", "init", "--username", "admin", "--password-stdin", *_data_dir_arg(tmp_path)],
        input="Admin123456!\n",
    )

    assert result.exit_code == 2
    assert "interactive prompt" in result.stderr


def test_admin_init_writes_hmac_archive_event_without_plain_username(tmp_path, monkeypatch):
    _set_audit_key(monkeypatch)
    monkeypatch.setenv("LOOM_INSTANCE_ID", "admin-test")
    runner = CliRunner()

    result = runner.invoke(
        cli,
        ["admin", "init", "--username", "admin", "--password-stdin", *_data_dir_arg(tmp_path)],
        input="Admin123456!\n",
    )

    archive_text = (tmp_path / "data" / "archive" / str(AUTH_ARCHIVE_SESSION_ID) / "0001.jsonl").read_text()
    events = [json.loads(line) for line in archive_text.splitlines()]
    payload = events[-1]["payload"]
    assert result.exit_code == 0, result.output
    assert events[-1]["event_type"] == "auth.admin_init"
    assert payload["instance_id"] == "admin-test"
    assert payload["source"] == "file"
    assert payload["username_hmac"]
    assert '"username":"admin"' not in archive_text
    assert "Admin123456!" not in archive_text


def test_admin_remove_archive_uses_backup_basename_only(tmp_path, monkeypatch):
    _set_audit_key(monkeypatch)
    runner = CliRunner()
    init = runner.invoke(
        cli,
        ["admin", "init", "--username", "admin", "--password-stdin", *_data_dir_arg(tmp_path)],
        input="Admin123456!\n",
    )

    removed = runner.invoke(cli, ["admin", "remove", "--confirm", *_data_dir_arg(tmp_path)])

    archive_text = "\n".join(
        path.read_text() for path in sorted((tmp_path / "data" / "archive" / str(AUTH_ARCHIVE_SESSION_ID)).glob("*.jsonl"))
    )
    events = [json.loads(line) for line in archive_text.splitlines()]
    payload = events[-1]["payload"]
    assert init.exit_code == 0
    assert removed.exit_code == 0, removed.output
    assert events[-1]["event_type"] == "auth.admin_removed"
    assert payload["backup_basename"].startswith("auth.json.disabled.")
    assert "/" not in payload["backup_basename"]
    assert str(tmp_path) not in archive_text


def test_admin_init_requires_archive_writer_before_writing_auth_file(tmp_path, monkeypatch):
    monkeypatch.delenv("LOOM_FERNET_KEY", raising=False)
    runner = CliRunner()

    result = runner.invoke(
        cli,
        ["admin", "init", "--username", "admin", "--password-stdin", *_data_dir_arg(tmp_path)],
        input="Admin123456!\n",
    )

    assert result.exit_code == 2
    payload = _json_from_output(result.stderr)
    assert payload["cli_schema_version"] == "1"
    assert payload["error"] == "archive_unavailable"
    assert payload["detail"] == "LOOM_FERNET_KEY required for admin audit"
    assert not (tmp_path / "data" / AUTH_FILENAME).exists()


def test_admin_reset_requires_archive_writer_before_rewriting_auth_file(tmp_path, monkeypatch):
    _set_audit_key(monkeypatch)
    runner = CliRunner()
    init = runner.invoke(
        cli,
        ["admin", "init", "--username", "admin", "--password-stdin", *_data_dir_arg(tmp_path)],
        input="Admin123456!\n",
    )
    before = read_auth_file(data_dir=tmp_path / "data")
    monkeypatch.delenv("LOOM_FERNET_KEY", raising=False)

    result = runner.invoke(
        cli,
        ["admin", "reset-password", "--password-stdin", *_data_dir_arg(tmp_path)],
        input="NewAdmin123!\n",
    )

    after = read_auth_file(data_dir=tmp_path / "data")
    assert init.exit_code == 0
    assert result.exit_code == 2
    assert _json_from_output(result.stderr)["error"] == "archive_unavailable"
    assert after.password_hash == before.password_hash


def test_admin_remove_requires_archive_writer_before_renaming_auth_file(tmp_path, monkeypatch):
    _set_audit_key(monkeypatch)
    runner = CliRunner()
    init = runner.invoke(
        cli,
        ["admin", "init", "--username", "admin", "--password-stdin", *_data_dir_arg(tmp_path)],
        input="Admin123456!\n",
    )
    monkeypatch.delenv("LOOM_FERNET_KEY", raising=False)

    result = runner.invoke(cli, ["admin", "remove", "--confirm", *_data_dir_arg(tmp_path)])

    assert init.exit_code == 0
    assert result.exit_code == 2
    assert _json_from_output(result.stderr)["error"] == "archive_unavailable"
    assert (tmp_path / "data" / AUTH_FILENAME).exists()
    assert not list((tmp_path / "data").glob("auth.json.disabled.*"))


def test_admin_show_skips_archive_when_fernet_key_missing(tmp_path, monkeypatch):
    _set_audit_key(monkeypatch)
    monkeypatch.delenv("LOOM_AUTH_USERNAME", raising=False)
    monkeypatch.delenv("LOOM_AUTH_PASSWORD_HASH", raising=False)
    runner = CliRunner()
    init = runner.invoke(
        cli,
        ["admin", "init", "--username", "admin", "--password-stdin", *_data_dir_arg(tmp_path)],
        input="Admin123456!\n",
    )
    monkeypatch.delenv("LOOM_FERNET_KEY", raising=False)
    archive_before = sorted((tmp_path / "data" / "archive" / str(AUTH_ARCHIVE_SESSION_ID)).glob("*.jsonl"))

    result = runner.invoke(cli, ["admin", "show", "--json", *_data_dir_arg(tmp_path)])

    archive_after = sorted((tmp_path / "data" / "archive" / str(AUTH_ARCHIVE_SESSION_ID)).glob("*.jsonl"))
    assert init.exit_code == 0
    assert result.exit_code == 0, result.output
    assert _json_from_output(result.stdout)["username"] == "admin"
    assert archive_after == archive_before
