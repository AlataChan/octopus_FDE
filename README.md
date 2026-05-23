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
export LOOM_AUTH_USERNAME='admin'
export LOOM_AUTH_PASSWORD_HASH="$(python -c 'import os,hashlib,base64,getpass; pw=getpass.getpass("Password: ").encode(); salt=os.urandom(16); h=hashlib.scrypt(pw,salt=salt,n=2**14,r=8,p=1,dklen=32,maxmem=128*1024*1024); print(f"scrypt$16384$8$1${base64.b64encode(salt).decode()}${base64.b64encode(h).decode()}")')"
export LOOM_INSTANCE_ID='local-fde'
export LOOM_DATA_DIR=./.loom-data
docker compose up -d --build
curl http://localhost:18080/v1/health
```

Open `http://localhost:18080` and sign in with `LOOM_AUTH_USERNAME` plus the
password used to generate `LOOM_AUTH_PASSWORD_HASH`. Docker runs uvicorn with a
single worker because auth sessions are stored in process memory.

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

Headless automation helpers:

- `loom brief [INTENT_FILE] --scope <scope> [--target hiagent|dify] [--draft-json path]`
  runs a dry-run Self-Design missing-field probe. Exit `0` means ready, exit
  `1` means blocking fields remain and is a normal CI branch, and exit `2`
  means invalid input or redaction trip.
- `loom session show-turns <session-id> --actor <actor> [--json]` lists safe
  turn metadata only; raw messages, IR snapshots, planner replies, and
  validation internals are intentionally omitted.
- `loom session brief <session-id> --actor <actor>` prints the stored redacted
  brief draft plus clarify state for offline inspection.

## Pinned Runtimes

ADR 0002 pins Hiagent 2.6 and Dify 1.14.0. Hiagent ZIP import format is
documented in `docs/runtimes/hiagent/zip-import-format.md`.
