"""DifyAdapter - concrete RuntimeAdapter for Dify Cloud / self-hosted Dify v1.14."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

import yaml  # type: ignore[import-untyped]

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


class DifyAdapter:
    target = "dify"
    version = DIFY_VERSION

    def compile(self, ir: IRDocument):
        # compile_to_yaml already returns YAML string; the adapter passes it through.
        return compile_to_yaml(ir)

    def reverse(self, dsl: Any) -> tuple[IRDocument, list[UnrecognizedConstruct]]:
        raise NotImplementedError(
            "Dify reverse compiler is first-customer-deferred (MVP scope; needs live runtime)"
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
        raise NotImplementedError(
            "Dify push_draft is first-customer-deferred (MVP scope; needs customer Dify endpoint)"
        )

    async def publish(self, handle: DraftHandle, ctx: PublishContext) -> PublishHandle:
        raise NotImplementedError("first-customer-deferred")

    async def export_draft(self, draft_id: str) -> Any:
        raise NotImplementedError("first-customer-deferred")

    async def run_draft(self, draft_id: str, *, inputs: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError("first-customer-deferred")

    def redlines(self) -> list[str]:
        # Pinned Dify v1.14 native gaps; conformance baseline at first customer integration fills these in.
        return []
