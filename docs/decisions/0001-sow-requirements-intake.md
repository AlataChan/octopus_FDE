# ADR 0001 — SOW / requirements intake

**Status:** Accepted
**Date:** 2026-05-06

## Decision

FDE Session starts with a SOW / requirements intake before Workflow Brief generation.

Required fields:
- `sow_id`
- `persona_id`
- `business_goal`
- `target_runtime`: `hiagent` | `dify`
- `vertical`: `ecommerce` | `tcm_shadow` | `<other>`
- `workflow_candidates`: 5 candidate workflows with trigger, inputs, outputs, tools/datasets, reviewer policy, success criteria
- `credential_bindings`: platform LLM bindings + HTTP auth bindings
- `reviewer_policy`
- `success_metrics`

Synthetic-partner mode is valid: if no real partner is ready, use a Bambu Lab-style cross-border ecommerce operator profile to fill the SOW and move engineering forward.

## Context

The previous external partner confirmation gate was too heavy. Partner context is an input to FDE, not a prerequisite to building FDE. The SOW contract gives Planner / Persona Brief / Workflow Brief a stable input shape.

## Initial synthetic SOW

Use cross-border ecommerce operations as the default synthetic SOW:
1. ecommerce customer FAQ / KB Q&A
2. ecommerce order-exception triage
3. product-content localization
4. after-sales escalation
5. operations reporting

TCM clinic workflows remain shadow corpus inputs, not the primary SOW.

## Replacement by real partner

When a real partner exists, write a new SOW file under `sow/<partner>/<sow_id>.yaml`; do not rewrite the contract.

## Consequences

- Phase 0 examples are derived from the SOW, not from an implicit external-partner assumption.
- Persona Brief and Workflow Brief both consume this intake shape.
