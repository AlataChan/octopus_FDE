# FDE

Deterministic, reviewable AI workflows. FDE engineers use the browser console to
chat with the Planner, produce IR, compile Hiagent/Dify artifacts, download
them, and manually import them into customer runtimes.

![FDE Console screenshot placeholder](data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII=)

See `docs/PRD.md` for the full spec.

## Docker Quickstart

```bash
python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'
export LOOM_FERNET_KEY='<generated-key>'
export LOOM_DATA_DIR=./.loom-data
docker compose up -d --build
curl http://localhost:8000/v1/health
```

Open `http://localhost:8000`.

Docker is the primary deployment path. Runtime data lives in `LOOM_DATA_DIR`;
the image does not contain sessions DBs, archive JSONL, generated artifacts, or
real customer bindings.

## Dev Quickstart

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
npm --prefix web install
APP_ENV=dev make serve
make web-dev
```

Use the dev path for frontend changes; do not rebuild Docker for every UI edit.

## CLI Relationship

The `loom` CLI remains useful for local compile/validate workflows and runtime
investigation. The web console is the primary Phase 2 FDE operator surface.
Both use the same IR validators and runtime compilers.

## Pinned Runtimes

ADR 0002 pins Hiagent 2.6 and Dify 1.14.0. Hiagent ZIP import format is
documented in `docs/runtimes/hiagent/zip-import-format.md`.
