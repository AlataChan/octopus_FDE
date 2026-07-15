# Backend Architecture and Code Review

## Executive Summary

本次审阅覆盖 `loom/` 后端、IR schema/registry、运行时编译链、状态与归档、CLI/构建脚本、相关测试，以及 PRD/ADR 的实现一致性。结论是：仓库已经具备可演示的“会话 → 规划 → IR → 校验 → 生成制品 → 归档/注册”骨架，但当前不能把“Validator 通过”或“生成成功”解释为目标运行时会忠实执行 IR。最主要的系统性风险是校验器不构建控制流和类型流，两个编译器又会在不报错的情况下改写、丢弃或占位实现 IR 语义。

风险排序如下：

- 1 项 Critical：编译器对循环、并行、条件、Agent、模型、凭据等语义做静默降级，且没有可执行的一致性门禁。
- 11 项 High：Validator 漏检、既有 IR 编辑实际重建、路径穿越、安全策略缺失、漂移哈希不稳定、运行时抽象旁路、审阅 diff 不完整、registry pin 失效、异常泄密、并发覆盖和跨用户授权。
- 8 项 Medium：归档竞争、编译持久化非事务、敏感信息识别窄、规划失败恢复不足、wheel 资源缺失、固定运行时环境不可启动、状态机漂移、依赖构建不可复现。
- 3 项 Low：CLI 行为与文档不一致、Phase 0 门禁引用不存在脚本、本地环境脚本存在已知口令误用风险。

验证结果：全量测试通过（420 passed、4 skipped、2 xfailed），但一致性 runner 只定义数据结构，没有执行编译/部署/运行；两个 xfail 也直接承认已知的制品结构泄漏。专项行为探针进一步确认，当前 `validate()` 会接受循环、悬空边、重复 node id、错误输出路径、类型不匹配和错误 registry pin；显式默认值与省略默认值会产生不同 IR hash。专项安全脚本对 4 个示例返回非零，均为缺少幂等声明的 code 节点。静态检查工具未安装在当前环境，因此未把 lint/typecheck 结果当作审阅证据。

建议把当前生成/编译能力明确标记为 preview，并在恢复生产就绪声明前按顺序完成：校验器 fail-closed、编译器支持矩阵与拒绝策略、可执行双运行时一致性门禁、既有 IR 的确定性编辑、并发与授权隔离。

## Findings by severity

### Critical

#### C-1 — 编译成功会静默改变 IR 的执行语义

- **Evidence:** 次运行时把 `loop`、`parallel` 和 `agent` 全部编译为返回 `TODO` 字符串的 code 占位节点（`loom/runtimes/dify/v1_14/compiler_nodes.py:254-265`），无法解析的条件表达式被静默替换为“输入 query 非空”（`loom/runtimes/dify/v1_14/compiler_nodes.py:268-277`），LLM/检索/HTTP 映射忽略模型、rerank、凭据、重试、幂等和部分 schema 约束（`loom/runtimes/dify/v1_14/compiler_nodes.py:126-177`, `loom/runtimes/dify/v1_14/compiler_nodes.py:226-237`）。主运行时把所有有界 loop 输出为 `LoopType: Infinite`（`loom/runtimes/hiagent/v2_6/compiler_nodes.py:292-307`），parallel 只生成一个字段格式也与已验证 Code 结构不一致的 code 节点，分支仅作为元数据保存而不执行（`loom/runtimes/hiagent/v2_6/compiler_nodes.py:310-335`）；嵌套子节点根本不在顶层节点遍历中生成（`loom/runtimes/hiagent/v2_6/compiler_nodes.py:29-39`）。这还直接违反 Accepted ADR 对“loop max_iterations honored”和“parallel children expanded”的承诺（`docs/decisions/0024-hiagent-bundle-compilation.md:70-83`）。
- **Concrete failure scenario:** 一个 `max_iterations=3`、每轮调用有副作用 API 的流程，通过 Validator 并成功生成主运行时制品后会成为无限循环；同一 IR 在次运行时则只返回占位文本。另一个复杂条件无法匹配简单正则时，会按“query 非空”选支，可能绕过人工审核或风险分支。调用方只看到成功制品和有限的 policy warning，无法知道语义已改变。
- **Suggested fix:** 建立逐构造、逐运行时的 capability table；未实现或未经一致性验证的 IR 构造必须抛出结构化 `UnsupportedConstruct`，不得产出制品。优先实现 loop bound、parallel fan-out/merge、规则条件、Agent budget/schema/fallback、credential/retry/idempotency/model binding；每项必须有编译后实际运行断言。编译端点在矩阵全绿前返回 preview/unsafe 状态，并把任何降级作为阻断错误而非 warning。

### High

#### H-1 — Validator 没有执行其宣称的 DAG、数据流和类型流校验

- **Evidence:** 引用检查只验证 `${node...}` 的 node id 是否出现在全局 producer 集合，不验证 producer 是否 upstream、输出路径是否存在或作用域是否合法（`loom/validator/validate.py:58-71`, `loom/validator/validate.py:108-119`）。函数结尾明确把 type-flow 留作 deferred（`loom/validator/validate.py:99-105`）；独立 typecheck 库只在单元测试中使用。入口也不检查 edge 端点、重复 id、trigger/output 基数、可达性或 loop 外环。PRD 明确要求构建 DAG、拒绝环、验证类型和上游数据作用域（`docs/PRD.md:295-309`）。
- **Concrete failure scenario:** planner 生成 `answer` 引用不存在字段、边指向 ghost node、两个节点重名，或 A 引用其下游 B。`validate()` 返回空失败列表，之后编译器可能抛出 KeyError、生成缺边制品，或在运行时读取错误类型。当前针对性探针已复现这些输入全部通过。
- **Suggested fix:** 在 schema/Pydantic 后构建扁平化 graph symbol table；强制 node id 唯一、edge 端点存在、trigger/output 约束、可达性和 loop 外 DAG。为每种 node 声明输出端口/schema，在引用消费字段调用 typechecker，并按 topological/compound scope 验证 upstream、路径和类型。把 unknown schema version 转为 `ValidationFailure` 而非异常。

#### H-2 — “既有 IR 自然语言编辑”实际是从原始消息重新生成整份流程

- **Evidence:** `parse_edit_intent()` 结果只用于跳过澄清（`loom/service/routes/sessions.py:840-871`）。随后 planner 调用只接收用户消息、session 元数据、target、scope 和模型配置，没有传递 `latest_ir_json`、base hash 或解析后的 edit（`loom/service/routes/sessions.py:237-250`）。默认 planner 又只构造 `IntentRequest(intent=user_message, ...)`（`loom/service/app.py:45-70`）；虽然请求模型有 `extra_context`，retry loop 从未消费它（`loom/planner/types.py:35-40`, `loom/planner/retry.py:23-34`）。测试只断言 planner 被调用一次，并不验证旧 IR 或预期 diff（`tests/service/test_routes_sessions.py:303-323`）。
- **Concrete failure scenario:** 已有 20 节点流程的用户输入“retriever top_k 8”。planner 只看到这 3 个词，可能生成一个新的最小流程；成功返回后 `finish_turn_succeeded()` 直接用新 IR 覆盖 session 最新 IR，未提及的 19 个节点和治理配置消失。
- **Suggested fix:** 对已识别编辑实现确定性 patch service：输入 canonical current IR、current hash、typed edit intent，输出受限 patch 和 expected diff。复杂编辑若仍需规划器，必须传当前 canonical IR、base hash、允许变化字段和完整 Workflow Brief；应用前用 compare-and-swap 检查 revision，并拒绝超出声明范围的 diff。

#### H-3 — 强制安全策略未进入 Validator，credentialed HTTP 与 code 可绕过信任边界

- **Evidence:** policy 目前只检查 timeout/retry tightening、写 HTTP 幂等、code retry 幂等及 Agent budget/tool subset（`loom/validator/policy.py:25-100`）。credential registry 只有 `vault_path` 和 scopes，没有 auth scheme、allowed hosts、placement 或 TLS 要求（`loom/validator/registry.py:46-71`），与 Accepted ADR 的 binding metadata 决策相反（`docs/decisions/0003-credential-binding.md:6-20`）。已有安全报告把危险 code、code 网络访问、credentialed HTTP host allowlist、用户 URL 和 untrusted prompt delimiter 列为 Phase 1 必做项（`reports/security-review.md:74-81`），但它们仍只存在于手工脚本。
- **Concrete failure scenario:** planner 生成带 credential handle 的 `${input.url}` HTTP 节点，或在 code 节点中直接发起网络请求。它会通过 Validator；当运行时完成 credential binding 后，攻击者可把服务端凭据发往任意 host，或利用 code runtime 访问内网。检索到的恶意文本也未被强制包裹为不可信内容。
- **Suggested fix:** 把 security review 规则提升为 mandatory validator policy：credential 元数据包含 scheme/allowed_hosts/placement/TLS；URL 必须为允许的 HTTPS base，拒绝全 URL 用户变量、loopback/link-local/private network（除显式租户 allowlist）；code 使用 AST/import allowlist 并禁止网络/进程/文件系统，无法沙箱则拒绝 code；prompt 模板强制 trust-boundary delimiters。CI 必须直接跑这些规则。

#### H-4 — compile binding handle 可做目录穿越并读取绑定目录外的 YAML

- **Evidence:** API 的 `CompileRequest.binding` 只是无约束字符串（`loom/service/routes/sessions.py:62-65`）。编译时直接拼接 `binding_dir / f"{binding_handle}.hiagent.yaml"`，只检查 exists 后读取（`loom/service/routes/sessions.py:1034-1049`），没有 `resolve()` containment、slug 校验、symlink 防护或 catalog membership。现有遍历测试只覆盖 artifact 下载路径，不覆盖 binding（`tests/service/test_routes_sessions.py:390-406`）。
- **Concrete failure scenario:** 已认证用户传入 `../../shared/customer-prod`，服务会读取绑定目录外符合命名的 YAML；其中 workspace/model/dataset/tool id 随生成制品返回，导致本地配置泄漏或把流程绑定到另一客户资源。
- **Suggested fix:** 请求只接受枚举出的 binding handle；使用严格 slug regex，`candidate.resolve().relative_to(binding_dir.resolve())`，要求 regular file 且拒绝 symlink。store 层按 actor/tenant 授权 binding，编译日志只记录 opaque handle。

#### H-5 — canonical IR 与 canonical runtime AST 不能提供稳定漂移判断

- **Evidence:** IR canonicalizer 在 node dict 本身仍以 `Node` 为 parent 时先做 default stripping，因此 `RetrievalNode.top_k=5/rerank=false` 等规则不会命中（`loom/ir/canonicalize.py:18-55`, `loom/ir/canonicalize.py:65-82`）；nodes/edges 列表也从不排序或稳定化 id。针对性探针确认省略默认和显式默认 hash 不同、列表换序 hash 也不同。次运行时 AST 实际节点在 `workflow.graph.nodes/edges`，但 order-invariant path 写成 `workflow.nodes/edges`（`loom/runtimes/dify/v1_14/ast.py:24-35`, `loom/runtimes/dify/v1_14/ast.py:67-74`）。对应测试只覆盖 key sort、edge 默认和简化的错误 AST 形状（`tests/ir/test_canonicalize_ir.py:14-89`, `tests/dify/test_canonicalize_dify_ast.py:1-45`）。
- **Concrete failure scenario:** 运行时仅重排 graph 节点，或导入时显式补上默认 top_k，系统便报告 drift；反过来，registry/policy 真实变化又可能被不完整 diff 掩盖。团队无法依赖 hash 决定是否同步、回滚或阻断发布。
- **Suggested fix:** 在 typed IR 上规范化：先按 node `type` 选择规则，再 stripping defaults，稳定排序 nodes/edges/branch children，并定义 stable-id normalization。修正 runtime AST path，使用真实 compiler 输出做 reorder/default round-trip tests；canonical version 变更需迁移 registry baseline。

#### H-6 — RuntimeAdapter 不是实际编排边界，且 capability 信息为空

- **Evidence:** Accepted ADR 要求 session、planner、validator、deployer、conformance 和 CLI 全部经 adapter，禁止直接导入运行时模块（`docs/decisions/0015-runtime-adapter.md:32-43`）。当前 service 直接导入两个 concrete compiler（`loom/service/routes/sessions.py:30-32`），compile helper 分支调用具体函数（`loom/service/routes/sessions.py:1034-1050`），CLI 也对主运行时特殊处理。Protocol 的 `compile(ir)` 与主 adapter 的 `compile(ir, *, binding=...)` 不兼容（`loom/runtimes/base.py:44-62`, `loom/runtimes/hiagent/adapter.py:23-40`）；reverse/push/publish/export/run 大量 `NotImplementedError`，两个 `redlines()` 均返回空（`loom/runtimes/hiagent/adapter.py:42-79`, `loom/runtimes/dify/adapter.py:32-65`），planner 却声称两个运行时实现相同 IR contract（`loom/planner/client.py:55-56`）。
- **Concrete failure scenario:** planner 被告知 loop/parallel/Agent 可用，生成后 concrete compiler 静默降级。添加第三运行时或 binding context 时，service、CLI、planner 和测试必须分别修改，fake adapter 也无法覆盖真正路径。
- **Suggested fix:** 将 binding、mode、actor/tenant 等统一放入 `CompileContext`，使 protocol 签名真实可实现；通过 adapter registry 路由所有 orchestration。`redlines()` 从版本化 capability matrix 生成，并同时供 planner、validator 和 compiler 使用；未实现 lifecycle 方法应从公开能力/路由中移除或显式返回 unsupported 状态。

#### H-7 — reviewer-facing diff 忽略顶层治理字段、条件边和嵌套节点

- **Evidence:** `diff_ir()` 只建立顶层 node map 和 `(from,to)` edge set（`loom/diff/ir_diff.py:15-67`, `loom/diff/ir_diff.py:70-93`）。它不比较 metadata、registry_ref、policy、inputs/outputs，也丢弃 edge 的 `when`/`data`；loop/parallel 子节点不递归。测试仅覆盖节点增删、重命名、普通 config 和边端点（`tests/diff/test_ir_diff.py:1-42`）。
- **Concrete failure scenario:** 一次编辑删除 guardrail、替换 credential handle、扩大 Agent budget、把 edge 从 data 改成 control，或修改分支条件；API diff 可能返回 `total=0`。Reviewer 基于“无变更”批准后，安全与执行语义已经改变。
- **Suggested fix:** 对 canonical IR 做结构化全量 diff，明确分类 identity/registry/credential/policy/compliance/schema/control/data/nested-node 变化；edge identity 包含 condition/port/data。为高风险字段生成 hard-block review item，值做大小限制和敏感字段遮盖。

#### H-8 — IR 的 immutable registry pin 被忽略

- **Evidence:** Validator 无条件加载 `Registry.load("v1")`，不读取 `ir.registry_ref.registry_version`（`loom/validator/validate.py:73-100`）。loader 从可变的 `registry/v1/registry.json` 读取，并在非 SHA 时回退零值（`loom/validator/registry.py:53-76`）；当前 registry 本身就是 `sha:0000000`（`registry/v1/registry.json:1-3`）。PRD 要求所有引用按 IR 锁定的 immutable commit 解析（`docs/PRD.md:330-333`）。探针确认任意错误 pin 仍验证成功。
- **Concrete failure scenario:** 已发布 IR 锁定旧 registry，但后来 v1 删除或改变 handle；重新验证时会悄悄使用最新内容，旧 IR 的可复现性和 ACL 判断随时间变化。反之，完全不存在的 pin 也不会阻断。
- **Suggested fix:** 建立 content-addressed registry resolver，按完整 digest/commit 查找 immutable snapshot；验证 exact match、snapshot 存在、内容 hash 正确，并移除零值 sentinel。IR 所列 tools/datasets/credentials 也应与实际使用和 scope 做双向一致性检查。

#### H-9 — 规划器异常原文被输出到 stderr，绕过持久化脱敏

- **Evidence:** 失败归档对异常内容只存 hash，但此前先执行 `message = str(error)` 并完整 `print(... message=...)` 到 stderr（`loom/service/routes/sessions.py:531-550`）。现有测试只断言客户端、DB 和 archive 不包含 secret，没有捕获日志（`tests/service/test_routes_sessions.py:359-387`）。
- **Concrete failure scenario:** 上游 SDK 异常含请求 URL query token、响应体或 Authorization 片段。API 返回通用错误，但容器日志/集中日志收集完整 secret，访问面比原 SQLite 更广。
- **Suggested fix:** 日志只写 correlation id、异常类型和稳定错误码，不写 `str(error)`；需要调试内容时先经统一 sanitizer 并放入显式受控 debug channel。新增 `capsys`/日志 sink 测试，使用 URL token、header、私钥等代表性输入断言不泄漏。

#### H-10 — 同一 session 的并发 turn 可发生丢失更新

- **Evidence:** `create_turn()` 允许任意多个 `running` turn，未记录 base revision/hash（`loom/state/store.py:354-381`）。`finish_turn_succeeded()` 只按 turn id 更新 turn，再无条件覆盖 session 的 `latest_ir_json`（`loom/state/store.py:383-415`），没有 compare-and-swap 或 stale check。
- **Concrete failure scenario:** 两个请求同时从 IR v1 开始，A 修改 retry，B 修改 top_k；A 先写 v2，B 后写仍基于 v1 的结果，最终 retry 修改丢失且无冲突提示。两条 audit turn 看似都成功。
- **Suggested fix:** session 增加单调 revision；turn 保存 base revision/hash。完成时在同一事务执行 `UPDATE ... WHERE revision=base_revision`，失败返回 409 并要求 rebase；或者数据库约束每个 session 只有一个 active turn。并发测试需使用两个连接/barrier 复现交错。

#### H-11 — 已验证身份没有落实到 workflow registry 授权

- **Evidence:** registry list/get 路由显式丢弃 actor，返回全局数据；get 甚至用 row 的创建者身份读取 artifact（`loom/service/routes/registry.py:25-55`）。任意 actor 可调用 mark-deployed 修改任意 workflow，并向其 session archive 写事件（`loom/service/routes/registry.py:58-83`）。认证中间件已经用 cookie 注入 verified actor（`loom/service/app.py:157-181`），但 Accepted ADR 要求认证落地后审计每个 endpoint 的权限（`docs/decisions/0027-rbac-seams-mvp-no-auth.md:28-35`）。
- **Concrete failure scenario:** 多用户部署中，用户 A 枚举用户 B 的 workflow 元数据和 artifact 摘要，再把 B 的 workflow 标记为部署并写入 B 的审计链；没有角色或所有权检查阻止跨租户操作。
- **Suggested fix:** registry store 的 list/get/update 全部要求 actor/tenant filter；普通用户只能访问 own/tenant rows，部署操作需要显式 role/capability。数据库增加 tenant/owner 索引与约束，跨 actor API 测试覆盖 list/get/mark-deployed。更新 ADR 状态，明确当前 single-admin 限制或完成授权后再宣称 multi-user。

### Medium

#### M-1 — JSONL hash-chain append 有竞争条件且随事件数呈二次增长

- **Evidence:** 每次 append 都先完整读取并验证 session 全历史，用 `len(prior)+1` 和最后 hash 生成事件，再以普通 append 写文件（`loom/archive/jsonl.py:23-45`, `loom/archive/jsonl.py:47-65`）。没有线程/进程锁、原子 compare、fsync 或单写者机制。
- **Concrete failure scenario:** 两个并发请求都读取相同 tail，生成相同 seq/previous hash 后追加；下一次 `validate_chain()` 报 non-contiguous，整个 session 后续归档失败。长 session 每次都重读全量事件，累计成本 O(n²)。
- **Suggested fix:** 优先把 event chain 放入 SQLite 单事务并对 `(session_id, seq)` 唯一约束，JSONL 作为导出；若保留文件，使用 per-session OS lock、持久化 tail、atomic append/fsync 和启动恢复扫描。增加多进程并发与 chunk rotation 测试。

#### M-2 — 制品文件、状态库、workflow registry 和 archive 不是一个可恢复事务

- **Evidence:** compile 路由依次写临时文件、插入 artifact、rename、调用 private path rewrite、写 registry、最后 append archive（`loom/service/routes/sessions.py:384-443`）。任何步骤失败都没有补偿或 recovery marker。
- **Concrete failure scenario:** artifact DB 插入后 rename 失败，留下指向不存在路径的行；registry 写成功后 archive append 失败，则业务响应 500，但 workflow 已可见且无完整审计事件。重试又生成新的 workflow/artifact。
- **Suggested fix:** 引入 compile job/outbox：先在单一 DB 事务记录 pending artifact/registry/event，再原子 rename，最后标记 committed；后台恢复 pending/清理 orphan。公开 store API 替代 private path rewrite，并以 idempotency key 防止重复提交。用 fault injection 覆盖每个步骤失败。

#### M-3 — secret detection 范围过窄，普通 turn 会保存未识别的原始消息

- **Evidence:** detector 只有 bearer、authorization、两类特定 key 和 `api_key=` 五种正则（`loom/fde_session/redaction.py:11-27`）。未命中时，普通 turn 把 `body.user_message` 原文写入 SQLite（`loom/service/routes/sessions.py:209-215`），archive 只保存消息 hash，二者策略不一致。
- **Concrete failure scenario:** 用户粘贴云访问密钥、代码托管 token、PEM 私钥、数据库 DSN、cookie 或短密码，detector 不命中，原文长期保存在 turn 表并可能继续进入规划器。
- **Suggested fix:** 使用可配置 secret scanner 覆盖高熵 token、私钥块、DSN、常见 provider 格式和 key/value 语境；疑似 secret 时不持久化原文，只保存 redaction reason/hash，并引导用户使用 credential handle。定义 DB retention/encryption 与删除语义，增加代表性 corpus 测试。

#### M-4 — planner retry 只处理 JSON/Validator 失败，不处理传输异常和未知 schema version

- **Evidence:** `client.call()` 在 try 块外，网络、限流和上游异常会直接退出 retry loop（`loom/planner/retry.py:23-40`）。`validate()` 在收集 failure 前调用 `load_schema_for_doc()`，未知 `ir_version` 会抛 `ValueError` 而不是返回 schema failure（`loom/validator/validate.py:39-46`, `loom/ir/schema.py:20-31`）。`extra_context` 同样未传入 client（`loom/planner/types.py:35-40`, `loom/planner/retry.py:28-34`）。
- **Concrete failure scenario:** 第一次调用短暂 429/timeout，尽管请求配置 3 次重试，turn 立即失败；若返回合法 JSON 但 `ir_version=9`, retry loop 也直接异常，无法把错误反馈给下一次规划。
- **Suggested fix:** 把可重试 transport/status 异常纳入指数退避和总时限，非重试错误映射稳定 failure bucket；unknown schema version 转成 validator failure。把 `extra_context` 明确定义为结构化 Workflow/Edit Context 并透传，或者删除该误导字段。

#### M-5 — 构建出的 wheel 不包含运行必需的 schema 与 registry

- **Evidence:** wheel 配置只打包 `loom`（`pyproject.toml:33-34`），schema loader 从 package 目录向上寻找顶层 `schemas/`（`loom/ir/schema.py:11-26`），registry loader同样依赖源码树顶层目录（`loom/validator/registry.py:53-57`）。Docker 通过额外 `COPY schemas/` 和 `COPY registry/` 掩盖该问题（`Dockerfile:18-22`）。
- **Concrete failure scenario:** 用户从 wheel 安装到干净虚拟环境，在非源码 checkout 下运行 planner/validator，首次加载 schema 或 registry 时 `FileNotFoundError`；源码内测试均通过，发布制品却不可用。
- **Suggested fix:** 把 schema、registry snapshot 和 planner resources 作为 package data，使用 `importlib.resources` 加载；或明确拆分可版本化资源包。CI 构建 wheel 后在空目录/新 venv 安装并执行 validate/compile smoke。

#### M-6 — “固定版本运行时”文件是占位模板，无法支撑可重复一致性验证

- **Evidence:** 次运行时 compose 使用 `<digest>` 并以省略号代替正式服务定义（`docker/dify-pinned/docker-compose.yml:8-22`）；主运行时 compose 仍是 `<hiagent-image>:2.6@sha256:DIGEST`（`docker/hiagent-pinned/docker-compose.yml:9`）。ADR 要求锁定版本并在每次升级重跑一致性矩阵（`docs/decisions/0002-runtime-versions.md:19-48`）。
- **Concrete failure scenario:** 新开发者或 CI 无法按仓库文件启动参考运行时，编译器对真实 import schema 的偏差只能靠样本猜测；同一 tag 上游变动也无法被 digest 固定。
- **Suggested fix:** 提供可解析、可启动的完整 compose 和真实 image digest，环境变量只承载 secret；增加 healthcheck、seed/import/run/export 脚本和离线 fixture。若主运行时镜像不可分发，记录外部受控 test harness 与证据时间戳，而不是提交不可执行占位文件。

#### M-7 — 状态机定义与持久化路径脱节

- **Evidence:** 独立状态机定义存在，但 `create_turn()` 只插入 running turn，不迁移 session；failure 也只更新 turn（`loom/state/store.py:354-381`, `loom/state/store.py:500-522`）。compile 仅拒绝 `state == init`，可在另一个新 turn 正在运行时编译旧 `latest_ir_json`（`loom/service/routes/sessions.py:361-376`）。
- **Concrete failure scenario:** UI 显示 session 仍为 validated，同时后台有 running turn；用户点击 compile 得到旧 IR 制品，新 turn 随后成功覆盖 IR。registry/审计中出现“最新流程”概念不一致。
- **Suggested fix:** 将状态转换放入 store 的事务 API并强制 `loom/state/sm.py`；明确 planning 时是否允许编译旧 revision，若允许则 artifact/registry 显式记录 compiled revision/hash。为所有 transition、并发 turn 和 stale compile 建状态表测试。

#### M-8 — 依赖与容器构建不可复现

- **Evidence:** Python 依赖均为宽版本范围，没有 lock/hash（`pyproject.toml:10-20`）；Docker 在构建时从可变第三方镜像源解析最新匹配版本（`Dockerfile:25-29`）。这与确定性编译、固定运行时和可审计重建目标冲突。
- **Concrete failure scenario:** 同一 commit 两周后构建解析到新的 validator、HTTP client 或 YAML 版本，测试/序列化行为变化；镜像源异常或被替换也会影响供应链来源，无法用源码 commit 复现制品。
- **Suggested fix:** 生成 reviewed lockfile 与 hashes，CI/Docker 用 frozen install；基础镜像和前端/运行时镜像用 digest；镜像源改为可配置且保留官方 fallback/签名策略。记录 SBOM 和构建 provenance。

### Low

#### L-1 — CLI 的 compile/validate 契约与 README 不一致

- **Evidence:** README 声称 CLI 和 web 使用相同 Validator/Compiler（`README.md:58-62`），但 compile CLI 只做 Pydantic parse 后直接进入具体 compiler，没有调用完整 `loom.validator.validate`（`loom/cli/commands/compile.py:48-111`）。因此 CLI 与 web 的接受集合不同。
- **Concrete failure scenario:** 一个违反 registry scope 或 policy 的 IR 在 `loom validate` 失败，但 `loom compile` 仍输出制品，自动化脚本误把“编译成功”视为可部署。
- **Suggested fix:** compile 默认先跑统一 Validator，并要求显式 `--unsafe-skip-validation` 才绕过；CLI、service 都通过同一 application service/adapter。加 contract test 对同一 fixture 比较两入口结果。

#### L-2 — Phase 0 gate 提示引用仓库中不存在的脚本

- **Evidence:** `make phase0-gate` 提示运行 `scripts/round_trip_proof.py` 与 `scripts/reverse_compile_spike.py`（`Makefile:17-20`），当前 scripts 清单没有这两个文件；runtime AST 文档也要求重跑其中之一（`loom/runtimes/dify/v1_14/ast.py:5-10`）。
- **Concrete failure scenario:** 维护者按门禁说明准备证据时命令直接失败，只能手工判断 drift/reverse 能力，报告无法复现。
- **Suggested fix:** 恢复可运行脚本和 fixture，或把提示改为实际 test target；门禁命令应以非零状态表示缺失证据，而不是只 echo。

#### L-3 — 本地环境脚本默认创建已知口令并放宽 cookie

- **Evidence:** 完整模式默认账号口令固定为 `admin / Admin123456!`，文档示例也直接展示（`scripts/setup-env.sh:10-22`, `scripts/setup-env.sh:28-35`）；非 fernet-only 模式默认将 insecure cookie 设为 true（`scripts/setup-env.sh:55-57`）。
- **Concrete failure scenario:** 操作者误把完整模式生成的 `.env` 用于可被局域网访问的服务，形成可预测凭据和明文 HTTP session cookie。虽然注释定位为本地测试，这类配置很容易随 compose/部署复制。
- **Suggested fix:** 无显式 `PASSWORD` 时生成随机一次性密码或拒绝启动；insecure cookie 必须由显式 `--local-http` 开关启用，并在非 loopback bind/prod 环境 fail closed。部署文档只展示安全路径。

## Test coverage gaps

| Area | Current signal | Missing coverage / recommended gate |
|---|---|---|
| Validator graph semantics | schema/ref/registry/policy happy paths；typecheck 库有孤立单测 | 重复 id、ghost edge、trigger/output 基数、可达性、loop 外 cycle、upstream scope、输出字段路径、edge data/type、nested scope、错误 registry pin；每例必须在入口 `validate()` 失败 |
| Runtime compiler semantics | 大量测试只断言节点 type、字段存在或 YAML 可解析；主运行时测试明确接受 `Infinite` | 每个 IR construct 的输入 → 实际 runtime 输出断言；有界 loop、parallel 三种 merge、condition truth table、Agent budget/fallback/schema、HTTP retry/idempotency/credential、LLM model/schema；unsupported 必须 fail closed |
| Conformance | `loom/conformance/runner.py:22-38` 只有 dataclass；matrix smoke 只实例化 factory（`tests/conformance/test_runner_smoke.py:5-27`） | 实现 compile → import/push → run → assert runner；固定本地 runtime 做 PR gate，受控 live runtime 做周期 gate；保存 runtime version/digest、artifact hash 和结果 |
| Existing-IR edit | 只断言 post-IR edit 调用了 planner | 断言 planner/patcher收到 current IR + base hash；只产生 expected canonical diff；未提及节点保持不变；stale base 409；recognized/unrecognized edit 分流 |
| Canonicalization/drift | 简化结构、key order、单一默认值 | 真实 compiler AST、node/edge reorder、explicit/implicit defaults、stable id、nested branches、registry/policy changes、canonical version migration |
| Review diff | 顶层 node/edge 基础变化 | metadata/registry/policy/credentials/I/O schema、edge when/data/port、nested loop/parallel、risk classification、secret redaction、大字段截断 |
| Security | 制品纯度与部分 secret DB/archive 测试 | binding traversal/symlink、credentialed SSRF、code network/import、log sink secret、cross-actor registry、provider base URL scheme/host、DLP corpus |
| Concurrency/recovery | 单请求 store/archive happy path | concurrent turns、archive append/rotation、CAS/rebase、compile 每一步 fault injection、process restart recovery、duplicate retry idempotency |
| Packaging/build | 源码 checkout 与 Docker copy 可运行 | build wheel → clean install → validate/compile；frozen dependency audit；完整 pinned compose startup/health/import/export |
| CLI/service parity | 各入口单独 smoke | 同一 IR 在 validate/compile/service 的接受与错误分类一致；adapter registry fake 覆盖所有 orchestration |

## ADR/PRD consistency notes

| Contract | Implementation status | Evidence / impact |
|---|---|---|
| PRD: Validator 构建 DAG、检查类型/引用 | **Contradicted** | `loom/validator/validate.py:58-105` 只做全局 node id 引用和显式 deferred type-flow；Validator-passing 不代表语义有效 |
| PRD: 自然语言编辑确定性更新当前 IR | **Contradicted** | `loom/service/routes/sessions.py:237-250`, `loom/service/app.py:45-70` 未传 current IR/edit context，实际是重建 |
| PRD: 每个 runtime 一致性 100%，红格阻断发布 | **Aspirational / not executable** | `loom/conformance/runner.py:1-38` 没有 runner；`reports/conformance-baseline.md:3-29` 全部 deferred；编译器仍静默降级 |
| ADR 0015: 全部 orchestration 经统一 adapter | **Contradicted** | service/CLI 直接导入 concrete compiler；主 adapter compile 签名与 protocol 不一致；lifecycle 未实现 |
| ADR 0024: 一次生成、无占位；loop bound/parallel expansion | **Contradicted** | `loom/runtimes/hiagent/v2_6/compiler_nodes.py:292-335` 输出 Infinite loop 和 metadata parallel code |
| ADR 0003: credential binding metadata 与平台 slot | **Contradicted** | registry 存 `vault_path` 而非 scheme/allowed host/TLS；两个 compiler 不完整消费 HTTP credential |
| ADR 0004: recognized forward constructs 可 reverse round-trip | **Not implemented** | 两个 adapter 的 reverse 均为 `NotImplementedError`（`loom/runtimes/hiagent/adapter.py:42-50`, `loom/runtimes/dify/adapter.py:32-35`） |
| ADR 0005: Agent/LLM 默认值与副作用治理 | **Partial** | validator 只在 workflow 明确预算时限制；编译器不保证 Agent budget/fallback/output schema 和工具调用审计（`docs/decisions/0005-agent-governance.md:6-40`） |
| ADR 0001 + ADR 0023: SOW → Persona Brief → Workflow Brief → Planner | **Partial / bypassed in web path** | 默认 planner 只用 message/scope/target（`loom/service/app.py:45-70`）；session 未解析 SOW/persona，Accepted ADR 仍写作已决定流程（`docs/decisions/0001-sow-requirements-intake.md:6-25`, `docs/decisions/0023-persona-brief.md:6-28`） |
| PRD: Git-backed single source of truth、runtime draft/hash/review summary | **Aspirational** | 当前 source of truth 是 SQLite latest IR；registry row 只有 artifact/IR signature 和部署字段（`loom/registry/models.py:11-33`），没有 IR commit、runtime canonical AST、persona/workflow brief、review summary |
| ADR 0027: authentication lands 后逐端点授权 | **Partially superseded, incomplete** | cookie authentication 已落地，但 registry actor 被忽略；应更新 ADR 状态并补 capability policy |

已实现且可以作为后续修复基础的部分包括：版本化 Pydantic/JSON Schema IR、结构化 planner JSON 与 validator-feedback retry、确定性 clarification draft、scope-aware registry handle lookup、SQLite actor-filtered session/turn/artifact、加密的会话模型凭据、hash-chained archive、两类可下载制品以及较完整的单元/路由 happy-path suite。问题不在于这些组件不存在，而在于它们还没有形成 PRD 所承诺的闭环证据。

## Open questions

1. 当前发布边界是什么：只允许“生成供工程师手工修复的 preview 制品”，还是已经允许把 compile 成功解释为可导入/可运行？建议在 capability/conformance 门禁完成前选择前者。
2. 每个固定 runtime 真正支持的 IR 子集是什么？如果近期无法实现 loop/parallel/Agent 等语义，是否愿意从可生成 schema/Planner capability 中暂时移除，而不是继续占位？
3. 生产部署究竟是 single-admin/single-tenant，还是 ADR 所述 multi-user？若是前者，应在 API/README 明示；若是后者，registry、binding、archive 和部署操作的 tenant/role model 必须先完成。
4. Git-backed IR 仍是正式 source of truth 吗？若是，何时由 SQLite session 产出 versioned commit，并如何把 registry row 绑定到 commit/revision；若否，应更新 PRD 与 drift contract。
5. session 删除后的 artifact、archive 和 registry retention 是“依法保留”“手工清理”还是必须级联删除？需要把用户可见删除语义、审计保留和 right-to-erasure 分开定义。
6. 用户消息允许以明文长期存在 SQLite 吗？如果需要用于复盘，应定义加密、retention、访问审计和 DLP；如果不需要，应只保存 redacted snapshot/hash。
7. binding 文件的信任边界和管理者是谁？是否应进入 tenant-scoped registry，并由服务只接收 opaque handle，而不允许任意本地路径派生？
8. Accepted ADR 中哪些是目标状态、哪些是当前强制约束？建议引入 `Proposed / Accepted-not-implemented / Enforced / Superseded` 或对应 implementation checklist，避免代码、测试和发布声明引用不同现实。
