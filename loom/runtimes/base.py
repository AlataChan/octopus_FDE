from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from loom.ir.models import IRDocument


@dataclass(frozen=True)
class DraftHandle:
    target: str        # "hiagent" | "dify"
    draft_id: str
    canonical_ast_hash: str


@dataclass(frozen=True)
class PublishHandle:
    target: str
    publish_id: str
    canonical_ast_hash: str


@dataclass(frozen=True)
class UnrecognizedConstruct:
    target: str
    construct: str
    reason: str
    remediation: str


@dataclass(frozen=True)
class PushContext:
    actor: str
    workflow_name: str | None = None


@dataclass(frozen=True)
class PublishContext:
    actor: str


class RuntimeAdapter(Protocol):
    target: str
    version: str
    # IR ↔ DSL
    def compile(self, ir: IRDocument) -> Any: ...
    def reverse(self, dsl: Any) -> tuple[IRDocument, list[UnrecognizedConstruct]]: ...
    def canonical_ast_hash(self, dsl: Any) -> str: ...
    # DSL serialization
    def serialize_dsl(self, dsl: Any) -> str: ...
    def parse_dsl(self, raw: str) -> Any: ...
    # Lifecycle
    async def push_draft(self, dsl: Any, ctx: PushContext) -> DraftHandle: ...
    async def publish(self, handle: DraftHandle, ctx: PublishContext) -> PublishHandle: ...
    async def export_draft(self, draft_id: str) -> Any: ...
    # Conformance / parity
    async def run_draft(self, draft_id: str, *, inputs: dict[str, Any]) -> dict[str, Any]: ...
    # Planner consultation
    def redlines(self) -> list[str]: ...
