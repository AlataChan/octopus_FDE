# FDE Console Deploy Guide

FDE Console is a single FastAPI service with the React web build mounted at `/`.
Runtime state lives only in `LOOM_DATA_DIR`: `sessions.db`,
`workflow_registry.db`, archive JSONL, and generated artifacts.

## Path A — Docker [Recommended]

1. Generate a Fernet key and keep it with your deployment secrets:

   ```bash
   python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'
   export LOOM_FERNET_KEY='<generated-key>'
   export LOOM_AUTH_USERNAME='admin'
   export LOOM_AUTH_PASSWORD_HASH="$(python -c 'import os,hashlib,base64,getpass; pw=getpass.getpass("Password: ").encode(); salt=os.urandom(16); h=hashlib.scrypt(pw,salt=salt,n=2**14,r=8,p=1,dklen=32,maxmem=128*1024*1024); print(f"scrypt$16384$8$1${base64.b64encode(salt).decode()}${base64.b64encode(h).decode()}")')"
   export LOOM_INSTANCE_ID='local-fde'
   ```

2. Choose a persistent data directory:

   ```bash
   export LOOM_DATA_DIR=./.loom-data
   mkdir -p "$LOOM_DATA_DIR"
   chmod 700 "$LOOM_DATA_DIR"
   ```

3. Start the service:

   ```bash
   docker compose up -d --build
   curl http://localhost:18080/v1/health
   ```

4. Open `http://localhost:18080` and sign in with the configured local account.

Customer binding files are read from `config/customers/`, mounted read-only into
the container. Keep real customer bindings out of Git; commit only examples.

## Path B — Dev / Hacking

Use this path for frontend changes. Do not rebuild the Docker image for every UI
edit.

```bash
source .venv/bin/activate
APP_ENV=dev make serve
make web-dev
```

The Vite dev server runs on `http://127.0.0.1:5173`; set
`LOOM_CORS_ALLOW_ORIGINS=http://127.0.0.1:5173,http://localhost:5173` when
running an auth-enabled backend for frontend development. To build the frontend once:

```bash
make web-build
```

## Backup / Restore `DATA_DIR`

Back up the whole data directory:

```bash
tar -czf fde-data-backup.tgz "$LOOM_DATA_DIR"
```

Restore on a new host:

```bash
mkdir -p "$LOOM_DATA_DIR"
tar -xzf fde-data-backup.tgz -C "$(dirname "$LOOM_DATA_DIR")"
docker compose up -d
```

Backups include encrypted BYOK credentials. They are only usable with the same
`LOOM_FERNET_KEY`. If the key is lost, users must re-enter LLM credentials in
new sessions.

## Data Portability

The workflow registry is a separate SQLite DB at
`<DATA_DIR>/workflow_registry.db`; archive events are size-rotated JSONL files
under `<DATA_DIR>/archive/`.

Phase 3 migration note: when multi-tenancy lands, SQLite is expected to move to
Postgres and backup/restore changes to `pg_dump` / restore procedures.
