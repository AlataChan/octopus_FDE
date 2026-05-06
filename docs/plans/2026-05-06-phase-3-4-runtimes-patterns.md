# FDE Phase 3 / Phase 4 — Multi-Tenancy + Pattern Library + Self-Improvement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Document location:** Project execution plans live in `docs/plans/`.

**Naming note:** Product-facing language is FDE / AI 驻场流程工程师. Internal implementation paths may temporarily retain the `loom/` Python namespace.

**Status:** Phase 3 and Phase 4 are PRD §7 "持续" phases. They are NOT a single 4-week sprint. This file plans **two milestone bands**: Phase 3 (multi-tenancy + IR v0.4 minor bump + optional LangGraph alpha, ~3–6 weeks) and Phase 4 (pattern library + self-improvement, ~10–14 weeks). Each milestone has its own gate; treat any milestone as independently shippable.

**Goal:**

- **Phase 3 (Multi-tenancy + IR v0.4):** The `RuntimeAdapter` abstraction with Hiagent + Dify dual support already shipped in Phase 1 (decision 2026-05-06: n8n out of v1 scope). Phase 3.1 closes PRD §11 Q4 multi-tenancy and ships the IR v0.3 → v0.4 minor bump (adds `metadata.compliance_class` + `output_schema.<field>.pii_class` overrides). Phase 3.2 (LangGraph alpha) is **optional** — execute only if budget allows or a customer asks; otherwise defer to v1.5.
- **Phase 4 (Pattern Library + Self-Improvement):** Capture validated workflows as parameterized patterns; surface them to Planner during planning to lift first-try IR validity beyond 85%; close the loop from runtime trace → corpus → planner improvement; introduce a controlled self-edit loop where FDE proposes IR refactors after observing N runs.

**Removed in this revision:** Phase 3.2 n8n GA (n8n out of v1 scope), ADR 0006 (n8n version pin), ADR 0007 (portability redlines), ADR 0018 (redline manifest UI). Phase 3 milestone count drops from 3 to 2. Runtime portability is proven by construction in Phase 1's dual-runtime compile (Hiagent + Dify), not by a redline-refusal stub.

**Architecture:** Phase 3 introduces multi-tenancy as a tenant-scoped column threaded through state, registry, vault, and audit. Phase 2A reserved the column; Phase 3.1 enforces. The IR v0.4 minor bump is additive (defaults preserve v0.3 round-trip). Phase 3.2 LangGraph (optional) follows the same `RuntimeAdapter` contract Phase 1 established for Hiagent + Dify.

Phase 4 introduces a per-tenant pattern library (`loom/patterns/`), a trace-to-corpus pipeline (`loom/learning/`), and a controlled self-edit proposer. All three are gated by Reviewer approval — no auto-apply.

**Tech Stack additions:** `pgvector` for pattern retrieval; `OpenTelemetry` traces (already in 2A) feed offline `loom/learning/` aggregator. Optional LangGraph (Phase 3.2): `langgraph` Python package, pinned. Web stack unchanged from 2B.

> **Trim note (2026-05-06):** Code snippets, ADR templates, and gate-criterion enumerations below are **illustrative**. Contracts to preserve: (a) ADR 0015 RuntimeAdapter (already shipped in Phase 1), (b) ADR 0016 multi-tenancy isolation rule (404 on cross-tenant), (c) ADR 0021 self-edit safety lock via structured `compliance_class`, (d) Phase 4 patterns + corpus + proposals are tenant-scoped. Per project owner directive 2026-05-06: trim over-specification, keep contracts.

**Prerequisites:** Phase 2B complete:
- `reports/phase-2b-gate.md` shows all rows pass.
- RBAC + audit + drift detection have been exercised by at least one design partner pilot for ≥4 weeks.
- `ux-evidence` shows ≥4/5 reviewer summary usefulness and ≥4/5 replacement willingness.

---

## Phase 3 — Milestone 3.1: Multi-tenancy + IR v0.4 minor bump (≈3–4 weeks)

**Goal:** Close PRD §11 Q4 multi-tenancy. Ship the IR v0.3 → v0.4 minor bump (additive: `metadata.compliance_class` + `output_schema.<field>.pii_class` per-field overrides). Both fields are required by ADRs already authored (ADR 0010 trace privacy; ADR 0021 self-edit safety lock); v0.4 makes them part of the IR contract.

### Phase 3 repo additions

```
docs/decisions/
├── 0006-WITHDRAWN.md            (n8n version pin — n8n out of scope 2026-05-06)
├── 0007-WITHDRAWN.md            (IR portability redlines — n8n out of scope)
├── 0015-runtime-adapter.md      (authored in Phase 1; documented here for completeness)
├── 0016-multi-tenancy.md        (NEW — Tenant model + isolation; Phase 3.1)
├── 0017-langgraph-version.md    (NEW — pinned LangGraph; Phase 3.2 OPTIONAL)
├── 0018-WITHDRAWN.md            (Redline manifest — n8n out of scope)
├── 0019-pattern-model.md        (NEW — Pattern + PatternBinding; Phase 4.1)
├── 0020-trace-to-corpus.md      (NEW — synthesis pipeline + curation; Phase 4.2)
├── 0021-self-edit-safety.md     (NEW — proposal kinds + safety rails; Phase 4.3)
└── 0022-ir-v0.4-bump.md         (NEW — additive minor bump; Phase 3.1)

loom/
├── ir/
│   ├── v0.4/                    (NEW — IR v0.4 schema + Pydantic models)
│   └── compat.py                (NEW — v0.3 ↔ v0.4 forward-only canonicalization)
├── tenancy/                     (NEW)
│   ├── models.py                (Tenant, Membership)
│   ├── policy.py                (every read/write has tenant scope guard)
│   └── middleware.py            (FastAPI middleware sets tenant context)
└── service/
    └── routes/
        └── tenants.py           (admin: list/create/manage tenants)

apps/web/src/
├── components/tenancy/
│   └── TenantSwitcher.tsx
└── app/(app)/admin/tenants/page.tsx

reports/
└── phase-3-1-gate.md            (multi-tenancy + v0.4 bump evidence)
```

### Task 3.1.0: Withdrawn-ADR tombstones

Drop tombstone files for ADRs that no longer apply:

```markdown
# ADR 0006 — WITHDRAWN

Status: Withdrawn 2026-05-06
Replaces: original "n8n version pin for portability probe"
Reason: n8n is out of v1 scope per project owner decision (2026-05-06). Hiagent + Dify
are the only supported runtimes. Runtime portability is proven by Phase 1's dual-runtime
compile, not by a falsifiable refusal stub.
See: ADR 0015 (RuntimeAdapter), Phase 1 plan, Phase 1.5 plan.
```

(Same shape for ADR 0007 and ADR 0018.)

```bash
git add docs/decisions/0006-WITHDRAWN.md docs/decisions/0007-WITHDRAWN.md docs/decisions/0018-WITHDRAWN.md
git commit -m "docs(adr): withdraw 0006/0007/0018 — n8n out of v1 scope"
```

### Task 3.1.1: ADR 0016 + ADR 0022

- [ ] Write `docs/decisions/0016-multi-tenancy.md`:

```markdown
# ADR 0016 — Multi-tenancy

Status: Proposed → Accepted (after review)
Date: 2026-MM-DD

## Decision

- Single Postgres database; row-level isolation via `tenant_id` on every table holding workflow / session / actor / audit / trace data.
- Service rejects any request whose token's `tenant_id` does not match the resource's `tenant_id`. Enforced by middleware, not per-route code.
- Vault paths are scoped: `<tenant_id>/<credential_name>`.
- Registry: each tenant has its own `registry/<tenant_id>/` git directory. Cross-tenant reads are forbidden.
- Shared tooling (Planner, Validator, Compiler, RuntimeAdapter) is tenant-agnostic; only state and registry are partitioned.

## Consequences

- A new Alembic migration adds `tenant_id NOT NULL` to every relevant table; data migration backfills the existing single tenant as `default`.
- Web app gains a tenant switcher; the actor's accessible tenants come from `Membership`.
- All audit receipts include `tenant_id` in payload.
- Phase 1.5 corpus migrates from `corpus/full/<archetype>/` to `corpus/full/<tenant>/<archetype>/` (the Phase 1.5 loader already supports both forms; CI fails if both coexist post-migration).
```

- [ ] Write `docs/decisions/0022-ir-v0.4-bump.md`:

```markdown
# ADR 0022 — IR v0.3 → v0.4 minor bump

Status: Proposed → Accepted (after review)
Date: 2026-MM-DD

## Decision

Two additive fields, both optional with explicit defaults:

- `metadata.compliance_class`: `Literal["none", "regulatory", "clinical", "human_review_required"]`, default `"none"`. Required by ADR 0021 (self-edit safety lock).
- `output_schema.<field>.pii_class`: optional override for any field in any node's `output_schema`; values `Literal["none", "low", "medium", "high"]`. Required by ADR 0010 (trace ingest pii_class routing).

Tools/datasets/credentials in the registry already carry `pii_class` (Phase 2A); v0.4 extends to per-field overrides on output_schema.

## Consequences

- v0.3 IRs round-trip through v0.4 unchanged (defaults preserved).
- Forward-only canonicalization in `loom/ir/compat.py` strips defaults; `canonical_ir` continues to produce stable hashes across v0.3 ↔ v0.4 documents.
- A CI gate refuses to compile a v0.3 IR if the workflow touches a registry entry whose `pii_class` is `medium`/`high` without an explicit per-field override; the gate forces authors onto v0.4 when sensitive data is in scope.
```

- [ ] Commit + reviewer pass.

### Task 3.1.2: Tenant model + middleware

- [ ] Alembic data migration: add `tenant` table, `membership` table, `tenant_id` columns on the relevant Phase 2A/2B tables. Backfill existing rows to tenant `default`.
- [ ] `loom/tenancy/middleware.py` resolves tenant from token; sets `request.state.tenant_id`; rejects cross-tenant lookups in DI helpers.
- [ ] Update SQLAlchemy query paths to include `tenant_id` in `where`.
- [ ] `tests/tenancy/test_isolation.py`: matrix of (actor in tenant A, resource in tenant B) operations all return 404 (not 403; 403 leaks resource existence).
- [ ] Web: tenant switcher in top bar; gates the workspace selector.

### Task 3.1.3: IR v0.4 schema + canonicalizer

- [ ] `schemas/ir-v0.4.schema.json` — JSON Schema 2020-12, additive only.
- [ ] `loom/ir/v0.4/models.py` — Pydantic v2 models extending v0.3 with the two new optional fields.
- [ ] `loom/ir/compat.py` — `to_canonical(ir)` accepts v0.3 or v0.4 and returns v0.4 with defaults stripped. `canonical_ir_hash(ir)` stable across both versions.
- [ ] `tests/ir/test_v0_4_compat.py` — every example archetype round-trips v0.3 → v0.4 → v0.3 with no semantic change.

### Task 3.1.4: Phase 3.1 gate

```markdown
# Phase 3.1 gate — Multi-tenancy + IR v0.4

| Criterion | Target | Actual | Status |
|---|---|---|---|
| Cross-tenant access returns 404 across the full operation matrix | 100% | NN% | pass/fail |
| Audit receipts include tenant_id | 100% | NN% | pass/fail |
| Web tenant switcher works for multi-tenant accounts | green | green/red | pass/fail |
| IR v0.4 schema accepts every Phase 1.5 archetype unchanged | 5/5 | N/5 | pass/fail |
| Canonical IR hash stable across v0.3 ↔ v0.4 | stable | stable/drift | pass/fail |
| Registry pii_class gate rejects v0.3 IRs touching medium/high pii_class without overrides | enforced | enforced/missing | pass/fail |
| Corpus migration to corpus/full/<tenant>/<archetype>/ complete | complete | complete/incomplete | pass/fail |
| All Phase 2A/2B tests pass after the migration (regression) | green | green/red | pass/fail |
```

Commit, reviewer pass.

---

## Phase 3 — Milestone 3.2: LangGraph alpha (≈4 weeks, OPTIONAL)

**Status: optional.** Execute only if budget allows or a customer asks. v1 ships with Hiagent + Dify; LangGraph is alpha-quality and not required for v1 final gate.

**Goal:** Add LangGraph as a third runtime via the existing `RuntimeAdapter`. Alpha quality: limited archetype coverage (≥1 archetype compiles + runs end-to-end), full adapter contract.

### Task 3.2.1: ADR 0017 — LangGraph version

- [ ] Pin a LangGraph version + Python package digest. Alpha is single-version.

### Task 3.2.2: Compiler + reverse + canonical hash

- [ ] `loom/runtimes/langgraph/<vL_X>/compiler.py`: IR → LangGraph spec (`StateGraph` + nodes + edges).
- [ ] `loom/runtimes/langgraph/<vL_X>/reverse.py`: alpha — narrow round-trip for `trigger`, `llm`, `condition`, `output` only. Wider coverage in subsequent iterations.
- [ ] `loom/runtimes/langgraph/<vL_X>/ast.py`: canonical LangGraph spec hash.
- [ ] `loom/runtimes/langgraph/adapter.py`: `RuntimeAdapter` implementation.

### Task 3.2.3: Phase 3.2 gate (only if executed)

```markdown
# Phase 3.2 gate — LangGraph alpha (OPTIONAL)

| Criterion | Target | Actual | Status |
|---|---|---|---|
| Adapter contract tests pass (parity with Hiagent + Dify) | 100% | NN% | pass/fail |
| At least 1 archetype compiles + runs in LangGraph | 1/5 | N/5 | pass/fail |
| Web target picker includes LangGraph (alpha tag) | shipped | shipped/missing | pass/fail |
| Round-trip canonical equality on narrow set | green | green/red | pass/fail |
```

If Phase 3.2 is skipped, the v1 final gate notes "LangGraph alpha deferred to v1.5".

---

## Phase 3 closing report

`reports/runtime-coverage-matrix.md`:

```markdown
# Runtime coverage matrix

| Archetype | Vertical role | Hiagent (GA) | Dify (GA) | LangGraph (alpha, optional) |
|---|---|---|---|---|
| 01 Ecommerce customer FAQ | primary | ✓ | ✓ | ✓ (alpha) or — |
| 02 TCM intake | shadow | ✓ | ✓ | — |
| 03 Clinic ops summary | shadow | ✓ | ✓ | — |
| 04 TCM follow-up | shadow | ✓ | ✓ | — |
| 05 Ecommerce order-exception | primary | ✓ | ✓ | — |
```

The matrix is the single source of truth for "where can this archetype run today"; the web app's target picker reads it.

---

## Phase 4 — Pattern Library + Self-Improvement

Three milestones: 4.1 Pattern library + retrieval; 4.2 Trace-to-corpus pipeline; 4.3 Controlled self-edit loop.

### Phase 4 repo additions

```
loom/
├── patterns/                    (NEW)
│   ├── models.py                (Pattern, PatternBinding, PatternUsage)
│   ├── store.py                 (Postgres + pgvector store)
│   ├── extract.py               (workflow → Pattern via parameterization)
│   ├── retrieve.py              (top-K retrieval; hybrid BM25 + vector)
│   ├── apply.py                 (Pattern + bindings → IR fragment, validates against base validator)
│   └── routes.py                (GET /v1/patterns, POST /v1/patterns)
├── learning/                    (NEW)
│   ├── trace_aggregator.py      (run-level metrics)
│   ├── corpus_synth.py          (trace → candidate corpus prompt)
│   ├── corpus_curator.py        (human-in-the-loop curation queue)
│   └── self_edit_proposer.py    (typed IR refactor proposals after N runs)
├── validator/                   (extension; see Phase 4.1)
│   ├── refs.py                  (extended: template_mode flag for ${{slot}})
│   └── template.py              (NEW — validate_template entry point)
└── service/routes/
    ├── patterns.py              (already covered above)
    └── proposals.py             (GET/POST /v1/proposals)

apps/web/src/
├── app/(app)/patterns/          (browse + detail)
├── app/(app)/workflows/[id]/proposals/page.tsx
└── components/
    ├── patterns/                (PatternCard, PatternMatchPanel, BindingForm)
    └── proposals/               (ProposalCard, ProposalReviewBar)

reports/
├── phase-4-1-gate.md
├── phase-4-2-gate.md
└── phase-4-3-gate.md
```

---

### Phase 4 — Milestone 4.1: Pattern library + retrieval (≈4–5 weeks)

**Goal:** Capture validated workflows as parameterized patterns; surface top-K patterns to the Planner during planning to lift first-try IR validity from 85% (Phase 2A target) toward 92%.

#### Task 4.1.0: ADR 0019 — Pattern model

```markdown
# ADR 0019 — Pattern model

Status: Proposed → Accepted (after review)
Date: 2026-MM-DD

## Decision

A `Pattern` stores a parameterized IR fragment with the following fields:

- `id`: stable slug (`<tenant>/<scope>/<name>@v<version>`).
- `owner_tenant`: tenant id; cross-tenant retrieval is forbidden (per ADR 0016).
- `scope`: registry scope the pattern is valid in (e.g., `ecommerce/kb`).
- `intent_summary`: zh-CN + en strings used for retrieval (BM25 + pgvector).
- `ir_template`: a v0.4 IR document where placeholders use the form `${{slot.name}}`. Phase 1's VarRef parser does NOT recognize `${{…}}`; Phase 4.1 ships an explicit Phase 1 validator extension (Task 4.1.1a below) that adds the `${{…}}` placeholder grammar in *template-only* mode and rejects `${{…}}` everywhere else.
- `required_slots`: list of `{name, type, description}` — must be filled at apply time.
- `optional_slots`: list of `{name, type, description, default}` — defaults applied if omitted.
- `examples`: at least 2 fully-bound IR documents that validate.
- `version`: integer, monotonically increasing per `id`.
- `created_from_workflow_id`: nullable; non-null for extracted patterns, null for hand-authored.
- `validated_run_count`: how many production runs of `created_from_workflow_id` had `success` status when extraction proposed this pattern.

Apply-time guarantee: `apply(pattern, bindings)` produces an IR document that the Phase 1 Validator accepts; if not, apply raises `PatternApplyFailed` carrying the validator failures.

## Consequences

- The pattern *template* is itself a v0.4 IR document — no second grammar — making validation and canonicalization free.
- Cross-tenant patterns are out of scope for v1 (no marketplace).
- A pattern that no longer validates (e.g., because v0.4 minor bumped) blocks retrieval and is flagged for re-extraction; we do not silently downgrade.
```

#### Task 4.1.1a: Phase 1 VarRef parser extension for templates

- [ ] Modify `loom/validator/refs.py`: add `template_mode` flag to the parser. When `template_mode=False` (default), `${{` raises `RefParseError`. When `True`, `${{slot.name}}` is parsed as a `TemplateSlotRef`.
- [ ] Create `loom/validator/template.py`: `validate_template(doc, *, scope, declared_slots) -> list[ValidationFailure]`. Like `validate(...)`, but accepts `${{slot.name}}` in any VarRef position; fails if a slot name is referenced that isn't in `declared_slots`.
- [ ] Tests: RED tests prove (a) normal mode rejects `${{`, (b) template mode accepts declared slots, (c) `validate_template` rejects undeclared slots, (d) the existing `validate(...)` keeps rejecting `${{` so non-template IR files cannot smuggle slots through.

#### Task 4.1.2: Extraction

- [ ] `loom/patterns/extract.py`: from a published, validated workflow with ≥10 successful runs, propose a parameterized pattern by:
  - identifying constants that can become slots (URLs, dataset names, prompts, top_k, budgets).
  - preserving structure (nodes, edges, policies).
  - generating `intent_summary` from `metadata.description` + `rationale` fields.
- [ ] Extraction is *proposed*, not auto-applied; Admin reviews and accepts via `POST /v1/patterns`.

#### Task 4.1.3: Retrieval + apply

- [ ] `loom/patterns/retrieve.py`: top-K retrieval against pattern intents using hybrid BM25 + pgvector. K=5 default. Tenant-scoped.
- [ ] Wire into Planner: at planning time, retrieve top-K and pass as additional few-shot context (with bindings cleared). Track which patterns were retrieved per planning call.
- [ ] `loom/patterns/apply.py`: `Pattern + bindings → IR fragment`. Validates required slots; rejects malformed bindings. Result IR must pass the *normal* validator (no `${{` in final IR).
- [ ] Web: when retrieving pattern matches during planning, the chat console offers "use pattern <name>"; clicking opens `BindingForm` to fill the slots; submit → Planner builds IR from the pattern + bindings → goes through validation as if the Planner produced it.

#### Task 4.1.4: Phase 4.1 gate

```markdown
# Phase 4.1 gate

| Criterion | Target | Actual | Status |
|---|---|---|---|
| ≥5 patterns extracted from production workflows | 5+ | N | pass/fail |
| Retrieval recall@5 on labeled corpus | ≥0.7 | NN | pass/fail |
| Planner first-try IR validity with retrieval enabled | ≥88% (full corpus) | NN% | pass/fail |
| Pattern apply path validates same as planner output | parity | parity/missing | pass/fail |
| Cross-tenant pattern leak | 0 | NN | pass/fail |
| validate() rejects ${{ outside template scope | enforced | enforced/missing | pass/fail |
```

---

### Phase 4 — Milestone 4.2: Trace-to-corpus pipeline (≈3–4 weeks)

**Goal:** Real production runs become curated corpus prompts that improve the Planner.

#### Task 4.2.0: ADR 0020 — Trace-to-corpus

```markdown
# ADR 0020 — Trace-to-corpus synthesis + curation

Status: Proposed → Accepted (after review)
Date: 2026-MM-DD

## Decision

- Synthesis runs nightly per tenant; only `success` runs (per ADR 0010 retention windows) are eligible.
- Each candidate prompt carries: tenant_id, workflow_id, run_id, intent (paraphrased from transcript), declared_context (from registry_ref + scope), ground_truth_ir (canonical IR of the published workflow at run time), license = `internal-use-only`.
- Curation requires Admin (per ADR 0012). Acceptance commits the prompt to `corpus/full/<tenant>/<archetype>/` via a service identity; rejection records a reason for telemetry.
- PII gates run twice: synthesis-time (drops candidates that contain potential PII) and pre-commit (final assertion before the git commit). A synthetic-PII injection test in CI guards both.
- No cross-tenant prompt sharing in v1; prompts stay under `corpus/full/<tenant>/`.

## Consequences

- The eval corpus from Phase 1.5 (`corpus/full/`) becomes per-tenant in Phase 3.1 (already migrated); Phase 4.2 adds candidates produced from production traffic.
- Curators cannot edit `ground_truth_ir`; if it is wrong they reject and re-extract from a different run.
```

#### Task 4.2.1: Aggregator + synthesis + curation UX

- [ ] `loom/learning/trace_aggregator.py`: per workflow per day, aggregates success/fail/partial counts, p50/p95 latency, top failure buckets. Writes to `workflow_aggregate` table.
- [ ] `loom/learning/corpus_synth.py`: for each successful run, builds a candidate prompt; lands in `corpus_candidate` table (NOT directly in `corpus/full/`).
- [ ] `loom/learning/corpus_curator.py`: queue of candidates, optionally with adversarial perturbations.
- [ ] Web: `apps/web/src/app/(app)/admin/corpus/page.tsx` renders the queue. Admin marks candidates `accepted` / `rejected` with optional editing. Accepted candidates are written to `corpus/full/<tenant>/<archetype>/` via a service-managed git commit (commits signed by the service identity).
- [ ] PII safeguards: synth never includes PII; redaction tests reuse Phase 2A patterns + final pre-commit assertion.

#### Task 4.2.2: Phase 4.2 gate

```markdown
# Phase 4.2 gate

| Criterion | Target | Actual | Status |
|---|---|---|---|
| Trace aggregator runs nightly + tested | green | green/red | pass/fail |
| Candidate corpus reaches ≥30 entries from production traffic per pilot tenant | 30+ | N | pass/fail |
| Curator accepts ≥10 to corpus/full/<tenant>/ per pilot tenant | 10+ | N | pass/fail |
| Re-running eval after corpus update | first-try IR validity stable or up | delta% | pass/fail |
| PII never reaches corpus_candidate (synthetic injection test) | 0 leaks | NN | pass/fail |
```

---

### Phase 4 — Milestone 4.3: Controlled self-edit loop (≈3–4 weeks)

**Goal:** After N runs of a workflow, FDE proposes typed IR refactors when observed metrics suggest a better policy. Proposals NEVER auto-apply; Author + Reviewer must approve.

#### Task 4.3.0: ADR 0021 — Self-edit safety

```markdown
# ADR 0021 — Self-edit proposer safety rails

Status: Proposed → Accepted (after review)
Date: 2026-MM-DD

## Decision

- Proposals are typed: `add_retry_policy`, `change_retrieval_top_k`, `agent_budget_increased`, `add_input_validator`. New kinds require a follow-up ADR amendment.
- Auto-apply is forbidden. Every proposal goes through the Phase 2B edit flow (Reviewer approval).
- Rate limit: 1 proposal per workflow per 24 hours.
- Statistical floor: no proposal until ≥50 runs of the workflow exist post-publish.
- Compliance lock: a node is exempt from proposals iff its `metadata.compliance_class` (per IR v0.4, ADR 0022) is in `{regulatory, clinical, human_review_required}` OR it calls a tool whose registry entry has `tools.<name>.compliance_class != "none"` (lock inherits up the call edge). Free-text scanning of `metadata.rationale` is NOT a safety gate.
- Suppression: an explicit Reviewer "reject_forever" suppresses the same `(workflow_id, kind, target_node_id)` for 30 days; re-proposal before that emits an audit alert.

## Consequences

- The proposer is rule-based at v1; ML-based proposers are post-v1 and require a new ADR.
- Audit receipts cover `proposal_emitted`, `proposal_accepted`, `proposal_rejected`, `proposal_rejected_forever`. Suppression bypass attempts emit `proposal_suppression_violation`.
```

#### Task 4.3.1: Proposer + approval flow + safety rails

- [ ] `loom/learning/self_edit_proposer.py`: rule-based proposals first.
  - p95 of `http` node exceeds budget AND retry succeeds when manually retried → propose `add_retry_policy(node_id, max_attempts=2)`.
  - `agent` budget exhausted in >20% of runs → propose `agent_budget_increased(node_id, +20%)`.
  - Fail rate >10% on a `condition` node consistently triggered by malformed input → propose `add_input_validator(node_id)`.
- [ ] Each proposal: typed object with `kind`, `target_node_id`, `before/after`, `rationale_from_metrics`, `confidence`, `evidence_run_ids`.
- [ ] `POST /v1/proposals`: list active proposals; Author can `accept` (creates a new draft via existing pipeline) or `reject_forever` (suppresses re-proposal of same kind for 30 days). Acceptance triggers normal Phase 2B edit flow + Reviewer approval.
- [ ] Audit receipts: `proposal_emitted`, `proposal_accepted`, `proposal_rejected`.
- [ ] Web: `apps/web/src/app/(app)/workflows/[id]/proposals/page.tsx` lists proposals with confidence + evidence; Author can preview the resulting IR diff before accepting.
- [ ] Safety: proposer never proposes against a workflow with <50 runs; never proposes lifting a compliance boundary (structural lock per ADR 0021); rate-limited per workflow (1/24h).

#### Task 4.3.2: Phase 4.3 gate

```markdown
# Phase 4.3 gate

| Criterion | Target | Actual | Status |
|---|---|---|---|
| At least 3 proposal kinds in production | 3+ | N | pass/fail |
| Auto-apply rate | 0% (always human-reviewed) | NN% | pass/fail |
| Rejected forever leak: same kind re-proposed within 30d | 0 | NN | pass/fail |
| Compliance-boundary safety: no proposal touches locked nodes (`metadata.compliance_class` set OR inherits via `tools.<name>.compliance_class`) | 0 violations | NN | pass/fail |
| Author opt-in rate (proposals accepted / shown) | tracked, no target | NN% | report |
| Reviewer approval rate on accepted proposals | tracked | NN% | report |
```

---

## Cross-cutting tasks

### CT-1: Per-milestone code review

At every milestone gate, send the diff since the previous gate to reviewer (`/ask codex "[CODE REVIEW REQUEST] ..."`). Pass criteria per CLAUDE.md §5.

### CT-2: Eval re-runs at every gate

Re-run the full corpus eval on both Hiagent + Dify; compare to the previous gate. Regressions in first-try IR validity > 2 percentage points block the gate.

### CT-3: PRD revision triggers

Each new ADR may close PRD §11 open questions. Update PRD §11 + append a "Phase 3/4 changelog" section to PRD.md / PRD.zh-CN.md at the gate.

### CT-4: Capability checklist re-verification

After every milestone, re-verify the FDE Capability Checklist (`docs/design/fde-product-design.md`) against the new surface area. Specifically: 4.1 patterns must not bypass clarification; 4.3 self-edit must not bypass review.

---

## Final consolidated gate (end of Phase 4)

`reports/v1-final-gate.md`:

```markdown
# v1 final gate

Date: YYYY-MM-DD

## PRD §2.2 outcome verification

| Outcome | Evidence |
|---|---|
| Governance: Git is single source of truth, drift contract enforced | reports/phase-2a-gate.md, reports/drift-detection.md |
| FDE collaboration loop (NL → clarify → IR → DSL → edit) | reports/phase-2b-gate.md, reports/ux-evidence.md |
| Pre-run validation | reports/phase-1-gate.md, reports/phase-1-5-gate.md |
| Bounded agent zones | reports/phase-2a-gate.md (typed I/O + budgets enforced) |
| Delivery efficiency: typical workflow <1 hour | reports/ux-evidence.md |
| Reviewer SLO <5 min | reports/ux-evidence.md |
| Portability: IR + runtime decoupled (Hiagent + Dify) | reports/runtime-coverage-matrix.md, ADR 0015 |

## PRD §10.3 KPIs

| KPI | Target | Actual | Status |
|---|---|---|---|
| First-try IR validity | ≥85% (Phase 2A) and ≥88% with patterns (Phase 4.1) | NN% | pass/fail |
| FDE create-loop success | ≥70% deep | NN% | pass/fail |
| NL edit success (recognized) | ≥80% | NN% | pass/fail |
| Reviewer summary usefulness | ≥4/5 median | N/5 | pass/fail |
| End-to-end execution success | ≥90% | NN% | pass/fail |
| Semantic conformance (both runtimes) | 100% green | NN/NN | pass/fail |
| Reverse-compile round-trip | 100% recognized | NN% | pass/fail |
| Reviewer hard-block rate | <5% | NN% | pass/fail |
| Cost / latency targets | per PRD §10.3 | NN | pass/fail |
| Replacement willingness | ≥4/5 median | N/5 | pass/fail |

## Closed PRD §11 open questions

- Q1, Q2, Q3, Q5, Q6 — closed in Phase 0 (ADR 0001–0005).
- Q4 multi-tenancy — closed in Phase 3.1 (ADR 0016).
- Q7 Build vs Buy — recorded in design notes (decision frozen at Phase 0).
- Q8 RBAC timing — closed in Phase 2B (ADR 0012).
- Q9 trademark/domain/package — pending; flag in v1 release notes.

## v1 runtime support

- Hiagent (GA, primary)
- Dify (GA, secondary)
- LangGraph (alpha if Phase 3.2 executed; deferred to v1.5 otherwise)
- n8n: NOT supported; out of scope per project owner decision 2026-05-06.
```

Cut a v1 git tag; final reviewer pass.

---

## Self-review summary

- **Spec coverage:** PRD §7 Phase 3/4 ("持续 — 多运行时扩展、模式库与自改进闭环") expanded into 5 milestones (3.1, optional 3.2, 4.1, 4.2, 4.3) with explicit gates. Multi-tenancy (PRD §11 Q4) closed in 3.1. Pattern library + self-improvement loops directly address PRD §2.3 v1 outputs and §10 KPIs that don't have a Phase 1/2 path.
- **Removed in this revision:** Phase 3.2 n8n GA (n8n out of v1 scope per project owner 2026-05-06). ADR 0006/0007/0018 withdrawn. Runtime adapter promoted to Phase 1 (no longer a Phase 3 deliverable).
- **Type consistency:** `RuntimeAdapter`, `Tenant`, `Membership`, `Pattern`, `PatternBinding`, `PatternUsage`, `Proposal` — names stable across Python and (TS-generated) web.
- **Known seams beyond v1:**
  - LangGraph remains alpha at v1 if Phase 3.2 executed; full GA is post-v1.
  - Self-edit proposer is rule-based; model-based proposer is post-v1.
  - Pattern library is per-tenant only; cross-tenant marketplace explicitly out of scope.
  - Mobile / tablet UI parity is post-v1.

---

## Execution Handoff

Plan complete. Phase 3 + Phase 4 milestones are independently shippable. Recommended:

1. **Subagent-Driven (recommended)** — Fresh subagent per milestone task; gate at every milestone end.
2. **Inline Execution** — Milestone-by-milestone in this session.

Do not start a new milestone before the prior milestone's gate has been signed by the reviewer per CLAUDE.md §5.
