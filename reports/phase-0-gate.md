# Phase 0 gate report

**Date:** 2026-05-07
**Status:** **MVP-critical closed; gate ceremony partially deferred**

This report assembles the per-criterion evidence required by PRD §7 to declare Phase 0 closed. Under the 2026-05-07 MVP scope clarification (commit `4c4dd03`), gate rows requiring a live runtime endpoint or external reviewers are deferred until first customer integration; rows that are runtime-neutral and authored ship as-evidenced.

## Phase 0 decisions / defaults (PRD §7)

| # | Item | Status | ADR / artifact |
|---|---|---|---|
| 1 | SOW / requirements intake contract accepted and first SOW packet written | accepted | `docs/decisions/0001-sow-requirements-intake.md`, `sow/default-ecommerce/phase0-synthetic-sow.yaml` |
| 2 | Runtime versions fixed: Hiagent 2.6 + Dify 1.14.0 (self-hosted-docker on customer cloud VM, per 2026-05-07 amendment) | accepted | `docs/decisions/0002-runtime-versions.md` |
| 3 | Credential binding strategy accepted | accepted | `docs/decisions/0003-credential-binding.md` |
| 4 | Reverse-compile default scope accepted | accepted | `docs/decisions/0004-reverse-compile-scope.md` |
| 5 | Agent / LLM defaults accepted (`max_output_tokens = 8000`) | accepted | `docs/decisions/0005-agent-governance.md` |

All five `accepted`. Phase 1 prerequisite block: clear.

## Phase 0 gate criteria (PRD §7)

| # | Criterion | Status | Evidence |
|---|---|---|---|
| 1 | All 5 archetypes express in IR ≤25 nodes; 0 unsupported semantics requiring `code` workaround | **pass** | `pytest tests/archetypes/` (5 archetypes 5/6/7/8/11 nodes; 0 v0.3-out-of-scope types) |
| 2 | 0 archetypes require a node type outside v0.3 list (≤1 deliberate IR bump permitted) | **pass** | `git log schemas/` + ADR list (no IR-version bumps in Phase 0) |
| 3 | Each hand-authored IR runs the conformance suite for every construct it uses on the Phase 0 engineering target (Dify); smoke test passes | **deferred_to_first_customer_integration** | `reports/conformance-baseline.md` (factories shipped in `loom/conformance/matrix.py`; live execution awaits customer Dify endpoint) |
| 4 | Phase 0 engineering target import/export canonicalization proven N=10, false-drift rate 0 (Dify) | **deferred_to_first_customer_integration** | Phase 0 Task 15 — same trigger as criterion 3 |
| 5 | Reverse-compile spike on one archetype canonically equal | **deferred_to_first_customer_integration** | Phase 0 Task 16 — same trigger |
| 6 | Reviewer edit simulation: publish-blocking + remediation flow | **deferred_to_first_customer_integration** | Phase 0 Task 17 — same trigger |
| 7 | Security review on `http`, `code`, `agent` (runtime-neutral; covers IR contracts) | **pass** | `reports/security-review.md` (4 findings, all triaged false positives; Phase 1 Validator follow-up: pure-vs-impure code distinction) |
| 8 | Reviewability median ≥ 4 across archetypes (3 reviewers, 1–5 scale) | **deferred_to_first_customer_integration** | `reports/reviewability.md` (rating session deferred to include customer-domain reviewer) |
| 9 | ADR 0002 amendment recorded if Cost-budget escape hatch invoked before Phase 0 close (Dify dropped → above rows pivot to Hiagent) | n/a | escape hatch not invoked |

## Decision

**Phase 1 unblocked for MVP path.**

Gate criteria 1, 2, 7 (pass) cover everything required to author IR + reason about safety. Criteria 3-6, 8 (deferred) are evidence-quality rows that need live customer infrastructure or external reviewers to produce; deferring them does not block Phase 1 implementation, only delays the formal gate-report close to first-customer integration.

If first-customer integration produces a result that fails any deferred row, this report is regenerated with the failing rows visible and Phase 1 work that depends on the failed assumption is reopened.

## Companion artifacts

- `reports/conformance-baseline.md` — Task 14 stub (deferred)
- `reports/security-review.md` — Task 18 (passed)
- `reports/reviewability.md` — Task 19 stub (deferred)
- (To produce at first customer integration: `reports/round-trip-proof.json` Task 15, `reports/reverse-compile-spike.md` Task 16, `reports/reviewer-edit-simulation.md` Task 17)
