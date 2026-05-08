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

    def to_zip_bytes(self) -> bytes:
        """Render bundle to a ZIP archive [bytes].

        Each entry in self.files is dumped as YAML and stored under
        '<bundle_name>/<relative-path>' in the zip. Mirrors the customer
        sample folder layout exactly.

        ZIP entries use a deterministic timestamp so equal bundle contents
        produce byte-identical zips.
        """
        import io
        import zipfile

        import yaml  # type: ignore[import-untyped]

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for rel_path, content in sorted(self.files.items()):
                full = f"{self.bundle_name}/{rel_path}"
                yaml_text = yaml.safe_dump(
                    content,
                    sort_keys=False,
                    allow_unicode=True,
                    default_flow_style=False,
                )
                info = zipfile.ZipInfo(full, date_time=(1980, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                # Set UTF-8 filename flag (bit 11 of general purpose bit flag).
                # Hiagent's Java zip parser fails with cryptic "No signature
                # found after EOCD record" when filenames contain non-ASCII
                # bytes without this flag set. Always-on is safe for ASCII too.
                info.flag_bits |= 0x800
                # Standard Unix file permissions (rw-r--r--) so Java parsers
                # don't choke on default external_attr=0.
                info.external_attr = (0o644 & 0xFFFF) << 16
                zf.writestr(info, yaml_text.encode("utf-8"))
        return buf.getvalue()
