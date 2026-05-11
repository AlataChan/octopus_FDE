.PHONY: phase0-gate test lint type all web-dev web-build serve

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
