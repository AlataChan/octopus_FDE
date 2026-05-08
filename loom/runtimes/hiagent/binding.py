"""Hiagent customer Binding file model + loader.

A Binding is a per-customer artifact filled at onboarding [ADR 0024
§Customer Binding file]: workspace_id required; KB / Model / Tool ID
maps optional [empty means customer wires in Hiagent UI after import].
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, Literal

import yaml  # type: ignore[import-untyped]
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, ValidationError

if TYPE_CHECKING:
    from pathlib import Path


class HiagentBindingError(ValueError):
    """Raised when binding cannot be loaded or fails validation."""


WorkspaceId = Annotated[str, StringConstraints(min_length=1)]


class HiagentBinding(BaseModel):
    """Per-customer Hiagent deployment binding.

    `workspace_id` is required [compile fails fast if empty].
    All ID maps are optional; missing entries cause the compiler to emit
    empty strings in the YAML, which the customer then wires in the
    Hiagent UI after import.
    """
    model_config = ConfigDict(extra="forbid", frozen=True)

    customer: str = Field(min_length=1)
    target: Literal["hiagent"]
    target_version: str = "2.6"
    workspace_id: WorkspaceId
    dataset_id_map: dict[str, str] = Field(default_factory=dict)
    model_id_map: dict[str, str] = Field(default_factory=dict)
    rerank_model_id: str = ""
    tool_id_map: dict[str, str] = Field(default_factory=dict)

    @classmethod
    def load(cls, path: Path) -> HiagentBinding:
        """Load a binding YAML file. Raise HiagentBindingError on any problem."""
        if not path.exists():
            raise HiagentBindingError(f"binding file not found: {path}")
        try:
            data = yaml.safe_load(path.read_text())
        except yaml.YAMLError as e:
            raise HiagentBindingError(f"binding YAML parse error: {e}") from e
        if not isinstance(data, dict):
            raise HiagentBindingError(f"binding root must be a mapping, got {type(data).__name__}")
        try:
            return cls.model_validate(data)
        except ValidationError as e:
            raise HiagentBindingError(f"binding validation failed: {e}") from e

    def resolve_dataset(self, handle: str) -> str:
        """Return Hiagent KB id for IR dataset handle, or '' if unbound."""
        return self.dataset_id_map.get(handle, "")

    def resolve_model(self, handle: str) -> str:
        return self.model_id_map.get(handle, "")

    def resolve_tool(self, handle: str) -> str:
        return self.tool_id_map.get(handle, "")
