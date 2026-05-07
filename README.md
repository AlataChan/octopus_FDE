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

## Pinned runtimes (cloud SaaS)

ADR 0002 pins Hiagent Cloud (primary) and Dify Cloud (secondary) at API version `v1`. Both runtimes are cloud SaaS — no local docker required. Configure endpoints + auth tokens in `config/runtimes.yaml` (template at `config/runtimes.example.yaml`):

    cp config/runtimes.example.yaml config/runtimes.yaml
    # then export your Cloud API tokens:
    export HIAGENT_CLOUD_TOKEN=...
    export DIFY_CLOUD_TOKEN=...

Phase 0 engineering evidence runs against pinned Dify Cloud; the Hiagent Cloud equivalent ships in Phase 1 Task 11.5. If running both runtimes is too costly, ADR 0002's escape hatch permits Hiagent-only mode by `loom.runtimes.registry.unregister("dify")`.
