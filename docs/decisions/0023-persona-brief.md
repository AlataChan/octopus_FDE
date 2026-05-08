# ADR 0023 — Persona Brief as first FDE Session step

Status: Accepted
Date: 2026-05-08

## Decision

The FDE Session has two briefs, in order:

1. **Persona Brief** (NEW): captures Author role / vertical / End User / Reviewer / compliance boundary. Resolved against `registry/v1/personas/` — a per-tenant catalog of Persona templates.
2. **Workflow Brief**: captures trigger / inputs / data sources / tools / approval / etc. (unchanged from earlier drafts.)

Both are inputs to the Planner. The Planner system prompt receives Persona Brief context BEFORE Workflow Brief.

**Phase 1 vs Phase 3.1 split.** In Phase 1 (IR v0.3) the Persona Brief shapes the Planner's behavior through three channels — (a) blocking-question policy (`clarify.py` reads persona compliance constraints to decide what is "missing"), (b) scope filter (persona scope narrows registry visibility), (c) system-prompt context (the LLM is told "this Author is a {role} in {vertical}; review goes through {reviewer.role}; do not promise compensation amounts beyond persona policy"). The Persona Brief does NOT write a typed `metadata.compliance_class` field into the IR in Phase 1, because v0.3 does not have that field yet. Phase 3.1 ships ADR 0022 (IR v0.3 → v0.4 minor bump) which adds `metadata.compliance_class` and `output_schema.<field>.pii_class` overrides; from v0.4 onward, the Planner emits those fields structurally, derived from the Persona Brief's `compliance_boundary`. Until v0.4, persona-driven compliance signals are carried in node `rationale` text + clarify questions, not as typed IR fields.

Persona Brief fields:

- `author_role`: `Literal["operator", "cs_lead", "ops_manager", "finance", "compliance", ...]` — extensible.
- `vertical`: `Literal["ecommerce", "tcm_clinic", "internal_hr", "manufacturing", ...]` — extensible.
- `end_user`: `Literal["buyer", "patient", "internal_employee", "supplier", ...]`.
- `reviewer`: `{ role, decision_authority }` — who has publish authority.
- `compliance_boundary`: `{ pii_class_default, regulatory_tags, geographies }`.
- `success_criteria`: free-text but bounded; what does "this workflow worked" mean to the Author.

A Persona registered in `registry/v1/personas/<persona-id>.yaml` is the canonical template; an FDE Session may *clone and override* but cannot use a Persona that isn't registered.

Pending Phase 1 Planner wiring: `IntentRequest.persona_brief` and the Persona Brief system-prompt section will be added when the Planner request model is introduced in Task 1.

## Consequences

- v1 ships ≥3 seed Personas: `ecommerce-operator`, `ecommerce-cs-lead`, `tcm-clinic-operator`. Each is a YAML file in the registry.
- Adding a vertical = adding ≥1 Persona YAML; no FDE Session code change needed.
- Eval corpus prompts get tagged with `persona_id`; Phase 1.5 reports persona × archetype × runtime breakdown.
- Phase 4 pattern library can index by persona too — patterns are persona-aware.
- Phase 0 ADR 0001 (design partner) gates "we have ≥1 real partner Persona", not "we have a brand-locked partner".

## Non-goals

- Persona Brief is NOT a personality / tone-of-voice config for the LLM. Tone lives inside individual node prompts.
- v1 does not synthesize new Personas from chat history; Personas are authored, not learned.
