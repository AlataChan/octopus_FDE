# ADR 0025: SQLite State Store for FDE Web Console

Status: Accepted

Date: 2026-05-10

## Context

Phase 2 ships a single-tenant, multi-user FDE Web Console. The user explicitly
cut Postgres and Alembic from the MVP, but the backend still needs durable
sessions, turn history, BYOK LLM config, and artifact metadata.

## Decision

Use SQLite for the Phase 2 session store at `<DATA_DIR>/sessions.db`.

The store owns:

- sessions: state, actor id, accepted IR pointer, encrypted BYOK config
- turns: `running | succeeded | failed`, `ir_before`, `ir_after`, validation errors
- artifacts: UUID-addressed artifact metadata and server-side relative path

SQLite is configured with:

- `PRAGMA journal_mode=WAL`
- `PRAGMA busy_timeout=5000`
- short write transactions only
- no database transaction held across planner LLM calls

BYOK API keys are encrypted at rest with `cryptography.fernet`.

- `APP_ENV=dev`: missing `LOOM_FERNET_KEY` creates an ephemeral per-process key
  with a startup warning.
- `APP_ENV=prod`: missing `LOOM_FERNET_KEY` is a startup error.
- `llm_key_version` is stored for future manual key rotation.

Artifact download is addressed only by `(session_id, artifact_id)` UUIDs.
Filesystem paths never cross the API boundary.

## Consequences

- Local MVP deployment stays simple and portable.
- SQLite write contention is acceptable for the expected single-tenant MVP load.
- Moving to Postgres in Phase 3 remains possible because repository boundaries
  isolate persistence details.
- Losing or rotating `LOOM_FERNET_KEY` makes stored BYOK credentials
  undecryptable; users re-enter keys per session.
