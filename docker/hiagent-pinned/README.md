# Pinned Hiagent

This directory contains the docker-compose definition for the **only** Hiagent version FDE claims compliance with at this point in time.

This README is a placeholder shape; vendor-provided self-hosted artifact replaces image + digest fields.

The pinned tag is `2.6`; image digests and the upstream compose source are recorded in `docs/decisions/0002-runtime-versions.md` after pull. Do not bump them without:
1. Updating the ADR.
2. Re-running the full conformance matrix on Hiagent (and re-running parity vs Dify).
3. Updating the per-minor-version Compiler module under `loom/runtimes/hiagent/v2_6/` or a new explicit version directory.

## Run

    bash scripts/hiagent_up.sh
    # Console: http://localhost:32300
    # OpenAPI: http://localhost:32301

    bash scripts/hiagent_down.sh
