# Workspace Terminal 服務

以 Go 實作的 Aileron WebSocket Terminal 服務。

## 功能

- WebSocket 即時通訊
- 多分頁 Terminal 管理與輸出重播
- PTY 建立、調整尺寸與 process-tree 終止
- 透過 Manager `runtime-access` 進行 action-aware 授權
- 以 Ed25519/JWS 驗證 Manager 送出的短效 drain assertion
- drain 時拒絕新連線，並關閉全部 WebSocket、分頁與 PTY
- concurrency-safe 狀態管理與 graceful shutdown

## 技術

- Go 1.21+
- Gin
- `creack/pty`
- `zap`
- `gorilla/websocket`

## 必要環境變數

| 變數 | 說明 | 預設值 |
| --- | --- | --- |
| `TERMINAL_PORT` | 服務連接埠 | `8745` |
| `LOG_LEVEL` | Log 等級 | `info` |
| `AILERON_WORKSPACE_ID` | 此 workload 所屬 Workspace ID | 無，啟動時必須提供 |
| `AILERON_RUNTIME_INSTANCE_ID` | 此 execution-plane generation 的不可變 ID | 無，啟動時必須提供 |
| `AILERON_RUNTIME_ACCESS_REVISION` | Runtime access revision | 無，啟動時必須提供 |
| `AILERON_PLATFORM_PUBLIC_ORIGIN` | WebSocket Origin 驗證使用的唯一精確平台 Origin | 無，啟動時必須提供 |
| `AILERON_KB_MOUNT_REVISION` | Runtime 目前已掛載的 KB revision | 無，啟動時必須提供 |
| `AILERON_RUNTIME_ASSERTION_PUBLIC_KEY_SET_FILE` | Manager Ed25519 public JWKS 的唯讀檔案路徑 | 無，啟動時必須提供 |
| `AILERON_RUNTIME_ASSERTION_ISSUER` | Execution Grant 與 drain assertion issuer | `workspace-manager` |
| `TERMINAL_REPLAY_BUFFER_BYTES` | 每個分頁的重播 ring 大小 | `1048576` |
| `TERMINAL_OUTPUT_FLUSH_MS` | Terminal 輸出批次送出的最大等待毫秒數 | `12` |

## API

### Terminal WebSocket

```text
GET /ws/terminal?workspace_id={workspace_id}
Sec-WebSocket-Protocol: aileron-terminal-v1, bearer.{base64url(user_bearer)}
```

升級 WebSocket 前，Terminal 會用本機 public JWKS 驗證短效 `workspace-terminal` Execution Grant，並比對 Workspace ID、Runtime instance 與 access revision。簽章、audience、scope 或 generation context 不符時一律 fail closed。Terminal 不會把 bearer 保存到 client state、DB、child process environment 或 log。

### 內部 Drain

```text
POST /internal/drain
Authorization: Bearer {manager_signed_terminal_drain_jws}
```

assertion 必須使用 `alg=EdDSA`、`aud=workspace-terminal-drain`，並通過 issuer、Workspace、runtime instance、mounted revision、deadline、`exp <= 60s` 與 single-use `jti` 驗證。assertion 不接受 query string。

- `204`：全部本地 Terminal 資源已關閉；相同 `drainAttemptId` 搭配新 JTI 重送亦回 `204`。
- `401 RUNTIME_DRAIN_ASSERTION_INVALID`：signature、audience、時間、kid 或 replay 無效。
- `409 RUNTIME_DRAIN_CONTEXT_MISMATCH`：Workspace、instance、revision 或 drain attempt 不符。
- `504 RUNTIME_DRAIN_TIMEOUT`：deadline 前未完成本地清理。

drain 是 graceful 最佳化；最終 fencing 仍由 provisioner 強制終止並證明整個 Runtime workload identity 已消失。

### Health Check

```text
GET /health
```

## WebSocket 訊息格式

```json
{
  "type": "message_type",
  "tab_id": "tab_id",
  "data": {},
  "timestamp": 1699900000
}
```

Client-to-server 類型：

- `create_tab`
- `close_tab`
- `switch_tab`
- `list_tabs`
- `replay`
- `input`
- `resize`
- `clear`

Server-to-client 類型：

- `connected`
- `tab_created`
- `tab_closed`
- `tab_switched`
- `tab_updated`
- `tab_list`
- `tab_replay_reset`
- `output`
- `resized`
- `error`

## 容器測試

```bash
docker compose -f workspace-terminal/docker-compose.test.yml run --build --rm workspace-terminal-test \
  sh -c 'go vet ./... && go test -v ./... && go build -o /tmp/workspace-terminal ./cmd/server'
```
