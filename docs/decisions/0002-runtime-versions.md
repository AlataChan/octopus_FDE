# ADR 0002 — Runtime versions locked (Hiagent Cloud + Dify Cloud)

**Status:** Accepted (amended 2026-05-07: cloud-only deployment pivot)
**Date:** 2026-05-06
**Amendment:** 2026-05-07 — switch deployment model from self-hosted-docker (Dify) to cloud SaaS for both runtimes; drop docker-compose image pin in favor of API version pin. Local docker scaffolding removed (was YAGNI under cloud-only operation). Conformance baseline runs against cloud SaaS endpoints with auth tokens supplied via `config/runtimes.yaml`.

## Decision

### Hiagent Cloud (primary)
- Product: Hiagent Cloud SaaS
- API version pinned: `v1` (record exact minor + base URL on first integration; reflected in `config/runtimes.yaml`)
- API base URL: configured via `config/runtimes.yaml` (no default — must be set explicitly per environment)
- Auth: Bearer token via `HIAGENT_CLOUD_TOKEN` env (loaded by `config/runtimes.yaml` resolver)
- Compiler module path: `loom/runtimes/hiagent/cloud/`

### Dify Cloud (secondary)
- Product: Dify Cloud SaaS (e.g., `cloud.dify.ai`)
- API version pinned: `v1` (record exact base URL on first integration; reflected in `config/runtimes.yaml`)
- API base URL: configured via `config/runtimes.yaml` (e.g., `https://cloud.dify.ai/v1`)
- Auth: Bearer token via `DIFY_CLOUD_TOKEN` env
- Compiler module path: `loom/runtimes/dify/cloud/`

## Context

PRD §5 commits to a per-runtime semantic conformance matrix. The matrix has no target without locked versions. PRD §9 calls out "vendor lock to pinned runtime versions" as an explicit risk; under cloud SaaS the lock is to API version + cloud-provider's compatibility window, not docker image digest. Phase 1 ships RuntimeAdapter (ADR 0015) so adding/replacing a runtime is "write one adapter," not "rewrite orchestration."

Local docker self-host was the original Phase 0 engineering target but was retired on 2026-05-07: the project owner does not run local docker as a deployment model, and both Hiagent and Dify offer first-class cloud SaaS APIs. The previously-merged `docker/{hiagent,dify}-pinned/` scaffolding and `scripts/{hiagent,dify}_{up,down}.sh` were deleted in the same pivot commit; configuration moved to `config/runtimes.example.yaml`.

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

For Phase 0, Task 14 fills the Dify Cloud rows. Hiagent Cloud rows are filled in Phase 1 Task 11.5, when the RuntimeAdapter and Hiagent compiler/reverse path ship.

## Upgrade policy

Per PRD §9: each runtime API-version bump is a deliberate compatibility project. The conformance matrix is re-run end-to-end against the affected runtime. Target upgrade lead time: <14 calendar days per runtime. Cloud providers may roll out non-breaking minor changes silently; the conformance suite is the canary that catches behavior drift between versions.

## Cost-budget escape hatch

If during Phase 1 execution the cost of running both runtimes is too high (cloud SaaS billing or per-call pricing), the project owner may drop Dify (keep Hiagent — primary). Hiagent-only mode is a valid v1 ship state. Decision is recorded as an ADR amendment dated YYYY-MM-DD; affected gate rows for Dify are marked N/A in the corresponding gate report; `loom.runtimes.registry.unregister("dify")` makes it configuration-only.

## Consequences

- `config/runtimes.example.yaml` declares the Hiagent Cloud + Dify Cloud endpoints and auth-token slots.
- Phase 0 CI runs `.github/workflows/conformance.yml` against pinned Dify Cloud (auth token from CI secret). Phase 1 extends the same workflow to Hiagent Cloud.
- Runtime module paths are `loom/runtimes/hiagent/cloud/` and `loom/runtimes/dify/cloud/`.
- ADR 0015 (Phase 1) registers both adapters in `loom/runtimes/registry.py`.
- No local docker artifacts. If self-hosted is reintroduced later, a separate ADR is required.
