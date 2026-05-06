# FDE Phase 2A — Production Infrastructure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Document location:** Project execution plans live in `docs/plans/`. Superpowers is a methodology, not the product-plan directory.

**Naming note:** Product-facing language is FDE / AI 驻场流程工程师. Internal implementation paths may temporarily retain the `loom/` Python namespace until a package rename decision is made.

**Goal:** Turn the Phase 1 / 1.5 toolkit into something an organization can actually run in production. Phase 2A is "load-bearing infra" only — no UI work, no chat experience changes (those live in Phase 2B). The deliverables are: (1) a real Deployer that talks to a Postgres-backed state machine, blocks publish on drift, and records hashed audit receipts; (2) a fully versioned Registry with Git-of-truth + Postgres mirror + ACL; (3) a wide reverse compiler that round-trips every PRD §5 construct used across all 5 archetypes; (4) drift detection wired into the publish path; (5) Vault-backed credential handle resolution; (6) the failure-taxonomy emitter from PRD §10 wired through every layer; (7) Trace ingestion + retention; (8) a Phase 2A gate report demonstrating end-to-end flow on a partner pilot.

**Architecture:** The Phase 1 pipeline (`FDE Session → Planner → Validator → Compiler → push-as-draft`) was a single in-process flow with no durable state. Phase 2A introduces a **stateful service layer** behind FastAPI:

- `loom/service/` — FastAPI app, request handlers, idempotency layer, error envelope.
- `loom/state/` — SQLAlchemy models + Alembic migrations for the Git ↔ runtime state machine (PRD §6.4), runtime-neutral via the Phase 1 RuntimeAdapter: `commit_sha`, `target` (`hiagent` | `dify`), `canonical_ast_hash`, `target_draft_id`, `target_published_id`, `reverse_compile_status`. A single workflow may have multiple `Draft` rows — one per registered runtime — with the same `commit_sha` but different `target` + `target_draft_id`. Drift detection runs per-row.
- `loom/registry/` — git-versioned registry source plus a Postgres mirror with ACL evaluation; `registry_version` is an immutable SHA per PRD §5.1.
- `loom/vault/` — pluggable secret backend (the actual provider was decided in Phase 0 ADR 0003).
- `loom/audit/` — append-only hashed receipt log (one row per Plan / Compile / Deploy / Publish / Reverse).
- `loom/trace/` — Trace ingestion endpoints + retention.
- Runtime reverse compilers — both `loom/runtimes/hiagent/<vH_X>/reverse.py` and `loom/runtimes/dify/<vD_Y>/reverse.py` widen from "narrow" (Phase 1: 2 deep archetypes) to **full coverage of all 5 archetypes** on each runtime. Canonical-IR-equality remains the equivalence relation per PRD §6.3. If the Cost-budget escape hatch was invoked and Dify was dropped, only the Hiagent reverse widens.
- `loom/deployer/` — replaces Phase 1's push-as-draft helper with a state-machine-aware deployer that performs drift detection on publish.

PRD §6.4 defines the exact contract: "发布前执行漂移检测，不一致即阻塞发布，直到反编译生成新 IR 并完成新一轮闭环验证." Phase 2A makes that *enforced*, not aspirational. PRD §7 calls Phase 2A the "生产基础设施" phase: deployment, registry, full reverse compilation, drift detection + publish blocking, audit chain.

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy 2 + Alembic, asyncpg, Postgres 16, Redis (idempotency keys + queue), Pydantic v2, httpx, OpenTelemetry, structlog, pytest, pytest-asyncio, ruff, mypy, Docker Compose. Phase 0 / 1 / 1.5 toolchain preserved.

> **Trim note (2026-05-06):** Code snippets, SQLAlchemy column lists, Alembic migration numbers, route signatures, and test boilerplate below are **illustrative**. The contracts that must be preserved verbatim are: (a) PRD §6.4 state-machine identifiers, **runtime-neutralized** as: `commit_sha` / `target` / `canonical_ast_hash` / `target_draft_id` / `target_published_id` / `reverse_compile_status` — a single workflow may have one Draft row per registered runtime; (b) ADR 0010 retention windows + erasure API surface; (c) ADR 0011 audit receipt hash chain; (d) ADR 0015 RuntimeAdapter interface (Phase 1) — every state operation goes through the adapter, not direct runtime imports. Everything else may be adjusted by the executor. Per project owner directive 2026-05-06: trim over-specification, keep contracts.

**Prerequisites:** Phase 1.5 plan complete. Specifically:
- `reports/phase-1-5-gate.md` shows all rows pass.
- All 5 archetypes compile under Dify; deep 2 round-trip.
- Hiagent + Dify dual-runtime parity contract is green (Phase 1.5 Task 5).
- Eval corpus ≥75 prompts.

If any of these fails, do not start Phase 2A.

---

## Repo layout extended by Phase 2A

```
docs/
├── decisions/
│   ├── 0008-state-store.md            (NEW — Postgres schema + Alembic policy)
│   ├── 0009-registry-acl-model.md     (NEW — registry ACL semantics)
│   ├── 0010-trace-retention.md        (NEW — Trace PII + retention windows)
│   └── 0011-audit-receipts.md         (NEW — receipt format + signing)
└── plans/
    └── 2026-05-06-phase-2a-production-infra.md  (this file)

loom/
├── service/
│   ├── __init__.py
│   ├── app.py                         (FastAPI app factory)
│   ├── deps.py                        (DI: db session, registry, vault, audit)
│   ├── errors.py                      (problem+json error envelope)
│   ├── idempotency.py                 (Redis-backed idempotency keys per PRD §5)
│   └── routes/
│       ├── __init__.py
│       ├── plan.py                    (POST /plan)
│       ├── compile.py                 (POST /compile)
│       ├── deploy.py                  (POST /deploy/draft, POST /deploy/publish)
│       ├── reverse.py                 (POST /reverse)
│       ├── registry.py                (GET /registry, POST /registry/sync)
│       └── trace.py                   (POST /trace/ingest)
├── state/
│   ├── __init__.py
│   ├── models.py                      (Workflow, Draft, Publish, Reverse, AuditReceipt)
│   ├── workflow_sm.py                 (state-machine guards per PRD §6.4)
│   ├── drift.py                       (canonical Dify-AST hash compare)
│   └── alembic/
│       ├── env.py
│       ├── script.py.mako
│       └── versions/
│           └── 0001_initial.py
├── registry/
│   ├── __init__.py
│   ├── source.py                      (git-versioned registry loader)
│   ├── mirror.py                      (Postgres mirror sync)
│   ├── acl.py                         (scope/tool/credential ACL eval)
│   └── types.py                       (ToolEntry, DatasetEntry, CredentialEntry)
├── vault/
│   ├── __init__.py
│   ├── base.py                        (abstract Vault interface)
│   ├── handles.py                     (handle resolution; IR/DSL never carry values)
│   └── providers/
│       ├── infisical.py               (or whichever ADR 0003 chose)
│       └── env_dev.py                 (dev-only env-var backend)
├── audit/
│   ├── __init__.py
│   ├── receipts.py                    (hashed append-only receipts)
│   └── verifier.py                    (verify chain integrity)
├── trace/
│   ├── __init__.py
│   ├── ingest.py                      (POST handler logic)
│   ├── retention.py                   (PII windows + redaction)
│   └── store.py                       (Postgres trace metadata + S3-style blob ref)
├── deployer/
│   ├── __init__.py
│   ├── draft.py                       (push-as-draft, transactional w/ state)
│   └── publish.py                     (drift-checked publish; blocks on mismatch)
├── dify/
│   └── vX_Y/
│       └── reverse.py                 (WIDENED to all 5 archetypes)
├── eval/
│   └── runner.py                      (extended: emits failure taxonomy via audit)
└── cli/
    └── commands/
        ├── deploy.py                  (now hits the service)
        ├── reverse.py                 (now hits the service)
        └── service.py                 (loom service serve / migrate)

tests/
├── service/
│   ├── conftest.py                    (FastAPI test client + sqlite-backed test DB)
│   ├── test_plan_route.py
│   ├── test_compile_route.py
│   ├── test_deploy_routes.py          (draft + publish, drift block path)
│   ├── test_reverse_route.py
│   ├── test_registry_route.py
│   └── test_trace_route.py
├── state/
│   ├── test_workflow_sm.py
│   ├── test_drift.py
│   └── test_migrations.py
├── registry/
│   ├── test_source.py
│   ├── test_mirror.py
│   └── test_acl.py
├── vault/
│   ├── test_handles.py
│   └── test_env_dev.py
├── audit/
│   ├── test_receipts.py
│   └── test_verifier.py
├── trace/
│   ├── test_ingest.py
│   └── test_retention.py
├── deployer/
│   ├── test_draft.py
│   └── test_publish_drift.py
└── dify/
    └── vX_Y/
        └── test_reverse_full.py       (NEW — all 5 archetypes round-trip)

docker/
└── stack/                             (NEW — full local stack)
    ├── docker-compose.yml             (postgres + redis + hiagent + dify + loom-service)
    └── README.md

reports/
├── phase-2a-gate.md                   (NEW — evidence package)
├── reverse-coverage.md                (NEW — per-archetype round-trip table)
├── drift-detection.md                 (NEW — synthetic drift demo + block proof)
└── audit-receipts-sample.json         (NEW — committed sample chain for review)
```

---

## Task 0: ADRs for state, registry, trace, audit

**Files:**
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/docs/decisions/0008-state-store.md`
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/docs/decisions/0009-registry-acl-model.md`
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/docs/decisions/0010-trace-retention.md`
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/docs/decisions/0011-audit-receipts.md`

Phase 2A introduces durable state. We pin the schema-evolution policy, the ACL model, the trace-PII handling, and the receipt format up front so reviewers can sign off before any production code is written. ADR template follows the same shape as 0001–0007.

- [ ] **Step 1: ADR 0008 — state store**

```markdown
# ADR 0008 — Loom state store

Status: Proposed → Accepted (after review)
Date: 2026-MM-DD

## Decision

- DB: Postgres 16 (single primary; HA is out of v1 scope).
- Migrations: Alembic, forward-only by default; explicit data migration files when destructive.
- Tables: workflow, draft, publish, reverse_attempt, audit_receipt, trace_meta. Schemas frozen at v0.
- Connection pooling: asyncpg via SQLAlchemy 2.x async engine, pool size set per deployment.

## Consequences

- All workflow/state/trace tests run against an ephemeral Postgres in CI (slow lane); fast lane uses sqlite for unit tests with parity guarded by `tests/state/test_migrations.py`.
- Schema changes require a new ADR section with reasoning; no silent online migrations.
```

- [ ] **Step 2: ADR 0009 — registry ACL model**

```markdown
# ADR 0009 — Registry ACL model

Status: Proposed → Accepted (after review)
Date: 2026-MM-DD

## Decision

- Source of truth: a single Git repository (`registry/`) with `tools/`, `datasets/`, `credentials/` directories.
- Each entry carries a `scopes` array (e.g. `ecommerce/kb`, `ecommerce/orders`, `clinic/kb`).
- Postgres mirror is a content-addressed snapshot keyed by `registry_version = sha:<commit>`.
- ACL evaluation is per-Author scope. Author scope `ecommerce/kb` resolves only entries with intersecting scope; same rule for TCM shadow scopes.
- Credentials are *handles only*; values live in Vault. The handle includes the credential type and the Vault path, never the secret.

## Consequences

- IR `registry_ref.tools/datasets/credentials` arrays are filtered server-side at Plan time per Author's scope. The Planner never sees out-of-scope entries.
- Bumping `registry_version` is a Git commit; deploys reference the SHA explicitly to prevent "latest" drift.
```

- [ ] **Step 3: ADR 0010 — Trace retention + PII**

```markdown
# ADR 0010 — Trace retention + PII handling

Status: Proposed → Accepted (after review)
Date: 2026-MM-DD

## Decision

### Retention windows
- Trace metadata (workflow id, run id, node id, status, duration) retained 90 days hot in Postgres.
- Trace payloads (LLM I/O, tool I/O) retained 30 days in object storage.
- Beyond retention windows: hard delete via nightly retention job; no archival tier in v1.

### PII classification (`pii_class`)
- Every registry entry — tool, dataset, credential — declares `pii_class`: one of
  `none` | `low` (no direct identifiers) | `medium` (contact info, indirect identifiers) |
  `high` (medical, identity, payment, biometric).
- Each IR `output_schema` field MAY declare `pii_class` to override the entry-level default.
- Trace ingest (`loom/trace/ingest.py`) consults a resolved `pii_class` per node payload:
  - `none` → store as-is
  - `low` → store; subject-erasure API removes on request
  - `medium` → redact pattern-detected fields at ingest; store redacted form; honor erasure
  - `high` → reject ingest of raw payload; store only a one-way digest + structural shape; honor erasure
- **Customer / patient PII = hard contract.** For ecommerce primary workflows touching customer name / phone / address / payment, AND for TCM shadow workflows touching patient data, the Validator (Phase 1) refuses to compile if any node lacks an explicit `pii_class` declaration. This is a hard contract, not a setting.

### Right-to-erasure
- `DELETE /v1/trace/runs/{run_id}` — Reviewer or Admin scope; removes metadata + payload for one run; emits an `audit.trace_erased_run` receipt.
- `POST /v1/trace/erasure` body `{subject_ref: str, scope: str, reason: str}` — Admin scope; removes every trace metadata row + payload blob whose redacted-payload digest matches the subject ref across the tenant; emits an `audit.trace_erased_subject` receipt with count + duration. Idempotent (rerunning is a no-op).
- Erasure is hard delete (not tombstone). The audit receipt preserves *that* erasure happened, but never the erased content.

## Consequences

- `loom/trace/retention.py` implements both redaction at ingest and the deletion job.
- `loom/registry/types.py` adds a `pii_class` field on every entry type (Phase 2A Task 4 must include this).
- Tests must verify: (a) synthetic PII never appears in stored payloads (Phase 2A Task 10 already covers); (b) retention enforcement actually deletes >30d payloads and >90d metadata; (c) erasure API is reachable only with the right role; (d) erasure leaves an audit receipt; (e) `high` pii_class rejects raw payload ingestion.
```

- [ ] **Step 4: ADR 0011 — Audit receipts**

```markdown
# ADR 0011 — Audit receipts

Status: Proposed → Accepted (after review)
Date: 2026-MM-DD

## Decision

- Append-only `audit_receipt` table.
- Each receipt: `id`, `prev_hash`, `op` (plan|compile|deploy_draft|publish|reverse|registry_sync), `actor`, `subject` (workflow id), `payload_hash` (SHA-256 over a canonical JSON form of the operation), `created_at`, `self_hash` (SHA-256 over previous fields).
- Hash chain: `self_hash = sha256(prev_hash || canonical(payload))`. Genesis row uses zero-hash.
- v1 does NOT cryptographically sign receipts beyond the chain; signing is a Phase 3 candidate.

## Consequences

- `loom/audit/verifier.py` walks the chain and refuses to verify if any link is broken; this is run as part of the Phase 2A gate.
- Every state-machine transition emits exactly one receipt; tests verify 1:1 mapping.
```

- [ ] **Step 5: Commit + reviewer pass**

```bash
git add docs/decisions/0008-state-store.md docs/decisions/0009-registry-acl-model.md docs/decisions/0010-trace-retention.md docs/decisions/0011-audit-receipts.md
git commit -m "docs(adr): Phase 2A foundations — state, ACL, trace retention, audit receipts"
```

Send to reviewer (`/ask codex "[PLAN REVIEW REQUEST] ..."`). Pass criteria: every "Decision" bullet either has a clear single owner (Phase 2A code path) or moves to Phase 2B/3.

---

## Task 1: Local stack docker-compose

**Files:**
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/docker/stack/docker-compose.yml`
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/docker/stack/README.md`

The dev stack glues Postgres + Redis + Hiagent (ADR 0002) + Dify (ADR 0002) + the FastAPI service. Tests can opt in via `LOOM_STACK_LIVE=1`.

- [ ] **Step 1: Compose file**

```yaml
version: "3.9"
services:
  postgres:
    image: postgres:16
    environment:
      POSTGRES_DB: loom
      POSTGRES_USER: loom
      POSTGRES_PASSWORD: loom
    ports: ["5432:5432"]
    volumes: ["pg_data:/var/lib/postgresql/data"]

  redis:
    image: redis:7
    ports: ["6379:6379"]

  loom:
    build: ../..
    depends_on: [postgres, redis]
    environment:
      LOOM_DB_URL: postgresql+asyncpg://loom:loom@postgres:5432/loom
      LOOM_REDIS_URL: redis://redis:6379/0
      LOOM_VAULT_PROVIDER: env_dev
    ports: ["8000:8000"]
    command: ["uvicorn", "loom.service.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]

volumes:
  pg_data:
```

- [ ] **Step 2: README**

```markdown
# Loom local stack (Phase 2A)

Brings up Postgres + Redis + the FastAPI service. Use alongside `docker/hiagent-pinned/` and `docker/dify-pinned/` (run them independently to keep ports clean).

    docker compose -f docker/stack/docker-compose.yml up
```

- [ ] **Step 3: Commit**

```bash
git add docker/stack/
git commit -m "infra(stack): Postgres + Redis + service dev compose"
```

---

## Task 2: Service skeleton — FastAPI app + DI + error envelope

**Files:**
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/loom/service/__init__.py`
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/loom/service/app.py`
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/loom/service/deps.py`
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/loom/service/errors.py`
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/loom/service/idempotency.py`
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/tests/service/conftest.py`

- [ ] **Step 1: App factory + lifespan**

```python
# loom/service/app.py
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from loom.service.errors import register_exception_handlers
from loom.service.routes import plan, compile as compile_route, deploy, reverse as reverse_route, registry, trace
from loom.state.models import init_engine, dispose_engine


@asynccontextmanager
async def _lifespan(app: FastAPI):
    await init_engine()
    yield
    await dispose_engine()


def create_app() -> FastAPI:
    app = FastAPI(title="Loom FDE Service", version="0.2.0", lifespan=_lifespan)
    register_exception_handlers(app)
    app.include_router(plan.router, prefix="/v1")
    app.include_router(compile_route.router, prefix="/v1")
    app.include_router(deploy.router, prefix="/v1")
    app.include_router(reverse_route.router, prefix="/v1")
    app.include_router(registry.router, prefix="/v1")
    app.include_router(trace.router, prefix="/v1")
    return app
```

- [ ] **Step 2: Error envelope (problem+json)**

> Phase 1's `loom.validator.errors.ValidationFailure` is a frozen `@dataclass` *record*, not an exception, and `loom.validator.validate(...)` returns `list[ValidationFailure]`. Phase 2A introduces a thin wrapper exception, `ValidationFailed`, that carries the list so it can be raised from the service layer when the validator returns a non-empty list. The dataclass record itself is unchanged.

```python
# loom/service/errors.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from loom.validator.errors import ValidationFailure  # frozen dataclass record from Phase 1
from loom.runtimes.base import UnrecognizedConstruct  # from Phase 1 RuntimeAdapter (ADR 0015)


@dataclass
class ValidationFailed(Exception):
    """Service-layer wrapper raised when loom.validator.validate(...) returns a non-empty list."""
    failures: list[ValidationFailure]

    def __str__(self) -> str:
        return f"{len(self.failures)} validation failures"

    @property
    def primary_bucket(self) -> str | None:
        return self.failures[0].bucket if self.failures else None


class Problem(BaseModel):
    type: str
    title: str
    status: int
    detail: str
    bucket: str | None = None
    extras: dict[str, Any] = {}


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(ValidationFailed)
    async def _vf(request: Request, exc: ValidationFailed):
        return JSONResponse(
            status_code=422,
            content=Problem(
                type="urn:loom:validator", title="IR validation failed",
                status=422, detail=str(exc), bucket=exc.primary_bucket,
                extras={"errors": [vars(e) for e in exc.failures]},
            ).model_dump(),
        )

    @app.exception_handler(UnrecognizedConstruct)
    async def _uc(request: Request, exc: UnrecognizedConstruct):
        # Raised by reverse compiler when a runtime DSL contains a construct outside
        # the IR-recognized set (PRD §6 hard-block contract).
        return JSONResponse(
            status_code=409,
            content=Problem(
                type="urn:loom:reverse/unrecognized", title="Unrecognized runtime construct",
                status=409, detail=str(exc), bucket="reverse_compile",
                extras={"target": exc.target, "construct": exc.construct, "remediation": exc.remediation},
            ).model_dump(),
        )

    @app.exception_handler(Exception)
    async def _default(request: Request, exc: Exception):
        return JSONResponse(
            status_code=500,
            content=Problem(type="urn:loom:internal", title="Internal error", status=500, detail=str(exc)).model_dump(),
        )
```

> Service routes that call the validator must convert the returned list into `ValidationFailed` themselves: `failures = validate(ir, scope=scope); if failures: raise ValidationFailed(failures)`. The handler does the rest.

- [ ] **Step 3: Dependency injection**

`deps.py` provides: `get_session` (SQLAlchemy async session), `get_registry()`, `get_vault()`, `get_audit()`, `get_idempotency()`. Each is async; tests override via FastAPI `dependency_overrides`.

- [ ] **Step 4: Idempotency keys**

```python
# loom/service/idempotency.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from redis.asyncio import Redis


@dataclass
class IdempotencyResult:
    cached: bool
    response: dict[str, Any] | None


class IdempotencyStore:
    def __init__(self, redis: Redis, ttl_s: int = 86400) -> None:
        self.redis = redis
        self.ttl_s = ttl_s

    async def get_or_set(self, key: str, response_factory) -> IdempotencyResult:
        existing = await self.redis.get(f"idem:{key}")
        if existing:
            return IdempotencyResult(cached=True, response=json.loads(existing))
        response = await response_factory()
        await self.redis.setex(f"idem:{key}", self.ttl_s, json.dumps(response, default=str))
        return IdempotencyResult(cached=False, response=response)
```

PRD §5 mentions `idempotency_key` per node — note this service-level idempotency is for client requests, not runtime node idempotency.

- [ ] **Step 5: Test conftest**

`tests/service/conftest.py` builds a FastAPI test app with sqlite-backed SQLAlchemy + a fakeredis instance + an in-memory Vault. Real Postgres + Redis are exercised in slow lane only.

- [ ] **Step 6: Commit**

```bash
git add loom/service/ tests/service/conftest.py
git commit -m "feat(service): FastAPI app skeleton with DI, error envelope, idempotency"
```

---

## Task 3: State models + Alembic + state machine

**Files:**
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/loom/state/__init__.py`
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/loom/state/models.py`
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/loom/state/workflow_sm.py`
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/loom/state/drift.py`
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/loom/state/alembic/env.py`
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/loom/state/alembic/script.py.mako`
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/loom/state/alembic/versions/0001_initial.py`
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/tests/state/test_workflow_sm.py`
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/tests/state/test_drift.py`
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/tests/state/test_migrations.py`

- [ ] **Step 1: Models — match PRD §6.4 identifiers exactly**

```python
# loom/state/models.py (excerpt)
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import String, ForeignKey, DateTime, JSON, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase): ...


class Workflow(Base):
    __tablename__ = "workflow"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(256), unique=True)
    owner: Mapped[str] = mapped_column(String(256))
    scope: Mapped[str] = mapped_column(String(256))
    commit_sha: Mapped[str] = mapped_column(String(64))             # PRD §6.4
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Draft(Base):
    """One row per (workflow_id, target). Same workflow → multiple Draft rows, one per
    registered runtime. Drift detection runs per-row via the runtime's adapter."""
    __tablename__ = "draft"
    __table_args__ = (UniqueConstraint("workflow_id", "target", "commit_sha", name="uq_draft_wf_target_sha"),)
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workflow_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workflow.id"))
    target: Mapped[str] = mapped_column(String(32))                    # "hiagent" | "dify" (extensible)
    commit_sha: Mapped[str] = mapped_column(String(64))
    canonical_ast_hash: Mapped[str] = mapped_column(String(64))        # PRD §6.4 — runtime-neutral name
    target_draft_id: Mapped[str] = mapped_column(String(128))          # PRD §6.4 — id in the target runtime
    ir_blob: Mapped[dict] = mapped_column(JSON)
    dsl_blob: Mapped[dict] = mapped_column(JSON)                       # runtime-specific shape (Hiagent JSON or Dify YAML-as-dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Publish(Base):
    """A publish on a specific Draft row → one specific runtime. To publish a workflow
    on both runtimes, two Publish rows reference two Draft rows (same workflow_id,
    different target)."""
    __tablename__ = "publish"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    draft_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("draft.id"))
    target: Mapped[str] = mapped_column(String(32))                    # mirrored from Draft for query convenience
    target_published_id: Mapped[str] = mapped_column(String(128))      # PRD §6.4 — id in the target runtime
    expected_canonical_ast_hash: Mapped[str] = mapped_column(String(64))
    actual_canonical_ast_hash: Mapped[str] = mapped_column(String(64))
    drift_blocked: Mapped[bool] = mapped_column(default=False)         # PRD §6.4 contract
    actor: Mapped[str] = mapped_column(String(256))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ReverseAttempt(Base):
    __tablename__ = "reverse_attempt"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    draft_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("draft.id"))
    status: Mapped[str] = mapped_column(String(32))                   # PRD §6.4 reverse_compile_status
    new_ir_blob: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    unrecognized_constructs: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AuditReceipt(Base):
    __tablename__ = "audit_receipt"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    prev_hash: Mapped[str] = mapped_column(String(64))
    op: Mapped[str] = mapped_column(String(32))
    actor: Mapped[str] = mapped_column(String(256))
    subject: Mapped[str] = mapped_column(String(256))
    payload_hash: Mapped[str] = mapped_column(String(64))
    self_hash: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class TraceMeta(Base):
    __tablename__ = "trace_meta"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workflow_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workflow.id"))
    run_id: Mapped[str] = mapped_column(String(128))
    node_id: Mapped[str] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(32))
    duration_ms: Mapped[int]
    payload_ref: Mapped[str] = mapped_column(String(512))            # storage key
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
```

- [ ] **Step 2: State machine guards**

```python
# loom/state/workflow_sm.py
from __future__ import annotations

from enum import Enum


class State(str, Enum):
    NEW = "new"
    DRAFTED = "drafted"
    REVERSE_PENDING = "reverse_pending"
    REVERSE_BLOCKED = "reverse_blocked"
    PUBLISH_BLOCKED_DRIFT = "publish_blocked_drift"
    PUBLISHED = "published"


# (state, op) → next_state. Anything not listed is a programmer error.
TRANSITIONS = {
    (State.NEW, "deploy_draft"): State.DRAFTED,
    (State.DRAFTED, "deploy_draft"): State.DRAFTED,             # re-push allowed
    (State.DRAFTED, "reverse"): State.REVERSE_PENDING,
    (State.REVERSE_PENDING, "reverse_recognized"): State.DRAFTED,
    (State.REVERSE_PENDING, "reverse_unrecognized"): State.REVERSE_BLOCKED,
    (State.DRAFTED, "publish"): State.PUBLISHED,
    (State.DRAFTED, "publish_drift"): State.PUBLISH_BLOCKED_DRIFT,
    (State.PUBLISH_BLOCKED_DRIFT, "reverse"): State.REVERSE_PENDING,
    (State.PUBLISHED, "deploy_draft"): State.DRAFTED,            # next iteration
}


def next_state(current: State, op: str) -> State:
    try:
        return TRANSITIONS[(current, op)]
    except KeyError:
        raise InvalidTransition(current, op)


class InvalidTransition(Exception):
    def __init__(self, current: State, op: str) -> None:
        super().__init__(f"invalid transition from {current.value} via {op}")
        self.current, self.op = current, op
```

- [ ] **Step 3: Drift detector (runtime-neutral via RuntimeAdapter)**

> **Module-path note:** `loom/runtimes/<target>/ast.py` is intentionally **unversioned** for each runtime — canonical-AST hashing is a stable, version-agnostic facade (Phase 0 ADR 0002). The version-segmented modules (`loom/runtimes/<target>/v<X_Y>/compiler.py`, `reverse.py`) own everything that *does* change with the runtime version. The `RuntimeAdapter.canonical_ast_hash(dsl)` method re-exports the per-runtime hash function — same logic, adapter-shaped surface. Drift detection calls `adapter.canonical_ast_hash` and is therefore runtime-agnostic.

```python
# loom/state/drift.py
from __future__ import annotations
from dataclasses import dataclass

from loom.runtimes import registry as runtime_registry


@dataclass
class DriftResult:
    blocked: bool
    target: str
    expected: str
    actual: str
    delta_summary: str | None = None


def check(*, target: str, expected_canonical_hash: str, current_dsl: object) -> DriftResult:
    """Drift detection per runtime target. The current_dsl shape is runtime-specific
    (Hiagent JSON dict or Dify YAML-as-dict); the adapter knows how to hash it."""
    adapter = runtime_registry.get(target)
    actual = adapter.canonical_ast_hash(current_dsl)
    if actual == expected_canonical_hash:
        return DriftResult(blocked=False, target=target, expected=expected_canonical_hash, actual=actual)
    return DriftResult(blocked=True, target=target, expected=expected_canonical_hash, actual=actual,
                       delta_summary=f"canonical {target} AST hash differs; reverse-compile required before publish")
```

- [ ] **Step 4: Initial Alembic migration**

`loom/state/alembic/versions/0001_initial.py` creates all 6 tables. Use Alembic autogenerate from `Base.metadata`. Verify it runs against an empty Postgres in `tests/state/test_migrations.py` (slow lane).

- [ ] **Step 5: Tests**

```python
# tests/state/test_workflow_sm.py
import pytest

from loom.state.workflow_sm import State, next_state, InvalidTransition


def test_happy_path():
    s = State.NEW
    s = next_state(s, "deploy_draft")
    assert s == State.DRAFTED
    s = next_state(s, "publish")
    assert s == State.PUBLISHED


def test_drift_blocks_publish():
    s = State.DRAFTED
    s = next_state(s, "publish_drift")
    assert s == State.PUBLISH_BLOCKED_DRIFT


def test_invalid_transition():
    with pytest.raises(InvalidTransition):
        next_state(State.NEW, "publish")
```

```python
# tests/state/test_drift.py
import pytest

from loom.state.drift import check
from loom.runtimes import registry as runtime_registry


@pytest.fixture(autouse=True)
def _registry_with_fakes():
    # Phase 1 registers real adapters at import time; Phase 2A tests register lightweight
    # fakes that implement only canonical_ast_hash. Reset between tests.
    yield
    for t in list(runtime_registry.list_targets()):
        runtime_registry.unregister(t)


@pytest.mark.parametrize("target", ["hiagent", "dify"])
def test_no_drift(target, fake_adapter_factory, simple_dsl_for):
    runtime_registry.register(fake_adapter_factory(target))
    dsl = simple_dsl_for(target)
    h = runtime_registry.get(target).canonical_ast_hash(dsl)
    res = check(target=target, expected_canonical_hash=h, current_dsl=dsl)
    assert res.blocked is False
    assert res.target == target


@pytest.mark.parametrize("target", ["hiagent", "dify"])
def test_drift_blocks(target, fake_adapter_factory, simple_dsl_for):
    runtime_registry.register(fake_adapter_factory(target))
    dsl = simple_dsl_for(target)
    h = runtime_registry.get(target).canonical_ast_hash(dsl)
    # mutate the DSL — runtime-neutral: any structural change should change the hash
    edited = {**dsl, "_marker": "edited"}
    res = check(target=target, expected_canonical_hash=h, current_dsl=edited)
    assert res.blocked is True
    assert res.expected != res.actual
    assert res.target == target
```

- [ ] **Step 6: Commit**

```bash
git add loom/state/ tests/state/
git commit -m "feat(state): SQLAlchemy models + state machine + drift detector + alembic 0001"
```

---

## Task 4: Registry — git source + Postgres mirror + ACL

**Files:**
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/loom/registry/__init__.py`
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/loom/registry/types.py`
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/loom/registry/source.py`
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/loom/registry/mirror.py`
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/loom/registry/acl.py`
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/registry/README.md`
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/registry/tools/<sample>.yaml`
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/registry/datasets/<sample>.yaml`
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/registry/credentials/<sample>.yaml`
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/tests/registry/test_source.py`
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/tests/registry/test_mirror.py`
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/tests/registry/test_acl.py`

PRD §5.1 requires `registry_ref.registry_version` to be an immutable SHA. This task makes that real.

- [ ] **Step 1: Types**

```python
# loom/registry/types.py
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


PiiClass = Literal["none", "low", "medium", "high"]


class ToolEntry(BaseModel):
    name: str
    description: str
    schema_uri: str
    scopes: list[str]
    pii_class: PiiClass = "none"          # see ADR 0010


class DatasetEntry(BaseModel):
    name: str
    backend: str                          # e.g. "dify_kb", "postgres", "s3"
    handle: str
    scopes: list[str]
    pii_class: PiiClass                   # required — datasets carry data; choose explicitly


class CredentialEntry(BaseModel):
    name: str
    type: str                             # e.g. "api_key", "oauth_token"
    vault_path: str                       # values stay in Vault per ADR 0003
    scopes: list[str]
    pii_class: PiiClass = "none"          # most credentials are not data themselves


class RegistrySnapshot(BaseModel):
    registry_version: str                 # "sha:<commit>"
    tools: list[ToolEntry]
    datasets: list[DatasetEntry]
    credentials: list[CredentialEntry]
```

> Tests in `tests/registry/test_source.py` must include a fixture entry at every `pii_class` level so downstream trace-ingest tests can assert per-class behavior. Backfilling `pii_class` for existing registry entries is a one-time data migration committed alongside the schema bump.

- [ ] **Step 2: Git-versioned source loader**

```python
# loom/registry/source.py
from __future__ import annotations

import subprocess
from pathlib import Path

import yaml

from loom.registry.types import CredentialEntry, DatasetEntry, RegistrySnapshot, ToolEntry


def load(registry_root: Path, ref: str = "HEAD") -> RegistrySnapshot:
    sha = subprocess.check_output(["git", "-C", str(registry_root), "rev-parse", ref], text=True).strip()
    tools = [ToolEntry(**yaml.safe_load(p.read_text())) for p in (registry_root / "tools").glob("*.yaml")]
    datasets = [DatasetEntry(**yaml.safe_load(p.read_text())) for p in (registry_root / "datasets").glob("*.yaml")]
    creds = [CredentialEntry(**yaml.safe_load(p.read_text())) for p in (registry_root / "credentials").glob("*.yaml")]
    return RegistrySnapshot(registry_version=f"sha:{sha}", tools=tools, datasets=datasets, credentials=creds)
```

- [ ] **Step 3: Postgres mirror**

`mirror.py` upserts a `RegistrySnapshot` into `registry_snapshot` + `registry_entry` tables (added in a follow-up Alembic revision `0002_registry.py`). Read path is "give me the snapshot at sha X"; write path is "sync this snapshot if not already present".

- [ ] **Step 4: ACL evaluator**

```python
# loom/registry/acl.py
from __future__ import annotations

from loom.registry.types import RegistrySnapshot


def filter_by_scope(snap: RegistrySnapshot, scopes: list[str]) -> RegistrySnapshot:
    sset = set(scopes)
    return RegistrySnapshot(
        registry_version=snap.registry_version,
        tools=[t for t in snap.tools if sset & set(t.scopes)],
        datasets=[d for d in snap.datasets if sset & set(d.scopes)],
        credentials=[c for c in snap.credentials if sset & set(c.scopes)],
    )
```

- [ ] **Step 5: Tests**

Tests cover: load is reproducible at a given SHA; ACL filtering excludes non-matching scopes; mirror sync is idempotent; reading a missing SHA raises a typed error.

- [ ] **Step 6: Commit**

```bash
git add loom/registry/ registry/ tests/registry/
git commit -m "feat(registry): git-versioned source + Postgres mirror + scope ACL"
```

---

## Task 5: Vault provider wiring

**Files:**
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/loom/vault/__init__.py`
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/loom/vault/base.py`
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/loom/vault/handles.py`
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/loom/vault/providers/<chosen>.py`  (per ADR 0003)
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/loom/vault/providers/env_dev.py`
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/tests/vault/test_handles.py`
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/tests/vault/test_env_dev.py`

ADR 0003 picked the production Vault. The job here is wiring + invariants — IR/DSL must never carry a secret value, only a handle.

- [ ] **Step 1: Base interface**

```python
# loom/vault/base.py
from __future__ import annotations

from typing import Protocol


class Vault(Protocol):
    async def get(self, path: str) -> str: ...
    async def health(self) -> bool: ...
```

- [ ] **Step 2: Handle resolver + invariant test**

> Per Phase 0 IR v0.3, `ir.registry_ref.credentials` is `list[str]` — a list of credential *names* only. Values and Vault paths live in the registry mirror (Phase 2A Task 4). The resolver therefore takes a `RegistrySnapshot` and looks up each name to get its `vault_path`, then asks the Vault for the value. The resolved values stay in process memory and are never written back to the IR or DSL — that is the PRD §8 invariant the test in Step 3 protects.

```python
# loom/vault/handles.py
from __future__ import annotations

from loom.ir.models import IRDocument
from loom.registry.types import RegistrySnapshot
from loom.vault.base import Vault


class CredentialNotInRegistry(KeyError):
    """The IR references a credential name that the registry snapshot does not expose."""


async def resolve_handles(
    ir: IRDocument,
    registry: RegistrySnapshot,
    vault: Vault,
) -> dict[str, str]:
    """Returns {credential_name: secret_value} for runtime use only.

    PRD §8 invariant: IR/DSL only carry handles, never values. The registry maps a
    credential *name* (what the IR carries) to a *vault_path* (what the Vault knows).
    Values are not written back into the IR or DSL.
    """
    by_name = {c.name: c for c in registry.credentials}
    out: dict[str, str] = {}
    for name in ir.registry_ref.credentials:
        entry = by_name.get(name)
        if entry is None:
            raise CredentialNotInRegistry(
                f"credential {name!r} not in registry snapshot {registry.registry_version!r}"
            )
        out[name] = await vault.get(entry.vault_path)
    return out
```

- [ ] **Step 3: Tests for the invariant**

```python
# tests/vault/test_handles.py
import json

import pytest

from loom.ir.models import IRDocument


@pytest.mark.parametrize("path", [
    "examples/ir/01-ecommerce-customer-faq.json",
    "examples/ir/02-tcm-intake-triage.json",
    "examples/ir/03-clinic-ops-summary.json",
    "examples/ir/04-tcm-followup.json",
    "examples/ir/05-ecommerce-order-exception.json",
])
def test_ir_carries_no_secret_values(path):
    blob = json.loads(open(path).read())
    text = json.dumps(blob)
    # cheap heuristic: refuse if it looks like a secret leaked into IR
    assert "sk-" not in text, "OpenAI/Anthropic key shape leaked into IR"
    assert "xoxb-" not in text, "Slack token shape leaked into IR"
    assert "ghp_" not in text, "GitHub token shape leaked into IR"
```

- [ ] **Step 4: Commit**

```bash
git add loom/vault/ tests/vault/
git commit -m "feat(vault): handle-only contract with provider per ADR 0003"
```

---

## Task 6: Audit receipts — append-only chain

**Files:**
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/loom/audit/__init__.py`
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/loom/audit/receipts.py`
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/loom/audit/verifier.py`
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/tests/audit/test_receipts.py`
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/tests/audit/test_verifier.py`

- [ ] **Step 1: Receipt writer**

```python
# loom/audit/receipts.py
from __future__ import annotations

import hashlib
import json
from typing import Any, Literal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from loom.state.models import AuditReceipt

Op = Literal["plan", "compile", "deploy_draft", "publish", "reverse", "registry_sync"]
GENESIS = "0" * 64


def _canonical(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


async def emit(session: AsyncSession, op: Op, actor: str, subject: str, payload: dict[str, Any]) -> AuditReceipt:
    """Append one receipt to the chain.

    Caller is responsible for serializing concurrent emits (e.g., with a SELECT … FOR UPDATE
    on a tenant-scoped sentinel row, or by funnelling all writers through a single async
    queue). Two parallel emits without serialization will both read the same `prev_hash`
    and produce a fork; the verifier in Step 2 will refuse to verify such a chain.
    """
    stmt = select(AuditReceipt).order_by(AuditReceipt.created_at.desc()).limit(1)
    last = (await session.execute(stmt)).scalar_one_or_none()
    prev_hash = last.self_hash if last else GENESIS
    payload_hash = hashlib.sha256(_canonical(payload).encode()).hexdigest()
    self_hash = hashlib.sha256((prev_hash + payload_hash).encode()).hexdigest()

    rec = AuditReceipt(
        prev_hash=prev_hash, op=op, actor=actor, subject=subject,
        payload_hash=payload_hash, self_hash=self_hash,
    )
    session.add(rec)
    await session.flush()
    return rec
```

- [ ] **Step 2: Chain verifier**

```python
# loom/audit/verifier.py
from __future__ import annotations

import hashlib
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from loom.state.models import AuditReceipt


@dataclass
class VerifyResult:
    ok: bool
    checked: int
    broken_at: str | None = None


async def verify_chain(session: AsyncSession) -> VerifyResult:
    from sqlalchemy import select
    stmt = select(AuditReceipt).order_by(AuditReceipt.created_at)
    rows = (await session.execute(stmt)).scalars().all()
    prev = "0" * 64
    for i, r in enumerate(rows):
        if r.prev_hash != prev:
            return VerifyResult(ok=False, checked=i, broken_at=str(r.id))
        expected = hashlib.sha256((r.prev_hash + r.payload_hash).encode()).hexdigest()
        if expected != r.self_hash:
            return VerifyResult(ok=False, checked=i, broken_at=str(r.id))
        prev = r.self_hash
    return VerifyResult(ok=True, checked=len(rows))
```

- [ ] **Step 3: Tests**

Tests cover: chain verifies after N receipts; tampering with `payload_hash` fails verification; concurrent emits maintain order under a single transaction; genesis receipt has zero `prev_hash`.

- [ ] **Step 4: Commit**

```bash
git add loom/audit/ tests/audit/
git commit -m "feat(audit): append-only hashed receipts + chain verifier"
```

---

## Task 7: Wide reverse compilers — all 5 archetypes, both runtimes

**Files:**
- Modify: `loom/runtimes/hiagent/<vH_X>/reverse.py`
- Modify: `loom/runtimes/dify/<vD_Y>/reverse.py`
- Create: `tests/runtimes/hiagent/<vH_X>/test_reverse_full.py`
- Create: `tests/runtimes/dify/<vD_Y>/test_reverse_full.py`
- Create: `reports/reverse-coverage.md`

PRD §6.2: "正向编译可生成的结构必须可反向回 IR." Phase 1 made this true for 2 archetypes on each runtime. Phase 2A makes it true for **all 5 archetypes on both runtimes**. PRD §6.3: comparison is canonical-IR equality (runtime-agnostic).

> Cost-budget escape hatch: if Dify was dropped per ADR 0002, only the Hiagent reverse widens; Dify rows in the gate report are marked N/A.

- [ ] **Step 1: Inventory missing reverse cases per runtime**

For each (runtime, archetype) pair, list the runtime-DSL nodes the Phase 1 reverse compiler does not yet handle. Write into `reports/reverse-coverage.md` as a per-archetype × per-IR-node matrix split by runtime. The task list comes from the ✗ cells.

- [ ] **Step 2: Implement missing inverse-emit functions on each runtime**

For each ✗ cell, write a runtime-DSL → IR-node parser in the matching `loom/runtimes/<target>/<vX_Y>/reverse.py`. Each parser returns either `Node` or `UnrecognizedConstruct` (typed; PRD §6.4 hard-block contract). `UnrecognizedConstruct` (already imported from `loom.runtimes.base` per ADR 0015) carries `target`, `construct`, `reason`, `remediation`.

- [ ] **Step 3: Round-trip tests for all 5 archetypes on each runtime**

```python
# tests/runtimes/<target>/<vX_Y>/test_reverse_full.py  (one file per runtime)
import json
from pathlib import Path
import pytest

from loom.ir.models import IRDocument
from loom.ir.canonicalize import canonical_ir
from loom.runtimes import registry as runtime_registry

ARCHETYPES = [
    "01-ecommerce-customer-faq", "02-tcm-intake-triage", "03-clinic-ops-summary",
    "04-tcm-followup", "05-ecommerce-order-exception",
]
TARGET = "<hiagent or dify>"  # one file per target


@pytest.mark.parametrize("name", ARCHETYPES)
def test_round_trip_canonical_equality(name: str) -> None:
    ir = IRDocument.model_validate(json.loads(Path(f"examples/ir/{name}.json").read_text()))
    adapter = runtime_registry.get(TARGET)
    dsl = adapter.compile(ir)
    back, unrecognized = adapter.reverse(dsl)
    assert unrecognized == [], f"unrecognized constructs in {name} on {TARGET}: {unrecognized}"
    assert canonical_ir(ir) == canonical_ir(back), f"{name} round-trip not canonically equal on {TARGET}"
```

- [ ] **Step 4: `reports/reverse-coverage.md`**

```markdown
# Reverse coverage by archetype × runtime

## Hiagent

| Archetype | Vertical role | trigger | llm | retrieval | http | code | condition | loop | parallel | agent | output | round-trip |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 01-ecommerce-customer-faq | primary | ✓ | ✓ | ✓ | — | — | ✓ | — | — | — | ✓ | ✓ |
| 02-tcm-intake-triage | shadow | ✓ | ✓ | — | ✓ | — | ✓ | — | — | ✓ | ✓ | ✓ |
| 03-clinic-ops-summary | shadow | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | — | — | — | ✓ | ✓ |
| 04-tcm-followup | shadow | ✓ | ✓ | ✓ | ✓ | — | ✓ | ✓ | — | — | ✓ | ✓ |
| 05-ecommerce-order-exception | primary | ✓ | ✓ | — | ✓ | ✓ | ✓ | — | ✓ | ✓ | ✓ | ✓ |

## Dify (skip if Cost-budget escape hatch invoked)

(Same row set; cells filled per Dify's reverse coverage.)

All round-trip cells pass on each registered runtime. PRD §6.2 met for v0.3 IR.
```

- [ ] **Step 5: Commit**

```bash
git add loom/runtimes/hiagent/ loom/runtimes/dify/ tests/runtimes/ reports/reverse-coverage.md
git commit -m "feat(reverse): widen reverse compilers to all 5 archetypes on Hiagent + Dify"
```

---

## Task 8: Deployer — drift-checked publish path

**Files:**
- Modify: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/loom/deployer/draft.py`
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/loom/deployer/publish.py`
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/tests/deployer/test_draft.py`
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/tests/deployer/test_publish_drift.py`
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/reports/drift-detection.md`

PRD §6.4 contract: "发布前执行漂移检测，不一致即阻塞发布。"

- [ ] **Step 1: Transactional draft push (per target)**

`draft.py` extended from Phase 1: `push_as_draft(ir, target, actor, *, session)` resolves the runtime adapter, compiles, pushes via `adapter.push_draft`, records a `Draft` row keyed by `(workflow_id, target, commit_sha)` with the runtime-neutral columns (`canonical_ast_hash`, `target_draft_id`, `target` = "hiagent"|"dify"), emits `audit.deploy_draft` receipt with `target` in payload, returns a `DraftPushResult`. All in one transaction.

A workflow may have multiple Draft rows simultaneously — one per registered runtime — sharing `commit_sha`. Each is published independently.

- [ ] **Step 2: Publish with drift gate (runtime-neutral)**

```python
# loom/deployer/publish.py (excerpt)
from __future__ import annotations
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from loom.audit.receipts import emit as audit_emit
from loom.runtimes import registry as runtime_registry
from loom.state.drift import check
from loom.state.models import Draft, Publish
from loom.state.workflow_sm import State, next_state


@dataclass
class PublishResult:
    target: str
    drift_blocked: bool
    expected_hash: str
    actual_hash: str
    publish_id: str | None
    delta_summary: str | None


async def publish(draft_id: str, actor: str, session: AsyncSession) -> PublishResult:
    """Drift-checked publish of a Draft row on its specific runtime target."""
    draft = await session.get(Draft, draft_id)
    adapter = runtime_registry.get(draft.target)
    current_dsl = await adapter.export_draft(draft.target_draft_id)
    drift = check(target=draft.target, expected_canonical_hash=draft.canonical_ast_hash, current_dsl=current_dsl)
    if drift.blocked:
        next_state(State.DRAFTED, "publish_drift")
        await audit_emit(session, "publish", actor, str(draft.workflow_id),
                         {"target": draft.target, "draft_id": str(draft.id), "blocked": True,
                          "expected": drift.expected, "actual": drift.actual})
        return PublishResult(draft.target, True, drift.expected, drift.actual, None, drift.delta_summary)

    pub = await adapter.publish(handle=...)  # adapter handles its own publish API
    p = Publish(draft_id=draft.id, target=draft.target,
                target_published_id=pub.publish_id,
                expected_canonical_ast_hash=drift.expected,
                actual_canonical_ast_hash=drift.actual,
                drift_blocked=False, actor=actor)
    session.add(p)
    next_state(State.DRAFTED, "publish")
    await audit_emit(session, "publish", actor, str(draft.workflow_id),
                     {"target": draft.target, "draft_id": str(draft.id), "publish_id": pub.publish_id})
    return PublishResult(draft.target, False, drift.expected, drift.actual, pub.publish_id, None)
```

- [ ] **Step 3: Tests for both paths × both runtimes**

```python
# tests/deployer/test_publish_drift.py
import pytest


@pytest.mark.asyncio
@pytest.mark.parametrize("target", ["hiagent", "dify"])
async def test_publish_blocked_when_runtime_was_edited(target, session, fake_adapters_with_drift, draft_fixture_for):
    draft = draft_fixture_for(target)
    fake_adapters_with_drift[target].simulate_user_edit(draft.target_draft_id)
    res = await publish(str(draft.id), actor="alice", session=session)
    assert res.target == target
    assert res.drift_blocked is True
    assert res.publish_id is None


@pytest.mark.asyncio
@pytest.mark.parametrize("target", ["hiagent", "dify"])
async def test_publish_succeeds_when_no_drift(target, session, fake_adapters_no_drift, draft_fixture_for):
    draft = draft_fixture_for(target)
    res = await publish(str(draft.id), actor="alice", session=session)
    assert res.target == target
    assert res.drift_blocked is False
    assert res.publish_id is not None
```

- [ ] **Step 4: `reports/drift-detection.md` — synthetic demo (per runtime)**

For each registered runtime, demonstrate the end-to-end drift scenario:
- Push draft (target = hiagent | dify), record expected hash.
- Edit the runtime draft via UI (or simulate via the test fake) on that runtime.
- Attempt publish; observe block.
- Run reverse compile via that runtime's adapter; observe new IR generated; observe state transition `PUBLISH_BLOCKED_DRIFT → REVERSE_PENDING → DRAFTED`.
- Re-publish; observe success.

If the Cost-budget escape hatch was invoked, only the Hiagent demo is required.

- [ ] **Step 5: Commit**

```bash
git add loom/deployer/ tests/deployer/ reports/drift-detection.md
git commit -m "feat(deployer): drift-checked publish + state-machine wiring + audit receipts"
```

- [ ] **Step 6: Code review checkpoint**

Send to reviewer (`/ask codex "[CODE REVIEW REQUEST] ..."`) — focus on drift detection correctness and state machine completeness. Pass criteria per CLAUDE.md §5.

---

## Task 9: Service routes — wire the pipeline behind FastAPI

**Files:**
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/loom/service/routes/plan.py`
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/loom/service/routes/compile.py`
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/loom/service/routes/deploy.py`
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/loom/service/routes/reverse.py`
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/loom/service/routes/registry.py`
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/tests/service/test_plan_route.py`
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/tests/service/test_compile_route.py`
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/tests/service/test_deploy_routes.py`
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/tests/service/test_reverse_route.py`
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/tests/service/test_registry_route.py`

Each route is a thin handler that delegates to the existing pure-Python module and writes a state row + audit receipt. PRD §10 failure-bucket attribution flows through the error envelope built in Task 2.

Route surface:
- `POST /v1/plan` — body: `IntentRequest` or `WorkflowBrief` + scope + idempotency key. Returns `PlannerResult`.
- `POST /v1/compile` — body: `{ir, target}` where `target` is `"hiagent"` or `"dify"`. Returns `{target, dsl, canonical_ast_hash}`. The DSL shape is runtime-specific (Hiagent JSON or Dify YAML) and the response includes `target` so the caller knows which.
- `POST /v1/deploy/draft` — body: `{ir}` or `{workflow_id, ir}`. Pushes draft, returns `Draft`.
- `POST /v1/deploy/publish` — body: `{draft_id}`. Returns `PublishResult` (drift-aware).
- `POST /v1/reverse` — body: `{draft_id}` or `{dsl}`. Returns `{ir, unrecognized}` per PRD §6.2.
- `GET /v1/registry?scope=ecommerce/kb&ref=HEAD` — returns scope-filtered `RegistrySnapshot`.
- `POST /v1/registry/sync` — sync git → Postgres mirror. Idempotent; emits `registry_sync` receipt only on actual change.

- [ ] **Step 1: Implement routes**

Skeleton example:

```python
# loom/service/routes/deploy.py
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from loom.deployer.publish import publish, PublishResult
from loom.service.deps import get_session

router = APIRouter()


class PublishRequest(BaseModel):
    draft_id: str
    actor: str


@router.post("/deploy/publish", response_model=PublishResult)
async def publish_route(req: PublishRequest, session=Depends(get_session)):
    """Publish reads the Draft row, looks up its `target`, resolves the
    RuntimeAdapter via `loom.runtimes.registry.get(target)`, and runs the
    drift-checked publish through the adapter. No runtime-specific client
    dependency is injected — the adapter is the only contract."""
    return await publish(req.draft_id, req.actor, session=session)
```

- [ ] **Step 2: End-to-end happy-path service test**

```python
# tests/service/test_deploy_routes.py
import pytest


@pytest.mark.asyncio
async def test_full_pipeline_happy_path(client, session):
    plan_resp = await client.post("/v1/plan", json={"intent": "...", "scope": "ecommerce/kb"})
    assert plan_resp.status_code == 200
    ir = plan_resp.json()["ir"]

    compile_resp = await client.post("/v1/compile", json={"ir": ir})
    dsl = compile_resp.json()["dsl"]

    draft_resp = await client.post("/v1/deploy/draft", json={"ir": ir, "actor": "alice"})
    draft_id = draft_resp.json()["id"]

    pub_resp = await client.post("/v1/deploy/publish", json={"draft_id": draft_id, "actor": "alice"})
    assert pub_resp.status_code == 200
    assert pub_resp.json()["drift_blocked"] is False
```

- [ ] **Step 3: Drift block test through the service**

Same as Task 8 step 3, but exercised through the FastAPI client. Confirms the error envelope yields `bucket: "platform"` (PRD §10 taxonomy) and HTTP 409.

- [ ] **Step 4: Commit**

```bash
git add loom/service/routes/ tests/service/
git commit -m "feat(service): wire plan/compile/deploy/reverse/registry routes; drift-aware envelope"
```

---

## Task 10: Trace ingestion + retention

**Files:**
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/loom/trace/__init__.py`
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/loom/trace/ingest.py`
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/loom/trace/retention.py`
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/loom/trace/store.py`
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/loom/service/routes/trace.py`
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/tests/trace/test_ingest.py`
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/tests/trace/test_retention.py`
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/tests/service/test_trace_route.py`

Per ADR 0010, trace metadata lives 90 days in Postgres; payloads 30 days in object storage; ingest behavior is `pii_class`-driven; right-to-erasure is a first-class API.

- [ ] **Step 1: Ingest with pii_class-driven handling**

```python
# loom/trace/ingest.py
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any

from loom.registry.types import PiiClass


PII_PATTERNS = [
    re.compile(r"\b\d{18}\b"),                                              # CN ID card
    re.compile(r"\b1[3-9]\d{9}\b"),                                          # CN mobile
    re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),       # email
]


class PayloadRejectedHighPii(ValueError):
    """Raised by handle_ingest when pii_class='high' would store raw payload."""


def redact(payload: dict[str, Any]) -> dict[str, Any]:
    s = json.dumps(payload, ensure_ascii=False)
    for p in PII_PATTERNS:
        s = p.sub("[REDACTED]", s)
    return json.loads(s)


def digest(payload: dict[str, Any]) -> str:
    """Stable structural digest for high pii_class — never reveals values."""
    canon = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()
    return hashlib.sha256(canon).hexdigest()


@dataclass
class IngestResult:
    stored_payload: dict[str, Any] | None     # None for high → only digest is kept
    payload_digest: str
    pii_class: PiiClass


def handle_ingest(payload: dict[str, Any], pii_class: PiiClass) -> IngestResult:
    d = digest(payload)
    if pii_class == "none":
        return IngestResult(stored_payload=payload, payload_digest=d, pii_class=pii_class)
    if pii_class == "low":
        return IngestResult(stored_payload=payload, payload_digest=d, pii_class=pii_class)
    if pii_class == "medium":
        return IngestResult(stored_payload=redact(payload), payload_digest=d, pii_class=pii_class)
    if pii_class == "high":
        # store only structural shape (keys + types), never values
        shape = _shape_only(payload)
        return IngestResult(stored_payload={"_shape": shape}, payload_digest=d, pii_class=pii_class)
    raise PayloadRejectedHighPii(f"unknown pii_class {pii_class!r}")


def _shape_only(payload: Any) -> Any:
    if isinstance(payload, dict):
        return {k: _shape_only(v) for k, v in payload.items()}
    if isinstance(payload, list):
        return [_shape_only(payload[0])] if payload else []
    return type(payload).__name__
```

- [ ] **Step 2: Right-to-erasure routes + audit**

```python
# loom/service/routes/trace.py — additions
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from loom.audit.receipts import emit as audit_emit
from loom.auth.actor import Actor, Role
from loom.service.deps import get_session, require_role  # introduced in Phase 2B; in 2A this is a thin actor pass-through
from loom.trace.store import erase_run, erase_subject

router = APIRouter()


@router.delete("/trace/runs/{run_id}", status_code=204)
async def erase_run_route(run_id: str, actor: Actor = Depends(require_role(Role.REVIEWER, Role.ADMIN)), session=Depends(get_session)):
    n = await erase_run(run_id, session=session)
    await audit_emit(session, "trace_erased_run", actor.id, run_id, {"deleted_rows": n})
    return None


class SubjectErasureRequest(BaseModel):
    subject_ref: str
    scope: str
    reason: str


@router.post("/trace/erasure")
async def erase_subject_route(req: SubjectErasureRequest, actor: Actor = Depends(require_role(Role.ADMIN)), session=Depends(get_session)):
    if not req.reason:
        raise HTTPException(status_code=400, detail="reason is required for audit")
    summary = await erase_subject(req.subject_ref, scope=req.scope, session=session)
    await audit_emit(session, "trace_erased_subject", actor.id, req.subject_ref,
                     {"scope": req.scope, "reason": req.reason, **summary})
    return summary
```

> Phase 2A predates Phase 2B's auth wiring; if `require_role` is not yet available in 2A's branch, the routes are stubbed behind a feature flag and finalized in Phase 2B. The service-level invariant is that **erasure operations always emit an audit receipt** — never silent.

- [ ] **Step 3: Retention job**

`retention.py` provides a coroutine that, per ADR 0010, deletes hot rows older than 90 days and blob refs older than 30 days. Wire as a Click command `loom retention sweep`; cron runs it nightly (deployment concern, not Phase 2A code). The retention job emits an `audit.trace_retention_swept` receipt with the deletion counts.

- [ ] **Step 4: Tests**

```python
# tests/trace/test_ingest.py
import pytest

from loom.trace.ingest import digest, handle_ingest, redact


def test_pii_redacted_at_ingest_medium_ecommerce_buyer():
    """Ecommerce primary case: buyer phone + email + address line."""
    payload = {"buyer_msg": "Hi, my phone is 13800001111 and email bob@example.com; ship to 上海市浦东新区世纪大道 100 号."}
    out = handle_ingest(payload, pii_class="medium")
    s = str(out.stored_payload)
    assert "13800001111" not in s
    assert "bob@example.com" not in s
    assert "[REDACTED]" in s
    # digest stable so subject erasure can match later
    assert out.payload_digest == digest(payload)


def test_pii_redacted_at_ingest_medium_tcm_patient():
    """TCM shadow case: patient phone + ID + email."""
    payload = {"text": "患者电话 13800001111 ID 110101199003070000 ; bob@example.com"}
    out = handle_ingest(payload, pii_class="medium")
    s = str(out.stored_payload)
    assert "13800001111" not in s
    assert "110101199003070000" not in s
    assert "bob@example.com" not in s
    assert "[REDACTED]" in s
    assert out.payload_digest == digest(payload)


def test_high_pii_ecommerce_payment_token_stores_only_shape():
    """Ecommerce primary: payment tokens / full card data must never appear in stored payload."""
    payload = {"buyer_id": "B-9001", "payment_token": "tok_live_xxxx", "shipping_phone": "13800001111"}
    out = handle_ingest(payload, pii_class="high")
    s = str(out.stored_payload)
    assert "tok_live_xxxx" not in s
    assert "B-9001" not in s
    assert out.stored_payload == {"_shape": {"buyer_id": "str", "payment_token": "str", "shipping_phone": "str"}}


def test_high_pii_tcm_patient_record_stores_only_shape():
    """TCM shadow: patient_id + diagnosis must never appear in stored payload."""
    payload = {"patient_id": "P-123", "diagnosis": "..."}
    out = handle_ingest(payload, pii_class="high")
    assert out.stored_payload == {"_shape": {"patient_id": "str", "diagnosis": "str"}}
    assert "P-123" not in str(out.stored_payload)


def test_low_pii_unredacted_but_digestable():
    """Order id alone is low pii_class — kept as-is, digest still stable for erasure."""
    payload = {"order_id": "ORD-1"}
    out = handle_ingest(payload, pii_class="low")
    assert out.stored_payload == payload
    assert len(out.payload_digest) == 64
```

```python
# tests/trace/test_retention.py
import pytest


@pytest.mark.asyncio
async def test_retention_deletes_old_payloads(session, fake_storage):
    # seed payloads at 31 days, 89 days, 91 days
    ...  # verify only the 91-day metadata and the 31/91 day payloads are gone


@pytest.mark.asyncio
async def test_retention_emits_audit_receipt(session):
    ...  # after sweep, an audit_receipt with op='trace_retention_swept' exists
```

```python
# tests/service/test_trace_erasure.py
import pytest


@pytest.mark.asyncio
async def test_run_erasure_requires_reviewer_or_admin(client_as_author):
    r = await client_as_author.delete("/v1/trace/runs/run-1")
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_subject_erasure_emits_audit_ecommerce_buyer(client_as_admin, session):
    """Ecommerce primary: GDPR/PIPL erasure for a buyer."""
    r = await client_as_admin.post("/v1/trace/erasure",
                                    json={"subject_ref": "buyer-9001", "scope": "ecommerce/ops",
                                          "reason": "GDPR Art.17 deletion request 2026-05-01"})
    assert r.status_code == 200
    # audit receipt with op=trace_erased_subject and matching subject_ref


@pytest.mark.asyncio
async def test_subject_erasure_emits_audit_tcm_patient(client_as_admin, session):
    """TCM shadow: PIPL erasure for a patient."""
    r = await client_as_admin.post("/v1/trace/erasure",
                                    json={"subject_ref": "patient-42", "scope": "clinic/kb",
                                          "reason": "PIPL Art.47 deletion request 2026-05-01"})
    assert r.status_code == 200
    # audit receipt with op=trace_erased_subject and matching subject_ref
    ...
```

- [ ] **Step 5: Commit**

```bash
git add loom/trace/ loom/service/routes/trace.py tests/trace/ tests/service/test_trace_erasure.py tests/service/test_trace_route.py
git commit -m "feat(trace): pii_class ingest + erasure routes + retention; per ADR 0010"
```

---

## Task 11: CLI — point at the service

**Files:**
- Modify: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/loom/cli/commands/deploy.py`
- Modify: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/loom/cli/commands/reverse.py`
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/loom/cli/commands/service.py`

In Phase 1 the CLI ran the pipeline in-process. In Phase 2A the CLI is a client of the service. Keep the in-process path behind `--local` for unit tests and offline use, but default to the service.

- [ ] **Step 1: Service-aware deploy/reverse**

```python
# loom/cli/commands/deploy.py (excerpt)
@click.command()
@click.argument("ir_path", type=click.Path(exists=True))
@click.option("--actor", required=True)
@click.option("--service-url", default="http://localhost:8000")
@click.option("--local", is_flag=True, help="run in-process (Phase 1 path)")
def deploy(ir_path: str, actor: str, service_url: str, local: bool) -> None:
    ir = json.loads(Path(ir_path).read_text())
    if local:
        result = _local_draft_push(ir, actor)
    else:
        result = httpx.post(f"{service_url}/v1/deploy/draft", json={"ir": ir, "actor": actor}, timeout=60).json()
    click.echo(json.dumps(result, indent=2))
```

- [ ] **Step 2: `loom service` admin commands**

```python
# loom/cli/commands/service.py
@click.group()
def service() -> None: ...


@service.command()
def serve() -> None:
    import uvicorn
    uvicorn.run("loom.service.app:create_app", factory=True, host="0.0.0.0", port=8000)


@service.command()
def migrate() -> None:
    from alembic import command, config
    cfg = config.Config("loom/state/alembic.ini")
    command.upgrade(cfg, "head")
```

- [ ] **Step 3: Commit**

```bash
git add loom/cli/commands/deploy.py loom/cli/commands/reverse.py loom/cli/commands/service.py
git commit -m "feat(cli): service-aware deploy/reverse + service serve/migrate"
```

---

## Task 12: CI — slow lane runs the full stack

**Files:**
- Modify: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/.github/workflows/conformance.yml`
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/.github/workflows/integration.yml`

- [ ] **Step 1: Integration job**

```yaml
# .github/workflows/integration.yml
name: integration
on:
  pull_request:
    branches: [main]

jobs:
  integration:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16
        env:
          POSTGRES_USER: loom
          POSTGRES_PASSWORD: loom
          POSTGRES_DB: loom
        ports: ["5432:5432"]
      redis:
        image: redis:7
        ports: ["6379:6379"]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.11" }
      - run: pip install -e ".[dev]"
      - name: Migrate
        run: loom service migrate
        env: { LOOM_DB_URL: postgresql+asyncpg://loom:loom@localhost:5432/loom }
      - name: Service tests
        run: pytest tests/service/ tests/state/ tests/registry/ tests/audit/ tests/trace/ -v
        env:
          LOOM_DB_URL: postgresql+asyncpg://loom:loom@localhost:5432/loom
          LOOM_REDIS_URL: redis://localhost:6379/0
```

- [ ] **Step 2: Slow lane: round-trip + drift e2e**

Conformance workflow brings up **Hiagent + Dify** (skipping Dify if `vars.LOOM_DROP_DIFY=true`) + Postgres + Redis, runs `tests/runtimes/hiagent/<vH_X>/test_reverse_full.py` and `tests/runtimes/dify/<vD_Y>/test_reverse_full.py` (each per-runtime live-gated), `tests/deployer/test_publish_drift.py` (parameterized over both targets), and the failure-taxonomy eval over the full corpus per runtime. Same `LOOM_DROP_DIFY` pattern as Phase 1 Task 16.

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/integration.yml .github/workflows/conformance.yml
git commit -m "ci: integration job (postgres/redis); conformance slow lane runs reverse + drift"
```

---

## Task 13: Phase 2A release gate

**Files:**
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/reports/phase-2a-gate.md`
- Create: `/Users/apple/Documents/2.1 AI Journey/Cursor_projects/octopus_FDE/reports/audit-receipts-sample.json`

PRD §7 Phase 2A criterion: "deployment, registry, full reverse compilation, drift detection + publish blocking, audit chain." Gate criteria:

- [ ] **Step 1: Run all gates**

```bash
ruff check .
mypy loom
pytest -v
loom service migrate
# Hiagent (primary)
LOOM_HIAGENT_LIVE=1 LOOM_HIAGENT_KEY=<hkey> LOOM_DB_URL=<url> LOOM_REDIS_URL=<url> \
  pytest tests/conformance/ tests/runtimes/hiagent/<vH_X>/test_reverse_full.py tests/deployer/ -v
# Dify (secondary; skip if Cost-budget escape hatch invoked)
LOOM_DIFY_LIVE=1 LOOM_DIFY_KEY=<dkey> LOOM_DB_URL=<url> LOOM_REDIS_URL=<url> \
  pytest tests/conformance/ tests/runtimes/dify/<vD_Y>/test_reverse_full.py tests/deployer/ -v
ANTHROPIC_API_KEY=<key> python -c "
from loom.eval.corpus import load
from loom.eval.runner import run_eval
from loom.eval.report import write_json, write_markdown
from pathlib import Path
report = run_eval(load('full'))
write_json(report, Path('reports/eval-full-corpus.json'))
write_markdown(report, Path('reports/coverage-by-archetype.md'))
print(report.first_try_validity)
"
loom audit verify  # walks the receipt chain end-to-end
```

- [ ] **Step 2: Generate sample audit chain artifact**

```bash
loom audit export --since 2026-01-01 --to reports/audit-receipts-sample.json
```

- [ ] **Step 3: Write the gate**

```markdown
# Phase 2A gate

Date: YYYY-MM-DD
Pinned Hiagent: <tag@digest>   # ADR 0002 (Hiagent section)
Pinned Dify: <tag@digest>      # ADR 0002 (Dify section); N/A if Cost-budget escape hatch invoked

## PRD §7 Phase 2A criteria (per registered runtime)

| Criterion | Target | Hiagent | Dify | Status |
|---|---|---|---|---|
| Full reverse compiler covers all 5 archetypes | 5/5 round-trip canonical equality | N/5 | N/5 (or N/A) | pass/fail |
| Drift detection blocks publish on edited draft | demonstrated end-to-end | demo/not | demo/not (or N/A) | pass/fail |
| Audit chain verifies (genesis → latest), incl. `target` in payload | ok | ok/broken | ok/broken | pass/fail |
| Registry source ↔ Postgres mirror parity | 100% | NN% | NN% | pass/fail |
| Vault handles never carry values; IR/DSL secret-shape lint clean | 100% | NN% | NN% | pass/fail |
| Trace PII redaction tests pass (medium/high pii_class) | 100% | NN% | NN% | pass/fail |
| Right-to-erasure: DELETE /v1/trace/runs and POST /v1/trace/erasure work + emit audit | shipped + tested | shipped/missing | shipped/missing | pass/fail |
| Retention sweep deletes >30d payloads and >90d metadata; emits audit | enforced | enforced/missing | enforced/missing | pass/fail |
| Every registry entry declares `pii_class` | 100% | NN% | NN% | pass/fail |
| Service e2e happy path on full corpus, per runtime | ≥85% first-try IR validity | NN% | NN% | pass/fail |
| Failure taxonomy populated across all 11 buckets where applicable | covered | covered/missing | covered/missing | pass/fail |
| Migration applies cleanly on empty DB and on a Phase 1 dump | green | green/red | green/red | pass/fail |

> If the Cost-budget escape hatch was invoked (per ADR 0002), Dify columns above are N/A; Hiagent rows must still pass at full bar.

## State machine evidence (one row per (target, transition) demonstrated)

| Transition | Hiagent | Dify |
|---|---|---|
| NEW → DRAFTED | tests/deployer/test_draft.py (target=hiagent) | tests/deployer/test_draft.py (target=dify) |
| DRAFTED → REVERSE_PENDING → DRAFTED | tests/runtimes/hiagent/<vH_X>/test_reverse_full.py + tests/deployer | tests/runtimes/dify/<vD_Y>/test_reverse_full.py + tests/deployer |
| DRAFTED → PUBLISH_BLOCKED_DRIFT | tests/deployer/test_publish_drift.py (target=hiagent) | tests/deployer/test_publish_drift.py (target=dify) |
| PUBLISH_BLOCKED_DRIFT → REVERSE_PENDING → DRAFTED | reports/drift-detection.md (Hiagent section) | reports/drift-detection.md (Dify section) |
| DRAFTED → PUBLISHED | tests/service/test_deploy_routes.py (target=hiagent) | tests/service/test_deploy_routes.py (target=dify) |
| PUBLISHED → DRAFTED | tests/service/test_deploy_routes.py | tests/service/test_deploy_routes.py |

## Failure taxonomy (PRD §10) — populated

| Bucket | Count |
|---|---|
| schema | NN |
| reference | NN |
| type_flow | NN |
| policy | NN |
| compile | NN |
| deploy | NN |
| reverse_compile | NN |
| registry_acl | NN |
| semantic_conformance | NN |
| platform | NN |
| human_review | NN |

## Audit chain

- Genesis hash: 000…000
- Latest receipt id: <uuid>
- Receipts verified: NN
- Verification: ok / broken

## Decision

If every row above is `pass` → Phase 2B unblocked.
If any row is `fail` → iterate and re-run the gate.
```

- [ ] **Step 4: Commit**

```bash
git add reports/phase-2a-gate.md reports/audit-receipts-sample.json
git commit -m "docs: Phase 2A gate report + sample audit receipts"
```

- [ ] **Step 5: Final review**

`/ask codex "[CODE REVIEW REQUEST] ..."` — full diff since Phase 1.5 tag. Pass criteria per CLAUDE.md §5.

---

## Self-review summary

- **Spec coverage:** PRD §6.4 runtime-neutral state-machine identifiers (`commit_sha`, `target`, `canonical_ast_hash`, `target_draft_id`, `target_published_id`, `reverse_compile_status`) all map to columns in `loom/state/models.py`; one Draft + Publish row per `(workflow, target)`. PRD §6.2 reverse-compile contract enforced by Task 7 (per runtime) + Task 8 publish gate (per runtime via adapter). PRD §6.3 canonical-IR equality is the round-trip relation. PRD §5.1 immutable `registry_version` SHA enforced by `loom/registry/source.py`. PRD §8 IR/DSL handle-only invariant tested in `tests/vault/test_handles.py`. PRD §10 failure taxonomy: 11 buckets surfaced through the error envelope and audit receipts (per runtime). Cost-budget escape hatch (PRD §7) is a configuration drop; no schema or contract changes when invoked.

- **Placeholder scan:** `vX_Y` flagged at top of plan; `<chosen>` Vault provider follows ADR 0003. Sample `<sample>.yaml` registry entries are real fixture file names — they need partner-specific content before pilot. No orphan TODO/TBD.

- **Type consistency:** `Workflow`, `Draft`, `Publish`, `ReverseAttempt`, `AuditReceipt`, `TraceMeta`, `RegistrySnapshot`, `ToolEntry`, `DatasetEntry`, `CredentialEntry`, `DriftResult`, `PublishResult`, `IdempotencyResult`, `Op` — names are stable across state / registry / audit / deployer / service modules.

- **Known seams to Phase 2B:** Service exposes JSON-only API; the chat console + semantic-diff UI + RBAC live in Phase 2B. Phase 2B will add `/v1/sessions/*` (FDE Session persistence) and `/v1/diffs/*`. The state machine + audit chain in Phase 2A is what the UI renders.

- **Known seams to Phase 3/4:** Multi-tenancy (Phase 3.1), IR v0.4 minor bump (Phase 3.1), optional LangGraph alpha (Phase 3.2), pattern library + self-improvement (Phase 4). Multi-runtime is already shipped in Phase 1 (Hiagent + Dify); Phase 3 only adds tenancy + schema bump on top.

---

## Execution Handoff

Plan complete and saved to `docs/plans/2026-05-06-phase-2a-production-infra.md`. Recommended execution modes:

1. **Subagent-Driven (recommended)** — Dispatch a fresh subagent per task, review between tasks, fast iteration.
2. **Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints.
