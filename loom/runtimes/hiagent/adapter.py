"""HiagentAdapter - concrete RuntimeAdapter for Hiagent v2.6."""
from __future__ import annotations

import json as json_lib
from typing import TYPE_CHECKING, Any

from loom.runtimes.hiagent.v2_6 import HIAGENT_VERSION

if TYPE_CHECKING:
    from loom.ir.models import IRDocument
    from loom.runtimes.base import (
        DraftHandle,
        PublishContext,
        PublishHandle,
        PushContext,
        UnrecognizedConstruct,
    )


class HiagentAdapter:
    target = "hiagent"
    version = HIAGENT_VERSION

    def compile(self, ir: IRDocument) -> Any:
        raise NotImplementedError(
            "Hiagent compile requires a customer binding file after ADR 0024; "
            "Sub-task C wires CLI --binding and bundle serialization"
        )

    def reverse(self, dsl: Any) -> tuple[IRDocument, list[UnrecognizedConstruct]]:
        raise NotImplementedError(
            "Hiagent reverse compiler is first-customer-deferred (MVP scope)"
        )

    def canonical_ast_hash(self, dsl: Any) -> str:
        # Hiagent canonical-AST hashing is Phase 1.5+ work (per ADR 0002 amendments).
        # Stub a stable hash on the JSON text so Phase 1 tooling that reads this
        # field still functions; replace with real canonicalize when adapter ships.
        import hashlib
        text = dsl if isinstance(dsl, str) else json_lib.dumps(dsl, sort_keys=True)
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def serialize_dsl(self, dsl: Any) -> str:
        if isinstance(dsl, str):
            return dsl
        return json_lib.dumps(dsl, indent=2, ensure_ascii=False)

    def parse_dsl(self, raw: str) -> Any:
        return json_lib.loads(raw)

    async def push_draft(self, dsl: Any, ctx: PushContext) -> DraftHandle:
        raise NotImplementedError("first-customer-deferred")

    async def publish(self, handle: DraftHandle, ctx: PublishContext) -> PublishHandle:
        raise NotImplementedError("first-customer-deferred")

    async def export_draft(self, draft_id: str) -> Any:
        raise NotImplementedError("first-customer-deferred")

    async def run_draft(self, draft_id: str, *, inputs: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError("first-customer-deferred")

    def redlines(self) -> list[str]:
        return []
