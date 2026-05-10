"""HiagentBundle data structure.

The validated customer path is TOP-signed API push. This bundle remains a
small in-memory carrier for inspection and tests; it does not serialize to the
retired external ZIP import format.
"""
from __future__ import annotations

import hashlib
import io
import zipfile
from dataclasses import dataclass, field
from typing import Any, cast

import yaml  # type: ignore[import-untyped]


@dataclass(frozen=True)
class HiagentBundle:
    """A Hiagent v2.6 in-memory bundle."""

    bundle_name: str
    files: dict[str, Any] = field(default_factory=dict)

    @property
    def index(self) -> dict[str, Any]:
        if "index.yaml" not in self.files:
            raise KeyError("bundle missing index.yaml")
        return cast("dict[str, Any]", self.files["index.yaml"])

    def agent_files(self) -> list[tuple[str, dict[str, Any]]]:
        """Return [path, content] tuples for every agent/*.yaml entry."""
        return [
            (path, cast("dict[str, Any]", content))
            for path, content in self.files.items()
            if path.startswith("agent/")
        ]

    def to_zip_bytes(self) -> bytes:
        """Render an importable Hiagent ZIP bundle.

        See `docs/runtimes/hiagent/zip-import-format.md`: entries must be
        flat at archive root and Hiagent requires a 32-byte ASCII md5 trailer
        appended after EOCD. Do not add a bundle-name directory prefix.
        """
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for rel_path, content in self.files.items():
                if isinstance(content, bytes):
                    payload = content
                else:
                    payload = yaml.safe_dump(
                        content,
                        sort_keys=False,
                        allow_unicode=True,
                    ).encode("utf-8")
                zf.writestr(rel_path, payload)

        zip_body = buf.getvalue()
        trailer = hashlib.md5(zip_body).hexdigest().encode("ascii")
        return zip_body + trailer
