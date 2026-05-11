# M2.2 Smoke Checklist — FDE Session Console MVP

1. Start the backend with `APP_ENV=dev .venv/bin/uvicorn loom.service.app:app`.
2. Start the frontend with `cd web && npm run dev`.
3. Open `http://127.0.0.1:5173/` and confirm the sessions list renders.
4. Create a new session and confirm the browser navigates to `/sessions/<id>`.
5. In the first-run BYOK modal, save `api_key`, `base_url`, and `model`.
6. Send one Planner message and wait for the non-streaming turn to complete.
7. Confirm the middle IR panel shows the current IR as read-only YAML-like text.
8. Select `hiagent` + `chatflow` + a Hiagent binding, compile, and download the ZIP artifact.
9. Select `dify`, compile, and download the YAML artifact.
10. On an artifact card, fill `platform_app_id` and a note, then mark it imported.

M2.2 intentionally does not cover streaming, graph visualization, IR diff UI, rich validation display, visual polish, or browser E2E automation.
