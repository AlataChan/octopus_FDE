"""HiagentBundle data structure - the artifact the compiler emits.

Hiagent has two import shapes (verified against customer-supplied samples):

1. **Workflow zip** (single-yaml; what `loom compile --target hiagent` emits):
   The zip root contains exactly ONE yaml file holding a workflow document
   (DLVersion / Depends / DisplayName / FlowType / ID / MetaType / Nodes /
   WorkspaceID at top level). This is what the customer's "Export workflow"
   button produces; it's also what "Import workflow" expects.

2. **App bundle** (multi-file; out of MVP scope):
   The zip root contains a single bundle directory with `index.yaml` +
   `workflow/`, `agent/`, `knowledge/`, `model/`, `asset/upload/` subdirs.
   This is for "Export App" / "Import App"; supporting it requires far
   more dependent-resource generation than v1 needs.

For MVP we ONLY emit shape (1). The HiagentBundle in-memory model still
carries `index.yaml` + `workflow/<name>.yaml` shape internally (matching
ADR 0024) but `to_zip_bytes()` flattens to shape (1) at write time. This
keeps tests readable (they assert against the structured `files` dict)
while the on-disk artifact is what Hiagent actually accepts.
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

    def to_zip_bytes(self) -> bytes:
        """Render the bundle's primary workflow as a Hiagent workflow-import zip.

        On-disk shape (verified against customer's 小芸维修专家-<ts>.zip):
        - Exactly one yaml entry at zip root, named '<DisplayName>-<ts>.yaml'
        - The entry's content IS the workflow yaml (DLVersion: v2 ... Nodes ...)
        - No 'index.yaml', no subdirectories.
        - ZIP uses deterministic 1980-01-01 timestamps so equal inputs produce
          byte-identical zips.

        The picked yaml is the first 'workflow/*.yaml' entry in `self.files`.
        Raises ValueError if no workflow yaml is present.
        """
        import io
        import zipfile

        import yaml  # type: ignore[import-untyped]

        wf = self.workflow_files()
        if not wf:
            raise ValueError(
                "HiagentBundle.to_zip_bytes: no workflow yaml in bundle.files; "
                "expected at least one entry under 'workflow/<name>.yaml'"
            )
        # Single-workflow shape only for MVP; multi-workflow bundles would
        # be App-bundle territory (out of scope per module docstring).
        rel_path, content = wf[0]
        # Filename in zip uses the workflow's DisplayName when available,
        # else the original basename. Mirrors customer sample naming.
        display_name = (
            content.get("DisplayName") if isinstance(content, dict) else None
        ) or rel_path.split("/")[-1].rsplit(".", 1)[0]
        # Hiagent samples use '-' separators in the export filename (e.g.,
        # '小芸维修专家-20260506-113013.yaml'). bundle_name already contains a
        # timestamp suffix from the compiler; reuse the trailing chunk.
        ts_suffix = self.bundle_name.rsplit("_", 1)[-1] if "_" in self.bundle_name else ""
        zip_entry_name = (
            f"{display_name}-{ts_suffix}.yaml" if ts_suffix else f"{display_name}.yaml"
        )

        yaml_text = yaml.safe_dump(
            content,
            sort_keys=False,
            allow_unicode=True,
            default_flow_style=False,
        )

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            info = zipfile.ZipInfo(zip_entry_name, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.flag_bits |= 0x800  # UTF-8 filename flag
            info.external_attr = (0o644 & 0xFFFF) << 16
            zf.writestr(info, yaml_text.encode("utf-8"))
        return buf.getvalue()
