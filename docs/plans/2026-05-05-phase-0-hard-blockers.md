# FDE Phase 0 — Default Decisions and Evidence Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Document location:** Project execution plans live in `docs/plans/`. This file was moved out of `docs/superpowers/plans/`; Superpowers is a methodology, not the product-plan directory.

**Naming note:** Product-facing language is FDE / AI 驻场流程工程师. Internal implementation paths may temporarily retain the `loom/` Python namespace until a package rename decision is made.

**Goal:** Close the Phase 0 default decisions and produce the Phase 0 evidence package, so that Phase 1 code can be written against fixed versions, credential-binding rules, reverse-compile boundaries, and agent/LLM defaults. The first FDE step is a **SOW / requirements intake**; a real partner SOW is useful but synthetic-partner mode is acceptable.

**Architecture:** Phase 0 is mostly *decisions* and *artifacts*, not running software. The deliverables are: (1) ADR 0001 SOW / requirements intake contract; (2) ADR 0002 runtime pins — **Hiagent 2.6** and **Dify 1.14.0**; (3) ADR 0003 credential binding strategy — platform-managed LLM credentials and HTTP auth bindings for non-LLM integrations; (4) ADR 0004 default reverse-compile scope; (5) ADR 0005 agent/LLM defaults with `max_output_tokens = 8000`; (6) a frozen IR v0.3 JSON Schema; (7) five SOW-derived archetype IRs; (8) Phase 0 Dify engineering evidence: conformance baseline, N=10 canonicalization proof, reverse-compile spike, and security review. Code in Phase 0 is the minimum scaffolding to prove the assumptions. None of this code is the production system.

**Tech Stack:** Python 3.11, Pydantic v2, JSON Schema 2020-12, Docker (pinned Hiagent + Dify images per ADR 0002), pytest, ruff, mypy.

> **Trim note (2026-05-06):** Phase 0 is mostly *contracts and ADRs* — these MUST be detailed. Code snippets (Pydantic models, canonicalizer, conformance harness) below stay verbatim because Phase 1 + Phase 1.5 build on them. ADR 0001 is now the SOW / requirements intake contract, not an external partner confirmation gate. ADR 0004 is the default reverse-compile scope, not a senior-review signoff gate. Per project owner directive 2026-05-06: trim only execution-detail noise, keep all contract-level specs.

> **n8n out (2026-05-06):** n8n was scoped out of v1. Phase 0 ADR 0002 covers Hiagent + Dify version pinning (extended from earlier draft that pinned only Dify); Phase 1 ships RuntimeAdapter + both compilers. References to n8n / portability redlines in earlier drafts are obsolete; ADR 0006 / 0007 / 0018 are tombstones (see Phase 3-4 plan).

> **Phase 0 runtime scope (2026-05-06 clarification).** ADR 0002 pins **both** runtime versions in this phase — that's a *decision* artifact, runtime-neutral. The Phase 0 *engineering* artifacts (Dify client, canonicalization proof, conformance baseline, reverse-compile spike, gate evidence) below are intentionally **Dify-only** in this phase to keep Phase 0's scope tight. The Hiagent equivalents (`loom/runtimes/hiagent/client.py`, Hiagent canonicalization proof, Hiagent conformance baseline, Hiagent reverse spike) ship in **Phase 1 Task 11.5** alongside the RuntimeAdapter abstraction (ADR 0015). The Phase 1 gate (Task 17) requires both runtimes to pass conformance + round-trip; the Phase 0 gate only requires Dify. If the Cost-budget escape hatch (per PRD §7) is invoked **before** Phase 0 completes, Dify is dropped, this Phase 0 evidence list becomes the *Hiagent* evidence list, and the equivalent files are produced under `loom/runtimes/hiagent/` instead.

> **MVP scope (2026-05-07).** The cloud-only-pivot of 2026-05-07 was reverted because both runtimes are **self-hosted-docker on customer-owned cloud VMs** (the customer's IT ops deploys; FDE itself does not run docker locally or operate cloud VMs). MVP definition is locked at **"NL → Planner → IR → Compiler → YAML file"** — no auto-push, no per-customer endpoint/token wiring. The operator manually imports the generated YAML in their self-hosted Dify / Hiagent console.
>
> Implications for Phase 0 task scope under MVP:
> - **Tasks 7 / 8 / 9 / 10**: critical path, ship as-written.
> - **Tasks 11 / 12 / 13**: ship as-written **but run offline only** in MVP (unit + golden + canonical-AST hash; no live HTTP smoke unless the executor sets `LOOM_DIFY_LIVE=1` against an externally-provided Dify endpoint).
> - **Tasks 14 / 15 / 16 / 17 (Phase 0 gate evidence rows that need a live runtime)**: marked **first-customer-deferred**. The evidence is produced when the first customer integration provides a Dify endpoint + token; the Phase 0 gate report carries these rows as `deferred_to_first_customer_integration` rather than `passed`. Phase 0 close-out for MVP does not require these rows green.
> - **Task 3.1 (deferred upstream Dify 1.14.0 compose sourcing)**: still deferred; needed eventually for customer-side deployment artifacts but not blocking MVP.

---

## Repo layout established by Phase 0

```
octopus_FDE/
├── docs/
│   ├── PRD.md                                  (existing, v0.4)
│   ├── PRD.zh-CN.md                            (existing)
│   ├── design/
│   │   ├── fde-product-design.md
│   │   └── fde-ecommerce-tcm.zh-CN.md
│   ├── decisions/                              (NEW — ADR-style decision records)
│   │   ├── 0001-sow-requirements-intake.md
│   │   ├── 0002-runtime-versions.md     (Hiagent + Dify pinned versions; was 0002-dify-version.md before 2026-05-06)
│   │   ├── 0003-credential-binding.md
│   │   ├── 0004-reverse-compile-scope.md
│   │   └── 0005-agent-governance.md
│   └── plans/
│       └── 2026-05-05-phase-0-hard-blockers.md (this file)
├── schemas/
│   ├── ir-v0.2.schema.json                     (existing, frozen)
│   └── ir-v0.3.schema.json                     (NEW — Phase 0 deliverable)
├── sow/
│   └── default-ecommerce/
│       └── phase0-synthetic-sow.yaml           (NEW — first SOW packet; replace/add real partner SOW later)
├── examples/
│   └── ir/
│       ├── 01-ecommerce-customer-faq.json           (existing v0.2 placeholder; rewrite to v0.3 + validate against SOW)
│       ├── 02-tcm-intake-triage.json                 (shadow)
│       ├── 03-clinic-ops-summary.json                (shadow)
│       ├── 04-tcm-followup.json                      (shadow)
│       ├── 05-ecommerce-order-exception.json
│       └── sow/                                (NEW — five SOW-derived workflows; real or synthetic)
│           ├── 01-<name>.json
│           ├── 02-<name>.json
│           ├── 03-<name>.json
│           ├── 04-<name>.json
│           └── 05-<name>.json
├── shadow-corpus/                              (NEW — second team / Dify gallery, 5 workflows)
│   └── ir/
│       └── ...
├── pyproject.toml                              (NEW)
├── ruff.toml                                   (NEW)
├── mypy.ini                                    (NEW)
├── README.md                                   (NEW — how to run Phase 0 evidence)
├── loom/
│   ├── __init__.py
│   ├── ir/
│   │   ├── __init__.py
│   │   ├── models.py                           (Pydantic v0.3 models)
│   │   ├── schema.py                           (JSON Schema loader/validator)
│   │   └── canonicalize.py                     (canonical IR + canonical Dify-AST)
│   ├── runtimes/
│   │   ├── __init__.py
│   │   └── dify/
│   │       ├── __init__.py
│   │       └── v1_14/
│   │           ├── __init__.py
│   │           ├── client.py                   (thin Dify 1.14 HTTP client, auth + import/export)
│   │           └── ast.py                      (Dify 1.14 DSL parse → canonical AST tree)
│   └── conformance/
│       ├── __init__.py
│       ├── matrix.py                           (matrix definitions; one row per §5 cell)
│       └── runner.py                           (executes a matrix row against pinned Dify)
├── scripts/
│   ├── dify_up.sh                              (docker compose up of pinned Dify)
│   ├── dify_down.sh
│   ├── round_trip_proof.py                     (N=10 import/export, hash stability)
│   ├── reverse_compile_spike.py                (manual edit → reverse compile → equality check)
│   └── security_review.py                      (static-check helper for §9 risks)
├── tests/
│   ├── ir/
│   │   ├── test_v03_schema.py
│   │   ├── test_canonicalize_ir.py
│   │   └── test_canonicalize_dify_ast.py
│   ├── dify/
│   │   └── test_client_smoke.py
│   ├── conformance/
│   │   └── test_runner_smoke.py
│   └── archetypes/
│       └── test_archetype_validates.py
├── .github/
│   └── workflows/
│       ├── ci.yml                              (lint + type + tests)
│       └── conformance.yml                     (Phase 0 slow lane against pinned Dify; Hiagent added in Phase 1 Task 11.5)
├── docker/
│   ├── hiagent-pinned/
│   │   ├── docker-compose.yml                  (pinned tag from decision 0002, Hiagent section)
│   │   └── README.md
│   └── dify-pinned/
│       ├── docker-compose.yml                  (pinned tag from decision 0002, Dify section)
│       └── README.md
└── reports/
    ├── phase-0-gate.md                         (NEW — the evidence package)
    ├── round-trip-proof.json                   (artifact of round-trip script)
    ├── reverse-compile-spike.md                (artifact of spike script)
    ├── security-review.md                      (artifact of security pass)
    └── reviewer-edit-simulation.md             (artifact of reviewer simulation)
```

Each task below states which files it creates or modifies. The order is the execution order; later tasks depend on earlier ones.

---

## Task 1: Bootstrap repo scaffolding (pyproject, lint, CI skeleton)

**Files:**
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/pyproject.toml`
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/ruff.toml`
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/mypy.ini`
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/README.md`
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/.gitignore`
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/loom/__init__.py`
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/tests/__init__.py`
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/tests/test_smoke.py`
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/.github/workflows/ci.yml`

- [ ] **Step 1: Write `pyproject.toml`**

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "loom"
version = "0.0.1"
description = "Deterministic, reviewable AI workflows. NL intent → IR → target runtime draft."
requires-python = ">=3.11"
dependencies = [
  "pydantic>=2.6,<3",
  "jsonschema>=4.21,<5",
  "httpx>=0.27,<1",
  "pyyaml>=6.0,<7",
  "click>=8.1,<9",
]

[project.optional-dependencies]
dev = [
  "pytest>=8.0,<9",
  "pytest-asyncio>=0.23,<1",
  "ruff>=0.4,<1",
  "mypy>=1.10,<2",
]

[tool.hatch.build.targets.wheel]
packages = ["loom"]
```

- [ ] **Step 2: Write `ruff.toml`**

```toml
line-length = 100
target-version = "py311"

[lint]
select = ["E", "F", "I", "B", "UP", "SIM", "TCH"]
ignore = ["E501"]

[lint.per-file-ignores]
"tests/**" = ["B", "E402"]
```

- [ ] **Step 3: Write `mypy.ini`**

```ini
[mypy]
python_version = 3.11
strict = True
plugins = pydantic.mypy

[mypy-tests.*]
disallow_untyped_decorators = False
```

- [ ] **Step 4: Write `README.md`**

```markdown
# FDE

Deterministic, reviewable AI workflows. The Planner emits a small IR; deterministic runtime adapters turn it into target runtime drafts.

See `docs/PRD.md` for the full spec.

## Phase 0 status

Phase 0 closes five default decisions and produces evidence the production system is buildable.
Run `make phase0-gate` to regenerate the evidence package in `reports/`.

## Dev quickstart

    python3 -m venv .venv
    source .venv/bin/activate
    pip install -e ".[dev]"
    pytest
    ruff check .
    mypy loom

## Pinned runtimes

ADR 0002 pins Hiagent 2.6 and Dify 1.14.0. Phase 0 engineering evidence runs against pinned Dify; the Hiagent equivalent ships in Phase 1 Task 11.5.
```

- [ ] **Step 5: Write empty package init files**

```python
# loom/__init__.py
"""FDE: deterministic, reviewable AI workflows."""

__version__ = "0.0.1"
```

```python
# tests/__init__.py
```

- [ ] **Step 5a: Write `.gitignore`** (project hygiene; keeps venv + caches out of git)

```
.venv/
__pycache__/
*.pyc
*.pyo
.mypy_cache/
.pytest_cache/
.ruff_cache/
.DS_Store
*.egg-info/
build/
dist/
```

- [ ] **Step 5b: Write `tests/test_smoke.py`** (placeholder so `pytest -v` exits 0; replaced by real tests in later tasks)

```python
def test_smoke() -> None:
    """Phase 0 scaffold smoke test. Removed once any real test exists."""
    assert True
```

- [ ] **Step 6: Write `.github/workflows/ci.yml`**

```yaml
name: ci
on:
  push:
    branches: [main]
  pull_request:

jobs:
  lint-type-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: pip install -e ".[dev]"
      - run: ruff check .
      - run: mypy loom
      - run: pytest -v
```

- [ ] **Step 7: Verify scaffolding** (in a project-local venv)

```bash
cd "/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE"
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest -v
ruff check .
mypy loom
```

Expected: `pytest -v` runs `test_smoke` and exits 0 (1 passed); `ruff check .` reports `All checks passed!`; `mypy loom` reports `Success: no issues found`.

- [ ] **Step 8: Commit** (project-local repo; init with `git init && git checkout -b main` if `octopus_FDE/.git` does not yet exist)

```bash
git checkout -b feature/phase-0-task-1-bootstrap
git add pyproject.toml ruff.toml mypy.ini README.md .gitignore loom/__init__.py tests/__init__.py tests/test_smoke.py .github/workflows/ci.yml
git commit -m "chore: bootstrap Phase 0 repo scaffolding"
```

---

## Task 2: Decision record 0001 — SOW / requirements intake

**Files:**
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/docs/decisions/0001-sow-requirements-intake.md`
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/sow/default-ecommerce/phase0-synthetic-sow.yaml`

This is a **decision + input artifact**, not code. It defines and instantiates the first FDE step: before Workflow Brief and IR generation, FDE captures a SOW / requirements packet. A real partner can fill it, but synthetic-partner mode is acceptable for Phase 0.

- [ ] **Step 1: Write the decision record**

```markdown
# ADR 0001 — SOW / requirements intake

**Status:** Accepted
**Date:** YYYY-MM-DD

## Decision

FDE Session starts with a SOW / requirements intake before Workflow Brief generation.

Required fields:
- `sow_id`
- `persona_id`
- `business_goal`
- `target_runtime`: `hiagent` | `dify`
- `vertical`: `ecommerce` | `tcm_shadow` | `<other>`
- `workflow_candidates`: 5 candidate workflows with trigger, inputs, outputs, tools/datasets, reviewer policy, success criteria
- `credential_bindings`: platform LLM bindings + HTTP auth bindings
- `reviewer_policy`
- `success_metrics`

Synthetic-partner mode is valid: if no real partner is ready, use a Bambu Lab-style cross-border ecommerce operator profile to fill the SOW and move engineering forward.

## Context

The previous external partner confirmation gate was too heavy. Partner context is an input to FDE, not a prerequisite to building FDE. The SOW contract gives Planner / Persona Brief / Workflow Brief a stable input shape.

## Initial synthetic SOW

Use cross-border ecommerce operations as the default synthetic SOW:
1. ecommerce customer FAQ / KB Q&A
2. ecommerce order-exception triage
3. product-content localization
4. after-sales escalation
5. operations reporting

TCM clinic workflows remain shadow corpus inputs, not the primary SOW.

## Replacement by real partner

When a real partner exists, write a new SOW file under `sow/<partner>/<sow_id>.yaml`; do not rewrite the contract.

## Consequences

- Phase 0 examples are derived from the SOW, not from an implicit external-partner assumption.
- Persona Brief and Workflow Brief both consume this intake shape.
```

- [ ] **Step 2: Write `sow/default-ecommerce/phase0-synthetic-sow.yaml`**

```yaml
sow_id: phase0-synthetic-ecommerce
source: synthetic
partner_profile: bambu-lab-style-cross-border-ecommerce-operator
persona_id: ecommerce-operator
business_goal: >
  Standardize multilingual customer support and order-exception workflows
  across Amazon, Shopify, TikTok Shop, Shein, and Temu channels.
target_runtime: dify
vertical: ecommerce
channels:
  - amazon
  - shopify
  - tiktok_shop
  - shein
  - temu
credential_bindings:
  llm:
    mode: platform_configured_after_import
    bindings:
      - provider: platform_default
        model: default_planner_model
        secret_values_in_artifacts: false
  http:
    - handle: shopify_api
      scheme: bearer
      allowed_hosts: ["*.myshopify.com"]
      secret_values_in_artifacts: false
    - handle: amazon_sp_api
      scheme: oauth2_client_credentials
      allowed_hosts: ["sellingpartnerapi-*.amazon.com"]
      secret_values_in_artifacts: false
reviewer_policy:
  reviewer_role: ecommerce_cs_lead
  publish_requires_review: true
  unrecognized_runtime_edits: block_publish_with_remediation
success_metrics:
  first_try_ir_validity: ">=70% in Phase 1"
  reviewability_median: ">=4"
  reviewer_hard_block_rate: "<5% steady-state"
workflow_candidates:
  - id: 01-ecommerce-customer-faq
    trigger: buyer question arrives from marketplace or storefront channel
    inputs: [buyer_locale, channel, product_id, question_text]
    outputs: [answer, citations, confidence]
    tools_datasets: [product_kb, policy_kb]
    reviewer_policy: low confidence escalates to human support
  - id: 05-ecommerce-order-exception
    trigger: order, shipment, return, or refund anomaly event
    inputs: [order_id, channel, buyer_locale, exception_type]
    outputs: [ops_queue_route, buyer_reply, manager_review_required]
    tools_datasets: [shopify_api, amazon_sp_api, policy_kb]
    reviewer_policy: refund or SLA-impacting actions require manager approval
  - id: product-content-localization
    trigger: new or changed listing content
    inputs: [source_locale, target_locale, product_id, source_copy]
    outputs: [localized_copy, risk_flags]
    tools_datasets: [product_kb, policy_kb]
    reviewer_policy: human review before marketplace publish
  - id: after-sales-escalation
    trigger: buyer complaint or negative review intent
    inputs: [channel, buyer_locale, message_text, order_context]
    outputs: [reply_draft, escalation_reason, queue]
    tools_datasets: [policy_kb]
    reviewer_policy: sentiment/high-risk complaints route to human support
  - id: operations-reporting
    trigger: daily scheduled report
    inputs: [date_range, channels]
    outputs: [gmv_summary, return_rate_summary, support_sla_summary]
    tools_datasets: [shopify_api, amazon_sp_api]
    reviewer_policy: report is internal read-only output
```

- [ ] **Step 3: Commit**

```bash
git add docs/decisions/0001-sow-requirements-intake.md sow/default-ecommerce/phase0-synthetic-sow.yaml
git commit -m "docs: ADR 0001 SOW intake contract and synthetic ecommerce SOW"
```

---

## Task 3: Decision record 0002 — Runtime versions locked (Hiagent + Dify)

**Files:**
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/docs/decisions/0002-runtime-versions.md`
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/docker/hiagent-pinned/docker-compose.yml`
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/docker/hiagent-pinned/README.md`
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/docker/dify-pinned/docker-compose.yml`
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/docker/dify-pinned/README.md`
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/scripts/hiagent_up.sh`
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/scripts/hiagent_down.sh`
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/scripts/dify_up.sh`
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/scripts/dify_down.sh`

This is the second default decision (PRD §7, §11 Q2). The deliverable is a runtime-version contract for **both Hiagent (primary) and Dify (secondary)** plus a runnable Phase 0 engineering target for Dify 1.14.0. Hiagent 2.6 is pinned here as a decision; its adapter evidence ships in Phase 1 Task 11.5 unless the Cost-budget escape hatch drops Dify before Phase 0 closes.

> **Cost-budget escape hatch.** If during execution the cost of running both runtimes is too high, drop Dify (keep Hiagent — primary). The ADR allows a "Hiagent-only" sub-mode that is still considered a valid Phase 0 close-out; the Phase 1 RuntimeAdapter registry simply unregisters the Dify adapter. This is documented in the ADR template's "Consequences" section.

- [ ] **Step 1: Write `docs/decisions/0002-runtime-versions.md`**

```markdown
# ADR 0002 — Runtime versions locked (Hiagent + Dify)

**Status:** Accepted
**Date:** YYYY-MM-DD

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
```

- [ ] **Step 2: Write `docker/hiagent-pinned/docker-compose.yml`**

```yaml
# Pinned Hiagent environment for FDE conformance testing.
# Tag + digest decided in docs/decisions/0002-runtime-versions.md (Hiagent section).
# Replace image name and digest once the Hiagent 2.6 artifact is provided.
# Hiagent compose layout depends on the deployment artifact provided by the vendor;
# this is a placeholder shape — adjust per the actual Hiagent self-hosted package.
version: "3.9"
services:
  hiagent:
    image: <hiagent-image>:2.6@sha256:DIGEST
    environment:
      - LOG_LEVEL=INFO
    ports:
      - "32300:32300"   # platform UI per public docs
      - "32301:32301"   # OpenAPI per HiAgent OpenAPI spec
    volumes:
      - hiagent-data:/var/lib/hiagent
volumes:
  hiagent-data:
```

> The Hiagent self-hosted package is enterprise-licensed; the compose snippet above is a placeholder. Replace image / port / volume layout once the vendor's pinned artifact is on hand. The ADR 0002 Hiagent section commits to the version + digest; this file commits to the docker-compose shape.

- [ ] **Step 2.1: Write `docker/hiagent-pinned/README.md`** (mirrors dify-pinned README; substitute Hiagent throughout).

- [ ] **Step 2.2: Write `scripts/hiagent_up.sh` and `scripts/hiagent_down.sh`** (shape mirrors `scripts/dify_*.sh`; up-script polls `http://localhost:32301/health` instead of Dify's port).

- [ ] **Step 3: Write `docker/dify-pinned/docker-compose.yml`**

```yaml
# Pinned Dify environment for FDE conformance testing.
# Source this file from the official Dify 1.14.0 docker compose, then pin
# every Dify-owned image tag/digest here. Do not hand-minimize the service set:
# if upstream 1.14.0 requires worker, plugin daemon, sandbox, nginx, etc.,
# keep them. Phase 0 evidence is valid only against a compose file that
# `docker compose config` accepts and `scripts/dify_up.sh` can bring healthy.
version: "3.9"
x-dify-api-image: &dify_api_image langgenius/dify-api:1.14.0@sha256:<digest>
x-dify-web-image: &dify_web_image langgenius/dify-web:1.14.0@sha256:<digest>
services:
  # Keep the official Dify 1.14.0 service graph here.
  # At minimum, FDE needs the API import/export/run paths and console auth path
  # reachable from localhost for Phase 0 evidence scripts.
  api:
    image: *dify_api_image
    # ... official 1.14.0 service definition ...
  worker:
    image: *dify_api_image
    # ... official 1.14.0 service definition ...
  web:
    image: *dify_web_image
    # ... official 1.14.0 service definition ...
  # db / redis / sandbox / plugin daemon / nginx / volumes: keep as required by upstream 1.14.0.
```

Record the source URL / commit / release tag used to seed this file in `docker/dify-pinned/README.md`. The implementation task is not complete until:

```bash
docker compose -f docker/dify-pinned/docker-compose.yml config >/dev/null
bash scripts/dify_up.sh
bash scripts/dify_down.sh
```

- [ ] **Step 4: Write `docker/dify-pinned/README.md`**

```markdown
# Pinned Dify

This directory contains the docker-compose definition for the **only** Dify version FDE claims compliance with at this point in time.

The pinned tag is `1.14.0`; image digests and the upstream compose source are recorded in `docs/decisions/0002-runtime-versions.md` after pull. Do not bump them without:
1. Updating the ADR.
2. Re-running the full conformance matrix on Dify (and re-running parity vs Hiagent).
3. Updating the per-minor-version Compiler module under `loom/runtimes/dify/v1_14/` or a new explicit version directory.

## Run

    bash scripts/dify_up.sh
    # Console: http://localhost:3000
    # API:     http://localhost:5001

    bash scripts/dify_down.sh
```

- [ ] **Step 5: Write `scripts/dify_up.sh`**

```bash
#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
docker compose -f docker/dify-pinned/docker-compose.yml up -d
echo "Waiting for Dify API…"
for i in {1..60}; do
  if curl -fsS http://localhost:5001/health >/dev/null 2>&1; then
    echo "Dify API up."
    exit 0
  fi
  sleep 2
done
echo "Dify API did not come up in time." >&2
exit 1
```

- [ ] **Step 6: Write `scripts/dify_down.sh`**

```bash
#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
docker compose -f docker/dify-pinned/docker-compose.yml down -v
```

- [ ] **Step 7: chmod and smoke**

```bash
cd "/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE"
chmod +x scripts/hiagent_up.sh scripts/hiagent_down.sh scripts/dify_up.sh scripts/dify_down.sh
# Dify is the Phase 0 engineering target:
bash scripts/dify_up.sh && bash scripts/dify_down.sh
# If a self-hosted Hiagent 2.6 artifact is available, also smoke:
#   bash scripts/hiagent_up.sh && bash scripts/hiagent_down.sh
```

- [ ] **Step 8: Commit**

```bash
git add docs/decisions/0002-runtime-versions.md docker/hiagent-pinned/ docker/dify-pinned/ scripts/hiagent_up.sh scripts/hiagent_down.sh scripts/dify_up.sh scripts/dify_down.sh
git commit -m "docs: ADR 0002 + pinned Hiagent 2.6 and Dify 1.14.0 runtime templates"
```

---

## Task 4: Decision record 0003 — Credential binding strategy

**Files:**
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/docs/decisions/0003-credential-binding.md`

PRD §5 credential binding. This replaces the previous central secret-manager choice blocker.

- [ ] **Step 1: Write the ADR**

```markdown
# ADR 0003 — Credential binding strategy

**Status:** Accepted
**Date:** YYYY-MM-DD

## Decision

1. LLM credentials are configured inside the target runtime platform. FDE-generated YAML / JSON / ZIP artifacts reference provider/model bindings but never include provider API keys. After import, the operator binds the workflow to the platform's configured LLM credential.
2. Non-LLM credentials are represented as HTTP-node auth bindings: handle, auth scheme, allowed host, header/query placement, and TLS requirement. Secret values are configured in the target platform or supplied during import/configuration; FDE does not store them.
3. Generated artifacts contain binding points and handles only. No secret values in IR, DSL, YAML, JSON, ZIP, logs, reports, or tests.

## Context

This matches the first-build deployment model: FDE produces importable artifacts and the target platform owns credential configuration. A dedicated central secret manager may be added later for enterprise deployment, but it is not a Phase 0 blocker.

## Consequences

- The registry records credential handles with auth binding metadata, not secret-value storage paths.
- Runtime adapters emit platform-specific credential binding slots.
- Tests assert generated artifacts contain no values that look like secrets.

## Alternatives considered

- **Dedicated central secret manager in v1**: stronger central governance, but heavier than the current import/configure workflow.
- **Inline secrets in generated artifacts**: rejected.
```

- [ ] **Step 2: Commit**

```bash
git add docs/decisions/0003-credential-binding.md
git commit -m "docs: ADR 0003 credential binding strategy"
```

---

## Task 5: Decision record 0004 — Reverse-compile default scope

**Files:**
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/docs/decisions/0004-reverse-compile-scope.md`

PRD §6 reverse compiler policy. This is now a default product decision, not an external senior-review blocker.

- [ ] **Step 1: Write the ADR**

```markdown
# ADR 0004 — Reverse-compile default scope

**Status:** Accepted
**Date:** YYYY-MM-DD

## Decision

The reverse compiler operates by the rules in PRD §6:

1. **Recognized constructs round-trip** under canonical IR equality (PRD §6).
2. **Unrecognized constructs hard-block** with an actionable error naming the offending runtime, node type, and parameter set.
3. **No silent IR extension.** New IR node types only via deliberate IR-version bumps.
4. **Hard-block remediation UX:**
   a. Surface the exact runtime node type + parameter set that triggered the block.
   b. One-click "revert to last known IR-clean draft."
   c. "Request IR extension" button → templated issue with the offending construct.
   d. Fast-path "use `code` escape hatch" wizard with I/O schemas pre-filled.

## My recommendation

Keep the first reverse compiler deliberately narrow:
- Accept parameter edits on nodes FDE emitted.
- Accept node additions only when the node type is in IR v0.3 and the adapter can prove canonical equality.
- Reject runtime-native nodes outside IR v0.3 instead of inferring new IR shape.

This protects the Git source of truth and avoids a large reverse-engineering project before product fit is proven.

## Consequences

- The Phase 1 narrow reverse compiler implements (1) for the deep-coverage archetypes only; (2) is a hard error.
- Phase 2A's full reverse compiler implements (1) for all v0.3 constructs and (2)–(4) end-to-end.
- The Phase 0 gate criterion "Reverse-compile spike on one archetype" (PRD §7) proves (1) is feasible before MVP code is written.
```

- [ ] **Step 2: Commit**

```bash
git add docs/decisions/0004-reverse-compile-scope.md
git commit -m "docs: ADR 0004 reverse-compile default scope"
```

---

## Task 6: Decision record 0005 — Agent governance

**Files:**
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/docs/decisions/0005-agent-governance.md`

PRD §5 agent budgets and LLM runtime defaults. This is a default product decision; operators can adjust after import.

- [ ] **Step 1: Write the ADR**

```markdown
# ADR 0005 — Agent governance defaults

**Status:** Accepted
**Date:** YYYY-MM-DD

## Decision

Workflow-level `policy.agent_budget` defaults (PRD §5):

| Field | Default | Per-node tighten allowed | Per-node loosen allowed |
|---|---|---|---|
| `max_iterations` | 10 | yes | no |
| `max_tokens` | 50000 | yes | no |
| `max_wall_clock_s` | 300 | yes | no |

LLM call defaults:

| Field | Default |
|---|---|
| `max_output_tokens` | 8000 |
| `temperature` | node-specific; default 0 for planning / validation-sensitive calls |

Runtime import behavior:
- FDE emits default settings into YAML / JSON / ZIP where the target runtime supports them.
- After import, the operator may adjust platform-side settings before publish.
- Any operator-side change is captured by reverse compile / drift detection before publish.

Tool side-effect policy:
- Tools with `side_effects: true` in the registry require an `idempotency_key` on every invocation.
- Side-effecting tool calls are audited to the trace store with `(tool, args, result, latency)` (PRD §5 agent contract).

## Context

The first build should not block on organization-specific budget policy. Use conservative defaults, import them, and let the operator adjust in the target platform.

## Consequences

- The Validator (Phase 1) rejects agents whose budget exceeds the workflow `policy.agent_budget`.
- The conformance matrix has a row for "agent budget exhaustion → fallback edge taken."
- Trace storage (Phase 2A) carries the audit fields above.
```

- [ ] **Step 2: Commit**

```bash
git add docs/decisions/0005-agent-governance.md
git commit -m "docs: ADR 0005 agent and LLM defaults"
```

---

## Task 7: IR v0.3 JSON Schema

**Files:**
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/schemas/ir-v0.3.schema.json`
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/loom/ir/__init__.py`
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/loom/ir/schema.py`
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/tests/ir/__init__.py`
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/tests/ir/test_v03_schema.py`

This task upgrades the existing v0.2 schema to v0.3 per PRD §5 changes. Diff vs v0.2:
- `ir_version` const becomes `"0.3"`.
- `metadata` adds required `rationale` (string, minLength 1).
- `metadata.owner` keeps minLength 1.
- `RegistryRef.registry_version` documented as immutable git SHA (still string but with regex `^sha:[0-9a-f]{7,40}$`).
- `AgentBudget` adds required `max_wall_clock_s` (integer, ≥ 1, ≤ 3600).
- All node types gain a required `rationale` string (minLength 1, ≤ 500).
- `TypeName` enum extended: keeps v0.2 entries; adds `null`. Compounds (`array<T>`, `object<...>`, `union<T1|T2>`) are expressed as strings whose grammar the Validator parses (the JSON Schema layer can't easily express this; the Validator owns it).
- `ParallelNode` gains optional `branch_types` (object) so the Validator can check declared types match branches per merge_strategy.
- `LoopNode` documents `${<id>.item}` and `${<id>.index}` exposure (Validator concern, schema-level just allows the strings).
- `ConditionNode` branches gain optional `narrows` (a tiny predicate-shape) so the Validator can apply branch narrowing rules.
- `Edge` gains optional `data` (boolean, default true) per PRD §5 "pure control edges."

- [ ] **Step 1: Write the failing tests first**

```python
# tests/ir/test_v03_schema.py
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

SCHEMAS = Path(__file__).resolve().parents[2] / "schemas"


def load_schema():
    return json.loads((SCHEMAS / "ir-v0.3.schema.json").read_text())


def test_schema_is_valid_jsonschema():
    schema = load_schema()
    Draft202012Validator.check_schema(schema)


def test_ir_version_is_const_0_3():
    schema = load_schema()
    assert schema["properties"]["ir_version"] == {"const": "0.3"}


def test_metadata_requires_rationale():
    schema = load_schema()
    md = schema["$defs"]["Metadata"]
    assert "rationale" in md["required"]
    assert md["properties"]["rationale"]["minLength"] >= 1


def test_registry_version_is_sha_pattern():
    schema = load_schema()
    rv = schema["$defs"]["RegistryRef"]["properties"]["registry_version"]
    assert rv["pattern"] == r"^sha:[0-9a-f]{7,40}$"


def test_agent_budget_requires_max_wall_clock_s():
    schema = load_schema()
    ab = schema["$defs"]["AgentBudget"]
    assert "max_wall_clock_s" in ab["required"]
    assert ab["properties"]["max_wall_clock_s"]["minimum"] == 1
    assert ab["properties"]["max_wall_clock_s"]["maximum"] == 3600


def test_every_node_requires_rationale():
    schema = load_schema()
    for node_def in [
        "TriggerNode", "LLMNode", "RetrievalNode", "HTTPNode", "CodeNode",
        "ConditionNode", "LoopNode", "ParallelNode", "AgentNode", "OutputNode",
    ]:
        n = schema["$defs"][node_def]
        assert "rationale" in n["required"], f"{node_def} missing rationale in required"
        assert n["properties"]["rationale"]["minLength"] >= 1


def test_typename_includes_null():
    schema = load_schema()
    assert "null" in schema["$defs"]["TypeName"]["enum"]


def test_edge_has_optional_data_flag():
    schema = load_schema()
    edge = schema["$defs"]["Edge"]
    assert "data" in edge["properties"]
    assert edge["properties"]["data"]["type"] == "boolean"
    assert edge["properties"]["data"]["default"] is True


def test_minimal_v03_doc_validates():
    schema = load_schema()
    doc = {
        "ir_version": "0.3",
        "metadata": {
            "name": "smoke",
            "owner": "ops",
            "rationale": "smoke test",
        },
        "registry_ref": {
            "registry_version": "sha:0000000",
            "tools": [], "datasets": [], "credentials": [],
        },
        "policy": {},
        "inputs": [],
        "outputs": [],
        "nodes": [
            {
                "id": "start",
                "type": "trigger",
                "mode": "manual",
                "rationale": "entry",
            },
            {
                "id": "out",
                "type": "output",
                "rationale": "terminal",
                "bindings": {"x": "${start.y}"},
            },
        ],
        "edges": [{"from": "start", "to": "out"}],
    }
    Draft202012Validator(schema).validate(doc)


def test_doc_without_rationale_rejected():
    schema = load_schema()
    doc = {
        "ir_version": "0.3",
        "metadata": {"name": "smoke", "owner": "ops"},
        "registry_ref": {"registry_version": "sha:0000000"},
        "policy": {},
        "inputs": [], "outputs": [],
        "nodes": [{"id": "start", "type": "trigger", "mode": "manual"}],
        "edges": [],
    }
    with pytest.raises(Exception):
        Draft202012Validator(schema).validate(doc)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd "/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE" && pytest tests/ir/test_v03_schema.py -v`
Expected: FAIL — schema file does not exist.

- [ ] **Step 3: Write the v0.3 schema**

Copy `schemas/ir-v0.2.schema.json` to `schemas/ir-v0.3.schema.json`, then apply the diff below. The full file is long; the diff is what changes. Keep all v0.2 fields/defs not listed below unchanged.

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://loom.example/schemas/ir-v0.3.schema.json",
  "title": "FDE IR v0.3",
  "description": "v0.3 — adds rationale (top-level + per-node), immutable SHA registry pin, max_wall_clock_s on agent budget, error outputs, branch narrowing hints, parallel branch_types, edge data-flag. See PRD.md §5 v0.2→v0.3 change log.",
  "type": "object",
  "required": ["ir_version", "metadata", "registry_ref", "policy", "inputs", "outputs", "nodes", "edges"],
  "additionalProperties": false,
  "properties": {
    "ir_version": { "const": "0.3" },
    "metadata":     { "$ref": "#/$defs/Metadata" },
    "registry_ref": { "$ref": "#/$defs/RegistryRef" },
    "policy":       { "$ref": "#/$defs/Policy" },
    "inputs":  { "type": "array", "items": { "$ref": "#/$defs/PortDecl" } },
    "outputs": { "type": "array", "items": { "$ref": "#/$defs/PortDecl" } },
    "nodes":   { "type": "array", "minItems": 1, "items": { "$ref": "#/$defs/Node" } },
    "edges":   { "type": "array", "items": { "$ref": "#/$defs/Edge" } }
  },
  "$defs": {
    "Metadata": {
      "type": "object",
      "required": ["name", "owner", "rationale"],
      "additionalProperties": false,
      "properties": {
        "name":        { "type": "string", "minLength": 1 },
        "description": { "type": "string" },
        "owner":       { "type": "string", "minLength": 1 },
        "rationale":   { "type": "string", "minLength": 1, "maxLength": 1000 }
      }
    },
    "RegistryRef": {
      "type": "object",
      "required": ["registry_version"],
      "additionalProperties": false,
      "properties": {
        "registry_version": {
          "type": "string",
          "pattern": "^sha:[0-9a-f]{7,40}$",
          "description": "Immutable git SHA of the registry repo. Calendar tags forbidden in v0.3."
        },
        "tools":       { "type": "array", "items": { "type": "string" }, "uniqueItems": true, "default": [] },
        "datasets":    { "type": "array", "items": { "type": "string" }, "uniqueItems": true, "default": [] },
        "credentials": { "type": "array", "items": { "type": "string" }, "uniqueItems": true, "default": [] }
      }
    },
    "Policy": {
      "type": "object",
      "additionalProperties": false,
      "properties": {
        "default_timeout_s": { "type": "number", "exclusiveMinimum": 0 },
        "default_retry":     { "$ref": "#/$defs/Retry" },
        "agent_budget":      { "$ref": "#/$defs/AgentBudget" }
      }
    },
    "Retry": {
      "type": "object",
      "required": ["max_attempts"],
      "additionalProperties": false,
      "properties": {
        "max_attempts": { "type": "integer", "minimum": 1, "maximum": 10 },
        "backoff":      { "enum": ["none", "linear", "exponential"], "default": "exponential" },
        "retry_on":     { "type": "array", "items": { "enum": ["5xx", "4xx", "timeout", "network", "rate_limit"] }, "uniqueItems": true }
      }
    },
    "AgentBudget": {
      "type": "object",
      "required": ["max_iterations", "max_tokens", "max_wall_clock_s"],
      "additionalProperties": false,
      "properties": {
        "max_iterations":   { "type": "integer", "minimum": 1, "maximum": 50 },
        "max_tokens":       { "type": "integer", "minimum": 1000, "maximum": 200000 },
        "max_wall_clock_s": { "type": "integer", "minimum": 1, "maximum": 3600 }
      }
    },
    "PortDecl": {
      "type": "object",
      "required": ["name", "type"],
      "additionalProperties": false,
      "properties": {
        "name":        { "type": "string", "pattern": "^[a-zA-Z_][a-zA-Z0-9_]*$" },
        "type":        { "$ref": "#/$defs/TypeName" },
        "required":    { "type": "boolean", "default": false },
        "description": { "type": "string" }
      }
    },
    "TypeName": {
      "description": "v0.3 primitives + compounds. Compound types (array<T>, object<{...}>, union<T1|T2>) are expressed as strings; the Validator parses the grammar.",
      "enum": [
        "string", "number", "boolean", "null", "json",
        "string[]", "number[]", "json[]",
        "chunks", "file", "any"
      ]
    },
    "VarRef": { "type": "string" },
    "JSONSchemaLite": { "type": "object" },
    "NodeIdentifier": { "type": "string", "pattern": "^[a-zA-Z_][a-zA-Z0-9_]*$" },
    "Node": {
      "oneOf": [
        { "$ref": "#/$defs/TriggerNode" },
        { "$ref": "#/$defs/LLMNode" },
        { "$ref": "#/$defs/RetrievalNode" },
        { "$ref": "#/$defs/HTTPNode" },
        { "$ref": "#/$defs/CodeNode" },
        { "$ref": "#/$defs/ConditionNode" },
        { "$ref": "#/$defs/LoopNode" },
        { "$ref": "#/$defs/ParallelNode" },
        { "$ref": "#/$defs/AgentNode" },
        { "$ref": "#/$defs/OutputNode" }
      ]
    },
    "TriggerNode": {
      "type": "object",
      "required": ["id", "type", "mode", "rationale"],
      "additionalProperties": false,
      "properties": {
        "id":          { "$ref": "#/$defs/NodeIdentifier" },
        "type":        { "const": "trigger" },
        "rationale":   { "type": "string", "minLength": 1, "maxLength": 500 },
        "description": { "type": "string" },
        "mode":        { "enum": ["manual", "schedule", "webhook"] },
        "schedule":    { "type": "string" },
        "webhook":     {
          "type": "object",
          "additionalProperties": false,
          "properties": {
            "path":   { "type": "string" },
            "method": { "enum": ["POST", "GET", "PUT", "PATCH", "DELETE"] }
          }
        }
      },
      "allOf": [
        { "if": { "properties": { "mode": { "const": "schedule" } } }, "then": { "required": ["schedule"] } },
        { "if": { "properties": { "mode": { "const": "webhook"  } } }, "then": { "required": ["webhook"] } }
      ]
    },
    "LLMNode": {
      "type": "object",
      "required": ["id", "type", "model", "prompt", "rationale"],
      "additionalProperties": false,
      "properties": {
        "id":            { "$ref": "#/$defs/NodeIdentifier" },
        "type":          { "const": "llm" },
        "rationale":     { "type": "string", "minLength": 1, "maxLength": 500 },
        "description":   { "type": "string" },
        "model":         { "type": "string" },
        "prompt":        { "$ref": "#/$defs/VarRef" },
        "system_prompt": { "$ref": "#/$defs/VarRef" },
        "temperature":   { "type": "number", "minimum": 0, "maximum": 2 },
        "max_tokens":    { "type": "integer", "minimum": 1 },
        "output_schema": { "$ref": "#/$defs/JSONSchemaLite" },
        "timeout_s":     { "type": "number", "exclusiveMinimum": 0 },
        "retry":         { "$ref": "#/$defs/Retry" }
      }
    },
    "RetrievalNode": {
      "type": "object",
      "required": ["id", "type", "dataset", "query", "rationale"],
      "additionalProperties": false,
      "properties": {
        "id":          { "$ref": "#/$defs/NodeIdentifier" },
        "type":        { "const": "retrieval" },
        "rationale":   { "type": "string", "minLength": 1, "maxLength": 500 },
        "description": { "type": "string" },
        "dataset":     { "type": "string" },
        "query":       { "$ref": "#/$defs/VarRef" },
        "top_k":       { "type": "integer", "minimum": 1, "maximum": 100, "default": 5 },
        "rerank":      { "type": "boolean", "default": false },
        "timeout_s":   { "type": "number", "exclusiveMinimum": 0 },
        "retry":       { "$ref": "#/$defs/Retry" }
      }
    },
    "HTTPNode": {
      "type": "object",
      "required": ["id", "type", "method", "url", "rationale"],
      "additionalProperties": false,
      "properties": {
        "id":              { "$ref": "#/$defs/NodeIdentifier" },
        "type":            { "const": "http" },
        "rationale":       { "type": "string", "minLength": 1, "maxLength": 500 },
        "description":     { "type": "string" },
        "method":          { "enum": ["GET", "POST", "PUT", "PATCH", "DELETE"] },
        "url":             { "$ref": "#/$defs/VarRef" },
        "headers":         { "type": "object", "additionalProperties": { "$ref": "#/$defs/VarRef" } },
        "body":            {},
        "credential":      { "type": "string" },
        "timeout_s":       { "type": "number", "exclusiveMinimum": 0 },
        "retry":           { "$ref": "#/$defs/Retry" },
        "idempotency_key": { "$ref": "#/$defs/VarRef" }
      },
      "allOf": [
        {
          "if": { "properties": { "method": { "enum": ["POST", "PUT", "PATCH", "DELETE"] } } },
          "then": { "required": ["idempotency_key"] }
        }
      ]
    },
    "CodeNode": {
      "type": "object",
      "required": ["id", "type", "language", "source", "rationale"],
      "additionalProperties": false,
      "properties": {
        "id":              { "$ref": "#/$defs/NodeIdentifier" },
        "type":            { "const": "code" },
        "rationale":       { "type": "string", "minLength": 1, "maxLength": 500 },
        "description":     { "type": "string" },
        "language":        { "enum": ["python", "javascript"] },
        "source":          { "type": "string" },
        "inputs":          { "type": "object", "additionalProperties": { "$ref": "#/$defs/VarRef" } },
        "output_schema":   { "$ref": "#/$defs/JSONSchemaLite" },
        "timeout_s":       { "type": "number", "exclusiveMinimum": 0 },
        "retry":           { "$ref": "#/$defs/Retry" },
        "idempotency_key": { "$ref": "#/$defs/VarRef" }
      }
    },
    "ConditionNode": {
      "type": "object",
      "required": ["id", "type", "branches", "rationale"],
      "additionalProperties": false,
      "properties": {
        "id":          { "$ref": "#/$defs/NodeIdentifier" },
        "type":        { "const": "condition" },
        "rationale":   { "type": "string", "minLength": 1, "maxLength": 500 },
        "description": { "type": "string" },
        "branches": {
          "type": "array",
          "minItems": 1,
          "items": {
            "type": "object",
            "required": ["when", "next"],
            "additionalProperties": false,
            "properties": {
              "when":    { "type": "string" },
              "next":    { "$ref": "#/$defs/NodeIdentifier" },
              "narrows": {
                "type": "object",
                "additionalProperties": false,
                "properties": {
                  "var":    { "type": "string" },
                  "to_type": { "$ref": "#/$defs/TypeName" }
                }
              }
            }
          }
        },
        "default": { "$ref": "#/$defs/NodeIdentifier" }
      }
    },
    "LoopNode": {
      "type": "object",
      "required": ["id", "type", "over", "as", "body", "max_iterations", "rationale"],
      "additionalProperties": false,
      "properties": {
        "id":             { "$ref": "#/$defs/NodeIdentifier" },
        "type":           { "const": "loop" },
        "rationale":      { "type": "string", "minLength": 1, "maxLength": 500 },
        "description":    { "type": "string" },
        "over":           { "$ref": "#/$defs/VarRef" },
        "as":             { "type": "string", "pattern": "^[a-zA-Z_][a-zA-Z0-9_]*$" },
        "body":           { "type": "array", "minItems": 1, "items": { "$ref": "#/$defs/Node" } },
        "max_iterations": { "type": "integer", "minimum": 1, "maximum": 1000 },
        "collect":        { "$ref": "#/$defs/VarRef" },
        "timeout_s":      { "type": "number", "exclusiveMinimum": 0 }
      }
    },
    "ParallelNode": {
      "type": "object",
      "required": ["id", "type", "branches", "merge_strategy", "rationale"],
      "additionalProperties": false,
      "properties": {
        "id":             { "$ref": "#/$defs/NodeIdentifier" },
        "type":           { "const": "parallel" },
        "rationale":      { "type": "string", "minLength": 1, "maxLength": 500 },
        "description":    { "type": "string" },
        "branches": {
          "type": "object",
          "minProperties": 2,
          "additionalProperties": { "type": "array", "minItems": 1, "items": { "$ref": "#/$defs/Node" } }
        },
        "merge_strategy": { "enum": ["concat", "object_merge", "first_success"] },
        "branch_types":   { "type": "object", "additionalProperties": { "$ref": "#/$defs/TypeName" } },
        "timeout_s":      { "type": "number", "exclusiveMinimum": 0 }
      }
    },
    "AgentNode": {
      "type": "object",
      "required": ["id", "type", "model", "tools", "input_schema", "output_schema", "budget", "on_budget_exhausted", "rationale"],
      "additionalProperties": false,
      "properties": {
        "id":                 { "$ref": "#/$defs/NodeIdentifier" },
        "type":               { "const": "agent" },
        "rationale":          { "type": "string", "minLength": 1, "maxLength": 500 },
        "description":        { "type": "string" },
        "model":              { "type": "string" },
        "tools":              { "type": "array", "minItems": 1, "uniqueItems": true, "items": { "type": "string" } },
        "input_schema":       { "$ref": "#/$defs/JSONSchemaLite" },
        "output_schema":      { "$ref": "#/$defs/JSONSchemaLite" },
        "inputs":             { "type": "object", "additionalProperties": { "$ref": "#/$defs/VarRef" } },
        "system_prompt":      { "$ref": "#/$defs/VarRef" },
        "budget":             { "$ref": "#/$defs/AgentBudget" },
        "on_budget_exhausted": { "enum": ["fallback", "fail", "return_partial"] },
        "fallback_edge":      { "$ref": "#/$defs/NodeIdentifier" },
        "timeout_s":          { "type": "number", "exclusiveMinimum": 0 }
      },
      "allOf": [
        {
          "if":   { "properties": { "on_budget_exhausted": { "const": "fallback" } } },
          "then": { "required": ["fallback_edge"] }
        }
      ]
    },
    "OutputNode": {
      "type": "object",
      "required": ["id", "type", "bindings", "rationale"],
      "additionalProperties": false,
      "properties": {
        "id":          { "$ref": "#/$defs/NodeIdentifier" },
        "type":        { "const": "output" },
        "rationale":   { "type": "string", "minLength": 1, "maxLength": 500 },
        "description": { "type": "string" },
        "bindings":    { "type": "object", "minProperties": 1, "additionalProperties": { "$ref": "#/$defs/VarRef" } }
      }
    },
    "Edge": {
      "type": "object",
      "required": ["from", "to"],
      "additionalProperties": false,
      "properties": {
        "from": { "$ref": "#/$defs/NodeIdentifier" },
        "to":   { "$ref": "#/$defs/NodeIdentifier" },
        "when": { "type": "string" },
        "data": { "type": "boolean", "default": true }
      }
    }
  }
}
```

- [ ] **Step 4: Write `loom/ir/__init__.py`**

```python
"""FDE IR — schema and Pydantic models."""
```

- [ ] **Step 5: Write `loom/ir/schema.py`**

```python
"""Load and validate IR documents against the v0.3 JSON Schema."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

_SCHEMAS = Path(__file__).resolve().parents[2] / "schemas"
_CURRENT = "0.3"


@lru_cache(maxsize=None)
def load_schema(version: str = _CURRENT) -> dict[str, Any]:
    path = _SCHEMAS / f"ir-v{version}.schema.json"
    return json.loads(path.read_text())


@lru_cache(maxsize=None)
def _validator(version: str = _CURRENT) -> Draft202012Validator:
    return Draft202012Validator(load_schema(version))


def validate(doc: dict[str, Any], version: str = _CURRENT) -> None:
    """Raise jsonschema.ValidationError on schema violation."""
    _validator(version).validate(doc)


def is_valid(doc: dict[str, Any], version: str = _CURRENT) -> bool:
    return _validator(version).is_valid(doc)
```

- [ ] **Step 6: Write `tests/ir/__init__.py`** (empty)

- [ ] **Step 7: Run tests to verify they pass**

Run: `cd "/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE" && pytest tests/ir/test_v03_schema.py -v`
Expected: 9/9 PASS.

- [ ] **Step 8: Commit**

```bash
git add schemas/ir-v0.3.schema.json loom/ir/ tests/ir/
git commit -m "feat(ir): add v0.3 schema (rationale, immutable SHA pin, agent wall-clock)"
```

---

## Task 8: Hand-author the five archetype IRs in v0.3

**Files:**
- Rename + rewrite: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/examples/ir/01-rag-qa.json` → `01-ecommerce-customer-faq.json` (rewrite to v0.3, ecommerce-themed; replaces previous TCM-KB-QA placeholder per PRD §1 ecommerce-primary wedge)
- Rename + rewrite: existing placeholder `02-document-audit.json` → `02-tcm-intake-triage.json` (shadow)
- Rename + rewrite: existing placeholder `03-etl-summarize.json` → `03-clinic-ops-summary.json` (shadow)
- Rename + rewrite: existing placeholder `04-multi-step-research.json` → `04-tcm-followup.json` (shadow)
- Rename + rewrite: existing placeholder `05-triage-routing.json` → `05-ecommerce-order-exception.json`
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/tests/archetypes/__init__.py`
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/tests/archetypes/test_archetype_validates.py`

The existing five archetype JSONs are PRD-§3 placeholders in v0.2. This task does two things: (a) rewrite them to v0.3 (add `rationale` everywhere, change `registry_version` to `sha:` form, add `max_wall_clock_s` to any agent budget), (b) derive the Phase 0 examples from ADR 0001's SOW / requirements intake. If a real partner SOW is unavailable, use the synthetic cross-border ecommerce SOW and keep placeholders as portability checks.

- [ ] **Step 1: Write the validation test first**

```python
# tests/archetypes/test_archetype_validates.py
import json
from pathlib import Path

import pytest

from loom.ir.schema import validate

ROOT = Path(__file__).resolve().parents[2]
PLACEHOLDER_DIR = ROOT / "examples" / "ir"
SOW_DIR = ROOT / "examples" / "ir" / "sow"


def _archetypes(d: Path) -> list[Path]:
    if not d.exists():
        return []
    return sorted(p for p in d.glob("*.json") if p.is_file())


@pytest.mark.parametrize("path", _archetypes(PLACEHOLDER_DIR), ids=lambda p: p.name)
def test_placeholder_archetype_validates(path: Path):
    doc = json.loads(path.read_text())
    validate(doc)


@pytest.mark.parametrize("path", _archetypes(SOW_DIR), ids=lambda p: p.name)
def test_sow_archetype_validates(path: Path):
    doc = json.loads(path.read_text())
    validate(doc)


def test_archetype_node_count_within_25(tmp_path):
    """PRD §7 Phase 0 gate: each archetype ≤25 nodes."""
    for p in _archetypes(SOW_DIR) or _archetypes(PLACEHOLDER_DIR):
        doc = json.loads(p.read_text())
        n = _count_nodes(doc["nodes"])
        assert n <= 25, f"{p.name} has {n} nodes (limit 25)"


def _count_nodes(nodes):
    total = 0
    for n in nodes:
        total += 1
        if n["type"] == "loop":
            total += _count_nodes(n["body"])
        elif n["type"] == "parallel":
            for branch in n["branches"].values():
                total += _count_nodes(branch)
    return total
```

- [ ] **Step 2: Run test — expect failures**

Run: `cd "/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE" && pytest tests/archetypes/ -v`
Expected: failures on each placeholder file (still v0.2 — missing `rationale`, calendar-tag `registry_version`, missing `max_wall_clock_s`).

- [ ] **Step 3: Rewrite `examples/ir/01-ecommerce-customer-faq.json` to v0.3**

```json
{
  "ir_version": "0.3",
  "metadata": {
    "name": "Ecommerce Customer FAQ",
    "description": "Multilingual buyer-question Q&A from product/policy KB with citations and low-confidence escalation.",
    "owner": "ecommerce-ops",
    "rationale": "Baseline ecommerce knowledge-base archetype. Exercises trigger / retrieval / llm / output and llm.output_schema. Default deep-coverage #1 for Phase 1 per PRD §1 (ecommerce-primary wedge)."
  },
  "registry_ref": {
    "registry_version": "sha:0000000",
    "tools": ["translate"],
    "datasets": ["product_kb", "policy_kb"],
    "credentials": []
  },
  "policy": {
    "default_timeout_s": 60,
    "default_retry": { "max_attempts": 3, "backoff": "exponential", "retry_on": ["5xx", "timeout", "rate_limit"] },
    "agent_budget": { "max_iterations": 10, "max_tokens": 50000, "max_wall_clock_s": 300 }
  },
  "inputs":  [{ "name": "query", "type": "string", "required": true }, { "name": "buyer_locale", "type": "string", "required": false }],
  "outputs": [{ "name": "answer", "type": "string" }, { "name": "sources", "type": "string[]" }, { "name": "confidence", "type": "number" }],
  "nodes": [
    { "id": "start", "type": "trigger", "mode": "manual", "rationale": "Manual entry; this archetype is interactive — invoked per buyer message." },
    { "id": "retrieve", "type": "retrieval", "rationale": "Pull top-K candidate passages from the merged product + policy KB before LLM ranking.",
      "dataset": "product_kb", "query": "${input.query}", "top_k": 20 },
    { "id": "rerank", "type": "llm", "rationale": "Cheap re-rank pass to narrow 20 → 5; reduces tokens for the answer step and lets us threshold confidence.",
      "model": "configured-small-model",
      "system_prompt": "You re-rank candidate passages by relevance to the buyer query. Return only the indices and a confidence score.",
      "prompt": "Query: ${input.query}\n\nPassages:\n${retrieve.chunks}\n\nReturn JSON: top 5 passage indices and a 0.0–1.0 confidence score for whether the KB can answer this query.",
      "temperature": 0,
      "output_schema": {
        "type": "object", "required": ["top_indices", "confidence"],
        "properties": {
          "top_indices": { "type": "array", "items": { "type": "integer" }, "minItems": 1, "maxItems": 5 },
          "confidence": { "type": "number", "minimum": 0.0, "maximum": 1.0 }
        }
      }
    },
    { "id": "answer", "type": "llm", "rationale": "Final answer in the buyer's locale, with citations by source index. No compensation promises beyond stated policy.",
      "model": "configured-planner-model",
      "system_prompt": "Answer the buyer's query using only the provided KB context. Cite by source index. Do not promise specific refund/compensation amounts beyond policy. Reply in buyer_locale if provided, else infer from query.",
      "prompt": "Query: ${input.query}\nLocale: ${input.buyer_locale}\nTop passage indices: ${rerank.top_indices}\nFull retrieval: ${retrieve.chunks}\n\nProduce a JSON answer.",
      "temperature": 0.2,
      "output_schema": {
        "type": "object", "required": ["answer", "sources"],
        "properties": { "answer": { "type": "string" }, "sources": { "type": "array", "items": { "type": "string" } } }
      }
    },
    { "id": "out", "type": "output", "rationale": "Bind workflow outputs; confidence is the raw rerank score (0.0–1.0). The boolean needs_escalation is derived from a condition node introduced in Phase 1.5 once the SOW/operator-configured threshold is locked.",
      "bindings": { "answer": "${answer.answer}", "sources": "${answer.sources}", "confidence": "${rerank.confidence}" } }
  ],
  "edges": [
    { "from": "start", "to": "retrieve" },
    { "from": "retrieve", "to": "rerank" },
    { "from": "rerank", "to": "answer" },
    { "from": "answer", "to": "out" }
  ]
}
```

> The placeholder exposes the raw `confidence` (number 0.0–1.0). Phase 1.5 introduces a `condition` node that compares against the SOW/operator-configured threshold and adds a typed `needs_escalation: boolean` output downstream. Splitting the work this way keeps the Phase 0 reverse-compile spike target as small as possible — type-clean against the v0.3 schema (no boolean ← number coercion) and structurally identical to the Phase 1 production compile output.

- [ ] **Step 4: Rewrite the other four archetypes to v0.3**

Apply the same pattern to `02-tcm-intake-triage.json` (shadow), `03-clinic-ops-summary.json` (shadow), `04-tcm-followup.json` (shadow), `05-ecommerce-order-exception.json` (deep-coverage #2):
- Change `"ir_version": "0.2"` → `"0.3"`.
- Change `"registry_version": "<calendar tag>"` → `"sha:0000000"` (placeholder; real SHA fills in once registry is committed).
- Add `"rationale"` to `metadata` (1–2 sentences explaining why this archetype exists).
- Add `"max_wall_clock_s": 300` to `policy.agent_budget`.
- Add `"rationale"` to every node (1 sentence, ≤500 chars).
- For agent nodes: ensure `budget.max_wall_clock_s` is present.

If any of the existing placeholder files exceeds 25 nodes (Phase 0 gate), simplify it. If any uses a node type outside the v0.3 ten-type list, that is a Phase 0 gate failure — surface it for an IR-version review, not a silent extension.

- [ ] **Step 5: Run tests**

Run: `cd "/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE" && pytest tests/archetypes/ -v`
Expected: all five `test_placeholder_archetype_validates[*]` PASS, `test_archetype_node_count_within_25` PASS. Partner-dir tests skip (dir empty).

- [ ] **Step 6: Commit**

```bash
git add examples/ir/ tests/archetypes/
git commit -m "feat(examples): rewrite five placeholder archetypes to IR v0.3"
```

- [ ] **Step 7: Author SOW-derived archetypes**

Create `examples/ir/sow/01-<name>.json` … `05-<name>.json` from the SOW. If a real partner SOW is not ready, use the synthetic ecommerce SOW. Run the same validation tests; commit with message `feat(examples): SOW archetypes <names> in IR v0.3`.

- [ ] **Step 8: Build shadow corpus**

Pick five workflows from a *different* team (or the public Dify template gallery). Hand-author them as v0.3 IR under `shadow-corpus/ir/`. Add the same parametrized test pointing at this directory. Mitigates the SOW-overfit risk (PRD §9).

```bash
mkdir -p shadow-corpus/ir
# Author 5 .json files following the v0.3 schema, named 01..05-<short-name>.json.
git add shadow-corpus/
git commit -m "feat(corpus): shadow corpus of 5 v0.3 IRs from independent source"
```

---

## Task 9: Pydantic v0.3 IR models

**Files:**
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/loom/ir/models.py`
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/tests/ir/test_models.py`

The Pydantic models give the rest of Phase 0 (and all of Phase 1) typed Python access to IR documents. The models mirror the JSON Schema 1:1 — anything the schema validates, the model accepts; anything the schema rejects, the model rejects.

- [ ] **Step 1: Write the failing test**

```python
# tests/ir/test_models.py
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from loom.ir.models import IRDocument

ROOT = Path(__file__).resolve().parents[2]


def test_load_ecommerce_faq_archetype_into_model():
    doc = json.loads((ROOT / "examples" / "ir" / "01-ecommerce-customer-faq.json").read_text())
    ir = IRDocument.model_validate(doc)
    assert ir.ir_version == "0.3"
    assert ir.metadata.rationale  # required in v0.3
    assert {n.id for n in ir.nodes} == {"start", "retrieve", "rerank", "answer", "out"}


def test_missing_rationale_rejected():
    doc = json.loads((ROOT / "examples" / "ir" / "01-ecommerce-customer-faq.json").read_text())
    del doc["metadata"]["rationale"]
    with pytest.raises(ValidationError):
        IRDocument.model_validate(doc)


def test_calendar_tag_registry_version_rejected():
    doc = json.loads((ROOT / "examples" / "ir" / "01-ecommerce-customer-faq.json").read_text())
    doc["registry_ref"]["registry_version"] = "2026-04-15"
    with pytest.raises(ValidationError):
        IRDocument.model_validate(doc)


def test_agent_budget_requires_wall_clock():
    doc = json.loads((ROOT / "examples" / "ir" / "01-ecommerce-customer-faq.json").read_text())
    del doc["policy"]["agent_budget"]["max_wall_clock_s"]
    with pytest.raises(ValidationError):
        IRDocument.model_validate(doc)
```

- [ ] **Step 2: Run test to verify failure**

Run: `cd "/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE" && pytest tests/ir/test_models.py -v`
Expected: ImportError on `loom.ir.models`.

- [ ] **Step 3: Write `loom/ir/models.py`**

```python
"""Pydantic v2 models for FDE IR v0.3.

These mirror schemas/ir-v0.3.schema.json. Any divergence is a bug; the
test_archetype_validates suite + test_models suite catch most cases.
"""
from __future__ import annotations

from typing import Annotated, Any, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

# ---- Primitives ----------------------------------------------------------

NodeId = Annotated[str, StringConstraints(pattern=r"^[a-zA-Z_][a-zA-Z0-9_]*$")]
Identifier = Annotated[str, StringConstraints(pattern=r"^[a-zA-Z_][a-zA-Z0-9_]*$")]
RegistrySha = Annotated[str, StringConstraints(pattern=r"^sha:[0-9a-f]{7,40}$")]
NonEmptyShort = Annotated[str, StringConstraints(min_length=1, max_length=500)]
NonEmptyLong = Annotated[str, StringConstraints(min_length=1, max_length=1000)]

VarRef = str  # Validator owns the syntax

TypeName = Literal[
    "string", "number", "boolean", "null", "json",
    "string[]", "number[]", "json[]",
    "chunks", "file", "any",
]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


# ---- Top-level pieces ---------------------------------------------------

class Metadata(_Strict):
    name: Annotated[str, StringConstraints(min_length=1)]
    description: str | None = None
    owner: Annotated[str, StringConstraints(min_length=1)]
    rationale: NonEmptyLong


class RegistryRef(_Strict):
    registry_version: RegistrySha
    tools: list[str] = Field(default_factory=list)
    datasets: list[str] = Field(default_factory=list)
    credentials: list[str] = Field(default_factory=list)


class Retry(_Strict):
    max_attempts: Annotated[int, Field(ge=1, le=10)]
    backoff: Literal["none", "linear", "exponential"] = "exponential"
    retry_on: list[Literal["5xx", "4xx", "timeout", "network", "rate_limit"]] | None = None


class AgentBudget(_Strict):
    max_iterations: Annotated[int, Field(ge=1, le=50)]
    max_tokens: Annotated[int, Field(ge=1000, le=200000)]
    max_wall_clock_s: Annotated[int, Field(ge=1, le=3600)]


class Policy(_Strict):
    default_timeout_s: Annotated[float, Field(gt=0)] | None = None
    default_retry: Retry | None = None
    agent_budget: AgentBudget | None = None


class PortDecl(_Strict):
    name: Identifier
    type: TypeName
    required: bool = False
    description: str | None = None


# ---- Nodes --------------------------------------------------------------

class _NodeBase(_Strict):
    id: NodeId
    rationale: NonEmptyShort
    description: str | None = None


class TriggerWebhook(_Strict):
    path: str | None = None
    method: Literal["POST", "GET", "PUT", "PATCH", "DELETE"] | None = None


class TriggerNode(_NodeBase):
    type: Literal["trigger"]
    mode: Literal["manual", "schedule", "webhook"]
    schedule: str | None = None
    webhook: TriggerWebhook | None = None


class LLMNode(_NodeBase):
    type: Literal["llm"]
    model: str
    prompt: VarRef
    system_prompt: VarRef | None = None
    temperature: Annotated[float, Field(ge=0, le=2)] | None = None
    max_tokens: Annotated[int, Field(ge=1)] | None = None
    output_schema: dict[str, Any] | None = None
    timeout_s: Annotated[float, Field(gt=0)] | None = None
    retry: Retry | None = None


class RetrievalNode(_NodeBase):
    type: Literal["retrieval"]
    dataset: str
    query: VarRef
    top_k: Annotated[int, Field(ge=1, le=100)] = 5
    rerank: bool = False
    timeout_s: Annotated[float, Field(gt=0)] | None = None
    retry: Retry | None = None


class HTTPNode(_NodeBase):
    type: Literal["http"]
    method: Literal["GET", "POST", "PUT", "PATCH", "DELETE"]
    url: VarRef
    headers: dict[str, VarRef] | None = None
    body: Any = None
    credential: str | None = None
    timeout_s: Annotated[float, Field(gt=0)] | None = None
    retry: Retry | None = None
    idempotency_key: VarRef | None = None


class CodeNode(_NodeBase):
    type: Literal["code"]
    language: Literal["python", "javascript"]
    source: str
    inputs: dict[str, VarRef] | None = None
    output_schema: dict[str, Any] | None = None
    timeout_s: Annotated[float, Field(gt=0)] | None = None
    retry: Retry | None = None
    idempotency_key: VarRef | None = None


class ConditionBranchNarrowing(_Strict):
    var: str
    to_type: TypeName


class ConditionBranch(_Strict):
    when: str
    next: NodeId
    narrows: ConditionBranchNarrowing | None = None


class ConditionNode(_NodeBase):
    type: Literal["condition"]
    branches: Annotated[list[ConditionBranch], Field(min_length=1)]
    default: NodeId | None = None


class LoopNode(_NodeBase):
    type: Literal["loop"]
    over: VarRef
    as_: Annotated[str, StringConstraints(pattern=r"^[a-zA-Z_][a-zA-Z0-9_]*$")] = Field(alias="as")
    body: list["AnyNode"]
    max_iterations: Annotated[int, Field(ge=1, le=1000)]
    collect: VarRef | None = None
    timeout_s: Annotated[float, Field(gt=0)] | None = None


class ParallelNode(_NodeBase):
    type: Literal["parallel"]
    branches: dict[str, list["AnyNode"]]
    merge_strategy: Literal["concat", "object_merge", "first_success"]
    branch_types: dict[str, TypeName] | None = None
    timeout_s: Annotated[float, Field(gt=0)] | None = None


class AgentNode(_NodeBase):
    type: Literal["agent"]
    model: str
    tools: Annotated[list[str], Field(min_length=1)]
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    inputs: dict[str, VarRef] | None = None
    system_prompt: VarRef | None = None
    budget: AgentBudget
    on_budget_exhausted: Literal["fallback", "fail", "return_partial"]
    fallback_edge: NodeId | None = None
    timeout_s: Annotated[float, Field(gt=0)] | None = None


class OutputNode(_NodeBase):
    type: Literal["output"]
    bindings: Annotated[dict[str, VarRef], Field(min_length=1)]


AnyNode = Union[
    TriggerNode, LLMNode, RetrievalNode, HTTPNode, CodeNode,
    ConditionNode, LoopNode, ParallelNode, AgentNode, OutputNode,
]
LoopNode.model_rebuild()
ParallelNode.model_rebuild()


class Edge(_Strict):
    from_: NodeId = Field(alias="from")
    to: NodeId
    when: str | None = None
    data: bool = True


class IRDocument(_Strict):
    ir_version: Literal["0.3"]
    metadata: Metadata
    registry_ref: RegistryRef
    policy: Policy
    inputs: list[PortDecl]
    outputs: list[PortDecl]
    nodes: Annotated[list[AnyNode], Field(min_length=1)]
    edges: list[Edge]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd "/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE" && pytest tests/ir/test_models.py -v && mypy loom`
Expected: 4/4 PASS, mypy clean.

- [ ] **Step 5: Commit**

```bash
git add loom/ir/models.py tests/ir/test_models.py
git commit -m "feat(ir): pydantic v2 models for IR v0.3"
```

---

## Task 10: Canonical IR equality

**Files:**
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/loom/ir/canonicalize.py`
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/tests/ir/test_canonicalize_ir.py`

PRD §6: canonicalization is "a pure function in the FDE Compiler module" that runs the same way client-side, in CI, and inside the Deployer. Canonical form: keys sorted lexicographically; default-valued fields stripped; node IDs normalized to a stable hash of `(type, sorted_input_refs, position-in-topological-order)`; arrays whose semantics are order-independent (parallel branches) sorted by canonical node ID; `rationale` preserved verbatim.

- [ ] **Step 1: Write the failing test**

```python
# tests/ir/test_canonicalize_ir.py
import copy
import json
from pathlib import Path

from loom.ir.canonicalize import canonical_ir, canonical_ir_hash

ROOT = Path(__file__).resolve().parents[2]


def _ecommerce_faq():
    return json.loads((ROOT / "examples" / "ir" / "01-ecommerce-customer-faq.json").read_text())


def test_canonical_form_is_idempotent():
    doc = _ecommerce_faq()
    once = canonical_ir(doc)
    twice = canonical_ir(once)
    assert once == twice


def test_canonical_form_strips_default_data_flag_on_edges():
    doc = _ecommerce_faq()
    for e in doc["edges"]:
        e["data"] = True  # explicit default
    out = canonical_ir(doc)
    for e in out["edges"]:
        assert "data" not in e


def test_canonical_form_keys_are_sorted():
    out = canonical_ir(_ecommerce_faq())
    keys = list(out.keys())
    assert keys == sorted(keys)


def test_rationale_preserved_verbatim():
    doc = _ecommerce_faq()
    rationale = doc["nodes"][0]["rationale"]
    out = canonical_ir(doc)
    out_node = next(n for n in out["nodes"] if n["id"] == doc["nodes"][0]["id"])
    assert out_node["rationale"] == rationale


def test_parallel_branches_sorted_by_canonical_id():
    """Order-independent compounds get sorted in canonical form."""
    # Construct a minimal IR with parallel and assert branches dict comes out sorted.
    doc = {
        "ir_version": "0.3",
        "metadata": {"name": "p", "owner": "o", "rationale": "p"},
        "registry_ref": {"registry_version": "sha:0000000",
                          "tools": [], "datasets": [], "credentials": []},
        "policy": {},
        "inputs": [], "outputs": [],
        "nodes": [
            {"id": "start", "type": "trigger", "mode": "manual", "rationale": "r"},
            {
                "id": "p", "type": "parallel", "rationale": "fan-out",
                "branches": {
                    "z": [{"id": "z1", "type": "code", "rationale": "r",
                            "language": "python", "source": "pass"}],
                    "a": [{"id": "a1", "type": "code", "rationale": "r",
                            "language": "python", "source": "pass"}],
                },
                "merge_strategy": "concat",
            },
            {"id": "out", "type": "output", "rationale": "r",
             "bindings": {"x": "${start.y}"}},
        ],
        "edges": [{"from": "start", "to": "p"}, {"from": "p", "to": "out"}],
    }
    out = canonical_ir(doc)
    par = next(n for n in out["nodes"] if n["id"] == "p")
    assert list(par["branches"].keys()) == ["a", "z"]


def test_two_equivalent_irs_hash_equal():
    a = _ecommerce_faq()
    b = copy.deepcopy(a)
    # Add a default that should be stripped:
    for e in b["edges"]:
        e["data"] = True
    assert canonical_ir_hash(a) == canonical_ir_hash(b)


def test_semantic_difference_changes_hash():
    a = _ecommerce_faq()
    b = copy.deepcopy(a)
    b["nodes"][0]["rationale"] = "different rationale on purpose"
    assert canonical_ir_hash(a) != canonical_ir_hash(b)
```

- [ ] **Step 2: Run test to verify failure**

Run: `pytest tests/ir/test_canonicalize_ir.py -v`
Expected: ImportError.

- [ ] **Step 3: Write `loom/ir/canonicalize.py`**

```python
"""Canonical IR form. Pure function. Used by Compiler, Deployer, golden tests.

Canonicalization rules (PRD §6 v0.3):
 1. Keys sorted lexicographically at every level.
 2. Default-valued fields stripped.
 3. Order-independent compounds sorted by canonical id.
 4. `rationale` preserved verbatim.
"""
from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from typing import Any

# Default values that get stripped at canonicalization time. Keep this list in
# sync with the v0.3 schema's `default` declarations.
_DEFAULT_STRIPS: list[tuple[tuple[str, ...], Any]] = [
    (("Edge", "data"), True),
    (("RetrievalNode", "top_k"), 5),
    (("RetrievalNode", "rerank"), False),
    (("PortDecl", "required"), False),
    (("Retry", "backoff"), "exponential"),
]


def canonical_ir(doc: dict[str, Any]) -> dict[str, Any]:
    """Return the canonical form of an IR document."""
    return _canonicalize(deepcopy(doc), parent="IRDocument")


def canonical_ir_hash(doc: dict[str, Any]) -> str:
    """SHA-256 hex of the canonical IR's JSON serialization."""
    canon = canonical_ir(doc)
    payload = json.dumps(canon, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _canonicalize(value: Any, *, parent: str) -> Any:
    if isinstance(value, dict):
        # Strip defaults for this parent.
        for (kind, key), default in _DEFAULT_STRIPS:
            if kind == parent and value.get(key) == default:
                value.pop(key, None)
        # Special-case: parallel branches are order-independent.
        if parent == "ParallelNode" and "branches" in value:
            sorted_branches = {k: value["branches"][k] for k in sorted(value["branches"].keys())}
            value["branches"] = sorted_branches
        # Recurse with proper parent label.
        out: dict[str, Any] = {}
        for k in sorted(value.keys()):
            out[k] = _canonicalize(value[k], parent=_child_kind(parent, k, value[k]))
        return out
    if isinstance(value, list):
        return [_canonicalize(v, parent=parent) for v in value]
    return value


def _child_kind(parent: str, key: str, value: Any) -> str:
    """Return a canonical kind string for child dispatch.

    Exhaustively listed so default stripping stays predictable. Keep in sync
    with schemas/ir-v0.3.schema.json.
    """
    if parent == "IRDocument":
        return {
            "metadata": "Metadata",
            "registry_ref": "RegistryRef",
            "policy": "Policy",
            "inputs": "PortDecl",
            "outputs": "PortDecl",
            "nodes": "Node",
            "edges": "Edge",
        }.get(key, "any")
    if parent == "Node" or parent == "any":
        if isinstance(value, dict) and "type" in value:
            return _node_kind(value["type"])
        return "any"
    if parent == "LoopNode" and key == "body":
        return "Node"
    if parent == "ParallelNode" and key == "branches":
        return "any"  # branches are dict[str, list[Node]]; recurse keys then list-of-nodes
    if parent.endswith("Node") and key == "retry":
        return "Retry"
    if parent.endswith("Node") and key == "branches":
        return "ConditionBranch"
    if parent == "Policy" and key == "default_retry":
        return "Retry"
    if parent == "Policy" and key == "agent_budget":
        return "AgentBudget"
    return "any"


def _node_kind(node_type: str) -> str:
    return {
        "trigger": "TriggerNode", "llm": "LLMNode", "retrieval": "RetrievalNode",
        "http": "HTTPNode", "code": "CodeNode", "condition": "ConditionNode",
        "loop": "LoopNode", "parallel": "ParallelNode", "agent": "AgentNode",
        "output": "OutputNode",
    }.get(node_type, "any")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/ir/test_canonicalize_ir.py -v && mypy loom`
Expected: 7/7 PASS, mypy clean.

- [ ] **Step 5: Commit**

```bash
git add loom/ir/canonicalize.py tests/ir/test_canonicalize_ir.py
git commit -m "feat(ir): canonical IR form + content hash"
```

---

## Task 11: Dify HTTP client (thin)

**Files:**
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/loom/runtimes/__init__.py`
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/loom/runtimes/dify/__init__.py`
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/loom/runtimes/dify/v1_14/__init__.py`
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/loom/runtimes/dify/v1_14/client.py`
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/tests/dify/__init__.py`
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/tests/dify/test_client_smoke.py`

The thin client wraps the four Dify endpoints Phase 0 needs: import-DSL (create draft), export-DSL (fetch draft), publish, get app. Auth is API-key via header. The client lives in `loom/runtimes/dify/v1_14/` so Phase 1 can build the Dify compiler/reverse path without moving the Phase 0 integration code.

- [ ] **Step 1: Write the smoke test (network-gated)**

```python
# tests/dify/test_client_smoke.py
import os

import pytest

from loom.runtimes.dify.v1_14.client import DifyClient

LIVE = os.environ.get("LOOM_DIFY_LIVE") == "1"
pytestmark = pytest.mark.skipif(not LIVE, reason="set LOOM_DIFY_LIVE=1 to run against pinned Dify")


def test_health():
    c = DifyClient(base_url="http://localhost:5001", api_key=os.environ["LOOM_DIFY_KEY"])
    assert c.health() is True
```

- [ ] **Step 2: Write package init files**

```python
"""Runtime integrations."""
```

Create the same minimal `__init__.py` shape under `loom/runtimes/dify/` and `loom/runtimes/dify/v1_14/`.

- [ ] **Step 3: Write `loom/runtimes/dify/v1_14/client.py`**

```python
"""Thin Dify HTTP client used by the conformance harness and Phase 1+ Compiler.

Phase 0 only needs: health, import_dsl, export_dsl, publish, get_app.
We deliberately keep this small — the per-version Compiler module owns the
DSL emit logic; this module owns network only.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx


@dataclass(frozen=True)
class DifyApp:
    id: str
    name: str
    draft_id: str | None = None


class DifyClient:
    def __init__(self, *, base_url: str, api_key: str, timeout: float = 30.0):
        self._client = httpx.Client(
            base_url=base_url.rstrip("/"),
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=timeout,
        )

    def close(self) -> None:
        self._client.close()

    def health(self) -> bool:
        r = self._client.get("/health")
        return r.status_code == 200

    def import_dsl(self, *, name: str, dsl_yaml: str) -> DifyApp:
        r = self._client.post(
            "/console/api/apps/import",
            json={"mode": "yaml", "name": name, "yaml_content": dsl_yaml},
        )
        r.raise_for_status()
        body = r.json()
        return DifyApp(id=body["app_id"], name=name, draft_id=body.get("draft_id"))

    def export_dsl(self, *, app_id: str) -> str:
        r = self._client.get(f"/console/api/apps/{app_id}/export")
        r.raise_for_status()
        return r.json()["yaml_content"]

    def publish(self, *, app_id: str) -> None:
        r = self._client.post(f"/console/api/apps/{app_id}/publish")
        r.raise_for_status()

    def get_app(self, *, app_id: str) -> dict[str, Any]:
        r = self._client.get(f"/console/api/apps/{app_id}")
        r.raise_for_status()
        return r.json()
```

> **Note for the engineer:** the exact API payload shape must be verified against Dify 1.14.0. The values above are placeholders matching common Dify console-API conventions. The Phase 1 Compiler module owns precise DSL emission; this client only owns network calls that exist on the pinned version.

- [ ] **Step 4: Run smoke test (only if Dify is running)**

```bash
# Start the pinned Dify per Task 3:
bash scripts/dify_up.sh
LOOM_DIFY_LIVE=1 LOOM_DIFY_KEY=<key> pytest tests/dify/test_client_smoke.py -v
bash scripts/dify_down.sh
```

The smoke test stays skipped unless `LOOM_DIFY_LIVE=1`.

- [ ] **Step 5: Commit**

```bash
git add loom/runtimes/__init__.py loom/runtimes/dify/__init__.py loom/runtimes/dify/v1_14/__init__.py loom/runtimes/dify/v1_14/client.py tests/dify/
git commit -m "feat(dify): thin HTTP client (health, import, export, publish)"
```

---

## Task 12: Canonical Dify-AST hashing

**Files:**
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/loom/runtimes/dify/v1_14/ast.py`
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/tests/dify/test_canonicalize_dify_ast.py`

PRD §6 explicitly forbids hashing raw DSL bytes — Dify normalizes YAML on round-trip and would produce constant false drift. The canonical Dify AST is parse-tree-level: ignore whitespace, key order, and Dify-assigned defaults; preserve semantics. The function is owned by FDE and is the same one the reverse-compile golden tests use.

- [ ] **Step 1: Write the test**

```python
# tests/dify/test_canonicalize_dify_ast.py
import yaml

from loom.runtimes.dify.v1_14.ast import canonical_dify_ast, canonical_dify_ast_hash


def test_whitespace_and_key_order_invariant():
    a = """
    app:
      name: x
      mode: workflow
    workflow:
      nodes:
        - id: n1
          type: start
          data: {x: 1}
        - id: n2
          type: end
    """
    b = """
    app:
      mode: workflow
      name: x
    workflow:
      nodes:
        - id: n2
          type: end
        - id: n1
          type: start
          data: {x: 1}
    """
    assert canonical_dify_ast_hash(a) == canonical_dify_ast_hash(b)


def test_semantic_change_changes_hash():
    a = "app: {name: x, mode: workflow}\nworkflow: {nodes: [{id: n1, type: start}]}"
    b = "app: {name: x, mode: workflow}\nworkflow: {nodes: [{id: n1, type: end}]}"  # type changed
    assert canonical_dify_ast_hash(a) != canonical_dify_ast_hash(b)


def test_dify_assigned_defaults_stripped():
    """Fields the Dify import path silently injects don't change the hash."""
    plain = "app: {name: x, mode: workflow}\nworkflow: {nodes: []}"
    with_default = (
        "app: {name: x, mode: workflow, icon: '', description: ''}\n"
        "workflow: {nodes: [], graph: {nodes: [], edges: []}}"
    )
    assert canonical_dify_ast_hash(plain) == canonical_dify_ast_hash(with_default)
```

- [ ] **Step 2: Run to confirm fail**

Run: `pytest tests/dify/test_canonicalize_dify_ast.py -v`
Expected: ImportError.

- [ ] **Step 3: Write `loom/runtimes/dify/v1_14/ast.py`**

```python
"""Canonical Dify-AST hashing. PRD §6 — invariant under Dify import/export
normalization (whitespace, key order, default-stripping); changes only on
semantically meaningful edits.

The default-stripping list and the order-independent-compound list are
**owned by FDE** and **versioned with the IR schema**. When Dify changes its
import-path defaults, this module is the place we update. Update path:
1. Re-run scripts/round_trip_proof.py to confirm a new false-drift root cause.
2. Add the affected key/path here.
3. Bump CANONICAL_AST_VERSION.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

import yaml

CANONICAL_AST_VERSION = "1"

# Top-level paths whose value Dify silently sets on import. Stripped before
# hashing. Keep aligned with the pinned Dify version (ADR 0002).
_STRIP_DEFAULTS: list[tuple[str, Any]] = [
    ("app.icon", ""),
    ("app.description", ""),
    ("workflow.graph.nodes", []),
    ("workflow.graph.edges", []),
]

# Lists whose order is not semantically significant. Sorted before hashing.
_ORDER_INVARIANT_LISTS: list[str] = [
    "workflow.nodes",
    "workflow.edges",
]


def canonical_dify_ast(yaml_text: str) -> dict[str, Any]:
    """Parse Dify DSL YAML to a canonical Python dict."""
    raw = yaml.safe_load(yaml_text) or {}
    return _canon(raw, path="")


def canonical_dify_ast_hash(yaml_text: str) -> str:
    """SHA-256 of the canonical AST."""
    canon = canonical_dify_ast(yaml_text)
    payload = json.dumps(
        {"v": CANONICAL_AST_VERSION, "ast": canon},
        sort_keys=True, ensure_ascii=False, separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _canon(value: Any, *, path: str) -> Any:
    if isinstance(value, dict):
        # Strip defaults rooted here.
        for p, default in _STRIP_DEFAULTS:
            if _path_join(path, "") == "" and p.startswith(path):
                _strip_at(value, _suffix(p, path), default)
            elif p == path + "." + (path and "."):
                pass
        cleaned: dict[str, Any] = {}
        for k in sorted(value.keys()):
            child_path = _path_join(path, k)
            cleaned[k] = _canon(value[k], path=child_path)
        return cleaned
    if isinstance(value, list):
        rendered = [_canon(v, path=path) for v in value]
        if path in _ORDER_INVARIANT_LISTS:
            return sorted(
                rendered,
                key=lambda x: json.dumps(x, sort_keys=True, ensure_ascii=False),
            )
        return rendered
    return value


def _path_join(parent: str, child: str) -> str:
    return f"{parent}.{child}" if parent else child


def _suffix(full: str, prefix: str) -> str:
    if not prefix:
        return full
    return full[len(prefix) + 1:] if full.startswith(prefix + ".") else full


def _strip_at(node: dict[str, Any], rel_path: str, default: Any) -> None:
    parts = rel_path.split(".") if rel_path else []
    cur: Any = node
    for p in parts[:-1]:
        if not isinstance(cur, dict) or p not in cur:
            return
        cur = cur[p]
    if not parts:
        return
    last = parts[-1]
    if isinstance(cur, dict) and cur.get(last) == default:
        cur.pop(last, None)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/dify/test_canonicalize_dify_ast.py -v && mypy loom`
Expected: 3/3 PASS, mypy clean.

- [ ] **Step 5: Commit**

```bash
git add loom/runtimes/dify/v1_14/ast.py tests/dify/test_canonicalize_dify_ast.py
git commit -m "feat(dify): canonical AST + hash invariant under Dify normalizations"
```

---

## Task 13: Conformance matrix scaffold

**Files:**
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/loom/conformance/__init__.py`
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/loom/conformance/matrix.py`
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/loom/conformance/runner.py`
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/tests/conformance/__init__.py`
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/tests/conformance/test_runner_smoke.py`
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/.github/workflows/conformance.yml`

Phase 0's job here: **the matrix exists, with stubs for every PRD §5 cell.** Cells get filled in during Task 14 (the live baseline run). The runner is shaped so a row is "given this minimal IR, push to Dify, run with these inputs, assert this outcome."

- [ ] **Step 1: Write the smoke test**

```python
# tests/conformance/test_runner_smoke.py
from loom.conformance.matrix import MATRIX
from loom.conformance.runner import ConformanceCase


def test_matrix_covers_all_prd_cells():
    expected = {
        "loop_max_iterations",
        "parallel_concat",
        "parallel_object_merge",
        "parallel_first_success",
        "agent_budget_fallback",
        "agent_output_schema",
        "http_retry_on",
        "node_timeout",
        "http_idempotency",
        "condition_truthiness",
    }
    actual = {row.id for row in MATRIX}
    assert actual == expected


def test_every_row_has_runnable_case():
    for row in MATRIX:
        case = row.case_factory()
        assert isinstance(case, ConformanceCase)
        assert case.ir.metadata.name == row.id  # convention: name == row id
```

- [ ] **Step 2: Run — expect failure**

Run: `pytest tests/conformance/ -v`
Expected: ImportError.

- [ ] **Step 3: Write `loom/conformance/__init__.py`**

```python
"""Semantic conformance matrix. One row per PRD §5 IR construct."""
```

- [ ] **Step 4: Write `loom/conformance/runner.py`**

```python
"""Conformance runner.

A `ConformanceCase` is a self-contained test: take an IR doc, compile it (Phase 1
will inject the real compiler — for Phase 0 a stub `compile_ir` is used and most
cases skip until Phase 1 lands), push to Dify, run with given inputs, assert the
expected outcome.

For Phase 0, the runner exists so the matrix shape is fixed. The actual
end-to-end execution is wired up in Task 14 (baseline run) and Phase 1.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from loom.ir.models import IRDocument


@dataclass(frozen=True)
class ConformanceCase:
    """A single conformance test instance.

    `inputs`:  the inputs to pass when triggering the deployed Dify workflow.
    `expect`:  callable(run_result) -> None; raises on assertion failure.
    """
    ir: IRDocument
    inputs: dict[str, Any]
    expect: Callable[[dict[str, Any]], None]


@dataclass(frozen=True)
class MatrixRow:
    id: str  # stable id, e.g. "loop_max_iterations"
    description: str  # one-line PRD §5 cell
    case_factory: Callable[[], ConformanceCase]
```

- [ ] **Step 5: Write `loom/conformance/matrix.py`**

```python
"""Conformance matrix definitions — one row per PRD §5 cell.

Each row's `case_factory` builds a minimal IR exercising only that construct
plus the surrounding scaffolding (trigger + output). The expected outcome is
encoded as the `expect` callable.

Phase 0: factories return well-formed IR but the runner does not yet execute
end-to-end (no Compiler). Task 14 fills in the live execution; Phase 1 wires
the Compiler.
"""
from __future__ import annotations

from typing import Any

from loom.conformance.runner import ConformanceCase, MatrixRow
from loom.ir.models import (
    AgentBudget, AgentNode, ConditionBranch, ConditionNode, CodeNode, Edge,
    HTTPNode, IRDocument, LLMNode, LoopNode, Metadata, OutputNode, ParallelNode,
    Policy, PortDecl, RegistryRef, Retry, TriggerNode,
)

_REG = RegistryRef(registry_version="sha:0000000")


def _trigger(rationale: str = "manual entry") -> TriggerNode:
    return TriggerNode(id="start", type="trigger", mode="manual", rationale=rationale)


def _output(bindings: dict[str, str]) -> OutputNode:
    return OutputNode(id="out", type="output", bindings=bindings, rationale="terminal")


def _ir(name: str, nodes: list[Any], edges: list[Edge], inputs: list[PortDecl] | None = None,
        outputs: list[PortDecl] | None = None) -> IRDocument:
    return IRDocument(
        ir_version="0.3",
        metadata=Metadata(name=name, owner="loom-conformance",
                          rationale=f"Conformance row {name}"),
        registry_ref=_REG,
        policy=Policy(),
        inputs=inputs or [],
        outputs=outputs or [],
        nodes=nodes,
        edges=edges,
    )


# ---- Row factories ------------------------------------------------------

def case_loop_max_iterations() -> ConformanceCase:
    """Run a loop with N=20 input but max_iterations=5; expect bounded execution."""
    body_code = CodeNode(id="body", type="code", language="python", source="result = item",
                         inputs={"item": "${loop_main.item}"}, rationale="passthrough")
    loop = LoopNode(id="loop_main", type="loop", over="${input.items}", **{"as": "item"},
                    body=[body_code], max_iterations=5, rationale="bounded loop")
    out = _output({"count": "${loop_main.count}"})
    ir = _ir("loop_max_iterations",
             [_trigger(), loop, out],
             [Edge(**{"from": "start"}, to="loop_main"), Edge(**{"from": "loop_main"}, to="out")],
             inputs=[PortDecl(name="items", type="json[]", required=True)],
             outputs=[PortDecl(name="count", type="number")])

    def expect(result: dict[str, Any]) -> None:
        # PRD §5: "Test runs loop with N>bound input; expect bounded execution + structured truncation event"
        assert result["count"] == 5
        assert result.get("truncation_event") is not None

    return ConformanceCase(ir=ir, inputs={"items": list(range(20))}, expect=expect)


def case_parallel_concat() -> ConformanceCase:
    a = CodeNode(id="a", type="code", language="python", source="result = 1", rationale="branch a")
    b = CodeNode(id="b", type="code", language="python", source="result = 2", rationale="branch b")
    par = ParallelNode(id="p", type="parallel", branches={"a": [a], "b": [b]},
                        merge_strategy="concat", rationale="fan-out concat")
    out = _output({"items": "${p}"})
    ir = _ir("parallel_concat",
             [_trigger(), par, out],
             [Edge(**{"from": "start"}, to="p"), Edge(**{"from": "p"}, to="out")],
             outputs=[PortDecl(name="items", type="json[]")])

    def expect(result: dict[str, Any]) -> None:
        assert sorted(result["items"]) == [1, 2]

    return ConformanceCase(ir=ir, inputs={}, expect=expect)


def case_parallel_object_merge() -> ConformanceCase:
    a = CodeNode(id="a", type="code", language="python", source="result = {'x': 1}", rationale="x")
    b = CodeNode(id="b", type="code", language="python", source="result = {'y': 2}", rationale="y")
    par = ParallelNode(id="p", type="parallel", branches={"a": [a], "b": [b]},
                        merge_strategy="object_merge", rationale="fan-out merge")
    out = _output({"merged": "${p}"})
    ir = _ir("parallel_object_merge",
             [_trigger(), par, out],
             [Edge(**{"from": "start"}, to="p"), Edge(**{"from": "p"}, to="out")],
             outputs=[PortDecl(name="merged", type="json")])

    def expect(result: dict[str, Any]) -> None:
        assert result["merged"] == {"a": {"x": 1}, "b": {"y": 2}}

    return ConformanceCase(ir=ir, inputs={}, expect=expect)


def case_parallel_first_success() -> ConformanceCase:
    a = CodeNode(id="a", type="code", language="python", source="raise RuntimeError('fail')",
                 rationale="failing")
    b = CodeNode(id="b", type="code", language="python", source="result = 'b-wins'",
                 rationale="successful")
    par = ParallelNode(id="p", type="parallel", branches={"a": [a], "b": [b]},
                        merge_strategy="first_success", rationale="race")
    out = _output({"winner": "${p}"})
    ir = _ir("parallel_first_success",
             [_trigger(), par, out],
             [Edge(**{"from": "start"}, to="p"), Edge(**{"from": "p"}, to="out")],
             outputs=[PortDecl(name="winner", type="string")])

    def expect(result: dict[str, Any]) -> None:
        assert result["winner"] == "b-wins"

    return ConformanceCase(ir=ir, inputs={}, expect=expect)


def case_agent_budget_fallback() -> ConformanceCase:
    fallback = CodeNode(id="fb", type="code", language="python",
                        source="result = {'findings': 'fallback', 'sources': []}",
                        rationale="deterministic fallback")
    agent = AgentNode(
        id="ag", type="agent", model="configured-small-model",
        tools=["nop_tool"],
        input_schema={"type": "object"}, output_schema={"type": "object"},
        budget=AgentBudget(max_iterations=1, max_tokens=1000, max_wall_clock_s=5),
        on_budget_exhausted="fallback", fallback_edge="fb",
        rationale="bounded; force exhaustion",
    )
    out = _output({"findings": "${fb.findings}"})
    ir = _ir("agent_budget_fallback",
             [_trigger(), agent, fallback, out],
             [Edge(**{"from": "start"}, to="ag"),
              Edge(**{"from": "ag"}, to="fb"),
              Edge(**{"from": "fb"}, to="out")],
             outputs=[PortDecl(name="findings", type="string")])
    ir = ir.model_copy(update={"registry_ref": _REG.model_copy(update={"tools": ["nop_tool"]})})

    def expect(result: dict[str, Any]) -> None:
        assert result["findings"] == "fallback"

    return ConformanceCase(ir=ir, inputs={}, expect=expect)


def case_agent_output_schema() -> ConformanceCase:
    fallback = CodeNode(id="fb", type="code", language="python",
                        source="result = {'value': -1}", rationale="schema-violation fallback")
    agent = AgentNode(
        id="ag", type="agent", model="configured-small-model",
        tools=["nop_tool"],
        input_schema={"type": "object"},
        output_schema={"type": "object", "required": ["value"],
                       "properties": {"value": {"type": "integer"}}},
        budget=AgentBudget(max_iterations=2, max_tokens=2000, max_wall_clock_s=10),
        on_budget_exhausted="fallback", fallback_edge="fb",
        rationale="forces schema violation, expects fallback edge taken",
    )
    out = _output({"value": "${fb.value}"})
    ir = _ir("agent_output_schema",
             [_trigger(), agent, fallback, out],
             [Edge(**{"from": "start"}, to="ag"),
              Edge(**{"from": "ag"}, to="fb"),
              Edge(**{"from": "fb"}, to="out")],
             outputs=[PortDecl(name="value", type="number")])
    ir = ir.model_copy(update={"registry_ref": _REG.model_copy(update={"tools": ["nop_tool"]})})

    def expect(result: dict[str, Any]) -> None:
        assert result["value"] == -1  # fallback fired

    return ConformanceCase(ir=ir, inputs={}, expect=expect)


def case_http_retry_on() -> ConformanceCase:
    h = HTTPNode(
        id="h", type="http", method="POST", url="${input.url}",
        idempotency_key="${input.idem}",
        retry=Retry(max_attempts=3, retry_on=["5xx", "timeout"]),
        rationale="exercises retry classification",
    )
    out = _output({"status": "${h.status}"})
    ir = _ir("http_retry_on",
             [_trigger(), h, out],
             [Edge(**{"from": "start"}, to="h"), Edge(**{"from": "h"}, to="out")],
             inputs=[PortDecl(name="url", type="string", required=True),
                     PortDecl(name="idem", type="string", required=True)],
             outputs=[PortDecl(name="status", type="number")])

    def expect(result: dict[str, Any]) -> None:
        # Assertion details fill in once Task 14 sets up the fault-injection HTTP server.
        assert result["status"] in (200, 503)

    return ConformanceCase(
        ir=ir, inputs={"url": "http://faultinj.local/503-twice-then-200", "idem": "k1"},
        expect=expect,
    )


def case_node_timeout() -> ConformanceCase:
    slow = CodeNode(id="slow", type="code", language="python",
                    source="import time\ntime.sleep(10)\nresult = 'done'",
                    timeout_s=2, rationale="exceeds timeout")
    out = _output({"value": "${slow.error.code}"})
    ir = _ir("node_timeout",
             [_trigger(), slow, out],
             [Edge(**{"from": "start"}, to="slow"), Edge(**{"from": "slow"}, to="out")],
             outputs=[PortDecl(name="value", type="string")])

    def expect(result: dict[str, Any]) -> None:
        assert result["value"] == "TIMEOUT"

    return ConformanceCase(ir=ir, inputs={}, expect=expect)


def case_http_idempotency() -> ConformanceCase:
    h = HTTPNode(
        id="h", type="http", method="POST", url="${input.url}",
        idempotency_key="fixed-key-1", rationale="dedup proof",
    )
    out = _output({"calls": "${h.body.calls}"})
    ir = _ir("http_idempotency",
             [_trigger(), h, out],
             [Edge(**{"from": "start"}, to="h"), Edge(**{"from": "h"}, to="out")],
             inputs=[PortDecl(name="url", type="string", required=True)],
             outputs=[PortDecl(name="calls", type="number")])

    def expect(result: dict[str, Any]) -> None:
        # Two runs with same key → server records 1 effect.
        assert result["calls"] == 1

    return ConformanceCase(ir=ir, inputs={"url": "http://faultinj.local/count"}, expect=expect)


def case_condition_truthiness() -> ConformanceCase:
    truthy = CodeNode(id="t", type="code", language="python",
                      source="result = 'truthy'", rationale="truthy branch")
    falsy = CodeNode(id="f", type="code", language="python",
                     source="result = 'falsy'", rationale="falsy branch")
    cond = ConditionNode(id="c", type="condition", rationale="enumerate truthiness",
                          branches=[ConditionBranch(when="${input.x}", next="t")],
                          default="f")
    out = _output({"taken": "${input.expected}"})
    ir = _ir("condition_truthiness",
             [_trigger(), cond, truthy, falsy, out],
             [Edge(**{"from": "start"}, to="c"),
              Edge(**{"from": "c"}, to="t"),
              Edge(**{"from": "c"}, to="f"),
              Edge(**{"from": "t"}, to="out"),
              Edge(**{"from": "f"}, to="out")],
             inputs=[PortDecl(name="x", type="any", required=True),
                     PortDecl(name="expected", type="string", required=True)],
             outputs=[PortDecl(name="taken", type="string")])

    def expect(result: dict[str, Any]) -> None:
        # Runner parameterizes over a truthiness table — assertion is per-case.
        assert result["taken"] in {"truthy", "falsy"}

    return ConformanceCase(ir=ir, inputs={"x": 0, "expected": "falsy"}, expect=expect)


# ---- Matrix -------------------------------------------------------------

MATRIX: list[MatrixRow] = [
    MatrixRow("loop_max_iterations",   "loop bounded by max_iterations",                  case_loop_max_iterations),
    MatrixRow("parallel_concat",        "parallel + concat merge",                         case_parallel_concat),
    MatrixRow("parallel_object_merge",  "parallel + object_merge merge",                   case_parallel_object_merge),
    MatrixRow("parallel_first_success", "parallel + first_success merge",                  case_parallel_first_success),
    MatrixRow("agent_budget_fallback",  "agent budget exhaustion → fallback edge",         case_agent_budget_fallback),
    MatrixRow("agent_output_schema",    "agent output_schema enforcement → fallback",      case_agent_output_schema),
    MatrixRow("http_retry_on",          "http retry classes (5xx/timeout/non-retryable)",  case_http_retry_on),
    MatrixRow("node_timeout",           "node timeout_s hard-cuts",                        case_node_timeout),
    MatrixRow("http_idempotency",       "idempotency_key dedupes side-effect",             case_http_idempotency),
    MatrixRow("condition_truthiness",   "condition truthiness parity with Dify",           case_condition_truthiness),
]
```

- [ ] **Step 6: Write `tests/conformance/__init__.py`** (empty)

- [ ] **Step 7: Run smoke test**

Run: `pytest tests/conformance/ -v && mypy loom`
Expected: 2/2 PASS, mypy clean.

- [ ] **Step 8: Write `.github/workflows/conformance.yml` (template)**

```yaml
name: conformance
on:
  workflow_dispatch:
  schedule:
    - cron: "0 6 * * *"

jobs:
  matrix:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: pip install -e ".[dev]"
      - name: Start pinned Dify
        run: bash scripts/dify_up.sh
      - name: Run conformance matrix
        env:
          LOOM_DIFY_LIVE: "1"
          LOOM_DIFY_KEY: ${{ secrets.LOOM_DIFY_KEY }}
        run: pytest tests/conformance -v --tb=short
      - name: Stop Dify
        if: always()
        run: bash scripts/dify_down.sh
```

- [ ] **Step 9: Commit**

```bash
git add loom/conformance/ tests/conformance/ .github/workflows/conformance.yml
git commit -m "feat(conformance): matrix scaffold (one row per §5 cell, factories pending exec)"
```

---

## Task 14: Conformance baseline run + populate ADR 0002 cell table

**Files:**
- Modify: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/docs/decisions/0002-runtime-versions.md`
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/reports/conformance-baseline.md`

This task runs after ADR 0002 is written and pinned Dify 1.14.0 is running. For Phase 0, we use **hand-authored DSL** keyed off the conformance cases — Phase 1's Compiler will replace the hand-authoring. The point is to populate the Dify side of the §5 cell table in ADR 0002 and prove the matrix is executable end-to-end on the pinned Phase 0 engineering target.

- [ ] **Step 1: For each MATRIX row, hand-author the Dify DSL by hand**

Working off the matrix shapes in `loom/conformance/matrix.py`, hand-write a Dify YAML that implements the same semantics. Save to `examples/dify-conformance/<row.id>.yaml`. This is the least pleasant Phase 0 task; budget half a day per row.

- [ ] **Step 2: Push each DSL to pinned Dify and run with the case inputs**

Use `loom.runtimes.dify.v1_14.client.DifyClient.import_dsl(...)`, then trigger via Dify's run API (path is version-specific; consult ADR 0002). Record the result and call `case.expect(result)`.

- [ ] **Step 3: Fill in the cell table in `docs/decisions/0002-runtime-versions.md`**

Replace the `...` placeholders with concrete values:

| Cell | Native support | Wrapper needed | Notes |
|---|---|---|---|
| loop max_iterations | yes | none | iteration node honors bound, emits truncation event |
| parallel concat | yes | none | aggregator preserves order |
| parallel object_merge | partial | post-aggregator code node | native aggregator returns list-of-dicts; wrapper rekeys by branch name |
| ... | ... | ... | ... |

A "wrapper needed" cell tells the Phase 1 Compiler what extra emission shape to produce. A "no support" cell is a Phase 0 gate failure — FDE does not silently weaken; we raise it for an IR-version review or accept that this Dify version is the wrong target.

- [ ] **Step 4: Write `reports/conformance-baseline.md`**

```markdown
# Conformance baseline against Dify 1.14.0

Date: YYYY-MM-DD
Dify image: `langgenius/dify-api:1.14.0@sha256:<digest>`

## Matrix results

| Row | Pass | Notes |
|---|---|---|
| loop_max_iterations | yes/no | ... |
| parallel_concat | ... | ... |
| ... | ... | ... |

## Flake rate

- Runs: N (target ≥ 30)
- Flakes: M (definition: failed-then-passed without code change)
- Flake rate: M/N (target < 2 percent; > 5 percent blocks release per PRD §10)

## Action items

- For every "no" row, file an issue: <link>
- For every "wrapper needed" cell, update Phase 1 Compiler plan: <link>
```

- [ ] **Step 5: Commit**

```bash
git add docs/decisions/0002-runtime-versions.md reports/conformance-baseline.md examples/dify-conformance/
git commit -m "docs: conformance baseline against pinned Dify; populate cell table"
```

---

## Task 15: Round-trip canonicalization proof (N=10)

**Files:**
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/scripts/round_trip_proof.py`
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/reports/round-trip-proof.json`

PRD §7 Phase 0 gate: "Take a hand-authored IR, compile to DSL, push to Dify, pull back, run canonicalization (§6), confirm the canonical AST hash is stable across N=10 round-trips. False-drift rate must be 0."

For Phase 0 (no Compiler yet), substitute hand-authored DSL from Task 14 row 1 (`loop_max_iterations` is fine). The proof is about Dify normalization stability, not Compiler correctness.

- [ ] **Step 1: Write `scripts/round_trip_proof.py`**

```python
#!/usr/bin/env python3
"""Round-trip canonicalization proof — PRD §7 Phase 0 gate.

For a chosen DSL file:
  1. Push to pinned Dify (import_dsl) → app_id.
  2. Pull DSL back (export_dsl).
  3. Compute canonical_dify_ast_hash on the pulled DSL.
  4. Repeat N=10 times.
Assert all 10 hashes are identical. False-drift rate must be 0.

Usage:
  LOOM_DIFY_KEY=... python scripts/round_trip_proof.py \\
    --dsl examples/dify-conformance/loop_max_iterations.yaml \\
    --base-url http://localhost:5001 \\
    --runs 10 \\
    --report reports/round-trip-proof.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from loom.runtimes.dify.v1_14.ast import canonical_dify_ast_hash
from loom.runtimes.dify.v1_14.client import DifyClient


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--dsl", required=True)
    p.add_argument("--base-url", required=True)
    p.add_argument("--api-key", default=None, help="defaults to env LOOM_DIFY_KEY")
    p.add_argument("--runs", type=int, default=10)
    p.add_argument("--report", required=True)
    args = p.parse_args()

    import os
    api_key = args.api_key or os.environ["LOOM_DIFY_KEY"]
    yaml_in = Path(args.dsl).read_text()
    initial_hash = canonical_dify_ast_hash(yaml_in)

    client = DifyClient(base_url=args.base_url, api_key=api_key)
    hashes: list[str] = []
    apps: list[str] = []
    try:
        for i in range(args.runs):
            app = client.import_dsl(name=f"loom-rt-{i}", dsl_yaml=yaml_in)
            apps.append(app.id)
            yaml_back = client.export_dsl(app_id=app.id)
            hashes.append(canonical_dify_ast_hash(yaml_back))
    finally:
        client.close()

    unique = set(hashes)
    report = {
        "dsl": args.dsl,
        "runs": args.runs,
        "initial_hash": initial_hash,
        "round_trip_hashes": hashes,
        "unique_hash_count": len(unique),
        "false_drift_rate": (len(unique) - 1) / max(args.runs - 1, 1) if args.runs > 1 else 0,
    }
    Path(args.report).write_text(json.dumps(report, indent=2))

    if len(unique) != 1:
        print(f"FAIL: round-trip produced {len(unique)} distinct hashes; expected 1", file=sys.stderr)
        return 2
    if hashes[0] != initial_hash:
        print(f"FAIL: round-trip hash {hashes[0]} != initial hash {initial_hash}", file=sys.stderr)
        return 3
    print(f"PASS: {args.runs} round-trips, single canonical hash {hashes[0][:12]}…")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Make executable**

```bash
chmod +x scripts/round_trip_proof.py
```

- [ ] **Step 3: Run (only after pinned Dify 1.14.0 is up)**

```bash
bash scripts/dify_up.sh
LOOM_DIFY_KEY=<key> python scripts/round_trip_proof.py \
  --dsl examples/dify-conformance/loop_max_iterations.yaml \
  --base-url http://localhost:5001 \
  --runs 10 \
  --report reports/round-trip-proof.json
bash scripts/dify_down.sh
```

Expected: `PASS: 10 round-trips, single canonical hash …`. If FAIL, the canonicalization function in `loom/runtimes/dify/v1_14/ast.py` is undersized — likely a Dify-injected default we did not strip. Add the path to `_STRIP_DEFAULTS` and re-run. The Phase 0 gate cannot close until this returns PASS.

- [ ] **Step 4: Commit**

```bash
git add scripts/round_trip_proof.py reports/round-trip-proof.json
git commit -m "feat(scripts): N=10 round-trip canonicalization proof; report PASS"
```

---

## Task 16: Reverse-compile spike

**Files:**
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/scripts/reverse_compile_spike.py`
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/reports/reverse-compile-spike.md`

PRD §7 Phase 0 gate: "For at least one of the five archetypes, take the deployed Dify workflow, manually edit it (a node added/removed/parameter changed within the IR-recognized set), reverse-compile to IR, and confirm the resulting IR equals the manually-edited equivalent under canonical equality."

Phase 0 has no production reverse compiler. The spike is a hand-written, single-archetype reverse compiler scoped to *one* test case. Its purpose is to surface round-trip risk before Phase 1 commits.

- [ ] **Step 1: Pick the simplest archetype**

Ecommerce customer FAQ (`examples/ir/01-ecommerce-customer-faq.json`) is the simplest. Its Dify DSL exercises trigger / retrieval / llm / output — narrow enough to hand-write a reverse compiler.

- [ ] **Step 2: Write `scripts/reverse_compile_spike.py`**

```python
#!/usr/bin/env python3
"""Reverse-compile spike — PRD §7 Phase 0 gate, narrow to one archetype.

Steps:
  1. Load the deployed ecommerce-customer-faq Dify DSL (exported from Dify).
  2. Manually edit the YAML (e.g., change retrieve.top_k from 20 → 15).
  3. Run the spike reverse compiler: DSL → IR.
  4. Construct the same edit on the original IR.
  5. Compare via canonical_ir; assert equal.

This script is scoped to ecommerce-customer-faq only. The full reverse compiler in
Phase 2A covers all v0.3 constructs.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

from loom.ir.canonicalize import canonical_ir


def reverse_compile_ecommerce_faq(dify_yaml: str, registry_sha: str) -> dict:
    """Hand-written reverse compiler: ecommerce-customer-faq Dify DSL → IR v0.3 dict.

    Recognized only: trigger(manual), retrieval, llm (with output_schema), output.
    Anything else: raise NotImplementedError (PRD §6 hard-block policy).
    """
    src = yaml.safe_load(dify_yaml)
    nodes_in = src["workflow"]["nodes"]
    edges_in = src["workflow"]["edges"]

    out_nodes: list[dict] = []
    for n in nodes_in:
        t = n["type"]
        if t == "start":
            out_nodes.append({
                "id": n["id"], "type": "trigger", "mode": "manual",
                "rationale": n.get("data", {}).get("rationale", "Manual entry."),
            })
        elif t == "knowledge-retrieval":
            d = n["data"]
            out_nodes.append({
                "id": n["id"], "type": "retrieval",
                "rationale": d.get("rationale", "Retrieve from knowledge base."),
                "dataset": d["dataset_id"],
                "query": d["query"],
                "top_k": d.get("top_k", 5),
            })
        elif t == "llm":
            d = n["data"]
            out_nodes.append({
                "id": n["id"], "type": "llm",
                "rationale": d.get("rationale", "LLM call."),
                "model": d["model"]["name"],
                "system_prompt": d.get("system_prompt"),
                "prompt": d["prompt"],
                "temperature": d.get("temperature"),
                "output_schema": d.get("output_schema"),
            })
            # Strip Nones to keep canonical equality stable.
            out_nodes[-1] = {k: v for k, v in out_nodes[-1].items() if v is not None}
        elif t == "end":
            out_nodes.append({
                "id": n["id"], "type": "output",
                "rationale": n.get("data", {}).get("rationale", "Bind workflow outputs."),
                "bindings": n["data"]["bindings"],
            })
        else:
            raise NotImplementedError(
                f"Reverse-compile spike does not recognize node type {t!r}. "
                "PRD §6 hard-block: revert, request IR extension, or use code escape hatch."
            )

    return {
        "ir_version": "0.3",
        "metadata": src["app"].get("metadata", {"name": src["app"]["name"], "owner": "spike",
                                                  "rationale": "spike artifact"}),
        "registry_ref": {
            "registry_version": registry_sha,
            "tools": [], "datasets": [n["dataset"] for n in out_nodes if n["type"] == "retrieval"],
            "credentials": [],
        },
        "policy": src.get("policy", {}),
        "inputs": src.get("inputs", []),
        "outputs": src.get("outputs", []),
        "nodes": out_nodes,
        "edges": [{"from": e["from"], "to": e["to"]} for e in edges_in],
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--dify-yaml", required=True, help="manually edited Dify DSL")
    p.add_argument("--expected-ir", required=True, help="manually edited reference IR")
    p.add_argument("--registry-sha", required=True)
    args = p.parse_args()

    dify = Path(args.dify_yaml).read_text()
    expected = json.loads(Path(args.expected_ir).read_text())

    actual = reverse_compile_ecommerce_faq(dify, registry_sha=args.registry_sha)
    if canonical_ir(actual) != canonical_ir(expected):
        import difflib
        a = json.dumps(canonical_ir(actual), indent=2, sort_keys=True).splitlines()
        b = json.dumps(canonical_ir(expected), indent=2, sort_keys=True).splitlines()
        sys.stderr.write("\n".join(difflib.unified_diff(b, a, "expected", "actual")))
        sys.stderr.write("\nFAIL: reverse-compile spike not canonically equal.\n")
        return 2
    print("PASS: reverse-compile spike canonically equal to expected IR.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 3: Prepare inputs**

Take `examples/ir/01-ecommerce-customer-faq.json`. Compile to Dify DSL by hand (the Compiler does not exist yet) and push to pinned Dify. In Dify's editor, change `retrieve.top_k` from 20 to 15. Export. Save the exported YAML to `examples/spike/edited-ecommerce-faq.yaml`. Apply the same edit to the IR by hand and save to `examples/spike/edited-ecommerce-faq.json`.

- [ ] **Step 4: Run the spike**

```bash
python scripts/reverse_compile_spike.py \
  --dify-yaml examples/spike/edited-ecommerce-faq.yaml \
  --expected-ir examples/spike/edited-ecommerce-faq.json \
  --registry-sha sha:0000000
```

Expected: `PASS`. If FAIL, look at the unified diff — the most likely cause is a key the spike reverse compiler does not yet handle, or a canonicalization rule not yet captured.

- [ ] **Step 5: Write the spike report**

```markdown
# Reverse-compile spike report

Date: YYYY-MM-DD
Archetype: Ecommerce customer FAQ
Edit: retrieve.top_k 20 → 15 (parameter change within IR-recognized set)

## Result

PASS / FAIL

## Issues found

- ...

## What this proves

PRD §7 Phase 0 gate: round-trip risk surfaced before MVP code. Findings feed
the Phase 2A full reverse compiler design directly.
```

- [ ] **Step 6: Commit**

```bash
git add scripts/reverse_compile_spike.py examples/spike/ reports/reverse-compile-spike.md
git commit -m "feat(scripts): ecommerce-customer-faq reverse-compile spike; PRD §7 gate proven"
```

---

## Task 17: Reviewer-edit simulation

**Files:**
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/reports/reviewer-edit-simulation.md`

PRD §7 Phase 0 gate: demonstrate publish-blocking + remediation on the Phase 0 engineering target. This can be run with an internal reviewer or synthetic SOW; external senior-review signoff is not required.

This task is observation, not code.

- [ ] **Step 1: Schedule the session**

After the spike in Task 16 is green, schedule a 45–60 min internal reviewer simulation. Use a real partner reviewer if one exists; otherwise use the synthetic SOW reviewer role from ADR 0001.

- [ ] **Step 2: Run the session**

- Open one SOW-derived workflow that is deployed to pinned Dify.
- Have the reviewer make 3–5 realistic edits (parameter changes, node additions, branch tweaks).
- Walk through what happens at publish time:
  - Edit within IR-recognized set → reverse compile to IR commit on a feature branch (use the spike).
  - Edit outside the IR-recognized set → publish blocks; show the remediation UX wireframes (ADR 0004).
- Capture decisions and friction points.

- [ ] **Step 3: Write `reports/reviewer-edit-simulation.md`**

```markdown
# Reviewer edit simulation

Date: YYYY-MM-DD
Reviewer: <name/role or synthetic persona>
Archetype: <name>

## Edits attempted

1. ... (recognized / unrecognized; outcome)
2. ...
3. ...

## Friction observed

- ...

## Decisions

- Remediation UX item changes: ...
- Blocking IR-extension requests: ...

## Action items into Phase 2A plan

- ...
```

- [ ] **Step 4: Commit**

```bash
git add reports/reviewer-edit-simulation.md
git commit -m "docs: reviewer-edit simulation report"
```

---

## Task 18: Security review pass

**Files:**
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/scripts/security_review.py`
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/reports/security-review.md`

PRD §7 Phase 0 gate: "`http`, `code`, and `agent` nodes get a security pass (sandbox escape vectors, prompt-injection vectors, side-effect auditability). Surfaces issues that can't be retrofit."

- [ ] **Step 1: Write `scripts/security_review.py` (helper checks; not exhaustive)**

```python
#!/usr/bin/env python3
"""Security review helper — runs static checks against an IR file.

Not a substitute for human review. Flags the obvious so human review covers
the subtle.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

DANGEROUS_PY = [
    r"\b__import__\b",
    r"\beval\b",
    r"\bexec\b",
    r"\bopen\(\s*['\"]/",  # absolute path open
    r"\bos\.system\b",
    r"\bsubprocess\b",
    r"\bsocket\.\w+\(",
    r"\brequests\.\w+\(",
    r"\burllib\b",
    r"\bpickle\b",
    r"\bmarshal\b",
]
DANGEROUS_JS = [
    r"\beval\(",
    r"\bnew Function\(",
    r"\brequire\(['\"]child_process['\"]\)",
    r"\bfetch\(",
    r"\bXMLHttpRequest\b",
]

PROMPT_INJECTION_HINTS = [
    r"untrusted",
    r"user_input",
    r"<\|",
    r"```",
]


def review_ir(doc: dict) -> list[str]:
    findings: list[str] = []
    for n in _walk_nodes(doc["nodes"]):
        if n["type"] == "code":
            patterns = DANGEROUS_PY if n["language"] == "python" else DANGEROUS_JS
            for pat in patterns:
                if re.search(pat, n["source"]):
                    findings.append(
                        f"node {n['id']}: code uses '{pat}' — sandbox escape vector"
                    )
            if n.get("idempotency_key") is None:
                findings.append(
                    f"node {n['id']}: code without idempotency_key — re-run safety unclear"
                )
        if n["type"] == "http":
            if n.get("credential") and "${input." in (n.get("url") or ""):
                findings.append(
                    f"node {n['id']}: credentialed http with user-controlled URL — SSRF"
                )
        if n["type"] == "agent":
            sys_prompt = n.get("system_prompt") or ""
            for hint in PROMPT_INJECTION_HINTS:
                if re.search(hint, sys_prompt, re.I):
                    findings.append(
                        f"node {n['id']}: agent system prompt mentions {hint!r} — confirm typed-registry isolation"
                    )
            tools = n.get("tools", [])
            if not tools:
                findings.append(f"node {n['id']}: agent has empty tools list")
    return findings


def _walk_nodes(nodes):
    for n in nodes:
        yield n
        if n["type"] == "loop":
            yield from _walk_nodes(n["body"])
        elif n["type"] == "parallel":
            for branch in n["branches"].values():
                yield from _walk_nodes(branch)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("ir_files", nargs="+")
    args = p.parse_args()
    any_findings = False
    for f in args.ir_files:
        doc = json.loads(Path(f).read_text())
        findings = review_ir(doc)
        if findings:
            any_findings = True
            print(f"\n{f}:")
            for x in findings:
                print(f"  - {x}")
    return 1 if any_findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Run against all archetype IRs**

```bash
chmod +x scripts/security_review.py
python scripts/security_review.py examples/ir/*.json shadow-corpus/ir/*.json examples/ir/sow/*.json
```

Triage every finding: false positive, fix the IR, fix the registry, or note as a known constraint to revisit in Phase 1.

- [ ] **Step 3: Manual review**

Walk through the §9 risks specific to Phase 0:
- `code` sandbox escape (CPU/memory/wall-clock caps; no network).
- Prompt / tool-description injection (typed registry block, untrusted-content delimiters).
- HTTP SSRF (URL allowlist via registry; credentialed nodes can't take user-controlled URLs).
- Trace PII (redaction at write time per §9; default 30-day retention).

- [ ] **Step 4: Write `reports/security-review.md`**

```markdown
# Phase 0 security review

Date: YYYY-MM-DD
Reviewer: <name>

## Static-helper findings

(Output from scripts/security_review.py, triaged.)

## Manual review

### `code` sandbox

- CPU/memory/wall-clock caps: confirmed at runtime layer (Dify). Verify on pinned version.
- Network access: must be denied for `code`; only `http` reaches the network. Verify.
- Filesystem access: deny except scratch dir. Verify.

### Prompt / tool-description injection

- Tool descriptions in registry: review process: <link>.
- Planner system prompt isolates tool descriptions in a typed registry block: ...
- Agent prompt template renders untrusted content inside delimiters: ...

### HTTP SSRF

- URL allowlist scheme: ...
- Credentialed nodes with user-controlled URL: rejected by Validator (Phase 1).

### Trace PII

- Redaction at write time: filter implementation: ...
- Default retention: 30 days. Right-to-erasure: ... (Phase 2A).

## Action items into Phase 1

- ...
```

- [ ] **Step 5: Commit**

```bash
git add scripts/security_review.py reports/security-review.md
git commit -m "docs: Phase 0 security review pass; action items into Phase 1"
```

---

## Task 19: Reviewability rating from three reviewers

**Files:**
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/reports/reviewability.md`

PRD §7 Phase 0 gate: "reviewability score (subjective rating from 3 reviewers, 1–5) ≥ 4 median."

- [ ] **Step 1: Identify reviewers**

3 reviewers. At least one must be a Reviewer-persona target (senior engineer / SRE / security). The other two can be loom team members.

- [ ] **Step 2: Run the rating session**

For each archetype IR (5 placeholders + 5 SOW-derived examples), each reviewer rates 1–5 on:
- "I can read this in 5 minutes and decide approve / reject."
- "I can spot what changed in a diff against an earlier version."
- "The `rationale` fields are useful, not boilerplate."

- [ ] **Step 3: Write `reports/reviewability.md`**

```markdown
# Reviewability ratings

Date: YYYY-MM-DD

| Archetype | Reviewer 1 | Reviewer 2 | Reviewer 3 | Median |
|---|---|---|---|---|
| 01-ecommerce-customer-faq | ... | ... | ... | ... |
| ... | ... | ... | ... | ... |

Median over all archetypes: ...

Phase 0 gate: ≥ 4 median.

## Comments

- ...

## Action items into Phase 1 Planner prompts

The Planner few-shot library should bias toward rationale styles the reviewers
rated high.
```

- [ ] **Step 4: Commit**

```bash
git add reports/reviewability.md
git commit -m "docs: Phase 0 reviewability rating; gate >= 4 median"
```

---

## Task 20: Phase 0 gate report (the evidence package)

**Files:**
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/reports/phase-0-gate.md`
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/Makefile`

The gate report is the single artifact that asserts Phase 0 is closed. Every prior task feeds one row.

- [ ] **Step 1: Write `reports/phase-0-gate.md`**

```markdown
# Phase 0 gate report

Date: YYYY-MM-DD

## Phase 0 decisions/defaults (PRD §7)

| # | Item | Status | ADR / artifact |
|---|---|---|---|
| 1 | SOW / requirements intake contract accepted and first SOW packet written | accepted | docs/decisions/0001-sow-requirements-intake.md, sow/default-ecommerce/phase0-synthetic-sow.yaml |
| 2 | Runtime versions fixed: Hiagent 2.6 + Dify 1.14.0 | accepted | docs/decisions/0002-runtime-versions.md |
| 3 | Credential binding strategy accepted | accepted | docs/decisions/0003-credential-binding.md |
| 4 | Reverse-compile default scope accepted | accepted | docs/decisions/0004-reverse-compile-scope.md |
| 5 | Agent / LLM defaults accepted (`max_output_tokens = 8000`) | accepted | docs/decisions/0005-agent-governance.md |

All five must be `accepted`. Anything else: Phase 1 cannot start.

## Phase 0 gate criteria (PRD §7)

| Criterion | Status | Evidence |
|---|---|---|
| All 5 archetypes express in IR ≤25 nodes; 0 unsupported semantics requiring `code` workaround | pass/fail | `pytest tests/archetypes` |
| 0 archetypes require a node type outside v0.3 list (≤1 deliberate IR bump permitted) | pass/fail | git log of schemas/ + ADR list |
| Each hand-authored IR runs the conformance suite (on the Phase 0 engineering target — Dify) for every construct it uses; smoke test passes | pass/fail | reports/conformance-baseline.md |
| Phase 0 engineering target import/export canonicalization proven N=10, false-drift rate 0 (Dify in Phase 0; Hiagent equivalent in Phase 1 Task 11.5) | pass/fail | reports/round-trip-proof.json |
| Reverse-compile spike on one archetype canonically equal (on the Phase 0 engineering target — Dify; Hiagent spike in Phase 1 Task 11.5) | pass/fail | reports/reverse-compile-spike.md |
| Reviewer edit simulation on the Phase 0 engineering target (Dify) — publish-blocking + remediation | pass/fail | reports/reviewer-edit-simulation.md |
| Security review on `http`, `code`, `agent` (runtime-neutral; covers IR contracts, not runtime-specific surface) | pass/fail | reports/security-review.md |
| Reviewability median ≥ 4 across archetypes | pass/fail | reports/reviewability.md |
| ADR 0002 amendment recorded if Cost-budget escape hatch invoked before Phase 0 close (Dify dropped → above rows pivot to Hiagent) | n/a if not invoked | docs/decisions/0002-runtime-versions.md |

## Decision

If every row above is `pass` / `accepted` → Phase 1 unblocked.
If any row is not → Phase 1 stays blocked until iterated.
```

- [ ] **Step 2: Write a small `Makefile` for the evidence package**

```makefile
.PHONY: phase0-gate test lint type all

all: lint type test

lint:
	ruff check .

type:
	mypy loom

test:
	pytest -v

phase0-gate:
	@echo "Phase 0 gate is a manual report — see reports/phase-0-gate.md."
	@echo "Re-run scripts/round_trip_proof.py and scripts/reverse_compile_spike.py to refresh artifacts."
```

- [ ] **Step 3: Commit**

```bash
git add reports/phase-0-gate.md Makefile
git commit -m "docs: Phase 0 gate report scaffold; Makefile entry"
```

- [ ] **Step 4: Final review**

Walk through every checkbox in `reports/phase-0-gate.md`. If any is not green, do not start Phase 1. PRD §7: "If any criterion fails, iterate the SOW / IR before Phase 1 code depends on it."

---

## Self-review summary

- **Spec coverage:** Every Phase 0 default decision (§7) has a Task. Every Phase 0 gate criterion has a Task. The IR v0.2→v0.3 schema bump (§5 v0.3 changes) has a Task. Canonical-AST hashing (§6) has a Task. Conformance matrix (§5) has a Task with one row per cell. Reverse-compile spike (§7), reviewer edit simulation (§7), security review (§7), reviewability rating (§7) all have Tasks. Credential binding (§8) is referenced from ADR 0003 and consequenced into Phase 2A. Failure-taxonomy buckets (§10) are not populated in Phase 0 (no Planner yet); Phase 1 plan owns the metrics emitter.

- **Placeholder scan:** ADR templates contain `<…>` placeholders by design; each ADR has an explicit "fill in once" step. No orphan TODO/TBD items in code.

- **Type consistency:** Pydantic model names match schema $defs (TriggerNode, LLMNode, …). `MatrixRow.id` matches the keys in `case_factory` mapping.

- **Known seams to Phase 1:** (a) `loom/runtimes/dify/v1_14/client.py` payloads must be verified against the pinned Dify 1.14.0 API; (b) Task 14 hand-authored DSL is replaced by the Phase 1 Compiler; (c) the conformance runner currently builds IRs but does not invoke the Compiler — Phase 1 wires it.

---

## Execution Handoff

Plan complete and saved to `docs/plans/2026-05-05-phase-0-hard-blockers.md`. Recommended execution modes:

1. **Subagent-Driven (recommended)** — Dispatch a fresh subagent per task, review between tasks, fast iteration.
2. **Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints.
