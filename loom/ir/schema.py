"""Load and validate IR documents against versioned JSON Schemas."""
from __future__ import annotations

import json
from functools import cache
from pathlib import Path
from typing import Any, cast

from jsonschema import Draft202012Validator  # type: ignore[import-untyped]

_SCHEMAS = Path(__file__).resolve().parents[2] / "schemas"
_CURRENT = "0.4"
_DEFAULT_COMPAT = "0.3"
_BY_VERSION = {
    "0.3": "ir-v0.3.schema.json",
    "0.4": "ir-v0.4.schema.json",
}


@cache
def load_schema(version: str = _DEFAULT_COMPAT) -> dict[str, Any]:
    path_name = _BY_VERSION.get(version)
    if path_name is None:
        raise ValueError(f"Unsupported IR schema version: {version}")
    path = _SCHEMAS / path_name
    return cast("dict[str, Any]", json.loads(path.read_text()))


def load_schema_for_doc(doc: dict[str, Any]) -> dict[str, Any]:
    version = str(doc.get("ir_version") or _DEFAULT_COMPAT)
    return load_schema(version)


@cache
def _validator(version: str = _DEFAULT_COMPAT) -> Any:
    return Draft202012Validator(load_schema(version))


def validate(doc: dict[str, Any], version: str | None = None) -> None:
    """Raise jsonschema.ValidationError on schema violation."""
    selected = version or str(doc.get("ir_version") or _DEFAULT_COMPAT)
    _validator(selected).validate(doc)


def is_valid(doc: dict[str, Any], version: str | None = None) -> bool:
    selected = version or str(doc.get("ir_version") or _DEFAULT_COMPAT)
    return cast("bool", _validator(selected).is_valid(doc))
