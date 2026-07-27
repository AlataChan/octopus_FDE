# Plan Review: Planner Context Wiring (3b Phase 1)

Date: 2026-07-27  
Reviewed base: `70ad124af4be5b80a9e65c3f2d5a46aed4bf5860`  
Review mode: read-only; this report is the only created file

## Verdict

**REVISE BEFORE IMPLEMENTATION — FAIL**

The plan identifies two real wiring gaps:

- service Planner calls never supply `IntentRequest.persona_brief`;
- `_default_planner` drops the `extra_context` keyword supplied by the edit route.

W1 is therefore directionally right, and W3 is a good centralization for the
edit path. The plan is not safe to implement as written, however, because its
main premise says the Workflow Brief does not reach fresh generation when it
already does, W4 would either duplicate that brief or change every fresh
generation prompt, the generic `extra_context` renderer is explicitly
edit-only, and the proposed "redaction" does not redact PII. The design-card
premise is also stale: the current catalog already performs relevance scoring
and signature diversification.

### Scores

| Dimension | Score | Reason |
|---|---:|---|
| Correctness | 4/10 | Persona and edit-context gaps are real, but the fresh-generation call graph is misdescribed, W4 reuses an edit-only formatter, refusal has no representable result contract, and template/deterministic paths bypass persona behavior. |
| Simplicity | 5/10 | A nullable binding and one edit-context renderer are simple. Re-injecting an already-present brief through an untyped catch-all context, while combining persona rollout and design-card experimentation, adds avoidable complexity. |
| Security | 2/10 | `redact_draft()` / `redact_text()` detect a short list of secret patterns, not names, phone numbers, email addresses, national IDs, or medical data. The plan's third-party-LLM safety claim is unsound. |
| Conformance | 5/10 | The additive SQLite migration and existing Planner types fit repository patterns, but the plan does not reuse the existing ranked retriever precisely, omits the persona snapshot/UX work already called for by repo design, and misses generated API types and bypass paths. |
| **Overall** | **4.0/10** | Below the 7.0 pass threshold; Security is also at or below 3. |

## Verified production call graph

The statement "Every session generates IR from the raw user message alone" is
false on current main.

| Flow | Planner call | Context actually sent |
|---|---|---|
| Blank/self-design fresh generation | After brief review confirmation, `_finish_plan_from_draft()` calls the Planner with `_draft_to_planner_message(draft)` (`loom/service/routes/sessions.py:827-851`). | The message contains the redacted `draft.intent`, a `# Workflow brief draft` heading, and the serialized full draft (`sessions.py:1274-1279`). |
| Planner-assisted edit | The route builds `_edit_planner_context()`, folds it into `user_message`, and also passes it as `extra_context` (`sessions.py:257-292`). | Production receives the folded copy because `_default_planner` drops the structured keyword. |
| Deterministic edit | `_apply_deterministic_edit()` returns an IR directly (`sessions.py:264-273,994-1063`). | No Planner, persona, or design knowledge is consulted. |
| Template creation | `_seed_session_from_template()` validates and stores template IR directly (`sessions.py:1425-1480`). | No Planner or persona rule is consulted. |

This distinction matters: the proposed changes must preserve four paths, not
one convergence line.

## Consequence claims

### (a) "`render_persona_block(None)` means every production session runs dev-mode"

**Partly true, but materially overstated.**

- Every service call that reaches `_default_planner` currently creates an
  `IntentRequest` without `persona_brief` (`loom/service/app.py:45-65`), so
  `PlannerClient.call()` appends the `default-operator ... debug / dev mode`
  marker (`loom/planner/client.py:40-54,101-123`).
- There is no executable "dev mode" branch. It is prompt text, not a runtime
  flag.
- Not every production session reaches the Planner: template creation and most
  recognized edits bypass it.
- Persona catalog details are absent, but Workflow Brief compliance data is
  not necessarily absent. Fresh generation includes the serialized
  `compliance_boundary`; Planner-assisted edits include `workflow_brief` in
  their folded edit context when one exists.
- The standalone CLI accepts a full `IntentRequest`, including
  `persona_brief`, so the claim is only about the service default Planner path.

The accurate claim is: **every service invocation through `_default_planner`
currently passes `persona_brief=None` and therefore lacks a resolved catalog
persona.**

### (b) "`_default_planner` drops `extra_context`"

**True.**

The route supplies `extra_context=extra_context` at
`loom/service/routes/sessions.py:279-292`; `_default_planner` accepts arbitrary
keywords but constructs `IntentRequest` with only `intent`, `scope`, and
`target` at `loom/service/app.py:63-65`.

The existing route-level fold is why production edits still work. It is not
evidence that the context itself is unused by the current edit path.

### (c) "`extra_context` is only populated on the edit path"

**True for the service, but the conclusion drawn from it is false.**

`_edit_planner_context()` is the only service producer, guarded by
`current_doc is not None and parsed_edit is not None`
(`loom/service/routes/sessions.py:257-263`). Fresh generation omits the keyword
entirely. Fresh generation nevertheless sends the Workflow Brief through the
separate `_draft_to_planner_message()` path.

### Consequence 3: "A clarify probe cannot affect output"

**False.**

`missing_fields()` drives the deterministic clarify engine
(`loom/fde_session/clarify.py:22-107`;
`loom/fde_session/clarify_engine.py:65-95,278-282`). Answers are merged into
`WorkflowBriefDraft`, stored, and serialized into the eventual fresh Planner
message. A new probe that populates a draft field can therefore change both the
generation prompt and the resulting IR today. Planner wiring is a prerequisite
for persona/catalog assets that are not in the draft, not for the Workflow
Brief as a whole.

## W1 — Session persona binding

### Finding

**A persisted nullable persona binding is the right direction; `persona_id`
alone is not a complete session contract.**

There is no safe one-to-one derivation from `scope`. Both
`ecommerce-operator` and `ecommerce-cs-lead` map to ecommerce scopes, while a
persona also carries reviewer authority, end-user identity, geographies, and
success criteria that scope cannot reconstruct.

A no-SQLite-migration alternative exists: add persona data to
`WorkflowBriefDraft` and store it in the existing `brief_draft` JSON. It is a
worse fit:

- template-seeded sessions currently have no Workflow Brief;
- the brief is mutable workflow state, while persona is session identity;
- replacing or recovering the brief could silently lose the binding;
- it conflates the two ordered objects in ADR 0023.

The repository already uses additive, PRAGMA-probed nullable columns for
session fields (`loom/state/store.py:879-989`), so a nullable session column
conforms to the existing persistence pattern.

### Required corrections

1. Decide reproducibility semantics. Resolving only `persona_id` from live YAML
   means a catalog edit changes an existing session's next Planner call. ADR
   0023 permits a session to clone/override a registered Persona, and the
   accepted UX plan explicitly calls for storing `persona_id` **and the
   resolved snapshot** (`docs/plans/2026-06-21-fde-design-agent-ux-optimization.md:135-165`).
   Prefer either:
   - nullable `persona_id` plus a versioned/resolved persona snapshot; or
   - one nullable `persona_brief_json` containing the id and exact snapshot.
2. Define whether binding is immutable. If it can change, it must increment
   session revision, be actor-scoped, be audited, and invalidate/review an IR
   created under the previous persona.
3. Validate persona before creating the row, or make creation transactional.
   Do not create an orphan session and only then reject an unknown id.
4. Define persona/scope compatibility. A TCM persona with
   `scope=ecommerce/kb` is currently possible unless explicitly rejected or
   reconciled.
5. Include the binding in the relevant session response and regenerate
   `web/src/lib/types.generated.ts`. The current frontend always posts `{}` for
   a blank session and has no persona picker (`web/src/lib/api.ts:102-120`;
   `web/src/components/console/TemplateModal.tsx:12-119`). API-only support
   would leave all ordinary sessions at `None`.
6. Add a real legacy-database migration test: open a database whose sessions
   table predates the column and verify existing rows load with `None`.

The plan's open UX decision is therefore blocking for a deliverable opt-in
feature. W2 is not independently shippable without W1 and a way to set the
binding; W1 and W2 should be one atomic slice.

## W2 — Passing persona to the Planner

### Finding

Passing a resolved `PersonaBrief` into `IntentRequest.persona_brief` is correct,
but "this alone activates the compliance rules" overclaims what the code can
guarantee.

`PlannerClient` supports the object on every retry, but compliance is prompt
steering only. `validate()` receives `doc`, `scope`, and an audit-retention cap;
it never receives a persona (`loom/validator/validate.py:40-87`). There is no
persona-aware postcondition.

More seriously, the prompt says to "Refuse workflows" while the Planner
contract can only return valid IR JSON. A prose refusal becomes a schema error,
is retried, and eventually surfaces as generic `planner_error`. Verification
item 3 ("refused or gated") combines two different contracts and cannot be a
deterministic acceptance test.

### Required corrections

- Resolve through the app's already-loaded `app.state.persona_catalog`, or
  explicitly inject the catalog into the default Planner. `_default_planner`
  currently has no catalog dependency; reloading YAML on every call is an
  unnecessary hidden dependency.
- Choose one supported outcome:
  - require a **valid gated IR** and validate persona-specific invariants; or
  - add a typed refusal result and route/UI behavior.
  The current result type cannot represent the latter.
- Define precedence when the selected Persona and the Workflow Brief disagree,
  for example TCM/high/PIPL-medical versus a user-entered low compliance
  boundary.
- Cover template initialization and deterministic edits. Both bypass the
  Planner, so binding a persona does not make those flows compliant. At
  minimum, enforce persona/template compatibility and run persona-aware
  validation on every resulting IR.
- Describe this as model steering until deterministic validation exists, not
  as enforcement.

## W3 — Forwarding `extra_context`

### Finding

**Keeping the central retry renderer and removing the route renderer is the
correct direction for Planner-assisted edits, with three conditions.**

`_planner_message_with_context()` in the route and
`_intent_with_extra_context()` in `loom/planner/retry.py:65-73` currently emit
the same shape. Forwarding `extra_context` into `IntentRequest` and deleting
the route-level fold can therefore preserve the production edit prompt while
ensuring retries use the same payload.

The "structured path" description needs precision: `extra_context` is
structured at the Python boundary, but `retry.py` still serializes it into the
same user intent string before calling the LLM. This is central message
folding, not a distinct structured LLM channel.

### Edit regression conditions

1. Add a prompt snapshot/equality test showing a current Planner-assisted edit
   has byte-identical model intent before and after W3 and contains the payload
   exactly once on every retry.
2. Define the injected `PlannerCallable` contract. Removing the route fold
   means a custom Planner receives raw `user_message` plus structured
   `extra_context`, where today it receives both a folded message and the
   dictionary. Tests use this injection seam extensively.
3. Keep the renderer edit-specific. Its unconditional suffix says:
   "Apply only the declared edit and preserve every field outside
   allowed_change_fields." That is correct for `_edit_planner_context()` and
   wrong for fresh generation.

With those conditions, W3 should not regress the current edit path.

## W4 — Fresh context and design-knowledge cards

### Workflow Brief

Do **not** add a second fresh-generation brief copy.

Today `_draft_to_planner_message()` already adds the full draft. If W4 keeps
that message and also sets `extra_context["brief"]`, the model receives the
brief twice. If W4 replaces the existing formatter, then a
`persona_id=None` session no longer produces today's prompt. Either outcome
contradicts verification item 1.

The simpler design is:

- keep one generation renderer;
- keep one edit renderer;
- make the existing generation renderer accept the already-redacted brief and
  optional ranked pattern hints;
- do not route fresh context through an edit-only suffix.

Use consistent naming (`workflow_brief`, not `brief` in one mode and
`workflow_brief` in another), preferably through typed generation/edit context
models rather than an unconstrained `dict[str, Any]`.

### Design knowledge and N=3

The plan's premise that cards are "scope-filtered but not relevance-ranked" is
false. `DesignKnowledgeCatalog.retrieve()` already:

- hard-filters by scope and target;
- builds a query from intent, brief, and persona;
- scores tags, names, descriptions, persona vertical/compliance/reviewer data;
- sorts by descending score;
- diversifies by node signature;
- enforces `top_k`
  (`loom/registry/design_knowledge.py:78-104,217-307`).

Existing tests assert ranking and diversification
(`tests/registry/test_design_knowledge.py:26-77`), and the accepted UX plan
already names top 3 as the intended candidate count
(`docs/plans/2026-06-21-fde-design-agent-ux-optimization.md:334-364`).

Therefore **N=3 is a defensible maximum if W4 calls `retrieve()` with intent,
scope, target, persona, and the brief.** It is not defensible as "take the
first three scope matches."

One gap remains: `retrieve()` returns up to `top_k` even when lexical relevance
is zero, and the internal retrieval score is not exposed. Make injection
**0..3**, with an abstention/minimum-relevance rule and evals. Preserve at least
card `id`/source provenance alongside the four projected planning fields;
otherwise audit and quality diagnosis cannot tell which pattern influenced the
Planner. Do not treat the card's current `confidence` as a pure relevance
score—it starts from template properties before retrieval score is added.

Direct card injection is not blocked on implementing a new ranker; ranking
already exists. It should still be a separate, measurable slice after persona
and prompt-channel correctness, not bundled into the safety-critical persona
rollout.

## Security review

The proposed brief-redaction mitigation is not sound.

`loom/fde_session/redaction.py:13-29` recognizes bearer/authorization strings,
OpenAI/Stripe-like keys, and `api_key=...`. It does not recognize ordinary
PII. A direct probe on current main left this input unchanged in the redacted
draft:

```text
Patient Alice Zhang, phone 13800138000, email alice@example.com,
ID 110101199001011234
```

The title `"Alice's follow-up"` and success criterion `"Send Alice her lab
result"` were also unchanged. `redact_draft()` only applies that same secret
detector to selected text fields and does not make the brief safe for a
third-party model (`redaction.py:32-50`).

This is an existing exposure because `_draft_to_planner_message()` already
sends the brief; W4 would duplicate rather than create it. The plan must not
claim safety based on the existing helper.

Required controls before the security claim can pass:

1. Define an outbound Planner data policy separately from persistence
   redaction. Prefer data minimization and a field allowlist: workflow
   structure, handle names, categories, constraints, and policy labels—not
   customer/patient instance records.
2. Reject or transform direct identifiers before Planner assembly, covering at
   least names paired with case data, phone, email, national ID, address,
   account/order identifiers where sensitive, and medical free text.
3. Keep raw secrets blocked as today; PII filtering is additive, not a
   replacement.
4. Test the final assembled outbound system/user messages, not only an
   intermediate draft object. Seed multiple realistic PII classes and assert
   they are absent.
5. Define fail-closed behavior when safe transformation is uncertain. A single
   "known PII marker" assertion is too easy to satisfy without protecting
   unseen values.

## Does the nullable column contain behavior risk?

Only partially.

- For W1+W2 alone, strict `None -> persona_brief=None` behavior can preserve
  legacy service Planner calls.
- W4 changes every fresh self-design prompt, including existing rows whose
  `persona_id` is `None`; the nullable column does not contain that change.
- A persona-bound session can break because refusal has no typed result and
  becomes `planner_error`.
- Resolving a live catalog id without a snapshot lets later YAML changes alter
  old bound sessions.
- Template creation and deterministic edits bypass persona behavior, producing
  inconsistent enforcement rather than safely contained behavior.
- An incompatible persona/scope or persona/brief pairing can give the model
  contradictory instructions.

Verification item 1 ("`persona_id=None` produces a prompt identical to
today's") is valid for an isolated persona slice, but impossible for the full
W1-W4 plan. Split the rollout and snapshot prompts per slice.

## Required revised sequence

### Slice A — Persona binding and supported compliance outcome

1. Persist a nullable, reproducible persona binding (id plus snapshot/version,
   or a serialized Persona Brief).
2. Add create/read/API/generated-type/UI plumbing and audit/revision behavior.
3. Validate persona/scope/template compatibility and persona/Workflow Brief
   precedence.
4. Resolve from the app catalog and pass the same Persona Brief through fresh
   generation and Planner-assisted edits.
5. Require a valid gated IR or introduce a typed refusal; do not leave the
   outcome ambiguous.
6. Cover template and deterministic bypasses with persona-aware validation.

Legacy `None` prompts should remain unchanged in this slice.

### Slice B — Repair the edit context channel

1. Forward existing edit `extra_context` from `_default_planner`.
2. Remove `_planner_message_with_context()` from the route.
3. Prove model-input equivalence, exactly-once context, retry persistence, and
   custom-Planner contract behavior.

This slice should be behavior-preserving.

### Slice C — Generation context and pattern hints

1. Keep the Workflow Brief exactly once through a generation-specific
   renderer.
2. Call the existing ranked `DesignKnowledgeCatalog.retrieve()` with all
   available signals.
3. Inject 0..3 projected cards with relevance abstention and source ids.
4. Measure token growth and IR quality on the existing ecommerce and TCM eval
   cases before enabling it broadly.

This slice is an intentional behavior change and must not use the nullable
persona column as its rollout boundary.

### Slice D — Outbound-data safety

Implement and test an outbound Planner minimization/PII policy before claiming
that Workflow Brief transmission to a third-party LLM is safe. This is a
release blocker for the security argument, regardless of whether card
injection ships.

## Revised verification minimum

1. Legacy database opens and every old row resolves to no persona.
2. W1+W2 only: `persona_id=None` produces byte-identical system and user
   messages.
3. A bound persona is stable across catalog changes, or catalog versioning
   explicitly invalidates/re-resolves it.
4. Persona/scope, persona/brief, and persona/template conflicts have
   deterministic outcomes.
5. TCM generation yields a valid gated IR that passes a persona-aware
   postcondition; a refusal, if supported, uses a typed response.
6. Template creation and deterministic edits cannot bypass the chosen persona
   postcondition.
7. Planner-assisted edit context appears exactly once on every retry and is
   byte-equivalent to today's edit prompt.
8. Fresh Workflow Brief appears exactly once and never receives edit-only
   instructions.
9. Design knowledge uses ranked retrieval, injects 0..3 cards, retains source
   ids, and abstains on irrelevant input.
10. Final outbound messages contain none of the seeded secret, phone, email,
    national-ID, address, or medical-record markers.
11. Targeted backend tests, full suite, ruff, mypy, generated OpenAPI types,
    web tests, and web build are green.

## Bottom line

Do not implement the plan verbatim. Keep the nullable session binding concept,
make persona binding reproducible, and perform W3 as an edit-only
behavior-preserving cleanup. Correct the problem statement to acknowledge the
existing Workflow Brief generation path, use the already-ranked catalog with
an abstention rule, and replace the current secret scrubber with a real
outbound-data policy before sending any additional context to the third-party
Planner.
