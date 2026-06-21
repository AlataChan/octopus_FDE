# FDE Design Agent UX Optimization Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

> **中文摘要:** 本计划把当前偏工程控制台的 FDE Console，改造成面向中国跨境电商运营/客服主管、中医诊所运营的“共创式流程设计工作台”。核心不是删除 IR/Validator/Compiler，而是把它们退到可信工程层；用户主路径看到的是角色、流程简报、设计预览、业务规则、人审风险和交付状态。

**Goal:** Turn the current FDE console from an engineering-facing IR/compiler workbench into a Chinese-first co-design cockpit where an AI design agent uses internal templates, personas, registry facts, and examples to help operations users create, revise, validate, and hand off workflows.

**Architecture:** Keep the existing deterministic IR, validator, compiler, and session store. Add a user-facing Design Agent layer before the Planner: persona selection, workflow brief, pattern retrieval, design preview, user participation gates, and reviewer-ready summaries. The 30 templates remain internal knowledge sources; users see business scenarios, decisions, risks, and review gates instead of choosing technical patterns.

**Tech Stack:** Existing FastAPI service, SQLite session store, Pydantic models, React/Vite/TypeScript, Tailwind, TanStack Query, existing IR validator/compiler pipeline.

---

## Review Gate

This plan is considered passable only if it satisfies all four original questions with concrete implementation steps:

| User Question | Plan Coverage | Pass Criteria |
|---|---|---|
| 1. 前后端界面如何进一步符合用户习惯 | Phases 1, 2, 4, 5 | Primary UI copy and IA no longer require business users to understand IR, Validator, Compiler, YAML, or raw templates. |
| 2. 当前规划流程是否只有 2-3 次反馈、整体是否线性 | Current Findings §2, Phase 3 | The plan distinguishes "3 rounds before questionnaire" from a total feedback cap, and fixes post-IR edit routing. |
| 3. 用户如何更多参与设计 | Phases 3 and 4 | Users can confirm brief, approve or challenge design preview, edit business rules, review risks, and react to diff/sample feedback. |
| 4. 如何把 30 个模块变成一个设计 agent 及知识来源 | Phase 6 | Templates become `DesignKnowledgeCard` evidence for retrieval/composition, not a user-facing template market. |

Minimum review score: 8.0/10 overall, with no dimension below 7.0.

## Current Findings

### 1. Interface Fit

The current UI is a capable engineering console:

- `web/src/pages/sessions/[id].tsx` lays out a three-pane workbench: chat, IR/flow/issues/diff, compile/download.
- `web/src/components/console/ChatPanel.tsx` still calls the assistant "Planner" and says "生成第一版 IR".
- `web/src/components/console/IRColumn.tsx` exposes "IR 工作台", YAML, Validator, Diff, and node details.
- `web/src/components/console/CompileBar.tsx` asks users to choose target/mode/binding and download artifacts.
- `docs/user-guide/fde-console-zh.md` teaches BYOK, IR, Validator, compile, download, manual import.
- The user guide mentions marking a runtime import/deployment, and the frontend API already exposes `markWorkflowDeployed()`, but the artifact UI currently only downloads files. This leaves the handoff loop incomplete.

This fits an engineer or implementation partner. It does not yet fit a cross-border ecommerce operator, customer-service lead, or clinic operator who expects an "AI 驻场流程工程师".

### 2. Planning Feedback Loop

The user assumption is partly correct but needs precision.

Current implementation:

- `loom/fde_session/clarify_engine.py` asks one blocking question at a time from `missing_fields()`.
- `loom/service/routes/sessions.py` switches to `questionnaire` when `session.clarify_round >= 3` and blocking fields remain.
- `tests/service/test_routes_sessions.py` verifies that the fourth blocked turn emits a questionnaire.
- `loom/state/sm.py` remains a linear state chain: `init -> drafting -> validated -> compiled -> downloaded`, with turns restarting drafting.
- `SessionStore` often writes final states directly, so the state machine is currently more of an artifact lifecycle label than a full collaboration state machine.
- After a self-design session has generated IR, follow-up edit text can still enter the clarification path because `_should_run_clarify()` only checks `self_design`. This risks treating "change the threshold to 500" as another brief-completion answer instead of an edit to the existing design.
- Historical clarification bubbles remain submittable in the UI, but the backend derives the pending field from the latest turn only. Submitting an old bubble can misalign the answer with the expected field.

So the system is not strictly "2-3 feedback rounds and done"; it is "single-question sequential clarification, then questionnaire fallback after three clarification rounds." It is linear in state and interaction, but not capped at two total user messages.

### 3. User Participation

Current participation points are thin:

- User answers clarification fields.
- User sends natural-language edits.
- User can view flow nodes, YAML, validation issues, and IR diff.
- User can choose a template when creating a session.

Missing participation points:

- No persona-first setup in the UI, even though ADR 0023 accepts Persona Brief.
- No workflow brief panel that lets the user correct trigger, data source, reviewer, success criteria, and compliance boundary before planning.
- No design preview before IR generation.
- No business-rule cards for "refund threshold", "PII flow", "human review gate", "buyer-facing message boundary".
- No test-run or sample-case feedback loop.
- No reviewer-ready summary surfaced as a primary object.

### 4. Thirty Templates

`registry/v1/templates/index.json` has 30 templates across broad technical and domain patterns. Exposing these directly is not good product design for the target users:

- The labels are technical patterns, not business jobs.
- Many patterns are not China-market primary workflows.
- The current template modal hard-codes `ecommerce/kb`.
- Choosing a template makes the user act as an architect, not as an operations author.

The right move is not to delete the templates. Keep them as Design Agent knowledge sources: examples, pattern skeletons, constraints, and retrieval candidates.

---

## Product Position

Use this framing in UI and docs:

- Primary screen: "让 FDE 和你一起设计一个流程".
- User-facing objects: "业务目标", "流程简报", "设计方案", "关键规则", "风险与人审", "交付包".
- Internal objects: IR, Validator, Compiler, Template, Binding, YAML remain available in an advanced tab.

Reject this framing for primary UX:

- "选择模板生成 IR"
- "发送给 Planner"
- "编译产物"
- "Validator OK"

These are implementation concepts, not authoring concepts.

---

## Implementation Plan

### Phase 1: Rename And Reframe The Existing Console

**Goal:** Make the current UI read like FDE, without changing backend behavior.

**Files:**
- Modify: `web/src/locales/zh.json`
- Modify: `web/src/locales/en.json`
- Modify: `web/src/components/console/ChatPanel.tsx`
- Modify: `web/src/components/console/CompileBar.tsx`
- Modify: `web/src/components/console/IRColumn.tsx`
- Modify: `docs/user-guide/fde-console-zh.md`

**Changes:**
- Rename "Planner 对话" to "FDE 设计对话".
- Rename "发送给 Planner" to "交给 FDE".
- Rename "IR 工作台" to "流程设计与校验", with IR/YAML moved to advanced wording.
- Rename "编译与产物" to "交付到运行时".
- Keep IR/Validator details visible for engineers, but make them secondary.
- Update the guide around user jobs: create, answer blocking questions, review design, adjust rules, hand off.

**Acceptance:**
- No UI copy on the primary path tells a business user to "生成 IR".
- Existing tests still pass, with snapshots/text assertions updated.

### Phase 2: Add Persona-First Session Setup

**Goal:** Make ADR 0023 visible and usable.

**Files:**
- Modify: `loom/service/routes/templates.py` or add `loom/service/routes/personas.py`
- Create: `loom/registry/personas.py`
- Modify: `loom/service/app.py`
- Modify: `loom/state/models.py`
- Modify: `loom/state/store.py`
- Modify: `loom/fde_session/brief.py`
- Create: `web/src/components/console/PersonaPicker.tsx`
- Modify: `web/src/components/console/TemplateModal.tsx`
- Modify: `web/src/lib/api.ts`
- Modify: `web/src/lib/types.ts`

**Changes:**
- Add `GET /v1/personas` from `registry/v1/personas/*.yaml`.
- Implement a typed `PersonaCatalog` in `loom/registry/personas.py` instead of reading YAML ad hoc from the route.
- Store `persona_id` and resolved persona snapshot on the session or brief draft.
- Default choices should be `ecommerce-operator`, `ecommerce-cs-lead`, `tcm-clinic-operator`.
- Replace template-first creation with persona-first creation:
  - "我是跨境电商运营"
  - "我是客服主管"
  - "我是中医诊所运营"
- Let the persona set default scope/compliance/reviewer, while still allowing override.

**Acceptance:**
- A blank self-design session has a visible persona before the first workflow question.
- The first clarification question should not ask for scope/compliance if persona already supplies them and the user accepts defaults.
- Persona loading fails fast on invalid YAML and has tests for all existing files in `registry/v1/personas/`.

### Phase 3: Replace One-Question Linear Clarification With A 2+1 Design Loop

**Goal:** Keep clarification short, but turn the final step into design confirmation rather than field collection.

**Files:**
- Modify: `loom/fde_session/clarify.py`
- Modify: `loom/fde_session/clarify_engine.py`
- Modify: `loom/service/routes/sessions.py`
- Modify: `loom/state/models.py`
- Modify: `loom/state/store.py`
- Modify: `web/src/components/console/ClarifyBubble.tsx`
- Modify: `web/src/components/console/QuestionnaireBubble.tsx`
- Create: `web/src/components/console/DesignPreviewBubble.tsx`

**Proposed interaction:**
- Round 1: persona-aware business target and scenario.
- Round 2: only blocking operational facts: trigger, data source, reviewer, success criteria.
- Round 3: FDE shows a design preview:
  - workflow steps
  - data sources
  - human review gates
  - buyer/patient-facing boundary
  - assumptions
  - risks
- User can approve, edit a section, or ask FDE to regenerate the design preview.
- Questionnaire remains as fallback when required fields are still missing.

**Backend model:**
- Add turn kind: `design_preview`.
- Add a serializable `DesignPreview` model with:
  - `summary`
  - `steps`
  - `business_rules`
  - `data_access`
  - `human_review_gates`
  - `assumptions`
  - `risk_flags`
  - `recommended_patterns`
- Planner runs only after design preview is approved or user explicitly says to proceed.

**Lower-cost MVP option:**
- If `DesignPreview` is too large for the first implementation, ship a `brief_review` turn first.
- Render the existing `WorkflowBriefDraft` (`trigger`, `scope`, `target_runtime`, `data_sources`, `credentials`, `approval_points`, `success_criteria`, `compliance_boundary`) as a confirmation card.
- Only after the user confirms the brief does the route call Planner. This still fixes the biggest participation gap without adding pattern retrieval yet.

**Required fixes while touching this flow:**
- Extract `questionnaire_after_rounds=3` into a named policy setting. The value can stay 3, but the code should not make readers infer product policy from a magic number.
- Add a distinct edit route or branch inside `create_turn`: if `latest_ir_json` exists and the message is a recognized edit, use `loom/fde_session/edit_intent.py` or Planner edit mode instead of re-entering missing-field clarification.
- Disable old `ClarifyBubble` and `QuestionnaireBubble` submissions, or submit explicit `turn_id` and `field_path` so the backend does not infer the pending field from the latest turn.
- Extend session state labels to include `clarifying`, `questionnaire_pending`, `design_preview`, `planning`, and `editing`, while keeping the persisted lifecycle auditable.

**Acceptance:**
- A complete ecommerce FAQ request can reach design preview within two user replies.
- Planner is not called before required gates are satisfied.
- The preview is visible in the turn history and stored for audit.
- A post-IR edit such as "把高价值阈值从 300 改成 500" updates or proposes an IR diff instead of asking unrelated brief questions.

### Phase 4: Add Participatory Design Surfaces

**Goal:** Let users co-design the workflow after IR generation without reading YAML.

**Files:**
- Modify: `loom/diff/ir_diff.py`
- Extend or implement: `loom/fde_session/review_summary.py`
- Create: `loom/fde_session/business_rules.py`
- Modify: `loom/service/routes/sessions.py`
- Create: `web/src/components/console/BriefPanel.tsx`
- Create: `web/src/components/console/BusinessRuleCard.tsx`
- Create: `web/src/components/console/RiskGateCard.tsx`
- Create: `web/src/components/console/SampleRunPanel.tsx`
- Modify: `web/src/components/console/NodeInspectDrawer.tsx`
- Modify: `web/src/components/console/IRDiffView.tsx`

**User participation mechanisms:**
- Brief confirmation:
  - trigger
  - scope/runtime
  - data sources and credentials
  - approval points
  - success criteria
  - compliance boundary
- Business-rule cards:
  - refund threshold
  - low-confidence escalation
  - reply language rule
  - SLA / follow-up timing
  - no compensation promise
- Risk gate cards:
  - PII class
  - credential expansion
  - external writeback
  - medical/patient-facing boundary
  - human approval requirement
- Node detail as business explanation first, raw node fields second.
- Diff view shows "业务变化" before raw field paths.
- Diff rows support "接受" and "要求修改"; the first MVP can record acceptance as an audit/turn metadata event and route modification requests into the next natural-language edit, without partial rollback.
- Sample-run panel lets the user paste a synthetic customer/order/patient case and mark whether the proposed behavior is acceptable.

**Acceptance:**
- Users can identify and request edits to at least three business rules without opening YAML.
- Reviewer summary includes credentials, data access, external calls, policy/budget, and compliance changes.

### Phase 5: Complete Runtime Handoff

**Goal:** Close the gap between compiled files and reviewable runtime drafts.

**Files:**
- Modify: `web/src/components/console/CompileBar.tsx`
- Modify: `web/src/lib/api.ts`
- Modify: `web/src/lib/types.ts`
- Modify: `loom/service/routes/registry.py`
- Modify: `docs/user-guide/fde-console-zh.md`

**Changes:**
- Add an artifact card action for "标记已导入 / 标记已交接".
- Let the user record target platform app id, import note, and reviewer handoff status.
- Show artifact state as "已生成", "已下载", "已导入待审核", "已交接".
- Keep hashes and artifact ids in advanced metadata.

**Acceptance:**
- The user can complete the path documented in `docs/user-guide/fde-console-zh.md`.
- A workflow record shows platform app id and deployment note after handoff.
- The session list/sidebar surfaces whether the workflow is still local-only or already handed off.

### Phase 6: Convert Templates Into Design Agent Knowledge

**Goal:** Keep 30 templates internal and make the Design Agent select, combine, and explain them.

**Files:**
- Modify: `loom/registry/templates.py`
- Modify: `registry/v1/templates/index.json`
- Create: `loom/design_agent/models.py`
- Create: `loom/design_agent/retriever.py`
- Create: `loom/design_agent/preview.py`
- Create: `loom/service/routes/design_agent.py`
- Modify: `loom/planner/prompts/system.md`
- Modify: `loom/planner/client.py`
- Modify: `web/src/components/console/TemplateModal.tsx`

**New metadata for each template:**
- `business_use_cases`
- `compatible_personas`
- `required_fields`
- `risk_tags`
- `composition_role`: `primary | guardrail | enrichment | handoff | reporting`
- `not_for_user_choice`: boolean, default true for technical patterns

**Intermediate knowledge model:**
- Add `DesignKnowledgeCard` as the Design Agent facing projection of one or more templates.
- Suggested fields:
  - `id`
  - `source_template_ids`
  - `name`
  - `intent_summary`
  - `scopes`
  - `compile_targets`
  - `tags`
  - `node_signature`
  - `registry_handles`
  - `policy_features`
  - `required_capabilities`
  - `constraints`
  - `anti_goals`
  - `confidence`
  - `rationale`
- This is intentionally not a user-chosen template. It is evidence for the Design Agent and audit trail.

**Design Agent behavior:**
- Input: persona, workflow brief draft, scope, target runtime.
- Retrieve top patterns from template metadata, registry handles, and examples.
- Compose a design preview, not final IR.
- Explain recommended patterns in business language.
- Pass selected pattern hints to the Planner as structured context.
- Filter order:
  - hard filter by persona, scope, target runtime, and registry visibility
  - semantic rank by intent and workflow brief
  - diversify by node signature so top results are not five variants of the same skeleton
  - reject patterns whose anti-goals conflict with persona compliance boundaries

**Service interface:**
- Add `POST /v1/design-knowledge/retrieve`.
- Input: `intent`, `scope`, `target`, `persona_id` or `persona_brief`, `brief_draft`, `top_k`.
- Output: 2-5 `DesignKnowledgeCard` rows plus missing constraints or clarifying questions.
- Keep `GET /v1/templates` for admin/debug and existing template tests, not as the ordinary authoring entry point.

**Frontend behavior:**
- Template modal becomes "从典型场景开始", not "模板库".
- Business starters:
  - 跨境电商 FAQ / 知识库问答
  - 跨境电商订单异常分诊
  - 商品内容本地化
  - 售后升级
  - 中医问诊前资料收集（影子）
- Advanced users can still browse raw templates behind an "高级模板" tab.

**Acceptance:**
- A user never has to choose among 30 technical templates to start a workflow.
- The Design Agent can return top 3 internal pattern candidates with reasons.
- Existing template seeding remains supported for tests and advanced workflows.

### Phase 7: Evaluation And Evidence

**Goal:** Verify this is better for the target user, not just cleaner internally.

**Files:**
- Create: `tests/design_agent/test_retriever.py`
- Create: `tests/fde_session/test_design_preview.py`
- Create: `web/src/components/console/DesignPreviewBubble.test.tsx`
- Create: `web/src/components/console/BusinessRuleCard.test.tsx`
- Modify: `docs/user-guide/fde-console-zh.md`
- Create: `reports/fde-design-agent-ux-gate.md`

**Minimum eval set:**
- 15 ecommerce FAQ create/edit prompts.
- 15 ecommerce order exception create/edit prompts.
- 5 TCM shadow prompts.

**Metrics:**
- User-visible clarification turns before preview: target <= 2 for complete prompts, <= 3 for ambiguous prompts.
- At least 90% of previews include trigger, data source, human review, success criteria, and compliance boundary.
- At least 90% of business-rule edits map to an IR diff or a clear unsupported-edit explanation.
- Reviewer summary always highlights credential/data-access expansion.

---

## Implementation Verification Commands

Run these after each relevant implementation phase. The exact test list can be narrowed during execution, but every phase must produce fresh evidence.

### Backend

```bash
pytest -q tests/fde_session tests/service tests/registry tests/planner
```

Required additions:

- `tests/registry/test_personas.py` validates every persona YAML can load into `PersonaBrief`.
- `tests/fde_session/test_design_preview.py` covers `brief_review` or `design_preview` before Planner execution.
- `tests/service/test_routes_sessions.py` covers post-IR edit routing and stale clarification submission handling.
- `tests/registry/test_design_knowledge.py` covers `DesignKnowledgeCard` retrieval, scope filtering, target filtering, and node-signature diversification.

### Frontend

```bash
npm --prefix web test -- --run
```

Required additions:

- `DesignPreviewBubble.test.tsx`
- `BriefPanel.test.tsx`
- `BusinessRuleCard.test.tsx`
- `CompileBar.test.tsx` coverage for mark-as-imported/handoff behavior.

### Full Gate

```bash
ruff check .
pytest -q
npm --prefix web test -- --run
```

If implementation changes layout or primary workflow screens, also run the dev server and inspect the console in browser before claiming UX completion.

---

## Risk Management

| Risk | Impact | Mitigation |
|---|---|---|
| The UI rename hides necessary engineering controls | Medium | Keep IR/YAML/Validator in an advanced tab; do not remove existing debug capabilities. |
| Design preview adds latency before IR generation | Medium | Start with deterministic `brief_review`; add pattern retrieval only after the brief gate works. |
| Persona defaults over-constrain advanced users | Medium | Let users override scope/runtime/compliance fields, but record overrides in audit. |
| Business-rule extraction becomes brittle | High | Use deterministic extractors for known fields first; route uncertain fields into "assumptions" rather than silently presenting them as facts. |
| Template retrieval leaks irrelevant finance/legal/medical patterns into ecommerce | High | Hard filter by persona, scope, target runtime, registry visibility, and anti-goals before semantic ranking. |
| Post-IR edits bypass clarification safety | High | Edit routing must still run validation, reviewer summary extraction, and risk gate generation. |
| Sample-run feedback is mistaken for production execution | Medium | Label first version as synthetic dry-run feedback; do not imply runtime execution until trace/runtime integration exists. |

---

## Self-Review Iterations

### Round 1: Failed

Scores:

- Clarity: 7/10
- Completeness: 6/10
- Feasibility: 7/10
- Risk Assessment: 5/10
- Requirement Alignment: 8/10
- Overall: 6.6/10

Issues found:

- The plan was mostly English despite the Chinese-first product and user preference.
- It lacked an explicit review gate mapping the four user questions to acceptance criteria.
- Persona implementation did not call out a typed registry loader.
- Verification commands and required tests were too vague.
- Risks were implicit rather than reviewed.

Fixes applied:

- Added Chinese summary and four-question review gate.
- Added `PersonaCatalog` requirement.
- Added backend/frontend/full verification commands.
- Added risk management table.

### Round 2: Passed

Scores:

- Clarity: 8.5/10
- Completeness: 8.5/10
- Feasibility: 8/10
- Risk Assessment: 8/10
- Requirement Alignment: 9/10
- Overall: 8.4/10

Residual constraints:

- This is still a plan, not an implementation.
- The exact frontend layout should be validated with screenshots once implementation starts.
- The `DesignKnowledgeCard` retrieval can begin deterministic/BM25-free; vector retrieval is intentionally out of MVP.


## What I Would Push Back On

### "Only 2-3 Feedbacks" Is Too Rigid

The product should target 2-3 user interactions before a design preview, not before final workflow correctness. Some workflows need later participation through sample tests, rule changes, and reviewer comments. Limit discovery interviews; do not limit co-design.

### "Linear Planning" Is Good For Audit, Bad For Design

Keep the persisted lifecycle linear for reproducibility: draft, validate, compile, handoff. But the user experience should feel iterative: preview, confirm, revise rule, test sample, review diff. The state machine can remain linear while the product exposes controlled loops around the design object.

### "Turn 30 Modules Into One Agent" Should Not Mean One Giant Prompt

The right architecture is not one monolithic prompt that knows everything. It is:

- one Design Agent interface
- retrieval over templates/personas/registry/examples
- structured design preview
- deterministic validation and compilation

The agent should orchestrate knowledge sources; it should not replace the registry, validator, or compiler.

---

## Prioritized MVP

If doing this in one practical pass, do it in this order:

1. Copy and IA rename: make the existing UI say FDE, not Planner/IR.
2. Persona-first creation using the existing persona YAML files.
3. DesignPreview turn before Planner.
4. Business-rule cards generated from brief + IR diff.
5. Runtime handoff marker on compiled artifacts.
6. Template metadata enrichment and Design Agent retrieval.

This sequence preserves the current working system while moving user perception from "compiler console" to "AI 驻场流程工程师".
