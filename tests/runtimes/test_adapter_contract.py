import asyncio
import json
from typing import Any

import pytest

from loom.runtimes import registry
from loom.runtimes.base import (
    CompileContext,
    DraftHandle,
    PublishContext,
    PublishHandle,
    PushContext,
    RuntimeAdapter,
    UnrecognizedConstruct,
)


@pytest.fixture(autouse=True)
def reset_registry():
    yield
    for t in list(registry.list_targets()):
        registry.unregister(t)


class FakeAdapter:
    target = "fake"
    version = "0.0"

    def compile(
        self,
        ir: Any,
        *,
        context: CompileContext | None = None,
    ) -> tuple[dict[str, bool], list[Any]]:
        del ir, context
        return {"ok": True}, []

    def reverse(self, dsl: Any) -> tuple[None, list[UnrecognizedConstruct]]:
        return None, []

    def canonical_ast_hash(self, dsl: Any) -> str:
        return "0" * 64

    def serialize_dsl(self, dsl: Any) -> str:
        return json.dumps(dsl, sort_keys=True)

    def parse_dsl(self, raw: str) -> Any:
        return json.loads(raw)

    async def push_draft(self, dsl: Any, ctx: PushContext) -> DraftHandle:
        await asyncio.sleep(0)
        return DraftHandle(target=self.target, draft_id="d1", canonical_ast_hash="0" * 64)

    async def publish(self, handle: DraftHandle, ctx: PublishContext) -> PublishHandle:
        await asyncio.sleep(0)
        return PublishHandle(target=self.target, publish_id="p1", canonical_ast_hash=handle.canonical_ast_hash)

    async def export_draft(self, draft_id: str) -> Any:
        await asyncio.sleep(0)
        return {"draft_id": draft_id}

    async def run_draft(self, draft_id: str, *, inputs: dict[str, Any]) -> dict[str, Any]:
        await asyncio.sleep(0)
        return {"ok": True, "inputs": inputs}

    def redlines(self) -> list[str]:
        return []


def test_register_and_get():
    adapter: RuntimeAdapter = FakeAdapter()
    registry.register(adapter)
    assert registry.get("fake").target == "fake"


def test_unknown_target_raises():
    with pytest.raises(registry.UnknownTargetError):
        registry.get("does-not-exist")
