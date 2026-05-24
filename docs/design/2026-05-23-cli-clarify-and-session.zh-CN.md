# CLI 澄清与会话内省命令设计

> 状态：草案 v2（已整合 Codex Plan Review，overall=7.75 通过门禁）
> 作者：Claude（架构师角色）
> 日期：2026-05-23
> 关联代码：`loom/cli/main.py`、`loom/cli/commands/`、`loom/fde_session/`、`loom/state/store.py`、`loom/service/routes/sessions.py`

## 1. 背景

`loom` CLI 已有 `plan / validate / compile / hiagent push` 4 个命令，但新增的 Self-Design **意图澄清流程目前是 web-only**。CI、Codex/Gemini 等 agent、运维排障没有 headless 入口。

本设计只做"自动化场景必需"的最小补集，不做 CLI 版的交互对话循环（那是把 web 搬一遍，回报低）。

## 2. 目标与非目标

**目标**
- 加 `loom brief` —— 一次性 dry-run 确定性澄清，输入 intent + scope + target，输出 brief draft 与缺字段列表（JSON）
- 加 `loom session` 子命令：`show-turns` / `brief` —— 让运维能 headless 读取澄清状态、turn 列表
- CLI 命令是 service 层薄壳子，不再实现业务逻辑

**非目标**
- 不做交互式 TUI / 对话循环
- 不做"模拟前端"的 chip 渲染
- 不动 IR / 编译器 / Runtime adapter 协议
- 不引入新存储

## 3. 命令规格

### 3.1 `loom brief`

> **角色定位**：missing-field probe（缺字段探针）。**exit code 1 是 CI 的正常自动化分支**，不视为命令失败；exit code 2 才是真错误。这一点写入 `--help` 与 README。

```
loom brief [INTENT_FILE]
  --scope TEXT             必选；如 ecommerce/kb / clinic/kb
  --target [hiagent|dify]  可选；缺省进入 missing 列表
  --draft-json PATH        可选；预填 brief 字段的 JSON（如 {"trigger":{"mode":"manual"},
                           "success_criteria":"..."}）；与 stdin/INTENT_FILE 联合后做 merge
  --json / --text          输出形态；默认 --json
  --stdin                  从 stdin 读 intent 文本（与 INTENT_FILE 互斥）

退出码：
  0  ready（所有 block 字段齐全；可被 CI 当作"已就绪，可调 plan"信号）
  1  missing_block（CI 的正常分支：仍有阻塞字段；stderr 也按 JSON 输出缺失列表）
  2  invalid input / redaction trip / IO 错误（真异常）
```

通过组合 `--draft-json` 把 `trigger / compliance_boundary / success_criteria` 等 block 字段一次性预填，**exit 0 路径就是可达的**（用于 CI 在已有 brief 模板的场景下做 fast-path）。

**输入**：纯文本意图（一行或多行均可）。

**输出（--json）**（所有 JSON 输出含 `cli_schema_version: "1"`，错误形态也含）：
```json
{
  "cli_schema_version": "1",
  "brief_draft": {
    "intent": "...",
    "scope": "ecommerce/kb",
    "target_runtime": "hiagent",
    "trigger": null,
    "data_sources": [],
    "credentials": [],
    "approval_points": [],
    "compliance_boundary": null,
    "success_criteria": ""
  },
  "missing_block": [
    {"field_path": "trigger", "question": "What trigger should start this workflow?"},
    {"field_path": "compliance_boundary", "question": "..."}
  ],
  "missing_warn": [
    {"field_path": "known_edits", "question": "..."}
  ],
  "ready": false
}
```

**错误形态**（exit 2）：
```json
{"cli_schema_version": "1", "error": "intent_redacted", "detail": "potential secret in intent"}
```

**实现要点**：直接调用 `loom.fde_session.clarify.missing_fields()` + 把 intent / scope / target 塞进新构造的 `WorkflowBriefDraft`。**不调 LLM、不写 DB、不写 archive**。纯 dry-run。

### 3.2 `loom session show-turns`

```
loom session show-turns SESSION_ID
  --data-dir PATH    可选；缺省取 $LOOM_DATA_DIR
  --actor TEXT       必选；无 implicit fallback；与 store.list_turns(actor_id=...) 严格匹配
  --json / --table   默认 --table；CI 场景用 --json
```

**输出（--table，定宽手撸列，不引入 rich）**：
```
TURN_ID  KIND          STATUS     CREATED              DIGEST
abc12    clarify       succeeded  2026-05-23 14:58:01  field=trigger sev=block
def34    plan          succeeded  2026-05-23 14:59:12  ir_ok
ghi56    questionnaire succeeded  2026-05-23 15:00:30  missing=4
```

**输出（--json）**：
```json
{
  "cli_schema_version": "1",
  "session_id": "...",
  "turns": [
    {"turn_id":"abc12","kind":"clarify","status":"succeeded","created_at":"...","digest":"field=trigger sev=block"}
  ]
}
```

**输出字段白名单（安全 §6）**：
- 仅包含 `turn_id / kind / status / created_at / digest` 这 5 个字段
- **严禁输出**：`user_message`（原始用户输入或 sentinel）、`brief_before`、`brief_after`、`validation_errors` 原文、`planner_reply`、`ir_after`、`ir_before` —— 这些字段只在 web 鉴权路径下走（避免 CLI 越权读出敏感数据）
- 想看 ir / brief 全文 → 另起服务 + web 鉴权，不在 CLI 暴露

**实现要点**：复用 `SessionStore.list_turns(session_id, actor_id=...)`；严格按 actor_id 过滤（store 已有此能力），CLI 不做隐式 fallback。

### 3.3 `loom session brief`

```
loom session brief SESSION_ID
  --data-dir PATH    可选；缺省 $LOOM_DATA_DIR
  --actor TEXT       必选；store 严格按 actor_id 过滤
  --json             默认 JSON（这条命令不提供 table 形态）
```

**输出**（含 `cli_schema_version: "1"`）：`sessions.brief_draft` 列内容（已脱敏，与 web 等价），外加：`clarify_round`、`target_runtime`、`scope`、`self_design` 标志位。

```json
{
  "cli_schema_version": "1",
  "session_id": "...",
  "self_design": true,
  "clarify_round": 2,
  "target_runtime": "hiagent",
  "scope": "ecommerce/kb",
  "brief_draft": { ...脱敏后的字段... }
}
```

**退出码**：0 = 找到 session 并打印；1 = session 不存在 或 brief_draft 为空（stderr 输出 `{"cli_schema_version":"1","error":"not_found","detail":"..."}`）。

## 4. 共享设施

- 现有 `loom/cli/main.py` 用 `click`。新命令沿用同套 `@click.group` / `@click.command`。
- 新增 `loom/cli/commands/brief.py` 与 `loom/cli/commands/session.py`。
- 数据加载：`SessionStore` 已支持以 `data_dir` 初始化；CLI 直接走它，不经服务进程，因此**离线可用**。
- 输出渲染：JSON 用 `json.dumps(..., ensure_ascii=False, indent=2)`；table **手撸定宽列**（不引入 rich 等新依赖），列宽根据所收行内容动态算 max + padding。

## 5. 数据契约 / 状态机变更

**无**。这两条命令完全只读 + 纯函数 dry-run，不改 DB、不写 archive、不改 IR 协议。

## 6. 安全规则（沿用 spec §11）

- `loom session brief` 输出已是脱敏后的 `brief_draft`（与 DB 存储等价），无需额外处理。
- `loom brief`（dry-run）输入文本调用 `has_potential_secret()`：命中则 stderr 警告 + 把 intent 字段以 `[REDACTED:potential_secret]` 落 JSON（与 web 路径一致），返回码 2。

## 7. 验收标准

1. `echo "做一个客服 FAQ" | loom brief --stdin --scope ecommerce/kb` 返回 exit code = 1（缺 trigger / target_runtime / compliance），stderr 列出至少 3 条 missing_block。
2. `echo "..." | loom brief --stdin --scope ecommerce/kb --target hiagent` + 完整 intent → 仍 missing block（缺 trigger 等），命令本身正确解析。
3. `loom session show-turns <id> --actor test --json` 输出与 web `GET /v1/sessions/{id}/turns` 等价的 turn 列表（字段子集即可）。
4. `loom session brief <id> --actor test` 在 brief_draft 为空时返回 exit code = 1 + 明确 stderr 说明。
5. 不存在的 session-id → exit code = 2 + 提示。
6. 含明显密钥的 intent → exit code = 2 + `[REDACTED]` sentinel。
7. `pytest -q` 全绿；新增 CLI 命令各覆盖 1-2 个 happy path + 1 个 error path 单测，跑在 `tests/cli/` 下用 `click.testing.CliRunner`。
8. **Actor 隔离测试（新增）**：同一 `SESSION_ID` 用错误 `--actor` 调 `session show-turns` / `session brief` 必须返回 not_found（exit 1）；不能读到其他 actor 的数据。
9. **白名单字段测试（新增）**：`session show-turns --json` 输出禁止包含 `user_message` / `brief_before` / `brief_after` / `validation_errors` / `planner_reply` / `ir_after` / `ir_before` 任一字段（用 jsonpath / 字段集合断言）。
10. **`--draft-json` ready 路径测试（新增）**：构造完整 trigger + compliance + success_criteria 的 draft-json，`loom brief` 应返 exit 0、`ready=true`。
11. **schema 版本测试**：所有 JSON 输出（含 stderr 错误形态）首字段或顶层 key 含 `cli_schema_version: "1"`。

## 8. 工期与拆分

按 Codex 一次性可交付的颗粒：
1. backend: 新增 `loom/cli/commands/brief.py` + 单测（覆盖 ready / missing_block / redacted secret 三剧本）
2. backend: 新增 `loom/cli/commands/session.py`（含 `show-turns` 与 `brief` 子命令）+ 单测
3. backend: `loom/cli/main.py` 注册新命令；更新 `README.md` 的 "CLI Relationship" 段，列出新命令一行用法

不拆 PR；3 步合一 commit chain（feat × 2 + docs × 1）。

## 9. 风险

| 风险 | 缓解 |
|---|---|
| `SessionStore` 需要 fernet 才能 `get_session` | session 元数据读不需要解密 LLM key；如确有阻塞，CLI 加 `--fernet-key-env` 参数或文档化要求设 `LOOM_FERNET_KEY` |
| `--actor` 强制让运维瞎填 | spec 要求显式声明，避免与 web actor 状态隐式耦合 |
| CLI 输出 schema 漂移 | JSON 输出在 README/docstring 明确版本字段 `cli_schema_version: "1"`，未来 break 时升版本号 |

---

> 待 Codex Plan Review，标签：`[PLAN REVIEW REQUEST]`。
