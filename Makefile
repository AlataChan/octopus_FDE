.PHONY: phase0-gate test lint type all

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
