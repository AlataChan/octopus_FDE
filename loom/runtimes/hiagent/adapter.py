"""HiagentAdapter - concrete RuntimeAdapter for Hiagent v2.6 self-hosted."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from loom.runtimes.hiagent.binding import HiagentBinding, HiagentBindingError
from loom.runtimes.hiagent.v2_6 import HIAGENT_VERSION
from loom.runtimes.hiagent.v2_6.compiler import compile_ir as compile_to_bundle

if TYPE_CHECKING:
    from loom.ir.models import IRDocument
    from loom.runtimes.base import (
        DraftHandle,
        PublishContext,
        PublishHandle,
        PushContext,
        UnrecognizedConstruct,
    )
    from loom.runtimes.hiagent.v2_6.bundle import HiagentBundle


class HiagentAdapter:
    target = "hiagent"
    version = HIAGENT_VERSION

    def compile(self, ir: IRDocument, *, binding: HiagentBinding | None = None) -> HiagentBundle:
        """Compile IR to a HiagentBundle.

        Per ADR 0024, a customer Binding [workspace_id required] is mandatory
        for Hiagent compilation. Callers must pass it; we don't allow a
        default empty binding because workspace_id is customer-specific.
        """
        if binding is None:
            raise HiagentBindingError(
                "HiagentAdapter.compile requires a customer Binding "
                "[per ADR 0024]; pass binding=<HiagentBinding> or use "
                "loom compile --binding <path>"
            )
        return compile_to_bundle(ir, binding)

    def reverse(self, dsl: Any) -> tuple[IRDocument, list[UnrecognizedConstruct]]:
        raise NotImplementedError(
            "Hiagent reverse compiler is first-customer-deferred (MVP scope)"
        )

    def canonical_ast_hash(self, _dsl: Any) -> str:
        raise NotImplementedError(
            "Hiagent canonical AST hashing for API-pushed agents is deferred "
            "until ChatFlow adapter work"
        )

    def serialize_dsl(self, _dsl: Any) -> bytes:
        """External ZIP serialization was retired.

        Hiagent self-hosted accepts server-created app configs through the TOP
        API. Sub-task D will decide whether the adapter grows a ChatFlow export
        serializer; callers should use `loom hiagent push` for publishing.
        """
        raise NotImplementedError(
            "Hiagent external ZIP serialization is retired; use loom hiagent push"
        )

    def parse_dsl(self, raw: str | bytes) -> Any:
        raise NotImplementedError(
            "Hiagent reverse compiler is first-customer-deferred [MVP scope]"
        )

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
