# Planner Path Findings

Date: 2026-07-27
Status: findings record — NOT an approved plan
Architect: Cla
Plan Review (Dex, Reviewer): 4.0/10 FAIL — see
`2026-07-27-planner-path-findings-review.md`

> **This document was originally written as "Planner Context Wiring (3b Phase 1)"
> and failed Plan Review. It is retained as a findings record because the
> investigation surfaced real defects, but its central premise was wrong and its
> proposed work is NOT the 3b task.**
>
> **Corrections (verified against `70ad124`):**
>
> 1. **The Workflow Brief already reaches the Planner.** `_finish_plan_from_draft`
>    (`sessions.py:827`) calls the Planner with `_draft_to_planner_message(draft)`,
>    which serialises the whole draft via `model_dump(mode="json")`. Any field on
>    `WorkflowBriefDraft` reaches the Planner with no wiring at all. The original
>    premise — that the brief never arrives — was false, and W4's brief injection
>    would have duplicated it.
> 2. **Design-knowledge cards are already relevance-ranked.** `_score(card, query)
>    + _persona_score(card, persona)` with sorting and diversification. The "N=3
>    cap because cards are unranked" reasoning was built on a false premise.
> 3. **"Every production session runs dev-mode" was overstated.** Template
>    creation and deterministic edits never reach the Planner. The accurate claim
>    is: every service invocation through `_default_planner` passes
>    `persona_brief=None`.
> 4. **This is not 3b.** The chosen 3b work — extending `missing_fields()` with
>    the design baseline (no-evidence behaviour, cross-turn state ownership,
>    knowledge freshness, explicit escalation, non-goals) — appears nowhere below,
>    and needs none of the wiring proposed here.

## Findings that stand

| Finding | Severity | Status |
|---|---|---|
| `redact_text()` scrubs secrets only — names, phones, emails, national IDs and medical detail all reach the third-party LLM | **P0, live today** | open |
| `persona_brief` is never supplied on the `_default_planner` service path, so persona compliance rules are dormant | high | open |
| `_default_planner` accepts `extra_context` then drops it; `sessions.py` folds an identical copy into the message instead | medium | open |
| `DesignKnowledgeCatalog` is built and HTTP-exposed but never reaches the Planner | medium | open |
| `_intent_with_extra_context` appends an edit-only instruction whenever `extra_context` is non-empty, so any generation-time payload would be mislabelled as an edit | medium | open |

## Original problem statement (superseded — retained for context)

FDE builds three context assets and feeds them to the Planner inconsistently.

| Asset | Where it is built | Reaches Planner |
|---|---|---|
| `WorkflowBrief` / `WorkflowBriefDraft` | collected by the clarify flow | **yes** — via `_draft_to_planner_message` (correction 1) |
| `PersonaBrief` | `registry/v1/personas/*.yaml`, `PersonaCatalog` | no |
| `DesignKnowledgeCatalog` | built at `app.py:103`, served over its own router | no |

The persona and design-knowledge gaps converge on one line in
`loom/service/app.py`:

```python
IntentRequest(intent=user_message, scope=scope, target=target_runtime)
```

### Consequence 1: persona compliance rules are inert

`render_persona_block(None)` returns
`"Persona Brief: default-operator [no explicit persona supplied; debug / dev mode]."`

So every production session runs the Planner in dev mode, and this rule in
`loom/planner/prompts/system.md` never fires:

> Refuse workflows that violate the persona's compliance boundary (e.g., a TCM
> persona MUST NOT produce a node that auto-publishes patient-facing diagnostic
> content...)

`registry/v1/personas/tcm-clinic-operator.yaml` declares `pii_class_default:
high`, `regulatory_tags: [PIPL, PIPL-medical]`, reviewer decision authority
`[publish, medical_response_approval]`, and success criteria "no
diagnosis/prescription/treatment claims auto-published". None of it is enforced
at generation time. TCM clinics are the primary vertical, so this is the
highest-severity item in this plan.

### Consequence 2: a structured context channel already exists and is dead

`IntentRequest.extra_context: dict[str, Any] | None` exists
(`loom/planner/types.py:40`) and `loom/planner/retry.py:65`
(`_intent_with_extra_context`) already serialises it into the intent.

But `_default_planner` accepts `extra_context` as a kwarg and never forwards it
to `IntentRequest`. Context reaches the model only because
`loom/service/routes/sessions.py:275` separately folds it into `user_message`
via `_planner_message_with_context`. Two paths exist; the structured one is
dead.

`extra_context` is also populated only for edits — `_edit_planner_context(...)`
runs when `current_doc is not None and parsed_edit is not None`. Fresh workflow
generation always passes `None`.

### Consequence 3: the clarify probe cannot affect output

Extending `missing_fields()` (the original 3b framing) would improve the stored
brief and the operator conversation, and produce identical IR, because the brief
never reaches the Planner. Wiring is a prerequisite for that work, not a parallel
track.

## Non-goals

- No changes to `system.md` prose. The Planner stays runtime-agnostic; HiAgent
  specifics remain in the compiler and `spec_check`.
- No new clarify probes in this phase. That is Phase 2, and it is only
  measurable once this phase lands.
- No changes to the IR schema.
- No changes to the Dify or HiAgent compile paths.

## Design

Four changes, each independently testable.

### W1 — Bind a persona to the session

`SessionRow` (`loom/state/models.py:15`) has `scope`, `target_runtime`, and
`brief_draft` but no persona. Persona ids (`ecommerce-operator`,
`ecommerce-cs-lead`, `tcm-clinic-operator`) do not map 1:1 to scope strings
(`ecommerce/kb`), so persona cannot be derived from scope and must be stored.

- Add nullable `persona_id: str | None` to `SessionRow` and the sessions table.
- Migration must be additive and nullable so existing rows stay valid.
- Accept `persona_id` on session create; validate against `PersonaCatalog`.
- `None` preserves today's behaviour exactly (dev-mode persona block).

Nullable is deliberate: this must not break existing sessions or force a
backfill guess about which persona an old session belonged to.

### W2 — Pass the persona to the Planner

In `_default_planner` (`loom/service/app.py:45`), resolve `persona_id` through
`PersonaCatalog` and pass the result as `IntentRequest.persona_brief`.

`PlannerClient` and `render_persona_block` already consume it; no planner-side
change is needed. This alone activates the compliance rules.

### W3 — Forward `extra_context`, and pick one injection path

`_default_planner` must forward `extra_context` into `IntentRequest`.

Then remove the duplicate: with the structured path live,
`_planner_message_with_context` would inject the same payload a second time,
wasting tokens and presenting the model with two copies that can drift.

**Decision: keep the structured path, drop the message-folding path.** The
structured payload is what `retry.py` already formats, and it survives retries
through `plan()` without re-derivation.

### W4 — Populate `extra_context` for fresh generation

Extend `extra_context` beyond edit context to carry:

- `brief`: the redacted structured brief for the session, when present. Reuse
  the existing redaction path (`loom/fde_session/redaction.py`) — the brief may
  contain customer data and this payload goes to a third-party LLM.
- `design_knowledge`: up to **N = 3** cards matched on session scope and
  persona, each reduced to `intent_summary`, `constraints`, `anti_goals`,
  `policy_features`. Full cards carry fields the Planner cannot act on.

Cards are currently scope-filtered but not relevance-ranked, so an uncapped
injection would grow the prompt without bound. N = 3 is a starting cap to be
tuned against measured output quality, not a permanent constant.

## Risks

| Risk | Mitigation |
|---|---|
| Double injection of context (W3) | Remove `_planner_message_with_context` from the generation path in the same change; assert in tests that the payload appears exactly once |
| Prompt growth / cost regression | Cap cards at N=3 and project to four fields; record prompt token count in tests |
| Customer data sent to third-party LLM | Route the brief through existing redaction; add a test asserting a known PII marker never appears in the assembled prompt |
| Migration breaks existing sessions | `persona_id` nullable, no backfill; explicit test that a `None` persona reproduces current behaviour byte-for-byte |
| Persona refusals become newly active | This is the intent, but it changes behaviour for existing flows. Ship behind the nullable column: only sessions that opt in by setting `persona_id` change behaviour |

## Verification

1. Session with `persona_id=None` produces a prompt identical to today's.
2. Session with `persona_id=tcm-clinic-operator` renders the persona block with
   `pii_class_default=high` and the PIPL tags.
3. A TCM intent asking to auto-publish patient-facing diagnostic content is
   refused or gated, and the refusal cites the persona boundary.
4. `extra_context` payload appears exactly once in the assembled prompt.
5. Brief redaction: a seeded PII marker in the brief never reaches the prompt.
6. Design-knowledge injection is capped at 3 cards and only the four projected
   fields appear.
7. Full suite, ruff, mypy, web build all green.

## Open decisions for the user

1. **Persona selection UX.** Does the operator choose a persona when creating a
   session, or is it inferred from the brief during clarify? This plan assumes
   explicit selection at create time; inference is a larger change.
2. **Default persona.** Should an unset `persona_id` stay dev-mode forever, or
   should it eventually become a required field once the UI supports it?

## Sequencing

W1 → W2 → W3 → W4. W2 is the highest-value single step and is shippable alone.
