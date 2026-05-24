"""Admin credential initialization commands."""
from __future__ import annotations

import getpass
import json
import os
import socket
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import NoReturn, cast

import click

from loom.archive.jsonl import ArchiveWriter
from loom.archive.schema import ArchiveEventType
from loom.archive.writer import InstanceArchiveWriter
from loom.service.auth.credentials import (
    AUTH_FILENAME,
    AuthCredentialsError,
    AuthFileSchema,
    atomic_write_auth_file,
    load_auth_credentials,
    read_auth_file,
)
from loom.service.auth.password import hash_password
from loom.service.deps import Settings
from loom.service.routes.auth import AUTH_ARCHIVE_SESSION_ID

CLI_SCHEMA_VERSION = "1"


@click.group(help="Manage local single-user admin credentials.")
def admin() -> None:
    pass


@admin.command("init", help="Initialize the local admin auth.json file.")
@click.option("--data-dir", type=click.Path(path_type=Path), help="Data directory for auth.json.")
@click.option("--username", help="Admin username. Prompts when omitted.")
@click.option("--password-stdin", is_flag=True, help="Read one password line from stdin.")
@click.option("--force", is_flag=True, help="Overwrite an existing auth.json file.")
def init_cmd(data_dir: Path | None, username: str | None, password_stdin: bool, force: bool) -> None:
    root = _data_dir(data_dir, create=True)
    username = username or click.prompt("Username", type=str)
    password = _read_password(password_stdin)
    _validate_password_strength(password)
    doc = _new_auth_doc(username=username, password=password)
    try:
        path = atomic_write_auth_file(root, doc, force=force)
    except AuthCredentialsError as e:
        _exit(str(e), code=1 if "already exists" in str(e) else 2)
    _append_admin_event(root, "auth.admin_init", username=username, payload={"source": "file"})
    click.echo(f"✓ admin user '{username}' created at {path}")


@admin.command("reset-password", help="Reset the existing local admin password.")
@click.option("--data-dir", type=click.Path(path_type=Path), help="Data directory for auth.json.")
@click.option("--password-stdin", is_flag=True, help="Read one password line from stdin.")
def reset_password_cmd(data_dir: Path | None, password_stdin: bool) -> None:
    root = _data_dir(data_dir, create=False)
    auth_path = root / AUTH_FILENAME
    if not auth_path.exists() and not auth_path.is_symlink():
        _exit(f"{auth_path} not found; run `loom admin init` first", code=1)
    try:
        current = read_auth_file(data_dir=root)
    except AuthCredentialsError as e:
        _exit(str(e), code=2)
    password = _read_password(password_stdin)
    _validate_password_strength(password)
    updated = AuthFileSchema(
        username=current.username,
        password_hash=hash_password(password),
        created_at=current.created_at,
        last_password_changed_at=_now(),
    )
    try:
        atomic_write_auth_file(root, updated, force=True)
    except AuthCredentialsError as e:
        _exit(str(e), code=2)
    _append_admin_event(root, "auth.admin_password_reset", username=current.username, payload={})
    click.echo(f"✓ admin user '{current.username}' password reset")


@admin.command("remove", help="Disable the local admin auth.json file by renaming it.")
@click.option("--data-dir", type=click.Path(path_type=Path), help="Data directory for auth.json.")
@click.option("--confirm", is_flag=True, help="Required confirmation flag.")
def remove_cmd(data_dir: Path | None, confirm: bool) -> None:
    if not confirm:
        _exit("pass --confirm to disable auth.json", code=2)
    root = _data_dir(data_dir, create=False)
    auth_path = root / AUTH_FILENAME
    if not auth_path.exists() and not auth_path.is_symlink():
        _exit(f"{auth_path} not found", code=1)
    try:
        current = read_auth_file(data_dir=root)
    except AuthCredentialsError as e:
        _exit(str(e), code=2)
    backup = root / f"auth.json.disabled.{datetime.now(UTC).strftime('%Y%m%d-%H%M%S')}"
    try:
        os.rename(auth_path, backup)
        _fsync_dir(root)
    except OSError as e:
        _exit(f"failed to rename {auth_path}: {e}", code=2)
    _append_admin_event(root, "auth.admin_removed", username=current.username, payload={"backup_basename": backup.name})
    click.echo(f"✓ admin user '{current.username}' disabled; backup={backup.name}")


@admin.command("show", help="Show the active admin credential source.")
@click.option("--data-dir", type=click.Path(path_type=Path), help="Data directory for auth.json.")
@click.option("--json/--text", "json_output", default=False, show_default=True)
def show_cmd(data_dir: Path | None, json_output: bool) -> None:
    root = _data_dir(data_dir, create=False)
    try:
        credentials = load_auth_credentials(data_dir=root, env=os.environ, app_env=os.environ.get("APP_ENV", "prod"))
    except AuthCredentialsError as e:
        _exit(str(e), code=2)
    if credentials is None:
        _emit_json({"cli_schema_version": CLI_SCHEMA_VERSION, "error": "not_configured"}, err=True)
        sys.exit(1)
    payload = {
        "cli_schema_version": CLI_SCHEMA_VERSION,
        "instance_id": _instance_id(),
        "username": credentials.username,
        "source": credentials.source,
        "created_at": credentials.created_at.isoformat() if credentials.created_at else None,
        "last_password_changed_at": (
            credentials.last_password_changed_at.isoformat() if credentials.last_password_changed_at else None
        ),
    }
    if json_output:
        _emit_json(payload)
    else:
        click.echo(f"username={payload['username']}")
        click.echo(f"source={payload['source']}")
        click.echo(f"created_at={payload['created_at']}")
        click.echo(f"last_password_changed_at={payload['last_password_changed_at']}")


def _data_dir(data_dir: Path | None, *, create: bool) -> Path:
    root = data_dir or Path(os.environ.get("LOOM_DATA_DIR", ".loom-data"))
    if create:
        root.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(root, 0o700)
    return root


def _new_auth_doc(*, username: str, password: str) -> AuthFileSchema:
    now = _now()
    return AuthFileSchema(
        username=username,
        password_hash=hash_password(password),
        created_at=now,
        last_password_changed_at=now,
    )


def _read_password(password_stdin: bool) -> str:
    if password_stdin:
        if _stdin_is_tty():
            _exit("--password-stdin requires piped input; use the interactive prompt instead", code=2)
        return sys.stdin.readline().rstrip("\n")
    first = getpass.getpass("Password: ")
    second = getpass.getpass("Repeat password: ")
    if first == second:
        return first
    click.echo("Passwords did not match; try once more.", err=True)
    first = getpass.getpass("Password: ")
    second = getpass.getpass("Repeat password: ")
    if first != second:
        _exit("passwords did not match", code=1)
    return first


def _stdin_is_tty() -> bool:
    return sys.stdin.isatty()


def _validate_password_strength(password: str) -> None:
    categories = 0
    categories += any(ch.islower() for ch in password)
    categories += any(ch.isupper() for ch in password)
    categories += any(ch.isdigit() for ch in password)
    categories += any(not ch.isalnum() for ch in password)
    if len(password) < 10 or categories < 3:
        _exit(
            "Password must be at least 10 characters and include at least 3 of: uppercase, lowercase, digit, symbol",
            code=1,
        )


def _fsync_dir(data_dir: Path) -> None:
    dir_fd: int | None = None
    try:
        dir_fd = os.open(data_dir, os.O_RDONLY)
        os.fsync(dir_fd)
    finally:
        if dir_fd is not None:
            os.close(dir_fd)


def _emit_json(payload: dict[str, object], *, err: bool = False) -> None:
    click.echo(json.dumps(payload, ensure_ascii=False, indent=2), err=err)


def _append_admin_event(root: Path, event_type: str, *, username: str, payload: dict[str, object]) -> None:
    writer = _archive_writer(root)
    if writer is None:
        return
    writer.append(
        AUTH_ARCHIVE_SESSION_ID,
        actor_id="auth",
        event_type=cast(ArchiveEventType, event_type),
        payload={"username_hmac": writer.hmac_text(username), **payload},
    )


def _archive_writer(root: Path) -> InstanceArchiveWriter | None:
    fernet_key = os.environ.get("LOOM_FERNET_KEY")
    if not fernet_key:
        return None
    settings = Settings(
        data_dir=root,
        app_env=os.environ.get("APP_ENV", "prod"),
        fernet_key=fernet_key,
        instance_id=_instance_id(),
    )
    return InstanceArchiveWriter(
        ArchiveWriter(root),
        instance_id=settings.instance_id,
        hmac_key=settings.archive_hmac_key(),
    )


def _exit(message: str, *, code: int) -> NoReturn:
    click.echo(message, err=True)
    sys.exit(code)


def _instance_id() -> str:
    return os.environ.get("LOOM_INSTANCE_ID") or socket.gethostname()


def _now() -> datetime:
    return datetime.now(UTC)
