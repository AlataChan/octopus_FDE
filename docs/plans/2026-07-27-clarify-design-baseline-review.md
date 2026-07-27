# Plan Review: Clarify Design Baseline (3b)

Date: 2026-07-27  
Reviewed base: `d333c6222e9ad887ca04486b9a0be749faf140e3`  
Review mode: read-only; this report is the only intended created file  
Review lens: general plan review — Correctness, Simplicity, Security, and
Conformance — plus a two-runtime feasibility check for Part C

### Skill audit

- The `orchestration` skill was used only because this is an Orca-dispatched
  worker task and completion/progress had to use Orca's lifecycle messages.
- I initially inspected `hiagent-architect-kit:reviewing-hiagent-plans` because
  the requested feasibility work mentions HiAgent. The coordinator correctly
  identified that as the wrong review lens: this is an FDE Python/Planner plan,
  not a HiAgent implementation plan. No final score or finding relies on that
  skill's Standards/Spec framework.
- No domain-specific general plan-review skill applies. The final review uses
  the four axes requested by the task. The only runtime-specific analysis asks
  the legitimate cross-target question: whether Part C's claimed
  runtime-neutral IR constructs validate, compile, and retain behavior on both
  HiAgent 2.6 and Dify 1.14.

## Verdict

**REVISE BEFORE IMPLEMENTATION — FAIL**

The revised plan fixes the previous plan's central factual error: the
`WorkflowBriefDraft` does reach the Planner, and the newly merged outbound
allowlist is the boundary that decides which fields reach it. The proposed
implementation is still not executable as written. In particular:

1. `no_evidence_behaviour` would be a blocking question that the deterministic
   clarify engine cannot parse, so an ordinary reply leaves the same blocker in
   place indefinitely.
2. The three `warn` fields are not collected by the session flow at all;
   warnings are exposed only by the headless `loom brief` command.
3. The promised runtime-neutral IR mappings do not survive the two pinned
   targets. HiAgent's governed compile path rejects every rule `condition`
   node, Dify cannot safely lower the proposed empty-list comparison, both
   compilers warn that `policy.escalation` is not lowered, and the IR has no
   cache/freshness or durable state-ownership construct.
4. The four enum designs are too narrow for workflows already described in the
   repository.
5. Adding the fields only to `WorkflowBriefDraft` silently loses them in
   `to_strict()`, while `non_goals` is preserved unredacted by the existing
   draft-redaction helper and none of the new fields appears in the human
   brief-review panel.

### Scores

| Dimension | Score | Reason |
|---|---:|---|
| Correctness | 3/10 | The data path and allowlist premise are right, but the blocking answer cannot be consumed, warn probes are not collected, two required semantics have no IR representation, and the proposed no-evidence mapping fails the governed capability rules on HiAgent and in its exact empty-list form on Dify. |
| Simplicity | 5/10 | Five additive fields look small, but single workflow-level enums hide per-source, ordered-fallback, state-key, UI, parser, validator, and compiler work. |
| Security | 7/10 | Keeping unbounded `non_goals` out of the Planner preserves the P0 egress posture, and four validated enum fields cannot carry PII. P0 is unaffected by `non_goals` being retained unredacted in the stored reviewer draft, but the persistence policy is unstated; the plan also overstates the safety of a future detector-only allowlisting decision and includes unsafe `answer_without_evidence` without a policy gate. |
| Conformance | 3/10 | The plan conflicts with current runtime redlines, the strict-brief contract, current clarify/UI mechanics, and the product rule to ask a small number of genuinely blocking questions. Several verification items cannot pass on `d333c62`. |
| **Overall** | **4.5/10** | Below the 7.0 pass threshold, with Correctness and Conformance both at 3. |

Final risk: **HIGH** — implementing the plan literally can make self-design
clarification non-terminating and can generate IR that at least one pinned
runtime refuses to compile or cannot lower with the promised behavior.

## Premise verification

| Plan premise | Verdict | Evidence |
|---|---|---|
| The brief reaches the Planner. | **Verified.** | `_finish_plan_from_draft()` passes `brief=draft` into `prepare_outbound_planner_payload()` (`loom/service/routes/sessions.py:878-905`). Planner-assisted edits pass the stored brief inside `extra_context` (`sessions.py:1007-1026`), and the outbound sanitizer handles that nested copy (`loom/fde_session/planner_payload.py:170-185`). |
| Only allowlisted fields are transmitted. | **Verified.** | `_planner_brief_payload()` uses `model_dump(... include=_PLANNER_BRIEF_FIELDS, exclude_none=True)` and separately projects input fields (`planner_payload.py:144-167`). |
| `intent` is the only permitted unbounded free-text channel. | **Verified as the P0 policy, with a wording qualification.** | The allowlisted structures still contain constrained/operator strings such as handles, stages, tags, paths, and hosts. The security property is data minimization plus typed/structured fields, not “no other strings.” |
| The probe is rule-based and only `block` questions gate readiness. | **Verified.** | `missing_fields()` returns typed policy questions (`loom/fde_session/clarify.py:22-107`); the session engine and route select only blockers (`loom/fde_session/clarify_engine.py:88-95,129-141,278-282`; `sessions.py:740-788`). |

The supplied line references were directionally accurate after the P0 merge.

## Blocking finding 1 — the proposed fields cannot be collected by the current session

Adding fields and `missing_fields()` entries is not sufficient.

### Blocking answers have no parser

The deterministic engine applies a user's answer only through
`parse_field_answer(field_path, answer)` (`clarify_engine.py:85-87,144-275`).
That function has no branches for any of the five proposed fields. It also has
no proposed fields in the broad `intent_clarification` inference list
(`clarify_engine.py:157-165`).

The resulting path for `no_evidence_behaviour` is:

1. `missing_fields()` emits a blocking question.
2. The UI sends `no_evidence_behaviour=refuse`.
3. `parse_field_answer("no_evidence_behaviour", ...)` returns `{}`.
4. The draft remains unset.
5. The same blocking question is emitted again.

This is a release blocker, not an implementation detail.

### Warning probes are not asked

`knowledge_freshness`, `escalation_triggers`, and `non_goals` are proposed as
`warn`. The web/session path calls `next_blocking_questions()`, which filters
out every warning (`clarify_engine.py:129-130`). `_first_blocking_question()`
does the same (`clarify_engine.py:278-282`). Warnings appear in the headless CLI
response (`loom/cli/commands/brief.py:87-97,169-174`), but no conversational
surface displays or collects them.

Therefore Part A does not collect three of its five fields for the primary
product flow.

### List answers need an explicit UX contract

`escalation_triggers` is a list, but the current option UI is single-select:
`ClarifyBubble` stores one `selected` string, and `QuestionnaireBubble` stores
one string per field path
(`web/src/components/console/ClarifyBubble.tsx:23-38`;
`QuestionnaireBubble.tsx:23-45`). Adding four option buttons would still allow
only one trigger.

### Required repair

Before adding probes, specify and test the complete capture path:

- add parser branches and enum validation for each field;
- add option definitions and make enum questions non-freeform where appropriate;
- define multi-select encoding/parsing for `escalation_triggers`;
- distinguish “unanswered” from an explicit empty list;
- decide how warnings are surfaced and accepted in the session/brief-review
  flow, or stop claiming that warn fields are collected;
- add a turn-level test that asks, answers, persists, reloads, reviews, confirms,
  and transmits each field.

## Blocking finding 2 — two-runtime feasibility: Part C's mappings do not survive both targets

This section does not impose HiAgent node details on the runtime-agnostic
Planner. It tests the plan's own claim that each field maps to a runtime-neutral
IR construct: that claim is only useful if the construct retains its stated
behavior after both pinned compilers.

### JSON keys alone are not a contract

The Planner will see the JSON keys inside its user intent and may infer their
meaning. That is useful steering, but there is no stable contract for how a
model should turn `session_scoped` or `daily` into the current IR. A concise
`system.md` mapping is therefore justified.

Part C is **necessary but not sufficient**. Prompt prose cannot create missing
IR/runtime capabilities or prove that the generated graph honours a field on
both targets.

### The example no-evidence mapping conflicts with the primary runtime

The proposed mapping requires an empty-retrieval `condition` branch. On current
main:

- the IR can represent a generic `ConditionNode`
  (`loom/ir/models.py:160-175`);
- the governed HiAgent adapter rejects every condition as
  `condition.rule`, because rule conditions are converted to an LLM Intent
  classifier (`loom/runtimes/base.py:155-168,247-271`);
- that same redline is injected into the Planner system prompt through
  `render_target_block()` (`loom/planner/client.py:57-65`);
- the raw HiAgent compiler does in fact turn a condition into an Intent/LLM
  classifier with the query hard-wired as its input
  (`loom/runtimes/hiagent/v2_6/compiler_nodes.py:263-288`).

Thus the proposed guidance would tell the Planner both “emit an empty-result
condition” and “do not emit condition rules” for the primary target.

Dify does not rescue the exact example. Its governed path accepts only a simple
reference-to-string/number comparison (`loom/runtimes/base.py:210-217,272-278`);
an expression such as `${retrieve.chunks} == []` is not in that safe subset.
A code node could first derive a scalar `is_empty`, but the plan does not define
that graph or its target conformance.

Also, an `output` node cannot itself produce a literal decline; its bindings are
variable references (`loom/ir/models.py:209-212`). A non-LLM refusal branch
needs a producer, normally a code node, before the output.

### State ownership has no current IR/runtime representation

The IR has inputs and variable references, but no state store, state key, TTL,
or ownership/lifecycle object (`loom/ir/models.py:88-237`).

- HiAgent's Start schema always contains `chat_histories`, regardless of the
  brief (`loom/runtimes/hiagent/v2_6/compiler_nodes.py:102-157`).
- Dify LLM nodes are compiled with `memory: None`
  (`loom/runtimes/dify/v1_14/compiler_nodes.py:160-179`).
- “No reference to history” can approximate a stateless LLM prompt, but it does
  not implement `session_scoped` or `user_scoped` ownership.

Verification item 5 (“stateless produces IR with no history wiring”) is also
underspecified: IR has no `history_wiring` property, and compiled HiAgent Start
nodes always expose the history field.

### Freshness has no cache/retrieval contract

`RetrievalNode` exposes dataset, query, `top_k`, rerank, timeout, and retry; it
has no freshness, cache, invalidation, or maximum-staleness field
(`loom/ir/models.py:127-135`). A workflow-level value also cannot express
different requirements for different sources. Prompt guidance can encourage an
HTTP call for “realtime,” but it cannot honour daily/weekly cache semantics
without a source/cache contract and compiler support.

### Escalation is only partially representable and is not lowered

The typed IR `policy.escalation` represents one confidence threshold and one
handoff output (`loom/ir/models.py:67-70`). It cannot represent explicit user
request, policy violation, or repeated failure by itself. More importantly,
both compilers currently report that escalation is not lowered:

- HiAgent inserts no conditional branch
  (`loom/runtimes/hiagent/v2_6/compiler.py:402-412`);
- Dify retains only a compile warning
  (`loom/runtimes/dify/v1_14/compiler.py:117-126`).

### Required repair

Choose one honest scope before implementation:

1. **Collection/review-only slice:** persist and display the requirements, label
   them explicitly as not yet enforced, and do not claim that they shape IR; or
2. **End-to-end semantics slice:** first add the necessary typed IR semantics,
   target capability rules/compiler lowering, and deterministic brief-to-IR
   postconditions; or
3. **Narrow v1 slice:** retain only values that can be mapped and compiled on
   both pinned targets, with a documented fallback for unsupported values.

For any transmitted field, add a deterministic post-generation conformance
check. A prompt-only test that happens to produce one good IR is not an
enforcement mechanism.

## Challenge 1 — the four enum sets are too narrow

One concrete repository-aligned workflow exposes all four gaps:

> A cross-border order-exception assistant uses a static policy KB plus
> inventory data that must be no more than five minutes old. It keeps one
> durable after-sales case across Shopify chat, WhatsApp, the buyer, and a human
> agent. If KB retrieval is empty, it queries the live order API; if that also
> fails, it opens a ticket and returns the case id. It escalates when refund
> value exceeds USD 500, the SLA is breached, or the buyer is angry.

This is consistent with the documented order-exception flow and its
amount/SLA/channel questions
(`docs/design/fde-ecommerce-tcm.zh-CN.md:57-72,78-86,139-142`), but the proposed
types cannot express it:

| Field | Missing real requirement |
|---|---|
| `no_evidence_behaviour` | An ordered fallback: alternate source, then create a ticket, then return a case id. A single literal cannot express composition or retry/defer/partial-answer behavior. |
| `state_ownership` | State belongs to an after-sales **case/order**, spans users and channels, and is durable. It is neither one session nor one user. Tenant/account/workspace ownership is also absent. |
| `knowledge_freshness` | Freshness is per source and quantitative: policy KB may be static/weekly while inventory has a five-minute SLA or event-driven invalidation. One workflow-level `realtime|daily|weekly|static` value loses both facts. |
| `escalation_triggers` | Amount threshold, SLA breach, sentiment/risk, tool outage, missing identity, and clinical abnormality are all real triggers already present in the product scenarios. The four literals do not cover them, and triggers often carry parameters and destinations. |

A better contract is not simply “add more strings.” Likely shapes are:

- an ordered typed fallback policy for no-evidence behavior;
- a state spec containing ownership key/scope, system of record, lifetime, and
  reset behavior;
- per-source freshness requirements with a maximum-staleness duration and
  refresh mode;
- discriminated escalation rules carrying kind, threshold/reference,
  destination/reviewer, and precedence.

If that is too large for 3b, narrow 3b instead of declaring the initial enums
complete.

## Challenge 2 — withholding `non_goals` is security-correct but functionally incomplete

Keeping `list[str]` out of `_PLANNER_BRIEF_FIELDS` is the correct decision under
the P0 policy. Arbitrary non-goal text can contain names, diagnoses, addresses,
or other data the current detector cannot recognize. Merely applying the same
detector used for `intent` in a future phase does **not** solve that known
limitation (`docs/plans/2026-07-27-planner-pii-egress-design.md:115-122`).

However, the plan then overclaims the feature. A non-goal that is collected but
not transmitted cannot constrain Planner output. It can be useful to a human
reviewer only if it is displayed and clearly labelled review-only. The current
brief-review panel does not display it: `BriefPanel.sectionKeys` is a fixed list
without any proposed field
(`web/src/components/console/BriefPanel.tsx:13-23,31-68`).

The plan should choose one of these:

- rename/describe it as review-only, add it to the confirmation UI, and exclude
  it from claims or tests about generated IR;
- replace the load-bearing subset with an allowlist-safe typed field such as
  `forbidden_capabilities` / `automation_boundaries`, retaining a separate
  free-text reviewer note; or
- defer `non_goals` entirely until an approved outbound-data policy can carry it.

Do not silently let operators believe a displayed non-goal constrained the
generated workflow when the Planner never received it.

## Challenge 3 — system guidance is right in principle, wrong as the only honouring layer

Adding short semantic guidance to `system.md` is appropriate because unfamiliar
JSON keys alone do not define stable graph semantics. The proposed mapping is
not yet the right one:

- it requires a condition that HiAgent rejects;
- it has no mapping for user/case state or freshness;
- it risks mapping escalation to a typed policy both compilers explicitly do
  not lower;
- it gives no precedence rule when the selected behavior conflicts with
  compliance, for example `answer_without_evidence` in a clinical or
  source-grounded customer workflow.

Part C should follow—not precede—a capability/mapping table with one row per
field value:

| Value | Required IR postcondition | HiAgent 2.6 | Dify 1.14 | Unsupported outcome |
|---|---|---|---|---|

Only mappings that survive validation and governed compilation should be placed
in the Planner prompt. Then add a deterministic brief/IR conformance validator
or treat the prompt as measured steering rather than enforcement.

## Challenge 4 — unconditional `no_evidence_behaviour` blocking is not justified

The product baseline says FDE should ask a small number of facts that block safe
generation, not conduct a discovery interview
(`docs/design/fde-product-design.md:19-25,53-61`). No-evidence behavior is
load-bearing for retrieval/customer-facing workflows, especially regulated
ones. It is irrelevant to many webhook, transformation, reporting, and
human-only routing workflows.

The proposed unconditional blocker would therefore ask a meaningless question
for workflows with no retrieval. It also adds another blocker to a flow that can
already ask intent, runtime, scope, compliance, trigger, data source,
credentials, approval, and success criteria.

Use a conditional rule based on actual retrieval intent/data sources, and decide
whether a fail-closed default such as `refuse` is acceptable:

- regulated/customer-facing retrieval: block unless explicitly resolved;
- low-risk retrieval: default to `refuse` and show a warning/review assumption;
- no retrieval: no probe.

`answer_without_evidence` should be invalid or require an approval/compliance
gate for source-grounded or regulated workflows. Offering it without such a
rule contradicts the stated hallucination-risk motivation.

The plan's compatibility verification also conflicts with the blocker:
“existing sessions with none of these fields set generate IR as they do today”
cannot hold for an existing draft that re-enters the clarify gate and now lacks
an unconditional required field.

`state_ownership` cannot be left as an unresolved implementation decision.
Making it `warn` means the current session will not ask it at all; making it
conditionally `block` requires a tested predicate and a representable runtime
outcome.

## Challenge 5 — P0 egress remains intact, but this is still an allowlist policy change

As written, adding the four closed enum fields does not weaken the P0 egress
guard:

- values are fixed `Literal`s (or lists of them);
- `non_goals` remains excluded;
- fresh generation and edit context both pass through the same
  `_planner_brief_payload()` projection.

The plan should nevertheless stop saying “no change to P0's egress policy.”
Growing `_PLANNER_BRIEF_FIELDS` is a deliberate expansion of the outbound data
contract. Update the P0 field-classification table and test both the fresh and
nested edit payloads.

Required security regressions:

- exact allowed values are present in fresh and edit Planner payloads;
- `non_goals`, including seeded email/phone/secret/name-like text, is absent
  from both final outbound strings and `PreparedPlannerPayload.extra_context`;
- an unrelated future `WorkflowBriefDraft` field remains absent;
- detector failures still block before the Planner callable;
- a future proposal to transmit arbitrary `non_goals` is a new security review,
  not a routine reuse of the current detector.

## Challenge 6 — draft/strict/redaction/storage/API compatibility

Point 6 is materially under-specified. The detailed result is:

| Surface | Result on `d333c62` | Required plan change |
|---|---|---|
| Existing draft validation | Adding optional fields is backward-compatible for old JSON read by new code. | Test an actual legacy stored JSON string, not only a newly constructed object. |
| `to_strict()` | **Silently loses all new fields.** It explicitly constructs `WorkflowBrief` with the current field list (`loom/fde_session/brief.py:100-128`), and `WorkflowBrief` has none of the proposed fields (`brief.py:65-79`). A repository search finds no production call to `to_strict()`; current direct `WorkflowBrief` construction is in tests, while `missing_fields()` merely accepts either model. Current service Planner generation therefore keeps using the Draft and is not immediately broken, but the intended Draft-to-strict contract and any future strict consumer lose the fields. | Add the fields to `WorkflowBrief` and copy them through, or explicitly redefine them as draft-only and reconcile that with the accepted strict-materialization design. Add equality/preservation tests. |
| List defaults | `model_dump(... exclude_none=True)` does **not** drop `[]`. A default empty `escalation_triggers` would be transmitted for every legacy draft and change every prompt; default empty proposed fields would also be persisted on the next save. Empty also cannot mean both “unanswered” and “operator chose none.” | Use `None` for unanswered lists and `[]` for an explicit none, or define another presence marker. Preserve omission for legacy payloads. |
| Draft redaction | `redact_draft()` uses `model_copy(update=...)`, so every unlisted new field is preserved rather than dropped (`loom/fde_session/redaction.py:32-46`). That is correct and harmless for the four enums. A read-only runtime probe confirmed that `non_goals=["never use Bearer abc..."]` is also preserved unredacted. This does **not** weaken P0 because `non_goals` remains outside the egress allowlist; it does leave arbitrary text unchanged in the persisted/reviewer snapshot. | State the persistence policy explicitly. If stored drafts are expected to retain operator reviewer notes verbatim, test preservation and keep the field review-only. If the existing persisted-draft secret-scrubbing contract applies, redact/truncate every item. Any future allowlisting of `non_goals` requires a new egress policy regardless. |
| Same-version stored round-trip | `_draft_json()` dumps all non-`None` model fields and `_load_draft()` validates them (`sessions.py:1299-1325`); `_merge_draft()` starts from the full model dump, so same-version preservation should work. SQLite stores opaque JSON text, so no column migration is needed. | Add save/load/merge/stale-turn/brief-review tests proving values survive every route, not merely Pydantic JSON round-trip. |
| Rollback/old-reader compatibility | **Broken once new keys are persisted.** `WorkflowBriefDraft` uses `extra="forbid"` (`brief.py:81-82`), so code at `d333c62` rejects a stored draft containing any new key. The runtime probe produced five `extra_forbidden` errors. | This is not acceptable as an undocumented direct rollback. Prefer a two-stage rollout: first deploy an intentionally tolerant `_load_draft()` reader while still writing the old shape, then deploy the new writer and make that tolerant release the minimum rollback target. Otherwise ship a tested downgrade transform that removes the five keys before rolling back. A schema-version key alone does not help an already strict old reader. |
| Generated OpenAPI types | No direct generated-type break today. `create_turn()` returns `dict[str, object]`, so `types.generated.ts` exposes only `{[key:string]: unknown}` (`web/src/lib/types.generated.ts:884-910`). | Do not claim generated types were verified by field addition; they are too generic to detect drift. Regenerate only if a typed response model is introduced. |
| Manual web types and review UI | `WorkflowBriefSnapshot` has an index signature, so TypeScript accepts new keys (`web/src/lib/types.ts:77-88`), but `BriefPanel` renders only fixed keys and locale labels do not exist for the new fields. | Add explicit snapshot members, brief-review sections, English/Chinese labels, and component tests. This is required for the promise that `non_goals` is shown to reviewers. |
| Planner-assisted edits | The same allowlist projection is applied to nested `workflow_brief`, so the four enum fields will reach edit planning if added to the allowlist; `non_goals` will not. | Add a nested-edit regression for inclusion/exclusion and decide whether edits must preserve baseline semantics through deterministic postconditions. |

The runtime probe also confirmed that a proposed subclass round-trips correctly
within the same version; that is the easy case. Static inspection of the actual
session store reaches the same conclusion: it stores `brief_draft`,
`brief_before`, and `brief_after` as opaque JSON text, while the route performs
model loading at the boundary. There is no SQLite column migration for the new
members. The required tests are still important because merge, stale-turn,
brief-review, and rollback behavior—not the text columns themselves—are where
loss or incompatibility can occur.

## Verification plan gaps

The supplied seven checks are not sufficient. Add at least:

1. Every blocking question can be answered through the real
   `ClarifyBubble`/questionnaire encoding and disappears on the next turn.
2. Every warn field has an explicit collection or review surface; if not, it is
   labelled non-collected.
3. Multi-select escalation values survive parser, persistence, reload, and
   review.
4. `None` versus explicit `[]` has stable semantics and legacy outbound prompts
   omit absent fields.
5. `to_strict()` preserves every intended brief field.
6. The chosen `non_goals` persistence policy is explicit and tested:
   scrub/truncate each item if the existing persisted-draft redaction contract
   applies, or preserve it as an authorized reviewer note; either way it remains
   absent from Planner egress.
7. New-version stored drafts round-trip through session and turn rows, and the
   chosen downgrade/rollback path handles their keys.
8. The brief-review panel renders all new fields with English and Chinese
   labels.
9. Both final fresh-generation and edit-generation egress payloads contain only
   the four approved enum fields and never `non_goals`.
10. Each promised field value has a deterministic IR postcondition.
11. Each resulting IR validates and compiles through the governed adapter for
    both pinned targets, or produces the documented unsupported result.
12. Model evals cover at least the ecommerce FAQ, ecommerce order exception,
    TCM KB, and a non-retrieval workflow. Prompt snapshots alone do not prove
    behavior; stochastic output alone does not prove enforcement.
13. Full Python gates plus web tests/typecheck/build run, because the corrected
    plan necessarily changes the review UI.

## Required revised sequence

### Slice A — settle the semantic contract

1. Replace the four broad enums with requirements that cover the chosen real
   workflows, or explicitly narrow the v1 supported subset.
2. Produce the per-value IR/runtime capability table.
3. Decide which values are enforceable, review-only, defaulted, or unsupported.
4. Resolve the `state_ownership` severity decision before implementation.

### Slice B — complete capture and compatibility

1. Add fields to the appropriate Draft **and strict** models with presence-aware
   defaults.
2. Add parser, options, multi-select encoding, warning surfacing, redaction,
   persistence, rollback, and brief-review UI.
3. Test one complete conversational and stored-draft round-trip.

### Slice C — preserve P0 while transmitting only enforceable structure

1. Add only fixed typed fields to `_PLANNER_BRIEF_FIELDS`.
2. Keep arbitrary reviewer text out.
3. Update the P0 classification document and fresh/edit egress tests.

### Slice D — honour and enforce

1. Add `system.md` guidance only for mappings the current IR can represent.
2. Add or extend IR/compiler semantics for the rest before promising them.
3. Add deterministic brief-to-IR postconditions plus governed compile tests.
4. Treat model evals as quality evidence, not as the security or conformance
   boundary.

## Bottom line

Do not implement the submitted plan verbatim. Its corrected Planner/allowlist
premises and its caution around `non_goals` are solid, but the plan stops at
field declaration where the repository requires an end-to-end question,
answer, persistence, prompt, IR, compiler, and review contract. Revise around a
representable runtime subset, complete the capture and compatibility paths, and
make prompt guidance subordinate to deterministic IR/runtime conformance.
