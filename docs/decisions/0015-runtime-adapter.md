# ADR 0015 — RuntimeAdapter

Status: Accepted
Date: 2026-05-08

## Decision

Every supported runtime exposes a uniform contract. The full method set is fixed in this ADR; later phases must not add methods without an ADR amendment.

```python
class RuntimeAdapter(Protocol):
    target: str                                                          # "hiagent" | "dify"
    version: str                                                         # e.g. "1.6", "2.2"

    # IR ↔ DSL
    def compile(self, ir: IRDocument) -> DSL: ...
    def reverse(self, dsl: DSL) -> tuple[IRDocument, list[UnrecognizedConstruct]]: ...
    def canonical_ast_hash(self, dsl: DSL) -> str: ...

    # DSL serialization (used by CLI: file <-> in-memory DSL value)
    def serialize_dsl(self, dsl: DSL) -> str: ...
    def parse_dsl(self, raw: str) -> DSL: ...

    # Lifecycle on the target runtime
    async def push_draft(self, dsl: DSL, ctx: PushContext) -> DraftHandle: ...
    async def publish(self, handle: DraftHandle, ctx: PublishContext) -> PublishHandle: ...
    async def export_draft(self, draft_id: str) -> DSL: ...

    # Conformance / parity testing — runs the draft with given inputs and returns output dict
    async def run_draft(self, draft_id: str, *, inputs: dict) -> dict: ...

    # Optional metadata: list of IR constructs the runtime cannot honor today;
    # consulted by the Planner to avoid suggesting features that won't compile.
    def redlines(self) -> list[str]: ...   # may return [] if the runtime supports the full IR
```

Phase 1 ships two adapters: Hiagent (primary) and Dify (secondary). `loom/runtimes/registry.py` resolves a target name to an adapter; `UnknownTargetError` for anything else. Orchestration code (FDE Session, Planner, Validator, Deployer, Conformance runner, CLI) goes through this contract — never imports Hiagent or Dify modules directly.

## Consequences

- Adding a new runtime is "write one adapter"; orchestration code does not change.
- Per-runtime version pins live inside the adapter implementation, not the orchestration layer.
- Tests against orchestration use a `FakeRuntimeAdapter`; no live Hiagent / Dify needed for unit tests.
- Phase 1 cost-budget escape hatch: dropping Dify is `loom/runtimes/registry.py` unregister + remove `loom/runtimes/dify/` — Hiagent path is unaffected.
