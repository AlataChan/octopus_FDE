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
