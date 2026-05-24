import json
import os
import stat

from click.testing import CliRunner

from loom.cli.commands import admin as admin_cmd
from loom.cli.main import cli
from loom.service.auth.credentials import AUTH_FILENAME, read_auth_file
from loom.service.auth.password import verify_password


def _json_from_output(output: str) -> dict:
    return json.loads(output)


def _data_dir_arg(tmp_path) -> list[str]:
    return ["--data-dir", str(tmp_path / "data")]


def test_admin_init_password_stdin_creates_private_auth_file(tmp_path, monkeypatch):
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


def test_admin_init_rejects_weak_password(tmp_path):
    runner = CliRunner()

    result = runner.invoke(
        cli,
        ["admin", "init", "--username", "admin", "--password-stdin", *_data_dir_arg(tmp_path)],
        input="weak\n",
    )

    assert result.exit_code == 1
    assert "Password must be at least 10 characters" in result.stderr
    assert not (tmp_path / "data" / AUTH_FILENAME).exists()


def test_admin_init_existing_file_requires_force(tmp_path):
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


def test_admin_reset_password_requires_existing_auth_file(tmp_path):
    runner = CliRunner()

    result = runner.invoke(
        cli,
        ["admin", "reset-password", "--password-stdin", *_data_dir_arg(tmp_path)],
        input="Admin123456!\n",
    )

    assert result.exit_code == 1
    assert "loom admin init" in result.stderr


def test_admin_reset_password_preserves_username_and_changes_hash(tmp_path):
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


def test_admin_remove_renames_auth_file_to_timestamped_backup(tmp_path):
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
    monkeypatch.setattr(admin_cmd, "_stdin_is_tty", lambda: True)
    runner = CliRunner()

    result = runner.invoke(
        cli,
        ["admin", "init", "--username", "admin", "--password-stdin", *_data_dir_arg(tmp_path)],
        input="Admin123456!\n",
    )

    assert result.exit_code == 2
    assert "interactive prompt" in result.stderr
