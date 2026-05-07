"""Load and validate IR documents against the v0.3 JSON Schema."""
from __future__ import annotations

import json
from functools import cache
from pathlib import Path
from typing import Any, cast

from jsonschema import Draft202012Validator  # type: ignore[import-untyped]

_SCHEMAS = Path(__file__).resolve().parents[2] / "schemas"
_CURRENT = "0.3"


@cache
def load_schema(version: str = _CURRENT) -> dict[str, Any]:
    path = _SCHEMAS / f"ir-v{version}.schema.json"
    return cast("dict[str, Any]", json.loads(path.read_text()))


@cache
def _validator(version: str = _CURRENT) -> Any:
    return Draft202012Validator(load_schema(version))


def validate(doc: dict[str, Any], version: str = _CURRENT) -> None:
    """Raise jsonschema.ValidationError on schema violation."""
    _validator(version).validate(doc)


def is_valid(doc: dict[str, Any], version: str = _CURRENT) -> bool:
    return cast("bool", _validator(version).is_valid(doc))
