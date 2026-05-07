# FDE — Forward-Deployed Engineer for AI Workflows PRD v0.4

*(Previous codename: Loom. Product name and direction: **FDE**, short for **Forward-Deployed Engineer**. Chinese product language: **AI 驻场流程工程师**. Do not expand FDE as "Front-End Development Engineer"; that reading is explicitly out of scope. The implementation package may keep the `loom/` namespace temporarily, but product docs, user-facing language, and roadmap language should use FDE.)*

### Change log: v0.3 → v0.4

Repositioned the product around the **FDE role** rather than the IR/compiler mechanism. The goal is no longer "a workflow compiler users operate" but "an AI forward-deployed engineer that sits with the user, accepts spoken/typed business intent, asks clarifying questions, creates and edits workflows in the target runtime, and preserves an auditable source of truth."

- **§1, §2** — Reframed the pitch: FDE is the user-facing product; IR + Validator + Compiler + Reverse Compiler are the internal machinery that makes the FDE trustworthy.
- **§3** — Added the FDE role/capability model. The Author no longer thinks in IR or Dify DSL; the Author collaborates with FDE as if with an embedded implementation engineer.
- **§4, §6** — Added a conversational create/edit loop ahead of the Planner. Phase 1 must prove typed oral-style requests and edit instructions, not only JSON request files.
- **§7** — Updated Phase 1 to include a minimal FDE session loop: create from intent, edit from natural language, validate, compile, push as draft on the chosen target runtime (Hiagent primary / Dify secondary in v1), and reverse-compile recognized runtime-side edits.
- **§10** — Added FDE-specific metrics: clarification-turn count, natural-language edit success, time from spoken intent to runtime draft, and user-perceived "would I ask this instead of a human engineer?" rating.
- **§11** — Resolved the naming question in favor of FDE, with a remaining trademark/domain availability check before external launch.
- **China wedge** — First SOW / partner assumption is now cross-border ecommerce operations as the primary vertical and TCM clinic operations as the secondary/shadow vertical. Finance/audit and IP agency workflows are not the current primary wedge.

### Previous change log: v0.2 → v0.3

Patches applied after a Plan Review pass (Codex) and a market/design pass (Gemini). Net change: tighter contracts at the IR↔Dify boundary, governance-first positioning, and a more honest Phase 2.

- **§1, §2** — Added governance framing as the *primary* outcome (productivity is the lure, governance is the buyer). Added "Terraform for AI workflows" analogy.
- **§3** — Clarified that Author/Reviewer are *roles*, not necessarily distinct people. Publish rights + audit trail enforce the role boundary even when one person plays both.
- **§5** — Added `rationale` field on every node (the Planner externalizes its reasoning; reviewers actually read this). Tightened IR typing rules (nullable/optional, branch-result typing, loop-item typing, parallel-merge typing). Renamed "agentic islands" → "bounded agent zones" (clearer; "island" implied disconnection, the contract is the opposite).
- **§6** — Replaced "hash the emitted DSL bytes" with **canonical Dify-AST hashing** for drift detection (raw byte hashing produces constant false drift after Dify's import/export normalizes the YAML). Reverse compiler IR equality is now defined over canonical IR (sorted keys, default-stripped, stable IDs), not literal equality.
- **§7** — **Phase 1 ships dual-runtime (Hiagent primary + Dify secondary) from Day 1** via a `RuntimeAdapter` abstraction (originally Phase 3.1). **Phase 1.5** widens both compilers to the 3 TCM shadow archetypes; reverse stays narrow on the two ecommerce deep-coverage archetypes. **n8n removed** from v1 scope (decision 2026-05-06); runtime portability is proven by Phase 1's dual-build. **Phase 3.2** (was n8n GA) is now optional LangGraph alpha. **Phase 2** still split into 2A (load-bearing infra) and 2B (UI + RBAC + trace + full reverse). **Persona Brief** is a new first step in the FDE Session before the Workflow Brief — captures Author / vertical / End User / Reviewer / compliance boundary so the system is persona-agnostic instead of vertical-locked.
- **§9** — Added: IR-version migration story, prompt/tool-description injection, code-node sandbox escape, trace PII retention, trace volume cost, conformance-test flake. Expanded the Dify-native NL→workflow risk with explicit **kill/pivot trigger criteria**.
- **§10** — Failure taxonomy expanded beyond Planner-centric buckets (added: compile, deploy, runtime conformance, reverse-compile, registry/ACL, human-review rejection). Added operational metrics: reviewer hard-block rate, conformance-suite flake rate, trace storage cost, P95 Planner cost/latency.
- **§11** — Q1/Q2/Q3/Q5/Q6 are no longer external Phase 0 blockers. They are Phase 0 default decisions: SOW intake contract, Hiagent 2.6 + Dify 1.14.0 pins, credential-binding strategy, reverse-compile default scope, and Agent / LLM defaults (`max_output_tokens = 8000`). Q4, Q7, Q8, Q9 remain open.

## 1. Pitch

FDE is an **AI forward-deployed engineer for workflow automation**. A user describes a business process in natural language, as if speaking to an engineer sitting beside them. FDE asks the missing questions, creates the workflow, opens it in the target runtime for visual review, accepts natural-language edit requests, and keeps a git-backed, auditable source of truth in sync.

The user-facing promise is not "generate an IR." The promise is: **口述需求，FDE 帮你搭好、改好、验证好，并推到 Hiagent / Dify 这类运行时成为可审查草稿。**

Internally, FDE turns natural-language intent into deterministic, reviewable, production-ready workflows. The LLM's job moves from runtime execution to compile-time authoring: it emits a small, validatable Intermediate Representation (IR), which deterministic compilers translate into **Hiagent (primary) and Dify (secondary) workflows from Day 1** (Phase 1 ships dual-runtime). Humans review the workflow visually in the target runtime's editor, approve it, and ship it. Agents don't disappear — they live as **bounded agent zones** inside the deterministic graph, where their unpredictability is contained by typed I/O, scoped tools, and budget ceilings.

The thesis: **agentic for authoring, deterministic for production.**

The shortest external framing: **an AI FDE for workflow teams.** The shortest technical framing remains: **Terraform for AI workflows.** HCL became the industry standard IR for infrastructure-as-code, compiling to AWS / GCP / Azure APIs. FDE's IR aims to be the equivalent for LLM workflows, compiling to Hiagent + Dify in v1 (and LangGraph as an alpha candidate in Phase 3.2 if budget allows) — so that an org running multiple runtimes, or migrating between them, owns a portable, diffable, auditable source of truth for every workflow. n8n was scoped out 2026-05-06.

To make the contrast concrete: authoring a multilingual customer-support pipeline with a runtime-agent harness (OpenHands-style) might consume many LLM calls, several minutes, and produce a non-reproducible run. The FDE path is a short requirements conversation plus one Planner loop that emits an IR file, which then compiles deterministically and executes the same way every time. The cost shifts from runtime to authoring time, and the resulting workflow is a stable, reviewable artifact instead of an agent transcript.

**Working assumption for the first SOW:** China-market cross-border ecommerce operations. The SOW should cover real or synthetic workflows around multilingual customer support, order-exception triage, product-content localization, after-sales escalation, and operations reporting (DAU/GMV/return-rate dashboards). TCM clinic operations is the secondary/shadow vertical: pre-consultation intake, follow-up, knowledge-base support, and triage are kept as the cross-vertical transferability check. The product must not (in the TCM shadow) provide diagnosis, prescriptions, treatment claims, or any path that bypasses clinician/compliance review; FDE produces governed workflow drafts.

See `docs/design/fde-ecommerce-tcm.zh-CN.md` for the China-market product design.

## 2. Problem & Goals

### Problem

Pure runtime-agent harnesses (OpenHands, raw ReAct loops, Claude Code-style harnesses) are powerful for exploration but fragile in enterprise production: nondeterministic execution paths, runaway token costs, weak audit trails, opaque permissions, recovery semantics that effectively mean "rerun from scratch." Visual workflow runtimes (Hiagent, Dify, Coze) solve those problems but require humans to hand-build every flow.

The gap: teams need the equivalent of a forward-deployed engineer who can sit with the business owner, understand the process, build and revise the runtime workflow, and leave behind a governed artifact. Hiring or borrowing that engineer does not scale; raw agents are not governable enough; visual builders still require manual implementation work.

FDE fills that gap: a role-like AI system that produces and edits visual workflows from intent, with the LLM constrained enough to be reliable.

### Outcomes (v1)

What we're trying to move, in user/business terms. **Governance is the primary outcome — productivity is the lure.** The buyer (Engineering Platform / AI Ops, see §3) pays for safety harness; the Author experiences time-to-ship.

- **Governance / audit trail** — Every LLM workflow in the org has a single source of truth in git, with a strict drift-detection contract against the deployed runtime (§6). Auditors get a reproducible, diffable artifact instead of a runtime-platform export (Hiagent / Dify / etc.) and an agent transcript. This is the budget-unlocking outcome.
- **FDE collaboration loop** — Users can describe a workflow in natural language, answer clarifying questions, and request edits in natural language. FDE turns that collaboration into a runtime draft and source-of-truth IR without exposing users to IR mechanics.
- **Pre-runtime validation** — Generation errors (hallucinated tool refs, missing variables, broken type flow, agent-budget violations) are caught before reaching the target runtime. Concrete targets per phase in §10.
- **Bounded agent zones** are a first-class IR construct (§5), so unpredictable LLM behavior is contained inside typed, budget-capped, scoped-tool boundaries — composable from the rest of the deterministic graph.
- **Time-to-ship** for a new internal LLM workflow drops from days to <1 hour for archetype shapes.
- **Non-engineer Authors** can draft and submit production-quality workflows without engineering help. Final publish still requires Reviewer approval (security/SRE/senior eng) per the Author/Reviewer separation in §3 — that gate is a feature, not friction we're trying to remove.
- **Reviewers** spend <5 min approving a generated workflow vs. hours hand-building it.
- **Portability** — IR is runtime-agnostic. Phase 1 ships dual-runtime support (Hiagent primary + Dify secondary) via a `RuntimeAdapter` abstraction; portability is proven by construction. n8n was scoped out 2026-05-06.

### Outputs we'll build to achieve those outcomes (v1)

- NL intent + declared context (tools, datasets, constraints) → valid, executable workflow on the target runtime (Hiagent or Dify in v1).
- Natural-language edit instruction + current workflow state → validated updated IR + updated draft on the same target runtime.
- Clarification loop that asks for missing trigger, data source, credential, approval, and output-shape details before generating unsafe or underspecified workflows.
- Pre-runtime validation that catches generation errors at IR-time before they reach any target runtime. Concrete targets per phase in §10.
- Bounded agentic sub-tasks as a first-class IR node type.
- Every workflow has an IR file in git, semantically diffable across versions, with a strict drift-detection contract against each deployed runtime workflow (§6.4 — one (workflow, target) row per registered runtime).
- One-click "draft → review in target runtime → approve → deploy" loop.

### Non-goals (v1)

- Additional runtimes beyond Hiagent + Dify (LangGraph alpha optional in Phase 3.2; Temporal post-v1; n8n scoped out 2026-05-06).
- Building a new runtime or visual editor (we ride on the target runtimes' editors — Hiagent and Dify).
- Replacing agentic exploration; agents stay useful, just not as production runtime.
- Covering 100% of any runtime's node types — only what real workflows need; the IR is the contract, not a Hiagent / Dify superset.
- Medical diagnosis, prescription advice, treatment claims, or any publishing path that bypasses human clinical/compliance review.

### Prior art and positioning

The space is crowded. FDE positions against:

- **Hiagent, Dify, Coze, Activepieces** — visual workflow runtimes with hand-authored flows. FDE sits *above* them as an AI implementation role and authoring layer. We expect each to ship native NL→workflow, but those are runtime-locked and validate at runtime; FDE's IR is portable across runtimes and validates pre-runtime.
- **LangFlow, Flowise** — visual front-ends that emit code or LangChain graphs. Closer to the earlier compiler-centered idea, but no IR-as-contract: edits and generations interleave, no clean diff/git story, no separation of authoring from runtime.
- **LangGraph, Temporal** — durable execution, but pure code with no NL authoring or visual review. Possible FDE compile targets later.

FDE's defensible wedge: the role experience plus IR + pre-runtime validator + reverse compiler (so reviewer edits round-trip back to source-of-truth). If Hiagent or Dify ships NL→workflow without an IR layer, those generations are still tied to one runtime, still validated only at runtime, still not portable across the runtimes a multi-platform org deploys. We bet that matters in enterprise. We watch this competitive risk explicitly in §9.

## 3. Users & Primary Use Cases

Three roles:

- **Authors / Requesters** — analysts, ops engineers, clinic operators, ecommerce operators, junior devs. Describe what they want in natural language, pick from a tool/dataset catalog, answer FDE's clarifying questions, and get a working workflow draft on the chosen target runtime. Don't need to know Hiagent JSON, Dify DSL, or IR.
- **FDE** — the AI forward-deployed engineer. It elicits requirements (Persona Brief + Workflow Brief), identifies missing context, creates IR, validates it, compiles it, pushes a draft to the chosen target runtime via the RuntimeAdapter, accepts edit requests, explains review-relevant changes, and preserves the source-of-truth contract.
- **Reviewers** — senior engineers, SREs, security. Open the generated workflow in the target runtime's visual editor (Hiagent or Dify), diff against previous version, approve or reject.
- **Operators / End users** — run the deployed workflows.

**Buyer personas (separate from end-user roles):**

- **First China-market wedge:** Cross-border ecommerce sellers, ecommerce SaaS / 3PL integrators, and brand operations service providers serving Amazon / Shopify / TikTok Shop / Shein / Temu sellers. The budget is multilingual customer-support standardization, order-exception throughput, listing localization, after-sales SLA compliance, customer-PII handling, and reviewable change-control over agent-driven workflows. TCM clinic chains and clinic-management SaaS vendors are the secondary wedge for the same governance story applied to medical operations (intake, follow-up, knowledge-base support, triage); a TCM partner is desirable but not required to start.
- **Later technical buyer:** Engineering Platform / AI Ops team in a 200–2000-person tech company. The budget is "AI governance / safety harness," not "developer productivity tool."

**Author and Reviewer are roles, not necessarily distinct people.** In small early-partner teams, the same person may hold both. Role separation is enforced by *capability*, not headcount: publish rights and audit trail remain split even when one human plays both parts. v1 leans on the underlying target runtime's RBAC (Hiagent / Dify workspace) for the publish capability and writes its own audit trail to the workflow registry (§8). FDE-native RBAC ships in Phase 2B.

Initial use-case archetypes (these drive the IR scope and must be validated or replaced by the Phase 0 SOW). Primary archetypes are cross-border ecommerce; archetype 02–04 are kept as TCM shadow workflows for cross-vertical transferability checks:

1. **Cross-border ecommerce customer FAQ / KB Q&A** — multilingual buyer questions answered from product / policy KB with citations, low-confidence escalation, and channel-specific tone (Amazon, Shopify, TikTok Shop, Shein, Temu).
2. **TCM pre-consultation intake and triage** *(shadow)* — patient request/form → structured summary → manual review queue.
3. **TCM clinic operations ETL + summarize** *(shadow)* — appointment, follow-up, support, inventory/pharmacy data → daily/weekly digest → manager approval.
4. **TCM follow-up and treatment-course operations** *(shadow)* — scheduled follow-up → anomaly escalation → record writeback.
5. **Cross-border ecommerce order-exception triage** — order/shipment/return anomalies → multilingual customer reply + ops queue routing + refund / replacement workflow with manager approval where SLA-impacting.

**These are SOW-backed hypotheses, not generic demos.** Phase 0's first task is to validate or replace them against five workflow candidates in the SOW. The SOW can come from a real partner or a synthetic Bambu Lab-style ecommerce operator. If the SOW list looks materially different, the IR scope re-opens before Phase 1.

### FDE capability model

FDE must be evaluated as a role, not only as a compiler:

1. **Persona resolution** — resolves a Persona Brief (Author role / vertical / End User / Reviewer / compliance boundary) from the per-tenant Persona registry before asking workflow questions. Without this, FDE collapses into a vertical-locked tool.
2. **Requirements capture** — turns an oral-style request into a precise workflow brief; asks clarifying questions when trigger, data source, credential, policy, or output shape is missing. Asks within the constraints set by the Persona Brief.
3. **Workflow creation** — produces valid IR, compiles to the chosen runtime (Hiagent primary / Dify secondary in v1) at its pinned version, and pushes a draft.
4. **Workflow editing** — accepts natural-language edits like "change retrieval top_k from 20 to 15", "retry twice before failure", "send high-risk cases to manual review"; updates IR and draft deterministically on the same runtime.
5. **Review support** — explains what changed in reviewer language: nodes added/removed, credentials touched, policies changed, agent budget changed, compliance boundary changes, security implications.
6. **Governance preservation** — never edits only the runtime draft and loses source truth; every recognized edit round-trips back to IR, and every unrecognized edit hard-blocks with remediation.
7. **Runtime handoff** — leaves the workflow in the target runtime as a draft ready for visual inspection and approval.

## 4. Architecture

```
   ┌──────────────┐
   │  User Intent │  spoken / typed request + declared context
   └──────┬───────┘
          ▼
   ┌──────────────┐
   │ FDE Session  │  clarify → brief → edit intent → review explanation
   └──────┬───────┘
          ▼
   ┌──────────────┐
   │   Planner    │  LLM with structured outputs, IR grammar in system prompt
   │     (LLM)    │  + few-shot library + retrieval over past workflows
   └──────┬───────┘
          ▼
   ┌──────────────┐
   │      IR      │  ← canonical artifact, lives in git
   │   (JSON)     │
   └──────┬───────┘
          ▼
   ┌──────────────┐
   │  Validator   │  schema check + semantic check (tool refs, var refs, types)
   └──────┬───────┘
          │ if invalid → feedback loop to Planner (max 3 retries)
          ▼ if valid
   ┌──────────────┐
   │   Compiler   │  pure function via RuntimeAdapter: IR → target DSL
   │              │  (Hiagent JSON or Dify YAML; one adapter per target)
   └──────┬───────┘
          ▼
   ┌──────────────┐
   │   Deployer   │  push to target runtime API as draft → human review → publish
   └──────┬───────┘
          ▼
   ┌──────────────┐
   │Target Runtime│  Hiagent / Dify executes; emits traces
   └──────┬───────┘
          ▼
   ┌──────────────┐
   │   Observer   │  trace store; feeds back to Planner's retrieval corpus
   └──────────────┘
```

Three architectural commitments worth calling out:

- **The IR is the contract.** Everything upstream produces IR; everything downstream consumes IR. Compiler, validator, deployer never call the LLM. This is what makes the system testable.
- **The Planner is replaceable.** Today it is an OpenAI/Anthropic-compatible structured-output model; tomorrow it could be a fine-tuned small model. The IR doesn't care.
- **The target runtime is replaceable.** A new compiler is a few weeks of work, not a system rebuild.

### How the Planner gets context

"Declared context" is non-trivial at enterprise scale: realistic catalogs have 100+ tools and won't fit in a prompt. v1 design:

- The FDE session maintains a workflow brief: trigger, inputs, datasets/tools/credentials, success criteria, review policy, and known edits. The Planner receives this structured brief, not just raw chat history.
- The Author selects a **scope** at authoring time (e.g., a project, a team, a workflow template). Scope filters the catalog to typically <30 tools/datasets.
- That filtered set is embedded directly in the Planner's system prompt as a typed registry.
- A retrieval pass over past IR files (filtered by scope) surfaces 2–4 relevant few-shot examples.

If a single scope still exceeds prompt budget in Phase 1, fall back to retrieval-augmented selection (top-K tools by name/description match against the intent). Defer building this until we hit the limit.

## 5. The IR (Intermediate Representation)

The single most important design artifact. Scope it small, version it explicitly, validate it ruthlessly.

### Top-level

```json
{
  "ir_version": "0.3",
  "metadata": {
    "name": "...",
    "description": "...",
    "owner": "...",
    "rationale": "..."
  },
  "registry_ref": {
    "registry_version": "sha:b7c3d2e",
    "tools": ["web_search", "fetch_url", "translate"],
    "datasets": ["product_kb", "policy_kb"],
    "credentials": ["shopify_api", "amazon_sp_api", "wechat_work_api"]
  },
  "policy": {
    "default_timeout_s": 60,
    "default_retry": { "max_attempts": 3, "backoff": "exponential" },
    "agent_budget": { "max_iterations": 10, "max_tokens": 50000, "max_wall_clock_s": 300 }
  },
  "inputs":  [ { "name": "query",  "type": "string", "required": true } ],
  "outputs": [ { "name": "answer", "type": "string" } ],
  "nodes": [ ... ],
  "edges": [ ... ]
}
```

Two notes on this top-level shape:

- **`rationale` (new in v0.3)** — Every IR document carries a top-level rationale, and every node carries a per-node `rationale` (see node-types section). The Planner uses it to externalize *why* a step exists. It is what reviewers actually read in PR diffs and what makes a generated workflow legible six months later. It has no runtime semantics — each runtime adapter emits it as a node description / comment where that runtime supports it (Hiagent: `description` field; Dify: node-level annotation), and discards it where it does not. Reverse compile preserves it round-trip.
- **`registry_ref.registry_version` is now an immutable SHA** (was: calendar tag in v0.2). Calendar tags drift; SHAs don't. The registry is a git repo, and every IR pins a commit. Deprecation/removal of a registry handle is a deliberate registry commit, surfaced as an explicit deprecation event (§5 "Credential handles").
- The `policy` block (added in v0.2) provides per-workflow defaults for timeouts, retries, and agent budgets. Individual nodes can tighten but not loosen.

### Node types (v1 — keep this list short)

- `trigger` — manual, schedule, webhook
- `llm` — model, prompt template, optional output schema for structured response
- `retrieval` — query a registered dataset, return chunks
- `http` — call an external API (via opaque credential handle from the registry; see "Credential handles" below — never inline secrets)
- `code` — Python/JS sandbox cell (constrained imports). **Allowed for legitimate transforms; banned as a substitute for missing IR semantics.** See Phase 0 gates in §7.
- `condition` — if/else or switch on a variable expression
- `loop` — iterate over a collection (bounded by max_iterations)
- `parallel` — fan-out N branches, fan-in with merge strategy
- `agent` — bounded ReAct: declared tools, max_iterations, max_tokens, fallback path
- `output` — terminal node binding to workflow outputs

That's ten node types. We resist adding more until a real workflow needs one.

Every node, regardless of type, carries:

```json
{
  "id": "...",
  "type": "...",
  "rationale": "Why this node exists in the workflow — written by the Planner, read by reviewers."
}
```

`rationale` is mandatory in v0.3. The Validator rejects nodes with empty or placeholder rationale strings.

### Bounded agent zones (the `agent` node)

The whole pitch hinges on this working, so it gets its own subsection. (v0.2 called these "agentic islands"; renamed in v0.3 because "island" suggested disconnection — the contract is the opposite: typed I/O, scoped tools, budget caps, deterministic fallback paths. The agent is *bounded*, not *isolated*.)

```json
{
  "id": "research_agent",
  "type": "agent",
  "model": "configured-planner-model",
  "tools": ["web_search", "fetch_url"],
  "input_schema":  { "topic": "string" },
  "output_schema": { "findings": "string", "sources": "string[]" },
  "budget": { "max_iterations": 8, "max_tokens": 30000, "max_wall_clock_s": 240 },
  "on_budget_exhausted": "fallback",
  "fallback_edge": "summarize_node"
}
```

Contract:

- **Typed I/O — runtime-enforced.** Every agent declares an `input_schema` and `output_schema`. The Validator treats the agent as a black-box function with those types. The runtime enforces the output schema with a post-agent validator step; schema-invalid output emits a structured event and applies the on-exhaustion policy (it does not silently propagate).
- **Tool scoping.** `tools` must be a subset of the workflow's tool registry. The Validator rejects agents that reference tools the Author hasn't granted. **Side-effecting tools must be explicitly marked `side_effects: true` in the registry**; the Compiler emits an idempotency wrapper for them and the runtime audits every call (tool, args, result, latency) to the trace store.
- **Budget.** `max_iterations`, `max_tokens`, and `max_wall_clock_s` are mandatory in v0.3 (was: just iterations + tokens in v0.2). Workflow-level `policy.agent_budget` provides defaults; nodes can tighten but not loosen.
- **Partial output shape.** When `on_budget_exhausted: "return_partial"`, the agent emits an object matching `output_schema` with required fields filled best-effort, plus `_partial: true` and `_partial_fields: string[]` listing the fields the agent did not converge on. Downstream nodes that branch on `_partial` are explicit; the Validator rejects workflows that consume partial output without checking the flag.
- **Failure semantics.** On budget exhaustion, `on_budget_exhausted` decides: take the `fallback_edge` (deterministic recovery path), `fail` the workflow, or `return_partial`.
- **Output validity.** If the agent returns output that doesn't match `output_schema`, the runtime treats it as a budget-exhaustion event and applies the same policy.

This contract is what makes agents composable inside a deterministic graph. Without it, an agent is a black hole.

### Data flow and typing

- Every node has typed `inputs` and `outputs`.
- Variable references use a single path syntax: `${node_id.output.field}`, with `.field[index]` for arrays and `.field.subfield` for nested objects. Missing references are validation errors, not runtime nulls.
- The Validator builds a DAG and checks: every reference resolves, no cycles outside `loop`, types match (with explicit coercion rules — string→number requires a `code` node), tool refs exist in the registry.

**Type system (formalized in v0.3):**

- **Primitives:** `string`, `number`, `boolean`, `null`.
- **Compounds:** `array<T>`, `object<{k: T, ...}>`, `union<T1 | T2>`.
- **Nullability and optionality are distinct.** `T?` means optional (the field may be absent); `T | null` means present-but-null. The Validator rejects implicit conflation.
- **Branch result typing.** A `condition` node's downstream edges carry a *narrowed* type when the branch predicate is a type guard (`x != null`, `x.kind == "ok"`). Branches that don't narrow inherit the input type.
- **Loop item typing.** A `loop` over `array<T>` exposes `${loop_id.item}: T` and `${loop_id.index}: number` to the body. The loop's own output type is `array<U>` where `U` is the body's terminal type.
- **Parallel merge typing.** A `parallel` node declares a `merge_strategy`: `concat` (output type = `array<T>` where T is the common branch type), `object_merge` (output type = `object<{branch1: T1, branch2: T2, ...}>`), or `first_success` (output type = the union of branch types, narrowed to the successful one). The Validator rejects strategies whose declared types are inconsistent with the branches.
- **Edge semantics.** Edges carry both control flow and data flow. An edge `A → B` means "B may execute after A completes" *and* "B's input scope includes A's outputs." Pure control edges (no data dependency) are allowed but must be marked `data: false` for the Validator to skip type-flow checks on that edge.
- **Variable escaping.** The single path syntax `${...}` is escaped in string literals as `$${...}`. The Validator rejects ambiguous nesting.
- **Error outputs.** Every node implicitly has an `error` output of type `object<{code: string, message: string, retryable: boolean}>`. Downstream nodes may reference it but must explicitly declare an error edge; the Validator rejects silent error-path branching.
- **Coercion is explicit.** No implicit `string → number`, `number → string`, or stringification. The Author inserts a `code` node, or the Compiler refuses.

### Per-node runtime policy

Every executable node may carry:

```json
"timeout_s": 30,
"retry": { "max_attempts": 2, "backoff": "exponential", "retry_on": ["5xx", "timeout"] },
"idempotency_key": "${input.query_hash}"
```

Defaults come from the top-level `policy`. The IR carrying retry/timeout/idempotency policy explicitly is what keeps multiple compilers honest (Hiagent + Dify in v1; LangGraph + others post-v1); if it lived only in one compiler, portability would be a fiction. Non-idempotent `http` and `code` nodes must declare an `idempotency_key`; the Validator enforces this.

### Credential binding and the registry pin

The IR references credentials, tools, and datasets — but never holds secret values. Rules:

- **Platform-managed LLM credentials.** LLM provider keys are configured inside the target runtime platform (Hiagent / Dify) by the operator. FDE-generated YAML / JSON / ZIP packages reference the provider/model binding but do not embed API keys. After import, the operator binds the workflow to the platform's configured LLM credential.
- **HTTP credentials for non-LLM integrations.** Non-LLM credentials are represented as HTTP-node auth bindings: handle name, auth scheme, header/query placement, allowed host, and required TLS. The secret value is configured in the target platform or supplied by the operator at import/configuration time; at execution time it travels only from the runtime to the external API over HTTPS. FDE never stores or serializes the secret value.
- **Opaque handles in IR.** A node references a credential by stable handle: `"credential": "shopify_api"`. The Validator checks the handle against the workflow's `registry_ref.credentials`; the runtime adapter emits a target-runtime binding using the same handle. The handle may resolve to a platform LLM credential or an HTTP auth binding, but not to a secret value in the generated artifact.
- **Registry is versioned with the IR.** Every IR pins a `registry_ref.registry_version` (an immutable commit SHA of the registry repo, in v0.3). The Validator resolves all tool/dataset/credential refs against *that* version, not "latest." This makes IR diffs over time meaningful — a workflow doesn't silently break because the registry shifted.
- **Permission checks at author time and review time.** The Author can only reference handles their scope grants. The Reviewer's approval includes the resolved credential set; rotating a credential or revoking a handle invalidates the published workflow until reviewed again.
- **Forward compatibility.** A registry version may add handles. Old IRs continue to validate against their pinned registry_version; they only break if a referenced handle is removed, which surfaces as an explicit deprecation event.

This resolves the credential boundary: secret *values* are never in IR, YAML, JSON, or ZIP artifacts; credential *handles/bindings* are, by design, in generated artifacts because workflows need reproducible binding points. A dedicated central secret manager can be added later for enterprise deployments, but it is not required for Phase 0.

### Runtime capability matrix and semantic conformance

The IR specifies runtime semantics (loop bounds, parallel fan-in merge, agent fallback, output-schema enforcement, retry/timeout/idempotency). The deterministic-production claim is only true if these compile to **each registered runtime** (Hiagent, Dify) with the *same* semantics — not approximated, not silently weakened. We make this explicit per runtime:

| IR construct | Hiagent mapping (pinned version) | Dify mapping (pinned version) | Conformance test |
|---|---|---|---|
| `loop` w/ `max_iterations` | 循环节点 + bound | Iteration node + bound | Test runs loop with N>bound input; expect bounded execution + structured truncation event |
| `parallel` fan-in `merge_strategy` | 并行节点 + 合并 | Parallel branches + aggregator | Test verifies output equals declared merge for each strategy (concat / object-merge / first-success) |
| `agent` w/ `budget` + `on_budget_exhausted` | Agent 节点 + 分支边 | Agent node + branching edge | Test forces budget exhaustion; verifies fallback edge taken / fail / partial — matches IR policy |
| `agent` `output_schema` enforcement | 输出格式 (JSON / 自定义) | Schema validator post-agent | Test forces schema-invalid output; verifies same on-exhaustion policy fires |
| `retry` w/ `retry_on` | Node retry config | Node retry config | Test injects 5xx / timeout / non-retryable; verifies retry counts and final disposition |
| `timeout_s` | Node 超时设置 | Node timeout | Test runs slow node; verifies hard-cut at boundary, not "soft" continuation |
| `idempotency_key` on `http`/`code` | Header / dedup key (via 插件节点) | Header / dedup key | Test re-runs node twice with same key; verifies single side-effect on the target |
| `condition` truthiness rules | 选择器分支求值 | Branch eval | Test enumerates IR truthiness table; verifies parity with each runtime's evaluator |

Every cell of this matrix has a golden test in CI **per registered runtime**. **A red cell on any runtime is a release blocker** — we do not ship an FDE release whose runtime semantics diverge from the IR contract. If a runtime version can't honor a cell (e.g., no native idempotency on `http`), that runtime's adapter must either synthesize the behavior with a wrapper node or refuse to emit, never silently weaken.

This matrix is the operational definition of "the IR is the contract."

### Why not just generate runtime DSL directly?

Three reasons, in order of importance:

1. **Validation cost.** IR validation is ~50ms in pure Python. Validating the full DSL of any runtime (Hiagent JSON or Dify YAML — hundreds of node types each) often only fully validates at runtime, and errors are positional rather than semantic ("missing field in node #14" vs "variable `${search.results}` not produced by any upstream node").
2. **LLM grammar size.** A 10-node-type IR is small enough to fit comfortably in a system prompt with few-shot examples. A full runtime DSL grammar isn't.
3. **Multi-target.** v1 ships two compilers (Hiagent + Dify) sharing one IR; adding LangGraph (Phase 3.2 alpha) is "write one more adapter," not "fork the IR."

## 6. Lifecycle

```
Author intent ─→ FDE clarifies ─→ workflow brief ─→ Planner ─→ IR (committed to git as draft)
                                │
                                ▼
                         Validator passes
                                │
                                ▼
                  Compiler (RuntimeAdapter) ─→ target DSL (Hiagent JSON or Dify YAML)
                                │
                                ▼
                  Deployed as draft to target runtime workspace
                                │
                                ▼
                  Reviewer opens in target runtime editor; diff vs prev version
                                │
                                ▼
                  Approve → publish    OR    Edit in FDE / runtime editor → re-export IR → commit
                                │
                                ▼
                            Production
                                │
                                ▼
                  Traces captured; failures + edits feed back into
                  the few-shot library for the Planner
```

### FDE session loop

The lifecycle has two user-visible loops:

- **Create loop:** user describes the desired workflow; FDE resolves the Persona Brief (per ADR 0023); asks only blocking clarification questions; generates a Workflow Brief; Planner emits IR; Validator returns structured errors; FDE either self-corrects or asks the user for missing business context; Compiler + Deployer push a draft on the chosen target runtime (Hiagent or Dify).
- **Edit loop:** user says what to change in natural language or edits the draft in the target runtime's editor; FDE maps recognized edits to IR changes; Validator and Compiler re-run on the same target runtime; FDE summarizes the change and pushes a new draft. If the runtime-side edit is outside the recognized set, FDE hard-blocks publish on that runtime and presents remediation options.

### Reverse compiler policy

Reviewers will tweak generated workflows in the target runtime's editor; we need a runtime-DSL → IR reverse compiler **per registered runtime** so manual edits don't fork the source of truth. Key policy decisions (apply uniformly to Hiagent and Dify reverse compilers):

- **Recognized constructs round-trip.** Any pattern the forward compiler emits must be re-parseable. Enforced by golden tests: every (IR → target DSL) pair has a matching (target DSL → IR) test whose output equals the original IR **under canonical equality** (see below).
- **Unrecognized constructs hard-block, never silently drop.** If a reviewer adds a runtime node type the IR doesn't have, the reverse compile fails with an actionable error naming the construct (and the runtime that produced it). Reviewer's options: revert the edit, request the IR be extended (which goes through a deliberate IR-version review), or use the `code` escape-hatch node where applicable.
- **No silent IR extension.** New node types are added by deliberate IR-version bumps, never auto-inferred from a runtime-side diff. This protects the IR from sprawl.
- **Hard-block remediation UX is explicit.** Each unrecognized construct surfaces with: the runtime + exact node type and parameter set that triggered the block; one-click "revert to last known IR-clean draft"; a "request IR extension" button that opens a templated issue with the offending construct attached; and a fast-path "use `code` escape hatch" wizard that wraps the reviewer's intent in a sandbox cell with the I/O schemas pre-filled. We measure the **reviewer hard-block rate** per runtime (§10) — sustained spikes on either runtime are a signal that the IR is undersized.

### Canonical IR equality (new in v0.3)

Reverse-compile correctness cannot be defined as literal IR equality, because:

- Each target runtime's import/export normalizes whitespace, default-strips fields, reorders nodes, and rewrites node IDs (Hiagent and Dify both do this in their own way; the canonicalization function per runtime adapter handles the runtime-specific shape).
- Two IRs that compile to the same workflow may differ in inessential ways (key ordering, optional fields filled with their default value, redundant `null` vs absent fields).

The Validator and golden test harness compare IRs in **canonical form**, defined as: keys sorted lexicographically; default-valued fields stripped; node IDs normalized to a stable hash of `(type, sorted_input_refs, position-in-topological-order)`; arrays whose semantics are order-independent (e.g., parallel branches) sorted by canonical node ID; `rationale` preserved verbatim (it is part of the contract, not noise).

Canonicalization is a **pure function** in the FDE Compiler module; it runs the same way client-side, in CI, and inside the Deployer. The function is versioned alongside the IR schema; canonicalization changes are themselves IR-version bumps.

### Git ↔ runtime state machine (runtime-neutral)

Source of truth is git, but review and edit happen in the **target runtime** (v1: Hiagent primary, Dify secondary). That's a two-system contract that needs explicit ownership and **must work uniformly for any registered runtime**.

| Identifier | Owned by | Purpose |
|---|---|---|
| `commit_sha` | Git | The IR file's commit. Canonical workflow version. Runtime-agnostic. |
| `target` | FDE state | The runtime this state row pertains to: `"hiagent"` \| `"dify"` (extensible). A single workflow may have multiple state rows — one per registered runtime. |
| `canonical_ast_hash` | FDE Compiler (per runtime) | SHA-256 of the **canonical AST** produced by parsing the emitted DSL with the target runtime's importer and applying an FDE-defined canonicalization pass (whitespace-normalized, default-stripped, node-ID-stable, list-order-stable). Deterministic given IR + Compiler version + runtime version. Computed by `RuntimeAdapter.canonical_ast_hash(dsl)`. |
| `target_draft_id` | Target runtime API (Hiagent OpenAPI / Dify API / …) | Returned when FDE pushes a draft to that runtime. |
| `target_published_id` | Target runtime API | Returned on publish. |
| `reverse_compile_status` | FDE (per runtime) | `clean` (matches git IR under canonical equality) / `drifted` (runtime draft edited, reverse compile needed) / `unrecognized` (reverse compile failed). |

**Why not hash raw DSL bytes?** Each runtime's import/export pipeline rewrites its DSL on round-trip — whitespace, key ordering, default-value population, ID assignment all shift. Hashing raw bytes produces *constant* false-positive drift, which trains reviewers to ignore the alarm. Canonical AST hashing solves this: the hash is invariant under the runtime's normalizations and only changes when *semantically meaningful* fields change. The canonicalization function is owned by FDE (not by the runtime) and is the same function the reverse-compile golden tests use. Each runtime adapter exposes its own canonicalization at `loom/runtimes/<target>/ast.py` with the same shape.

**Workflow registry rows** (Postgres): one per `(workflow, target)` tuple, holding the current `(commit_sha, target, canonical_ast_hash, target_draft_id, target_published_id, reverse_compile_status)` plus history. A workflow with drafts on both Hiagent and Dify therefore has two rows.

**Drift detection runs on every publish attempt.** FDE asks the target runtime's adapter to fetch the current draft, parse + canonicalize, hash the result, and compare to the stored `canonical_ast_hash` for that `(workflow, target)` row. If they match, publish proceeds. If they don't, the publish on that runtime is **blocked** until reverse compile produces a new IR commit on a feature branch and a new (IR → DSL → canonical AST → hash) cycle confirms the edit. Drift on one runtime does not block publish on another runtime — each `(workflow, target)` row is independent.

**Publish blocking rules (per `(workflow, target)`):**

- If `reverse_compile_status == clean` and canonical-AST hash matches → publish allowed on that runtime.
- If canonical-AST hash differs but reverse compile succeeds (under canonical equality) → require explicit "accept reviewer edits" action that creates a new IR commit; then re-enter the cycle on that runtime.
- If reverse compile fails (`unrecognized`) → publish blocked on that runtime; reviewer must revert the edit, escalate for IR extension, or use `code` escape hatch.
- If git has moved ahead of the deployed `target_draft_id` (someone landed a new IR commit while the draft was open) → block publish on that runtime; require redeploy of the latest IR as a fresh draft.

This is the spec the Deployer enforces. It eliminates the "we approved one thing in the runtime but git says another" failure mode by construction. Adding a new runtime is "register one more `RuntimeAdapter` and add a row per workflow"; the contract above does not change.

> **Cost-budget escape hatch (per §7).** If Dify is dropped, only the Hiagent rows are populated; the contract is unchanged.

## 7. Phased Roadmap

> **Cost-budget escape hatch (cross-phase contract, decided 2026-05-06).** v1 ships dual-runtime (Hiagent primary + Dify secondary). If during execution the cost of running both runtimes exceeds the project's budget for any single phase (Phase 1 / 1.5 / 2A / 2B), the project owner may invoke the escape hatch: **drop Dify, keep Hiagent**. Gate criteria for the dropped runtime become N/A in the corresponding gate report; Hiagent rows must still pass at the full bar. Web target picker, runtime coverage matrix, conformance / parity / reverse / drift / publish flows are all written so that one runtime missing is a configuration drop (`loom/runtimes/registry.unregister("dify")`), not a refactor. The escape hatch is recorded as an ADR 0002 amendment with date and reason.

**Phase 0 — Discovery and default-contract lock (2 weeks).** Phase 0 no longer waits for external partner confirmation. The first FDE step is an **SOW / requirements intake**: persona, business goal, target runtime, channels, datasets/tools, credential bindings, reviewer policy, success criteria, and five workflow candidates. The SOW may come from a real partner or from a synthetic partner profile (for example a Bambu Lab-style cross-border ecommerce operator) so engineering can start without BD blocking the project. Hand-author the five SOW workflows as IR and run them against the Phase 0 engineering target.

**Phase 0 decisions/defaults (must be written before Phase 1 code):**

- **ADR 0001 — SOW / requirements intake contract.** Replaces the previous external partner confirmation gate. A real partner is one possible SOW source, not a prerequisite to build FDE.
- **ADR 0002 — Runtime versions fixed (cloud SaaS).** Hiagent Cloud (primary) and Dify Cloud (secondary) at API version `v1`. Both runtimes are cloud SaaS — no local docker. Endpoints + auth tokens configured via `config/runtimes.yaml`. Pins are at the API-version level; minor in-place upgrades by the cloud provider are caught by the conformance suite.
- **ADR 0003 — Credential binding strategy.** LLM credentials are configured in the target platform after import; non-LLM credentials are HTTP auth bindings. No dedicated central secret-manager decision blocks Phase 0.
- **ADR 0004 — Reverse-compile default scope.** Decision: reverse only FDE-emitted constructs and recognized parameter edits; unrecognized runtime-side edits hard-block with remediation. No external senior-review signoff is required to start Phase 1.
- **ADR 0005 — Agent / LLM defaults.** Start with defaults and let the operator adjust after import. Default `max_output_tokens = 8000`.

**Phase 0 gate criteria (all of):**

- All 5 archetypes express in IR within these limits: ≤25 nodes per workflow, zero unsupported semantics requiring `code` as a workaround for missing IR features (legitimate transforms in `code` are fine), reviewability score (subjective rating from 3 reviewers, 1–5) ≥4 median.
- Zero archetypes require a node type outside the IR v0.3 list, or any new node type is added by a deliberate, documented IR-version bump (≤1 such bump permitted).
- Each hand-authored IR compiles to the **locked Dify** DSL (Phase 0 engineering target; Hiagent equivalent ships in Phase 1 Task 11.5) and runs the **semantic conformance suite** for every IR construct it uses (the matrix in §5: loop bounds, parallel merge, agent budget/fallback, output_schema, retry, timeout, idempotency, condition truthiness). A passing smoke test is necessary but not sufficient.
- **Runtime import/export canonicalization proven on the Phase 0 engineering target (Dify Cloud).** Take a hand-authored IR, compile to Dify DSL via the Dify adapter shim, push to pinned Dify Cloud, pull back, run Dify's canonicalization (§6.4), confirm the canonical AST hash is stable across N=10 round-trips. False-drift rate must be 0. ADR 0002 also pins Hiagent Cloud (a *decision* artifact); the Hiagent canonicalization proof is a Phase 1 Task 11.5 deliverable, not Phase 0. If the Cost-budget escape hatch was invoked **before** Phase 0 completes and Dify was dropped, this row's proof is performed against Hiagent Cloud instead.
- **Reverse-compile spike on the Phase 0 engineering target:** for at least one of the five archetypes, take the deployed runtime workflow (Dify in Phase 0), manually edit it (a node added/removed/parameter changed within the IR-recognized set), reverse-compile to IR, and confirm the resulting IR equals the manually-edited equivalent **under canonical equality** (§6). Surfaces round-trip risk before any MVP code is written. The Hiagent reverse-compile spike is a Phase 1 Task 11.5 deliverable.
- **One Reviewer edit simulation on the Phase 0 engineering target (Dify Cloud).** An internal reviewer, real partner reviewer, or synthetic SOW reviewer opens a generated workflow in the Dify Cloud console, makes realistic edits, and walks through the publish-blocking + remediation flow.
- **Security review.** `http`, `code`, and `agent` nodes get a security pass (sandbox escape vectors, prompt-injection vectors, side-effect auditability). Surfaces issues that can't be retrofit.

If any criterion fails, iterate the SOW / IR before Phase 1 code depends on it.

**Phase 1 — MVP (5–6 weeks; revised up from 3–4).** FDE session loop (Persona Brief + Workflow Brief) + Planner + Validator + **dual-runtime support via `RuntimeAdapter` (Hiagent primary + Dify secondary; n8n out of scope 2026-05-06)** + CLI + **narrow reverse compilers** per runtime (round-trip support for the IR constructs used by the 2 deep-coverage archetypes, on each runtime). Input: a typed oral-style request or JSON request file with intent + context + persona + target. Output: a draft on the chosen target runtime plus a source-of-truth IR file; on demand, FDE applies a natural-language edit or reverse-compiles an edited runtime workflow back to IR. Cover **2 archetypes deeply** from the cross-border ecommerce backlog (ecommerce customer FAQ / KB Q&A and ecommerce order-exception triage), on **both runtimes**. Success criterion: ≥70% first-try IR validity on the deep-coverage archetypes per runtime (≥85% by end of Phase 2 per §10), all semantic conformance tests green on each runtime, narrow round-trip works on each runtime, and the minimal FDE create/edit loop succeeds on both archetypes on both runtimes. If the Cost-budget escape hatch was invoked, Dify rows are N/A and Hiagent rows must pass at the full bar.

The original 3–4 week estimate underweighted the dual-runtime compiler effort (programmatic emission across 10 node types × 2 runtimes + golden tests + conformance suite against live Hiagent + Dify is ~3–4 weeks alone). 5–6 is honest. Pulling the reverse compiler in this far is deliberate: it's the load-bearing piece of the defensible wedge (§2) and the thing most likely to surface IR design problems. Better to find them before Phase 2. If the Cost-budget escape hatch is invoked and Dify is dropped, this estimate compresses by ~30%.

**Phase 1.5 — Coverage extension + dual-runtime parity (3–4 weeks; immediately follows Phase 1).** Extend the **Hiagent and Dify forward compilers** (and Planner few-shot library) to cover the 3 TCM shadow archetypes (TCM intake/triage, TCM clinic-ops-summary, TCM follow-up) on both runtimes. Reverse compilers stay narrow on the two ecommerce deep-coverage archetypes for both runtimes; Phase 2A widens reverse to all 5 on both. Eval corpus grows from ≥30 deep prompts to ≥75 across 5 archetypes. **Runtime parity test**: same IR through both compilers must pass the same conformance-matrix cells. n8n was scoped out 2026-05-06; runtime portability is proven by Phase 1's dual-runtime build, not by a falsifiable n8n stub.

Success criterion: all 5 archetypes work on **both Hiagent and Dify** with at most 1 validation-feedback retry; the full IR v0.3 grammar has matrix-cell coverage in CI on both runtimes; runtime parity test (same IR → both compilers → same conformance cells pass) is green for all 5 archetypes.

This is effectively the back half of MVP — the Phase 1/1.5 split exists to put a checkpoint between "core machinery works on simple cases" and "machinery scales to harder ones with bounded agent zones, plus portability isn't a fiction."

**Phase 2A — Productionize, infra (3 weeks).** The load-bearing infra to make FDE usable in production:

- **Per-runtime adapter integration** (Hiagent + Dify, both via the Phase 1 RuntimeAdapter): auto-deploy as draft; fetch draft for drift detection; round-trip canonicalization wired end-to-end on both runtimes.
- Git-backed workflow registry (Postgres mirror per §6), with the full state machine and publish-blocking rules. State columns are runtime-target-aware: a single workflow can have draft handles on multiple runtimes simultaneously.
- **Full reverse compiler on both runtimes** (covers all v0.3 constructs, not just the deep archetype set; widens both Hiagent and Dify reverse from Phase 1's narrow set).
- Drift detection and publish-blocking running per-runtime on every publish attempt.
- Audit trail (who authored, who reviewed, who published, on which runtime, with timestamps and diffs) — the artifact the AI Ops buyer is paying for.
- FDE edit-history ledger: user instruction → interpreted workflow diff → validation result → draft id (per runtime).

**Phase 2B — Productionize, surface (3 weeks; immediately follows Phase 2A).** Everything that touches a human:

- Web UI for authoring (the v0-style intent → live IR + graph preview surface; see notes in §11).
- FDE conversation surface: requirements brief, blocking questions, generated plan, natural-language edit log, and review summary.
- Semantic diff view in the workflow registry (this is what reviewers see in PRs — table of node-level changes, not raw JSON diff).
- Trace observer dashboard.
- FDE-native RBAC layered over the workspace's RBAC.

**Why split Phase 2.** v0.2's single 4-week Phase 2 bundled the load-bearing infra (deployer, registry, drift, full reverse) with the surface (UI, RBAC, observer). That was unrealistic for 4 weeks. Splitting puts the *governance* artifacts in front first — which is also what the AI Ops buyer cares about — and lets Phase 2B ship after Phase 2A is operational, even if 2B slips.

**Phase 3 — Expand (ongoing).** Phase 3.1: multi-tenancy (PRD §11 Q4) + IR v0.3 → v0.4 minor bump (additive: `metadata.compliance_class` + `output_schema.<field>.pii_class` overrides). Phase 3.2 (optional): LangGraph alpha as a third runtime via the existing `RuntimeAdapter`. More node types as needed. Bounded-agent-zone enhancements.

**Phase 4 — Self-improvement (ongoing).** Workflow execution traces feed a corpus the Planner retrieves over. Failed workflows generate "lessons" that future plans avoid. This is where the system starts to compound.

## 8. Tech & Stack

- **Planner LLM:** OpenAI/Anthropic-compatible structured-output client; exact model selected per environment and benchmarked against the eval corpus.
- **IR:** JSON Schema spec; Pydantic models in-memory.
- **Validator:** Pydantic + custom semantic-check pass.
- **Compiler:** Python. Per-runtime DSL emitted programmatically through the RuntimeAdapter contract (Hiagent JSON + Dify YAML in v1; not via templates — too brittle).
- **Service:** FastAPI.
- **FDE session layer:** typed chat / CLI session in Phase 1; web conversation surface in Phase 2B.
- **Frontend (Phase 2):** Minimal Next.js FDE console, or keep CLI + the target runtime's native editor (Hiagent / Dify) until SOW / partner demand is proven.
- **Tests:** Golden-file tests for every (IR → DSL) pair *and* matching (DSL → IR) reverse pair. Property tests on the validator.

### Storage split

- **Git:** IR files, compiled DSL files, IR schema versions, few-shot library. Source of truth, diffable, reviewable.
- **Postgres:** Workflow registry metadata (name, owner, status, current version, deployment target), execution traces, planner-call telemetry, Author/Reviewer audit log.
- **Credential values:** LLM provider keys are configured in the target runtime platform after FDE imports the YAML / JSON / ZIP artifact. Non-LLM credentials are bound through HTTP auth handles (header/query/OAuth/client credentials) owned by the runtime workspace. Secret *values* are never stored in IR, generated artifacts, or the git registry; only handles and binding metadata are stored.
- **Tool/dataset/credential registry:** Versioned in git (immutable commit SHA referenced by every IR's `registry_ref.registry_version`). The registry contains handles, schemas, and ACL bindings — never secret values. Postgres mirrors the active registry version for fast Validator lookups.

Pin each runtime's version at the start (per ADR 0002 — Hiagent + Dify). CI runs a regression suite against each pinned version.

## 9. Risks & Mitigations

- **IR scope creep** → A node type is only added when a real workflow needs it. Each new node type requires a deliberate IR-version bump and golden tests in both directions.
- **IR-version migration story** → Old IR files must continue to validate (against their pinned `ir_version`) after a schema bump. The Validator carries every historical schema; new releases ship a one-shot migration tool (`loom ir migrate`) that produces a new-version IR plus a diff for human review. Migrations are never silent.
- **SOW quality / overfit risk** → If the first SOW's workflows look materially different from the placeholders in §3, IR scope re-opens. Mitigation: Phase 0 may use a real partner SOW or a synthetic ecommerce SOW, but it must also keep a second shadow corpus of 5 workflows from another team, the TCM shadow set, or a public template gallery (Hiagent / Dify) as a sanity check that IR is not overfit to one operator's idioms.
- **Customer-PII / TCM compliance boundary** → For ecommerce primary workflows, FDE handles customer name/phone/address/payment via `pii_class` (medium/high) with mandatory redaction at trace ingest and right-to-erasure (per ADR 0010); cross-border data flows respect the seller's GDPR/PIPL posture. For TCM shadow workflows, FDE can generate clinic operations/support/follow-up drafts only — never diagnosis, prescriptions, treatment claims, or paths that bypass clinician/compliance review. Mitigation in both verticals: human-review gates, explicit disclaimers in customer/patient-facing flows, PII minimization/redaction policy, and audit evidence for every draft.
- **Runtime DSL drift between versions** (per Hiagent / Dify) → Pin each runtime's API version (ADR 0002 — cloud SaaS, `v1` for both); have a single compiler module per runtime API major version (`loom/runtimes/<target>/cloud/`); CI runs golden tests against each pinned runtime. Each runtime API-version bump (or significant minor change observed in CI) is treated as an explicit compatibility project on that runtime (re-run conformance matrix end-to-end + parity test), not a routine dependency update.
- **Conformance-test flake** → The semantic conformance suite (§5) runs against live cloud SaaS endpoints (Hiagent Cloud + Dify Cloud in v1). Network/timing/cloud-side nondeterminism produces flakes. Mitigation: pin each runtime to its API version + base URL in CI (per ADR 0002), with auth tokens in CI secrets; report flake rate per runtime as a metric (§10); a flake rate >5% on any runtime blocks a release as much as a red cell.
- **Planner hallucinates tool/dataset names** → Validator checks every reference against a live registry. Hallucinated refs never reach the compiler.
- **Prompt / tool-description injection** → Tool descriptions and dataset metadata flow into the Planner's prompt (and into agent prompts at runtime). A malicious or sloppy tool description can hijack generation. Mitigation: registry entries are reviewed before being added; Planner system prompt isolates tool descriptions in a typed registry block (not free-text); agents that consume external data tag it as untrusted and the prompt template renders untrusted content inside explicit delimiters.
- **`code` node sandbox escape** → `code` nodes execute Python/JS with constrained imports. Escape vectors (unsafe `__import__`, deserialization, fs access via stdlib quirks) are real. Mitigation: Phase 0 security review of the sandbox; per-node CPU/memory/wall-clock caps; `code` nodes can't reach the network (network access is the `http` node's job, which has its own ACLs).
- **Trace PII retention** → Workflow traces capture LLM inputs/outputs, tool args, and intermediate variables — likely containing PII. Storage policy in v1: redact at write time using a configurable PII filter; default retention 30 days; right-to-erasure honored via trace deletion API. Tracked as a per-workflow `pii_class` in the registry.
- **Trace volume cost** → A 10-node workflow run can produce kilobytes of trace data. At enterprise scale this is significant. Mitigation: sampled traces by default (100% on errors, 10% on success); compressed storage; rollups for the Planner's lessons corpus rather than raw trace replay.
- **Planner cost spike under retries** → A pathological intent or a registry catalog growth event can blow the cost ceiling. Mitigation: hard cap of 3 retries × 8K tokens budgeted per workflow; sustained P95 cost over $1 triggers an alert and a planner-quality review (§10).
- **Reviewer fatigue** → Diffs must be semantic (node-level), not textual. Invest in the diff UI in Phase 2B. The `rationale` field per node (§5) is what makes diffs human-readable.
- **Reverse compiler drift** (manual edits in the target runtime diverge from IR — per Hiagent / Dify) → Strict pattern matching with canonical IR equality (§6); unrecognized constructs hard-block round-trip on that runtime with an actionable error and a remediation UX.
- **Cost** → Planner runs are cheap (one LLM call per workflow authored, not per execution). Budget ceiling: 3 retries × ~5K tokens ≈ $0.15/workflow. Spike in retries triggers a Planner-quality review.
- **Runtime failures** → IR carries per-node retry/timeout/idempotency policy (§5); compilers must honor it. Failures despite policy emit structured traces the Observer feeds back to the Planner's lessons corpus.
- **Vendor lock to pinned runtime versions (Hiagent Cloud + Dify Cloud)** → Pinning avoids surprise breakage but creates a slow upgrade path. Mitigation: portability is by construction — the IR compiles to two runtimes from Day 1 (Phase 1). If a runtime forces an API-version upgrade and our conformance suite goes red, we route customers to the other runtime if the affected workflows have parity coverage, while we close the gap. Phase 1.5 runtime parity contract is the regression guard. Cloud-only deployment means we don't ship a "stay on the old image" fallback — the runtime parity is the fallback.
- **FDE role underspecified** → If the product only compiles JSON requests, users will experience it as a developer tool, not an AI驻场工程师. Mitigation: Phase 1 must include typed oral-style create/edit sessions, blocking clarification questions, and review summaries.
- **Competition from a target runtime (Hiagent / Dify) or a competitor shipping NL→workflow natively** → FDE's wedge is role experience + portability across multiple runtimes + IR-as-contract + reverse compiler + governance/audit trail. **Explicit kill/pivot trigger criteria** (review at end of Phase 1.5 and quarterly thereafter):
  - **Pivot trigger.** Any single runtime's native offering ships that (a) covers ≥80% of our archetype shapes with ≥85% first-try validity, *and* (b) has a comparable audit/diff story, *and* (c) is the partner's preferred path. → Pivot FDE's value prop to the IR/validator/compliance layer alone, sold to teams running *multiple* runtimes (Hiagent + Dify + LangGraph + Temporal). The reverse compiler becomes an "import-from-runtime" feature.
  - **Kill trigger.** A native offering ships that meets all three pivot conditions *and* the multi-runtime layer has no clear buyer in our pipeline within 2 quarters. → Open-source the IR + validator + compilers as a reference implementation; wind down the product line.
  - **Continue trigger.** Native offerings exist but fail one or more of (a)/(b)/(c), or partners prefer FDE for governance or embedded-engineer workflow reasons. → Continue, double down on the FDE role loop, audit trail, and reverse-compile UX as the primary differentiation.

## 10. Success Metrics

### Evaluation corpus

All numerical targets below are measured against a fixed **eval corpus**: a frozen set of (NL intent, declared context, expected IR shape) tuples committed to the repo. Phase 1 corpus = ≥30 prompts across the 2 deep-coverage archetypes (≥15 each), drawn from the SOW workflow candidates where possible, hand-authored otherwise. Phase 1.5/2 corpus = ≥75 prompts across all 5 archetypes. Corpus changes are versioned and reviewed; you cannot game a metric by mutating the corpus.

### Failure taxonomy

Failures are bucketed across the full pipeline (v0.2 only had Planner-side buckets; v0.3 covers the whole lifecycle):

**Planner-side (IR generation):**

1. **Schema** — IR doesn't parse against JSON Schema (missing field, wrong type).
2. **Reference** — variable / tool / dataset / credential reference doesn't resolve.
3. **Type-flow** — DAG types don't match across edges.
4. **Policy** — agent budget or per-node policy missing/invalid.

**Compiler / Deployer-side:**

5. **Compile failure** — IR validates but a Compiler (Hiagent or Dify) refuses because the target runtime can't honor the requested semantics. The runtime parity contract (Phase 1.5) makes this a per-runtime metric.
6. **Deploy failure** — Compiled DSL rejected by Hiagent OpenAPI or Dify API (auth, version mismatch, transient). Tracked per runtime.
7. **Reverse-compile failure** — A runtime draft (Hiagent or Dify) contains unrecognized constructs (the §6 hard-block path). Tracked per runtime because reviewer hard-block rate is a UX metric, not a Planner-quality metric.
8. **Registry / ACL failure** — Author lacks the scope to reference a tool/credential, or the registry version is missing/corrupt.

**Runtime-side:**

9. **Semantic conformance** — IR validates and compiles, but the deployed runtime workflow's behavior diverges from the IR contract on a §5 matrix cell **on any registered runtime**. **Should be ~0 by Phase 2A; any occurrence is a release-blocker bug, not a metric to optimize.** Tracked per runtime.
10. **Platform failure** — any target runtime (Hiagent / Dify), platform credential store, registry mirror, etc. unavailable. Excluded from FDE-quality metrics; tracked for SRE per platform.

**Human-side:**

11. **Human-review rejection** — Reviewer rejects a generated workflow on the merits. The rejection reason is captured (`incorrect_logic`, `wrong_tool`, `policy_violation`, `style_preference`, `other`) and feeds the Planner lessons corpus.

Every metric below reports the breakdown across these buckets where applicable, not just an aggregate. A 70% pass rate hiding 25% Semantic failures is not the same as 70% hiding 25% Schema failures.

### System metrics

**Quality:**

- **FDE create-loop success rate** — fraction of oral-style requests where FDE asks only necessary clarification questions, produces a valid IR, compiles it, and pushes a draft on the chosen target runtime without human engineering intervention. Target ≥70% by end of Phase 1 on the 2 deep archetypes, per registered runtime.
- **Natural-language edit success rate** — fraction of user edit instructions that produce the intended canonical IR diff and updated runtime draft. Target ≥80% on recognized edit classes by end of Phase 1, per registered runtime.
- **First-try IR validity rate** — fraction of corpus prompts producing a Validator-passing IR on the first Planner call. Denominator: full eval corpus. Target ≥70% by end of Phase 1, ≥85% by end of Phase 2A.
- **End-to-end workflow execution success rate** — fraction of corpus prompts whose Validator-passing IR compiles, deploys, and runs to a correct expected output (per the corpus's expected shape). Denominator: full eval corpus. Target ≥90% by end of Phase 1.5 on the 5 archetypes.
- **Semantic conformance pass rate (per runtime)** — fraction of IR constructs whose semantic conformance test (§5 matrix) passes on each pinned runtime (Hiagent + Dify). Target: 100% on every registered runtime — any red cell on any runtime is a release blocker.
- **Conformance-suite flake rate** — fraction of conformance test runs that fail then pass on retry without any code change. Target <2%; >5% blocks a release.
- **Reverse-compile round-trip success** — fraction of (IR → DSL → IR) cycles producing a canonically-equal IR. Target 100% on recognized constructs.
- **Human edit distance** between generated IR and approved IR — node-level diff size, normalized by IR size. Should trend downward over time as the Planner learns from the lessons corpus.

**Reviewer experience:**

- **FDE review-summary usefulness** — median reviewer rating (1–5) for "I understand what FDE changed and why." Target ≥4 by Phase 1 gate.
- **Reviewer hard-block rate** — fraction of publish attempts blocked by `unrecognized` reverse-compile failure. Target <5% steady-state. A sustained spike is a signal the IR is undersized, not that reviewers are doing something wrong.
- **Reviewer bypass attempts (per runtime)** — count of attempts to publish around FDE on any registered runtime (e.g., editing in the runtime's editor and publishing via that runtime directly). Target 0 per runtime; nonzero is a UX failure indicating the hard-block remediation UX (§6) isn't fast enough on that runtime.

**Cost / latency:**

- **Cost per authored workflow** — target <$0.20 median, <$1 ceiling (3 retries × ~5K tokens). Spike triggers a Planner-quality review.
- **P95 Planner cost** — track the tail; high P95 with low median means a few intents are pathological and should be examined.
- **P95 Planner latency** — median <30s, P95 <90s; >90s P95 is an SLO breach.
- **Time from intent to deployed workflow** — median wall-clock from first NL prompt submitted to a draft visible in the chosen target runtime (Hiagent / Dify). Target <10 min for archetype workflows.
- **Clarification turns per workflow** — median number of FDE questions before draft generation. Target 1–3 for archetype workflows; 0 can mean unsafe assumption-making, >5 means the FDE is not acting like a competent engineer.
- **Trace storage cost** — $/workflow-run; tracked to keep the cost/value ratio honest.

**Operational:**

- **Runtime upgrade lead time (per runtime)** — calendar days from a new target-runtime version's release (Hiagent or Dify) to the conformance suite passing on it. Target <14 days per runtime; longer means FDE is becoming a brake on the partner's runtime upgrades.
- **FDE handoff completeness** — every runtime draft (Hiagent or Dify) has a linked IR commit, canonical AST hash, persona brief, workflow brief, and review summary. Target 100% per registered runtime.

### Human metrics

- **Reviewer time-to-approve** — median minutes from "draft on the target runtime" to "published," for workflows that are approved. Target <5 min for archetype workflows. Tracked per runtime, separately from "time-to-reject."
- **FDE replacement intent rating** — user rating for "I would ask FDE before asking a human engineer for this workflow." Target ≥4 median in SOW / partner sessions.
- **Author task completion rate** — fraction of Authors who successfully ship a workflow (through approval) within their first session. Measured in a Phase 2B user study with ≥10 participants. Target ≥80%.
- **Author repeat-use rate** — fraction of Authors who author a 2nd workflow within 4 weeks of their first. Want this trending up over Phase 2.

The success of v1 is the conjunction, not the disjunction, of these. A high validity rate with a low conformance pass rate means we generate IR that lies about its semantics. A high completion rate with low repeat-use rate means we built a one-time-use toy. The targets are co-binding.

## 11. Open Questions

The previous five Phase 0 external blockers are now Phase 0 **default decisions**:

- ~~Q1: Target customer / first deployment.~~ → captured through the SOW / requirements intake contract (ADR 0001). A real partner is useful, but synthetic-partner mode is enough to start.
- ~~Q2: Runtime version commitments.~~ → fixed by ADR 0002: Hiagent `2.6`, Dify `1.14.0`.
- ~~Q3: Secrets handling / central secret-manager choice.~~ → replaced by ADR 0003 credential binding: platform-managed LLM credentials plus HTTP auth bindings for non-LLM integrations.
- ~~Q5: Reverse-compiler scope.~~ → defaulted by ADR 0004: recognized FDE-emitted constructs round-trip; unknown runtime-side edits hard-block.
- ~~Q6: Bounded agent zone governance.~~ → defaulted by ADR 0005; `max_output_tokens = 8000` for the first build.

**Remaining open questions (resolve during Phase 0 / Phase 1; not blocking):**

4. **Multi-tenancy.** Single workspace v1, or multi-tenant from day one? Default plan: single workspace, multi-tenant in Phase 3.
7. **Build vs buy on the planning/session layer.** Wrap an existing structured-output / planning library, or DIY? My instinct: DIY for the IR Planner, but the FDE session loop may reuse a lightweight conversation-state library if it stays transparent and testable.
8. **FDE-native RBAC vs leaning on each target runtime's RBAC.** v0.4 leans on the target runtime's workspace RBAC (Hiagent / Dify) for v1; FDE-native RBAC ships in Phase 2B. Confirm this is acceptable for the first SOW / partner.
9. **Naming availability.** Product name is now **FDE** / **Forward-Deployed Engineer**. Remaining work: verify trademark, domain, GitHub org, package names, and Chinese-market ambiguity. If FDE is legally blocked, preserve the role concept and pick a brand that still says "AI 驻场工程师."

## 12. Immediate Next Steps

If we agree on the shape above, the next concrete pieces of work are:

1. **Write the SOW / requirements intake contract and first SOW packet.** Capture persona, business goal, target runtime, workflow candidates, tools/datasets, credential binding plan, reviewer policy, and success criteria. Use a real partner if available; otherwise write `sow/default-ecommerce/phase0-synthetic-sow.yaml` from a synthetic cross-border ecommerce operator such as a Bambu Lab-style profile. ~1 day.
2. **Fill five SOW workflow candidates.** For each workflow, capture oral-style request, expected clarifying questions, expected edit instructions, reviewer concerns, and runtime handoff evidence.
3. **Lock the IR v0.3 schema against the five SOW workflows.** Draft the JSON Schema + a sample IR for each workflow. Review together, iterate. ~2 days.
4. **Hand-author the 5 archetypes against the Phase 0 engineering target (Dify).** Confirm every IR construct compiles to working Dify DSL. The Hiagent equivalent ships in Phase 1 Task 11.5 alongside the RuntimeAdapter. This is the Phase 0 gate. ~3 days.
5. **Stand up the FDE session + Planner + Validator + RuntimeAdapter skeleton.** Get one archetype generating and editing end-to-end on **both Hiagent and Dify** (typed oral-style request → Persona resolve → clarification → IR → DSL → runtime draft → natural-language edit → updated draft) before building anything else. ~1 week.

That's the spine. Everything else is fleshing it out.

---
