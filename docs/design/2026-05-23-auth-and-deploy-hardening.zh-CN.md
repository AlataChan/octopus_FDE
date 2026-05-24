# 鉴权 + 部署收尾设计（A + C 最小预留）

> 状态：草案 v2（已整合 Codex Plan Review，overall=7.75 过线）
>
> v2 修订摘要（来自 Codex 5 项 required）：
> - **集中式鉴权**：FastAPI middleware + 显式 allowlist，取代分散的 `Depends(get_actor)`
> - **CSRF 防护**：所有 mutating 请求加 `Origin` / `Referer` 严格校验；不引入 token
> - **可信代理模型**：只有显式 `LOOM_TRUSTED_PROXY=true` 时才采信 `X-Forwarded-For`
> - **CORS 收紧**：禁用 `allow_origins=["*"]`；如开 CORS 必须 `allow_credentials=true` 配合显式 origin 白名单
> - **uvicorn 单 worker 强约束**：进程内 session store 要求 `--workers 1`，启动时校验并文档化
> - **密码哈希用 stdlib `hashlib.scrypt`** 取代 bcrypt，避免新增依赖
> - **session token 存哈希不存明文**：内存 dict 的 key 是 `sha256(token)`
> - **archive 标识符用 HMAC 而非裸 sha256**：用 `LOOM_FERNET_KEY` 派生 HMAC 密钥，避免归档跨机器后被字典枚举
> - **archive 注入集中化**：archive writer wrapper 统一 inject `instance_id` 与 HMAC 派生字段
> - **前端 React Router 显式注册**（非 file-router）
> 作者：Claude（架构师角色）
> 日期：2026-05-23
> 关联代码：`loom/service/{deps.py,app.py}`、`loom/service/routes/`、`loom/state/store.py`、`loom/archive/`、`loom/cli/`、`web/src/`、`Dockerfile`、`docker-compose.yml`

## 1. 背景

当前部署假设 = "内网信任 + 单组织"：`get_actor()` 仅读 `X-Actor-Id` 头，无验证；任何能访问 8000 端口的人都能伪造 actor 越权读写 session。注释里写得很坦白：`MVP attribution seam; this is not authentication`。

**最终形态目标（用户拍板）**：一个 Docker = 一个用户。鉴权简单、部署简单、不引入 IdP 依赖。

本设计把 3 件事打包到一个 PR：
1. **Docker 收尾**：8000 → 18080；加 healthcheck
2. **真鉴权 A（本地用户名+密码）**：env 配账号、登录页、cookie session、替换 `get_actor()`
3. **多租户最小预留**：`LOOM_INSTANCE_ID` env + archive payload 加 `instance_id` 字段；**不动 DB 列、不动 Actor 模型**

## 2. 目标与非目标

**目标**
- 部署到公网（或不可信内网）可用：所有 `/v1/*` 必须先登录
- "一个 Docker 一个用户"：账户由 env 配置，无注册流程
- CLI 路径**继续 headless 可用**（CLI 直连本地 DB，不走鉴权）
- 多实例部署时审计可关联（`instance_id`）

**非目标**
- 不做 OIDC / SSO / IdP 集成
- 不做多用户管理（注册、找回密码、权限分级）
- 不引入 DB 用户表 / role 表 / tenant 表
- 不重构 30 模板 / 澄清 / IR / 编译器
- 不改 CLI 现有行为（CLI 仍直读 DB，actor 由 `--actor` 显式声明）

## 3. 端口与 Healthcheck

### 3.1 端口 8000 → 18080
- `Dockerfile` 的 `EXPOSE` 改 18080
- `CMD` 的 `--port` 改 18080
- `docker-compose.yml` 的 `ports:` 改 `"18080:18080"`
- `README.md` 与 `env.example`、`docs/` 内出现的 `8000` 全部替换为 `18080`
- 本地 dev 路径（`make serve`）默认仍可保留 8000（仅本地开发，不暴露），但建议同步改 18080 减少认知负担

### 3.2 Healthcheck（compose 层）
```yaml
services:
  fde:
    # ...
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:18080/v1/health', timeout=2).status == 200 else 1)"]
      interval: 30s
      timeout: 5s
      retries: 3
      start_period: 20s
```
理由：用 python 自带 stdlib，不依赖 image 里有 `curl` / `wget`（python:3.11-slim 默认没装）。`/v1/health` 已存在（`loom/service/routes/health.py`）。

## 4. 鉴权 A：本地用户名 + 密码

### 4.1 配置（env 注入）
| env var | 必填？ | 说明 |
|---|---|---|
| `LOOM_AUTH_USERNAME` | 是（prod）；dev 可缺 | 登录用户名 |
| `LOOM_AUTH_PASSWORD_HASH` | 是（prod）；dev 可缺 | scrypt 哈希串，格式 `scrypt$N$r$p$<salt_b64>$<hash_b64>`；N≥2^14, r=8, p=1 |
| `LOOM_AUTH_SESSION_TTL_HOURS` | 否 | 默认 24h |
| `LOOM_AUTH_DISABLED` | 否 | 仅 dev 用，等价于"允许 single-user 直通"；prod 启动时校验为 false |
| `LOOM_TRUSTED_PROXY` | 否 | 默认 false；为 true 时才采信 `X-Forwarded-For` 第一段，否则用 `request.client.host` |
| `LOOM_CORS_ALLOW_ORIGINS` | 否 | 默认空（不开 CORS）；逗号分隔显式 origin，禁止 `*` |

**未配置时行为**：
- `APP_ENV=prod`：启动失败，错误信息明确告诉部署方需要配置
- `APP_ENV=dev`：自动 disabled + 警告日志（与现状 fernet key 等价处理）

**密码哈希选 stdlib `hashlib.scrypt`** 而不是 bcrypt，理由：
- pyproject 现有 deps 不含 bcrypt；引新 deps 是要避免的
- `hashlib.scrypt` 是 Python 3.11+ 标准库；密码哈希学术界推荐参数（N=2^14, r=8, p=1）单次校验 ~100ms
- 抗 GPU / ASIC 攻击优于 bcrypt（memory-hard）

哈希生成（README 给一行）：
```bash
python -c "
import os, hashlib, base64
pw = input('Password: ').encode()
salt = os.urandom(16)
h = hashlib.scrypt(pw, salt=salt, n=2**14, r=8, p=1, dklen=32, maxmem=128*1024*1024)
print(f'scrypt\$16384\$8\$1\${base64.b64encode(salt).decode()}\${base64.b64encode(h).decode()}')
"
```

启动时校验 hash 串格式 + 参数下限（N ≥ 2^14），不符则启动失败。

### 4.2 路由
- `POST /v1/auth/login`：body `{username, password}` → 校验 bcrypt → set HTTP-only Secure SameSite=Lax cookie `fde_session=<token>` → 200
- `POST /v1/auth/logout`：清 cookie → 200
- `GET /v1/auth/me`：返当前 user `{username, expires_at}`，未登录则 401
- 失败：401 + `{"error": "invalid_credentials"}`；rate limit 简单做（同 IP 失败 5 次/分钟 → 锁 60s，IP 取自 `X-Forwarded-For` 兜底 `client.host`）

### 4.3 Session token 实现
- 客户端 cookie 值 `token = secrets.token_urlsafe(32)`（明文，仅在客户端）
- 服务端 **不存 token 明文**：内存 dict 的 key = `hashlib.sha256(token.encode()).hexdigest()`
- 进程内存 `dict[token_sha256, SessionInfo]`（**不入 SQLite**，重启即失效，简单可控；适合"一 docker 一用户"场景）
- `SessionInfo = {username, created_at, expires_at, last_seen_at}`
- TTL 滑动：每次请求 last_seen_at 刷新；超过 `LOOM_AUTH_SESSION_TTL_HOURS` 自动失效
- 清理：FastAPI background task（lifespan 启动一个 asyncio task）每 5 分钟扫一次过期 token

**单 worker 约束**：进程内存 session 不能跨 worker 共享。`Dockerfile` 的 `CMD` 必须固定 `--workers 1`，且 `Settings.from_env()` 启动时打印告警："本架构要求单 worker；多 worker 部署需自行实现 Redis/外部 session 后端"。

> 不存 DB 的理由：单用户场景重启时让他重登一次完全可接受；不入持久存储就没有泄漏面。

### 4.4 集中式鉴权 middleware（替代分散 `Depends`）

Codex 指出 per-route `Depends(get_actor)` 容易在新增路由时漏挂。改成 FastAPI `@app.middleware("http")` 集中拦截：

```python
EXEMPT_PATHS = {"/v1/health", "/v1/auth/login", "/v1/auth/logout"}
EXEMPT_PREFIXES = ("/", "/assets/", "/favicon")  # 前端静态资源

@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    path = request.url.path
    # 1. 豁免静态资源 + auth/health 三条
    if path in EXEMPT_PATHS or _is_static(path):
        return await call_next(request)
    # 2. dev disabled 兜底
    if settings.auth_disabled:
        request.state.actor = Actor(id=request.headers.get("X-Actor-Id") or "single-user", role="fde")
        return await call_next(request)
    # 3. 仅 mutating 方法做 CSRF 校验
    if request.method in {"POST", "PATCH", "PUT", "DELETE"}:
        if not _origin_ok(request, settings):
            return JSONResponse({"error": "csrf_origin_mismatch"}, status_code=403)
    # 4. 取 cookie → 查 store（用 sha256(token) 当 key）
    token = request.cookies.get("fde_session")
    info = request.app.state.auth_store.validate(token) if token else None
    if info is None:
        return JSONResponse({"error": "not_authenticated"}, status_code=401)
    info.last_seen_at = now()
    request.state.actor = Actor(id=info.username, role="fde")
    return await call_next(request)
```

`get_actor()` 改为薄壳：从 `request.state.actor` 取已校验对象，不再做鉴权逻辑。

**CSRF：Origin/Referer 校验（不引入 token）**：
```python
def _origin_ok(request, settings) -> bool:
    # 允许同源（Host 与 Origin 主机一致）；显式 LOOM_CORS_ALLOW_ORIGINS 白名单
    origin = request.headers.get("Origin") or request.headers.get("Referer")
    if not origin:
        # 老式表单 POST 可能没有 Origin；如允许内网工具，可放行；建议默认拒绝
        return False
    parsed = urlparse(origin)
    if parsed.hostname == request.url.hostname:
        return True
    return parsed.hostname in settings.cors_allow_origin_hosts
```

> CLI 路径不走 HTTP，仍读 DB 直接构造 `Actor`，不受影响。

### 4.5 路由豁免（被 middleware allowlist 统一管）
- `/v1/health`、`/v1/auth/login`、`/v1/auth/logout`：免鉴权
- `/v1/auth/me`：需鉴权但失败返 401 不抛 500
- 其它 `/v1/*`：middleware 强制鉴权（无需各路由再写 `Depends`）
- 静态前端资源 `/`、`/assets/*`、`/favicon.ico`：免鉴权（前端 SPA 自己路由到 login）
- CORS：默认不启用；如 `LOOM_CORS_ALLOW_ORIGINS` 显式设置则启用 `CORSMiddleware(allow_origins=[...]，allow_credentials=True)`，**禁止 `*`**（启动校验）

### 4.6 前端（React Router 显式注册）
现状：`web/src/App.tsx` 用 `react-router-dom` 的 `<Routes>` 手动列路由（不是 file-based router）。新加：
- `web/src/pages/LoginPage.tsx`：登录页（username + password 输入 + submit → `POST /v1/auth/login`）
- `web/src/hooks/useAuth.ts`：拉 `/v1/auth/me`；未登录返 401 → 跳 `/login`
- `web/src/components/RequireAuth.tsx`：包裹路由组件；未登录跳 `/login`
- `web/src/lib/api.ts`：所有请求带 `credentials: "include"` 让 cookie 自动带；遇 401 自动跳 `/login`
- `App.tsx`：新增 `<Route element={<LoginPage />} path="/login" />`，把现有 sessions 路由用 `<RequireAuth>` 包裹
- `TopBar`：右上加用户名 + 登出按钮（调用 `/v1/auth/logout`）

i18n：`zh.json` / `en.json` 加 `auth.title / auth.username / auth.password / auth.submit / auth.logout / auth.error.invalid_credentials / auth.error.rate_limited` 等 key。

### 4.7 安全细节
- Cookie：`HttpOnly` + `Secure`（prod 强制；dev 可豁免）+ `SameSite=Lax` + `Path=/v1`
- 启动时校验 `LOOM_AUTH_PASSWORD_HASH` 合法 scrypt 串且 N ≥ 2^14，否则启动失败
- **登录响应时间常量化**：失败路径也必跑一次"dummy scrypt 校验"（用固定占位 hash）；无论 username 是否存在、密码是否正确，scrypt 操作恒发生一次；总耗时差 < 50ms
- 不输出原密码到日志 / archive
- **archive 标识符用 HMAC**：`hmac.new(instance_secret, username.encode(), 'sha256').hexdigest()` 取代裸 sha256；`instance_secret` 由 `LOOM_FERNET_KEY` 派生（HKDF）；这样归档跨机器后无法被字典枚举（因为密钥不出 instance）
- CSRF：**Origin/Referer 严格校验**（见 §4.4），不引入显式 token（"一 docker 一用户" 场景）
- 密码字段在 web 用 `<input type="password" autoComplete="current-password">`
- **代理头信任**：仅 `LOOM_TRUSTED_PROXY=true` 时采信 `X-Forwarded-For` 第一段；否则用 `request.client.host`（默认更安全）
- **rate limit 实现**：以 `client_ip_hmac` 为 key 计数；进程内存 dict（单 worker 假设）

### 4.8 审计事件扩展
`ArchiveEventType` 加：
- `"auth.login_succeeded"` — payload `{username_hmac, instance_id, client_ip_hmac}`
- `"auth.login_failed"` — payload `{username_hmac, instance_id, client_ip_hmac, reason}`（reason ∈ `"bad_credentials" | "rate_limited"`）
- `"auth.logout"` — payload `{username_hmac, instance_id}`
- `"auth.session_expired"` — payload `{username_hmac, instance_id, ttl_hours}`

> `*_hmac` 字段一律走 §4.7 提到的"instance_secret HMAC"，不写 sha256 也不写明文。

### 4.9 archive 注入集中化
新增 `loom/archive/writer.py`（如已有则补 wrapper）暴露 `append_event(event_type, payload)` 高阶函数：内部 deep-merge `{"instance_id": settings.instance_id}` 到 payload，再调底层 `ArchiveWriter.append`。所有调用方（sessions.py 路由 / clarify_engine / 新 auth 模块）改走这个 wrapper，禁止散落 `instance_id` 注入。

## 5. 多租户最小预留（C 路径的"等将来再说"标签）

### 5.1 `LOOM_INSTANCE_ID` env
- 默认值：取 `socket.gethostname()`（Docker 里就是容器 hostname）
- 显式注入：用户可在 compose 设 `LOOM_INSTANCE_ID=client-a-prod-tcm`
- 落地到 `Settings.instance_id: str`

### 5.2 Archive payload 加 `instance_id`
- `ArchiveEvent.payload` 已是 `dict`，在写事件时统一 inject `instance_id`
- 用 archive writer 的 wrapper 函数 `_append_event(event_type, payload)` 自动把 `instance_id` 合并进 payload

### 5.3 不做什么（重要）
- **不加 DB 列**：sessions / turns / artifacts 都不加 `instance_id`
- **不改 Actor 模型**
- **不改 store API 签名**
- 将来要做"一 DB 多实例聚合"或"真正多租户"，再加 DB 列（届时按 PRAGMA-probe 风格迁移）

### 5.4 CLI 输出可选
`loom session show-turns --json` / `loom session brief` 顶层 JSON 加 `"instance_id": "..."`（不破坏 `cli_schema_version: "1"`，是新增字段）。`loom brief` 也加。

## 6. 数据契约变更

| 维度 | 变更 |
|---|---|
| DB schema | **无新列** |
| `ArchiveEventType` | 加 4 条 auth.* 事件 |
| HTTP 路由 | 新增 `/v1/auth/{login,logout,me}` |
| `Actor` 模型 | 不变 |
| `Settings` | 加 `auth_username / auth_password_hash / auth_session_ttl_hours / auth_disabled / instance_id` |
| Cookie | 新增 `fde_session` |

## 7. 工期与拆分

按 Codex 颗粒：
1. backend: `Settings` 加新字段 + 启动校验 + `AuthSessionStore`（内存）+ 单测
2. backend: `/v1/auth/login|logout|me` 路由 + `get_actor()` 改造 + 路由豁免 + archive 事件扩展 + 单测
3. frontend: `useAuth` hook + `LoginPage` + 401 拦截器 + 顶栏登出 + i18n + 单测
4. deploy: Dockerfile 端口 18080 + compose healthcheck + README/env.example 全量替换 + 文档 bcrypt 生成示例
5. instance: `LOOM_INSTANCE_ID` env + archive wrapper 注入 + CLI 顶层 JSON 加字段 + 单测

合 1 PR 5 commits。

## 8. 验收标准

1. **未登录访问** `/v1/sessions` 等任意 `/v1/*` → 401
2. **正确登录** → set-cookie 成功，`/v1/sessions` 200
3. **错误密码** 3 次 → 第 4 次仍 401，不会泄漏"用户存在但密码错"vs"用户不存在"信息（响应时间常量化）
4. **同 IP 失败 5 次/分钟** → 第 6 次返 429 锁 60s
5. **cookie 过期** → 自动 401，前端跳 `/login`
6. **logout** → cookie 清，再访问 `/v1/sessions` → 401
7. **`/v1/health` 免鉴权** → 公网可见
8. **`APP_ENV=prod` 缺 `LOOM_AUTH_PASSWORD_HASH`** → 启动失败 + 明确错误信息
9. **bcrypt cost < 12** → 启动失败
10. **Docker port 18080** → `curl localhost:18080/v1/health` 200
11. **Healthcheck** → `docker compose ps` 显示 `healthy`
12. **CLI** → `loom session show-turns` 顶层 JSON 含 `instance_id` 字段
13. **archive** → `auth.login_succeeded` 事件落盘，payload 含 `username_sha256` + `instance_id`，**不含明文 username/password/ip**
14. `pytest -q` / `npm --prefix web test` / `mypy loom` 全绿

## 9. 风险

| 风险 | 缓解 |
|---|---|
| 内存 session store 重启即失效 | 文档明说"单用户场景重启可重登"；TTL 默认 24h；不入持久存储就没有泄漏面 |
| 改端口导致旧文档 / 团队习惯断裂 | README 显眼位置写"自本次起端口为 18080，原 8000 弃用"；env.example 同步 |
| scrypt 内存占用 128MB | 单 worker 单次 ~100ms / ~128MB；docker compose 默认无内存限制；如部署侧设过严内存可降 N=2^13（启动校验放宽到 N≥2^13 并提示降级影响） |
| uvicorn 多 worker 导致 session 失效 | Dockerfile 固定 `--workers 1`；启动时若检测到 `WEB_CONCURRENCY>1` 抛错 |
| 前端 CLI 共用 actor_id 语义 | CLI 仍走 `--actor` 显式声明，与 web 的 cookie session 独立；README 文档化两条路径不冲突 |
| HMAC instance_secret 派生与 fernet 共密钥 | 用 HKDF 派生子密钥（info=`"loom-archive-hmac-v1"`）；fernet 主密钥外泄等同于全失守，不再分隔降低复杂度 |

## 10. 顺手清单（独立 commit，建议同 PR）

- `.dockerignore` 加 `.antigravitycli/`（避免本地工具目录进入 image）
- `env.example` 加 `LOOM_AUTH_USERNAME` / `LOOM_AUTH_PASSWORD_HASH` / `LOOM_INSTANCE_ID` 示例
- `README.md` 部署小节加 bcrypt 哈希生成命令 + 登录流程说明

---

> 待 Codex Plan Review 评分（`[PLAN REVIEW REQUEST]`）。整合后请用户确认，再 Phase 2 委派实现。
