# FDE Console 用户手册

![FDE Console 截图占位](data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII=)

## 1. 启动 Docker

```bash
python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'
export LOOM_FERNET_KEY='<生成的 key>'
export LOOM_AUTH_USERNAME='admin'
export LOOM_AUTH_PASSWORD_HASH='<scrypt hash>'
docker compose up -d --build
```

打开 `http://localhost:18080`，使用配置的本地账号登录。

## 2. 创建 Session

在首页点击“新建 Session”。系统会进入 session detail 页面。

## 3. 填写 BYOK

首次进入 session 会弹出 LLM 配置：

- API Key
- Base URL
- Model

FDE 只把密钥加密保存在本机 SQLite 中，不会写入生成的 Hiagent/Dify 产物。

## 4. 与 Planner 对话

在左侧输入业务意图，等待非流式 Planner 调用完成。成功后中间面板会显示当前 IR。

## 5. 查看 IR、Diff、Validator

- 当前 IR 是只读 YAML 风格文本。
- 两次成功 turn 后可展开 IR 变更列表。
- Validator 错误会以卡片显示，点击 path 会高亮 IR 中的相关字段。

## 6. 编译并下载

在底部 Compile Bar 选择：

- `hiagent` + `chatflow`，下载 ZIP。
- `dify`，下载 YAML。

## 7. 手动导入平台

把 ZIP 拖入 Hiagent 导入智能体向导，或把 YAML 导入 Dify UI。FDE 不做自动上传。

## 8. 标记部署

导入成功后，在 artifact 卡片填写平台 App ID 和备注，点击“标记已导入”。这会回填 workflow registry，便于后续追踪。
