from pathlib import Path
import json

import pytest

from loom.registry.templates import TemplateCatalog, TemplateLoadError
from loom.runtimes.dify.v1_14.compiler import compile_ir as compile_dify
from loom.runtimes.hiagent.binding import HiagentBinding
from loom.runtimes.hiagent.v2_6.compiler import compile_ir as compile_hiagent

ROOT = Path(__file__).resolve().parents[2]
INDEX_PATH = ROOT / "registry" / "v1" / "templates" / "index.json"


def test_template_catalog_loads_indexed_v04_templates():
    catalog = TemplateCatalog.load()
    rows = catalog.list()
    expected_count = len(json.loads(INDEX_PATH.read_text())["templates"])

    assert len(rows) == expected_count
    assert {row.ir["ir_version"] for row in rows} == {"0.4"}
    assert catalog.list(target="dify")
    assert all("_internal_source" not in row.ir for row in rows)


def test_templates_validate_and_compile_to_declared_targets_without_placeholders():
    catalog = TemplateCatalog.load()
    binding = HiagentBinding.load(ROOT / "tests" / "fixtures" / "test.hiagent.yaml")

    for row in catalog.list():
        ir = row.ir_document
        for target in row.entry.compile_targets:
            if target == "hiagent":
                bundle, warnings = compile_hiagent(ir, binding)
                raw = bundle.to_zip_bytes()
                assert b"TODO" not in raw
                assert b"placeholder" not in raw.lower()
            else:
                text, warnings = compile_dify(ir)
                assert "TODO" not in text
                assert "placeholder" not in text.lower()
            assert all(warning.code for warning in warnings)


def test_corrupted_template_file_fails_catalog_load(tmp_path):
    (tmp_path / "index.json").write_text(
        """
        {
          "version": "sha:0000000",
          "templates": [{
            "id": "bad",
            "name": {"zh": "坏模板", "en": "Bad"},
            "description": {"zh": "坏", "en": "Bad"},
            "tags": [],
            "ir_file": "bad.yaml",
            "scopes": ["ecommerce/kb"],
            "compile_targets": ["hiagent"],
            "_internal_source": "test",
            "_internal_pattern": "bad"
          }]
        }
        """
    )
    (tmp_path / "bad.yaml").write_text("ir_version: [")

    with pytest.raises(TemplateLoadError, match="failed to load template bad"):
        TemplateCatalog.load(tmp_path)
