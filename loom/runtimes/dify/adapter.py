"""DifyAdapter - concrete RuntimeAdapter for Dify Cloud / self-hosted Dify v1.14."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

import yaml  # type: ignore[import-untyped]

from loom.runtimes.base import (
    CompileContext,
    UnsupportedRuntimeOperation,
    assert_runtime_ir_supported,
    capability_redlines,
)
from loom.runtimes.dify.v1_14 import DIFY_VERSION
from loom.runtimes.dify.v1_14.ast import canonical_dify_ast_hash
from loom.runtimes.dify.v1_14.compiler import compile_ir as compile_to_yaml

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


class DifyAdapter:
    target = "dify"
    version = DIFY_VERSION

    def compile(
        self,
        ir: IRDocument,
        *,
        context: CompileContext | None = None,
    ) -> tuple[str, list[CompileWarning]]:
        del context
        assert_runtime_ir_supported(ir, target=self.target, version=self.version)
        # compile_to_yaml already returns YAML string; the adapter passes it through.
        return compile_to_yaml(ir)

    def reverse(self, dsl: Any) -> tuple[IRDocument, list[UnrecognizedConstruct]]:
        raise UnsupportedRuntimeOperation(
            target=self.target,
            version=self.version,
            operation="reverse",
            reason="reverse compiler is first-customer-deferred and needs a live runtime",
        )

    def canonical_ast_hash(self, dsl: Any) -> str:
        text = dsl if isinstance(dsl, str) else yaml.safe_dump(dsl, sort_keys=False)
        return canonical_dify_ast_hash(text)

    def serialize_dsl(self, dsl: Any) -> str:
        if isinstance(dsl, str):
            return dsl
        return cast("str", yaml.safe_dump(dsl, sort_keys=False, allow_unicode=True))

    def parse_dsl(self, raw: str) -> Any:
        return yaml.safe_load(raw)

    async def push_draft(self, dsl: Any, ctx: PushContext) -> DraftHandle:
        raise UnsupportedRuntimeOperation(
            target=self.target,
            version=self.version,
            operation="push_draft",
            reason="first-customer-deferred and needs a customer Dify endpoint",
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
