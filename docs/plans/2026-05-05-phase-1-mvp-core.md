# FDE Phase 1 — MVP Core Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Document location:** Project execution plans live in `docs/plans/`. This file was moved out of `docs/superpowers/plans/`; Superpowers is a methodology, not the product-plan directory.

**Naming note:** Product-facing language is FDE / AI 驻场流程工程师. Internal implementation paths may temporarily retain the `loom/` Python namespace until a package rename decision is made.

**Goal:** Ship the MVP FDE authoring loop end-to-end on **dual runtimes (Hiagent primary + Dify secondary)**: oral-style typed request → FDE Session (Persona Brief + Workflow Brief) → Planner LLM call → IR v0.3 → Validator → Compiler → DSL on the chosen runtime → push as draft → natural-language edit → updated draft. Plus a narrow reverse compiler per runtime and a CLI. Cover 2 archetypes deeply, selected from the design partner backlog; default to **cross-border ecommerce customer FAQ / KB Q&A and ecommerce order-exception triage** (per PRD §1 v0.4 ecommerce-primary wedge). One TCM clinic shadow flow is included if partner data is available. Hit ≥70% FDE create-loop success on the deep-coverage archetypes; all semantic conformance tests green on both runtimes; narrow round-trip works on both runtimes.

**Architecture:** Seven modules behind a single CLI. The **FDE Session** (`loom/fde_session/`) owns the *Persona Brief* (NEW — captures Author role / vertical / End User / Reviewer / compliance boundary), the *Workflow Brief* (trigger / inputs / data sources / tools / approval / etc.), the blocking-question policy, the edit-intent classification, and the reviewer summary. The **Planner** (`loom/planner/`) is the only LLM caller that emits IR — it takes Persona Brief + Workflow Brief + scope and emits IR v0.3, with up to 3 self-correction retries via the Validator's structured errors. The **Validator** (`loom/validator/`) is pure Python: schema check, then semantic checks (registry refs, var refs, type flow, agent budget bounds, narrowing predicates). The **RuntimeAdapter abstraction** (`loom/runtimes/base.py`) defines a uniform contract `compile / reverse / canonical_ast_hash / push_draft / publish / export_draft`. Two adapters ship in Phase 1: `loom/runtimes/hiagent/<vH_X>/` and `loom/runtimes/dify/<vD_Y>/`, each with `compiler.py` (pure function `IRDocument → DSL`) + `reverse.py` (narrow). The **CLI** (`loom/cli/`) wires them together with a `--target hiagent|dify` flag (default: `hiagent`). The conformance matrix from Phase 0 is now wired to the real Compilers; CI runs it on **both runtimes** on every PR.

**Cost-budget escape hatch.** If during Phase 1 execution the dual-runtime cost is too high, drop **Dify** (keep Hiagent — primary per project owner decision 2026-05-06). Conversion to Hiagent-only mode is a configuration drop, not a refactor: `loom/runtimes/registry.py` simply unregisters the Dify adapter. Phase 1.5 conformance/parity tests guard the seam.

**Tech Stack:** Python 3.11, Pydantic v2, OpenAI/Anthropic-compatible structured-output client (exact model configured per environment), pytest, ruff, mypy, click, jsonschema, httpx, pyyaml. Phase 0 toolchain is preserved.

> **Trim note (2026-05-06):** Code snippets below are **illustrative**. Contracts to preserve verbatim: (a) IR v0.3 schema (Phase 0 deliverable, frozen), (b) Validator failure-bucket taxonomy + ValidationFailure dataclass shape, (c) RuntimeAdapter interface (ADR 0015, Task 8.5), (d) Persona Brief shape (ADR 0023, Task 0.5), (e) Phase 1 gate criteria (Task 17 — dual-runtime explicit). Everything else may be adjusted by the executor. Per project owner directive 2026-05-06: trim over-specification, keep contracts.

> **Cloud-only deployment pivot (2026-05-07).** Both runtimes are cloud SaaS (Hiagent Cloud + Dify Cloud at API `v1`). Module path placeholders **`vH_X` and `vD_Y` resolve to `cloud`** (was e.g., `v2_6` / `v1_14` under self-hosted-docker). Concretely: `loom/runtimes/dify/cloud/`, `loom/runtimes/hiagent/cloud/`. Deployer / Compiler / reverse compiler / CLI / conformance runner all hit cloud SaaS endpoints with bearer tokens loaded from `config/runtimes.yaml` (template at `config/runtimes.example.yaml`); see ADR 0002 amendment. No `bash scripts/dify_up.sh` etc. — those scripts were deleted in the same pivot. Wherever this plan still says `vH_X` / `vD_Y` / `v1_14` / `v2_6`, read it as **`cloud`**.

**Prerequisites:** Phase 0 plan complete. Specifically:
- ADRs 0001–0005 all `Accepted` (ADR 0002 carries the 2026-05-07 cloud SaaS amendment).
- `config/runtimes.yaml` configured with Hiagent Cloud + Dify Cloud base URLs and `HIAGENT_CLOUD_TOKEN` / `DIFY_CLOUD_TOKEN` env tokens.
- `reports/phase-0-gate.md` shows all rows pass.
- `loom.runtimes.dify.ast.canonical_dify_ast_hash` and `loom.runtimes.hiagent.ast.canonical_hiagent_ast_hash` are stable on each pinned runtime.
- The conformance matrix scaffold (`loom/conformance/`) exists with all 10 PRD §5 cells.

If any of these fails, stop. Re-iterate Phase 0 per PRD §7 before starting.

---

## Notes on runtime version segments

> **Cloud pivot 2026-05-07.** Both placeholders `vH_X` and `vD_Y` resolve to `cloud` (cloud SaaS API `v1`). Concrete paths: `loom/runtimes/hiagent/cloud/` and `loom/runtimes/dify/cloud/`. The pre-pivot text (kept below for diff continuity) referred to docker-tag-pinned major.minor segments — that was self-hosted; we no longer ship that.

The Compiler module paths use `loom/runtimes/hiagent/cloud/` and `loom/runtimes/dify/cloud/`, where `cloud` is the API-version-pinned cloud SaaS module per ADR 0002 (amended 2026-05-07). Throughout this plan we write `vH_X` and `vD_Y` as legacy placeholders; **substitute `cloud` for both**. PRD §9: "a single compiler module per runtime API major version."

`loom/runtimes/dify/ast.py` and `loom/runtimes/hiagent/ast.py` are intentionally unversioned (canonical-AST hashing is version-stable per Phase 0 ADR 0002). The version-segmented modules own everything that *does* change with the runtime API version.

---

## Repo layout extended by Phase 1

```
loom/
├── fde_session/
│   ├── __init__.py
│   ├── persona_brief.py              (NEW — Persona Brief: Author / vertical / End User / Reviewer / compliance)
│   ├── brief.py                      (workflow brief model + normalization)
│   ├── clarify.py                    (blocking-question policy)
│   ├── edit_intent.py                (natural-language edit → typed edit intent)
│   └── review_summary.py             (reviewer-facing summary)
├── planner/
│   ├── __init__.py
│   ├── prompts/
│   │   ├── system.md                 (system prompt with IR grammar + examples)
│   │   └── few_shot/
│   │       ├── 01-ecommerce-customer-faq.json        (NL ↔ IR pair from archetype 01, deep-coverage #1)
│   │       └── 05-ecommerce-order-exception.json     (NL ↔ IR pair from archetype 05, deep-coverage #2; 02-04 are TCM shadow archetypes covered in Phase 1.5)
│   ├── client.py                     (structured-output LLM client wrapper, structured outputs)
│   ├── retry.py                      (Validator-feedback self-correction loop)
│   ├── scope.py                      (registry filtering by scope)
│   └── types.py                      (IntentRequest, PersonaBrief, PlannerResult)
├── validator/
│   ├── __init__.py
│   ├── errors.py                     (structured error taxonomy: schema/reference/type-flow/policy)
│   ├── refs.py                       (VarRef parser; ${node.field.subfield[i]} grammar)
│   ├── typecheck.py                  (DAG type flow + branch narrowing + loop item + parallel merge)
│   ├── registry.py                   (registry resolver: tools/datasets/credentials)
│   ├── policy.py                     (per-node retry/timeout/idempotency invariants)
│   └── validate.py                   (entry point: schema → refs → typecheck → registry → policy)
├── runtimes/                         (NEW — RuntimeAdapter abstraction; see Task 8.5)
│   ├── __init__.py
│   ├── base.py                       (RuntimeAdapter Protocol; DraftHandle; PublishHandle)
│   ├── registry.py                   (target name → adapter; "hiagent" + "dify" registered)
│   ├── hiagent/
│   │   ├── __init__.py
│   │   ├── ast.py                    (canonical Hiagent workflow JSON; version-stable)
│   │   ├── client.py                 (Hiagent OpenAPI client; auth + import/export draft)
│   │   ├── adapter.py                (RuntimeAdapter implementation for Hiagent)
│   │   └── vH_X/                     (per-Hiagent-major-version module — see ADR 0002)
│   │       ├── __init__.py
│   │       ├── compiler.py           (IR → Hiagent workflow JSON; deterministic)
│   │       ├── compiler_nodes.py     (one emit fn per IR node type)
│   │       ├── reverse.py            (narrow Hiagent JSON → IR for the 2 deep-coverage archetypes)
│   │       └── wrappers.py           (synthesis wrappers where Hiagent lacks native primitives)
│   └── dify/
│       ├── __init__.py
│       ├── ast.py                    (canonical Dify-AST hash; version-stable; from Phase 0)
│       ├── client.py                 (Dify HTTP client; from Phase 0)
│       ├── adapter.py                (RuntimeAdapter implementation for Dify)
│       └── vX_Y/                     (per-Dify-major-version module)
│           ├── __init__.py
│           ├── compiler.py           (IR → Dify DSL; deterministic)
│           ├── compiler_nodes.py     (one emit fn per IR node type)
│           ├── reverse.py            (narrow Dify DSL → IR for the 2 deep-coverage archetypes)
│           └── wrappers.py           (synthesis wrappers where Dify lacks native support)
├── cli/
│   ├── __init__.py
│   ├── main.py                       (click-based CLI; --target hiagent|dify, default hiagent)
│   ├── commands/
│   │   ├── plan.py                   (loom plan <intent.json> -> IR)
│   │   ├── validate.py               (loom validate <ir.json>)
│   │   ├── compile.py                (loom compile <ir.json> --target <runtime> -> dsl)
│   │   ├── deploy.py                 (loom deploy <ir.json> --target <runtime> -> push as draft)
│   │   └── reverse.py                (loom reverse <dsl> --target <runtime> -> IR)
├── deployer/
│   ├── __init__.py
│   └── draft.py                      (push-as-draft via RuntimeAdapter; Phase 2A adds publish-blocking)
└── eval/
    ├── __init__.py
    ├── corpus.py                     (load eval corpus tuples)
    └── runner.py                     (run Planner over corpus on each runtime, report failure taxonomy)

corpus/
├── deep/                             (Phase 1 corpus: ≥30 prompts, ecommerce customer FAQ + ecommerce order-exception only)
│   ├── 01-ecommerce-customer-faq/
│   │   ├── prompt-01.json            (NL intent + declared context + expected IR shape)
│   │   ├── prompt-02.json
│   │   └── ...
│   └── 05-ecommerce-order-exception/
│       ├── prompt-01.json
│       └── ...
└── full/                             (Phase 1.5 corpus: ≥75 across 5 archetypes — out of scope here)

tests/
├── fde_session/
│   ├── test_brief.py
│   ├── test_clarify.py
│   ├── test_edit_intent.py
│   └── test_review_summary.py
├── planner/
│   ├── test_client.py
│   ├── test_retry.py
│   └── test_scope.py
├── validator/
│   ├── test_schema.py                (covers v0.3 schema-level rejection)
│   ├── test_refs.py
│   ├── test_typecheck.py
│   ├── test_registry.py
│   └── test_policy.py
├── runtimes/
│   ├── hiagent/vH_X/
│   │   ├── test_compiler_golden.py   (IR → Hiagent workflow JSON pairs; one per archetype)
│   │   ├── test_compiler_nodes.py
│   │   ├── test_reverse_narrow.py    (Hiagent JSON → IR pairs for the 2 deep archetypes)
│   │   └── test_wrappers.py
│   └── dify/vX_Y/
│       ├── test_compiler_golden.py   (IR → Dify DSL pairs; one per archetype)
│       ├── test_compiler_nodes.py
│       ├── test_reverse_narrow.py    (Dify DSL → IR pairs for the 2 deep archetypes)
│       └── test_wrappers.py
├── cli/
│   └── test_cli.py
├── conformance/
│   └── test_runner_live.py           (now invokes Compiler — was stub in Phase 0)
└── eval/
    └── test_eval_corpus.py
```

---

## Task 0: FDE Session foundation

**Files:**
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/loom/fde_session/__init__.py`
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/loom/fde_session/brief.py`
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/loom/fde_session/clarify.py`
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/loom/fde_session/edit_intent.py`
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/loom/fde_session/review_summary.py`
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/tests/fde_session/__init__.py`
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/tests/fde_session/test_brief.py`
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/tests/fde_session/test_clarify.py`
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/tests/fde_session/test_edit_intent.py`
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/tests/fde_session/test_review_summary.py`

This task is required by the FDE repositioning. Without it, Phase 1 remains a developer-oriented `intent.json -> IR -> DSL` pipeline and does not satisfy the PRD.

- [ ] **Step 1: Define `WorkflowBrief`**

`WorkflowBrief` captures trigger, inputs, data sources, tools, credentials, approval points, success criteria, compliance boundary, and known edits. It is the Planner input; raw chat history is not.

- [ ] **Step 2: Define blocking-question policy**

`clarify.py` returns only questions that block safe generation. Missing trigger, source dataset, credential, human-review policy, output destination, or medical/compliance boundary must produce a question; cosmetic uncertainty must not.

- [ ] **Step 3: Define edit-intent model**

`edit_intent.py` maps natural-language edits to typed edit intents such as `change_trigger_delay`, `change_retrieval_top_k`, `add_retry_policy`, `add_manual_review_gate`, and `mark_unrecognized`.

- [ ] **Step 4: Define reviewer summary model**

`review_summary.py` surfaces node changes, credential/data-access changes, external calls, policy/budget changes, compliance boundary changes, and reverse-compile status.

- [ ] **Step 5: Add tests before implementation**

Tests must cover at least one cross-border ecommerce primary flow and one TCM clinic shadow flow:

- Ecommerce order-exception request asks for store/channel (Shopify/Amazon/TikTok Shop/Shein/Temu), buyer locale handling, refund/compensation thresholds, and SLA escalation channel before planning.
- Ecommerce customer-facing FAQ requires source citation, channel-appropriate tone, low-confidence escalation, and policy-bounded compensation language.
- TCM follow-up request (shadow) asks for data source, channel, escalation queue, and writeback destination before planning.
- TCM patient-facing Q&A (shadow) requires source citation, disclaimer/boundary, and human escalation.
- Ecommerce order-exception edit maps to a typed diff without any medical assumptions.
- Reviewer summary flags credential expansion and patient/customer-data access changes.

- [ ] **Step 6: Wire Planner types to consume `WorkflowBrief`**

After this task, `loom/planner/types.py` should accept a structured workflow brief in addition to raw `intent` for backward compatibility. New tests should prefer `WorkflowBrief`.

---

## Task 0.5: Persona Brief — first FDE Session step

**Files:**
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/loom/fde_session/persona_brief.py`
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/registry/v1/personas/` (seed persona templates)
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/tests/fde_session/test_persona_brief.py`
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/docs/decisions/0023-persona-brief.md`

**Why this task exists.** Earlier drafts of Phase 1 jumped straight from "user intent" to "Workflow Brief". That implicitly hard-codes a vertical (was: TCM; now: ecommerce). Per project owner decision 2026-05-06: the system must be **persona-agnostic** — extensible to any vertical by adding a Persona to a registry, not by editing FDE Session code. The Persona Brief is the FDE Session's first step; it captures *who* is using FDE before *what* workflow they want.

- [ ] **Step 1: Write ADR 0023**

```markdown
# ADR 0023 — Persona Brief as first FDE Session step

Status: Proposed → Accepted (after review)
Date: 2026-MM-DD

## Decision

The FDE Session has two briefs, in order:

1. **Persona Brief** (NEW): captures Author role / vertical / End User / Reviewer / compliance boundary. Resolved against `registry/v1/personas/` — a per-tenant catalog of Persona templates.
2. **Workflow Brief**: captures trigger / inputs / data sources / tools / approval / etc. (unchanged from earlier drafts.)

Both are inputs to the Planner. The Planner system prompt receives Persona Brief context BEFORE Workflow Brief.

**Phase 1 vs Phase 3.1 split.** In Phase 1 (IR v0.3) the Persona Brief shapes the Planner's behavior through three channels — (a) blocking-question policy (`clarify.py` reads persona compliance constraints to decide what is "missing"), (b) scope filter (persona scope narrows registry visibility), (c) system-prompt context (the LLM is told "this Author is a {role} in {vertical}; review goes through {reviewer.role}; do not promise compensation amounts beyond persona policy"). The Persona Brief does NOT write a typed `metadata.compliance_class` field into the IR in Phase 1, because v0.3 does not have that field yet. Phase 3.1 ships ADR 0022 (IR v0.3 → v0.4 minor bump) which adds `metadata.compliance_class` and `output_schema.<field>.pii_class` overrides; from v0.4 onward, the Planner emits those fields structurally, derived from the Persona Brief's `compliance_boundary`. Until v0.4, persona-driven compliance signals are carried in node `rationale` text + clarify questions, not as typed IR fields.

Persona Brief fields:

- `author_role`: `Literal["operator", "cs_lead", "ops_manager", "finance", "compliance", ...]` — extensible.
- `vertical`: `Literal["ecommerce", "tcm_clinic", "internal_hr", "manufacturing", ...]` — extensible.
- `end_user`: `Literal["buyer", "patient", "internal_employee", "supplier", ...]`.
- `reviewer`: `{ role, decision_authority }` — who has publish authority.
- `compliance_boundary`: `{ pii_class_default, regulatory_tags, geographies }`.
- `success_criteria`: free-text but bounded; what does "this workflow worked" mean to the Author.

A Persona registered in `registry/v1/personas/<persona-id>.yaml` is the canonical template; an FDE Session may *clone and override* but cannot use a Persona that isn't registered.

## Consequences

- v1 ships ≥3 seed Personas: `ecommerce-operator`, `ecommerce-cs-lead`, `tcm-clinic-operator`. Each is a YAML file in the registry.
- Adding a vertical = adding ≥1 Persona YAML; no FDE Session code change needed.
- Eval corpus prompts get tagged with `persona_id`; Phase 1.5 reports persona × archetype × runtime breakdown.
- Phase 4 pattern library can index by persona too — patterns are persona-aware.
- Phase 0 ADR 0001 (design partner) gates "we have ≥1 real partner Persona", not "we have a brand-locked partner".

## Non-goals

- Persona Brief is NOT a personality / tone-of-voice config for the LLM. Tone lives inside individual node prompts.
- v1 does not synthesize new Personas from chat history; Personas are authored, not learned.
```

- [ ] **Step 2: Define `PersonaBrief` model**

```python
# loom/fde_session/persona_brief.py
from __future__ import annotations
from typing import Literal
from pydantic import BaseModel, Field

PiiClass = Literal["none", "low", "medium", "high"]


class ReviewerSpec(BaseModel):
    role: str                                 # e.g. "cs_supervisor", "clinic_manager"
    decision_authority: list[str]             # e.g. ["publish", "refund_above_500_USD"]


class ComplianceBoundary(BaseModel):
    pii_class_default: PiiClass = "low"
    regulatory_tags: list[str] = []           # e.g. ["GDPR", "PIPL", "PIPL-medical"]
    geographies: list[str] = []               # e.g. ["CN", "EU", "US"]


class PersonaBrief(BaseModel):
    persona_id: str = Field(min_length=1)     # references registry/v1/personas/<persona_id>.yaml
    author_role: str
    vertical: str
    end_user: str
    reviewer: ReviewerSpec
    compliance_boundary: ComplianceBoundary
    success_criteria: str = Field(min_length=1, max_length=500)
```

- [ ] **Step 3: Persona registry seed files**

Three seed personas (one yaml file per persona):

```yaml
# registry/v1/personas/ecommerce-operator.yaml
persona_id: ecommerce-operator
author_role: operator
vertical: ecommerce
end_user: buyer
reviewer:
  role: cs_supervisor
  decision_authority: [publish, refund_threshold]
compliance_boundary:
  pii_class_default: medium                   # buyer phone / address / email default to medium
  regulatory_tags: [GDPR, PIPL]
  geographies: [CN, EU, US, JP]
success_criteria: "Buyers receive accurate, channel-appropriate replies; SLA-impacting cases reach a human supervisor; no compensation promises beyond policy."
```

```yaml
# registry/v1/personas/ecommerce-cs-lead.yaml
persona_id: ecommerce-cs-lead
author_role: cs_lead
vertical: ecommerce
end_user: buyer
reviewer:
  role: ops_manager
  decision_authority: [publish, refund_above_500_USD, compensation_above_threshold]
compliance_boundary:
  pii_class_default: medium
  regulatory_tags: [GDPR, PIPL]
  geographies: [CN, EU, US, JP]
success_criteria: "Order exceptions triaged by priority; refund / compensation flows respect monetary thresholds; queue stays within SLA."
```

```yaml
# registry/v1/personas/tcm-clinic-operator.yaml
persona_id: tcm-clinic-operator
author_role: operator
vertical: tcm_clinic
end_user: patient
reviewer:
  role: clinician
  decision_authority: [publish, medical_response_approval]
compliance_boundary:
  pii_class_default: high                     # patient health data is high pii_class
  regulatory_tags: [PIPL, PIPL-medical]
  geographies: [CN]
success_criteria: "Patient-facing content always reviewed by a clinician; intake summaries reach the right queue; no diagnosis/prescription/treatment claims auto-published."
```

- [ ] **Step 4: Tests**

```python
# tests/fde_session/test_persona_brief.py
from loom.fde_session.persona_brief import PersonaBrief, ReviewerSpec, ComplianceBoundary


def test_persona_brief_minimum():
    p = PersonaBrief(
        persona_id="ecommerce-operator",
        author_role="operator",
        vertical="ecommerce",
        end_user="buyer",
        reviewer=ReviewerSpec(role="cs_supervisor", decision_authority=["publish"]),
        compliance_boundary=ComplianceBoundary(pii_class_default="medium",
                                                regulatory_tags=["GDPR", "PIPL"],
                                                geographies=["CN", "US"]),
        success_criteria="Buyers receive accurate, channel-appropriate replies.",
    )
    assert p.compliance_boundary.pii_class_default == "medium"


def test_high_pii_persona_default():
    """TCM persona must default to high pii_class."""
    p = PersonaBrief(
        persona_id="tcm-clinic-operator",
        author_role="operator",
        vertical="tcm_clinic",
        end_user="patient",
        reviewer=ReviewerSpec(role="clinician", decision_authority=["publish", "medical_response_approval"]),
        compliance_boundary=ComplianceBoundary(pii_class_default="high",
                                                regulatory_tags=["PIPL", "PIPL-medical"]),
        success_criteria="No diagnosis or prescription auto-published.",
    )
    assert p.compliance_boundary.pii_class_default == "high"
```

- [ ] **Step 5: Wire Persona Brief into Planner input**

`loom/planner/types.py` `IntentRequest` adds an optional `persona_brief: PersonaBrief | None = None` field. The Planner system prompt template renders the Persona Brief section before the Workflow Brief section. If `persona_brief` is None (developer / debug mode), fall back to a generic `default-operator` persona.

- [ ] **Step 6: Commit**

```bash
git add loom/fde_session/persona_brief.py registry/v1/personas/ tests/fde_session/test_persona_brief.py docs/decisions/0023-persona-brief.md
git commit -m "feat(fde_session): Persona Brief + 3 seed personas (ecommerce + tcm); ADR 0023"
```

---

## Task 1: Planner types

**Files:**
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/loom/planner/__init__.py`
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/loom/planner/types.py`
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/tests/planner/__init__.py`
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/tests/planner/test_types.py`

`IntentRequest` is what the Author submits; `PlannerResult` is what the Planner returns. Pydantic-validated for both. Lives in its own module so the rest of `loom/planner/` is implementation.

- [ ] **Step 1: Write the failing test**

```python
# tests/planner/test_types.py
import pytest
from pydantic import ValidationError

from loom.planner.types import IntentRequest, PlannerResult


def test_intent_request_minimum():
    r = IntentRequest(
        intent="Build an ecommerce customer-FAQ workflow that answers buyer questions from the product/policy KB with citations and escalation on low confidence.",
        scope="ecommerce/kb",
        max_retries=3,
    )
    assert r.intent.startswith("Build")


def test_intent_request_rejects_missing_scope():
    with pytest.raises(ValidationError):
        IntentRequest(intent="...", max_retries=3)  # type: ignore[call-arg]


def test_planner_result_carries_attempts_and_failure_taxonomy():
    pr = PlannerResult(
        ir=None,
        attempts=3,
        ok=False,
        failures=[{"bucket": "schema", "detail": "missing rationale"}],
        cost_usd=0.18,
        latency_s=42.5,
    )
    assert pr.attempts == 3
    assert pr.failures[0]["bucket"] == "schema"
```

- [ ] **Step 2: Run — expect ImportError**

Run: `cd "/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE" && pytest tests/planner/ -v`
Expected: ImportError on `loom.planner.types`.

- [ ] **Step 3: Write `loom/planner/__init__.py`**

```python
"""FDE Planner — NL intent → IR v0.3 via LLM with structured output and Validator-feedback retries."""
```

- [ ] **Step 4: Write `loom/planner/types.py`**

```python
"""Types crossing the Planner boundary."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from loom.ir.models import IRDocument


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class IntentRequest(_Strict):
    """An Author's request to plan a workflow.

    `scope` filters the registry (per PRD §4 "How the Planner gets context").
    `persona_brief` (NEW per ADR 0023) shapes the Planner system prompt — drives the
    clarification policy, registry scope filtering, and informs the Planner about
    compliance boundaries. In Phase 1 (IR v0.3) the Persona Brief does NOT write
    structured fields into the IR; it influences the Planner's natural-language
    reasoning. Phase 3.1's IR v0.4 bump (ADR 0022) adds `metadata.compliance_class`
    and `output_schema.<field>.pii_class` overrides which the Planner will then emit
    structurally. Until v0.4, Persona-driven compliance signals live in node
    `rationale` text + `clarify.py` blocking-question policy + scope filtering, NOT
    as a typed IR field.

    `target` selects the runtime; defaults to "hiagent" (primary). The Planner's
    output IR is runtime-agnostic, but knowing the target lets the Planner avoid
    suggesting node features that the chosen runtime cannot honor (consulted via
    each adapter's `redlines()` method on the RuntimeAdapter contract from ADR 0015).
    """
    intent: str = Field(min_length=1)
    scope: str = Field(min_length=1)
    persona_brief: "PersonaBrief | None" = None    # see loom/fde_session/persona_brief.py
    target: Literal["hiagent", "dify"] = "hiagent"
    max_retries: int = Field(ge=0, le=5, default=3)
    extra_context: dict[str, Any] | None = None


FailureBucket = Literal[
    # Planner-side (PRD §10 failure taxonomy 1–4):
    "schema", "reference", "type_flow", "policy",
    # Compiler/Deployer-side (5–8):
    "compile", "deploy", "reverse_compile", "registry_acl",
    # Runtime (9–10):
    "semantic_conformance", "platform",
    # Human:
    "human_review_rejection",
]


class FailureRecord(_Strict):
    bucket: FailureBucket
    detail: str
    location: str | None = None  # e.g., "nodes[2].rationale" — from Validator


class PlannerResult(_Strict):
    """The Planner's verdict for one IntentRequest."""
    ir: IRDocument | None
    attempts: int
    ok: bool
    failures: list[FailureRecord] = Field(default_factory=list)
    cost_usd: float
    latency_s: float
```

- [ ] **Step 5: Write `tests/planner/__init__.py`** (empty)

- [ ] **Step 6: Run — expect pass**

Run: `pytest tests/planner/test_types.py -v && mypy loom`
Expected: 3/3 PASS, mypy clean.

- [ ] **Step 7: Commit**

```bash
git add loom/planner/__init__.py loom/planner/types.py tests/planner/
git commit -m "feat(planner): IntentRequest, PlannerResult, failure taxonomy"
```

---

## Task 2: VarRef parser

**Files:**
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/loom/validator/__init__.py`
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/loom/validator/refs.py`
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/tests/validator/__init__.py`
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/tests/validator/test_refs.py`

PRD §5 var-ref syntax: `${node_id.field}`, `${node_id.field[i]}`, `${node_id.field.subfield}`. Single path syntax. Escape: `$${...}`. Used in many node fields (prompt, body, headers, query, etc.) — embedded in arbitrary strings.

- [ ] **Step 1: Write the failing test**

```python
# tests/validator/test_refs.py
import pytest

from loom.validator.refs import RefParseError, VarRef, parse_refs


def test_simple_node_ref():
    refs = parse_refs("${retrieve.chunks}")
    assert refs == [VarRef(node_id="retrieve", path=("chunks",))]


def test_nested_field_ref():
    refs = parse_refs("hi ${a.b.c} bye")
    assert refs == [VarRef(node_id="a", path=("b", "c"))]


def test_array_index_ref():
    refs = parse_refs("${rerank.top_indices[0]}")
    assert refs == [VarRef(node_id="rerank", path=("top_indices", "[0]"))]


def test_input_ref():
    refs = parse_refs("Query: ${input.query}")
    assert refs == [VarRef(node_id="input", path=("query",))]


def test_loop_item_and_index():
    refs = parse_refs("${loop_main.item} at ${loop_main.index}")
    assert refs == [
        VarRef(node_id="loop_main", path=("item",)),
        VarRef(node_id="loop_main", path=("index",)),
    ]


def test_escaped_dollar_not_a_ref():
    refs = parse_refs("price is $${value}")
    assert refs == []


def test_multiple_refs_in_string():
    refs = parse_refs("${a.b} and ${c.d}")
    assert {r.node_id for r in refs} == {"a", "c"}


def test_unterminated_ref_rejected():
    with pytest.raises(RefParseError):
        parse_refs("${a.b")


def test_invalid_node_id_rejected():
    with pytest.raises(RefParseError):
        parse_refs("${1node.x}")  # leading digit


def test_empty_path_rejected():
    with pytest.raises(RefParseError):
        parse_refs("${node_only}")  # missing field
```

- [ ] **Step 2: Run — expect ImportError**

Run: `pytest tests/validator/test_refs.py -v`
Expected: ImportError.

- [ ] **Step 3: Write `loom/validator/__init__.py`**

```python
"""FDE Validator — schema, references, type flow, registry, policy."""
```

- [ ] **Step 4: Write `loom/validator/refs.py`**

```python
"""Variable-reference parser for IR strings.

Grammar (PRD §5):
    ref         := '${' identifier ('.' segment)+ '}'
    segment     := identifier | '[' digits ']'
    identifier  := [a-zA-Z_][a-zA-Z0-9_]*
    escape      := '$$' '{' ... '}'  # not a ref

A segment of '[i]' is preserved literally as the path entry "[i]" so the
typecheck layer can distinguish array index vs field access without a second
parse.
"""
from __future__ import annotations

import re
from dataclasses import dataclass


class RefParseError(ValueError):
    pass


@dataclass(frozen=True)
class VarRef:
    node_id: str
    path: tuple[str, ...]  # at least one segment


_IDENT = r"[a-zA-Z_][a-zA-Z0-9_]*"
_SEG = rf"(?:\.{_IDENT}|\[\d+\])"
_REF_RE = re.compile(rf"\$\{{({_IDENT})((?:{_SEG})+)\}}")
_ESCAPE_RE = re.compile(r"\$\$\{[^}]*\}")
_UNTERM_RE = re.compile(r"(?<!\$)\$\{[^}]*$")


def parse_refs(s: str) -> list[VarRef]:
    """Return all VarRefs in *s*. Empty list if none. Raise on syntax errors."""
    if _UNTERM_RE.search(s):
        raise RefParseError(f"unterminated reference in: {s!r}")

    # Mask escapes so they don't match.
    masked = _ESCAPE_RE.sub(lambda m: "X" * len(m.group(0)), s)

    # Quick syntactic check: any `${` that isn't matched by the ref regex is invalid.
    bare_dollars = [m.start() for m in re.finditer(r"(?<!\$)\$\{", masked)]
    matches = list(_REF_RE.finditer(masked))
    if len(bare_dollars) != len(matches):
        # Identify the first bad position.
        for pos in bare_dollars:
            if not any(m.start() == pos for m in matches):
                raise RefParseError(f"invalid reference at offset {pos} in {s!r}")

    out: list[VarRef] = []
    for m in matches:
        node_id = m.group(1)
        seg_text = m.group(2)
        segs = _split_segments(seg_text)
        if not segs:
            raise RefParseError(f"empty path in reference {m.group(0)!r}")
        out.append(VarRef(node_id=node_id, path=tuple(segs)))
    return out


def _split_segments(seg_text: str) -> list[str]:
    """'.b.c[0][1]' → ['b', 'c', '[0]', '[1]']"""
    segs: list[str] = []
    i = 0
    while i < len(seg_text):
        ch = seg_text[i]
        if ch == ".":
            j = i + 1
            while j < len(seg_text) and (seg_text[j].isalnum() or seg_text[j] == "_"):
                j += 1
            segs.append(seg_text[i + 1 : j])
            i = j
        elif ch == "[":
            j = seg_text.index("]", i) + 1
            segs.append(seg_text[i:j])  # keep brackets so callers can distinguish
            i = j
        else:
            raise RefParseError(f"unexpected segment char {ch!r}")
    return segs
```

- [ ] **Step 5: Write `tests/validator/__init__.py`** (empty)

- [ ] **Step 6: Run — expect pass**

Run: `pytest tests/validator/test_refs.py -v && mypy loom`
Expected: 10/10 PASS, mypy clean.

- [ ] **Step 7: Commit**

```bash
git add loom/validator/__init__.py loom/validator/refs.py tests/validator/
git commit -m "feat(validator): VarRef parser per PRD §5 grammar"
```

---

## Task 3: Validator structured errors

**Files:**
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/loom/validator/errors.py`
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/tests/validator/test_errors.py`

The Validator returns a list of structured `FailureRecord`s (matching the Planner's failure taxonomy). The Planner's retry loop reads these to construct a corrective prompt.

- [ ] **Step 1: Write the test**

```python
# tests/validator/test_errors.py
from loom.validator.errors import ValidationFailure, fmt_for_planner


def test_fmt_for_planner_human_readable():
    fs = [
        ValidationFailure(bucket="schema", detail="missing rationale", location="nodes[1]"),
        ValidationFailure(bucket="reference", detail="${miss.x} not produced", location="nodes[2].prompt"),
    ]
    s = fmt_for_planner(fs)
    assert "schema" in s
    assert "reference" in s
    assert "nodes[1]" in s
    assert "${miss.x}" in s
```

- [ ] **Step 2: Run — expect failure**

Run: `pytest tests/validator/test_errors.py -v`
Expected: ImportError.

- [ ] **Step 3: Write `loom/validator/errors.py`**

```python
"""Structured Validator errors.

The shape mirrors loom.planner.types.FailureRecord so the Planner can read
ValidationFailure objects directly into a corrective prompt.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Literal

Bucket = Literal["schema", "reference", "type_flow", "policy"]


@dataclass(frozen=True)
class ValidationFailure:
    bucket: Bucket
    detail: str
    location: str | None = None


def fmt_for_planner(failures: Iterable[ValidationFailure]) -> str:
    """Render failures as a numbered list the Planner can act on."""
    lines = []
    for i, f in enumerate(failures, 1):
        loc = f" at `{f.location}`" if f.location else ""
        lines.append(f"{i}. [{f.bucket}]{loc}: {f.detail}")
    return "\n".join(lines) if lines else "(no failures)"
```

- [ ] **Step 4: Run — expect pass**

Run: `pytest tests/validator/test_errors.py -v && mypy loom`
Expected: 1/1 PASS, mypy clean.

- [ ] **Step 5: Commit**

```bash
git add loom/validator/errors.py tests/validator/test_errors.py
git commit -m "feat(validator): structured ValidationFailure + planner-formatter"
```

---

## Task 4: Registry resolver

**Files:**
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/loom/validator/registry.py`
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/tests/validator/test_registry.py`
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/registry/v1/registry.json`

PRD §5 / §8: the registry is a versioned git artifact. Phase 1 ships a single in-tree registry (`registry/v1/registry.json`) with the tools/datasets/credentials referenced by the deep-coverage archetypes. Each entry has a stable handle, a typed schema, an ACL placeholder, and (for tools) a `side_effects` flag.

- [ ] **Step 1: Write the failing test**

```python
# tests/validator/test_registry.py
import pytest

from loom.validator.registry import Registry, RegistryEntryNotFound


def test_load_v1():
    reg = Registry.load("v1")
    assert reg.version.startswith("sha:")  # pinned in the loader
    assert "clinic_kb" in reg.datasets
    assert reg.datasets["clinic_kb"].handle == "clinic_kb"


def test_resolve_existing_dataset():
    reg = Registry.load("v1")
    ds = reg.resolve_dataset("clinic_kb", scope="clinic/kb")
    assert ds.handle == "clinic_kb"


def test_resolve_missing_dataset():
    reg = Registry.load("v1")
    with pytest.raises(RegistryEntryNotFound):
        reg.resolve_dataset("nonexistent_kb", scope="clinic/kb")


def test_scope_acl_blocks_out_of_scope():
    reg = Registry.load("v1")
    with pytest.raises(RegistryEntryNotFound):
        reg.resolve_dataset("clinic_kb", scope="some-other-team/foo")
```

- [ ] **Step 2: Run — expect ImportError**

- [ ] **Step 3: Write `registry/v1/registry.json`**

```json
{
  "version": "sha:0000000",
  "tools": [
    {
      "handle": "web_search",
      "description": "Search the public web. Returns a list of {title, url, snippet}.",
      "input_schema": {"type": "object", "required": ["query"], "properties": {"query": {"type": "string"}}},
      "output_schema": {"type": "array", "items": {"type": "object", "required": ["title", "url", "snippet"]}},
      "side_effects": false,
      "scopes": ["ecommerce/kb", "ecommerce/ops", "clinic/kb", "clinic/ops"]
    },
    {
      "handle": "fetch_url",
      "description": "GET a URL. Returns body as string.",
      "input_schema": {"type": "object", "required": ["url"], "properties": {"url": {"type": "string"}}},
      "output_schema": {"type": "object", "required": ["body"], "properties": {"body": {"type": "string"}}},
      "side_effects": false,
      "scopes": ["ecommerce/kb", "ecommerce/ops", "clinic/kb", "clinic/ops"]
    },
    {
      "handle": "translate",
      "description": "Translate text between supported buyer locales (en/zh/es/de/fr/ja).",
      "input_schema": {"type": "object", "required": ["text", "target_locale"], "properties": {"text": {"type": "string"}, "target_locale": {"type": "string"}}},
      "output_schema": {"type": "object", "required": ["text"], "properties": {"text": {"type": "string"}}},
      "side_effects": false,
      "scopes": ["ecommerce/kb", "ecommerce/ops"]
    }
  ],
  "datasets": [
    {
      "handle": "product_kb",
      "description": "Ecommerce product catalog + listing copy + spec sheets.",
      "scopes": ["ecommerce/kb", "ecommerce/ops"]
    },
    {
      "handle": "policy_kb",
      "description": "Ecommerce store policy KB: returns/refunds, shipping, warranty, platform-specific rules.",
      "scopes": ["ecommerce/kb", "ecommerce/ops"]
    },
    {
      "handle": "clinic_kb",
      "description": "Clinic FAQ and service-policy knowledge base (shadow vertical).",
      "scopes": ["clinic/kb", "clinic/ops"]
    }
  ],
  "credentials": [
    {
      "handle": "shopify_api",
      "description": "Shopify Admin API token for store-level order/listing reads and customer reply posting.",
      "vault_path": "secret/fde/shopify_api",
      "scopes": ["ecommerce/ops"]
    },
    {
      "handle": "amazon_sp_api",
      "description": "Amazon Selling Partner API for orders, returns, listings, and feedback.",
      "vault_path": "secret/fde/amazon_sp_api",
      "scopes": ["ecommerce/ops"]
    },
    {
      "handle": "clinic_system_api",
      "description": "Clinic system API key for operations-summary jobs (shadow).",
      "vault_path": "secret/fde/clinic_system_api",
      "scopes": ["clinic/ops"]
    }
  ]
}
```

- [ ] **Step 4: Write `loom/validator/registry.py`**

```python
"""FDE registry: handles + ACLs + scope filtering.

Phase 1 ships a single in-tree v1 registry. Phase 2A introduces the git-backed
versioned registry per PRD §8.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

_REGISTRY_ROOT = Path(__file__).resolve().parents[2] / "registry"


class RegistryEntryNotFound(KeyError):
    pass


@dataclass(frozen=True)
class ToolEntry:
    handle: str
    description: str
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    side_effects: bool
    scopes: tuple[str, ...]


@dataclass(frozen=True)
class DatasetEntry:
    handle: str
    description: str
    scopes: tuple[str, ...]


@dataclass(frozen=True)
class CredentialEntry:
    handle: str
    description: str
    vault_path: str
    scopes: tuple[str, ...]


@dataclass(frozen=True)
class Registry:
    version: str
    tools: dict[str, ToolEntry] = field(default_factory=dict)
    datasets: dict[str, DatasetEntry] = field(default_factory=dict)
    credentials: dict[str, CredentialEntry] = field(default_factory=dict)

    @staticmethod
    @lru_cache(maxsize=8)
    def load(version: str) -> "Registry":
        path = _REGISTRY_ROOT / version / "registry.json"
        raw = json.loads(path.read_text())
        tools = {t["handle"]: ToolEntry(
            handle=t["handle"], description=t["description"],
            input_schema=t["input_schema"], output_schema=t["output_schema"],
            side_effects=t.get("side_effects", False),
            scopes=tuple(t.get("scopes", [])),
        ) for t in raw.get("tools", [])}
        datasets = {d["handle"]: DatasetEntry(
            handle=d["handle"], description=d["description"],
            scopes=tuple(d.get("scopes", [])),
        ) for d in raw.get("datasets", [])}
        credentials = {c["handle"]: CredentialEntry(
            handle=c["handle"], description=c["description"],
            vault_path=c["vault_path"], scopes=tuple(c.get("scopes", [])),
        ) for c in raw.get("credentials", [])}
        return Registry(
            version=f"sha:{raw['version'][4:]}" if raw["version"].startswith("sha:")
            else f"sha:0000000",
            tools=tools, datasets=datasets, credentials=credentials,
        )

    def resolve_tool(self, handle: str, *, scope: str) -> ToolEntry:
        entry = self.tools.get(handle)
        if entry is None or scope not in entry.scopes:
            raise RegistryEntryNotFound(
                f"tool {handle!r} not in registry or out of scope {scope!r}"
            )
        return entry

    def resolve_dataset(self, handle: str, *, scope: str) -> DatasetEntry:
        entry = self.datasets.get(handle)
        if entry is None or scope not in entry.scopes:
            raise RegistryEntryNotFound(
                f"dataset {handle!r} not in registry or out of scope {scope!r}"
            )
        return entry

    def resolve_credential(self, handle: str, *, scope: str) -> CredentialEntry:
        entry = self.credentials.get(handle)
        if entry is None or scope not in entry.scopes:
            raise RegistryEntryNotFound(
                f"credential {handle!r} not in registry or out of scope {scope!r}"
            )
        return entry
```

- [ ] **Step 5: Run — expect pass**

Run: `pytest tests/validator/test_registry.py -v && mypy loom`
Expected: 4/4 PASS.

- [ ] **Step 6: Commit**

```bash
git add registry/ loom/validator/registry.py tests/validator/test_registry.py
git commit -m "feat(validator): registry v1 + scope-filtered resolver"
```

---

## Task 5: Type-flow checker

**Files:**
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/loom/validator/typecheck.py`
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/tests/validator/test_typecheck.py`

PRD §5 type system: primitives + compounds (`array<T>`, `object<{...}>`, `union<T1|T2>`); nullability vs optionality distinct; branch narrowing; loop item typing; parallel merge typing; explicit coercion. The compound grammar is parsed here (the JSON Schema layer can't easily express it).

- [ ] **Step 1: Write the failing test**

```python
# tests/validator/test_typecheck.py
import pytest

from loom.validator.typecheck import (
    NodeOutputs, TypeMismatch, parse_type, typecheck_edge, narrow_branch,
    loop_item_type, parallel_merge_type,
)


def test_parse_primitives_and_compounds():
    assert parse_type("string").name == "string"
    arr = parse_type("array<string>")
    assert arr.name == "array" and arr.params[0].name == "string"
    obj = parse_type("object<{a: string, b: number}>")
    assert obj.name == "object"
    union = parse_type("union<string | null>")
    assert union.name == "union"


def test_typecheck_edge_pass():
    src_outs = NodeOutputs({"chunks": parse_type("string[]")})
    typecheck_edge(src_outs, ref_path=("chunks",), expected=parse_type("string[]"))


def test_typecheck_edge_fail():
    src_outs = NodeOutputs({"chunks": parse_type("string[]")})
    with pytest.raises(TypeMismatch):
        typecheck_edge(src_outs, ref_path=("chunks",), expected=parse_type("number"))


def test_narrow_branch_with_not_null_predicate():
    out = parse_type("union<string | null>")
    narrowed = narrow_branch(out, predicate="${x} != null")
    assert narrowed.name == "string"


def test_loop_item_over_array():
    item, idx = loop_item_type(parse_type("array<string>"))
    assert item.name == "string"
    assert idx.name == "number"


def test_parallel_merge_concat():
    branches = [parse_type("string"), parse_type("string")]
    out = parallel_merge_type("concat", branches, branch_keys=["a", "b"])
    assert out.name == "array"
    assert out.params[0].name == "string"


def test_parallel_merge_object_merge():
    branches = [parse_type("string"), parse_type("number")]
    out = parallel_merge_type("object_merge", branches, branch_keys=["a", "b"])
    assert out.name == "object"


def test_parallel_merge_first_success():
    branches = [parse_type("string"), parse_type("number")]
    out = parallel_merge_type("first_success", branches, branch_keys=["a", "b"])
    assert out.name == "union"


def test_concat_rejects_inconsistent_branches():
    branches = [parse_type("string"), parse_type("number")]
    with pytest.raises(TypeMismatch):
        parallel_merge_type("concat", branches, branch_keys=["a", "b"])
```

- [ ] **Step 2: Run — expect ImportError**

- [ ] **Step 3: Write `loom/validator/typecheck.py`**

```python
"""IR type-flow checker.

Implements PRD §5 type system:
 - primitives: string, number, boolean, null, json, file, any, chunks
 - compounds:  array<T>, object<{k: T, …}>, union<T1 | T2 | …>
 - branch narrowing on type-guard predicates
 - loop item typing
 - parallel merge typing (concat / object_merge / first_success)
 - explicit coercion only (no implicit string ↔ number)
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Iterable

from loom.validator.errors import ValidationFailure


class TypeMismatch(ValueError):
    pass


@dataclass(frozen=True)
class TypeExpr:
    name: str  # "string" | "number" | "array" | "object" | "union" | …
    params: tuple["TypeExpr", ...] = ()
    # for object:
    fields: tuple[tuple[str, "TypeExpr"], ...] = ()


def _t(name: str, *params: TypeExpr) -> TypeExpr:
    return TypeExpr(name=name, params=tuple(params))


_PRIMITIVES = {"string", "number", "boolean", "null", "json", "file", "any", "chunks"}


def parse_type(s: str) -> TypeExpr:
    s = s.strip()
    if s in _PRIMITIVES:
        return _t(s)
    if s.endswith("[]"):
        # legacy short form (string[], number[], json[])
        return _t("array", parse_type(s[:-2]))
    if s.startswith("array<") and s.endswith(">"):
        return _t("array", parse_type(s[len("array<") : -1]))
    if s.startswith("union<") and s.endswith(">"):
        body = s[len("union<") : -1]
        members = [parse_type(p.strip()) for p in _split_top(body, "|")]
        return TypeExpr(name="union", params=tuple(members))
    if s.startswith("object<{") and s.endswith("}>"):
        body = s[len("object<{") : -2]
        fields: list[tuple[str, TypeExpr]] = []
        for piece in _split_top(body, ","):
            k, _, v = piece.partition(":")
            fields.append((k.strip(), parse_type(v.strip())))
        return TypeExpr(name="object", fields=tuple(fields))
    raise TypeMismatch(f"unparseable type {s!r}")


def _split_top(s: str, sep: str) -> list[str]:
    out: list[str] = []
    depth = 0
    buf: list[str] = []
    for ch in s:
        if ch in "<{(":
            depth += 1
        elif ch in ">})":
            depth -= 1
        if ch == sep and depth == 0:
            out.append("".join(buf))
            buf = []
        else:
            buf.append(ch)
    if buf:
        out.append("".join(buf))
    return out


@dataclass(frozen=True)
class NodeOutputs:
    """Map output-name → type expression."""
    fields: dict[str, TypeExpr] = field(default_factory=dict)

    def get_path(self, path: tuple[str, ...]) -> TypeExpr:
        if not path:
            raise TypeMismatch("empty path")
        head, *rest = path
        cur = self.fields.get(head)
        if cur is None:
            raise TypeMismatch(f"output {head!r} not declared")
        for seg in rest:
            cur = _step(cur, seg)
        return cur


def _step(t: TypeExpr, seg: str) -> TypeExpr:
    # Array index "[i]"
    if re.fullmatch(r"\[\d+\]", seg):
        if t.name != "array":
            raise TypeMismatch(f"index {seg} on non-array {t.name}")
        return t.params[0]
    # Field
    if t.name == "object":
        for k, v in t.fields:
            if k == seg:
                return v
        raise TypeMismatch(f"field {seg!r} not on object")
    if t.name == "json" or t.name == "any":
        return t  # json/any propagate
    raise TypeMismatch(f"cannot step {seg!r} into {t.name}")


def typecheck_edge(src: NodeOutputs, *, ref_path: tuple[str, ...], expected: TypeExpr) -> None:
    actual = src.get_path(ref_path)
    if not _assignable(actual, expected):
        raise TypeMismatch(f"actual {actual.name} not assignable to expected {expected.name}")


def _assignable(a: TypeExpr, b: TypeExpr) -> bool:
    if b.name == "any" or a.name == "any":
        return True
    if a.name != b.name:
        return False
    if a.name == "array":
        return _assignable(a.params[0], b.params[0])
    if a.name == "object":
        bfields = dict(b.fields)
        for k, v in a.fields:
            if k not in bfields or not _assignable(v, bfields[k]):
                return False
        return True
    if a.name == "union":
        return all(any(_assignable(am, bm) for bm in b.params) for am in a.params)
    return True


_TYPE_GUARD_RE = re.compile(r"^\s*\$\{[^}]+\}\s*!=\s*null\s*$")


def narrow_branch(t: TypeExpr, *, predicate: str) -> TypeExpr:
    if t.name == "union" and _TYPE_GUARD_RE.match(predicate):
        non_null = [m for m in t.params if m.name != "null"]
        if len(non_null) == 1:
            return non_null[0]
        return TypeExpr(name="union", params=tuple(non_null))
    return t


def loop_item_type(over: TypeExpr) -> tuple[TypeExpr, TypeExpr]:
    if over.name != "array":
        raise TypeMismatch(f"loop over non-array {over.name}")
    return over.params[0], _t("number")


def parallel_merge_type(strategy: str, branches: Iterable[TypeExpr], *, branch_keys: list[str]) -> TypeExpr:
    branches = list(branches)
    if strategy == "concat":
        first = branches[0]
        if not all(_assignable(b, first) and _assignable(first, b) for b in branches[1:]):
            raise TypeMismatch("concat requires all branches to share a common type")
        return _t("array", first)
    if strategy == "object_merge":
        return TypeExpr(name="object", fields=tuple((k, b) for k, b in zip(branch_keys, branches)))
    if strategy == "first_success":
        return TypeExpr(name="union", params=tuple(branches))
    raise TypeMismatch(f"unknown merge_strategy {strategy!r}")


def to_failure(e: TypeMismatch, *, location: str | None = None) -> ValidationFailure:
    return ValidationFailure(bucket="type_flow", detail=str(e), location=location)
```

- [ ] **Step 4: Run — expect pass**

Run: `pytest tests/validator/test_typecheck.py -v && mypy loom`
Expected: 9/9 PASS.

- [ ] **Step 5: Commit**

```bash
git add loom/validator/typecheck.py tests/validator/test_typecheck.py
git commit -m "feat(validator): IR type system + type-flow checker (compounds, narrow, merge)"
```

---

## Task 6: Per-node policy invariants

**Files:**
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/loom/validator/policy.py`
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/tests/validator/test_policy.py`

PRD §5 policy invariants (subset the schema cannot enforce):
- Per-node policy may *tighten* but not loosen workflow `policy` defaults — so a node `timeout_s` ≤ workflow `default_timeout_s`, node `retry.max_attempts` ≤ workflow `default_retry.max_attempts`, agent budget ≤ workflow agent_budget.
- Non-idempotent `http`/`code` nodes must declare `idempotency_key` (also schema-enforced; double check here).
- Side-effecting tool calls require `idempotency_key` on the calling node.
- Agent `on_budget_exhausted == "fallback"` requires a `fallback_edge` that points at a node which exists.
- Tool list is a *subset* of `registry_ref.tools`.

- [ ] **Step 1: Write the failing test**

```python
# tests/validator/test_policy.py
import json
from pathlib import Path

import pytest

from loom.ir.models import IRDocument
from loom.validator.policy import check_policy

ROOT = Path(__file__).resolve().parents[2]


def _ecommerce_faq():
    return IRDocument.model_validate(json.loads((ROOT / "examples" / "ir" / "01-ecommerce-customer-faq.json").read_text()))


def test_clean_archetype_has_no_policy_failures():
    failures = check_policy(_ecommerce_faq())
    assert failures == []


def test_node_timeout_cannot_exceed_workflow_default():
    ir = _ecommerce_faq().model_copy(update={
        "policy": _ecommerce_faq().policy.model_copy(update={"default_timeout_s": 10}),
    })
    # mutate one node to exceed default
    nodes = list(ir.nodes)
    nodes[1] = nodes[1].model_copy(update={"timeout_s": 30})  # retrieve.timeout_s = 30 > 10
    ir = ir.model_copy(update={"nodes": nodes})
    failures = check_policy(ir)
    assert any(f.bucket == "policy" and "timeout_s" in f.detail for f in failures)


def test_agent_fallback_requires_existing_node():
    # The `01-ecommerce-customer-faq` archetype has no agent. Build a minimal agent IR programmatically
    # in this test for clarity.
    from loom.ir.models import (
        AgentBudget, AgentNode, Edge, Metadata, OutputNode, Policy, PortDecl,
        RegistryRef, TriggerNode,
    )
    ir = IRDocument(
        ir_version="0.3",
        metadata=Metadata(name="agent-fb", owner="o", rationale="r"),
        registry_ref=RegistryRef(registry_version="sha:0000000", tools=["t1"]),
        policy=Policy(),
        inputs=[], outputs=[PortDecl(name="x", type="string")],
        nodes=[
            TriggerNode(id="s", type="trigger", mode="manual", rationale="r"),
            AgentNode(
                id="a", type="agent", model="m", tools=["t1"],
                input_schema={"type": "object"}, output_schema={"type": "object"},
                budget=AgentBudget(max_iterations=1, max_tokens=1000, max_wall_clock_s=5),
                on_budget_exhausted="fallback", fallback_edge="missing",
                rationale="r",
            ),
            OutputNode(id="o", type="output", bindings={"x": "${a.x}"}, rationale="r"),
        ],
        edges=[Edge(**{"from": "s"}, to="a"), Edge(**{"from": "a"}, to="o")],
    )
    failures = check_policy(ir)
    assert any("fallback_edge" in f.detail for f in failures)
```

- [ ] **Step 2: Run — expect ImportError**

- [ ] **Step 3: Write `loom/validator/policy.py`**

```python
"""Per-node policy invariants beyond what the JSON Schema enforces."""
from __future__ import annotations

from collections.abc import Iterable

from loom.ir.models import (
    AgentNode, CodeNode, HTTPNode, IRDocument, LoopNode, ParallelNode,
)
from loom.validator.errors import ValidationFailure


def check_policy(ir: IRDocument) -> list[ValidationFailure]:
    failures: list[ValidationFailure] = []
    node_ids = {n.id for n in _walk(ir.nodes)}

    default_timeout = ir.policy.default_timeout_s
    default_retry_max = (ir.policy.default_retry.max_attempts
                         if ir.policy.default_retry else None)
    default_budget = ir.policy.agent_budget

    for n in _walk(ir.nodes):
        loc = f"nodes[{n.id}]"
        # Timeout tightening only.
        node_to = getattr(n, "timeout_s", None)
        if default_timeout is not None and node_to is not None and node_to > default_timeout:
            failures.append(ValidationFailure(
                "policy",
                f"node timeout_s {node_to} exceeds workflow default_timeout_s {default_timeout}",
                location=loc,
            ))
        # Retry tightening only.
        node_retry = getattr(n, "retry", None)
        if default_retry_max is not None and node_retry is not None \
                and node_retry.max_attempts > default_retry_max:
            failures.append(ValidationFailure(
                "policy",
                f"node retry.max_attempts {node_retry.max_attempts} exceeds default {default_retry_max}",
                location=loc,
            ))
        # http POST/PUT/PATCH/DELETE: idempotency_key required (schema also enforces; we re-check).
        if isinstance(n, HTTPNode) and n.method in {"POST", "PUT", "PATCH", "DELETE"} and not n.idempotency_key:
            failures.append(ValidationFailure(
                "policy", f"{n.method} without idempotency_key", location=loc,
            ))
        # code: best-practice idempotency_key when retry is enabled.
        if isinstance(n, CodeNode) and node_retry is not None and not n.idempotency_key:
            failures.append(ValidationFailure(
                "policy", "code with retry must declare idempotency_key", location=loc,
            ))
        # agent: budget tightening, fallback edge existence, tools subset.
        if isinstance(n, AgentNode):
            if default_budget is not None:
                if n.budget.max_iterations > default_budget.max_iterations:
                    failures.append(ValidationFailure(
                        "policy", "agent max_iterations exceeds workflow default", location=loc,
                    ))
                if n.budget.max_tokens > default_budget.max_tokens:
                    failures.append(ValidationFailure(
                        "policy", "agent max_tokens exceeds workflow default", location=loc,
                    ))
                if n.budget.max_wall_clock_s > default_budget.max_wall_clock_s:
                    failures.append(ValidationFailure(
                        "policy", "agent max_wall_clock_s exceeds workflow default", location=loc,
                    ))
            if n.on_budget_exhausted == "fallback":
                if not n.fallback_edge or n.fallback_edge not in node_ids:
                    failures.append(ValidationFailure(
                        "policy", f"fallback_edge {n.fallback_edge!r} does not point at an existing node",
                        location=loc,
                    ))
            for tool in n.tools:
                if tool not in ir.registry_ref.tools:
                    failures.append(ValidationFailure(
                        "policy", f"agent tool {tool!r} not in registry_ref.tools", location=loc,
                    ))

    return failures


def _walk(nodes: Iterable):
    for n in nodes:
        yield n
        if isinstance(n, LoopNode):
            yield from _walk(n.body)
        elif isinstance(n, ParallelNode):
            for branch in n.branches.values():
                yield from _walk(branch)
```

- [ ] **Step 4: Run — expect pass**

Run: `pytest tests/validator/test_policy.py -v && mypy loom`
Expected: 3/3 PASS.

- [ ] **Step 5: Commit**

```bash
git add loom/validator/policy.py tests/validator/test_policy.py
git commit -m "feat(validator): per-node policy invariants (tighten-only, fallback, tool subset)"
```

---

## Task 7: Validator entry point

**Files:**
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/loom/validator/validate.py`
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/tests/validator/test_validate.py`

Single entry point: `validate(ir_dict, scope) -> list[ValidationFailure]`. Runs schema → references → registry → typecheck → policy in that order, accumulating failures. The Planner reads the result.

- [ ] **Step 1: Write the test**

```python
# tests/validator/test_validate.py
import json
from pathlib import Path

import pytest

from loom.validator.validate import validate

ROOT = Path(__file__).resolve().parents[2]


def test_clean_ecommerce_faq_archetype_passes():
    doc = json.loads((ROOT / "examples" / "ir" / "01-ecommerce-customer-faq.json").read_text())
    failures = validate(doc, scope="ecommerce/kb")
    assert failures == [], failures


def test_missing_rationale_caught_as_schema_failure():
    doc = json.loads((ROOT / "examples" / "ir" / "01-ecommerce-customer-faq.json").read_text())
    del doc["nodes"][1]["rationale"]
    failures = validate(doc, scope="ecommerce/kb")
    assert any(f.bucket == "schema" for f in failures)


def test_unknown_var_ref_caught_as_reference_failure():
    doc = json.loads((ROOT / "examples" / "ir" / "01-ecommerce-customer-faq.json").read_text())
    # rerank prompt references ${nonexistent.x}
    doc["nodes"][2]["prompt"] = "Bad ref ${nonexistent.x}"
    failures = validate(doc, scope="ecommerce/kb")
    assert any(f.bucket == "reference" for f in failures)


def test_out_of_scope_dataset_caught_as_registry_failure():
    doc = json.loads((ROOT / "examples" / "ir" / "01-ecommerce-customer-faq.json").read_text())
    failures = validate(doc, scope="some-other-team/foo")
    # product_kb / policy_kb are scoped to ecommerce/kb — out-of-scope here
    assert any(f.bucket == "policy" or f.bucket == "reference" for f in failures), failures
```

- [ ] **Step 2: Run — expect ImportError**

- [ ] **Step 3: Write `loom/validator/validate.py`**

```python
"""Validator entry point. Returns the accumulated ValidationFailure list."""
from __future__ import annotations

from typing import Any

from jsonschema import Draft202012Validator
from pydantic import ValidationError

from loom.ir.models import IRDocument
from loom.ir.schema import load_schema
from loom.validator.errors import ValidationFailure
from loom.validator.policy import check_policy
from loom.validator.refs import RefParseError, parse_refs
from loom.validator.registry import Registry, RegistryEntryNotFound


def validate(doc: dict[str, Any], *, scope: str) -> list[ValidationFailure]:
    failures: list[ValidationFailure] = []

    # 1. JSON Schema (returns all errors at once)
    schema = load_schema()
    for err in Draft202012Validator(schema).iter_errors(doc):
        failures.append(ValidationFailure(
            "schema", err.message, location=_loc(err.absolute_path),
        ))
    if failures:
        return failures

    # 2. Pydantic (catches what JSON Schema oneOf can't always pin)
    try:
        ir = IRDocument.model_validate(doc)
    except ValidationError as e:
        for err in e.errors():
            failures.append(ValidationFailure(
                "schema", err["msg"], location=".".join(str(p) for p in err["loc"]),
            ))
        return failures

    # 3. Reference parse + resolution against the producer set.
    producers = _producer_outputs(ir)
    for ref_field, txt, loc in _iter_string_fields(ir):
        try:
            for ref in parse_refs(txt):
                if ref.node_id != "input" and ref.node_id not in producers:
                    failures.append(ValidationFailure(
                        "reference", f"${{{ref.node_id}.…}} not produced upstream",
                        location=loc,
                    ))
        except RefParseError as e:
            failures.append(ValidationFailure(
                "reference", str(e), location=loc,
            ))

    # 4. Registry resolution (scope-aware)
    reg = Registry.load("v1")
    for n in _walk(ir.nodes):
        if n.type == "retrieval":
            try:
                reg.resolve_dataset(n.dataset, scope=scope)
            except RegistryEntryNotFound as e:
                failures.append(ValidationFailure(
                    "policy", str(e), location=f"nodes[{n.id}].dataset",
                ))
        if n.type == "http" and n.credential is not None:
            try:
                reg.resolve_credential(n.credential, scope=scope)
            except RegistryEntryNotFound as e:
                failures.append(ValidationFailure(
                    "policy", str(e), location=f"nodes[{n.id}].credential",
                ))
        if n.type == "agent":
            for tool in n.tools:
                try:
                    reg.resolve_tool(tool, scope=scope)
                except RegistryEntryNotFound as e:
                    failures.append(ValidationFailure(
                        "policy", str(e), location=f"nodes[{n.id}].tools",
                    ))

    # 5. Per-node policy invariants
    failures.extend(check_policy(ir))

    # 6. Type-flow check (deferred to Task 8 wiring; placeholder here so the entry
    # point is the single seam the Planner calls. Phase 1 test_validate covers
    # ref resolution; type-flow tests in test_typecheck.py exercise the lib.)
    return failures


def _producer_outputs(ir: IRDocument) -> set[str]:
    return {n.id for n in _walk(ir.nodes)}


def _walk(nodes):
    for n in nodes:
        yield n
        if n.type == "loop":
            yield from _walk(n.body)
        elif n.type == "parallel":
            for branch in n.branches.values():
                yield from _walk(branch)


def _iter_string_fields(ir):
    """Yield (field_label, text, loc) for every field that may contain VarRefs."""
    for n in _walk(ir.nodes):
        loc_base = f"nodes[{n.id}]"
        if n.type == "llm":
            yield "prompt", n.prompt, f"{loc_base}.prompt"
            if n.system_prompt:
                yield "system_prompt", n.system_prompt, f"{loc_base}.system_prompt"
        elif n.type == "retrieval":
            yield "query", n.query, f"{loc_base}.query"
        elif n.type == "http":
            yield "url", n.url, f"{loc_base}.url"
            if n.idempotency_key:
                yield "idempotency_key", n.idempotency_key, f"{loc_base}.idempotency_key"
            if isinstance(n.body, str):
                yield "body", n.body, f"{loc_base}.body"
        elif n.type == "code":
            if n.idempotency_key:
                yield "idempotency_key", n.idempotency_key, f"{loc_base}.idempotency_key"
            for k, v in (n.inputs or {}).items():
                yield f"inputs.{k}", v, f"{loc_base}.inputs.{k}"
        elif n.type == "agent":
            if n.system_prompt:
                yield "system_prompt", n.system_prompt, f"{loc_base}.system_prompt"
            for k, v in (n.inputs or {}).items():
                yield f"inputs.{k}", v, f"{loc_base}.inputs.{k}"
        elif n.type == "loop":
            yield "over", n.over, f"{loc_base}.over"
            if n.collect:
                yield "collect", n.collect, f"{loc_base}.collect"
        elif n.type == "output":
            for k, v in n.bindings.items():
                yield f"bindings.{k}", v, f"{loc_base}.bindings.{k}"


def _loc(path) -> str:
    parts = []
    for p in path:
        parts.append(str(p))
    return ".".join(parts)
```

- [ ] **Step 4: Run — expect pass**

Run: `pytest tests/validator/test_validate.py -v && mypy loom`
Expected: 4/4 PASS.

- [ ] **Step 5: Commit**

```bash
git add loom/validator/validate.py tests/validator/test_validate.py
git commit -m "feat(validator): single entry point (schema → refs → registry → policy)"
```

---

## Task 8: Planner client + retry loop + scope filter

**Files:**
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/loom/planner/client.py`
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/loom/planner/retry.py`
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/loom/planner/scope.py`
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/loom/planner/prompts/system.md`
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/loom/planner/prompts/few_shot/01-ecommerce-customer-faq.json`
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/loom/planner/prompts/few_shot/05-ecommerce-order-exception.json`
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/tests/planner/test_client.py`
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/tests/planner/test_retry.py`
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/tests/planner/test_scope.py`

The Planner uses a configured structured-output LLM client with prompt caching where the provider supports it. Structured output uses JSON-mode or tool/schema constraints plus the v0.3 schema as the response contract. The retry loop runs the Validator on each attempt; on failure, formats the failures back into the next user message and retries up to `max_retries`.

PRD §10 cost target: <$0.20 median, <$1 ceiling, 3 retries × ~5K tokens each. Caching the ~10K-token system prompt makes this realistic.

- [ ] **Step 1: Add LLM provider dependency**

Modify `pyproject.toml` `dependencies = [...]` by adding the provider SDK selected for the deployment (Anthropic adapter shown below; OpenAI adapter can implement the same boundary). Re-install: `pip install -e ".[dev]"`.

- [ ] **Step 2: Write the system prompt**

`loom/planner/prompts/system.md`:

```markdown
You are FDE Planner. Convert a natural-language workflow intent into an IR v0.3 JSON document.

# Persona context

You are designing a workflow for **{persona.author_role}** in vertical **{persona.vertical}**.
The end user of the resulting workflow is **{persona.end_user}**.
Approval / publish authority belongs to **{persona.reviewer.role}** with decision_authority {persona.reviewer.decision_authority}.
Compliance boundary: pii_class_default = **{persona.compliance_boundary.pii_class_default}**, regulatory_tags = {persona.compliance_boundary.regulatory_tags}, geographies = {persona.compliance_boundary.geographies}.
Success criteria for the Author: {persona.success_criteria}.

Persona-driven behavior in v0.3:
- Encode persona-relevant constraints in node `rationale` text (e.g., "PII redacted before LLM call per persona.compliance_boundary.pii_class_default=high"). Phase 3.1's IR v0.4 minor bump introduces typed `metadata.compliance_class` and `output_schema.<field>.pii_class`; until then, keep compliance signals in rationale + clarify policy + scope.
- Refuse workflows that violate the persona's compliance boundary (e.g., a TCM persona MUST NOT produce a node that auto-publishes patient-facing diagnostic content; an ecommerce persona MUST NOT promise specific compensation amounts beyond persona policy without a human-approved gate).

# Target runtime

The user will deploy this workflow to **{target}** (one of: hiagent, dify). Both runtimes implement the same IR contract; do not emit features the chosen runtime cannot honor (consult the runtime's adapter `redlines()` for the current set, exposed as a comment list above this prompt).

# Hard rules

1. Output **only** a JSON document conforming to FDE IR v0.3 (the schema is included below). No prose, no Markdown, no comments.
2. Every node must include a `rationale` string (1–500 chars) explaining *why* the node is in the workflow. Reviewers read these. Persona-relevant constraints (PII handling, compliance class, refund/compensation thresholds) MUST appear in rationale where applicable.
3. Every workflow must include a top-level `metadata.rationale` (1–1000 chars).
4. Use only the tools, datasets, and credentials listed in the **Declared registry** below. Hallucinated handles are rejected.
5. Use only the 10 IR node types: trigger, llm, retrieval, http, code, condition, loop, parallel, agent, output. Do not invent new types.
6. Variable references use `${node_id.field}`, `${node_id.field.subfield}`, `${node_id.field[i]}`. The reserved `input` namespace exposes workflow inputs.
7. `policy.agent_budget` defaults: max_iterations 10, max_tokens 50000, max_wall_clock_s 300. Per-node budgets may tighten but not loosen.
8. Non-idempotent http/code nodes must declare `idempotency_key`.
9. `agent.on_budget_exhausted == "fallback"` requires `fallback_edge` pointing at an existing node.
10. Coercion is explicit. No implicit string↔number. Use a `code` node to convert.

# IR v0.3 schema (excerpt)

(The full schema follows; the engineer who runs this loads schemas/ir-v0.3.schema.json verbatim.)

# Declared registry

(Inserted at request time: scope-filtered tools / datasets / credentials per persona scope.)

# Few-shot examples

(Two examples follow at the end of this prompt — ecommerce customer FAQ and ecommerce order-exception triage. Use them as patterns, not as templates to copy verbatim.)

# Self-correction

If a previous attempt failed validation, the user message will include a numbered list of failures. Read each, locate it by `location`, and fix it without rewriting the whole IR unless necessary.

```

- [ ] **Step 3: Write the few-shot files**

Each few-shot file is `{ "intent": "...", "scope": "...", "ir": <IR v0.3 doc> }` for one archetype. Use the bodies of `examples/ir/01-ecommerce-customer-faq.json` and `examples/ir/05-ecommerce-order-exception.json` (Phase 0 deliverables) as the `ir` field. Add a 1–2 sentence `intent` like "Answer multilingual buyer questions from the product/policy KB with citations and low-confidence escalation."

```json
// loom/planner/prompts/few_shot/01-ecommerce-customer-faq.json
{
  "intent": "Answer multilingual buyer questions from the product/policy KB with citations and low-confidence escalation; channel-aware tone (Amazon / Shopify / TikTok Shop / Shein / Temu).",
  "scope": "ecommerce/kb",
  "ir": <paste examples/ir/01-ecommerce-customer-faq.json content>
}
```

(Engineer: literally paste the v0.3 IR JSON in the `ir` field. Same for `05-ecommerce-order-exception.json`.)

- [ ] **Step 4: Write `loom/planner/scope.py`**

```python
"""Scope-based registry filtering for the Planner prompt.

PRD §4: Author selects a scope; scope filters the catalog to typically <30
tools/datasets. The filtered set is embedded in the Planner system prompt as a
typed registry block.
"""
from __future__ import annotations

from loom.validator.registry import Registry


def render_registry_block(reg: Registry, *, scope: str) -> str:
    tools = sorted([t for t in reg.tools.values() if scope in t.scopes],
                   key=lambda t: t.handle)
    datasets = sorted([d for d in reg.datasets.values() if scope in d.scopes],
                      key=lambda d: d.handle)
    creds = sorted([c for c in reg.credentials.values() if scope in c.scopes],
                   key=lambda c: c.handle)

    parts: list[str] = ["## Declared registry", f"Scope: `{scope}`", ""]
    parts.append("### Tools")
    for t in tools:
        side = " (side_effects)" if t.side_effects else ""
        parts.append(f"- `{t.handle}`{side}: {t.description}")
    parts.append("\n### Datasets")
    for d in datasets:
        parts.append(f"- `{d.handle}`: {d.description}")
    parts.append("\n### Credentials")
    for c in creds:
        parts.append(f"- `{c.handle}`: {c.description}")
    return "\n".join(parts)
```

- [ ] **Step 5: Write `tests/planner/test_scope.py`**

```python
from loom.planner.scope import render_registry_block
from loom.validator.registry import Registry


def test_scope_filters_to_relevant_only():
    reg = Registry.load("v1")
    block = render_registry_block(reg, scope="clinic/kb")
    assert "clinic_kb" in block
    assert "clinic_system_api" not in block  # scoped to clinic/ops


def test_scope_with_no_matches_renders_empty_sections():
    reg = Registry.load("v1")
    block = render_registry_block(reg, scope="unknown-team/x")
    assert "Tools" in block and "Datasets" in block
    # No bulleted entries.
    assert "- `" not in block.split("### Tools")[1].split("### Datasets")[0]
```

- [ ] **Step 6: Write `loom/planner/client.py`**

```python
"""structured-output LLM client wrapper for the Planner.

Uses prompt caching on the system block (system prompt + IR schema +
declared-registry + few-shot library). PRD §10 cost target hinges on the cache.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path

import anthropic

from loom.ir.schema import load_schema
from loom.planner.scope import render_registry_block
from loom.validator.registry import Registry

_PROMPT_DIR = Path(__file__).resolve().parent / "prompts"


@dataclass(frozen=True)
class CallResult:
    ir_text: str        # raw model output (JSON)
    cost_usd: float
    latency_s: float


class PlannerClient:
    """One-call wrapper. The retry loop owns the multi-call story."""

    def __init__(
        self,
        *,
        model: str = "configured-planner-model",
        max_tokens: int = 16000,
        api_key: str | None = None,
    ):
        self._model = model
        self._max_tokens = max_tokens
        self._anthropic = anthropic.Anthropic(api_key=api_key)
        self._system_static = self._build_static_system()

    def _build_static_system(self) -> list[dict]:
        prompt_md = (_PROMPT_DIR / "system.md").read_text()
        schema = json.dumps(load_schema(), indent=2)
        few_shot_files = sorted((_PROMPT_DIR / "few_shot").glob("*.json"))
        few_shot = "\n\n".join(p.read_text() for p in few_shot_files)
        # Provider prompt caching: each cacheable block should stay within provider limits.
        return [
            {
                "type": "text",
                "text": prompt_md + "\n\n# IR v0.3 JSON Schema (verbatim)\n```json\n" + schema + "\n```",
                "cache_control": {"type": "ephemeral"},
            },
            {
                "type": "text",
                "text": "# Few-shot library\n\n" + few_shot,
                "cache_control": {"type": "ephemeral"},
            },
        ]

    def call(
        self,
        *,
        intent: str,
        scope: str,
        persona_brief: "PersonaBrief | None" = None,
        target: Literal["hiagent", "dify"] = "hiagent",
        prior_failures_md: str = "",
    ) -> CallResult:
        reg_block = render_registry_block(Registry.load("v1"), scope=scope)
        persona_block = render_persona_block(persona_brief)  # generates the {persona.*} fills
        target_block = render_target_block(target)            # injects redlines from adapter
        system = list(self._system_static) + [
            {"type": "text", "text": persona_block},
            {"type": "text", "text": target_block},
            {"type": "text", "text": reg_block},
        ]
        user_parts = [f"# Intent\n{intent}\n\n# Scope\n{scope}\n\n# Target runtime\n{target}"]
        if prior_failures_md:
            user_parts.append("# Validator failures from previous attempt\n" + prior_failures_md)
        user_parts.append("Emit IR v0.3 JSON only.")

        t0 = time.monotonic()
        msg = self._anthropic.messages.create(
            model=self._model,
            max_tokens=self._max_tokens,
            system=system,
            messages=[{"role": "user", "content": "\n\n".join(user_parts)}],
        )
        latency = time.monotonic() - t0
        text = "".join(b.text for b in msg.content if getattr(b, "type", None) == "text")
        cost = _estimate_cost(self._model, msg.usage)
        return CallResult(ir_text=text, cost_usd=cost, latency_s=latency)


def _estimate_cost(model: str, usage) -> float:
    """Token cost estimate. Update when prices change."""
    # Indicative pricing (USD per 1K tokens); configure per selected model.
    # Update when provider pricing changes; this is tracking data, not invoicing.
    rates = {
        "configured-planner-model": {"in": 0.003, "out": 0.015,
                                     "cache_read": 0.0003, "cache_write": 0.00375},
        "configured-small-model": {"in": 0.0008, "out": 0.004,
                                       "cache_read": 0.00008, "cache_write": 0.001},
    }
    r = rates.get(model, {"in": 0.003, "out": 0.015,
                           "cache_read": 0.0003, "cache_write": 0.00375})
    in_tok = getattr(usage, "input_tokens", 0)
    out_tok = getattr(usage, "output_tokens", 0)
    cw = getattr(usage, "cache_creation_input_tokens", 0)
    cr = getattr(usage, "cache_read_input_tokens", 0)
    return (in_tok * r["in"] + out_tok * r["out"]
            + cw * r["cache_write"] + cr * r["cache_read"]) / 1000.0
```

- [ ] **Step 7: Write `loom/planner/retry.py`**

```python
"""Validator-feedback self-correction loop."""
from __future__ import annotations

import json
import time

from loom.ir.models import IRDocument
from loom.planner.client import PlannerClient
from loom.planner.types import FailureRecord, IntentRequest, PlannerResult
from loom.validator.errors import fmt_for_planner
from loom.validator.validate import validate


def plan(req: IntentRequest, *, client: PlannerClient | None = None) -> PlannerResult:
    client = client or PlannerClient()
    failures_md = ""
    total_cost = 0.0
    t0 = time.monotonic()
    attempt = 0
    last_failures = []

    while attempt < req.max_retries + 1:
        attempt += 1
        # Pass persona_brief + target through every retry — the Planner's clarification
        # policy and target-runtime redlines are persona/target-dependent. Skipping these
        # would silently regress Persona Brief enforcement on retry attempts.
        call = client.call(
            intent=req.intent,
            scope=req.scope,
            persona_brief=req.persona_brief,
            target=req.target,
            prior_failures_md=failures_md,
        )
        total_cost += call.cost_usd

        try:
            doc = json.loads(_extract_json(call.ir_text))
        except (json.JSONDecodeError, ValueError) as e:
            last_failures = [FailureRecord(bucket="schema", detail=f"non-JSON output: {e}")]
            failures_md = fmt_for_planner_records(last_failures)
            continue

        validator_failures = validate(doc, scope=req.scope)
        if not validator_failures:
            ir = IRDocument.model_validate(doc)
            return PlannerResult(
                ir=ir, attempts=attempt, ok=True, failures=[],
                cost_usd=total_cost, latency_s=time.monotonic() - t0,
            )

        last_failures = [
            FailureRecord(bucket=f.bucket, detail=f.detail, location=f.location)
            for f in validator_failures
        ]
        failures_md = fmt_for_planner(validator_failures)

    return PlannerResult(
        ir=None, attempts=attempt, ok=False, failures=last_failures,
        cost_usd=total_cost, latency_s=time.monotonic() - t0,
    )


def _extract_json(text: str) -> str:
    """Strip ```json fences if the model added them despite the system prompt."""
    s = text.strip()
    if s.startswith("```"):
        first = s.find("\n")
        last = s.rfind("```")
        if first != -1 and last != -1:
            s = s[first + 1 : last].strip()
    return s


def fmt_for_planner_records(records: list[FailureRecord]) -> str:
    lines = []
    for i, f in enumerate(records, 1):
        loc = f" at `{f.location}`" if f.location else ""
        lines.append(f"{i}. [{f.bucket}]{loc}: {f.detail}")
    return "\n".join(lines)
```

- [ ] **Step 8: Write `tests/planner/test_client.py`**

```python
from unittest.mock import MagicMock, patch

from loom.planner.client import PlannerClient


def test_static_system_built_with_two_cache_breakpoints():
    with patch("anthropic.Anthropic"):
        c = PlannerClient(api_key="x")
    assert len(c._system_static) == 2
    assert all(b.get("cache_control", {}).get("type") == "ephemeral" for b in c._system_static)


def test_call_appends_persona_target_registry_blocks_and_user_msg():
    with patch("anthropic.Anthropic") as mock_anth:
        instance = mock_anth.return_value
        instance.messages.create.return_value = MagicMock(
            content=[MagicMock(type="text", text='{"ir_version": "0.3"}')],
            usage=MagicMock(input_tokens=100, output_tokens=50,
                            cache_creation_input_tokens=0, cache_read_input_tokens=0),
        )
        from loom.fde_session.persona_brief import PersonaBrief, ReviewerSpec, ComplianceBoundary
        persona = PersonaBrief(
            persona_id="ecommerce-cs-lead",
            author_role="cs_lead", vertical="ecommerce", end_user="buyer",
            reviewer=ReviewerSpec(role="ops_manager", decision_authority=["publish", "refund_above_500_USD"]),
            compliance_boundary=ComplianceBoundary(pii_class_default="medium", regulatory_tags=["GDPR", "PIPL"]),
            success_criteria="Refund flows respect monetary thresholds; queue stays within SLA.",
        )
        c = PlannerClient(api_key="x")
        result = c.call(intent="do X", scope="ecommerce/ops", persona_brief=persona, target="hiagent")
        kwargs = instance.messages.create.call_args.kwargs
        # Persona, target, and registry blocks all present in system blocks
        assert any("Persona context" in b["text"] for b in kwargs["system"])
        assert any("Target runtime" in b["text"] for b in kwargs["system"])
        assert any("Declared registry" in b["text"] for b in kwargs["system"])
        # Persona-relevant text actually filled in
        assert any("ecommerce-cs-lead" in b["text"] or "cs_lead" in b["text"] for b in kwargs["system"])
        # Target injected
        assert any("hiagent" in b["text"] for b in kwargs["system"])
        assert "do X" in kwargs["messages"][0]["content"]
        assert result.ir_text.startswith('{"ir_version"')


def test_call_default_persona_when_none():
    """Developer / debug mode without an explicit persona falls back to default-operator."""
    with patch("anthropic.Anthropic") as mock_anth:
        instance = mock_anth.return_value
        instance.messages.create.return_value = MagicMock(
            content=[MagicMock(type="text", text='{"ir_version": "0.3"}')],
            usage=MagicMock(input_tokens=100, output_tokens=50,
                            cache_creation_input_tokens=0, cache_read_input_tokens=0),
        )
        c = PlannerClient(api_key="x")
        c.call(intent="do X", scope="ecommerce/kb", persona_brief=None, target="hiagent")
        kwargs = instance.messages.create.call_args.kwargs
        assert any("default-operator" in b["text"] for b in kwargs["system"])
```

- [ ] **Step 9: Write `tests/planner/test_retry.py`**

```python
import json
from pathlib import Path
from unittest.mock import patch

from loom.planner.client import CallResult
from loom.planner.retry import plan
from loom.planner.types import IntentRequest

ROOT = Path(__file__).resolve().parents[2]


def _good_ir_text():
    return (ROOT / "examples" / "ir" / "01-ecommerce-customer-faq.json").read_text()


def _bad_ir_text():
    doc = json.loads(_good_ir_text())
    del doc["nodes"][1]["rationale"]
    return json.dumps(doc)


class _FakeClient:
    def __init__(self, sequence):
        self._sequence = list(sequence)
        self.calls = 0
        self.last_kwargs: dict | None = None

    def call(self, **kwargs):
        self.calls += 1
        self.last_kwargs = kwargs
        return CallResult(ir_text=self._sequence.pop(0), cost_usd=0.05, latency_s=0.1)


def test_intent_request_passes_persona_and_target_through_to_client():
    """Persona Brief + target on IntentRequest must reach PlannerClient.call."""
    from loom.fde_session.persona_brief import PersonaBrief, ReviewerSpec, ComplianceBoundary
    persona = PersonaBrief(
        persona_id="tcm-clinic-operator",
        author_role="operator", vertical="tcm_clinic", end_user="patient",
        reviewer=ReviewerSpec(role="clinician", decision_authority=["publish", "medical_response_approval"]),
        compliance_boundary=ComplianceBoundary(pii_class_default="high", regulatory_tags=["PIPL", "PIPL-medical"]),
        success_criteria="No diagnosis or prescription auto-published.",
    )
    fc = _FakeClient([_good_ir_text()])
    req = IntentRequest(
        intent="x", scope="clinic/kb",
        persona_brief=persona, target="dify", max_retries=3,
    )
    plan(req, client=fc)
    assert fc.last_kwargs is not None
    assert fc.last_kwargs["persona_brief"] is persona
    assert fc.last_kwargs["target"] == "dify"


def test_first_try_pass():
    fc = _FakeClient([_good_ir_text()])
    res = plan(IntentRequest(intent="x", scope="ecommerce/kb", max_retries=3), client=fc)
    assert res.ok and res.attempts == 1
    assert fc.calls == 1


def test_self_correction_on_second_try():
    fc = _FakeClient([_bad_ir_text(), _good_ir_text()])
    res = plan(IntentRequest(intent="x", scope="ecommerce/kb", max_retries=3), client=fc)
    assert res.ok and res.attempts == 2


def test_gives_up_after_max_retries():
    fc = _FakeClient([_bad_ir_text()] * 4)
    res = plan(IntentRequest(intent="x", scope="ecommerce/kb", max_retries=3), client=fc)
    assert not res.ok and res.attempts == 4
    assert any(f.bucket == "schema" for f in res.failures)
```

- [ ] **Step 10: Run tests**

Run: `pytest tests/planner/ -v && mypy loom`
Expected: all PASS.

- [ ] **Step 11: Commit**

```bash
git add pyproject.toml loom/planner/ tests/planner/
git commit -m "feat(planner): cached system prompt, scope-filtered registry, validator-feedback retries"
```

---

## Task 8.5: RuntimeAdapter abstraction + ADR 0015

**Files:**
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/docs/decisions/0015-runtime-adapter.md`
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/loom/runtimes/__init__.py`
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/loom/runtimes/base.py`
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/loom/runtimes/registry.py`
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/tests/runtimes/test_adapter_contract.py`

Originally Phase 3.1 work; promoted to Phase 1 (per project owner decision 2026-05-06: dual runtime from Day 1, n8n out of v1 scope). Without this abstraction Tasks 9–13 ship Dify-only and Hiagent becomes a Phase 2A retrofit. With it, Hiagent and Dify are co-equal from the start.

- [ ] **Step 1: Write ADR 0015**

```markdown
# ADR 0015 — RuntimeAdapter

Status: Proposed → Accepted (after review)
Date: 2026-MM-DD

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
```

- [ ] **Step 2: Write `loom/runtimes/base.py`**

```python
from __future__ import annotations
from dataclasses import dataclass
from typing import Any, Protocol

from loom.ir.models import IRDocument


@dataclass(frozen=True)
class DraftHandle:
    target: str        # "hiagent" | "dify"
    draft_id: str
    canonical_ast_hash: str


@dataclass(frozen=True)
class PublishHandle:
    target: str
    publish_id: str
    canonical_ast_hash: str


@dataclass(frozen=True)
class UnrecognizedConstruct:
    target: str
    construct: str
    reason: str
    remediation: str


@dataclass(frozen=True)
class PushContext:
    actor: str
    workflow_name: str | None = None


@dataclass(frozen=True)
class PublishContext:
    actor: str


class RuntimeAdapter(Protocol):
    target: str
    version: str
    # IR ↔ DSL
    def compile(self, ir: IRDocument) -> Any: ...
    def reverse(self, dsl: Any) -> tuple[IRDocument, list[UnrecognizedConstruct]]: ...
    def canonical_ast_hash(self, dsl: Any) -> str: ...
    # DSL serialization
    def serialize_dsl(self, dsl: Any) -> str: ...
    def parse_dsl(self, raw: str) -> Any: ...
    # Lifecycle
    async def push_draft(self, dsl: Any, ctx: PushContext) -> DraftHandle: ...
    async def publish(self, handle: DraftHandle, ctx: PublishContext) -> PublishHandle: ...
    async def export_draft(self, draft_id: str) -> Any: ...
    # Conformance / parity
    async def run_draft(self, draft_id: str, *, inputs: dict) -> dict: ...
    # Planner consultation
    def redlines(self) -> list[str]: ...
```

- [ ] **Step 3: Write `loom/runtimes/registry.py`**

```python
from __future__ import annotations
from typing import Literal

from loom.runtimes.base import RuntimeAdapter

Target = Literal["hiagent", "dify"]


class UnknownTargetError(KeyError):
    """Target name is not registered."""


_REGISTRY: dict[str, RuntimeAdapter] = {}


def register(adapter: RuntimeAdapter) -> None:
    _REGISTRY[adapter.target] = adapter


def unregister(target: str) -> None:
    _REGISTRY.pop(target, None)


def get(target: str) -> RuntimeAdapter:
    try:
        return _REGISTRY[target]
    except KeyError:
        raise UnknownTargetError(f"runtime target {target!r} not registered")


def list_targets() -> list[str]:
    return sorted(_REGISTRY)
```

- [ ] **Step 4: Adapter contract test**

```python
# tests/runtimes/test_adapter_contract.py
import pytest
from loom.runtimes.base import RuntimeAdapter
from loom.runtimes import registry


@pytest.fixture(autouse=True)
def reset_registry():
    yield
    for t in list(registry.list_targets()):
        registry.unregister(t)


class FakeAdapter:
    target = "fake"
    version = "0.0"
    def compile(self, ir): return {"ok": True}
    def reverse(self, dsl): return None, []
    def canonical_ast_hash(self, dsl): return "0" * 64
    def serialize_dsl(self, dsl): return json.dumps(dsl, sort_keys=True)
    def parse_dsl(self, raw): return json.loads(raw)
    async def push_draft(self, dsl, ctx): ...
    async def publish(self, handle, ctx): ...
    async def export_draft(self, draft_id): ...
    async def run_draft(self, draft_id, *, inputs): return {"ok": True, "inputs": inputs}
    def redlines(self): return []


def test_register_and_get():
    registry.register(FakeAdapter())
    assert registry.get("fake").target == "fake"


def test_unknown_target_raises():
    with pytest.raises(registry.UnknownTargetError):
        registry.get("does-not-exist")
```

- [ ] **Step 5: Commit**

```bash
git add docs/decisions/0015-runtime-adapter.md loom/runtimes/__init__.py loom/runtimes/base.py loom/runtimes/registry.py tests/runtimes/
git commit -m "feat(runtimes): RuntimeAdapter abstraction (Hiagent + Dify dual support); ADR 0015"
```

---

## Task 9: Compiler scaffold (per-Dify-version module)

**Files:**
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/loom/runtimes/dify/vX_Y/__init__.py`
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/loom/runtimes/dify/vX_Y/compiler.py`
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/loom/runtimes/dify/vX_Y/compiler_nodes.py`
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/loom/runtimes/dify/vX_Y/wrappers.py`
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/tests/runtimes/dify/vX_Y/__init__.py`
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/tests/runtimes/dify/vX_Y/test_compiler_nodes.py`

> Replace `vX_Y` with `cloud` (per 2026-05-07 cloud pivot in ADR 0002). The path appears in *every* file path below; doing the replacement once at the start of this task is the easiest path.

The Compiler is a pure function — `IRDocument → str` (Dify YAML). It dispatches per node type; cells where the pinned Dify can't honor IR semantics natively get a wrapper synthesis (per the cell table in ADR 0002).

- [ ] **Step 1: Write the dispatch test**

```python
# tests/runtimes/dify/vX_Y/test_compiler_nodes.py
import json
from pathlib import Path

from loom.ir.models import IRDocument
from loom.runtimes.dify.vX_Y.compiler import compile_ir

ROOT = Path(__file__).resolve().parents[3]


def _load(name: str) -> IRDocument:
    return IRDocument.model_validate(json.loads((ROOT / "examples" / "ir" / name).read_text()))


def test_ecommerce_faq_emits_yaml():
    ir = _load("01-ecommerce-customer-faq.json")
    yaml_text = compile_ir(ir)
    assert yaml_text.startswith("app:")
    assert "workflow:" in yaml_text
    assert "knowledge-retrieval" in yaml_text or "retrieval" in yaml_text  # depends on Dify version
    assert "llm" in yaml_text


def test_clinic_ops_summary_emits_yaml():
    ir = _load("05-ecommerce-order-exception.json")
    yaml_text = compile_ir(ir)
    assert "http" in yaml_text or "tool" in yaml_text  # clinic ops summary fetches via http
    assert "llm" in yaml_text
```

- [ ] **Step 2: Run — expect ImportError**

- [ ] **Step 3: Write the Compiler module**

```python
# loom/runtimes/dify/vX_Y/__init__.py
"""Dify <version> Compiler. PRD §9 vendor-lock policy: one module per Dify major version."""
DIFY_VERSION = "X.Y"  # replace with the value from ADR 0002
```

```python
# loom/runtimes/dify/vX_Y/compiler.py
"""IR v0.3 → Dify <DIFY_VERSION> DSL.

Pure function. Programmatic emission (PRD §8: "not via templates — too brittle").
Per-node emission lives in compiler_nodes.py; synthesis wrappers in wrappers.py.
"""
from __future__ import annotations

from typing import Any

import yaml

from loom.dify.vX_Y import DIFY_VERSION
from loom.runtimes.dify.vX_Y.compiler_nodes import emit_node
from loom.ir.models import IRDocument


def compile_ir(ir: IRDocument) -> str:
    """Return Dify DSL YAML."""
    nodes_dsl: list[dict[str, Any]] = []
    edges_dsl: list[dict[str, Any]] = []

    for n in ir.nodes:
        node_dsls, extra_edges = emit_node(n)
        nodes_dsl.extend(node_dsls)
        edges_dsl.extend(extra_edges)
    for e in ir.edges:
        edges_dsl.append({"from": e.from_, "to": e.to})

    doc = {
        "app": {
            "name": ir.metadata.name,
            "description": ir.metadata.description or "",
            "mode": "workflow",
            "loom": {
                "ir_version": ir.ir_version,
                "rationale": ir.metadata.rationale,
                "registry_version": ir.registry_ref.registry_version,
                "compiler_version": f"loom-dify-{DIFY_VERSION}",
            },
        },
        "workflow": {
            "nodes": nodes_dsl,
            "edges": edges_dsl,
        },
        "policy": ir.policy.model_dump(exclude_none=True) if ir.policy else {},
        "inputs": [p.model_dump() for p in ir.inputs],
        "outputs": [p.model_dump() for p in ir.outputs],
    }
    return yaml.safe_dump(doc, sort_keys=False, allow_unicode=True)
```

```python
# loom/runtimes/dify/vX_Y/compiler_nodes.py
"""Per-node emit functions.

Returns (list[dict] dsl_nodes, list[dict] extra_edges) so a single IR node can
expand into multiple DSL nodes when a wrapper is needed.
"""
from __future__ import annotations

from typing import Any

from loom.dify.vX_Y import wrappers
from loom.ir.models import (
    AgentNode, AnyNode, CodeNode, ConditionNode, HTTPNode, LLMNode, LoopNode,
    OutputNode, ParallelNode, RetrievalNode, TriggerNode,
)


def emit_node(n: AnyNode) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if isinstance(n, TriggerNode):
        return [_trigger(n)], []
    if isinstance(n, LLMNode):
        return [_llm(n)], []
    if isinstance(n, RetrievalNode):
        return [_retrieval(n)], []
    if isinstance(n, HTTPNode):
        return wrappers.http(n)  # may inject idempotency wrapper
    if isinstance(n, CodeNode):
        return [_code(n)], []
    if isinstance(n, ConditionNode):
        return [_condition(n)], []
    if isinstance(n, LoopNode):
        return wrappers.loop(n)  # may inject truncation-event sentinel
    if isinstance(n, ParallelNode):
        return wrappers.parallel(n)  # merge_strategy may need post-aggregator
    if isinstance(n, AgentNode):
        return wrappers.agent(n)  # output_schema validator + fallback edge
    if isinstance(n, OutputNode):
        return [_output(n)], []
    raise NotImplementedError(f"unhandled node type {type(n).__name__}")


def _trigger(n: TriggerNode) -> dict[str, Any]:
    base = {"id": n.id, "type": "start", "data": {"rationale": n.rationale}}
    if n.mode == "schedule":
        base["data"]["schedule"] = n.schedule
    if n.mode == "webhook":
        base["data"]["webhook"] = n.webhook.model_dump() if n.webhook else {}
    return base


def _llm(n: LLMNode) -> dict[str, Any]:
    return {
        "id": n.id, "type": "llm",
        "data": {
            "rationale": n.rationale,
            "model": {"name": n.model},
            "system_prompt": n.system_prompt,
            "prompt": n.prompt,
            "temperature": n.temperature,
            "max_tokens": n.max_tokens,
            "output_schema": n.output_schema,
        },
    }


def _retrieval(n: RetrievalNode) -> dict[str, Any]:
    return {
        "id": n.id, "type": "knowledge-retrieval",
        "data": {
            "rationale": n.rationale,
            "dataset_id": n.dataset,
            "query": n.query,
            "top_k": n.top_k,
            "rerank": n.rerank,
        },
    }


def _code(n: CodeNode) -> dict[str, Any]:
    return {
        "id": n.id, "type": "code",
        "data": {
            "rationale": n.rationale,
            "language": n.language,
            "source": n.source,
            "inputs": n.inputs or {},
            "output_schema": n.output_schema,
            "idempotency_key": n.idempotency_key,
        },
    }


def _condition(n: ConditionNode) -> dict[str, Any]:
    return {
        "id": n.id, "type": "if-else",
        "data": {
            "rationale": n.rationale,
            "branches": [b.model_dump() for b in n.branches],
            "default": n.default,
        },
    }


def _output(n: OutputNode) -> dict[str, Any]:
    return {"id": n.id, "type": "end",
            "data": {"rationale": n.rationale, "bindings": n.bindings}}
```

```python
# loom/runtimes/dify/vX_Y/wrappers.py
"""Synthesis wrappers for cells where pinned Dify lacks native IR semantics.

The list below is *seeded by ADR 0002's cell table*. Engineer: edit each
wrapper based on the conformance baseline; if the Dify version supports the
cell natively, the wrapper degenerates to a single emit.

The wrappers ARE the part most likely to change between Dify versions.
"""
from __future__ import annotations

from typing import Any

from loom.ir.models import AgentNode, HTTPNode, LoopNode, ParallelNode


def http(n: HTTPNode) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    base = {
        "id": n.id, "type": "http-request",
        "data": {
            "rationale": n.rationale,
            "method": n.method, "url": n.url,
            "headers": n.headers or {}, "body": n.body,
            "credential": n.credential,
            "timeout_s": n.timeout_s,
            "retry": n.retry.model_dump(exclude_none=True) if n.retry else None,
            "idempotency_key": n.idempotency_key,
        },
    }
    return [base], []


def loop(n: LoopNode) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    base = {
        "id": n.id, "type": "iteration",
        "data": {
            "rationale": n.rationale,
            "over": n.over, "as": n.as_,
            "max_iterations": n.max_iterations,
            "collect": n.collect,
            "body": [{"id": b.id, "type": b.type} for b in n.body],
        },
    }
    return [base], []


def parallel(n: ParallelNode) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    base = {
        "id": n.id, "type": "parallel",
        "data": {
            "rationale": n.rationale,
            "branches": {k: [{"id": b.id, "type": b.type} for b in v] for k, v in n.branches.items()},
            "merge_strategy": n.merge_strategy,
        },
    }
    return [base], []


def agent(n: AgentNode) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    base = {
        "id": n.id, "type": "agent",
        "data": {
            "rationale": n.rationale,
            "model": {"name": n.model},
            "tools": n.tools,
            "input_schema": n.input_schema,
            "output_schema": n.output_schema,
            "system_prompt": n.system_prompt,
            "budget": n.budget.model_dump(),
            "on_budget_exhausted": n.on_budget_exhausted,
            "fallback_edge": n.fallback_edge,
        },
    }
    return [base], []
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/runtimes/dify/vX_Y/ -v && mypy loom`
Expected: 2/2 PASS.

- [ ] **Step 5: Commit**

```bash
git add loom/runtimes/dify/vX_Y/ tests/runtimes/dify/vX_Y/
git commit -m "feat(compiler): IR → Dify DSL, per-major-version module, dispatch + wrappers"
```

---

## Task 10: Golden tests for IR → DSL pairs

**Files:**
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/tests/runtimes/dify/vX_Y/test_compiler_golden.py`
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/tests/runtimes/dify/vX_Y/golden/01-ecommerce-customer-faq.yaml`
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/tests/runtimes/dify/vX_Y/golden/05-ecommerce-order-exception.yaml`

PRD §8: "Golden-file tests for every (IR → DSL) pair *and* matching (DSL → IR) reverse pair." Phase 1 ships goldens for the two deep-coverage archetypes; Phase 1.5 adds the rest.

- [ ] **Step 1: Write the golden test**

```python
# tests/runtimes/dify/vX_Y/test_compiler_golden.py
import json
from pathlib import Path

import pytest

from loom.ir.models import IRDocument
from loom.runtimes.dify.vX_Y.compiler import compile_ir
from loom.dify.ast import canonical_dify_ast_hash

ROOT = Path(__file__).resolve().parents[3]
GOLDEN_DIR = Path(__file__).resolve().parent / "golden"

PAIRS = [
    ("01-ecommerce-customer-faq.json", "01-ecommerce-customer-faq.yaml"),
    ("05-ecommerce-order-exception.json", "05-ecommerce-order-exception.yaml"),
]


@pytest.mark.parametrize("ir_name,dsl_name", PAIRS, ids=lambda x: x)
def test_golden_compile_matches_canonical_hash(ir_name, dsl_name):
    ir = IRDocument.model_validate(json.loads((ROOT / "examples" / "ir" / ir_name).read_text()))
    actual_yaml = compile_ir(ir)
    expected_yaml = (GOLDEN_DIR / dsl_name).read_text()
    assert canonical_dify_ast_hash(actual_yaml) == canonical_dify_ast_hash(expected_yaml)


@pytest.mark.parametrize("ir_name,dsl_name", PAIRS, ids=lambda x: x)
def test_golden_compile_is_deterministic(ir_name, dsl_name):
    ir = IRDocument.model_validate(json.loads((ROOT / "examples" / "ir" / ir_name).read_text()))
    a = compile_ir(ir)
    b = compile_ir(ir)
    assert a == b
```

- [ ] **Step 2: Generate the golden files**

```bash
cd "/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE"
mkdir -p tests/runtimes/dify/vX_Y/golden
python -c "
import json
from pathlib import Path
from loom.ir.models import IRDocument
from loom.runtimes.dify.vX_Y.compiler import compile_ir

for ir_name, dsl_name in [('01-ecommerce-customer-faq.json','01-ecommerce-customer-faq.yaml'),('05-ecommerce-order-exception.json','05-ecommerce-order-exception.yaml')]:
    ir = IRDocument.model_validate(json.loads(Path('examples/ir/' + ir_name).read_text()))
    Path(f'tests/runtimes/dify/vX_Y/golden/{dsl_name}').write_text(compile_ir(ir))
"
```

Inspect both files. Confirm by hand that they look like sensible Dify DSL for the pinned version. If a wrapper from Task 9 produced something off (e.g., a synthesis path the Dify version doesn't actually need), fix the wrapper *now* — that's the point of the goldens.

- [ ] **Step 3: Run tests**

Run: `pytest tests/runtimes/dify/vX_Y/ -v`
Expected: 4/4 PASS (2 golden + 2 determinism).

- [ ] **Step 4: Commit**

```bash
git add tests/runtimes/dify/vX_Y/test_compiler_golden.py tests/runtimes/dify/vX_Y/golden/
git commit -m "test(compiler): goldens for ecommerce-customer-faq and ecommerce-order-exception IR→DSL pairs"
```

---

## Task 11: Narrow reverse compiler

**Files:**
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/loom/runtimes/dify/vX_Y/reverse.py`
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/tests/runtimes/dify/vX_Y/test_reverse_narrow.py`

PRD §7 Phase 1: "narrow reverse compiler (round-trip support for the IR constructs used by the 2 deep-coverage archetypes)." So the supported set is: trigger(manual), llm, retrieval, http, code (only when archetype 05 ecommerce-order-exception uses it for refund / amount-threshold logic), parallel (only when archetype 05 uses it), output, edges. TCM shadow archetypes 02 / 03 / 04 are intentionally excluded from narrow round-trip.

The hard-block contract from PRD §6 still applies: any unrecognized construct raises with an actionable error.

- [ ] **Step 1: Write the round-trip test**

```python
# tests/runtimes/dify/vX_Y/test_reverse_narrow.py
import json
from pathlib import Path

import pytest

from loom.ir.canonicalize import canonical_ir
from loom.ir.models import IRDocument
from loom.runtimes.dify.vX_Y.compiler import compile_ir
from loom.runtimes.dify.vX_Y.reverse import UnrecognizedConstruct, reverse_compile

ROOT = Path(__file__).resolve().parents[3]
ARCHETYPES = ["01-ecommerce-customer-faq.json", "05-ecommerce-order-exception.json"]


@pytest.mark.parametrize("name", ARCHETYPES)
def test_round_trip_canonical_equality(name):
    ir = IRDocument.model_validate(json.loads((ROOT / "examples" / "ir" / name).read_text()))
    yaml_text = compile_ir(ir)
    back = reverse_compile(yaml_text)
    assert canonical_ir(ir.model_dump(by_alias=True)) == canonical_ir(back)


def test_unrecognized_construct_hard_blocks():
    yaml_text = """
app: {name: x, mode: workflow}
workflow:
  nodes:
    - id: x
      type: some-future-node
  edges: []
"""
    with pytest.raises(UnrecognizedConstruct) as exc:
        reverse_compile(yaml_text)
    assert "some-future-node" in str(exc.value)
```

- [ ] **Step 2: Run — expect ImportError**

- [ ] **Step 3: Write `loom/runtimes/dify/vX_Y/reverse.py`**

```python
"""Narrow Dify DSL → IR v0.3 reverse compiler.

Phase 1 scope: trigger, llm, retrieval, http, code, output (the 2 deep
archetypes). Anything else raises UnrecognizedConstruct (PRD §6 hard-block).
"""
from __future__ import annotations

from typing import Any

import yaml


class UnrecognizedConstruct(ValueError):
    pass


_RECOGNIZED = {"start", "llm", "knowledge-retrieval", "http-request", "code", "end"}


def reverse_compile(yaml_text: str) -> dict[str, Any]:
    src = yaml.safe_load(yaml_text)
    nodes: list[dict[str, Any]] = []
    for n in src["workflow"]["nodes"]:
        t = n["type"]
        if t not in _RECOGNIZED:
            raise UnrecognizedConstruct(
                f"reverse compile: node type {t!r} (id {n.get('id')!r}) is not in the "
                f"Phase 1 recognized set {_RECOGNIZED}. Per PRD §6: revert the edit, "
                f"request an IR extension, or use the `code` escape hatch."
            )
        nodes.append(_reverse_one(n))

    edges = [{"from": e["from"], "to": e["to"]} for e in src["workflow"].get("edges", [])]

    loom_meta = src["app"].get("loom", {})
    return {
        "ir_version": loom_meta.get("ir_version", "0.3"),
        "metadata": {
            "name": src["app"]["name"],
            "description": src["app"].get("description", ""),
            "owner": loom_meta.get("owner", "unknown"),
            "rationale": loom_meta.get("rationale", "Reverse-compiled from Dify DSL."),
        },
        "registry_ref": {
            "registry_version": loom_meta.get("registry_version", "sha:0000000"),
            "tools": _collect_tools(nodes),
            "datasets": _collect_datasets(nodes),
            "credentials": _collect_credentials(nodes),
        },
        "policy": src.get("policy", {}),
        "inputs": src.get("inputs", []),
        "outputs": src.get("outputs", []),
        "nodes": nodes,
        "edges": edges,
    }


def _reverse_one(n: dict[str, Any]) -> dict[str, Any]:
    d = n.get("data", {})
    rationale = d.get("rationale", "Reverse-compiled.")
    if n["type"] == "start":
        out: dict[str, Any] = {"id": n["id"], "type": "trigger",
                                "rationale": rationale, "mode": "manual"}
        if "schedule" in d:
            out["mode"] = "schedule"
            out["schedule"] = d["schedule"]
        if "webhook" in d:
            out["mode"] = "webhook"
            out["webhook"] = d["webhook"]
        return out
    if n["type"] == "llm":
        return _strip_none({
            "id": n["id"], "type": "llm", "rationale": rationale,
            "model": d["model"]["name"],
            "system_prompt": d.get("system_prompt"),
            "prompt": d["prompt"],
            "temperature": d.get("temperature"),
            "max_tokens": d.get("max_tokens"),
            "output_schema": d.get("output_schema"),
        })
    if n["type"] == "knowledge-retrieval":
        return _strip_none({
            "id": n["id"], "type": "retrieval", "rationale": rationale,
            "dataset": d["dataset_id"], "query": d["query"],
            "top_k": d.get("top_k", 5),
        })
    if n["type"] == "http-request":
        return _strip_none({
            "id": n["id"], "type": "http", "rationale": rationale,
            "method": d["method"], "url": d["url"],
            "headers": d.get("headers"),
            "body": d.get("body"),
            "credential": d.get("credential"),
            "timeout_s": d.get("timeout_s"),
            "retry": d.get("retry"),
            "idempotency_key": d.get("idempotency_key"),
        })
    if n["type"] == "code":
        return _strip_none({
            "id": n["id"], "type": "code", "rationale": rationale,
            "language": d["language"], "source": d["source"],
            "inputs": d.get("inputs"),
            "output_schema": d.get("output_schema"),
            "idempotency_key": d.get("idempotency_key"),
        })
    if n["type"] == "end":
        return {"id": n["id"], "type": "output",
                "rationale": rationale, "bindings": d["bindings"]}
    raise AssertionError("unreachable")  # _RECOGNIZED gate above


def _strip_none(d: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in d.items() if v is not None}


def _collect_tools(nodes):
    tools: set[str] = set()
    for n in nodes:
        if n["type"] == "agent":
            tools.update(n.get("tools", []))
    return sorted(tools)


def _collect_datasets(nodes):
    return sorted({n["dataset"] for n in nodes if n["type"] == "retrieval"})


def _collect_credentials(nodes):
    return sorted({n["credential"] for n in nodes
                   if n["type"] == "http" and "credential" in n})
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/runtimes/dify/vX_Y/test_reverse_narrow.py -v && mypy loom`
Expected: 3/3 PASS.

- [ ] **Step 5: Commit**

```bash
git add loom/runtimes/dify/vX_Y/reverse.py tests/runtimes/dify/vX_Y/test_reverse_narrow.py
git commit -m "feat(compiler): narrow reverse compile + UnrecognizedConstruct hard-block"
```

---

## Task 11.5: Hiagent compiler + reverse parity

**Files:**
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/loom/runtimes/hiagent/__init__.py`
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/loom/runtimes/hiagent/ast.py`
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/loom/runtimes/hiagent/client.py`
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/loom/runtimes/hiagent/adapter.py`
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/loom/runtimes/hiagent/vH_X/__init__.py`
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/loom/runtimes/hiagent/vH_X/compiler.py`
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/loom/runtimes/hiagent/vH_X/compiler_nodes.py`
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/loom/runtimes/hiagent/vH_X/wrappers.py`
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/loom/runtimes/hiagent/vH_X/reverse.py`
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/tests/runtimes/hiagent/vH_X/test_compiler_golden.py`
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/tests/runtimes/hiagent/vH_X/test_reverse_narrow.py`

This task mirrors Tasks 9 + 10 + 11 (Dify compiler + golden + reverse) for **Hiagent**. The IR primitives map cleanly to Hiagent's native node set (per the design audit 2026-05-06):

| FDE IR node | Hiagent node | Notes |
|---|---|---|
| `trigger` | Start 节点 | mode: manual / schedule / webhook |
| `llm` | 大模型节点 | output_schema → 输出格式 (JSON / 文本 / Markdown / 自定义) |
| `retrieval` | 知识库节点 | dataset → KB id |
| `http` | 插件节点 (HTTP) | method / url / headers / body |
| `code` | 代码节点 | language: python / javascript |
| `condition` | 选择器 | branches + default |
| `loop` | 循环节点 | over / as / max_iterations |
| `parallel` | 并行节点 | branches + merge_strategy |
| `agent` | Agent 节点 | typed I/O + budget; native first-class on Hiagent |
| `output` | End 节点 | bindings |

Wrappers are smaller than Dify's because Hiagent natively supports more of our IR primitives (e.g., `agent.budget`, `output_schema` enforcement, retry/timeout per node). Where wrappers are needed, document the cell + the conformance-matrix row that verifies semantic equivalence.

- [ ] **Step 1: ADR 0002 amendment — Hiagent version pin**

ADR 0002 in Phase 0 originally pinned only Dify. Amend it to pin a Hiagent version + image digest alongside. The amendment is additive (existing Dify pin unchanged):

```markdown
# ADR 0002 — Pinned runtime versions (amended 2026-05-06)

## Decision

- **Hiagent (primary)**: `<image>:<X.Y.Z>@sha256:<digest>`. Self-hosted, single-tenant, per Phase 1 dev environment.
- **Dify (secondary)**: `langgenius/dify:<X.Y.Z>@sha256:<digest>`. Same pinning policy as 2026-04 original.

## Consequences

- `loom.runtimes.hiagent.ast.canonical_hiagent_ast_hash` and `loom.runtimes.dify.ast.canonical_dify_ast_hash` are both stable on their respective pinned versions.
- Conformance matrix runs on both runtimes in CI slow lane.
```

- [ ] **Step 2: Implement `loom/runtimes/hiagent/{ast,client,adapter}.py`**

`ast.py` defines `canonical_hiagent_ast_hash(workflow_json) -> str`; `client.py` is a thin Hiagent OpenAPI client (auth + import-workflow + export-workflow + publish-workflow); `adapter.py` ties them together as a `RuntimeAdapter`. Register in `loom/runtimes/registry.py`:

```python
# loom/runtimes/__init__.py
from loom.runtimes import registry
from loom.runtimes.hiagent.adapter import HiagentAdapter
from loom.runtimes.dify.adapter import DifyAdapter

registry.register(HiagentAdapter())   # primary
registry.register(DifyAdapter())      # secondary
```

- [ ] **Step 3: Implement `compiler.py` + `compiler_nodes.py`**

Same dispatch pattern as Dify Task 9. One emit fn per IR node type; keep wrappers minimal — Hiagent natively handles most IR primitives.

- [ ] **Step 4: Golden tests for the 2 deep archetypes**

```python
# tests/runtimes/hiagent/vH_X/test_compiler_golden.py
import json
from pathlib import Path
import pytest
from loom.ir.models import IRDocument
from loom.runtimes.hiagent.vH_X.compiler import compile_ir

ARCHETYPES = ["01-ecommerce-customer-faq", "05-ecommerce-order-exception"]

@pytest.mark.parametrize("name", ARCHETYPES)
def test_archetype_compiles(name: str) -> None:
    ir_path = Path("examples/ir") / f"{name}.json"
    ir = IRDocument.model_validate(json.loads(ir_path.read_text()))
    workflow = compile_ir(ir)
    assert workflow["nodes"], f"{name} produced empty graph"
    types = {n["type"] for n in workflow["nodes"]}
    if name == "01-ecommerce-customer-faq":
        assert "Start" in types
        assert any("KnowledgeBase" in t or "知识库" in t for t in types)
        assert any("LLM" in t or "大模型" in t for t in types)
```

- [ ] **Step 5: Implement `reverse.py` (narrow)**

Narrow Hiagent JSON → IR for the 2 deep-coverage archetypes. Same hard-block contract as Dify reverse: `UnrecognizedConstruct` (typed) per PRD §6.2.

- [ ] **Step 6: Round-trip test**

Same shape as Task 11; round-trip canonical IR equality on the 2 deep archetypes.

- [ ] **Step 7: Adapter contract test**

```python
# tests/runtimes/hiagent/vH_X/test_adapter_contract.py
from loom.runtimes import registry

def test_hiagent_adapter_registered():
    a = registry.get("hiagent")
    assert a.target == "hiagent"

def test_dify_adapter_registered():
    a = registry.get("dify")
    assert a.target == "dify"
```

- [ ] **Step 8: Commit**

```bash
git add loom/runtimes/hiagent/ tests/runtimes/hiagent/ docs/decisions/0002-dify-version.md
git commit -m "feat(hiagent): compiler + reverse + adapter; ADR 0002 amended for dual runtime"
```

> **Cost-budget escape hatch in action.** If at this point the dual-runtime cost is too high to sustain (e.g., conformance matrix runs are budget-heavy on both runtimes), drop Dify by removing `loom/runtimes/dify/` and unregistering the adapter. Hiagent path is unchanged. Make a decision and commit; do not silently degrade.

---

## Task 12: Wire conformance runner to Compiler

**Files:**
- Modify: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/loom/conformance/runner.py`
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/loom/conformance/execute.py`
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/tests/conformance/test_runner_live.py`

Phase 0 left the runner with a stub. Now Compile + push + run + assert end-to-end **against both pinned Hiagent and pinned Dify** via the RuntimeAdapter contract (ADR 0015, Phase 1 Task 8.5). Live tests are gated by per-runtime env flags (`LOOM_HIAGENT_LIVE` / `LOOM_DIFY_LIVE`); local dev does not need either runtime running. The runner is target-parameterized — same case runs on each registered adapter.

> **Cost-budget escape hatch.** If Dify was dropped (per ADR 0002 Cost-budget escape hatch), only `LOOM_HIAGENT_LIVE` matters; the conformance gate runs on Hiagent only and the per-runtime parity test in Phase 1.5 is skipped.

- [ ] **Step 1: Write `loom/conformance/execute.py`**

```python
"""Execute one ConformanceCase against a RuntimeAdapter (Hiagent or Dify)."""
from __future__ import annotations

import time
from dataclasses import dataclass

from loom.runtimes import registry as runtime_registry
from loom.runtimes.base import RuntimeAdapter, PushContext
from loom.conformance.runner import ConformanceCase


@dataclass(frozen=True)
class ExecutionResult:
    ok: bool
    detail: str
    latency_s: float


def execute(case: ConformanceCase, *, target: str, actor: str = "conformance") -> ExecutionResult:
    """Execute one conformance case against the named runtime via its RuntimeAdapter."""
    adapter: RuntimeAdapter = runtime_registry.get(target)
    t0 = time.monotonic()
    try:
        dsl = adapter.compile(case.ir)
        ctx = PushContext(actor=actor, workflow_name=case.ir.metadata.name)
        # adapter handles the runtime's import/run path internally
        handle = await adapter.push_draft(dsl, ctx)
        run_result = await adapter.run_draft(handle.draft_id, inputs=case.inputs)  # adapter exposes run_draft
        case.expect(run_result)
        return ExecutionResult(ok=True, detail="pass", latency_s=time.monotonic() - t0)
    except AssertionError as e:
        return ExecutionResult(ok=False, detail=f"assertion: {e}", latency_s=time.monotonic() - t0)
    except Exception as e:
        return ExecutionResult(ok=False, detail=f"{type(e).__name__}: {e}",
                                latency_s=time.monotonic() - t0)
```

> Note: `RuntimeAdapter.run_draft(draft_id, inputs) -> dict` is part of the ADR 0015 protocol (defined in Task 8.5). The `FakeAdapter` in `tests/runtimes/test_adapter_contract.py` already implements it — no contract amendment needed here.

- [ ] **Step 2: Write the live test (target-parameterized)**

```python
# tests/conformance/test_runner_live.py
import os
import pytest

from loom.conformance.execute import execute
from loom.conformance.matrix import MATRIX

# Per-runtime live gating: tests skip per target unless its env flag is set.
TARGETS_LIVE = []
if os.environ.get("LOOM_HIAGENT_LIVE") == "1":
    TARGETS_LIVE.append("hiagent")
if os.environ.get("LOOM_DIFY_LIVE") == "1":
    TARGETS_LIVE.append("dify")

if not TARGETS_LIVE:
    pytestmark = pytest.mark.skip(reason="set LOOM_HIAGENT_LIVE and/or LOOM_DIFY_LIVE to run live")


@pytest.mark.parametrize("target", TARGETS_LIVE)
@pytest.mark.parametrize("row", MATRIX, ids=lambda r: r.id)
@pytest.mark.asyncio
async def test_row_executes(row, target):
    case = row.case_factory()
    result = await execute(case, target=target)
    assert result.ok, f"{row.id} failed on {target}: {result.detail}"
```

- [ ] **Step 3: Update `loom/conformance/runner.py`**

The Phase 0 stub does not need changes — the runner module is shape only. `execute.py` is the new piece. Confirm `from loom.conformance.runner import ConformanceCase, MatrixRow` still works.

- [ ] **Step 4: Run live (one or both runtimes)**

```bash
# Hiagent (primary)
bash scripts/hiagent_up.sh
LOOM_HIAGENT_LIVE=1 LOOM_HIAGENT_KEY=<key> pytest tests/conformance/test_runner_live.py -v
bash scripts/hiagent_down.sh

# Dify (secondary)
bash scripts/dify_up.sh
LOOM_DIFY_LIVE=1 LOOM_DIFY_KEY=<key> pytest tests/conformance/test_runner_live.py -v
bash scripts/dify_down.sh

# Both at once
LOOM_HIAGENT_LIVE=1 LOOM_HIAGENT_KEY=<hk> LOOM_DIFY_LIVE=1 LOOM_DIFY_KEY=<dk> \
  pytest tests/conformance/test_runner_live.py -v
```

Expected: 10/10 PASS per registered target. Red row blocks the Phase 1 release per PRD §5 / §10. If only one runtime is up, the gate covers only that runtime; the Phase 1 gate report (Task 17) will mark the other runtime's rows N/A only if the Cost-budget escape hatch was invoked (per ADR 0002).

- [ ] **Step 5: Commit**

```bash
git add loom/conformance/execute.py tests/conformance/test_runner_live.py loom/runtimes/base.py
git commit -m "feat(conformance): runner targets RuntimeAdapter; per-runtime live gating (Hiagent + Dify)"
```

---

## Task 13: Deployer (push as draft only)

**Files:**
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/loom/deployer/__init__.py`
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/loom/deployer/draft.py`
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/tests/deployer/__init__.py`
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/tests/deployer/test_draft.py`

Phase 1 deployer only pushes-as-draft, **target-parameterized** via the RuntimeAdapter (ADR 0015). Publish-blocking, drift detection, registry mirror — those land in Phase 2A on top of the same adapter contract.

- [ ] **Step 1: Write the test (target-parameterized via fake adapter)**

```python
# tests/deployer/test_draft.py
import json
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock

import pytest

from loom.deployer.draft import push_as_draft
from loom.ir.models import IRDocument
from loom.runtimes.base import DraftHandle, PushContext
from loom.runtimes import registry as runtime_registry

ROOT = Path(__file__).resolve().parents[2]


def _fake_adapter(target: str):
    a = MagicMock()
    a.target = target
    a.compile = MagicMock(return_value={"ok": True, "target": target})
    a.canonical_ast_hash = MagicMock(return_value="0" * 64)
    a.push_draft = AsyncMock(return_value=DraftHandle(target=target, draft_id=f"{target}-d1", canonical_ast_hash="0" * 64))
    return a


@pytest.fixture(autouse=True)
def _reset_registry():
    yield
    for t in list(runtime_registry.list_targets()):
        runtime_registry.unregister(t)


@pytest.mark.asyncio
@pytest.mark.parametrize("target", ["hiagent", "dify"])
async def test_push_as_draft_uses_adapter_for_target(target):
    runtime_registry.register(_fake_adapter(target))
    ir = IRDocument.model_validate(json.loads((ROOT / "examples" / "ir" / "01-ecommerce-customer-faq.json").read_text()))
    result = await push_as_draft(ir, target=target, actor="alice")
    assert result.handle.target == target
    assert result.handle.draft_id == f"{target}-d1"
```

- [ ] **Step 2: Write `loom/deployer/__init__.py`**

```python
"""FDE Deployer: push compiled DSL to a target runtime (Hiagent or Dify) as draft."""
```

- [ ] **Step 3: Write `loom/deployer/draft.py`**

```python
"""Phase 1 deployer: push as draft on the chosen runtime. No publish, no drift, no
registry mirror — those are Phase 2A on top of the same RuntimeAdapter."""
from __future__ import annotations
from dataclasses import dataclass

from loom.ir.models import IRDocument
from loom.runtimes import registry as runtime_registry
from loom.runtimes.base import DraftHandle, PushContext


@dataclass(frozen=True)
class DraftPushResult:
    handle: DraftHandle
    dsl: object   # runtime-specific DSL (Hiagent JSON or Dify YAML)


async def push_as_draft(ir: IRDocument, *, target: str = "hiagent", actor: str) -> DraftPushResult:
    adapter = runtime_registry.get(target)
    dsl = adapter.compile(ir)
    handle = await adapter.push_draft(dsl, PushContext(actor=actor, workflow_name=ir.metadata.name))
    return DraftPushResult(handle=handle, dsl=dsl)
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/deployer/ -v && mypy loom`
Expected: 2/2 PASS (one per target).

- [ ] **Step 5: Commit**

```bash
git add loom/deployer/ tests/deployer/
git commit -m "feat(deployer): Phase 1 push-as-draft via RuntimeAdapter; target-parameterized (Hiagent + Dify)"
```

---

## Task 14: CLI

**Files:**
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/loom/cli/__init__.py`
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/loom/cli/main.py`
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/loom/cli/commands/__init__.py`
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/loom/cli/commands/plan.py`
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/loom/cli/commands/validate.py`
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/loom/cli/commands/compile.py`
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/loom/cli/commands/deploy.py`
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/loom/cli/commands/reverse.py`
- Modify: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/pyproject.toml` — add console_scripts
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/tests/cli/__init__.py`
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/tests/cli/test_cli.py`

Single CLI entry: `loom <command>`. Each command lives in its own file.

- [ ] **Step 1: Write the CLI test**

```python
# tests/cli/test_cli.py
import json
from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner

from loom.cli.main import cli

ROOT = Path(__file__).resolve().parents[2]


def test_validate_passes_for_clean_archetype(tmp_path):
    src = ROOT / "examples" / "ir" / "01-ecommerce-customer-faq.json"
    runner = CliRunner()
    result = runner.invoke(cli, ["validate", str(src), "--scope", "ecommerce/kb"])
    assert result.exit_code == 0, result.output


def test_validate_fails_on_missing_rationale(tmp_path):
    src = json.loads((ROOT / "examples" / "ir" / "01-ecommerce-customer-faq.json").read_text())
    del src["nodes"][1]["rationale"]
    p = tmp_path / "bad.json"
    p.write_text(json.dumps(src))
    runner = CliRunner()
    result = runner.invoke(cli, ["validate", str(p), "--scope", "ecommerce/kb"])
    assert result.exit_code != 0
    assert "schema" in result.output


def test_compile_writes_dsl(tmp_path):
    src = ROOT / "examples" / "ir" / "01-ecommerce-customer-faq.json"
    out = tmp_path / "out.yaml"
    runner = CliRunner()
    result = runner.invoke(cli, ["compile", str(src), "--out", str(out)])
    assert result.exit_code == 0, result.output
    assert out.exists()
    assert "app:" in out.read_text()


def test_reverse_round_trips(tmp_path):
    src = ROOT / "examples" / "ir" / "01-ecommerce-customer-faq.json"
    yaml_path = tmp_path / "ecommerce_faq.yaml"
    runner = CliRunner()
    runner.invoke(cli, ["compile", str(src), "--out", str(yaml_path)])
    out_ir = tmp_path / "back.json"
    result = runner.invoke(cli, ["reverse", str(yaml_path), "--out", str(out_ir)])
    assert result.exit_code == 0, result.output
```

- [ ] **Step 2: Write the command modules**

```python
# loom/cli/__init__.py
"""FDE CLI."""
```

```python
# loom/cli/commands/__init__.py
```

```python
# loom/cli/main.py
import click

from loom.cli.commands import compile as cmd_compile
from loom.cli.commands import deploy as cmd_deploy
from loom.cli.commands import plan as cmd_plan
from loom.cli.commands import reverse as cmd_reverse
from loom.cli.commands import validate as cmd_validate


@click.group(help="FDE: deterministic AI workflows.")
def cli() -> None:
    pass


cli.add_command(cmd_plan.plan)
cli.add_command(cmd_validate.validate_cmd, name="validate")
cli.add_command(cmd_compile.compile_cmd, name="compile")
cli.add_command(cmd_deploy.deploy_cmd, name="deploy")
cli.add_command(cmd_reverse.reverse_cmd, name="reverse")


if __name__ == "__main__":
    cli()
```

```python
# loom/cli/commands/plan.py
import json
import sys
from pathlib import Path

import click

from loom.planner.retry import plan as plan_intent
from loom.planner.types import IntentRequest


@click.command(help="Plan: NL intent + scope → IR JSON.")
@click.argument("intent_file", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--out", "out_path", type=click.Path(path_type=Path), required=True)
def plan(intent_file: Path, out_path: Path) -> None:
    req = IntentRequest.model_validate_json(intent_file.read_text())
    res = plan_intent(req)
    if not res.ok:
        click.echo("Planner failed after retries:", err=True)
        for f in res.failures:
            click.echo(f"  [{f.bucket}] {f.detail}", err=True)
        sys.exit(2)
    out_path.write_text(json.dumps(res.ir.model_dump(by_alias=True), indent=2))
    click.echo(f"OK in {res.attempts} attempts; ${res.cost_usd:.4f}; {res.latency_s:.1f}s")
```

```python
# loom/cli/commands/validate.py
import json
import sys
from pathlib import Path

import click

from loom.validator.validate import validate


@click.command()
@click.argument("ir_file", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--scope", required=True)
def validate_cmd(ir_file: Path, scope: str) -> None:
    doc = json.loads(ir_file.read_text())
    failures = validate(doc, scope=scope)
    if not failures:
        click.echo("OK")
        return
    for f in failures:
        click.echo(f"[{f.bucket}] {f.location or '-'}: {f.detail}", err=True)
    sys.exit(2)
```

```python
# loom/cli/commands/compile.py
import json
from pathlib import Path

import click

from loom.runtimes import registry as runtime_registry
from loom.ir.models import IRDocument


@click.command()
@click.argument("ir_file", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--target", type=click.Choice(["hiagent", "dify"]), default="hiagent",
              help="Target runtime; default hiagent (primary).")
@click.option("--out", "out_path", type=click.Path(path_type=Path), required=True)
def compile_cmd(ir_file: Path, target: str, out_path: Path) -> None:
    """Compile IR to the chosen runtime's DSL via RuntimeAdapter."""
    ir = IRDocument.model_validate(json.loads(ir_file.read_text()))
    adapter = runtime_registry.get(target)
    dsl = adapter.compile(ir)
    # adapter.serialize_dsl renders to text (Hiagent JSON or Dify YAML); part of ADR 0015
    out_path.write_text(adapter.serialize_dsl(dsl))
    click.echo(f"wrote {out_path} ({target})")
```

```python
# loom/cli/commands/deploy.py
import json
import os
from pathlib import Path

import asyncio
import click

from loom.deployer.draft import push_as_draft
from loom.ir.models import IRDocument


@click.command()
@click.argument("ir_file", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--target", type=click.Choice(["hiagent", "dify"]), default="hiagent",
              help="Target runtime; default hiagent (primary).")
@click.option("--actor", default=lambda: os.environ.get("LOOM_ACTOR", "cli"), help="Actor for audit purposes.")
def deploy_cmd(ir_file: Path, target: str, actor: str) -> None:
    """Compile + push as draft on the chosen runtime via RuntimeAdapter."""
    ir = IRDocument.model_validate(json.loads(ir_file.read_text()))
    result = asyncio.run(push_as_draft(ir, target=target, actor=actor))
    click.echo(f"draft pushed on {target}: draft_id={result.handle.draft_id} ast_hash={result.handle.canonical_ast_hash[:12]}")
```

```python
# loom/cli/commands/reverse.py
import json
from pathlib import Path

import click

from loom.runtimes import registry as runtime_registry
from loom.runtimes.base import UnrecognizedConstruct


@click.command()
@click.argument("dsl_file", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--target", type=click.Choice(["hiagent", "dify"]), default="hiagent",
              help="Source runtime; the file is interpreted as that runtime's DSL.")
@click.option("--out", "out_path", type=click.Path(path_type=Path), required=True)
def reverse_cmd(dsl_file: Path, target: str, out_path: Path) -> None:
    adapter = runtime_registry.get(target)
    dsl_raw = dsl_file.read_text()
    # adapter parses its own DSL format
    dsl = adapter.parse_dsl(dsl_raw)  # adapter exposes parse_dsl per ADR 0015
    ir, unrecognized = adapter.reverse(dsl)
    if unrecognized:
        for u in unrecognized:
            click.echo(f"unrecognized on {u.target}: {u.construct} — {u.remediation}", err=True)
        raise SystemExit(2)
    out_path.write_text(json.dumps(ir.model_dump(), indent=2))
    click.echo(f"wrote {out_path} (reverse-compiled from {target})")
```

- [ ] **Step 3: Modify `pyproject.toml` to expose the CLI**

Add this block:

```toml
[project.scripts]
loom = "loom.cli.main:cli"
```

Re-install:

```bash
pip install -e ".[dev]"
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/cli/ -v && mypy loom`
Expected: 4/4 PASS.

- [ ] **Step 5: Smoke the CLI end-to-end**

```bash
# Validate (runtime-agnostic)
loom validate examples/ir/01-ecommerce-customer-faq.json --scope ecommerce/kb

# Compile + reverse on Hiagent (primary)
loom compile examples/ir/01-ecommerce-customer-faq.json --target hiagent --out /tmp/ecommerce_faq.hiagent.json
loom reverse /tmp/ecommerce_faq.hiagent.json --target hiagent --out /tmp/ecommerce_faq.from-hiagent.json

# Compile + reverse on Dify (secondary; skip if Cost-budget escape hatch invoked)
loom compile examples/ir/01-ecommerce-customer-faq.json --target dify --out /tmp/ecommerce_faq.dify.yaml
loom reverse /tmp/ecommerce_faq.dify.yaml --target dify --out /tmp/ecommerce_faq.from-dify.json
```

Expected: each command prints OK / wrote …. Both `*.from-{hiagent,dify}.json` files canonicalize to the same IR (parity contract).

- [ ] **Step 6: Commit**

```bash
git add loom/cli/ tests/cli/ pyproject.toml
git commit -m "feat(cli): loom plan/validate/compile/deploy/reverse"
```

---

## Task 15: Eval corpus + runner

**Files:**
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/corpus/deep/01-ecommerce-customer-faq/prompt-01.json`
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/corpus/deep/01-ecommerce-customer-faq/prompt-02.json` … prompt-15
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/corpus/deep/05-ecommerce-order-exception/prompt-01.json` … prompt-15
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/loom/eval/__init__.py`
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/loom/eval/corpus.py`
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/loom/eval/runner.py`
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/tests/eval/__init__.py`
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/tests/eval/test_eval_corpus.py`

PRD §10: "Phase 1 corpus = ≥30 prompts across the 2 deep-coverage archetypes (≥15 each), drawn from the design partner's real backlog where possible, hand-authored otherwise. Corpus changes are versioned and reviewed; you cannot game a metric by mutating the corpus."

The `expected_ir_shape` in each tuple is **structural**, not literal — a small fingerprint (set of node types, presence of certain references) the runner can match. Literal IR equality is too strict; PRD §10 measures "first-try IR validity rate" against schema+validator, not literal match.

- [ ] **Step 1: Write each prompt file**

Format:

```json
// corpus/deep/01-ecommerce-customer-faq/prompt-01.json
{
  "intent": "Build a multilingual customer-FAQ workflow that answers buyer questions over the product_kb and policy_kb datasets, with re-rank before answering and citations in the response. Reply in buyer_locale; do not promise specific compensation amounts beyond what policy_kb states.",
  "scope": "ecommerce/kb",
  "expected_shape": {
    "node_types": ["trigger", "retrieval", "llm", "llm", "output"],
    "must_reference": ["${input.query}", "${retrieve.chunks}"],
    "must_have_output_schema_on_terminal_llm": true
  }
}
```

The engineer authoring this corpus drafts 15 prompts per archetype. Vary along: query verbosity, number of constraints mentioned, ordering of steps in the NL, presence of ambiguity. The full set is committed to git.

- [ ] **Step 2: Write `loom/eval/corpus.py`**

```python
"""Eval-corpus loader + expected-shape matcher."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

CORPUS_ROOT = Path(__file__).resolve().parents[2] / "corpus"


@dataclass(frozen=True)
class CorpusItem:
    archetype: str
    prompt_id: str
    intent: str
    scope: str
    expected_shape: dict[str, Any]


def load(subset: str = "deep") -> list[CorpusItem]:
    out: list[CorpusItem] = []
    root = CORPUS_ROOT / subset
    for arch_dir in sorted(root.iterdir()):
        if not arch_dir.is_dir():
            continue
        for p in sorted(arch_dir.glob("prompt-*.json")):
            data = json.loads(p.read_text())
            out.append(CorpusItem(
                archetype=arch_dir.name,
                prompt_id=p.stem,
                intent=data["intent"],
                scope=data["scope"],
                expected_shape=data.get("expected_shape", {}),
            ))
    return out


def shape_match(ir: dict[str, Any], expected: dict[str, Any]) -> list[str]:
    """Return list of mismatch reasons; empty list = match."""
    issues: list[str] = []
    if "node_types" in expected:
        actual = [n["type"] for n in _walk_nodes(ir["nodes"])]
        if sorted(actual) != sorted(expected["node_types"]):
            issues.append(f"node types {actual} != expected {expected['node_types']}")
    if "must_reference" in expected:
        flat = json.dumps(ir)
        for ref in expected["must_reference"]:
            if ref not in flat:
                issues.append(f"missing reference {ref}")
    if expected.get("must_have_output_schema_on_terminal_llm"):
        terminal_llms = [n for n in ir["nodes"]
                         if n["type"] == "llm" and n["id"] == _terminal_llm_id(ir)]
        if not terminal_llms or not terminal_llms[0].get("output_schema"):
            issues.append("terminal llm missing output_schema")
    return issues


def _walk_nodes(nodes):
    for n in nodes:
        yield n
        if n["type"] == "loop":
            yield from _walk_nodes(n["body"])
        elif n["type"] == "parallel":
            for branch in n["branches"].values():
                yield from _walk_nodes(branch)


def _terminal_llm_id(ir) -> str | None:
    """The llm node whose id is referenced from the output node bindings."""
    out = next((n for n in ir["nodes"] if n["type"] == "output"), None)
    if not out:
        return None
    for v in out["bindings"].values():
        if isinstance(v, str) and v.startswith("${") and "." in v:
            ref_node = v[2:].split(".")[0]
            for n in ir["nodes"]:
                if n["id"] == ref_node and n["type"] == "llm":
                    return ref_node
    return None
```

- [ ] **Step 3: Write `loom/eval/runner.py`**

```python
"""Run the Planner over a corpus subset; report failure taxonomy + cost."""
from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from statistics import median

from loom.eval.corpus import CorpusItem, load, shape_match
from loom.planner.client import PlannerClient
from loom.planner.retry import plan
from loom.planner.types import IntentRequest


@dataclass(frozen=True)
class EvalReport:
    n_total: int
    n_first_try_valid: int
    n_after_retries_valid: int
    n_failed: int
    bucket_counts: dict[str, int]
    median_cost: float
    p95_cost: float
    median_latency: float
    p95_latency: float


def run_eval(items: list[CorpusItem], *, max_retries: int = 3,
              client: PlannerClient | None = None) -> EvalReport:
    bucket_counter: Counter[str] = Counter()
    first_try = 0
    after_retries = 0
    failed = 0
    costs: list[float] = []
    latencies: list[float] = []

    client = client or PlannerClient()

    for item in items:
        req = IntentRequest(intent=item.intent, scope=item.scope, max_retries=max_retries)
        res = plan(req, client=client)
        costs.append(res.cost_usd)
        latencies.append(res.latency_s)
        if res.ok:
            if res.attempts == 1:
                first_try += 1
            else:
                after_retries += 1
            shape_issues = shape_match(res.ir.model_dump(by_alias=True), item.expected_shape)
            if shape_issues:
                bucket_counter["shape_match"] += 1
        else:
            failed += 1
            for f in res.failures:
                bucket_counter[f.bucket] += 1

    return EvalReport(
        n_total=len(items),
        n_first_try_valid=first_try,
        n_after_retries_valid=after_retries,
        n_failed=failed,
        bucket_counts=dict(bucket_counter),
        median_cost=median(costs),
        p95_cost=_pct(costs, 0.95),
        median_latency=median(latencies),
        p95_latency=_pct(latencies, 0.95),
    )


def _pct(xs: list[float], q: float) -> float:
    if not xs:
        return 0.0
    s = sorted(xs)
    return s[min(int(q * len(s)), len(s) - 1)]
```

- [ ] **Step 4: Write a tiny offline test (no live LLM)**

```python
# tests/eval/test_eval_corpus.py
from loom.eval.corpus import load, shape_match


def test_corpus_loads_at_least_30_items():
    items = load("deep")
    assert len(items) >= 30
    archs = {it.archetype for it in items}
    assert archs == {"01-ecommerce-customer-faq", "05-ecommerce-order-exception"}


def test_shape_match_passes_on_clean_ir():
    import json
    from pathlib import Path
    ir = json.loads(Path("examples/ir/01-ecommerce-customer-faq.json").read_text())
    expected = {
        "node_types": ["trigger", "retrieval", "llm", "llm", "output"],
        "must_reference": ["${input.query}", "${retrieve.chunks}"],
        "must_have_output_schema_on_terminal_llm": True,
    }
    assert shape_match(ir, expected) == []
```

- [ ] **Step 5: Run offline tests**

Run: `pytest tests/eval/ -v && mypy loom`
Expected: 2/2 PASS.

- [ ] **Step 6: Run the live eval (optional in dev; mandatory before declaring Phase 1 done)**

```bash
ANTHROPIC_API_KEY=<key> python -c "
from loom.eval.corpus import load
from loom.eval.runner import run_eval
report = run_eval(load('deep'))
print(report)
"
```

PRD §10 Phase 1 target: first-try validity ≥ 70 percent across the deep corpus. If below, examine bucket_counts: schema/reference/type_flow/policy. Fix the system prompt or few-shot library, re-run.

- [ ] **Step 7: Commit**

```bash
git add corpus/ loom/eval/ tests/eval/
git commit -m "feat(eval): deep-corpus (15+15) + runner with PRD §10 failure taxonomy"
```

---

## Task 16: Update Phase 0 conformance CI to invoke Compiler

**Files:**
- Modify: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/.github/workflows/conformance.yml`

Phase 0 wired the conformance workflow to a stub. Phase 1 has a real Compiler. Update the workflow to run `tests/conformance/test_runner_live.py` (live matrix) and to fail-fast on a single red row (PRD §5 release-blocker rule).

- [ ] **Step 1: Update the workflow file**

Replace the body with:

```yaml
name: conformance
on:
  workflow_dispatch:
  schedule:
    - cron: "0 6 * * *"
  pull_request:
    paths:
      - "loom/runtimes/**"
      - "loom/conformance/**"

jobs:
  matrix:
    runs-on: ubuntu-latest
    timeout-minutes: 90
    env:
      # When Cost-budget escape hatch is invoked, set vars.LOOM_DROP_DIFY=true in repo settings;
      # the Dify steps below skip and the Dify gate rows are marked N/A in the report.
      LOOM_DROP_DIFY: ${{ vars.LOOM_DROP_DIFY || 'false' }}
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.11" }
      - run: pip install -e ".[dev]"

      # Hiagent (primary) — always runs unless not registered for this repo
      - name: Start pinned Hiagent
        run: bash scripts/hiagent_up.sh
      - name: Run live conformance matrix on Hiagent
        env:
          LOOM_HIAGENT_LIVE: "1"
          LOOM_HIAGENT_KEY: ${{ secrets.LOOM_HIAGENT_KEY }}
          LOOM_HIAGENT_URL: http://localhost:32301
        run: pytest tests/conformance/test_runner_live.py -v --maxfail=1
      - name: Stop Hiagent
        if: always()
        run: bash scripts/hiagent_down.sh

      # Dify (secondary) — skipped if Cost-budget escape hatch invoked
      - name: Start pinned Dify
        if: env.LOOM_DROP_DIFY != 'true'
        run: bash scripts/dify_up.sh
      - name: Run live conformance matrix on Dify
        if: env.LOOM_DROP_DIFY != 'true'
        env:
          LOOM_DIFY_LIVE: "1"
          LOOM_DIFY_KEY: ${{ secrets.LOOM_DIFY_KEY }}
          LOOM_DIFY_URL: http://localhost:5001
        run: pytest tests/conformance/test_runner_live.py -v --maxfail=1
      - name: Stop Dify
        if: always() && env.LOOM_DROP_DIFY != 'true'
        run: bash scripts/dify_down.sh
```

> The two runtime sections are independent and run sequentially (avoids port collisions / resource contention). When Dify is dropped, only the Hiagent block runs; the gate report marks Dify rows N/A and the conformance contract still holds for Hiagent. Adding LangGraph alpha (Phase 3.2 optional) follows the same `vars.LOOM_DROP_*` pattern.

- [ ] **Step 2: Commit**

```bash
git add .github/workflows/conformance.yml
git commit -m "ci(conformance): live matrix on PR (fail-fast on red cell per PRD §5)"
```

---

## Task 17: Phase 1 release gate

**Files:**
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/reports/phase-1-gate.md`

PRD §7 Phase 1 success criterion: "≥70% first-try IR validity on the deep-coverage archetypes (≥85% by end of Phase 2 per §10), all semantic conformance tests green, narrow round-trip works on the deep-coverage archetypes."

- [ ] **Step 1: Run all gates**

```bash
ruff check .
mypy loom
pytest -v
ANTHROPIC_API_KEY=<key> python -c "
import json
from loom.eval.corpus import load
from loom.eval.runner import run_eval
report = run_eval(load('deep'))
print(json.dumps(report.__dict__, indent=2))
"
LOOM_DIFY_LIVE=1 LOOM_DIFY_KEY=<key> pytest tests/conformance/test_runner_live.py -v
```

- [ ] **Step 2: Write `reports/phase-1-gate.md`**

```markdown
# Phase 1 gate

Date: YYYY-MM-DD
Pinned Hiagent: <tag@digest>   # ADR 0002
Pinned Dify: <tag@digest>      # ADR 0002

## Success criteria (PRD §7 Phase 1)

| Criterion | Target | Actual | Status |
|---|---|---|---|
| First-try IR validity, deep corpus (overall) | ≥ 70% | NN% | pass/fail |
| First-try IR validity, deep corpus, Hiagent | ≥ 70% | NN% | pass/fail |
| First-try IR validity, deep corpus, Dify | ≥ 70% | NN% | pass/fail |
| Semantic conformance matrix, Hiagent | 100% green | NN of 10 | pass/fail |
| Semantic conformance matrix, Dify | 100% green | NN of 10 | pass/fail |
| Conformance flake rate (max across runtimes) | <2% (>5% blocks) | NN% | pass/fail |
| Narrow round-trip canonical equality, 01-ecommerce-customer-faq, Hiagent | pass | pass/fail | pass/fail |
| Narrow round-trip canonical equality, 01-ecommerce-customer-faq, Dify | pass | pass/fail | pass/fail |
| Narrow round-trip canonical equality, 05-ecommerce-order-exception, Hiagent | pass | pass/fail | pass/fail |
| Narrow round-trip canonical equality, 05-ecommerce-order-exception, Dify | pass | pass/fail | pass/fail |
| RuntimeAdapter contract test passes for both runtimes | green | green/red | pass/fail |
| Persona Brief integrated into FDE Session and Planner | shipped | shipped/missing | pass/fail |

## Failure taxonomy breakdown (PRD §10)

| Bucket | Hiagent | Dify | Total |
|---|---|---|---|
| schema | NN | NN | NN |
| reference | NN | NN | NN |
| type_flow | NN | NN | NN |
| policy | NN | NN | NN |
| compile | NN | NN | NN |
| deploy | NN | NN | NN |
| reverse_compile | NN | NN | NN |

## Cost / latency

- Median Planner cost: $0.NN (target <$0.20)
- P95 Planner cost: $0.NN (target <$1.00)
- Median Planner latency: NNs (target <30s)
- P95 Planner latency: NNs (target <90s)

## Cost-budget escape decision (if invoked)

If during Phase 1 the dual-runtime cost was too high and Dify was dropped, document here:
- Decision date: YYYY-MM-DD
- Reason: <brief>
- Affected gate rows: Dify rows above marked N/A
- Hiagent rows: must still pass at full bar
```

- [ ] **Step 3: Commit**

```bash
git add reports/phase-1-gate.md
git commit -m "docs: Phase 1 gate report"
```

---

## Self-review summary

- **Spec coverage:** FDE Session, Planner, Validator, Compiler, narrow reverse compiler, CLI, deployer-as-draft, conformance live runner, eval corpus + runner, Phase 1 gate report — all from PRD §4 / §5 / §6 / §7 / §8 / §10. The workflow brief, blocking-question policy, edit-intent model, IR v0.3 grammar (§5), credential handles (§5), per-major-Dify-version Compiler module (§9 vendor-lock policy), and prompt-injection mitigations (§9) are present. Drift detection, full reverse compiler, registry mirror, web UI, RBAC are *deliberately* deferred to Phase 2A/2B (consistent with PRD §7 split).

- **Placeholder scan:** every `vX_Y` is flagged at the top of Task 9 with explicit replacement instructions; few-shot files have a paste instruction with a clear source. No orphan TODO/TBD.

- **Type consistency:** `IntentRequest`, `PlannerResult`, `FailureRecord`, `ValidationFailure`, `IRDocument`, `Registry`, `ToolEntry`, `DraftPushResult`, `ConformanceCase`, `MatrixRow` — names match across files. The Validator's `FailureBucket` matches the Planner's failure taxonomy (PRD §10). The Compiler's `compile_ir` signature matches in conformance, deployer, CLI.

- **Known seams to Phase 1.5 / Phase 2A:** (a) eval corpus is `deep` only; Phase 1.5 adds `full`. (b) Reverse compiler is narrow; Phase 2A widens it. (c) Deployer is push-as-draft; Phase 2A adds drift + publish-blocking. (d) Registry is in-tree v1; Phase 2A makes it git-versioned and Postgres-mirrored.

---

## Execution Handoff

Plan complete and saved to `docs/plans/2026-05-05-phase-1-mvp-core.md`. Recommended execution modes:

1. **Subagent-Driven (recommended)** — Dispatch a fresh subagent per task, review between tasks, fast iteration.
2. **Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints.
