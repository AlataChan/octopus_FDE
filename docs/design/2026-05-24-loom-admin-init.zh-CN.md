# `loom admin` 凭据初始化命令设计

> 状态：草案 v2（已整合 Codex Plan Review，overall=7.5 过线）
>
> v2 修订摘要（来自 Codex 5 项 required）：
> - **bootstrap 顺序矛盾修复**：用 `docker compose run --rm` 在 `up` 之前 init，避免"服务因缺凭据退出 → exec 不能跑"死锁
> - prod 下 auth.json 权限不严于 0o600 → **启动失败**（不再只 warning）；dev 保留 warning
> - 原子写细化：同目录 tmp 文件 + `O_CREAT|O_EXCL|O_NOFOLLOW` + `fsync(file)` + `fsync(dir)` + rename + 写后 lstat 校验非 symlink
> - archive `backup_path` 只存 basename，不存绝对路径
> - CLI 审计走与服务相同的 `InstanceArchiveWriter` + HMAC helper，不自构造
> 作者：Claude（架构师角色）
> 日期：2026-05-24
> 关联代码：`loom/cli/commands/`、`loom/service/{auth/,deps.py}`、`scripts/setup-env.sh`、`Dockerfile`

## 1. 背景

当前鉴权方案要求在 `.env` 中手填 `LOOM_AUTH_USERNAME` + `LOOM_AUTH_PASSWORD_HASH`。痛点：
- 部署方必须先在本地跑 `scripts/setup-env.sh` 生成 scrypt 哈希
- 改密码 = 改 env + 重启容器
- 哈希字符串落在 `.env` 文件里，密码生成命令需要外部 Python 环境
- 不符合"部署后初始化"的产品直觉

目标：**部署后**用一条 `docker compose exec fde loom admin init` 完成凭据初始化，把哈希写入数据卷里的持久文件，env 只保留 `LOOM_FERNET_KEY`。

## 2. 目标与非目标

**目标**
- 新增 `loom admin {init, reset-password, remove, show}` 4 个子命令
- 凭据持久化到 `$LOOM_DATA_DIR/auth.json`（与 sessions DB 同卷），文件权限 0600
- 鉴权加载优先级：**env > 文件 > 启动失败**（兼容现状不破坏既有部署）
- `scripts/setup-env.sh` 加 `--fernet-only` 模式，只生成密钥不动账号；老用法保留
- README 增加"推荐部署流程"段：单 fernet env + docker exec init
- 密码强度校验（交互式 + 非交互式都强制）
- 审计事件扩展

**非目标**
- 不引入多用户 / 角色管理（仍是"一 docker 一用户"）
- 不引入密码自助找回（私域部署，运维直接 reset）
- 不改 IR / 编译器 / runtime adapter / 现有 cookie session 机制
- 不动 web 前端登录页（auth.json 对前端透明）

## 3. 总体流程

```
=== 推荐新流程 ===
1. bash scripts/setup-env.sh --fernet-only
     → .env 只写一行 LOOM_FERNET_KEY=...
2. docker compose build
     → 仅构建镜像，不启动服务（避免缺凭据死循环）
3. docker compose run --rm fde loom admin init
     → 一次性容器跑 init：交互式 prompt → scrypt → 写 /data/auth.json (600)
     → --rm 让容器跑完即清；auth.json 持久在挂载卷 /data
4. docker compose up -d
     → 此时 /data/auth.json 已存在 → 服务正常启动
5. 浏览器登录 http://localhost:18080

=== 改密（服务运行中可用 exec） ===
docker compose exec fde loom admin reset-password
     → 同样交互式 prompt；不需要重启服务

=== 删账号（极端场景） ===
docker compose exec fde loom admin remove --confirm
     → 把 /data/auth.json 改名为 auth.json.disabled.<timestamp>，下次启动报错提示重新 init
     → 后续要重新 init 必须先 docker compose down，再走 run --rm 路径
     → 因为服务已不能正常启动接 exec

=== 兼容老流程（env 哈希）===
原 LOOM_AUTH_USERNAME / LOOM_AUTH_PASSWORD_HASH 仍可用，且优先级高于 auth.json。
便于 CI / 不可变基础设施场景。
```

## 4. CLI 规格

### 4.1 `loom admin init`
```
loom admin init
  --data-dir PATH        可选；缺省取 $LOOM_DATA_DIR
  --username TEXT        可选；若缺则交互式 prompt
  --password-stdin       从 stdin 读密码（非交互式，CI 用）
  --force                覆盖已存在的 auth.json（默认拒绝）

退出码：
  0  成功
  1  已存在 auth.json 且未传 --force / 密码强度不通过 / 二次输入不一致
  2  IO 错误 / 文件权限错误 / data-dir 不存在
```

行为：
- 已存在 `auth.json` 且无 `--force` → 报错提示用 `reset-password`
- 强度校验：≥10 chars + 4 类（大写/小写/数字/符号）至少 3 类，否则拒绝
- 交互式：`getpass()` 两次输入；两次不一致重试 1 次再失败
- 非交互式：`--password-stdin` 从 stdin 读一行；省去强度校验则违背 spec，所以非交互式同样强校验
- **原子写（symlink-safe）**：
  1. `tmp_path = data_dir / f".auth.json.tmp.{os.getpid()}"`（同目录，避免跨 fs rename）
  2. `fd = os.open(tmp_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)`
  3. `os.write(fd, payload_bytes)` → `os.fsync(fd)` → `os.close(fd)`
  4. `os.rename(tmp_path, auth_path)`
  5. `dir_fd = os.open(data_dir, os.O_RDONLY)` → `os.fsync(dir_fd)` → `os.close(dir_fd)`
  6. `st = os.lstat(auth_path)`：校验 `stat.S_ISREG(st.st_mode)` 且 `(st.st_mode & 0o777) == 0o600`；不符合则 raise
- 目录权限继承现有 `LOOM_DATA_DIR`（已是 0o700）；写前校验目录权限不松于 0o700
- 写入后 stdout 打印：`✓ admin user '<username>' created at /data/auth.json`

### 4.2 `loom admin reset-password`
```
loom admin reset-password
  --data-dir PATH
  --password-stdin
```
仅改密码，username 不变。要求 `auth.json` 已存在；不存在则提示先 `init`。

### 4.3 `loom admin remove`
```
loom admin remove --confirm
  --data-dir PATH
```
将 `auth.json` 改名 `auth.json.disabled.<YYYYMMDD-HHMMSS>` 保留备份。下次服务启动如 env 也没配 → 启动失败，错误信息明确提示运行 `loom admin init`。

### 4.4 `loom admin show`
```
loom admin show
  --data-dir PATH
  --json / --text
```
打印当前账号状态：`username / created_at / last_password_changed_at / source(env|file)`。**不打印**任何密码相关字段。退出码 0=找到 / 1=未配置。

## 5. `auth.json` 文件格式

```json
{
  "schema_version": "1",
  "username": "admin",
  "password_hash": "scrypt$16384$8$1$<salt_b64>$<hash_b64>",
  "created_at": "2026-05-24T13:00:00+00:00",
  "last_password_changed_at": "2026-05-24T13:00:00+00:00"
}
```
- `schema_version` 闭合 `Literal["1"]`，未来 break 升号
- 读取时严格 schema 校验；不识别字段拒绝加载（防止误操作）
- pydantic `_Strict` 风格（extra=forbid，frozen）

## 6. 鉴权加载优先级（`Settings.from_env` 改造）

```python
@dataclass(frozen=True)
class AuthCredentials:
    username: str
    password_hash: str
    source: Literal["env", "file"]

def load_auth_credentials(*, data_dir: Path, env: dict) -> AuthCredentials | None:
    # 1. env 优先（兼容现有部署 + 不可变基础设施）
    if env.get("LOOM_AUTH_USERNAME") and env.get("LOOM_AUTH_PASSWORD_HASH"):
        return AuthCredentials(env["LOOM_AUTH_USERNAME"], env["LOOM_AUTH_PASSWORD_HASH"], "env")
    # 2. 文件兜底
    f = data_dir / "auth.json"
    if f.exists():
        doc = AuthFileSchema.model_validate(json.loads(f.read_text()))
        return AuthCredentials(doc.username, doc.password_hash, "file")
    # 3. 都没 → None；调用方决定是否容忍（prod 必须报错）
    return None
```

`Settings.from_env()` 在 `APP_ENV != "dev"` 且 `auth_disabled` 不为 true 时，必须能拿到 `AuthCredentials`，否则启动失败：
```
RuntimeError: No admin credentials configured.
Run `loom admin init` inside the container, or set LOOM_AUTH_USERNAME and LOOM_AUTH_PASSWORD_HASH env vars.
```

混合配置时（env + file 都有）打印 INFO 日志说明 env 优先；不抛错（运维场景常见，env 临时覆盖文件）。

## 7. 安全细节

| 项 | 处理 |
|---|---|
| auth.json 权限 | 写入用 `O_CREAT\|O_EXCL\|O_NOFOLLOW` 直接 0o600；启动加载时 lstat 校验：prod 下若 mode > 0o600 或非常规文件 → **启动失败**；dev 下 warning |
| 写文件原子性 | 同目录 tmp + O_CREAT\|O_EXCL\|O_NOFOLLOW + fsync(file) + rename + fsync(dir) + lstat 复核 |
| symlink / hardlink 攻击 | O_NOFOLLOW 拒打开 symlink；写后 lstat 复核 S_ISREG；不接受 hardlink（lstat 复核 nlink==1 可选，spec 暂不强求） |
| 密码强度 | ≥10 chars + 4 类至少 3 类（大写/小写/数字/符号） |
| getpass 不回显 | stdlib `getpass.getpass()` |
| `--password-stdin` 截断换行 | `input()` 或 `sys.stdin.readline().rstrip('\n')`；如检测到 `sys.stdin.isatty()` → 拒绝并提示用交互式 prompt（防止误用） |
| scrypt 参数 | 与 env 路径一致：N=2^14, r=8, p=1, dklen=32, maxmem=128MB |
| `loom admin show` 不输出密码相关字段 | 严格白名单 |
| 改密后清理旧 hash | 直接 rename → 替换；旧文件不留存（用户主动 backup 自负） |
| Container exec 限制 | 在 docker exec 内运行；外部需要 root 才能进容器，与 host 同信任域 |

## 8. 审计事件扩展

`ArchiveEventType` 加：
- `"auth.admin_init"` — payload `{username_hmac, source: "file"}`
- `"auth.admin_password_reset"` — payload `{username_hmac}`
- `"auth.admin_removed"` — payload `{username_hmac, backup_basename}`（**只存 basename**，如 `"auth.json.disabled.20260524-130000"`，不存绝对路径，避免泄漏文件系统布局）

由 CLI 命令调用与服务**相同的 `InstanceArchiveWriter`**（`loom/archive/writer.py`）写事件，自动注入 `instance_id` 与 HMAC 派生密钥；不允许自构造 hash 或绕过 wrapper。CLI 在 dispatch 时按 `LOOM_INSTANCE_ID` env + `LOOM_FERNET_KEY` 构造 writer 实例。

## 9. `scripts/setup-env.sh` 改造

加 `--fernet-only` 模式：
- 不生成密码 / 不询问 username / 不写 `LOOM_AUTH_*`
- 只生成 `LOOM_FERNET_KEY` + `LOOM_INSTANCE_ID` + `LOOM_DATA_DIR` + `LOOM_AUTH_COOKIE_INSECURE_OK`
- 保留默认模式（写完整 LOOM_AUTH_*）作为快速本地测试入口

调用：`bash scripts/setup-env.sh --fernet-only`

## 10. README 更新

新增"推荐部署流程"段（取代当前 quickstart 主路径）：
```bash
# 1. 生成 Fernet 密钥并写入 .env（无账号信息）
bash scripts/setup-env.sh --fernet-only

# 2. 仅构建镜像，不启动服务
docker compose build

# 3. 一次性容器跑 init（交互式输入 username + password）
docker compose run --rm fde loom admin init

# 4. 启动服务
docker compose up -d

# 5. 浏览器登录 http://localhost:18080
```

> 这里用 `run --rm` 而不是 `up` + `exec`，是因为缺凭据时服务会拒启 → exec 进不去。run --rm 跑完即清，auth.json 留在挂载卷 /data。

改密 / 查询账号（服务运行中）：
```bash
docker compose exec fde loom admin reset-password
docker compose exec fde loom admin show
```

把"老流程（env 哈希）"段降级为"备用方案 / CI 不可变基础设施场景"。

## 11. 数据契约变更

| 维度 | 变更 |
|---|---|
| DB schema | **无** |
| `ArchiveEventType` | 加 3 条 admin.* 事件 |
| HTTP 路由 | **无** |
| `Settings` | 新增 `data_dir_auth_path` derive |
| 新增文件 | `$LOOM_DATA_DIR/auth.json` |
| 新增 CLI | `loom admin {init, reset-password, remove, show}` |

## 12. 验收标准

1. 全新部署：`setup-env.sh --fernet-only` → `docker compose build` → `docker compose run --rm fde loom admin init` 交互式输入 → `docker compose up -d` → 浏览器登录成功；其中第 4 步如缺 auth.json 必须 exit 非零并提示"先跑 loom admin init"
2. 强度校验：密码 `weak` → CLI 拒绝并提示规则
3. 二次输入不一致 → 重试 1 次仍不一致 → exit 1
4. 已存在 auth.json 无 `--force` → exit 1 提示用 `reset-password`
5. 带 `--force` → 直接覆盖
6. `loom admin reset-password` 不存在 auth.json → exit 1
7. `loom admin remove --confirm` → 文件改名带时间戳；下次服务启动报错文案含 `loom admin init` 提示
8. `loom admin show --json` → 输出含 `username / source / created_at`；**不含 password_hash / salt**
9. env 与 file 都有 → 用 env 凭据 + INFO 日志
10. env 缺 file 缺 + APP_ENV=prod → 启动失败，error 文案明确
11. 文件权限 > 0o600 → prod 启动失败、dev 仅 warning；文件为 symlink → 任何 env 都启动失败
17. archive `auth.admin_removed` 事件 payload 只含 basename，不含绝对路径
18. `--password-stdin` 在 TTY 下被拒绝（避免误用）
19. 写入中插入 symlink 攻击模拟（test fixture 在 tmp 目录预置同名 symlink）→ open 失败 / rename 拒绝
20. CLI 写 archive 走 `InstanceArchiveWriter`，不直接调底层 jsonl writer
12. `--password-stdin` 非交互模式可工作
13. auth.json 损坏 / schema 不匹配 → 启动失败，error 含文件路径
14. 写文件中途崩溃（mock） → 不留半写文件（tmp+rename 原子性）
15. `pytest -q` / `mypy loom` 全绿
16. archive 含 auth.admin_init 事件，payload 无明文 username

## 13. 工期与拆分

按 Codex 颗粒（同 PR，6 个 commit）：
1. backend: `loom/service/auth/credentials.py` —— `AuthFileSchema` + `load_auth_credentials()` + 文件原子写入工具 + 单测
2. backend: `Settings.from_env` 改造接 `load_auth_credentials`；保留 env 优先级 + 兜底报错 + 单测
3. backend: `loom/cli/commands/admin.py` —— `init / reset-password / remove / show` 子命令 + 强度校验 + 单测（用 CliRunner）
4. backend: ArchiveEventType 扩展 + CLI 写 archive 路径
5. chore: `scripts/setup-env.sh --fernet-only` 模式 + README 推荐流程改写
6. tests: docker-compose smoke（如 CI 不便跑 docker 则文档化"手测必跑"）

## 14. 风险

| 风险 | 缓解 |
|---|---|
| 用户漏跑 admin init → 服务起不来 | 启动错误文案直接给出补救命令；README 推荐流程把 init 排在 docker up 之后必跑步骤 |
| 容器重建后 auth.json 丢失 | auth.json 在挂载卷 /data 里；容器重建不影响；如把卷一并删了 → 重新 init |
| 同时设 env 和 file 引起混淆 | INFO 日志 + `loom admin show` 显式输出 `source` 字段 |
| docker exec 进入容器后误删 auth.json | `loom admin remove` 用 rename 保留 backup；`rm` 直接删的运维责任自负 |
| 文件权限审计噪声 | 仅 warning 不阻止启动；同时记录到 archive |

---

> 待 Codex Plan Review（标签 `[PLAN REVIEW REQUEST]`），整合后请用户确认，再 Phase 2 委派实现。
