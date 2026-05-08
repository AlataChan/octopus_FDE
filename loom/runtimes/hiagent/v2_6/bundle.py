"""HiagentBundle data structure - the artifact the compiler emits.

Per ADR 0024 §Bundle structure. Sub-task C [next] writes this to disk
as a directory tree + zip; this module only models the structure.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, cast


@dataclass(frozen=True)
class HiagentBundle:
    """A multi-file Hiagent v2.6 export bundle [in-memory representation].

    `files` maps relative path inside the bundle [e.g. 'index.yaml',
    'workflow/<name>.yaml'] to the parsed YAML content [dict / list / scalar].
    Sub-task C will yaml.dump each file and zip the tree.
    """
    bundle_name: str
    files: dict[str, Any] = field(default_factory=dict)

    @property
    def index(self) -> dict[str, Any]:
        if "index.yaml" not in self.files:
            raise KeyError("bundle missing index.yaml")
        return cast("dict[str, Any]", self.files["index.yaml"])

    def workflow_files(self) -> list[tuple[str, dict[str, Any]]]:
        """Return [path, content] tuples for every workflow/*.yaml entry."""
        return [
            (p, cast("dict[str, Any]", c))
            for p, c in self.files.items()
            if p.startswith("workflow/")
        ]
