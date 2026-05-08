"""HiagentBundle data structure.

The validated customer path is TOP-signed API push. This bundle remains a
small in-memory carrier for inspection and tests; it does not serialize to the
retired external ZIP import format.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, cast


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
