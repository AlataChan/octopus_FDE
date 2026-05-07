# Conformance baseline against pinned Dify

**Status:** `deferred_to_first_customer_integration` (per Phase 0 plan MVP scope clarification, 2026-05-07)
**Date:** N/A (not yet executed)
**Dify pin:** `1.14.0` (per ADR 0002)
**Deployment model:** self-hosted-docker on customer-owned cloud VM (per ADR 0002, post-2026-05-07-cloud-pivot revert)

## Why this is deferred

The MVP scope for v1 is **NL → Planner → IR → Compiler → YAML file**: FDE generates DSL artifacts that the operator imports manually into their self-hosted Dify console. FDE does not auto-push, does not operate a Dify instance, and does not require a live Dify endpoint to ship the MVP.

Phase 0 Task 14 originally specified a live conformance baseline run: hand-author a Dify YAML for each PRD §5 cell, push to a pinned Dify, run with case inputs, populate the cell table in ADR 0002. That work depends on a reachable Dify 1.14.0 endpoint with operator credentials. Under the MVP path, the first such endpoint becomes available at first customer integration — at which point this report is regenerated end-to-end against the customer's environment.

## Matrix cell results

Each row maps to one of the 10 PRD §5 cells defined in `loom/conformance/matrix.py`. Cells stay `deferred` until live execution; the row IDs and case factories are already shaped so the run is mechanical when the endpoint is in place.

| Row | Status | Notes |
|---|---|---|
| `loop_max_iterations` | deferred_to_first_customer_integration | factory ready in `loom.conformance.matrix.case_loop_max_iterations` |
| `parallel_concat` | deferred_to_first_customer_integration | factory ready |
| `parallel_object_merge` | deferred_to_first_customer_integration | factory ready |
| `parallel_first_success` | deferred_to_first_customer_integration | factory ready |
| `agent_budget_fallback` | deferred_to_first_customer_integration | factory ready |
| `agent_output_schema` | deferred_to_first_customer_integration | factory ready |
| `http_retry_on` | deferred_to_first_customer_integration | factory ready |
| `node_timeout` | deferred_to_first_customer_integration | factory ready |
| `http_idempotency` | deferred_to_first_customer_integration | factory ready |
| `condition_truthiness` | deferred_to_first_customer_integration | factory ready |

## Flake rate

Not measured (not yet executed against live runtime).
Target: ≥ 30 runs, < 2% flake rate when this report is regenerated. > 5% blocks release per PRD §10.

## Action items

- **At first customer integration:** export `LOOM_DIFY_LIVE=1`, set `LOOM_DIFY_KEY` to the customer-provided token, set base URL to the customer's self-hosted Dify endpoint, run `pytest tests/conformance -v`. Fill in this table from results. Update ADR 0002 cell table from per-row wrapper-needed observations.
- **Companion deferred Phase 0 evidence rows:**
  - Task 15 (round-trip canonicalization N=10) — same deferral, same trigger.
  - Task 16 (reverse-compile spike on one archetype) — same.
  - Task 17 (one reviewer-edit simulation) — same.
- **Hiagent equivalent (Phase 1 Task 11.5):** when Hiagent compiler ships, this same report regenerates against Hiagent Cloud with the same matrix.

## Cost-budget escape hatch

If the project owner invokes the escape hatch at first customer integration (per ADR 0002 amendment), Dify rows here become N/A; Hiagent rows from the Phase 1 Task 11.5 conformance run become the v1 baseline.
