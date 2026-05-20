"""Structured compiler warning payloads shared by runtime adapters."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class CompileWarning:
    target: Literal["hiagent", "dify"]
    node_id: str | None
    field: str
    message: str
    code: str
