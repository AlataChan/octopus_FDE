import io
import json
import struct
import time
import zipfile
from pathlib import Path

import pytest
import yaml

from loom.ir.models import IRDocument
from loom.runtimes.hiagent.binding import HiagentBinding
from loom.runtimes.hiagent.v2_6.bundle import HiagentBundle
from loom.runtimes.hiagent.v2_6.compiler import compile_ir

ROOT = Path(__file__).resolve().parents[4]


@pytest.fixture
def sample_bundle() -> HiagentBundle:
    ir = IRDocument.model_validate(
        json.loads((ROOT / "examples" / "ir" / "01-ecommerce-customer-faq.json").read_text())
    )
    binding = HiagentBinding(
        customer="test",
        target="hiagent",
        workspace_id="d31pcnoboot936af1tsg",
    )
    return compile_ir(ir, binding)


def _zip_infos(bundle: HiagentBundle) -> list[zipfile.ZipInfo]:
    with zipfile.ZipFile(io.BytesIO(bundle.to_agent_bundle_zip_bytes())) as zf:
        return zf.infolist()


def _zip_yaml(bundle: HiagentBundle, name: str) -> dict:
    with zipfile.ZipFile(io.BytesIO(bundle.to_agent_bundle_zip_bytes())) as zf:
        return yaml.safe_load(zf.read(name))


def _local_extra(raw: bytes, info: zipfile.ZipInfo) -> bytes:
    offset = info.header_offset
    assert raw[offset : offset + 4] == b"PK\x03\x04"
    name_len, extra_len = struct.unpack_from("<HH", raw, offset + 26)
    start = offset + 30 + name_len
    return raw[start : start + extra_len]


def test_agent_zip_entries_are_root_relative_with_index_first(sample_bundle: HiagentBundle):
    names = [i.filename for i in _zip_infos(sample_bundle)]
    assert names[0] == "index.yaml"
    assert any(n.startswith("agent/") and n.endswith(".yaml") for n in names)
    assert not any(n.startswith(sample_bundle.bundle_name + "/") for n in names)


def test_agent_zip_has_index_before_agent(sample_bundle: HiagentBundle):
    names = [i.filename for i in _zip_infos(sample_bundle)]
    agent_index = next(i for i, n in enumerate(names) if n.startswith("agent/"))
    assert names.index("index.yaml") < agent_index


def test_agent_zip_has_no_workflow_entry_for_chat_mode(sample_bundle: HiagentBundle):
    names = [i.filename for i in _zip_infos(sample_bundle)]
    assert not any(n.startswith("workflow/") for n in names)


def test_agent_zip_contains_complete_gold_style_folder_skeleton(sample_bundle: HiagentBundle):
    names = [i.filename for i in _zip_infos(sample_bundle)]
    assert any(n.startswith("agent/") for n in names)
    assert any(n.startswith("knowledge/") for n in names)
    assert any(n.startswith("model/") for n in names)
    assert any(n.startswith("asset/upload/full/") for n in names)
    assert len(names) >= 5


def test_binary_asset_entry_is_not_yaml_serialized(sample_bundle: HiagentBundle):
    raw = sample_bundle.to_agent_bundle_zip_bytes()
    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        asset_name = next(n for n in zf.namelist() if n.startswith("asset/upload/full/"))
        assert zf.read(asset_name) == b"\x00"


def test_zip_metadata_matches_hiagent_export_conventions(sample_bundle: HiagentBundle):
    infos = _zip_infos(sample_bundle)
    for info in infos:
        assert info.compress_type == zipfile.ZIP_DEFLATED
        assert info.create_system == 0
        assert info.create_version == 20
        assert info.extract_version == 20
        assert info.external_attr == 0
        assert info.flag_bits & 0x8


def test_zip_entries_have_info_zip_ut_extra_in_central_and_local_headers(
    sample_bundle: HiagentBundle,
):
    raw = sample_bundle.to_agent_bundle_zip_bytes()
    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        infos = zf.infolist()
    for info in infos:
        assert info.extra[:5] == b"UT\x05\x00\x01"
        assert len(info.extra) == 9
        assert _local_extra(raw, info) == info.extra
        mtime = struct.unpack("<I", info.extra[5:9])[0]
        assert info.date_time == time.localtime(mtime)[:6]


def test_ascii_and_non_ascii_filename_flags_match_hiagent_exports():
    bundle = HiagentBundle(
        bundle_name="bn",
        files={
            "index.yaml": {"DLVersion": "0.0.1"},
            "agent/用户维修方案.yaml": {"MetaType": "Agent"},
        },
    )
    with zipfile.ZipFile(io.BytesIO(bundle.to_agent_bundle_zip_bytes())) as zf:
        infos = {info.filename: info for info in zf.infolist()}
    assert infos["index.yaml"].flag_bits == 0x0008
    assert infos["agent/用户维修方案.yaml"].flag_bits == 0x0808


def test_index_yaml_has_required_agent_fields_at_zip_root(sample_bundle: HiagentBundle):
    idx = _zip_yaml(sample_bundle, "index.yaml")
    assert idx["DLVersion"] == "0.0.1"
    assert idx["FromWorkspaceID"] == "d31pcnoboot936af1tsg"
    assert idx["MainMeta"] == "Agent"
    assert idx["MainMetaName"]
    assert idx["MainUniqueName"]


def test_agent_yaml_uses_single_chat_agent_shape(sample_bundle: HiagentBundle):
    agent_path = next(i.filename for i in _zip_infos(sample_bundle) if i.filename.startswith("agent/"))
    agent = _zip_yaml(sample_bundle, agent_path)
    assert agent["MetaType"] == "Agent"
    assert agent["AppInfo"]["AppType"] == "Chat"
    assert agent["AppInfo"]["AgentMode"] == "Single"
    app_config = agent["AppConfig"]
    assert app_config["AgentMode"] == "Single"
    assert app_config["ChatFlowDetail"] is None
    assert app_config["MultiAgentConfig"] is None
    single = app_config["SingleAgentConfig"]
    assert isinstance(single, dict)
    assert "ChatAdvancedConfig" in single
    assert "FeedbackTagConfig" in single["ChatAdvancedConfig"]
    assert "OpeningConfig" in single["ChatAdvancedConfig"]
    assert "UploadConfig" in single["ChatAdvancedConfig"]
    assert "KnowledgeConfig" in single
    assert "ModelConfig" in single


def test_agent_zip_entries_are_valid_yaml(sample_bundle: HiagentBundle):
    raw = sample_bundle.to_agent_bundle_zip_bytes()
    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        for name in zf.namelist():
            if not name.endswith(".yaml"):
                continue
            assert yaml.safe_load(zf.read(name)) is not None


def test_to_workflow_json_raises_when_no_workflow():
    b = HiagentBundle(bundle_name="bn", files={"index.yaml": {"a": 1}})
    with pytest.raises(ValueError, match="no workflow"):
        b.to_workflow_json()
