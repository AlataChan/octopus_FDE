.PHONY: phase0-gate test lint type all web-dev web-build serve ship docker-up docker-down

IMAGE ?= fde-console
TAG ?= $(shell git rev-parse --short HEAD)

all: lint type test

lint:
	ruff check .

type:
	mypy loom

test:
	pytest -v

phase0-gate:
	@echo "Phase 0 gate is a manual report — see reports/phase-0-gate.md."
	@echo "Re-run scripts/security_review.py and (when live infra arrives)"
	@echo "scripts/round_trip_proof.py and scripts/reverse_compile_spike.py to refresh artifacts."

web-dev:
	npm --prefix web run dev

web-build:
	npm --prefix web run build

serve:
	APP_ENV=$${APP_ENV:-dev} .venv/bin/uvicorn loom.service.app:app --host 127.0.0.1 --port 8000

ship:
	docker build -t $(IMAGE):$(TAG) -t fde-console:latest .
	@echo "Built $(IMAGE):$(TAG)"
	@echo "Generate key: python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'"
	@echo "Then: export LOOM_FERNET_KEY=<key> && docker compose up -d"
	@echo "Open http://localhost:8000 after the service is healthy."

docker-up:
	docker compose up -d --build

docker-down:
	docker compose down
