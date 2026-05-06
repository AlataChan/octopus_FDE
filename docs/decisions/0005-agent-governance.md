# ADR 0005 — Agent governance defaults

**Status:** Accepted
**Date:** 2026-05-06

## Decision

Workflow-level `policy.agent_budget` defaults (PRD §5):

| Field | Default | Per-node tighten allowed | Per-node loosen allowed |
|---|---|---|---|
| `max_iterations` | 10 | yes | no |
| `max_tokens` | 50000 | yes | no |
| `max_wall_clock_s` | 300 | yes | no |

LLM call defaults:

| Field | Default |
|---|---|
| `max_output_tokens` | 8000 |
| `temperature` | node-specific; default 0 for planning / validation-sensitive calls |

Runtime import behavior:
- FDE emits default settings into YAML / JSON / ZIP where the target runtime supports them.
- After import, the operator may adjust platform-side settings before publish.
- Any operator-side change is captured by reverse compile / drift detection before publish.

Tool side-effect policy:
- Tools with `side_effects: true` in the registry require an `idempotency_key` on every invocation.
- Side-effecting tool calls are audited to the trace store with `(tool, args, result, latency)` (PRD §5 agent contract).

## Context

The first build should not block on organization-specific budget policy. Use conservative defaults, import them, and let the operator adjust in the target platform.

## Consequences

- The Validator (Phase 1) rejects agents whose budget exceeds the workflow `policy.agent_budget`.
- The conformance matrix has a row for "agent budget exhaustion → fallback edge taken."
- Trace storage (Phase 2A) carries the audit fields above.
