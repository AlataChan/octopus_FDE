"""Service settings and dependency helpers."""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path

from cryptography.fernet import Fernet
from fastapi import Header

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class Actor:
    id: str = "single-user"
    role: str = "fde"


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    app_env: str = "dev"
    fernet_key: str | None = None
    binding_dir: Path = Path("config/customers")

    @classmethod
    def from_env(cls) -> Settings:
        app_env = os.environ.get("APP_ENV", "dev")
        key = os.environ.get("LOOM_FERNET_KEY")
        if app_env != "dev" and not key:
            raise RuntimeError("LOOM_FERNET_KEY is required when APP_ENV is prod")
        if app_env == "dev" and not key:
            key = Fernet.generate_key().decode("ascii")
            LOGGER.warning("LOOM_FERNET_KEY missing in dev; using an ephemeral per-process key")
        return cls(
            data_dir=Path(os.environ.get("LOOM_DATA_DIR", ".loom-data")),
            app_env=app_env,
            fernet_key=key,
            binding_dir=Path(os.environ.get("LOOM_BINDING_DIR", "config/customers")),
        )

    def ensure_data_dir(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(self.data_dir, 0o700)

    def fernet(self) -> Fernet:
        key = self.fernet_key
        if not key:
            if self.app_env == "dev":
                key = Fernet.generate_key().decode("ascii")
            else:
                raise RuntimeError("LOOM_FERNET_KEY is required")
        return Fernet(key.encode("ascii"))


def get_actor(x_actor_id: str | None = Header(default=None, alias="X-Actor-Id")) -> Actor:
    """MVP attribution seam; this is not authentication."""
    return Actor(id=x_actor_id or "single-user", role="fde")
