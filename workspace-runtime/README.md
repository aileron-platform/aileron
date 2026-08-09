# Aileron Workspace Runtime

Workspace Runtime 是每個 Workspace 的隔離執行層，提供 Agent 執行、檔案與 Git、Automation、系統監控、Canvas 整合及即時事件串流。

## 主要能力

- Claude Code、Codex 與 OpenCode 執行
- Workspace filesystem、Git 與檔案事件
- Automation Runner 與執行追蹤
- CPU、記憶體與磁碟監控
- Thread event WebSocket 與 HTTP streaming
- Browser CDP 與 Canvas 內部服務整合

## 設定所有權

Runtime 不提供獨立 `.env` 安裝介面。Docker 由 Manager Provisioner 注入，Kubernetes 由 Workspace Operator 注入；兩者都使用相同的 canonical `AILERON_*` 平台環境。Workspace 使用者設定不得使用 `AILERON_*` 前綴。

必要平台欄位如下：

| 變數 | 說明 |
| --- | --- |
| `AILERON_WORKSPACE_ID` | Workspace ID |
| `AILERON_WORKSPACE_PATH` | Workspace filesystem root |
| `AILERON_RUNTIME_INSTANCE_ID` | execution-plane generation ID |
| `AILERON_RUNTIME_ACCESS_REVISION` | Runtime access revision |
| `AILERON_KB_MOUNT_REVISION` | Knowledge Base mount revision |
| `AILERON_WORKTREE_SUBDIR` | 受管理的 Git worktree 子目錄 |
| `AILERON_MANAGER_INTERNAL_URL` | Manager 內部 Service URL |
| `AILERON_PLATFORM_PUBLIC_ORIGIN` | 瀏覽器可見的唯一精確 Origin |
| `AILERON_RUNTIME_STATE_DATABASE_URL_FILE` | Workspace-scoped database URL 的唯讀 Secret 檔案 |
| `AILERON_RUNTIME_CONTROL_TOKEN_FILE` | generation-scoped Manager control token 的唯讀 Secret 檔案 |
| `AILERON_RUNTIME_ASSERTION_PUBLIC_KEY_SET_FILE` | Manager assertion public JWKS 的唯讀檔案 |
| `AILERON_RUNTIME_ASSERTION_ISSUER` | Manager assertion issuer |
| `AILERON_BROWSER_SERVICE_NAME` | Browser 內部 service name |
| `AILERON_BROWSER_WEBRTC_INTERNAL_URL` | Browser 內部 WebRTC URL |
| `AILERON_BROWSER_CDP_URL` | Browser 內部 CDP URL |
| `AILERON_CANVAS_SERVICE_NAME` | Canvas 內部 service name |
| `AILERON_CANVAS_INTERNAL_URL` | Canvas renderer 內部 URL |
| `AILERON_CANVAS_API_URL` | Canvas 管理 API 內部 URL |

Database credential 與 control token 只從絕對路徑的 Secret file 讀取，不接受明文環境變數。Runtime 不接收 external OIDC issuer、client secret、provider token、平台 `DATABASE_URL` 或共用 internal token。

## 公開路徑

Frontend 與瀏覽器只組合 same-origin 相對路徑：

- Runtime HTTP：`/workspaces/{workspaceId}/runtime/api/v1/...`
- Thread WebSocket：`/workspaces/{workspaceId}/runtime/api/v1/threads/events`
- Terminal WebSocket：`/workspaces/{workspaceId}/runtime/ws/terminal`

Frontend gateway 只把 canonical Workspace UUID 與固定 target 轉成部署內部服務位址。Runtime 的內部 DNS、容器 port 或 upstream URL 不會交給瀏覽器。

## 本機建置

```bash
make build-runtime-base-lite
make build-workspace-runtime
```

Runtime image 由平台 Provisioner 建立，不應以手寫 `docker run -e ...` 形成另一套設定來源。

## 主要端點

- `GET /health`
- `/api/v1/files/*`
- `/api/v1/settings`
- `/api/v1/scripts`
- `/api/v1/threads/*`
- `WS /api/v1/threads/events`
- `WS /api/v1/ws`
- `POST /internal/automation/executions/{execution_id}/cancel`

## Container 測試

```bash
make test-all
```
