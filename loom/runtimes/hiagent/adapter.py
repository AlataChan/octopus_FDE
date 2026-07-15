"""HiagentAdapter - concrete RuntimeAdapter for Hiagent v2.6 self-hosted."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from loom.runtimes.base import (
    CompileContext,
    UnsupportedRuntimeOperation,
    assert_runtime_ir_supported,
    capability_redlines,
)
from loom.runtimes.hiagent.binding import HiagentBinding, HiagentBindingError
from loom.runtimes.hiagent.v2_6 import HIAGENT_VERSION
from loom.runtimes.hiagent.v2_6.bundle import HiagentBundle
from loom.runtimes.hiagent.v2_6.compiler import (
    compile_ir as compile_to_bundle,
)
from loom.runtimes.hiagent.v2_6.compiler import (
    compile_ir_chatflow as compile_to_chatflow_bundle,
)

if TYPE_CHECKING:
    from loom.ir.models import IRDocument
    from loom.runtimes.base import (
        DraftHandle,
        PublishContext,
        PublishHandle,
        PushContext,
        UnrecognizedConstruct,
    )
    from loom.runtimes.warnings import CompileWarning


class HiagentAdapter:
    target = "hiagent"
    version = HIAGENT_VERSION

    def compile(
        self,
        ir: IRDocument,
        *,
        context: CompileContext | None = None,
        binding: HiagentBinding | None = None,
    ) -> tuple[HiagentBundle, list[CompileWarning]]:
        """Compile IR to a HiagentBundle.

        Per ADR 0024, a customer Binding [workspace_id required] is mandatory
        for Hiagent compilation. Callers must pass it; we don't allow a
        default empty binding because workspace_id is customer-specific.
        """
        selected_binding = context.binding if context is not None else binding
        if not isinstance(selected_binding, HiagentBinding):
            raise HiagentBindingError(
                "HiagentAdapter.compile requires a customer Binding "
                "[per ADR 0024]; pass context=CompileContext(binding=...) or use "
                "loom compile --binding <path>"
            )
        assert_runtime_ir_supported(
            ir,
            target=self.target,
            version=self.version,
            # CompileContext is the governed orchestration path. The legacy
            # binding keyword remains temporarily for the out-of-scope CLI,
            # which still exposes its established preview-with-warnings mode.
            binding=selected_binding if context is not None else None,
        )
        if context is not None and context.mode == "chatflow":
            return compile_to_chatflow_bundle(ir, selected_binding)
        return compile_to_bundle(ir, selected_binding)

    def reverse(self, dsl: Any) -> tuple[IRDocument, list[UnrecognizedConstruct]]:
        raise UnsupportedRuntimeOperation(
            target=self.target,
            version=self.version,
            operation="reverse",
            reason="reverse compiler is first-customer-deferred",
        )

    def canonical_ast_hash(self, _dsl: Any) -> str:
        raise UnsupportedRuntimeOperation(
            target=self.target,
            version=self.version,
            operation="canonical_ast_hash",
            reason="hashing for API-pushed agents is deferred until ChatFlow adapter work",
        )

    def serialize_dsl(self, dsl: Any) -> bytes:
        """Serialize a HiagentBundle to the verified zip-import format."""
        if not isinstance(dsl, HiagentBundle):
            raise TypeError(
                f"HiagentAdapter.serialize_dsl expected HiagentBundle, got {type(dsl).__name__}"
            )
        return dsl.to_zip_bytes()

    def parse_dsl(self, raw: str | bytes) -> Any:
        raise UnsupportedRuntimeOperation(
            target=self.target,
            version=self.version,
            operation="parse_dsl",
            reason="reverse compiler is first-customer-deferred",
        )

    async def push_draft(self, dsl: Any, ctx: PushContext) -> DraftHandle:
        raise UnsupportedRuntimeOperation(
            target=self.target, version=self.version, operation="push_draft", reason="first-customer-deferred"
        )

    async def publish(self, handle: DraftHandle, ctx: PublishContext) -> PublishHandle:
        raise UnsupportedRuntimeOperation(
            target=self.target, version=self.version, operation="publish", reason="first-customer-deferred"
        )

    async def export_draft(self, draft_id: str) -> Any:
        raise UnsupportedRuntimeOperation(
            target=self.target, version=self.version, operation="export_draft", reason="first-customer-deferred"
        )

    async def run_draft(self, draft_id: str, *, inputs: dict[str, Any]) -> dict[str, Any]:
        raise UnsupportedRuntimeOperation(
            target=self.target, version=self.version, operation="run_draft", reason="first-customer-deferred"
        )

    def redlines(self) -> list[str]:
        return capability_redlines(self.target, self.version)
