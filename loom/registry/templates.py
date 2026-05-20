"""Template gallery loader and validation."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import yaml  # type: ignore[import-untyped]
from pydantic import BaseModel, ConfigDict, Field

from loom.ir.models import IRDocument
from loom.ir.schema import validate as validate_schema
from loom.validator.registry import Registry, RegistryEntryNotFound
from loom.validator.validate import validate

TEMPLATES_DIR = Path(__file__).resolve().parents[2] / "registry" / "v1" / "templates"
Target = Literal["hiagent", "dify"]


class TemplateLoadError(RuntimeError):
    pass


class LocalizedText(BaseModel):
    zh: str
    en: str


class TemplateIndexEntry(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    name: LocalizedText
    description: LocalizedText
    tags: list[str]
    ir_file: str
    scopes: list[str]
    compile_targets: list[Target]
    internal_source: str = Field(alias="_internal_source")
    internal_pattern: str = Field(alias="_internal_pattern")


class TemplateIndex(BaseModel):
    version: str
    templates: list[TemplateIndexEntry]


@dataclass(frozen=True)
class TemplateRecord:
    entry: TemplateIndexEntry
    ir: dict

    @property
    def ir_document(self) -> IRDocument:
        return IRDocument.model_validate(self.ir)


class TemplateCatalog:
    def __init__(self, *, version: str, records: dict[str, TemplateRecord]):
        self.version = version
        self._records = records

    @classmethod
    def load(cls, root: Path = TEMPLATES_DIR) -> TemplateCatalog:
        try:
            raw_index = json.loads((root / "index.json").read_text())
            index = TemplateIndex.model_validate(raw_index)
        except Exception as e:  # noqa: BLE001 - boot should report any catalog defect clearly
            raise TemplateLoadError(f"failed to load template index: {e}") from e

        registry = Registry.load("v1")
        records: dict[str, TemplateRecord] = {}
        for entry in index.templates:
            if entry.id in records:
                raise TemplateLoadError(f"duplicate template id: {entry.id}")
            if not entry.scopes:
                raise TemplateLoadError(f"template {entry.id} must declare at least one scope")
            if not entry.compile_targets:
                raise TemplateLoadError(f"template {entry.id} must declare at least one compile target")
            ir = _load_template_ir(root / entry.ir_file, entry.id)
            _validate_template(entry, ir, registry)
            records[entry.id] = TemplateRecord(entry=entry, ir=ir)
        return cls(version=index.version, records=records)

    def list(self, *, scope: str | None = None, target: Target | None = None) -> list[TemplateRecord]:
        rows = list(self._records.values())
        if scope:
            rows = [row for row in rows if scope in row.entry.scopes]
        if target:
            rows = [row for row in rows if target in row.entry.compile_targets]
        return rows

    def get(self, template_id: str) -> TemplateRecord | None:
        return self._records.get(template_id)


def _load_template_ir(path: Path, template_id: str) -> dict:
    try:
        raw = yaml.safe_load(path.read_text())
    except Exception as e:  # noqa: BLE001
        raise TemplateLoadError(f"failed to load template {template_id}: {e}") from e
    if not isinstance(raw, dict):
        raise TemplateLoadError(f"template {template_id} must contain a YAML object")
    return raw


def _validate_template(entry: TemplateIndexEntry, ir: dict, registry: Registry) -> None:
    try:
        validate_schema(ir)
        doc = IRDocument.model_validate(ir)
    except Exception as e:  # noqa: BLE001
        raise TemplateLoadError(f"template {entry.id} schema/model validation failed: {e}") from e
    if doc.ir_version != "0.4":
        raise TemplateLoadError(f"template {entry.id} must use ir_version 0.4")

    for scope in entry.scopes:
        failures = validate(ir, scope=scope)
        if failures:
            details = "; ".join(f"{f.location}: {f.detail}" for f in failures)
            raise TemplateLoadError(f"template {entry.id} failed validation for scope {scope}: {details}")
        try:
            for handle in doc.registry_ref.tools:
                registry.resolve_tool(handle, scope=scope)
            for handle in doc.registry_ref.datasets:
                registry.resolve_dataset(handle, scope=scope)
            for handle in doc.registry_ref.credentials:
                registry.resolve_credential(handle, scope=scope)
        except RegistryEntryNotFound as e:
            raise TemplateLoadError(f"template {entry.id} registry_ref invalid for scope {scope}: {e}") from e
