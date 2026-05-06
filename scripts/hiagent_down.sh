#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
docker compose -f docker/hiagent-pinned/docker-compose.yml down -v
