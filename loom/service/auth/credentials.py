"""File-backed local admin credentials for single-user deployments."""
from __future__ import annotations

import contextlib
import json
import logging
import os
import stat
from dataclasses import dataclass
from datetime import datetime  # noqa: TC003
from typing import TYPE_CHECKING, Annotated, Literal

from pydantic import BaseModel, ConfigDict, StringConstraints, ValidationError

from loom.service.auth.password import ScryptPasswordError, validate_scrypt_hash

if TYPE_CHECKING:
    from collections.abc import Mapping
    from pathlib import Path

LOGGER = logging.getLogger(__name__)
AUTH_FILENAME = "auth.json"


class AuthCredentialsError(ValueError):
    """Raised when admin credentials cannot be safely loaded or written."""


class AuthFileSchema(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1"] = "1"
    username: Annotated[str, StringConstraints(min_length=1, max_length=200)]
    password_hash: str
    created_at: datetime
    last_password_changed_at: datetime


@dataclass(frozen=True)
class AuthCredentials:
    username: str
    password_hash: str
    source: Literal["env", "file"]
    created_at: datetime | None = None
    last_password_changed_at: datetime | None = None


def load_auth_credentials(
    *,
    data_dir: Path,
    env: Mapping[str, str | None],
    app_env: str,
) -> AuthCredentials | None:
    auth_path = data_dir / AUTH_FILENAME
    if auth_path.exists() or auth_path.is_symlink():
        _validate_auth_path(auth_path, app_env=app_env)

    env_username = env.get("LOOM_AUTH_USERNAME")
    env_hash = env.get("LOOM_AUTH_PASSWORD_HASH")
    if bool(env_username) != bool(env_hash):
        raise AuthCredentialsError("LOOM_AUTH_USERNAME and LOOM_AUTH_PASSWORD_HASH must both be set")
    if env_username and env_hash:
        if auth_path.exists():
            LOGGER.info("Admin credentials configured in env and auth.json; env credentials take precedence")
        try:
            _validate_hash(env_hash, auth_path=None)
        except ScryptPasswordError as e:
            raise AuthCredentialsError(str(e)) from e
        return AuthCredentials(username=env_username, password_hash=env_hash, source="env")

    if not auth_path.exists():
        return None

    try:
        raw = json.loads(auth_path.read_text(encoding="utf-8"))
        doc = AuthFileSchema.model_validate(raw)
        _validate_hash(doc.password_hash, auth_path=auth_path)
    except (OSError, json.JSONDecodeError, ValidationError, ScryptPasswordError) as e:
        raise AuthCredentialsError(f"failed to load {auth_path}: {e}") from e

    return AuthCredentials(
        username=doc.username,
        password_hash=doc.password_hash,
        source="file",
        created_at=doc.created_at,
        last_password_changed_at=doc.last_password_changed_at,
    )


def read_auth_file(*, data_dir: Path, app_env: str = "prod") -> AuthFileSchema:
    auth_path = data_dir / AUTH_FILENAME
    _validate_auth_path(auth_path, app_env=app_env)
    try:
        raw = json.loads(auth_path.read_text(encoding="utf-8"))
        doc = AuthFileSchema.model_validate(raw)
        _validate_hash(doc.password_hash, auth_path=auth_path)
    except (OSError, json.JSONDecodeError, ValidationError, ScryptPasswordError) as e:
        raise AuthCredentialsError(f"failed to load {auth_path}: {e}") from e
    return doc


def atomic_write_auth_file(data_dir: Path, doc: AuthFileSchema, *, force: bool = False) -> Path:
    _validate_data_dir(data_dir)
    auth_path = data_dir / AUTH_FILENAME
    if auth_path.is_symlink():
        raise AuthCredentialsError(f"refusing symlink at {auth_path}")
    if auth_path.exists() and not force:
        raise AuthCredentialsError(f"{auth_path} already exists; use reset-password or --force")

    payload = (doc.model_dump_json(indent=2) + "\n").encode("utf-8")
    tmp_path = data_dir / f".auth.json.tmp.{os.getpid()}"
    fd: int | None = None
    try:
        flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_NOFOLLOW", 0)
        fd = os.open(tmp_path, flags, 0o600)
        _write_all(fd, payload)
        os.fsync(fd)
        os.close(fd)
        fd = None
        os.rename(tmp_path, auth_path)
        _fsync_dir(data_dir)
        _validate_auth_path(auth_path, app_env="prod")
        return auth_path
    except AuthCredentialsError:
        raise
    except OSError as e:
        raise AuthCredentialsError(f"failed to write {auth_path}: {e}") from e
    finally:
        if fd is not None:
            with contextlib.suppress(OSError):
                os.close(fd)
        if tmp_path.exists() or tmp_path.is_symlink():
            with contextlib.suppress(OSError):
                tmp_path.unlink()


def _validate_hash(encoded: str, *, auth_path: Path | None) -> None:
    try:
        validate_scrypt_hash(encoded)
    except ScryptPasswordError as e:
        if auth_path is None:
            raise
        raise ScryptPasswordError(f"{auth_path}: {e}") from e


def _validate_data_dir(data_dir: Path) -> None:
    try:
        st = os.lstat(data_dir)
    except OSError as e:
        raise AuthCredentialsError(f"data directory does not exist: {data_dir}") from e
    if not stat.S_ISDIR(st.st_mode):
        raise AuthCredentialsError(f"data directory is not a directory: {data_dir}")
    if st.st_mode & 0o077:
        raise AuthCredentialsError(f"data directory must not be more permissive than 0700: {data_dir}")


def _validate_auth_path(auth_path: Path, *, app_env: str) -> None:
    try:
        st = os.lstat(auth_path)
    except OSError as e:
        raise AuthCredentialsError(f"failed to inspect {auth_path}: {e}") from e
    if stat.S_ISLNK(st.st_mode):
        raise AuthCredentialsError(f"refusing symlink at {auth_path}")
    if not stat.S_ISREG(st.st_mode):
        raise AuthCredentialsError(f"{auth_path} must be a regular file")
    mode = st.st_mode & 0o777
    if mode != 0o600:
        message = f"{auth_path} permissions must be mode 0600, got {mode:04o}"
        if app_env == "dev":
            LOGGER.warning("auth.json permissions warning: %s", message)
        else:
            raise AuthCredentialsError(message)


def _write_all(fd: int, payload: bytes) -> None:
    view = memoryview(payload)
    while view:
        written = os.write(fd, view)
        if written <= 0:
            raise OSError("short write")
        view = view[written:]


def _fsync_dir(data_dir: Path) -> None:
    dir_fd: int | None = None
    try:
        dir_fd = os.open(data_dir, os.O_RDONLY)
        os.fsync(dir_fd)
    finally:
        if dir_fd is not None:
            os.close(dir_fd)
