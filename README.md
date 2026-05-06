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
