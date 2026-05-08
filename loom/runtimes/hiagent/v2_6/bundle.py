"""HiagentBundle data structure - the artifact the compiler emits.

Hiagent Agent import accepts a ZIP whose entries are root-relative:
`index.yaml`, `agent/<name>.yaml`, and optional `model/` / `knowledge/`
sidecar YAML files. The import parser rejects bundles nested under a
top-level directory with a misleading "No signature found after EOCD
record" error, so ZIP serialization intentionally mirrors the working
customer exports' entry layout and metadata.
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

        Used by the Workflow Import path (single .json file). Sub-task D pivots
        to Agent Import (zip bundle) as the primary path; this method stays for
        the workflow-import variant.
        """
        import json

        wf = self.workflow_files()
        if not wf:
            raise ValueError(
                "HiagentBundle.to_workflow_json: no workflow in bundle.files"
            )
        _, content = wf[0]
        return json.dumps(content, ensure_ascii=False, indent=2)

    def to_agent_bundle_zip_bytes(self) -> bytes:
        """Render the bundle to a multi-file Agent-import ZIP archive.

        On-disk layout (matches customer 用户维修方案 / 车联网故障问数 samples):

            index.yaml
            agent/<name>.yaml
            model/<name>.yaml       # optional, when binding has model IDs
            knowledge/<name>.yaml   # optional, when binding has dataset IDs

        Each entry's content is dumped as YAML. The ZIP is written through a
        non-seekable buffer so Python emits data descriptors (flag bit 0x8),
        and every entry carries Info-ZIP's UT extended timestamp extra field,
        matching Hiagent's working exports more closely.
        """
        import io
        import struct
        import time
        import zipfile

        import yaml  # type: ignore[import-untyped]

        class _NonSeekableBytesIO(io.BytesIO):
            def seekable(self) -> bool:
                return False

            def seek(self, *args: Any, **kwargs: Any) -> int:
                raise io.UnsupportedOperation("non-seekable")

        buf = _NonSeekableBytesIO()
        mtime_int = int(time.time())
        # ZIP's DOS timestamp stores seconds at 2-second granularity. Keep
        # the UT extra and date_time exactly consistent by using an even mtime.
        mtime_int -= mtime_int % 2
        timestamp = time.localtime(mtime_int)[:6]
        ut_extra = struct.pack("<HHB", 0x5455, 5, 0x01) + struct.pack("<I", mtime_int)
        with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for rel_path, content in self.files.items():
                yaml_text = yaml.safe_dump(
                    content,
                    sort_keys=False,
                    allow_unicode=True,
                    default_flow_style=False,
                )
                info = zipfile.ZipInfo(rel_path, date_time=timestamp)
                info.compress_type = zipfile.ZIP_DEFLATED
                info.create_system = 0
                info.create_version = 20
                info.extract_version = 20
                info.extra = ut_extra
                zf.writestr(info, yaml_text.encode("utf-8"))
        return _zero_external_attrs(buf.getvalue())


def _zero_external_attrs(raw: bytes) -> bytes:
    """Set central-directory external attributes to zero.

    Python's zipfile fills 0600 attrs when writing from a ZipInfo with attrs
    unset; Hiagent exports use external_attr=0. Patch only central-directory
    headers, leaving local file headers and payloads untouched.
    """
    import struct

    data = bytearray(raw)
    eocd = data.rfind(b"PK\x05\x06")
    if eocd < 0:
        return raw
    cd_size = struct.unpack_from("<I", data, eocd + 12)[0]
    cd_offset = struct.unpack_from("<I", data, eocd + 16)[0]
    pos = cd_offset
    end = cd_offset + cd_size
    while pos < end:
        if data[pos : pos + 4] != b"PK\x01\x02":
            break
        name_len, extra_len, comment_len = struct.unpack_from("<HHH", data, pos + 28)
        data[pos + 38 : pos + 42] = b"\x00\x00\x00\x00"
        pos += 46 + name_len + extra_len + comment_len
    return bytes(data)
