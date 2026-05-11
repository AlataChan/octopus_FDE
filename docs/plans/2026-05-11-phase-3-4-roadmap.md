# Phase 3 + Phase 4 Roadmap (paused state)

**Status**: Drafted 2026-05-11. **Not active**. octopus_FDE Phase 1 + Phase 2 已交付到 main；用户决定暂停新开发，进入"用 FDE 跑真实客户"阶段。本文档是未来重启 phase 时的起点。

## Decision principle (from 2026-05-11 user direction)

> "It is OK for personal user. we should test it."

所有 Phase 3/4 工作都被冻结，直到任何一条触发条件成立才解冻：
- 有 ≥2 家企业并发用 FDE → 启动 Phase 3.1
- 有 ≥1 家客户提供平台 trace API 凭证 → 启动 Phase 3.2
- 已运行 6+ 月、积累 ≥1000 条真实 trace → 启动 Phase 4.1

不触发，就不启动。这是"先 do the work，再 build the platform"路径（BP §阶段一）。

---

## Phase 3 — Multi-tenancy + AgentOS integration (~6-10 weeks 总量)

### Phase 3.1 — 多租户 + IR v0.4 (≈3-4 weeks)

**触发**: ≥2 家企业并发使用，或 FDE 实施商伙伴接入。

| ID | 任务 | 关键产出 |
|---|---|---|
| 3.1.1 | IR v0.3 → v0.4 minor bump（向后兼容） | 新增顶层 `tenant_id`、`metadata.owner_tenant + owner_user`；旧 IR 默认 `tenant_id=default` |
| 3.1.2 | SQLite → Postgres 数据层迁移 | SQLModel 引擎切换；Alembic 迁移；session/turn/registry/archive 全部按 tenant_id 隔离 |
| 3.1.3 | 真 RBAC 替换 X-Actor-Id seam（ADR 0027 要求） | Token 颁发 + 验证；`/v1/auth/login` + bearer；后端忽略客户端传的 X-Actor-Id；Actor 加 tenant_id + role |
| 3.1.4 | Tenant 管理 endpoint | `POST /v1/admin/tenants` + 邀请用户 |
| 3.1.5 | 前端登录页 + tenant 切换器 + admin 后台 | |
| 3.1.6 | ADR 0029 multi-tenancy + 0030 rbac-prod（0027 标 superseded） | |
| 3.1.7 | `loom-migrate` CLI：single-user SQLite → 多租户 Postgres | |
| 3.1.8 | 多租户隔离回归测试（A tenant 看不到 B tenant 数据） | |

**DoD**: 2 tenant × 3 user 演示数据并存且互不可见；Phase 2 Docker 平滑迁移到含 Postgres 的双容器架构；IR v0.4 spec 文档化。

### Phase 3.2 — AgentOS adapter-mcp 接收器 (≈3-4 weeks，**新增**)

**触发**: ≥1 家客户给平台 trace API 凭证。**这是连 FDE → AgentOS 飞轮的关键**。

| ID | 任务 |
|---|---|
| 3.2.1 | 新仓库 `AlataChan/adapter-mcp` 或保留单仓库 `loom/agentos/`（用户决定）。FastAPI + Postgres 接收器服务 |
| 3.2.2 | Hiagent + Dify trace API puller：定时拉客户已部署 agent 运行 trace；标准化为 AgentOS 统一格式 |
| 3.2.3 | 跨部署模式聚合 schema（工作流签名 + 行为指纹），匿名化跨客户聚合 |
| 3.2.4 | Drift detection 基础：trace 实际行为 vs workflow registry IR 基准 → drift score |
| 3.2.5 | FDE 端 `loom/service/routes/agentos.py` 加 export endpoint + Anonymizer 模块（去 API key / prompt 选项 / PII） |
| 3.2.6 | ADR 0031 agentos-export 协议 + ADR 0032 anonymization-policy |

**DoD**: FDE happy path 后 `loom-cli agentos export` 把数据推到接收器；接收器给出"该客户 N 个 workflow，平均 token X，drift Y"统计面板。

### Phase 3.3 (OPTIONAL) — LangGraph runtime alpha

**触发**: 客户明确要 LangGraph。否则**不做**——中国市场 Hiagent + Dify 已覆盖。

---

## Phase 4 — Pattern Library + Self-Improvement (~8-12 weeks)

**触发**: Phase 3.2 上线 6+ 月且 ≥1000 条真实跨客户 trace 数据。这是 BP §阶段四"AgentOS 不再需要靠 FDE 实施商来'推'进企业"的阶段；1B 估值核心。

### Phase 4.1 — Pattern Library (≈3-4 weeks)

| ID | 任务 |
|---|---|
| 4.1.1 | Pattern 数据模型：抽象 IR 骨架 + 频率 + 适用领域 + 边缘案例。Postgres |
| 4.1.2 | 聚类抽取 pattern 候选（IR 结构相似度） |
| 4.1.3 | FDE / admin 审核工作流，标注"公共模板"升级 |
| 4.1.4 | 新客户接入自动推荐 pattern：planner LLM + persona brief → 检索 top 3 → 对话起点 |
| 4.1.5 | 行业基准报告自动 PDF（市场营销 + 护城河展示） |
| 4.1.6 | ADR 0033 pattern-library |

### Phase 4.2 — Trace → Corpus 合成 (≈2-3 weeks)

替代 Phase 1.5 被砍的 75-prompt 人工 corpus。

| ID | 任务 |
|---|---|
| 4.2.1 | Trace → eval prompt 合成器（user_input + expected_output 提取） |
| 4.2.2 | 自动去重 + 多样性筛选 |
| 4.2.3 | 每个 pattern 生成 ≥20 prompt eval suite |
| 4.2.4 | Eval runner：定期跑 corpus 回归监控 |

### Phase 4.3 — Self-Edit Proposer (≈3-5 weeks)

**触发**: Phase 4.1 + 4.2 跑稳 + drift signal 充足。

| ID | 任务 |
|---|---|
| 4.3.1 | Drift signal → 候选 IR 修改方案的 LLM 提案器 |
| 4.3.2 | 安全栏杆：proposal 必须 validator pass；不允许跨节点剧变（"加 LLM OK，删 trigger 二次确认"） |
| 4.3.3 | Proposal review UI：FDE 工程师看到"建议改 X→Y，原因 Z，影响 W" |
| 4.3.4 | 接受/拒绝循环 → 拒绝信号反向学习 |
| 4.3.5 | ADR 0034 self-edit-safety-rails |

---

## 已确认砍掉 / 推迟（不要在 Phase 3/4 偷偷加回来）

| 原 Phase 3/4 项 | 状态 | 理由 |
|---|---|---|
| LangGraph runtime alpha | DROP（除非客户要） | 中国主流已覆盖 |
| 75-prompt 手工 eval corpus | REPLACED by 4.2 自动合成 | 用户砍了人工版 |
| CI Github Actions for Phase 1.5 | 推到 Phase 3.1 | 多人协作起来才需要 |
| Hiagent Workflow type | DROP（除非客户要） | Chat + ChatFlow 已覆盖 |
| Hiagent MultiAgent type | DROP（除非客户要） | 同上 |
| Hiagent 子 workflow ChatFlow | DROP | 同上 |
| Artifact 内注入 telemetry hooks | **永久 DROP** | 用户硬约束：customer artifact 必须纯净；trace 走 Phase 3.2 平台 API |
| IR-input → ChatFlow VariableConfigs 旁路 | MAYBE 跟 IR v0.4 合作 | 优先级低 |

---

## 重启前的检查清单

任何一个 Phase 3/4 项启动前，必走完：
1. 确认触发条件真的成立（不是想做而是必须做）
2. 重读用户砍掉列表，避免偷加内容
3. 重读 AgentOS_BP.md / AgentOS_1B_Thesis.md 战略框架是否变化
4. Plan Review by Codex（沿用 Phase 1/2 节奏：max 3 轮）
5. 用户拍板 scope 后才派活给 Codex 实施
