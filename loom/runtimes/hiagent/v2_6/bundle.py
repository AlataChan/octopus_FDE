"""HiagentBundle data structure - the artifact the compiler emits.

Hiagent has TWO import paths (verified by user 2026-05-08 with screenshot
of import dialog):

1. **Workflow import** (what we target for MVP):
   Accepts a single **.json** file (NOT a zip!). The JSON content is the
   workflow document directly: top-level `DLVersion: v2`, `MetaType: Workflow`,
   `FlowType: Workflow`, `DisplayName`, `ID`, `Nodes[]`, `Depends`, `WorkspaceID`.
   This is the same shape as the workflow.yaml from the App-bundle export,
   just JSON-serialized.

2. **Agent import** (out of MVP scope):
   Accepts a multi-file **.zip** containing index.yaml + agent/ + knowledge/
   + model/ + asset/upload/. Used for full chat-agent imports. We may add
   support in v1.1 once Workflow import is validated end-to-end.

The earlier `to_zip_bytes()` we wrote targeted neither path correctly —
Hiagent's "No signature found after EOCD record" error was its way of
saying "this isn't a valid Agent zip". The fix: emit JSON via
`to_workflow_json()` and skip zip entirely for Workflow import.

The HiagentBundle in-memory model still carries the structured
`index.yaml` + `workflow/<name>.yaml` files dict (matching ADR 0024) for
clarity at the compiler level; serialization picks one entry depending on
the requested format.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, cast


@dataclass(frozen=True)
class HiagentBundle:
    """A Hiagent v2.6 bundle [in-memory representation].

    `files` is a logical tree: 'index.yaml' + 'workflow/<name>.yaml' entries.
    `to_zip_bytes()` writes the on-disk Hiagent workflow-zip shape (single
    yaml at zip root, no subdirs).
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

    def to_workflow_json(self) -> str:
        """Serialize the primary workflow as a Hiagent workflow-import JSON string.

        Hiagent's "Import Workflow" dialog accepts a .json file directly
        (verified 2026-05-08 from import-dialog screenshot). The JSON content
        is the workflow document itself: top-level DLVersion / MetaType:
        Workflow / FlowType / DisplayName / ID / Nodes[] / Depends / WorkspaceID.

        Returns indented UTF-8 JSON (Hiagent accepts both compact and
        pretty-printed). Raises ValueError if no workflow entry is present.
        """
        import json

        wf = self.workflow_files()
        if not wf:
            raise ValueError(
                "HiagentBundle.to_workflow_json: no workflow in bundle.files; "
                "expected at least one entry under 'workflow/<name>.yaml'"
            )
        _, content = wf[0]
        return json.dumps(content, ensure_ascii=False, indent=2)
