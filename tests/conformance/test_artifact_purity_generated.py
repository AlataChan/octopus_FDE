import io
import json
import re
import zipfile
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]

from loom.ir.models import IRDocument
from loom.runtimes.dify.v1_14.compiler import compile_ir as compile_dify
from loom.runtimes.hiagent.binding import HiagentBinding
from loom.runtimes.hiagent.v2_6.compiler import compile_ir_chatflow

ROOT = Path(__file__).resolve().parents[2]
FORBIDDEN_TERMS = re.compile(rb"telemetry|phone\.home|callback|webhook|analytics|track", re.IGNORECASE)
URL_RE = re.compile(r"https?://[^\s\"']+")


def test_generated_hiagent_and_dify_artifacts_stay_pure():
    ir = IRDocument.model_validate(
        json.loads((ROOT / "examples" / "ir" / "01-ecommerce-customer-faq.json").read_text())
    )
    binding = HiagentBinding.load(ROOT / "tests" / "fixtures" / "test.hiagent.yaml")
    source_urls = _urls_in_obj(ir.model_dump(by_alias=True))
    ir_node_ids = {node.id for node in ir.nodes}
    ir_rationales = {node.rationale for node in ir.nodes}

    hiagent_raw = compile_ir_chatflow(ir, binding).to_zip_bytes()
    assert not FORBIDDEN_TERMS.search(hiagent_raw)
    hiagent_docs = _yaml_docs_from_hiagent_zip(hiagent_raw)
    for name, doc in hiagent_docs:
        assert not FORBIDDEN_TERMS.search(yaml.safe_dump(doc, sort_keys=False, allow_unicode=True).encode("utf-8"))
        _assert_no_new_urls(name, doc, source_urls)
        if name.startswith("agent/"):
            _assert_hiagent_nodes_have_provenance(doc, ir_rationales)

    dify_raw = compile_dify(ir).encode("utf-8")
    assert not FORBIDDEN_TERMS.search(dify_raw)
    dify_doc = yaml.safe_load(dify_raw)
    _assert_no_new_urls("dify.yaml", dify_doc, source_urls)
    _assert_dify_nodes_have_provenance(dify_doc, ir_node_ids)


def _yaml_docs_from_hiagent_zip(raw: bytes) -> list[tuple[str, Any]]:
    with zipfile.ZipFile(io.BytesIO(raw[:-32])) as zf:
        return [
            (name, yaml.safe_load(zf.read(name)))
            for name in zf.namelist()
            if name.endswith(".yaml")
        ]


def _assert_no_new_urls(name: str, doc: Any, source_urls: set[str]) -> None:
    for url in URL_RE.findall(yaml.safe_dump(doc, sort_keys=False, allow_unicode=True)):
        assert url in source_urls, f"{name} contains unexpected URL {url!r}"


def _assert_hiagent_nodes_have_provenance(doc: Any, ir_rationales: set[str]) -> None:
    nodes = doc.get("AppConfig", {}).get("ChatFlowDetail", {}).get("Nodes", [])
    for node in nodes:
        assert node.get("Description") in ir_rationales


def _assert_dify_nodes_have_provenance(doc: Any, ir_node_ids: set[str]) -> None:
    graph_nodes = doc["workflow"]["graph"]["nodes"]
    for node in graph_nodes:
        assert node["id"] in ir_node_ids


def _urls_in_obj(obj: Any) -> set[str]:
    out: set[str] = set()
    for value in _walk_strings(obj):
        out.update(URL_RE.findall(value))
    return out


def _walk_strings(obj: Any) -> Iterable[str]:
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for value in obj.values():
            yield from _walk_strings(value)
    elif isinstance(obj, list):
        for value in obj:
            yield from _walk_strings(value)
