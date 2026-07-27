# Clarify Design Baseline (3b)

Date: 2026-07-27
Status: **FAILED Plan Review — do not implement**
Architect: Cla
Base: `d333c62`
Plan Review (Dex, Reviewer): 4.5/10 FAIL — Correctness 3, Simplicity 5,
Security 7, Conformance 3. See `2026-07-27-clarify-design-baseline-review.md`.

> **Why this failed, recorded so the next attempt does not repeat it.**
>
> 1. **Part C contradicts a declared runtime redline.** The plan proposed telling
>    the Planner to emit an empty-retrieval `condition` branch. `condition.rule`
>    is a blocking HiAgent 2.6 redline (`loom/runtimes/base.py:165`), and
>    `render_target_block()` (`loom/planner/client.py:57`) injects redlines into
>    the same system prompt under "do not emit any construct listed below". The
>    guidance would have contradicted itself in one prompt.
> 2. **Warn-severity probes are never asked.** `severity == "block"` is the only
>    filter (`clarify_engine.py:130`, `:280`, `cli/commands/brief.py:88`), so the
>    three warn-severity fields would have been collected never.
> 3. **New fields have no capture path.** `parse_field_answer`
>    (`clarify_engine.py:144`) dispatches on `field_path` with hand-written
>    branches; an unknown path discards the operator's answer. `_options_for_field`
>    and `_allow_freeform` are keyed the same way. The plan scoped "add a probe"
>    and missed the parser, options, freeform, both models, `to_strict()`, and the
>    egress allowlist.
> 4. **Enum sets too narrow.** `no_evidence_behaviour` cannot express an ordered
>    fallback; `state_ownership` cannot express case/order-scoped state that spans
>    users and channels.
>
> **Compatibility findings, corrected after verification:** `to_strict()` drops
> the new fields, but production never calls it (only `tests/fde_session/
> test_brief.py:130,140`), so that gap is latent rather than active. The real
> hazard is rollback: `_load_draft` (`sessions.py:1299`) uses
> `model_validate_json` against `extra="forbid"`, so drafts written after this
> change cannot be read by code from before it.
>
> **What survives:** P0 egress was confirmed intact (Security 7). The insight
> that enum fields are allowlist-safe while free text is not still holds.
>
> **Correct next step:** a capability/mapping table — one row per candidate
> field, naming the IR construct, whether it compiles on HiAgent 2.6 and Dify
> 1.14, and whether it is redlined — BEFORE any further design. Both failed plans
> for this work lacked that artifact. The `condition.rule` remediation text
> points at the viable route: deterministic branching via a code node rather than
> a condition rule, which is the construct hardened in 3a.

## Verified premises

Each premise below was checked against `d333c62`. The previous plan for this
work failed review at 4.0/10 for asserting unverified premises, so these are
stated with their evidence.

1. **The brief reaches the Planner.** `_finish_plan_from_draft`
   (`sessions.py:890`) and the edit path (`sessions.py:278`) both call
   `prepare_outbound_planner_payload`, which serialises the draft through
   `_planner_brief_payload` (`planner_payload.py:144`).
2. **Only allowlisted fields are transmitted.**
   `draft.model_dump(mode="json", include=_PLANNER_BRIEF_FIELDS)`
   (`planner_payload.py:155`). The allowlist is currently
   `{intent, target_runtime, scope, trigger, compliance_boundary, data_sources,
   credentials, approval_points, inputs, tools}`.
   **A new brief field does not reach the Planner unless it is added here.**
   Verified by subclassing the model with a new field: it did not appear in the
   outbound payload.
3. **Free text cannot be transmitted safely.** P0 established that `intent` is
   the single transmitted free-text field, and it blocks on detection rather
   than redacting, because names are not regex-detectable.
4. **The probe is rule-based and typed.** `missing_fields()`
   (`clarify.py:22`) returns `ClarifyQuestion(field_path, question, severity)`;
   `clarify_engine.py:127` filters on `severity == "block"`.

## Problem

The clarify probe under-asks. Comparing the design baseline against
`missing_fields()` today:

| Baseline item | Probed today |
|---|---|
| Users, channels, regions, languages | partial — `data_sources` covers channels |
| In-scope journeys, edge cases, **non-goals** | bundled into free-text `intent_clarification` |
| AI/human boundary, **escalation conditions** | implicit only |
| Identity, history, **cross-turn state ownership** | **not probed** |
| Knowledge sources, **freshness**, **no-evidence behaviour** | sources only |

Two of these are load-bearing for output quality:

- **No-evidence behaviour** — what the workflow does when retrieval returns
  nothing. Unspecified, this is a leading cause of hallucinated answers in
  production support agents.
- **Cross-turn state ownership** — unasked, despite the HiAgent compiler
  emitting `chat_histories` wiring.

## Design

### Part A — collect (new typed fields + probes)

Add to `WorkflowBriefDraft`, all optional so existing drafts stay valid.
Enum-typed wherever possible, because enums are allowlist-safe while free text
is not (premise 3).

| Field | Type | Why enum |
|---|---|---|
| `no_evidence_behaviour` | `Literal["refuse", "escalate_to_human", "answer_without_evidence", "ask_clarifying"]` | Four distinct IR shapes; free text adds nothing |
| `state_ownership` | `Literal["stateless", "session_scoped", "user_scoped"]` | Determines whether history is wired at all |
| `knowledge_freshness` | `Literal["realtime", "daily", "weekly", "static"]` | Drives retrieval vs cache decisions |
| `escalation_triggers` | `list[Literal["low_confidence", "explicit_user_request", "policy_violation", "repeated_failure"]]` | Closed set covers observed cases |
| `non_goals` | `list[str]` | **Inherently free text — see below** |

Add one `missing_fields()` probe per field. Severity:

- `no_evidence_behaviour` — **block**. Cannot design retrieval without it.
- `state_ownership` — **block** when the intent implies multi-turn.
- `knowledge_freshness` — **warn**. A default is defensible.
- `escalation_triggers` — **warn**. Empty is a valid answer.
- `non_goals` — **warn**. Absence is not an error.

### Part B — transmit (allowlist)

Add the four enum fields to `_PLANNER_BRIEF_FIELDS`. They are closed sets and
cannot carry PII.

**`non_goals` is NOT added to the allowlist in this phase.** It is operator
free text and could contain anything, and P0 deliberately holds the transmitted
free-text surface at exactly one field. It is still collected, stored, and shown
to human reviewers. If Planner output later shows it is needed, it can be added
with the same blocking detection `intent` uses — as a separate, deliberate
decision.

### Part C — honour (prompt guidance)

Collecting and transmitting a field does not make the Planner act on it.
`system.md` does not mention these fields, so the model would see unfamiliar
JSON keys and infer intent.

Add a short section to `loom/planner/prompts/system.md` mapping each field to
the IR construct that satisfies it, for example: `no_evidence_behaviour:
"refuse"` requires a condition node on empty retrieval whose branch reaches an
output that declines rather than an LLM node.

This stays runtime-agnostic — these are IR-level constructs, not HiAgent
specifics — so it does not violate the Planner's target-neutral contract.

**Part C is not optional.** Without it, Part A and Part B are data collection
with hopeful effect.

## Non-goals

- No persona wiring. That is P2 and is tracked separately.
- No design-knowledge card injection. That is P3.
- No changes to the IR schema. These fields shape IR generation; they are not IR.
- No change to P0's egress policy. `non_goals` stays untransmitted.

## Risks

| Risk | Mitigation |
|---|---|
| Two new blocking probes make clarify feel like an interrogation | Only `no_evidence_behaviour` blocks unconditionally; `state_ownership` blocks only when intent implies multi-turn |
| Enum sets are wrong / too narrow | Ship with the four values above and record which enum values operators reject in practice; treat the sets as v1 |
| Part C prompt growth | One short section, four field mappings, no examples |
| A future field bypasses P0 | Existing allowlist regression test covers this; extend it to assert `non_goals` specifically is absent |

## Verification

1. Each new field defaults to `None`/empty and existing drafts still validate.
2. Each new probe appears with the correct severity and `field_path`.
3. The four enum fields appear in the outbound payload; **`non_goals` does not**.
4. A brief with `no_evidence_behaviour="refuse"` produces IR containing an
   empty-retrieval branch that does not reach an LLM node.
5. A brief with `state_ownership="stateless"` produces IR with no history wiring.
6. Existing sessions with none of these fields set generate IR as they do today.
7. Full suite, ruff, mypy green.

## Open decision

`state_ownership` blocking "when the intent implies multi-turn" needs a
detection rule. The existing `_needs_retrieval_source` / `_needs_channel`
helpers in `clarify.py` are keyword-based; the same approach would work but is
crude. Alternative: make it unconditionally `warn`. Recommend starting with
`warn` and promoting it once there is evidence operators skip it.
