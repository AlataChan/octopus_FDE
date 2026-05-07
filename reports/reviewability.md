# Reviewability ratings

**Status:** `deferred_to_first_customer_integration` (per Phase 0 plan MVP scope clarification, 2026-05-07)
**Date:** N/A (not yet rated)

## Why this is deferred

PRD §7 Phase 0 gate criterion: "reviewability score (subjective rating from 3 reviewers, 1–5) ≥ 4 median." This requires 3 human reviewers — at least one a Reviewer-persona target (senior engineer / SRE / security) — to rate each archetype IR on the dimensions below.

For MVP velocity, this rating is **deferred until the first customer integration**, where the 3 reviewers can include the customer's domain reviewer (highest-signal observer) plus 2 internal reviewers. Rating Phase 0 archetype IRs in isolation would invest reviewer time without the customer-context comparison that gives the rating its meaning.

## Interim signal

Phase 1's Codex / Claude code review loop (CLAUDE.md §5 4-dimension scored review on every Plan and Code change) provides interim reviewability signal during MVP development. This does not substitute for Task 19's gate criterion but reduces the risk of shipping IR shapes that reviewers find unreadable.

## Rating template (when re-run)

For each archetype IR, each reviewer rates 1–5 on:

1. "I can read this in 5 minutes and decide approve / reject."
2. "I can spot what changed in a diff against an earlier version."
3. "The `rationale` fields are useful, not boilerplate."

| Archetype | Reviewer 1 | Reviewer 2 | Reviewer 3 | Median |
|---|---|---|---|---|
| 01-ecommerce-customer-faq | TBD | TBD | TBD | TBD |
| 02-tcm-intake-triage | TBD | TBD | TBD | TBD |
| 03-clinic-ops-summary | TBD | TBD | TBD | TBD |
| 04-tcm-followup | TBD | TBD | TBD | TBD |
| 05-ecommerce-order-exception | TBD | TBD | TBD | TBD |

Phase 0 gate: ≥ 4 median.

## Action items into Phase 1 Planner prompts

When the rating is run, the Planner few-shot library should bias toward rationale styles the reviewers rated high. To be filled in from rating session.
