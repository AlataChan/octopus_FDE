# FDE Console User Guide

![FDE Console screenshot placeholder](data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII=)

## 1. Start Docker

```bash
python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'
export LOOM_FERNET_KEY='<generated key>'
export LOOM_AUTH_USERNAME='admin'
export LOOM_AUTH_PASSWORD_HASH='<scrypt hash>'
docker compose up -d --build
```

Open `http://localhost:18080` and sign in with the configured local account.

## 2. Create A Session

Click “New session” on the home page. The console opens the session detail view.

## 3. Enter BYOK Credentials

The first visit to a session opens the LLM configuration modal:

- API Key
- Base URL
- Model

FDE stores the key encrypted in local SQLite and never injects it into generated
Hiagent or Dify artifacts.

## 4. Chat With The Planner

Enter the workflow intent in the left panel and wait for the non-streaming
Planner call to complete. The current IR appears in the center panel.

## 5. Review IR, Diff, And Validator Errors

- Current IR is displayed as read-only YAML-like text.
- After two successful turns, expand the IR changes list.
- Validator errors render as cards; clicking a path highlights the related IR field.

## 6. Compile And Download

Use the bottom Compile Bar:

- `hiagent` + `chatflow` downloads a ZIP.
- `dify` downloads YAML.

## 7. Import Manually

Drag the ZIP into Hiagent’s agent import wizard, or import the YAML in Dify UI.
FDE does not auto-upload artifacts.

## 8. Mark Imported

After manual import, fill platform App ID and a note on the artifact card, then
click “Mark imported”. This records the deployment in the workflow registry.
