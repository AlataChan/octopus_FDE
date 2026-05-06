# ADR 0002 — Runtime versions locked (Hiagent + Dify)

**Status:** Accepted
**Date:** 2026-05-06

## Decision

### Hiagent (primary)
- Product/runtime version: `2.6`
- Deployment mode: `hiagent-cloud` for first build unless a self-hosted artifact is provided.
- Workflow JSON module path: `loom/runtimes/hiagent/v2_6/`.

### Dify (secondary)
- Product/runtime version: `1.14.0`
- Deployment mode: `self-hosted-docker` for Phase 0 engineering target.
- Pinned image tag: `langgenius/dify-api:1.14.0`, `langgenius/dify-web:1.14.0` (record digest when pulled).
- DSL module path: `loom/runtimes/dify/v1_14/`.

## Context

PRD §5 commits to a per-runtime semantic conformance matrix. The matrix has no target without locked versions. PRD §9 calls out "vendor lock to pinned runtime versions" as an explicit risk; pinning is the trade-off accepted in exchange for the deterministic-production claim. Phase 1 ships RuntimeAdapter (ADR 0015) so adding/replacing a runtime is "write one adapter," not "rewrite orchestration."

## Conformance baseline (per runtime)

The matrix in PRD §5 was authored against these versions. Cells that cannot be honored natively are listed; each Compiler must synthesize with a wrapper or refuse to emit.

### Hiagent
| Cell | Native support | Wrapper needed | Notes |
|---|---|---|---|
| loop max_iterations | yes/no | ... | ... |
| parallel concat | ... | ... | ... |
| parallel object_merge | ... | ... | ... |
| parallel first_success | ... | ... | ... |
| agent budget+fallback | ... | ... | typed agent budgets are first-class on Hiagent |
| agent output_schema | ... | ... | output_schema enforcement: JSON / 文本 / Markdown / 自定义 |
| http retry retry_on | ... | ... | ... |
| node timeout_s | ... | ... | ... |
| http idempotency_key | ... | ... | ... |
| condition truthiness | ... | ... | ... |

### Dify
(Same row set as Hiagent; wrapper needs documented separately.)

For Phase 0, Task 14 fills the Dify 1.14.0 rows. Hiagent 2.6 rows are filled in Phase 1 Task 11.5, when the RuntimeAdapter and Hiagent compiler/reverse path ship.

## Upgrade policy

Per PRD §9: each runtime version bump is a deliberate compatibility project. The conformance matrix is re-run end-to-end against the affected runtime. Target upgrade lead time: <14 calendar days per runtime.

## Cost-budget escape hatch

If during Phase 1 execution the cost of running both runtimes is too high, the project owner may drop Dify (keep Hiagent — primary). Hiagent-only mode is a valid v1 ship state. Decision is recorded as an ADR amendment dated YYYY-MM-DD; affected gate rows for Dify are marked N/A in the corresponding gate report.

## Consequences

- `docker/hiagent-pinned/` and `docker/dify-pinned/` pin Hiagent 2.6 and Dify 1.14.0.
- Phase 0 CI runs `.github/workflows/conformance.yml` against pinned Dify 1.14.0. Phase 1 extends the same workflow to Hiagent 2.6.
- Runtime module paths are `loom/runtimes/hiagent/v2_6/` and `loom/runtimes/dify/v1_14/`.
- ADR 0015 (Phase 1) registers both adapters in `loom/runtimes/registry.py`.
