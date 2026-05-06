#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
docker compose -f docker/hiagent-pinned/docker-compose.yml up -d
echo "Waiting for Hiagent API…"
for i in {1..60}; do
  if curl -fsS http://localhost:32301/health >/dev/null 2>&1; then
    echo "Hiagent API up."
    exit 0
  fi
  sleep 2
done
echo "Hiagent API did not come up in time." >&2
exit 1
