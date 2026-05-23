# Self-Design 意图澄清（Clarify）设计

> 状态：草案 v2（已整合 Codex Plan Review，待用户确认）
> 作者：Claude（架构师角色）
> 日期：2026-05-23
> 关联代码：`loom/fde_session/{brief,clarify,persona_brief}.py`、`loom/service/{app.py,routes/sessions.py}`、`loom/archive/schema.py`、`loom/state/store.py`、`web/src/components/console/ChatPanel.tsx`
>
> v2 修订摘要（来自 Codex Plan Review）：
> - 新增 `WorkflowBriefDraft`（部分态、全字段可选），仅在硬 gate 通过后 materialize 为严格的 `WorkflowBrief`
> - `target_runtime` 与 `scope` 真正穿透到 Planner / Validator，移除当前硬编码 `target="hiagent"` / `scope="ecommerce/kb"`
> - 扩展 `ArchiveEventType`，澄清事件 payload 用哈希 + 脱敏快照
> - SQLite 迁移改回项目现有的 `PRAGMA table_info` 探测风格
> - 明确 redaction 规则：brief 仅存 credential handle/scheme/hosts，禁止落地裸密文
> - 工期拆分：v1 先上确定性反问（`missing_fields()` 直驱）+ questionnaire；LLMClarifyEngine 推迟到 v2

## 1. 背景与问题

当前 Self-Design 路径是**单轮直出**：用户在 `ChatPanel` 输入一句意图 → `POST /v1/sessions/{id}/turns` → `app.state.planner(user_message, session, llm_config)` → 直出 IR JSON → `validate()` → 存 `ir_after`。中间没有任何反问环节。

后果：
- 用户原话经常缺关键约束（trigger 模式、合规等级、approval gate、目标 runtime…），Planner 只能"自己猜"，猜错就要靠人读 IR 来回改。
- 仓库里已有完整的澄清"原料"但完全没接到运行时：
  - `loom/fde_session/brief.py` 的 `WorkflowBrief`（typed: trigger / data_sources / credentials / approval_points / compliance_boundary / inputs / outputs / known_edits / success_criteria / intent）
  - `loom/fde_session/clarify.py` 的 `missing_fields(brief)`（已实现 block / warn 分级策略，有单测）
  - `loom/fde_session/persona_brief.py`（已能注入 Planner system prompt）

30 模板路径（`POST /sessions { template_id }`）不受影响，本设计仅针对 Self-Design。

## 2. 目标与非目标

**目标**
- Self-Design 进入"对话式澄清 → IR 生成"两段流程，对话风格接近 Claude Code 的 brainstorming（一次一问、优先多选、模型判断何时收口）。
- 模型自评 ready 时由 `missing_fields()` 做最后硬 gate，确保 trigger / compliance / credentials / approval / target_runtime 等硬字段不被遗漏。
- 最多 3 轮澄清；超过则降级为"一次性兜底问卷"收口。
- 复用已有 `WorkflowBrief` / `missing_fields()` / `PersonaBrief`，零侵入 30 模板路径与 IR/编译链。

**非目标**
- 不重构 Planner、IR、编译器、Runtime adapter。
- 不引入新的存储层；用现有 `SessionRow` 增字段。
- 不做用户级 brief 模板预设（先靠对话+模板路径覆盖）。
- 不解决 Dify 占位符 bug（见 §10 顺手清单，独立 PR）。

## 3. 总体流程

```
ChatPanel ─▶ POST /v1/sessions/{id}/turns { user_message }
                │
                ▼
         create_turn route
                │
                ▼
   session.brief_snapshot == null
       OR turn.kind in {"clarify"}?
                │
        ┌───────┴───────┐
       yes              no  ──▶ 旧路径（直出 IR）
        ▼
   ClarifyEngine.step(brief_snapshot, user_message, persona, scope, registry_snapshot)
        │
        │  返回 JSON：
        │    intent_update: dict           # 把本轮答复 merge 到哪些字段
        │    next_action: "ask"|"ready"
        │    question: { text, field_path, options[]|null, allow_freeform } | null
        │    confidence: 0..1
        │
        ▼
   merge → new_brief；持久化到 session.brief_snapshot
        │
        ▼
   next_action == "ready"?
        │
   ┌────┴────┐
  no         yes
   │          │
   │          ▼
   │     gate = missing_fields(new_brief, with_target_runtime=True)
   │     任一 block 级?
   │          │
   │      ┌───┴────┐
   │     yes      no
   │      │        │
   │      │        ▼
   │      │   进入 plan 阶段：调用 Planner(brief→intent, persona, scope, target) → IR → validate → ir_after
   │      │        │
   │      │        ▼
   │      │   turn.kind="plan", planner_reply, ir_after, brief_after
   │      │   清空/保留 brief_snapshot（见 §6 状态规则）
   │      │        │
   │      │        └────────────────────────────────┐
   │      ▼                                          │
   │   把第一条 block 转成 ClarifyQuestion 覆盖 LLM   │
   │   的 question（gate 优先）                       │
   │      │                                          │
   ▼      ▼                                          │
   ClarifyTurn 返回：                                 │
     turn.kind="clarify"                              │
     turn.clarify_question = { text, options, ... }  │
     turn.brief_after = new_brief                     │
     turn.clarify_round = N                           │
        │                                             │
        ▼                                             │
   N >= 3 且仍未 ready?                                │
        │                                             │
   yes → 进入 questionnaire 兜底（见 §7）              │
   no  → 返回前端，等待下一轮 user_message            │
                                                      │
   前端：根据 turn.kind 渲染 ClarifyBubble / TurnBubble │
                              ◀──────────────────────┘
```

## 4. 数据契约变更

### 4.1 `SessionRow`（现有表 + 新列）
- `brief_draft: TEXT NULL` — 序列化后的 `WorkflowBriefDraft`（JSON，全字段可选），空表示尚未进入或已退出澄清。
- `clarify_round: INTEGER NOT NULL DEFAULT 0` — 当前会话内累计澄清轮次（仅澄清 turn 计入，plan turn 不计）。
- `target_runtime: TEXT NULL` — `"hiagent"` / `"dify"`，由澄清阶段确定后落地，供后续 plan 阶段使用。
- `scope: TEXT NULL` — registry scope（如 `ecommerce/kb`、`clinic/kb`），由澄清阶段或 persona 推导后落地。
- `self_design: BOOLEAN NOT NULL DEFAULT 0` — 显式区分 self-design 会话与模板会话；仅 self-design 进入澄清状态机，模板 seed 会话保持直出/编辑路径。

> 迁移：与现有风格一致（`loom/state/store.py` 的 init 段已用 `PRAGMA table_info(...)` 探测 + 条件 `ALTER TABLE`）。对每个新列：
> ```python
> cols = {row["name"] for row in con.execute("PRAGMA table_info(sessions)").fetchall()}
> if "brief_draft" not in cols:
>     con.execute("ALTER TABLE sessions ADD COLUMN brief_draft TEXT")
> # …其余同理
> ```
> 不使用 try/except `OperationalError`。老 session 默认 NULL / 0，进入 self-design 才创建。

### 4.1.5 `WorkflowBriefDraft`（新模型，全字段可选）
原因：现有 `WorkflowBrief` 是 `_Strict`（frozen, `extra="forbid"`）且 `title` / `intent` / `compliance_boundary` 必填，无法承载澄清中途的部分态。

```python
class WorkflowBriefDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")  # mutable, 字段全可选
    workflow_id: str | None = None
    title: str | None = None
    intent: str | None = None
    trigger: TriggerSpec | None = None
    inputs: list[InputSpec] = Field(default_factory=list)
    data_sources: list[DataSourceRef] = Field(default_factory=list)
    tools: list[str] = Field(default_factory=list)
    credentials: list[CredentialBindingRef] = Field(default_factory=list)
    approval_points: list[ApprovalPoint] = Field(default_factory=list)
    success_criteria: str = ""
    compliance_boundary: ComplianceBoundary | None = None
    known_edits: list[str] = Field(default_factory=list)
    target_runtime: Literal["hiagent", "dify"] | None = None
    scope: str | None = None

    def to_strict(self) -> WorkflowBrief: ...  # 任一必填空缺时抛 ValueError
```

`missing_fields()` 改造：接收 `WorkflowBriefDraft` 而非 `WorkflowBrief`，原有规则照搬；只在 gate 通过且 `to_strict()` 成功后才进入 plan 阶段。

### 4.2 `TurnRow`（现有表 + 新列）
- `kind: TEXT NOT NULL DEFAULT 'plan'` — `"clarify" | "plan" | "questionnaire"`
- `clarify_question: TEXT NULL` — JSON：`{text, field_path, options:[{label,value}]|null, allow_freeform, severity}`；questionnaire 时为 `{questions:[…]}`
- `brief_before: TEXT NULL` — 入参 `WorkflowBriefDraft` 快照（已脱敏，见 §11）
- `brief_after: TEXT NULL` — 出参 `WorkflowBriefDraft` 快照（已脱敏，见 §11）
- `error_correlation_id: TEXT NULL` — Planner / Validator 失败时生成的排障关联 ID；前端可见，原始异常不落 DB。

> 迁移同 4.1 风格：PRAGMA 探测 + 条件 ALTER。

### 4.3 `POST /v1/sessions/{id}/turns` 响应（向后兼容）
现有字段不变。新增可选字段：
```json
{
  "kind": "clarify" | "plan" | "questionnaire",
  "clarify_question": null | { "text", "field_path", "options", "allow_freeform", "severity" },
  "brief_after": null | { ...WorkflowBrief... },
  "clarify_round": 0..3,
  "error_correlation_id": null | "uuid4hex"
}
```

## 5. ClarifyEngine（v1 = 确定性；v2 = LLM）

**v1（首发）：`DeterministicClarifyEngine`**
- 入参 `brief_draft` → `missing_fields(brief_draft)`
- 若有 block：取第 1 条，按 `field_path` 查表（`field_path → 候选 chip / 形态 / 文案`）→ 产出 `ClarifyQuestion`
- 若无 block：`next_action="ready"`
- 答复 merge：服务端按 `field_path` 路由到对应字段写入器（trigger 解析枚举、data_sources 拆出 handle、credentials 校验为 ref 形态等），失败则把同一字段再问一次（不计入额外轮次，最多 1 次重试）
- 完全可单测，无 LLM 依赖

**v2（后续）：`LLMClarifyEngine`**（保留下方原设计，仅 v2 才接入）

新模块：`loom/fde_session/clarify_engine.py`（v1 + v2 同一模块两个实现）。

```python
class ClarifyEngineResult(BaseModel):
    intent_update: dict                       # merge 到 brief 的 patch
    next_action: Literal["ask", "ready"]
    question: ClarifyQuestion | None
    confidence: float                          # 0..1

class ClarifyEngine(Protocol):
    def step(
        self,
        *,
        brief: WorkflowBrief | None,
        user_message: str,
        persona_brief: PersonaBrief,
        scope: str,
        registry_snapshot: RegistrySnapshot,
        round_index: int,
    ) -> ClarifyEngineResult: ...
```

**实现**：`LLMClarifyEngine`
- system prompt：明确"一次一问、优先多选、硬字段（trigger/compliance/credentials/approval/target_runtime）必收"
- 强制 JSON 出参（`response_format=json_schema` 或客户端 schema 校验+重试 1 次）
- 把 `registry_snapshot`（当前 scope 过滤后的 datasets / credentials / tools）作为多选 chip 候选来源
- 失败回退：解析失败 → 走兜底问卷（不抛错给用户）

**测试桩**：`FakeClarifyEngine`（脚本驱动），用于服务层 + 路由的单元/集成测试。

## 6. 状态机规则

| 当前 session.brief_snapshot | 当前 user_message | 行为 |
|---|---|---|
| null | 首条 self-design 消息 | 进 ClarifyEngine 第 1 轮，写 brief_snapshot |
| 非空（在 clarify 中） | 用户答复 | ClarifyEngine 第 N+1 轮，update brief |
| 非空（已 ready 上一轮出 plan） | 新消息 | **重置 brief，重新进 clarify**（视为新的设计意图迭代）；或下游可选"继续在现 IR 上局部编辑"——本设计 v1 先走"重置"路径 |
| 非空 + clarify_round >= 3 + 仍未 ready | 任意 | 触发 questionnaire 兜底（见 §7） |

`brief_snapshot` 的清空时机：进入 `plan` 阶段成功出 IR 后**保留**（便于审计），但 `clarify_round` 归零，下次新消息按"新的设计意图迭代"重新起轮。

## 7. 兜底问卷（questionnaire）

当 `clarify_round >= 3` 且 `missing_fields()` 仍有 block，返回 `kind="questionnaire"` 的 turn：
- 把当前所有 block 级缺失字段一次性铺平
- 前端渲染为短表单（每个字段一个 chip 组或短答框）
- 用户一次性提交 → 合并 brief → 直接进入 gate；通过则出 IR，未通过则返回标红字段（不再追加轮次，但允许 resubmit）

实现复用：服务端把多条 `ClarifyQuestion` 数组返回到 `clarify_question.questions[]`（与单问形态共用结构，前端按数组长度切换 UI）。

## 8. 硬 Gate 字段扩展

`missing_fields()` 现状阻塞的字段：trigger、data_sources（条件）、credentials（条件）、approval_points（条件）、success_criteria；warn 级：known_edits、intent 过短。

**新增 block 级**：
- `target_runtime`（`"hiagent" | "dify"`）—— 编译器选择直接决定能用的节点特性集合（Hiagent 不支持 `policy.escalation` / `policy.guardrails` 等），早一步固化能减少回工。
- `scope`（如 `ecommerce/kb` / `clinic/kb`）—— 决定 registry 过滤集；当前路由硬编码 `ecommerce/kb`，必须显式化。

`WorkflowBriefDraft` 已含两个字段（见 §4.1.5），`clarify.py` 加两条 block 规则。

## 8.5 Planner / Validator 适配（关键修正）

现状（待修复）：
- `loom/service/app.py` 的默认 `planner` 适配器硬编码 `scope="ecommerce/kb"`、`target="hiagent"`
- `loom/service/routes/sessions.py:167` 的 `validate(..., scope="ecommerce/kb", ...)` 同样硬编码

改造：
- `PlannerCallable` 协议签名增加 `target: Literal["hiagent","dify"]` 与 `scope: str`（关键字参数），由 `create_turn` 在 plan 阶段从 `session.target_runtime` / `session.scope` 读取并传入
- `validate(..., scope=session.scope, ...)` 同步替换
- `app.py` 默认适配器把 `target` / `scope` 透传到 `IntentRequest`，**不改动 Planner、IR、编译器、Runtime adapter 协议**
- 兼容性：30 模板路径在 `_seed_session_from_template` 阶段就把 `target_runtime` / `scope` 写入 session（取自 `entry.compile_targets[0]` / `entry.scopes[0]`），保证模板路径仍能直出

## 9. 前端变更

### 9.1 类型（`web/src/lib/types.ts`）
```ts
type ClarifyQuestion = {
  text: string;
  field_path: string;
  options?: { label: string; value: string }[];
  allow_freeform: boolean;
  severity: "block" | "warn";
};

type Turn = {
  // …existing
  kind: "clarify" | "plan" | "questionnaire";
  clarify_question?: ClarifyQuestion | { questions: ClarifyQuestion[] };
  brief_after?: WorkflowBriefSnapshot;
  clarify_round?: number;
};
```

### 9.2 组件
- `web/src/components/console/ClarifyBubble.tsx`（新）—— 渲染单问；options 用 `<Chip>` 多选/单选，allow_freeform 时附带短文本输入；提交即调用 `onSend(answer_text)`，前端把多选拼成自然句（如 "trigger=schedule, every 1h"），降低后端解析负担。
- `web/src/components/console/QuestionnaireBubble.tsx`（新）—— 渲染多问；统一短表单。
- `ChatPanel.tsx` 根据 `turn.kind` 切换 bubble。

### 9.3 i18n
`web/src/locales/*` 新增：`clarify.title`, `clarify.subtitle`, `clarify.send`, `clarify.options.trigger.manual` 等枚举翻译。

## 9.5 审计事件扩展（archive schema）

`loom/archive/schema.py` 的 `ArchiveEventType` 是闭合 `Literal`；需新增：
- `"turn.clarify_started"` — payload: `{turn_id, round_index, user_message_sha256, draft_before_sha256}`
- `"turn.clarify_replied"` — payload: `{turn_id, round_index, ask_field_path, options_count, draft_after_sha256, gate_pass: bool}`
- `"turn.questionnaire_emitted"` — payload: `{turn_id, missing_fields:[field_path,…], draft_snapshot_sha256}`

所有 payload **不写入 raw user_message 与 brief 内容**，仅写 sha256 + 元数据；如需排查，从 sessions DB 取脱敏快照（见 §11）。

## 11. 安全与脱敏规则

`brief_draft` / `brief_before` / `brief_after` 落地与审计前的强制脱敏：

| 字段 | 允许落地 | 禁止落地 |
|---|---|---|
| `credentials[].handle` | ✅ | — |
| `credentials[].scheme` | ✅ | — |
| `credentials[].allowed_hosts` | ✅ | — |
| credential 裸值 / Authorization 头 / api_key 字符串 | — | ❌ 检测到即 reject 该轮 turn 并要求重新表述 |
| `inputs[].name` / `inputs[].type` / `inputs[].required` | ✅ | — |
| `success_criteria` / `intent` | ✅（自由文本，先扫密文，命中替换为 `[REDACTED]`） | 上限 10 KB，超长截断；禁止 credential 裸值 |
| `turns.user_message` | ✅（普通文本） | 命中潜在密文时只能落固定 sentinel：`[REDACTED:potential_secret]` |
| `turn.validation_errors` | ✅（稳定错误码，如 `planner_error`） | ❌ Planner / Provider / Validator 原始异常文本 |
| 用户上传文件内容 | — | ❌（仅记录文件名/大小 hash） |

实现：新增 `loom/fde_session/redaction.py` 暴露 `def redact_draft(d: WorkflowBriefDraft) -> WorkflowBriefDraft`、`def redact_text(text: str) -> str` 与 `def has_potential_secret(text: str) -> bool`（启发式正则：`(?i)bearer\s+[a-z0-9_\-]{16,}` / `sk-[A-Za-z0-9]{20,}` 等）。检出用户输入潜在密文时，在写入 turn 前替换 `user_message` 为 sentinel，把当轮 turn 标为 `kind="clarify"` 并复用反问"请用 credential handle 名称替代裸密文"。Planner / Validator 失败时，客户端与 DB 仅保留 `planner_error` + `error_correlation_id`，archive payload 只写 `error_message_sha256`。

## 10. 顺手清单（独立 PR，与本设计正交）

修 Dify 编译器 5 个模板占位符泄漏：
- `loom/runtimes/dify/v1_14/compiler_nodes.py` 里 `http.body` 字段未走 `${node.field}` → `{{#node.field#}}` 翻译
- 复现：`code-generation-tdg` / `memory-augmented` / `document-intelligence` / `self-improving` / `domain-transforming-integration`
- 防回归：`tests/registry/test_templates.py` 第 23 行附近加 `assert "${" not in text` 对所有 dify 目标 yml

## 11. 验收标准

1. 全新 self-design 会话，输入"我要一个客服 FAQ"，被反问至少 1 轮，触达 trigger / target_runtime / compliance 至少之一。
2. 故意只回答 1 个问题、跳过 3 轮，第 4 轮收到 questionnaire 形态 turn。
3. 模型自评 ready 但 brief 缺 `target_runtime` → 服务端仍返回 clarify turn（gate 生效）。
4. 30 模板路径（`createSessionFromTemplate`）端到端 smoke 用例零回归。
5. 所有澄清 turn 的失败被审计写入 `archive_writer`（事件类型 `turn.clarify_started` / `turn.clarify_replied`）。
6. 单元测试：`FakeClarifyEngine` 脚本化 3 类剧本（直接 ready / 反问 2 轮再 ready / 3 轮未 ready 进兜底）。
7. 现有测试套件 0 回归（`pytest -q`、`npm --prefix web test`）。

## 12. 风险与缓解

| 风险 | 缓解 |
|---|---|
| LLM JSON 出参不稳 | 强制 schema + 重试 1 次 + 兜底问卷托底 |
| 反问体验冗长 | 3 轮上限 + 多选优先 + LLM 一次问最关键字段 |
| brief_snapshot 与 IR 不一致漂移 | brief_after 持久化到 turn；plan 阶段记录 brief→IR 因果链于 archive |
| 路由分支后老 client 不识别新 kind | TurnResponse 老字段保留；新字段为可选；老前端会忽略 clarify turn 并把 planner_reply 显示为空，需 release notes 提示前端同步升级 |

## 13. 工期与拆分（v1 收口先确定性 → v2 上 LLM）

**v1（首发，必须的子集）**
1. backend: 新增 `WorkflowBriefDraft` + `target_runtime`/`scope` 字段 + 改造 `missing_fields()` 接 Draft + 单测
2. backend: `app.py` 默认 planner 与 `sessions.py:create_turn` 的 `target` / `scope` 解耦改造（含 30 模板 seed 阶段写 session.target_runtime / scope）+ 集成测试
3. backend: `SessionRow` / `TurnRow` 字段扩展（PRAGMA-probe 迁移）+ `ArchiveEventType` 扩展 + `redaction.py` + create_turn 路由按 brief_draft 状态分支（**v1 用确定性反问**：直接从 `missing_fields()` 返回的第一条 block 转为 question；不接 LLM 提问器）
4. frontend: `Turn` 类型 / `ClarifyBubble` / `QuestionnaireBubble` / `ChatPanel` 分支 + 组件单测
5. backend+frontend: questionnaire 兜底（轮次到 3 一次性铺平）+ E2E smoke 三剧本

> v1 关键简化：不上 LLM 提问器；提问由 `missing_fields()` 直接驱动（每轮取第一条 block）。这就足以覆盖 §11 验收 1-7 条，且完全可单测、零 LLM 依赖。

**v2（后续迭代）**
6. backend: `LLMClarifyEngine` 真实实现（结构化出参 + 多选 chip 候选来自 registry 过滤）→ 让反问更自然、能合并多条问题
7. backend: persona-aware 反问（接 `PersonaBrief`，按行业语境调整问法）

**独立 PR（顺手清单）**
8. Dify 编译器 5 个模板 `http.body` 占位符泄漏修复 + `tests/registry/test_templates.py` 加 `assert "${" not in text`

---

> 待 Codex Plan Review 评分（标签：`[PLAN REVIEW REQUEST]`），用户确认后进入实现阶段。
