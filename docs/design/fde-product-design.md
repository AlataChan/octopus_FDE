# FDE Product Design

## Positioning

FDE means **Forward-Deployed Engineer**, not Front-End Development Engineer.

FDE is an AI workflow implementation engineer embedded beside the user. The user describes a business process in natural language; FDE asks clarifying questions, builds the workflow, edits it on request, validates it, pushes a draft to the target runtime, and preserves an auditable source of truth.

The product is not an IR editor. IR, Validator, Compiler, and Reverse Compiler are the reliability layer that lets the FDE role behave like a trustworthy engineer.

Phase 1 is a draft-authoring product, not an unattended operations product. FDE can create, update, validate, and hand off a runtime draft; publish control, production drift blocking, durable service state, and full RBAC arrive in later phases unless a plan explicitly pulls them forward.

## Product Promise

> Describe the workflow. FDE builds it, revises it, validates it, and hands it off as a reviewable runtime draft.

The user should experience FDE as a competent implementation partner:

- It asks missing business questions instead of guessing.
- It explains what it will build before pushing a draft.
- It creates and edits workflows through natural language.
- It produces a Dify draft that a reviewer can inspect visually.
- It keeps Git, IR, compiled DSL, and Dify draft state aligned.
- It blocks unsafe or unrecognized runtime edits instead of silently losing source truth.
- It turns ambiguity into a small number of blocking questions, not a long discovery interview.

## Primary Users

- **Requester / Author:** describes business intent and approves the draft shape.
- **FDE:** captures requirements, generates/edits workflows, validates, compiles, deploys draft, and explains changes.
- **Reviewer:** inspects the Dify draft and semantic diff, then approves or rejects.
- **Integrator / Admin:** configures runtime workspaces, datasets, tools, credential handles, scopes, and approval paths.
- **Operator:** runs the published workflow.

## China Market Wedge

The main China-market design doc is `docs/design/fde-ecommerce-tcm.zh-CN.md`.

The first vertical assumption is cross-border ecommerce operations: multilingual customer FAQ, order-exception triage, product-content localization, after-sales escalation, and ops reporting. TCM clinic operations is the secondary/shadow vertical for transferability checks: pre-consultation intake, follow-up, knowledge-base Q&A, and triage — kept in scope to validate that the same FDE Session and IR transfer to a different governance domain (medical PII, clinician review).

In ecommerce primary workflows, FDE must surface customer-PII flows, refund/compensation amount thresholds, and platform-compliance changes (Amazon/Shopify/TikTok Shop/Shein/Temu) in reviewer summaries; auto-replies must not promise specific compensation amounts without a human-approved gate. In the TCM shadow vertical, FDE must not provide medical diagnosis, prescription advice, treatment claims, or any path that bypasses clinician/compliance review — human review is part of the product contract, not an optional add-on.

The wedge is not "ecommerce SaaS" or "healthcare AI" in general. It is governed workflow authoring for operations teams where a human reviewer remains accountable for customer/patient-facing content, escalation rules, and release decisions.

## Core Experience

### 1. Create From Intent

User says:

> Build a workflow that answers customer questions from our docs, cites sources, and escalates low-confidence answers.

FDE responds with only blocking questions:

- Which dataset should retrieval use?
- What confidence threshold requires escalation?
- Where should escalations go?

After clarification, FDE generates a workflow brief, IR, validation report, and Dify draft.

FDE should not ask every possible question up front. It should ask only for facts that block safe generation: trigger, inputs, data source, credential handle, output destination, approval path, retry/timeout policy, or compliance boundary.

### 2. Edit By Instruction

User says:

> Change retrieval from top 20 to top 15 and retry the API call twice before failing.

FDE maps the instruction to a canonical IR diff, reruns validation, recompiles, updates the Dify draft, and summarizes:

- `retrieve.top_k`: 20 -> 15
- `fetch.retry.max_attempts`: 1 -> 2
- No new credentials.
- No agent budget increase.

### 3. Review And Handoff

Reviewer sees:

- Dify visual draft.
- Semantic diff.
- FDE summary.
- Validation/conformance status.
- Credential and policy changes.
- Reverse-compile status.

A draft is eligible for reviewer handoff only when the canonical Dify AST matches the IR-derived expected hash.

Production publish blocking belongs to Phase 2A unless the implementation plan explicitly ships it earlier.

## FDE Session Contract

The FDE Session is a product object, not just a chat transcript. It must preserve:

- User request and subsequent edit instructions.
- Blocking questions, answers, and unresolved assumptions.
- Workflow brief: trigger, inputs, outputs, datasets, tools, credentials, approval points, retry/timeout policy, success criteria, and compliance boundary.
- Current IR hash/commit, compiled DSL hash, Dify draft id, and canonical Dify AST hash when available.
- Reviewer summary: node changes, credential/data-access changes, external calls, policy/budget changes, compliance implications, and reverse-compile status.
- Recognized vs. unrecognized edit decisions, including remediation paths.

If any of these fields cannot be produced, FDE should surface the gap. It should not hide the gap behind a plausible-looking Dify draft.

## FDE Capability Checklist

Every Phase 0/1 workflow should be evaluated against this checklist:

- Captures trigger, inputs, outputs, data sources, tools, credentials, retry/timeout policy, approval points, and success criteria.
- Refuses to invent missing tools, datasets, or credentials.
- Produces valid IR with meaningful `rationale` fields.
- Compiles to the pinned Dify version.
- Pushes a draft and links it to an IR commit/hash.
- Accepts natural-language edits for recognized constructs.
- Hard-blocks unrecognized Dify edits with remediation paths.
- Produces a reviewer-useful change summary.
- Leaves enough evidence for another engineer to reproduce the same draft from the same source truth.

## Architecture Implication

The architecture needs a new user-facing layer before the Planner:

```text
User request
  -> FDE Session: clarify, structure, track edit intent, produce review summary
  -> Planner: workflow brief -> IR
  -> Validator: schema + semantic checks
  -> Compiler: IR -> Dify DSL
  -> Deployer: push Dify draft
  -> Reverse Compiler: recognized edits -> IR
```

The FDE Session is not allowed to be a thin chat wrapper. It owns the workflow brief, clarification policy, edit-intent classification, and reviewer explanation.

## MVP Scope

Phase 1 must prove FDE as a role:

- Natural-language create request that reads like a spoken instruction.
- Minimal blocking clarification loop.
- Workflow brief generation.
- IR generation and validation.
- Dify draft push.
- Natural-language edit on the generated workflow.
- Reviewer-facing change summary.
- Narrow reverse-compile path for recognized edits in the deep archetypes.

If Phase 1 only supports `intent.json -> IR -> DSL`, it does not satisfy the FDE product direction.

Phase 1 evidence should include at least:

- Two deep archetypes from the design-partner backlog, with cross-border ecommerce operations as the default source (defaulting to ecommerce customer FAQ / KB Q&A and ecommerce order-exception triage); TCM clinic operations supplies the shadow corpus.
- A versioned eval corpus for create requests and natural-language edits.
- A transcript showing FDE asks blocking questions before planning.
- A successful create -> draft -> edit -> updated draft path.
- A reviewer summary that calls out credentials, data access, external calls, policy/budget changes, and human-review boundaries.
- A failed/unrecognized runtime edit that is blocked with a concrete remediation path.

## Things That Would Invalidate The Direction

- Users experience FDE as a form-filling wizard instead of an implementation partner.
- The system produces attractive drafts that cannot be traced back to IR and Git state.
- Ecommerce flows auto-execute refunds/compensations or final customer replies without a human-approved gate, or leak customer PII into prompts/logs.
- TCM shadow flows imply diagnosis, prescription, treatment claims, or patient-facing automation without review.
- TCM clinic operations becomes a second go-to-market motion before the primary ecommerce wedge is validated.
- Runtime portability claims are made before Phase 1.5 proves what does and does not port.

## Design Principles

- **Role first, compiler second.** Users buy an AI implementation engineer, not an IR pipeline.
- **Ask before guessing.** Missing business context must become a question, not a hallucinated default.
- **Every edit has provenance.** User instruction, interpreted diff, validation result, and Dify draft id are linked.
- **Runtime is the review surface.** FDE does not replace Dify's visual editor; it makes that editor source-controlled and governable.
- **Governance is visible.** Reviewer summaries must surface credentials, policies, budgets, side effects, and unrecognized edits.
