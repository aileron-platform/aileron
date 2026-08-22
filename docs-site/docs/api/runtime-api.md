---
title: Runtime API
---

# Workspace Runtime API

Workspace Runtime API 提供每個 workspace 內的 AI Chat thread、Agent 執行、檔案操作與即時事件能力。Claude Code、Codex 與 OpenCode 都透過同一套多 Agent runtime 介面運作。

## 互動式文件

- **Swagger UI**：`/workspaces/{workspaceId}/runtime/docs`
- **ReDoc**：`/workspaces/{workspaceId}/runtime/redoc`

:::note
每個 Workspace 都有獨立的 Runtime instance 與 revision。先透過 Manager 啟動 Workspace，再從目前 Platform Public Origin 使用 `/workspaces/{workspaceId}/runtime/...`；瀏覽器不接收 Runtime host 或 port。
:::

## Base URL

```text
/workspaces/{workspaceId}/runtime
```

## Runtime access gate

除精確 public health 與 signed internal route 外，Runtime 只接受 Manager 簽發、audience
為 `workspace-runtime` 的 Workspace Execution Access Grant。Runtime 在本地使用 public JWKS
驗證簽章、固定 60 秒 TTL、token kind、明確 action、`workspaceId`、`runtimeInstanceId` 與
`runtimeAccessRevision`；任一欄位不符都 fail closed。一般 Runtime action 不以 KB mount
revision 作為全域 gate；只有 `/knowledge` 與掛載管理操作會明確檢查 KB mount 狀態。

| 路徑／方法 | Action |
| --- | --- |
| 一般`GET`／`HEAD` | `runtime_read` |
| 一般寫入方法 | `runtime_write` |
| Claude／Codex／OpenCode raw settings 與 MCP env／headers | `workspace_settings` |
| Thread REST（讀取與 mutation）及 agent session | `agent` |
| Thread events WebSocket handshake | `runtime_read` |
| Automation | `automation` |
| Client Browser Relay | `browser_automation` |

每個 action 會映射到中央 Workspace OperationId。Reader 只能進入安全 read projection；`runtime_write`、`workspace_settings`、`terminal`、`agent`、`automation` 與 `browser_automation` 需要 Manager、Owner 或 Platform Admin。完整規則與 `403`／`423` 語意請參考 [使用者、群組與權限](/features/platform/permissions-and-roles)。

Runtime 依封閉的 route × method inventory 分類 action。敏感精確 route 與敏感 wildcard 優先於一般 mutation／read；未知或同時命中多個 family、Manager timeout 或驗證失敗時，Runtime 會在呼叫 upstream 前 fail closed。Runtime URL 只提供定位，不是授權憑證，每次請求都重新驗證。

Frontend 先使用 opaque Manager session 向
`POST /api/v1/workspaces/{workspaceId}/execution-grants` 申請 Grant；Manager 對每個 action
完成授權後才簽發。Runtime 不接觸 external OIDC token，也不逐 request 回呼 Manager。
Execution Grant 在 TTL 內可重複使用；Manager→Runtime 內部命令與 pairing 則使用不同
token kind、audience、verifier 與 one-time replay state。兩條 interface 都不接受前端傳入
角色作為授權依據。

Direct／group share 變更、群組成員變更、帳號停用、Owner 重新指派、Platform Admin 降權
及 Public KB 改回 Private 時，Manager 會提升 runtime access revision。舊 Grant 因 revision
fence 失效；cached Runtime URL 或未過期但 revision 過舊的 Grant 都不能繞過驗證。

## 主要端點

### 健康檢查

```http
GET /health
```

### 檔案管理

| Method | 路徑 | 說明 |
|--------|------|------|
| `GET` | `/api/v1/files/tree` | 取得目錄樹 |
| `GET` | `/api/v1/files/tree/children` | 延遲載入子節點 |
| `GET` | `/api/v1/files/search` | 搜尋檔案 |
| `GET`／`PUT` | `/api/v1/files/content` | 讀取／寫入單一檔案內容 |
| `POST` | `/api/v1/files/content/batch` | 批次寫入多個檔案內容 |
| `GET` | `/api/v1/files/download` | 下載檔案 |
| `POST`／`DELETE` | `/api/v1/files` | 建立／刪除檔案或資料夾 |
| `POST` | `/api/v1/files/upload` | 上傳檔案 |
| `POST` | `/api/v1/files/copy` | 複製檔案或資料夾 |
| `POST` | `/api/v1/files/move` | 搬移或重新命名 |
| `POST` | `/api/v1/files/batch-delete` | 批次刪除 |
| `POST`／`GET` | `/api/v1/files/archive`、`/api/v1/files/archive/{operation_id}` | 建立壓縮任務並查詢進度 |
| `GET` | `/api/v1/files/archive/{operation_id}/download` | 下載完成的 ZIP |
| `POST`／`GET` | `/api/v1/files/extract`、`/api/v1/files/extract/{operation_id}` | 建立解壓任務並查詢進度 |
| `GET` | `/api/v1/files/history` | 檔案異動歷史 |
| `POST` | `/api/v1/files/history/{entry_id}/restore` | 還原指定歷史版本 |

### Agent 與 CLI 設定

這組設定 API 管理 workspace 內的 agent 設定，涵蓋 Claude Code、Codex、OpenCode 的 rules、hooks、MCP、skills、slash commands 與 subagents 等資源。

| Method | 路徑 | 說明 |
|--------|------|------|
| `GET` | `/api/v1/workspaces/{workspace_id}/claude-code/settings` | 取得 Claude Code settings |
| `PUT` | `/api/v1/workspaces/{workspace_id}/claude-code/settings` | 更新 Claude Code settings |
| `GET` | `/api/v1/workspaces/{workspace_id}/codex` | 取得 Codex 設定能力 |
| `GET`／`PUT` | `/api/v1/workspaces/{workspace_id}/codex/config` | 取得／更新 Codex config |
| `GET` | `/api/v1/workspaces/{workspace_id}/{tool}/mcp-servers` | 取得 MCP server 設定 |
| `PUT` | `/api/v1/workspaces/{workspace_id}/{tool}/mcp-servers/{scope}/{server_name}` | 更新 MCP server |
| `GET` | `/api/v1/workspaces/{workspace_id}/{tool}/skills/tree` | 取得 skills 檔案樹 |
| `GET` | `/api/v1/workspaces/{workspace_id}/{tool}/slash-commands` | 列出 slash commands |
| `GET` | `/api/v1/workspaces/{workspace_id}/cli-settings/{tool}/prompt-invocations` | 取得可直接送出的 Commands 與 Skills invocation catalog |

`tool` 使用 `claude-code`、`codex` 或 `opencode`；各 provider 支援的 scope 與可寫資源
不同，完整 request／response schema 以目前 Runtime OpenAPI 為準。

Prompt invocation catalog 是 AI Chat 與 Automation 共用的唯讀契約。Runtime 會依指定工具
聚合 Commands 與 Skills，並回傳已格式化的 `invocation`、穩定項目 ID、可用 scope、內容
revision 與來源錯誤。部分來源失敗時回傳 `200` 與 `completeness: degraded`；所有來源都
無法讀取時回傳 `503`。Runtime 每次請求都重新驗證來源，不沿用來源清單快取；Prompt
Invocation Picker 每次開啟都重新載入 catalog，且 Picker 消費端原樣使用 Runtime 回傳的
`invocation`，不自行拼接命令格式。

Raw settings、MCP environment variables、HTTP headers、API key 與 token 都屬敏感設定，讀寫一律使用 `workspace_settings` action；一般 `runtime_read` 或 `agent` action 不能讀取這些值。

### AI Chat Threads

Thread metadata 與 history 分離；history 只使用 Message Item timeline。完整機制請見 [AI Chat 前後端架構](/architecture/overview/ai-chat#讀取與分頁)。

| Method | 路徑 | 說明 |
|--------|------|------|
| `GET` | `/api/v1/threads` | 列出 threads |
| `POST` | `/api/v1/threads/draft` | 建立 draft thread |
| `GET` | `/api/v1/threads/{thread_id}` | 取得 thread 詳情 |
| `PATCH` | `/api/v1/threads/{thread_id}/draft` | 更新 draft |
| `POST` | `/api/v1/threads/{thread_id}/submit` | 送出 draft 並啟動 agent |
| `POST` | `/api/v1/threads/{thread_id}/messages` | 追加訊息 |
| `GET` | `/api/v1/threads/{thread_id}/timeline` | 以 `beforeSequence` 讀取 Message Item history |
| `POST` | `/api/v1/threads/{thread_id}/timeline/items/batch-get` | 批次刷新最多 200 個已知 timeline items |
| `GET` | `/api/v1/threads/{thread_id}/messages/{message_id}/tool-result` | 依需要讀取完整 tool result |
| `POST` | `/api/v1/threads/{thread_id}/questions/{message_id}/answer` | 回答互動式問題 |
| `POST` | `/api/v1/threads/{thread_id}/stop` | 停止目前 Turn；有排隊訊息時接續下一則，否則 thread 結束為 canceled |
| `POST` | `/api/v1/threads/{thread_id}/retry` | 重試 thread |
| `POST` | `/api/v1/threads/{thread_id}/archive` | 封存 thread |
| `GET` | `/api/v1/threads/{thread_id}/attachments` | 列出附件 |
| `POST` | `/api/v1/threads/{thread_id}/attachments` | 上傳附件 |

### 版本控制（Git）

| Method | 路徑 | 說明 |
|--------|------|------|
| `GET` | `/api/v1/workspaces/{id}/version-control/status` | Git status |
| `GET` | `/api/v1/workspaces/{id}/version-control/changes` | Git changes |
| `POST` | `/api/v1/workspaces/{id}/version-control/changes/numstat` | 查詢 changes numstat |
| `GET` | `/api/v1/workspaces/{id}/version-control/commits` | Git commits |
| `GET` | `/api/v1/workspaces/{id}/version-control/commits/{commit_id}` | Commit 詳情 |
| `GET` | `/api/v1/workspaces/{id}/version-control/commits/{commit_id}/files` | Commit 檔案清單 |
| `GET` | `/api/v1/workspaces/{id}/version-control/diff` | Git diff |
| `GET` | `/api/v1/workspaces/{id}/version-control/blob` | 讀取 Git blob |
| `POST` | `/api/v1/workspaces/{id}/version-control/stage` | Stage changes |
| `POST` | `/api/v1/workspaces/{id}/version-control/unstage` | Unstage changes |
| `POST` | `/api/v1/workspaces/{id}/version-control/discard` | Discard changes |
| `POST` | `/api/v1/workspaces/{id}/version-control/commit` | Commit |
| `POST` | `/api/v1/workspaces/{id}/version-control/push` | Push |
| `POST` | `/api/v1/workspaces/{id}/version-control/pull` | Pull |
| `POST` | `/api/v1/workspaces/{id}/version-control/fetch` | Fetch |
| `GET` | `/api/v1/workspaces/{id}/version-control/branches` | 列出分支 |
| `POST` | `/api/v1/workspaces/{id}/version-control/branches/{branch_name}/checkout` | 切換或建立分支 |
| `GET` | `/api/v1/workspaces/{id}/version-control/operation-status` | 查詢目前 Git operation 狀態 |
| `POST` | `/api/v1/workspaces/{id}/version-control/force-unlock` | 強制解除 Git operation lock |

### WebSocket

| 端點 | 說明 |
|------|------|
| `WS /api/v1/threads/events` | Thread invalidation 與事件通知 |

#### Thread WebSocket 連線

Browser使用和Terminal一致的WebSocket subprotocol credential，不把token寫進URL：

```javascript
const encodedToken = btoa(token)
  .replaceAll('+', '-')
  .replaceAll('/', '_')
  .replace(/=+$/, '');
const threadEventsUrl = new URL(
  `/workspaces/${workspaceId}/runtime/api/v1/threads/events`,
  window.location.origin,
);
threadEventsUrl.protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
const ws = new WebSocket(
  threadEventsUrl,
  ['aileron-thread-v1', `bearer.${encodedToken}`],
);
```

Browser client 只從目前頁面的 Origin 組合固定相對路徑，不接收 Runtime host、port 或 upstream URL。

Runtime只選擇並echo `aileron-thread-v1` application protocol，不會把
`bearer.<base64url(token)>` credential protocol echo給client。非browser caller也可在
upgrade直接設定`Authorization: Bearer <token>`；同一request只能使用其中一種方式。

Runtime會先驗證token，再以`runtime_read`檢查current Workspace與instance，通過後才
accept。`token`／`access_token` query、internal token、同時使用header與subprotocol、
缺少application protocol、重複或格式錯誤的credential都會以`4401`fail closed。權限不足
使用`4403`，Runtime access 或 lifecycle lock 未收斂使用`4423`，Manager驗證無法完成則使用`4503`。

## Canvas

Canvas 端點皆掛在 Workspace 底下（`/api/v1/workspaces/{workspace_id}/canvas/*`），manifest 契約與生命週期請見 [Canvas Protocol](/architecture/overview/canvas/protocol)。

| Method | 路徑 | 說明 |
|--------|------|------|
| `GET` | `/api/v1/workspaces/{workspace_id}/canvas/detect` | 偵測 Canvas 專案類型 |
| `GET` | `/api/v1/workspaces/{workspace_id}/canvas/routes` | 取得可用路由清單 |
| `GET` | `/api/v1/workspaces/{workspace_id}/canvas/health` | Canvas dev server 健康檢查 |
| `GET` | `/api/v1/workspaces/{workspace_id}/canvas/logs` | 取得 Canvas 執行日誌 |
| `POST` | `/api/v1/workspaces/{workspace_id}/canvas/sync` | 同步／啟動 Canvas |
| `POST` | `/api/v1/workspaces/{workspace_id}/canvas/reset` | 重設 Canvas 狀態 |
| `GET`／`POST` | `/api/v1/workspaces/{workspace_id}/canvas/review-notes` | 列出或建立 review note |
| `PATCH` | `/api/v1/workspaces/{workspace_id}/canvas/review-notes/{note_id}/status` | 更新 review note 狀態 |
| `POST` | `/api/v1/workspaces/{workspace_id}/canvas/review-notes/{note_id}/replies` | 回覆 review note |
| `DELETE` | `/api/v1/workspaces/{workspace_id}/canvas/review-notes/{note_id}` | 刪除 review note |
| `DELETE` | `/api/v1/workspaces/{workspace_id}/canvas/manifest` | 停用 Canvas manifest |

## 第三方工具整合

| Method | 路徑 | 說明 |
|--------|------|------|
| `POST` | `/api/v1/audio/transcriptions` | 語音轉文字 |

## Client Browser Relay

供瀏覽器擴充功能與 Runtime 之間中繼 CDP（Chrome DevTools Protocol）連線；權限與 pairing 流程見 [Execution-Plane 生命週期與安全機制 — Browser extension pairing 安全](/architecture/overview/execution-plane#browser-extension-pairing-安全)。

| Method | 路徑 | 說明 |
|--------|------|------|
| `GET` | `/api/v1/client-browser-relay/health` | 健康檢查 |
| `GET` | `/api/v1/client-browser-relay` | 查詢 relay 狀態 |
| `GET`／`POST` | `/api/v1/client-browser-relay/pages` | 列出或建立可中繼的頁面 |
| `DELETE` | `/api/v1/client-browser-relay/pages/{name}` | 刪除 named page |
| `WS` | `/api/v1/client-browser-relay/cdp`、`/api/v1/client-browser-relay/cdp/{client_id}` | CDP client 連線 |
| `WS` | `/api/v1/client-browser-relay/extension` | 瀏覽器擴充功能連線 |

<!-- authorization-contract:runtime:start -->
<!-- generated by docs-site/scripts/check-authorization-contract.mjs -->
| Route template | Methods | Action | 優先序 | 敏感 | 說明 |
| --- | --- | --- | --- | --- | --- |
| `/api/v1/workspaces/{workspace_id}/claude-code/mcp-servers/{scope}/{server_name}/export` | `GET` | `workspace_settings` | `4043` | 是 | `GET` `/api/v1/workspaces/{workspace_id}/claude-code/mcp-servers/{scope}/{server_name}/export` 對應 `workspace_settings`；敏感路由：是。 |
| `/api/v1/workspaces/{workspace_id}/claude-code/mcp-servers/{scope}/{server_name}/toggle` | `PATCH` | `workspace_settings` | `4043` | 是 | `PATCH` `/api/v1/workspaces/{workspace_id}/claude-code/mcp-servers/{scope}/{server_name}/toggle` 對應 `workspace_settings`；敏感路由：是。 |
| `/api/v1/workspaces/{workspace_id}/agent-settings/cache/refresh` | `POST` | `workspace_settings` | `4041` | 是 | `POST` `/api/v1/workspaces/{workspace_id}/agent-settings/cache/refresh` 對應 `workspace_settings`；敏感路由：是。 |
| `/api/v1/workspaces/{workspace_id}/opencode/mcp-servers/{scope}/{server_name}/export` | `GET` | `workspace_settings` | `4040` | 是 | `GET` `/api/v1/workspaces/{workspace_id}/opencode/mcp-servers/{scope}/{server_name}/export` 對應 `workspace_settings`；敏感路由：是。 |
| `/api/v1/workspaces/{workspace_id}/opencode/mcp-servers/{scope}/{server_name}/toggle` | `PATCH` | `workspace_settings` | `4040` | 是 | `PATCH` `/api/v1/workspaces/{workspace_id}/opencode/mcp-servers/{scope}/{server_name}/toggle` 對應 `workspace_settings`；敏感路由：是。 |
| `/api/v1/workspaces/{workspace_id}/claude-code/mcp-servers` | `GET` | `workspace_settings` | `4037` | 是 | `GET` `/api/v1/workspaces/{workspace_id}/claude-code/mcp-servers` 對應 `workspace_settings`；敏感路由：是。 |
| `/api/v1/workspaces/{workspace_id}/claude-code/mcp-servers/{scope}` | `GET`, `POST` | `workspace_settings` | `4037` | 是 | `GET`, `POST` `/api/v1/workspaces/{workspace_id}/claude-code/mcp-servers/{scope}` 對應 `workspace_settings`；敏感路由：是。 |
| `/api/v1/workspaces/{workspace_id}/claude-code/mcp-servers/{scope}/{server_name}` | `DELETE`, `GET`, `PUT` | `workspace_settings` | `4037` | 是 | `DELETE`, `GET`, `PUT` `/api/v1/workspaces/{workspace_id}/claude-code/mcp-servers/{scope}/{server_name}` 對應 `workspace_settings`；敏感路由：是。 |
| `/api/v1/workspaces/{workspace_id}/claude-code/settings/raw` | `GET`, `PUT` | `workspace_settings` | `4037` | 是 | `GET`, `PUT` `/api/v1/workspaces/{workspace_id}/claude-code/settings/raw` 對應 `workspace_settings`；敏感路由：是。 |
| `/api/v1/workspaces/{workspace_id}/codex/mcp-servers/{scope}/{server_name}/export` | `GET` | `workspace_settings` | `4037` | 是 | `GET` `/api/v1/workspaces/{workspace_id}/codex/mcp-servers/{scope}/{server_name}/export` 對應 `workspace_settings`；敏感路由：是。 |
| `/api/v1/workspaces/{workspace_id}/codex/mcp-servers/{scope}/{server_name}/toggle` | `PATCH` | `workspace_settings` | `4037` | 是 | `PATCH` `/api/v1/workspaces/{workspace_id}/codex/mcp-servers/{scope}/{server_name}/toggle` 對應 `workspace_settings`；敏感路由：是。 |
| `/api/v1/workspaces/{workspace_id}/claude-code/mcp-import` | `POST` | `workspace_settings` | `4036` | 是 | `POST` `/api/v1/workspaces/{workspace_id}/claude-code/mcp-import` 對應 `workspace_settings`；敏感路由：是。 |
| `/api/v1/workspaces/{workspace_id}/claude-code/settings` | `GET`, `PUT` | `workspace_settings` | `4034` | 是 | `GET`, `PUT` `/api/v1/workspaces/{workspace_id}/claude-code/settings` 對應 `workspace_settings`；敏感路由：是。 |
| `/api/v1/workspaces/{workspace_id}/opencode/mcp-servers` | `GET` | `workspace_settings` | `4034` | 是 | `GET` `/api/v1/workspaces/{workspace_id}/opencode/mcp-servers` 對應 `workspace_settings`；敏感路由：是。 |
| `/api/v1/workspaces/{workspace_id}/opencode/mcp-servers/{scope}` | `GET`, `POST` | `workspace_settings` | `4034` | 是 | `GET`, `POST` `/api/v1/workspaces/{workspace_id}/opencode/mcp-servers/{scope}` 對應 `workspace_settings`；敏感路由：是。 |
| `/api/v1/workspaces/{workspace_id}/opencode/mcp-servers/{scope}/{server_name}` | `DELETE`, `GET`, `PUT` | `workspace_settings` | `4034` | 是 | `DELETE`, `GET`, `PUT` `/api/v1/workspaces/{workspace_id}/opencode/mcp-servers/{scope}/{server_name}` 對應 `workspace_settings`；敏感路由：是。 |
| `/api/v1/workspaces/{workspace_id}/opencode/mcp-import` | `POST` | `workspace_settings` | `4033` | 是 | `POST` `/api/v1/workspaces/{workspace_id}/opencode/mcp-import` 對應 `workspace_settings`；敏感路由：是。 |
| `/api/v1/workspaces/{workspace_id}/codex/mcp-servers` | `GET` | `workspace_settings` | `4031` | 是 | `GET` `/api/v1/workspaces/{workspace_id}/codex/mcp-servers` 對應 `workspace_settings`；敏感路由：是。 |
| `/api/v1/workspaces/{workspace_id}/codex/mcp-servers/{scope}` | `GET`, `POST` | `workspace_settings` | `4031` | 是 | `GET`, `POST` `/api/v1/workspaces/{workspace_id}/codex/mcp-servers/{scope}` 對應 `workspace_settings`；敏感路由：是。 |
| `/api/v1/workspaces/{workspace_id}/codex/mcp-servers/{scope}/{server_name}` | `DELETE`, `GET`, `PUT` | `workspace_settings` | `4031` | 是 | `DELETE`, `GET`, `PUT` `/api/v1/workspaces/{workspace_id}/codex/mcp-servers/{scope}/{server_name}` 對應 `workspace_settings`；敏感路由：是。 |
| `/api/v1/workspaces/{workspace_id}/codex/mcp-import` | `POST` | `workspace_settings` | `4030` | 是 | `POST` `/api/v1/workspaces/{workspace_id}/codex/mcp-import` 對應 `workspace_settings`；敏感路由：是。 |
| `/api/v1/workspaces/{workspace_id}/codex/config` | `GET`, `PUT` | `workspace_settings` | `4026` | 是 | `GET`, `PUT` `/api/v1/workspaces/{workspace_id}/codex/config` 對應 `workspace_settings`；敏感路由：是。 |
| `/api/v1/workspaces/{workspace_id}/codex/config/{section}` | `GET`, `PUT` | `workspace_settings` | `4026` | 是 | `GET`, `PUT` `/api/v1/workspaces/{workspace_id}/codex/config/{section}` 對應 `workspace_settings`；敏感路由：是。 |
| `/api/v1/workspaces/{workspace_id}/codex/plugins/{plugin_id:path}/mcp-servers/{server_id:path}/policy` | `PATCH` | `workspace_settings` | `3544` | 是 | `PATCH` `/api/v1/workspaces/{workspace_id}/codex/plugins/{plugin_id:path}/mcp-servers/{server_id:path}/policy` 對應 `workspace_settings`；敏感路由：是。 |
| `/api/v1/threads/by-automation-execution/{execution_id}` | `GET` | `agent` | `3035` | 否 | `GET` `/api/v1/threads/by-automation-execution/{execution_id}` 對應 `agent`；敏感路由：否。 |
| `/api/v1/threads/{thread_id}/timeline/items/batch-get` | `POST` | `agent` | `3034` | 否 | `POST` `/api/v1/threads/{thread_id}/timeline/items/batch-get` 對應 `agent`；敏感路由：否。 |
| `/api/v1/threads/{thread_id}/messages/{message_id}/tool-result` | `GET` | `agent` | `3031` | 否 | `GET` `/api/v1/threads/{thread_id}/messages/{message_id}/tool-result` 對應 `agent`；敏感路由：否。 |
| `/api/v1/client-browser-relay/pages` | `GET`, `POST` | `browser_automation` | `3030` | 否 | `GET`, `POST` `/api/v1/client-browser-relay/pages` 對應 `browser_automation`；敏感路由：否。 |
| `/api/v1/client-browser-relay/pages/{name}` | `DELETE` | `browser_automation` | `3030` | 否 | `DELETE` `/api/v1/client-browser-relay/pages/{name}` 對應 `browser_automation`；敏感路由：否。 |
| `/api/v1/threads/{thread_id}/questions/{message_id}/answer` | `POST` | `agent` | `3027` | 否 | `POST` `/api/v1/threads/{thread_id}/questions/{message_id}/answer` 對應 `agent`；敏感路由：否。 |
| `/api/v1/threads/{thread_id}/queued-messages/{queued_message_id}` | `DELETE` | `agent` | `3027` | 否 | `DELETE` `/api/v1/threads/{thread_id}/queued-messages/{queued_message_id}` 對應 `agent`；敏感路由：否。 |
| `/api/v1/client-browser-relay` | `GET` | `browser_automation` | `3025` | 否 | `GET` `/api/v1/client-browser-relay` 對應 `browser_automation`；敏感路由：否。 |
| `/api/v1/audio/transcriptions` | `POST` | `agent` | `3024` | 否 | `POST` `/api/v1/audio/transcriptions` 對應 `agent`；敏感路由：否。 |
| `/api/v1/threads/{thread_id}/attachments` | `GET`, `POST` | `agent` | `3023` | 否 | `GET`, `POST` `/api/v1/threads/{thread_id}/attachments` 對應 `agent`；敏感路由：否。 |
| `/api/v1/threads/{thread_id}/attachments/{attachment_id}` | `DELETE` | `agent` | `3023` | 否 | `DELETE` `/api/v1/threads/{thread_id}/attachments/{attachment_id}` 對應 `agent`；敏感路由：否。 |
| `/api/v1/threads/{thread_id}/messages` | `POST` | `agent` | `3020` | 否 | `POST` `/api/v1/threads/{thread_id}/messages` 對應 `agent`；敏感路由：否。 |
| `/api/v1/threads/{thread_id}/timeline` | `GET` | `agent` | `3020` | 否 | `GET` `/api/v1/threads/{thread_id}/timeline` 對應 `agent`；敏感路由：否。 |
| `/api/v1/threads/{thread_id}/archive` | `POST` | `agent` | `3019` | 否 | `POST` `/api/v1/threads/{thread_id}/archive` 對應 `agent`；敏感路由：否。 |
| `/api/v1/threads/{thread_id}/submit` | `POST` | `agent` | `3018` | 否 | `POST` `/api/v1/threads/{thread_id}/submit` 對應 `agent`；敏感路由：否。 |
| `/api/v1/threads/draft` | `POST` | `agent` | `3017` | 否 | `POST` `/api/v1/threads/draft` 對應 `agent`；敏感路由：否。 |
| `/api/v1/threads/{thread_id}/draft` | `PATCH` | `agent` | `3017` | 否 | `PATCH` `/api/v1/threads/{thread_id}/draft` 對應 `agent`；敏感路由：否。 |
| `/api/v1/threads/{thread_id}/retry` | `POST` | `agent` | `3017` | 否 | `POST` `/api/v1/threads/{thread_id}/retry` 對應 `agent`；敏感路由：否。 |
| `/api/v1/threads/{thread_id}/stop` | `POST` | `agent` | `3016` | 否 | `POST` `/api/v1/threads/{thread_id}/stop` 對應 `agent`；敏感路由：否。 |
| `/api/v1/threads` | `GET` | `agent` | `3012` | 否 | `GET` `/api/v1/threads` 對應 `agent`；敏感路由：否。 |
| `/api/v1/threads/{thread_id}` | `DELETE`, `GET` | `agent` | `3012` | 否 | `DELETE`, `GET` `/api/v1/threads/{thread_id}` 對應 `agent`；敏感路由：否。 |
| `/api/v1/workspaces/{workspace_id}/version-control/conflicts/mark-resolved` | `POST` | `runtime_write` | `2052` | 否 | `POST` `/api/v1/workspaces/{workspace_id}/version-control/conflicts/mark-resolved` 對應 `runtime_write`；敏感路由：否。 |
| `/api/v1/workspaces/{workspace_id}/claude-code/skills/conflicts/preflight` | `POST` | `runtime_write` | `2050` | 否 | `POST` `/api/v1/workspaces/{workspace_id}/claude-code/skills/conflicts/preflight` 對應 `runtime_write`；敏感路由：否。 |
| `/api/v1/workspaces/{workspace_id}/claude-code/slash-commands/{scope}/content` | `DELETE`, `PUT` | `runtime_write` | `2047` | 否 | `DELETE`, `PUT` `/api/v1/workspaces/{workspace_id}/claude-code/slash-commands/{scope}/content` 對應 `runtime_write`；敏感路由：否。 |
| `/api/v1/workspaces/{workspace_id}/opencode/skills/conflicts/preflight` | `POST` | `runtime_write` | `2047` | 否 | `POST` `/api/v1/workspaces/{workspace_id}/opencode/skills/conflicts/preflight` 對應 `runtime_write`；敏感路由：否。 |
| `/api/v1/workspaces/{workspace_id}/version-control/branches/publish` | `POST` | `runtime_write` | `2045` | 否 | `POST` `/api/v1/workspaces/{workspace_id}/version-control/branches/publish` 對應 `runtime_write`；敏感路由：否。 |
| `/api/v1/workspaces/{workspace_id}/version-control/operation/cancel` | `POST` | `runtime_write` | `2045` | 否 | `POST` `/api/v1/workspaces/{workspace_id}/version-control/operation/cancel` 對應 `runtime_write`；敏感路由：否。 |
| `/api/v1/workspaces/{workspace_id}/version-control/remote-branches` | `POST` | `runtime_write` | `2045` | 否 | `POST` `/api/v1/workspaces/{workspace_id}/version-control/remote-branches` 對應 `runtime_write`；敏感路由：否。 |
| `/api/v1/workspaces/{workspace_id}/claude-code/skills/batch-delete` | `POST` | `runtime_write` | `2044` | 否 | `POST` `/api/v1/workspaces/{workspace_id}/claude-code/skills/batch-delete` 對應 `runtime_write`；敏感路由：否。 |
| `/api/v1/workspaces/{workspace_id}/codex/skills/conflicts/preflight` | `POST` | `runtime_write` | `2044` | 否 | `POST` `/api/v1/workspaces/{workspace_id}/codex/skills/conflicts/preflight` 對應 `runtime_write`；敏感路由：否。 |
| `/api/v1/workspaces/{workspace_id}/opencode/slash-commands/{scope}/content` | `DELETE`, `PUT` | `runtime_write` | `2044` | 否 | `DELETE`, `PUT` `/api/v1/workspaces/{workspace_id}/opencode/slash-commands/{scope}/content` 對應 `runtime_write`；敏感路由：否。 |
| `/api/v1/workspaces/{workspace_id}/version-control/branches/create` | `POST` | `runtime_write` | `2044` | 否 | `POST` `/api/v1/workspaces/{workspace_id}/version-control/branches/create` 對應 `runtime_write`；敏感路由：否。 |
| `/api/v1/workspaces/{workspace_id}/version-control/branches/delete` | `POST` | `runtime_write` | `2044` | 否 | `POST` `/api/v1/workspaces/{workspace_id}/version-control/branches/delete` 對應 `runtime_write`；敏感路由：否。 |
| `/api/v1/workspaces/{workspace_id}/version-control/branches/rename` | `POST` | `runtime_write` | `2044` | 否 | `POST` `/api/v1/workspaces/{workspace_id}/version-control/branches/rename` 對應 `runtime_write`；敏感路由：否。 |
| `/api/v1/workspaces/{workspace_id}/version-control/branches/switch` | `POST` | `runtime_write` | `2044` | 否 | `POST` `/api/v1/workspaces/{workspace_id}/version-control/branches/switch` 對應 `runtime_write`；敏感路由：否。 |
| `/api/v1/workspaces/{workspace_id}/version-control/changes/numstat` | `POST` | `runtime_write` | `2044` | 否 | `POST` `/api/v1/workspaces/{workspace_id}/version-control/changes/numstat` 對應 `runtime_write`；敏感路由：否。 |
| `/api/v1/workspaces/{workspace_id}/version-control/conflicts/abort` | `POST` | `runtime_write` | `2044` | 否 | `POST` `/api/v1/workspaces/{workspace_id}/version-control/conflicts/abort` 對應 `runtime_write`；敏感路由：否。 |
| `/api/v1/workspaces/{workspace_id}/version-control/commits/revert` | `POST` | `runtime_write` | `2043` | 否 | `POST` `/api/v1/workspaces/{workspace_id}/version-control/commits/revert` 對應 `runtime_write`；敏感路由：否。 |
| `/api/v1/workspaces/{workspace_id}/claude-code/subagents/{scope}/content` | `DELETE`, `PUT` | `runtime_write` | `2042` | 否 | `DELETE`, `PUT` `/api/v1/workspaces/{workspace_id}/claude-code/subagents/{scope}/content` 對應 `runtime_write`；敏感路由：否。 |
| `/api/v1/workspaces/{workspace_id}/version-control/force-unlock` | `POST` | `runtime_write` | `2042` | 否 | `POST` `/api/v1/workspaces/{workspace_id}/version-control/force-unlock` 對應 `runtime_write`；敏感路由：否。 |
| `/api/v1/workspaces/{workspace_id}/codex/slash-commands/{scope}/content` | `DELETE`, `PUT` | `runtime_write` | `2041` | 否 | `DELETE`, `PUT` `/api/v1/workspaces/{workspace_id}/codex/slash-commands/{scope}/content` 對應 `runtime_write`；敏感路由：否。 |
| `/api/v1/workspaces/{workspace_id}/opencode/skills/batch-delete` | `POST` | `runtime_write` | `2041` | 否 | `POST` `/api/v1/workspaces/{workspace_id}/opencode/skills/batch-delete` 對應 `runtime_write`；敏感路由：否。 |
| `/api/v1/workspaces/{workspace_id}/canvas/review-notes/{note_id}/replies` | `POST` | `runtime_write` | `2040` | 否 | `POST` `/api/v1/workspaces/{workspace_id}/canvas/review-notes/{note_id}/replies` 對應 `runtime_write`；敏感路由：否。 |
| `/api/v1/workspaces/{workspace_id}/claude-code/slash-commands/{scope}` | `POST` | `runtime_write` | `2040` | 否 | `POST` `/api/v1/workspaces/{workspace_id}/claude-code/slash-commands/{scope}` 對應 `runtime_write`；敏感路由：否。 |
| `/api/v1/workspaces/{workspace_id}/version-control/lfs/convert` | `POST` | `runtime_write` | `2040` | 否 | `POST` `/api/v1/workspaces/{workspace_id}/version-control/lfs/convert` 對應 `runtime_write`；敏感路由：否。 |
| `/api/v1/workspaces/{workspace_id}/version-control/lfs/preview` | `POST` | `runtime_write` | `2040` | 否 | `POST` `/api/v1/workspaces/{workspace_id}/version-control/lfs/preview` 對應 `runtime_write`；敏感路由：否。 |
| `/api/v1/workspaces/{workspace_id}/canvas/review-notes/{note_id}/status` | `PATCH` | `runtime_write` | `2039` | 否 | `PATCH` `/api/v1/workspaces/{workspace_id}/canvas/review-notes/{note_id}/status` 對應 `runtime_write`；敏感路由：否。 |
| `/api/v1/workspaces/{workspace_id}/claude-code/memory/{scope}/content` | `DELETE`, `PUT` | `runtime_write` | `2039` | 否 | `DELETE`, `PUT` `/api/v1/workspaces/{workspace_id}/claude-code/memory/{scope}/content` 對應 `runtime_write`；敏感路由：否。 |
| `/api/v1/workspaces/{workspace_id}/claude-code/output-styles/{scope}` | `POST` | `runtime_write` | `2039` | 否 | `POST` `/api/v1/workspaces/{workspace_id}/claude-code/output-styles/{scope}` 對應 `runtime_write`；敏感路由：否。 |
| `/api/v1/workspaces/{workspace_id}/claude-code/output-styles/{scope}/{file_name}` | `DELETE`, `PUT` | `runtime_write` | `2039` | 否 | `DELETE`, `PUT` `/api/v1/workspaces/{workspace_id}/claude-code/output-styles/{scope}/{file_name}` 對應 `runtime_write`；敏感路由：否。 |
| `/api/v1/workspaces/{workspace_id}/claude-code/skills/content` | `PUT` | `runtime_write` | `2039` | 否 | `PUT` `/api/v1/workspaces/{workspace_id}/claude-code/skills/content` 對應 `runtime_write`；敏感路由：否。 |
| `/api/v1/workspaces/{workspace_id}/claude-code/skills/extract` | `POST` | `runtime_write` | `2039` | 否 | `POST` `/api/v1/workspaces/{workspace_id}/claude-code/skills/extract` 對應 `runtime_write`；敏感路由：否。 |
| `/api/v1/workspaces/{workspace_id}/opencode/subagents/{scope}/content` | `DELETE`, `PUT` | `runtime_write` | `2039` | 否 | `DELETE`, `PUT` `/api/v1/workspaces/{workspace_id}/opencode/subagents/{scope}/content` 對應 `runtime_write`；敏感路由：否。 |
| `/api/v1/workspaces/{workspace_id}/claude-code/skills/upload` | `POST` | `runtime_write` | `2038` | 否 | `POST` `/api/v1/workspaces/{workspace_id}/claude-code/skills/upload` 對應 `runtime_write`；敏感路由：否。 |
| `/api/v1/workspaces/{workspace_id}/codex/skills/batch-delete` | `POST` | `runtime_write` | `2038` | 否 | `POST` `/api/v1/workspaces/{workspace_id}/codex/skills/batch-delete` 對應 `runtime_write`；敏感路由：否。 |
| `/api/v1/workspaces/{workspace_id}/claude-code/hooks/import` | `POST` | `runtime_write` | `2037` | 否 | `POST` `/api/v1/workspaces/{workspace_id}/claude-code/hooks/import` 對應 `runtime_write`；敏感路由：否。 |
| `/api/v1/workspaces/{workspace_id}/codex/plugins/{plugin_id:path}/hook-trust` | `PATCH` | `runtime_write` | `2037` | 否 | `PATCH` `/api/v1/workspaces/{workspace_id}/codex/plugins/{plugin_id:path}/hook-trust` 對應 `runtime_write`；敏感路由：否。 |
| `/api/v1/workspaces/{workspace_id}/opencode/slash-commands/{scope}` | `POST` | `runtime_write` | `2037` | 否 | `POST` `/api/v1/workspaces/{workspace_id}/opencode/slash-commands/{scope}` 對應 `runtime_write`；敏感路由：否。 |
| `/api/v1/workspaces/{workspace_id}/version-control/discard` | `POST` | `runtime_write` | `2037` | 否 | `POST` `/api/v1/workspaces/{workspace_id}/version-control/discard` 對應 `runtime_write`；敏感路由：否。 |
| `/api/v1/workspaces/{workspace_id}/version-control/unstage` | `POST` | `runtime_write` | `2037` | 否 | `POST` `/api/v1/workspaces/{workspace_id}/version-control/unstage` 對應 `runtime_write`；敏感路由：否。 |
| `/api/v1/workspaces/{workspace_id}/claude-code/skills/move` | `POST` | `runtime_write` | `2036` | 否 | `POST` `/api/v1/workspaces/{workspace_id}/claude-code/skills/move` 對應 `runtime_write`；敏感路由：否。 |
| `/api/v1/workspaces/{workspace_id}/opencode/skills/content` | `PUT` | `runtime_write` | `2036` | 否 | `PUT` `/api/v1/workspaces/{workspace_id}/opencode/skills/content` 對應 `runtime_write`；敏感路由：否。 |
| `/api/v1/workspaces/{workspace_id}/opencode/skills/extract` | `POST` | `runtime_write` | `2036` | 否 | `POST` `/api/v1/workspaces/{workspace_id}/opencode/skills/extract` 對應 `runtime_write`；敏感路由：否。 |
| `/api/v1/workspaces/{workspace_id}/version-control/commit` | `POST` | `runtime_write` | `2036` | 否 | `POST` `/api/v1/workspaces/{workspace_id}/version-control/commit` 對應 `runtime_write`；敏感路由：否。 |
| `/api/v1/workspaces/{workspace_id}/version-control/remote` | `PUT` | `runtime_write` | `2036` | 否 | `PUT` `/api/v1/workspaces/{workspace_id}/version-control/remote` 對應 `runtime_write`；敏感路由：否。 |
| `/api/v1/workspaces/{workspace_id}/claude-code/claude-md` | `PUT` | `runtime_write` | `2035` | 否 | `PUT` `/api/v1/workspaces/{workspace_id}/claude-code/claude-md` 對應 `runtime_write`；敏感路由：否。 |
| `/api/v1/workspaces/{workspace_id}/claude-code/subagents/{scope}` | `POST` | `runtime_write` | `2035` | 否 | `POST` `/api/v1/workspaces/{workspace_id}/claude-code/subagents/{scope}` 對應 `runtime_write`；敏感路由：否。 |
| `/api/v1/workspaces/{workspace_id}/opencode/skills/upload` | `POST` | `runtime_write` | `2035` | 否 | `POST` `/api/v1/workspaces/{workspace_id}/opencode/skills/upload` 對應 `runtime_write`；敏感路由：否。 |
| `/api/v1/workspaces/{workspace_id}/version-control/clone` | `POST` | `runtime_write` | `2035` | 否 | `POST` `/api/v1/workspaces/{workspace_id}/version-control/clone` 對應 `runtime_write`；敏感路由：否。 |
| `/api/v1/workspaces/{workspace_id}/version-control/fetch` | `POST` | `runtime_write` | `2035` | 否 | `POST` `/api/v1/workspaces/{workspace_id}/version-control/fetch` 對應 `runtime_write`；敏感路由：否。 |
| `/api/v1/workspaces/{workspace_id}/version-control/stage` | `POST` | `runtime_write` | `2035` | 否 | `POST` `/api/v1/workspaces/{workspace_id}/version-control/stage` 對應 `runtime_write`；敏感路由：否。 |
| `/api/v1/workspaces/{workspace_id}/codex/slash-commands/{scope}` | `POST` | `runtime_write` | `2034` | 否 | `POST` `/api/v1/workspaces/{workspace_id}/codex/slash-commands/{scope}` 對應 `runtime_write`；敏感路由：否。 |
| `/api/v1/workspaces/{workspace_id}/version-control/init` | `POST` | `runtime_write` | `2034` | 否 | `POST` `/api/v1/workspaces/{workspace_id}/version-control/init` 對應 `runtime_write`；敏感路由：否。 |
| `/api/v1/workspaces/{workspace_id}/version-control/pull` | `POST` | `runtime_write` | `2034` | 否 | `POST` `/api/v1/workspaces/{workspace_id}/version-control/pull` 對應 `runtime_write`；敏感路由：否。 |
| `/api/v1/workspaces/{workspace_id}/version-control/push` | `POST` | `runtime_write` | `2034` | 否 | `POST` `/api/v1/workspaces/{workspace_id}/version-control/push` 對應 `runtime_write`；敏感路由：否。 |
| `/api/v1/workspaces/{workspace_id}/canvas/review-notes` | `POST` | `runtime_write` | `2033` | 否 | `POST` `/api/v1/workspaces/{workspace_id}/canvas/review-notes` 對應 `runtime_write`；敏感路由：否。 |
| `/api/v1/workspaces/{workspace_id}/canvas/review-notes/{note_id}` | `DELETE` | `runtime_write` | `2033` | 否 | `DELETE` `/api/v1/workspaces/{workspace_id}/canvas/review-notes/{note_id}` 對應 `runtime_write`；敏感路由：否。 |
| `/api/v1/workspaces/{workspace_id}/claude-code/plugins/{plugin_id:path}` | `PATCH` | `runtime_write` | `2033` | 否 | `PATCH` `/api/v1/workspaces/{workspace_id}/claude-code/plugins/{plugin_id:path}` 對應 `runtime_write`；敏感路由：否。 |
| `/api/v1/workspaces/{workspace_id}/codex/overview/trust` | `PATCH` | `runtime_write` | `2033` | 否 | `PATCH` `/api/v1/workspaces/{workspace_id}/codex/overview/trust` 對應 `runtime_write`；敏感路由：否。 |
| `/api/v1/workspaces/{workspace_id}/codex/rules/validate` | `POST` | `runtime_write` | `2033` | 否 | `POST` `/api/v1/workspaces/{workspace_id}/codex/rules/validate` 對應 `runtime_write`；敏感路由：否。 |
| `/api/v1/workspaces/{workspace_id}/codex/skills/content` | `PUT` | `runtime_write` | `2033` | 否 | `PUT` `/api/v1/workspaces/{workspace_id}/codex/skills/content` 對應 `runtime_write`；敏感路由：否。 |
| `/api/v1/workspaces/{workspace_id}/codex/skills/extract` | `POST` | `runtime_write` | `2033` | 否 | `POST` `/api/v1/workspaces/{workspace_id}/codex/skills/extract` 對應 `runtime_write`；敏感路由：否。 |
| `/api/v1/workspaces/{workspace_id}/opencode/skills/move` | `POST` | `runtime_write` | `2033` | 否 | `POST` `/api/v1/workspaces/{workspace_id}/opencode/skills/move` 對應 `runtime_write`；敏感路由：否。 |
| `/api/v1/workspaces/{workspace_id}/version-control/lfs` | `POST` | `runtime_write` | `2033` | 否 | `POST` `/api/v1/workspaces/{workspace_id}/version-control/lfs` 對應 `runtime_write`；敏感路由：否。 |
| `/api/v1/workspaces/{workspace_id}/claude-code/memory/{scope}` | `POST` | `runtime_write` | `2032` | 否 | `POST` `/api/v1/workspaces/{workspace_id}/claude-code/memory/{scope}` 對應 `runtime_write`；敏感路由：否。 |
| `/api/v1/workspaces/{workspace_id}/claude-code/skills` | `DELETE`, `POST` | `runtime_write` | `2032` | 否 | `DELETE`, `POST` `/api/v1/workspaces/{workspace_id}/claude-code/skills` 對應 `runtime_write`；敏感路由：否。 |
| `/api/v1/workspaces/{workspace_id}/codex/hooks/{scope}/disable` | `POST` | `runtime_write` | `2032` | 否 | `POST` `/api/v1/workspaces/{workspace_id}/codex/hooks/{scope}/disable` 對應 `runtime_write`；敏感路由：否。 |
| `/api/v1/workspaces/{workspace_id}/codex/skills/upload` | `POST` | `runtime_write` | `2032` | 否 | `POST` `/api/v1/workspaces/{workspace_id}/codex/skills/upload` 對應 `runtime_write`；敏感路由：否。 |
| `/api/v1/workspaces/{workspace_id}/opencode/agents-md` | `PUT` | `runtime_write` | `2032` | 否 | `PUT` `/api/v1/workspaces/{workspace_id}/opencode/agents-md` 對應 `runtime_write`；敏感路由：否。 |
| `/api/v1/workspaces/{workspace_id}/opencode/subagents/{scope}` | `POST` | `runtime_write` | `2032` | 否 | `POST` `/api/v1/workspaces/{workspace_id}/opencode/subagents/{scope}` 對應 `runtime_write`；敏感路由：否。 |
| `/api/v1/workspaces/{workspace_id}/claude-code/hooks/{scope}` | `DELETE`, `PUT` | `runtime_write` | `2031` | 否 | `DELETE`, `PUT` `/api/v1/workspaces/{workspace_id}/claude-code/hooks/{scope}` 對應 `runtime_write`；敏感路由：否。 |
| `/api/v1/workspaces/{workspace_id}/codex/hooks/{scope}/enable` | `POST` | `runtime_write` | `2031` | 否 | `POST` `/api/v1/workspaces/{workspace_id}/codex/hooks/{scope}/enable` 對應 `runtime_write`；敏感路由：否。 |
| `/api/v1/workspaces/{workspace_id}/codex/hooks/{scope}/entry` | `DELETE`, `PUT` | `runtime_write` | `2030` | 否 | `DELETE`, `PUT` `/api/v1/workspaces/{workspace_id}/codex/hooks/{scope}/entry` 對應 `runtime_write`；敏感路由：否。 |
| `/api/v1/workspaces/{workspace_id}/codex/skills/move` | `POST` | `runtime_write` | `2030` | 否 | `POST` `/api/v1/workspaces/{workspace_id}/codex/skills/move` 對應 `runtime_write`；敏感路由：否。 |
| `/api/v1/workspaces/{workspace_id}/canvas/manifest` | `DELETE` | `runtime_write` | `2029` | 否 | `DELETE` `/api/v1/workspaces/{workspace_id}/canvas/manifest` 對應 `runtime_write`；敏感路由：否。 |
| `/api/v1/workspaces/{workspace_id}/codex/agents-md` | `PUT` | `runtime_write` | `2029` | 否 | `PUT` `/api/v1/workspaces/{workspace_id}/codex/agents-md` 對應 `runtime_write`；敏感路由：否。 |
| `/api/v1/workspaces/{workspace_id}/codex/rules/file` | `DELETE`, `PUT` | `runtime_write` | `2029` | 否 | `DELETE`, `PUT` `/api/v1/workspaces/{workspace_id}/codex/rules/file` 對應 `runtime_write`；敏感路由：否。 |
| `/api/v1/workspaces/{workspace_id}/codex/subagents` | `DELETE`, `POST`, `PUT` | `runtime_write` | `2029` | 否 | `DELETE`, `POST`, `PUT` `/api/v1/workspaces/{workspace_id}/codex/subagents` 對應 `runtime_write`；敏感路由：否。 |
| `/api/v1/workspaces/{workspace_id}/opencode/skills` | `DELETE`, `POST` | `runtime_write` | `2029` | 否 | `DELETE`, `POST` `/api/v1/workspaces/{workspace_id}/opencode/skills` 對應 `runtime_write`；敏感路由：否。 |
| `/api/v1/files/conflicts/preflight` | `POST` | `runtime_write` | `2028` | 否 | `POST` `/api/v1/files/conflicts/preflight` 對應 `runtime_write`；敏感路由：否。 |
| `/api/v1/workspaces/{workspace_id}/codex/plugins/{plugin_id:path}` | `PATCH` | `runtime_write` | `2027` | 否 | `PATCH` `/api/v1/workspaces/{workspace_id}/codex/plugins/{plugin_id:path}` 對應 `runtime_write`；敏感路由：否。 |
| `/api/v1/workspaces/{workspace_id}/canvas/reset` | `POST` | `runtime_write` | `2026` | 否 | `POST` `/api/v1/workspaces/{workspace_id}/canvas/reset` 對應 `runtime_write`；敏感路由：否。 |
| `/api/v1/workspaces/{workspace_id}/codex/skills` | `DELETE`, `POST` | `runtime_write` | `2026` | 否 | `DELETE`, `POST` `/api/v1/workspaces/{workspace_id}/codex/skills` 對應 `runtime_write`；敏感路由：否。 |
| `/api/v1/workspaces/{workspace_id}/canvas/sync` | `POST` | `runtime_write` | `2025` | 否 | `POST` `/api/v1/workspaces/{workspace_id}/canvas/sync` 對應 `runtime_write`；敏感路由：否。 |
| `/api/v1/workspaces/{workspace_id}/codex/hooks/{scope}` | `PUT` | `runtime_write` | `2025` | 否 | `PUT` `/api/v1/workspaces/{workspace_id}/codex/hooks/{scope}` 對應 `runtime_write`；敏感路由：否。 |
| `/api/v1/files/history/{entry_id}/restore` | `POST` | `runtime_write` | `2024` | 否 | `POST` `/api/v1/files/history/{entry_id}/restore` 對應 `runtime_write`；敏感路由：否。 |
| `/api/v1/workspaces/{workspace_id}/codex/{resource}/file` | `DELETE`, `PUT` | `runtime_write` | `2024` | 否 | `DELETE`, `PUT` `/api/v1/workspaces/{workspace_id}/codex/{resource}/file` 對應 `runtime_write`；敏感路由：否。 |
| `/api/v1/files/batch-delete` | `POST` | `runtime_write` | `2022` | 否 | `POST` `/api/v1/files/batch-delete` 對應 `runtime_write`；敏感路由：否。 |
| `/api/v1/files/content/batch` | `POST` | `runtime_write` | `2022` | 否 | `POST` `/api/v1/files/content/batch` 對應 `runtime_write`；敏感路由：否。 |
| `/api/v1/files/archive` | `POST` | `runtime_write` | `2017` | 否 | `POST` `/api/v1/files/archive` 對應 `runtime_write`；敏感路由：否。 |
| `/api/v1/files/content` | `PUT` | `runtime_write` | `2017` | 否 | `PUT` `/api/v1/files/content` 對應 `runtime_write`；敏感路由：否。 |
| `/api/v1/files/extract` | `POST` | `runtime_write` | `2017` | 否 | `POST` `/api/v1/files/extract` 對應 `runtime_write`；敏感路由：否。 |
| `/api/v1/files/upload` | `POST` | `runtime_write` | `2016` | 否 | `POST` `/api/v1/files/upload` 對應 `runtime_write`；敏感路由：否。 |
| `/api/v1/files/paste` | `POST` | `runtime_write` | `2015` | 否 | `POST` `/api/v1/files/paste` 對應 `runtime_write`；敏感路由：否。 |
| `/api/v1/files/move` | `POST` | `runtime_write` | `2014` | 否 | `POST` `/api/v1/files/move` 對應 `runtime_write`；敏感路由：否。 |
| `/api/v1/files` | `DELETE`, `POST` | `runtime_write` | `2010` | 否 | `DELETE`, `POST` `/api/v1/files` 對應 `runtime_write`；敏感路由：否。 |
| `/api/v1/workspaces/{workspace_id}/cli-settings/claude-code/prompt-invocations` | `GET` | `runtime_read` | `1056` | 否 | `GET` `/api/v1/workspaces/{workspace_id}/cli-settings/claude-code/prompt-invocations` 對應 `runtime_read`；敏感路由：否。 |
| `/api/v1/workspaces/{workspace_id}/cli-settings/opencode/prompt-invocations` | `GET` | `runtime_read` | `1053` | 否 | `GET` `/api/v1/workspaces/{workspace_id}/cli-settings/opencode/prompt-invocations` 對應 `runtime_read`；敏感路由：否。 |
| `/api/v1/workspaces/{workspace_id}/cli-settings/codex/prompt-invocations` | `GET` | `runtime_read` | `1050` | 否 | `GET` `/api/v1/workspaces/{workspace_id}/cli-settings/codex/prompt-invocations` 對應 `runtime_read`；敏感路由：否。 |
| `/api/v1/workspaces/{workspace_id}/claude-code/slash-commands/{scope}/content` | `GET` | `runtime_read` | `1047` | 否 | `GET` `/api/v1/workspaces/{workspace_id}/claude-code/slash-commands/{scope}/content` 對應 `runtime_read`；敏感路由：否。 |
| `/api/v1/workspaces/{workspace_id}/version-control/operation-status` | `GET` | `runtime_read` | `1046` | 否 | `GET` `/api/v1/workspaces/{workspace_id}/version-control/operation-status` 對應 `runtime_read`；敏感路由：否。 |
| `/api/v1/workspaces/{workspace_id}/claude-code/skills/tree/children` | `GET` | `runtime_read` | `1044` | 否 | `GET` `/api/v1/workspaces/{workspace_id}/claude-code/skills/tree/children` 對應 `runtime_read`；敏感路由：否。 |
| `/api/v1/workspaces/{workspace_id}/opencode/slash-commands/{scope}/content` | `GET` | `runtime_read` | `1044` | 否 | `GET` `/api/v1/workspaces/{workspace_id}/opencode/slash-commands/{scope}/content` 對應 `runtime_read`；敏感路由：否。 |
| `/api/v1/workspaces/{workspace_id}/claude-code/subagents/{scope}/content` | `GET` | `runtime_read` | `1042` | 否 | `GET` `/api/v1/workspaces/{workspace_id}/claude-code/subagents/{scope}/content` 對應 `runtime_read`；敏感路由：否。 |
| `/api/v1/workspaces/{workspace_id}/version-control/commits/{commit_id}/files` | `GET` | `runtime_read` | `1042` | 否 | `GET` `/api/v1/workspaces/{workspace_id}/version-control/commits/{commit_id}/files` 對應 `runtime_read`；敏感路由：否。 |
| `/api/v1/workspaces/{workspace_id}/codex/slash-commands/{scope}/content` | `GET` | `runtime_read` | `1041` | 否 | `GET` `/api/v1/workspaces/{workspace_id}/codex/slash-commands/{scope}/content` 對應 `runtime_read`；敏感路由：否。 |
| `/api/v1/workspaces/{workspace_id}/opencode/skills/tree/children` | `GET` | `runtime_read` | `1041` | 否 | `GET` `/api/v1/workspaces/{workspace_id}/opencode/skills/tree/children` 對應 `runtime_read`；敏感路由：否。 |
| `/api/v1/workspaces/{workspace_id}/claude-code/slash-commands` | `GET` | `runtime_read` | `1040` | 否 | `GET` `/api/v1/workspaces/{workspace_id}/claude-code/slash-commands` 對應 `runtime_read`；敏感路由：否。 |
| `/api/v1/workspaces/{workspace_id}/claude-code/slash-commands/{scope}` | `GET` | `runtime_read` | `1040` | 否 | `GET` `/api/v1/workspaces/{workspace_id}/claude-code/slash-commands/{scope}` 對應 `runtime_read`；敏感路由：否。 |
| `/api/v1/workspaces/{workspace_id}/codex/managed-requirements` | `GET` | `runtime_read` | `1040` | 否 | `GET` `/api/v1/workspaces/{workspace_id}/codex/managed-requirements` 對應 `runtime_read`；敏感路由：否。 |
| `/api/v1/workspaces/{workspace_id}/version-control/repository` | `GET` | `runtime_read` | `1040` | 否 | `GET` `/api/v1/workspaces/{workspace_id}/version-control/repository` 對應 `runtime_read`；敏感路由：否。 |
| `/api/v1/workspaces/{workspace_id}/claude-code/memory/{scope}/content` | `GET` | `runtime_read` | `1039` | 否 | `GET` `/api/v1/workspaces/{workspace_id}/claude-code/memory/{scope}/content` 對應 `runtime_read`；敏感路由：否。 |
| `/api/v1/workspaces/{workspace_id}/claude-code/output-styles` | `GET` | `runtime_read` | `1039` | 否 | `GET` `/api/v1/workspaces/{workspace_id}/claude-code/output-styles` 對應 `runtime_read`；敏感路由：否。 |
| `/api/v1/workspaces/{workspace_id}/claude-code/output-styles/{scope}` | `GET` | `runtime_read` | `1039` | 否 | `GET` `/api/v1/workspaces/{workspace_id}/claude-code/output-styles/{scope}` 對應 `runtime_read`；敏感路由：否。 |
| `/api/v1/workspaces/{workspace_id}/claude-code/output-styles/{scope}/{file_name:path}` | `GET` | `runtime_read` | `1039` | 否 | `GET` `/api/v1/workspaces/{workspace_id}/claude-code/output-styles/{scope}/{file_name:path}` 對應 `runtime_read`；敏感路由：否。 |
| `/api/v1/workspaces/{workspace_id}/claude-code/skills/content` | `GET` | `runtime_read` | `1039` | 否 | `GET` `/api/v1/workspaces/{workspace_id}/claude-code/skills/content` 對應 `runtime_read`；敏感路由：否。 |
| `/api/v1/workspaces/{workspace_id}/claude-code/skills/plugins` | `GET` | `runtime_read` | `1039` | 否 | `GET` `/api/v1/workspaces/{workspace_id}/claude-code/skills/plugins` 對應 `runtime_read`；敏感路由：否。 |
| `/api/v1/workspaces/{workspace_id}/opencode/subagents/{scope}/content` | `GET` | `runtime_read` | `1039` | 否 | `GET` `/api/v1/workspaces/{workspace_id}/opencode/subagents/{scope}/content` 對應 `runtime_read`；敏感路由：否。 |
| `/api/v1/workspaces/{workspace_id}/codex/skills/tree/children` | `GET` | `runtime_read` | `1038` | 否 | `GET` `/api/v1/workspaces/{workspace_id}/codex/skills/tree/children` 對應 `runtime_read`；敏感路由：否。 |
| `/api/v1/workspaces/{workspace_id}/version-control/branches` | `GET` | `runtime_read` | `1038` | 否 | `GET` `/api/v1/workspaces/{workspace_id}/version-control/branches` 對應 `runtime_read`；敏感路由：否。 |
| `/api/v1/workspaces/{workspace_id}/version-control/contexts` | `GET` | `runtime_read` | `1038` | 否 | `GET` `/api/v1/workspaces/{workspace_id}/version-control/contexts` 對應 `runtime_read`；敏感路由：否。 |
| `/api/v1/workspaces/{workspace_id}/claude-code/hooks/export` | `GET` | `runtime_read` | `1037` | 否 | `GET` `/api/v1/workspaces/{workspace_id}/claude-code/hooks/export` 對應 `runtime_read`；敏感路由：否。 |
| `/api/v1/workspaces/{workspace_id}/opencode/slash-commands` | `GET` | `runtime_read` | `1037` | 否 | `GET` `/api/v1/workspaces/{workspace_id}/opencode/slash-commands` 對應 `runtime_read`；敏感路由：否。 |
| `/api/v1/workspaces/{workspace_id}/opencode/slash-commands/{scope}` | `GET` | `runtime_read` | `1037` | 否 | `GET` `/api/v1/workspaces/{workspace_id}/opencode/slash-commands/{scope}` 對應 `runtime_read`；敏感路由：否。 |
| `/api/v1/workspaces/{workspace_id}/version-control/changes` | `GET` | `runtime_read` | `1037` | 否 | `GET` `/api/v1/workspaces/{workspace_id}/version-control/changes` 對應 `runtime_read`；敏感路由：否。 |
| `/api/v1/workspaces/{workspace_id}/version-control/commits` | `GET` | `runtime_read` | `1037` | 否 | `GET` `/api/v1/workspaces/{workspace_id}/version-control/commits` 對應 `runtime_read`；敏感路由：否。 |
| `/api/v1/workspaces/{workspace_id}/version-control/commits/{commit_id}` | `GET` | `runtime_read` | `1037` | 否 | `GET` `/api/v1/workspaces/{workspace_id}/version-control/commits/{commit_id}` 對應 `runtime_read`；敏感路由：否。 |
| `/api/v1/workspaces/{workspace_id}/claude-code/skills/tree` | `GET` | `runtime_read` | `1036` | 否 | `GET` `/api/v1/workspaces/{workspace_id}/claude-code/skills/tree` 對應 `runtime_read`；敏感路由：否。 |
| `/api/v1/workspaces/{workspace_id}/opencode/skills/content` | `GET` | `runtime_read` | `1036` | 否 | `GET` `/api/v1/workspaces/{workspace_id}/opencode/skills/content` 對應 `runtime_read`；敏感路由：否。 |
| `/api/v1/workspaces/{workspace_id}/version-control/remote` | `GET` | `runtime_read` | `1036` | 否 | `GET` `/api/v1/workspaces/{workspace_id}/version-control/remote` 對應 `runtime_read`；敏感路由：否。 |
| `/api/v1/workspaces/{workspace_id}/version-control/status` | `GET` | `runtime_read` | `1036` | 否 | `GET` `/api/v1/workspaces/{workspace_id}/version-control/status` 對應 `runtime_read`；敏感路由：否。 |
| `/api/v1/workspaces/{workspace_id}/claude-code/claude-md` | `GET` | `runtime_read` | `1035` | 否 | `GET` `/api/v1/workspaces/{workspace_id}/claude-code/claude-md` 對應 `runtime_read`；敏感路由：否。 |
| `/api/v1/workspaces/{workspace_id}/claude-code/subagents` | `GET` | `runtime_read` | `1035` | 否 | `GET` `/api/v1/workspaces/{workspace_id}/claude-code/subagents` 對應 `runtime_read`；敏感路由：否。 |
| `/api/v1/workspaces/{workspace_id}/claude-code/subagents/{scope}` | `GET` | `runtime_read` | `1035` | 否 | `GET` `/api/v1/workspaces/{workspace_id}/claude-code/subagents/{scope}` 對應 `runtime_read`；敏感路由：否。 |
| `/api/v1/workspaces/{workspace_id}/codex/subagents/detail` | `GET` | `runtime_read` | `1035` | 否 | `GET` `/api/v1/workspaces/{workspace_id}/codex/subagents/detail` 對應 `runtime_read`；敏感路由：否。 |
| `/api/v1/workspaces/{workspace_id}/codex/slash-commands` | `GET` | `runtime_read` | `1034` | 否 | `GET` `/api/v1/workspaces/{workspace_id}/codex/slash-commands` 對應 `runtime_read`；敏感路由：否。 |
| `/api/v1/workspaces/{workspace_id}/codex/slash-commands/{scope}` | `GET` | `runtime_read` | `1034` | 否 | `GET` `/api/v1/workspaces/{workspace_id}/codex/slash-commands/{scope}` 對應 `runtime_read`；敏感路由：否。 |
| `/api/v1/workspaces/{workspace_id}/version-control/blob` | `GET` | `runtime_read` | `1034` | 否 | `GET` `/api/v1/workspaces/{workspace_id}/version-control/blob` 對應 `runtime_read`；敏感路由：否。 |
| `/api/v1/workspaces/{workspace_id}/version-control/diff` | `GET` | `runtime_read` | `1034` | 否 | `GET` `/api/v1/workspaces/{workspace_id}/version-control/diff` 對應 `runtime_read`；敏感路由：否。 |
| `/api/v1/workspaces/{workspace_id}/canvas/review-notes` | `GET` | `runtime_read` | `1033` | 否 | `GET` `/api/v1/workspaces/{workspace_id}/canvas/review-notes` 對應 `runtime_read`；敏感路由：否。 |
| `/api/v1/workspaces/{workspace_id}/claude-code/plugins` | `GET` | `runtime_read` | `1033` | 否 | `GET` `/api/v1/workspaces/{workspace_id}/claude-code/plugins` 對應 `runtime_read`；敏感路由：否。 |
| `/api/v1/workspaces/{workspace_id}/claude-code/plugins/{plugin_id:path}` | `GET` | `runtime_read` | `1033` | 否 | `GET` `/api/v1/workspaces/{workspace_id}/claude-code/plugins/{plugin_id:path}` 對應 `runtime_read`；敏感路由：否。 |
| `/api/v1/workspaces/{workspace_id}/codex/skills/content` | `GET` | `runtime_read` | `1033` | 否 | `GET` `/api/v1/workspaces/{workspace_id}/codex/skills/content` 對應 `runtime_read`；敏感路由：否。 |
| `/api/v1/workspaces/{workspace_id}/opencode/skills/tree` | `GET` | `runtime_read` | `1033` | 否 | `GET` `/api/v1/workspaces/{workspace_id}/opencode/skills/tree` 對應 `runtime_read`；敏感路由：否。 |
| `/api/v1/workspaces/{workspace_id}/version-control/lfs` | `GET` | `runtime_read` | `1033` | 否 | `GET` `/api/v1/workspaces/{workspace_id}/version-control/lfs` 對應 `runtime_read`；敏感路由：否。 |
| `/api/v1/workspaces/{workspace_id}/claude-code/memory` | `GET` | `runtime_read` | `1032` | 否 | `GET` `/api/v1/workspaces/{workspace_id}/claude-code/memory` 對應 `runtime_read`；敏感路由：否。 |
| `/api/v1/workspaces/{workspace_id}/codex/hooks-scopes` | `GET` | `runtime_read` | `1032` | 否 | `GET` `/api/v1/workspaces/{workspace_id}/codex/hooks-scopes` 對應 `runtime_read`；敏感路由：否。 |
| `/api/v1/workspaces/{workspace_id}/opencode/agents-md` | `GET` | `runtime_read` | `1032` | 否 | `GET` `/api/v1/workspaces/{workspace_id}/opencode/agents-md` 對應 `runtime_read`；敏感路由：否。 |
| `/api/v1/workspaces/{workspace_id}/opencode/subagents` | `GET` | `runtime_read` | `1032` | 否 | `GET` `/api/v1/workspaces/{workspace_id}/opencode/subagents` 對應 `runtime_read`；敏感路由：否。 |
| `/api/v1/workspaces/{workspace_id}/opencode/subagents/{scope}` | `GET` | `runtime_read` | `1032` | 否 | `GET` `/api/v1/workspaces/{workspace_id}/opencode/subagents/{scope}` 對應 `runtime_read`；敏感路由：否。 |
| `/api/v1/workspaces/{workspace_id}/claude-code/hooks` | `GET` | `runtime_read` | `1031` | 否 | `GET` `/api/v1/workspaces/{workspace_id}/claude-code/hooks` 對應 `runtime_read`；敏感路由：否。 |
| `/api/v1/workspaces/{workspace_id}/claude-code/hooks/{scope}` | `GET` | `runtime_read` | `1031` | 否 | `GET` `/api/v1/workspaces/{workspace_id}/claude-code/hooks/{scope}` 對應 `runtime_read`；敏感路由：否。 |
| `/api/v1/workspaces/{workspace_id}/codex/skills/tree` | `GET` | `runtime_read` | `1030` | 否 | `GET` `/api/v1/workspaces/{workspace_id}/codex/skills/tree` 對應 `runtime_read`；敏感路由：否。 |
| `/api/v1/workspaces/{workspace_id}/codex/agents-md` | `GET` | `runtime_read` | `1029` | 否 | `GET` `/api/v1/workspaces/{workspace_id}/codex/agents-md` 對應 `runtime_read`；敏感路由：否。 |
| `/api/v1/workspaces/{workspace_id}/codex/rules/file` | `GET` | `runtime_read` | `1029` | 否 | `GET` `/api/v1/workspaces/{workspace_id}/codex/rules/file` 對應 `runtime_read`；敏感路由：否。 |
| `/api/v1/workspaces/{workspace_id}/codex/subagents` | `GET` | `runtime_read` | `1029` | 否 | `GET` `/api/v1/workspaces/{workspace_id}/codex/subagents` 對應 `runtime_read`；敏感路由：否。 |
| `/api/v1/workspaces/{workspace_id}/codex/overview` | `GET` | `runtime_read` | `1028` | 否 | `GET` `/api/v1/workspaces/{workspace_id}/codex/overview` 對應 `runtime_read`；敏感路由：否。 |
| `/api/v1/workspaces/{workspace_id}/canvas/detect` | `GET` | `runtime_read` | `1027` | 否 | `GET` `/api/v1/workspaces/{workspace_id}/canvas/detect` 對應 `runtime_read`；敏感路由：否。 |
| `/api/v1/workspaces/{workspace_id}/canvas/health` | `GET` | `runtime_read` | `1027` | 否 | `GET` `/api/v1/workspaces/{workspace_id}/canvas/health` 對應 `runtime_read`；敏感路由：否。 |
| `/api/v1/workspaces/{workspace_id}/canvas/routes` | `GET` | `runtime_read` | `1027` | 否 | `GET` `/api/v1/workspaces/{workspace_id}/canvas/routes` 對應 `runtime_read`；敏感路由：否。 |
| `/api/v1/workspaces/{workspace_id}/codex/plugins` | `GET` | `runtime_read` | `1027` | 否 | `GET` `/api/v1/workspaces/{workspace_id}/codex/plugins` 對應 `runtime_read`；敏感路由：否。 |
| `/api/v1/workspaces/{workspace_id}/codex/plugins/{plugin_id:path}` | `GET` | `runtime_read` | `1027` | 否 | `GET` `/api/v1/workspaces/{workspace_id}/codex/plugins/{plugin_id:path}` 對應 `runtime_read`；敏感路由：否。 |
| `/api/v1/files/archive/{operation_id}/download` | `GET` | `runtime_read` | `1025` | 否 | `GET` `/api/v1/files/archive/{operation_id}/download` 對應 `runtime_read`；敏感路由：否。 |
| `/api/v1/workspaces/{workspace_id}/canvas/logs` | `GET` | `runtime_read` | `1025` | 否 | `GET` `/api/v1/workspaces/{workspace_id}/canvas/logs` 對應 `runtime_read`；敏感路由：否。 |
| `/api/v1/workspaces/{workspace_id}/codex/hooks/{scope}` | `GET` | `runtime_read` | `1025` | 否 | `GET` `/api/v1/workspaces/{workspace_id}/codex/hooks/{scope}` 對應 `runtime_read`；敏感路由：否。 |
| `/api/v1/workspaces/{workspace_id}/codex/rules` | `GET` | `runtime_read` | `1025` | 否 | `GET` `/api/v1/workspaces/{workspace_id}/codex/rules` 對應 `runtime_read`；敏感路由：否。 |
| `/api/v1/workspaces/{workspace_id}/codex/{resource}/files` | `GET` | `runtime_read` | `1025` | 否 | `GET` `/api/v1/workspaces/{workspace_id}/codex/{resource}/files` 對應 `runtime_read`；敏感路由：否。 |
| `/api/v1/workspaces/{workspace_id}/codex/apps` | `GET` | `runtime_read` | `1024` | 否 | `GET` `/api/v1/workspaces/{workspace_id}/codex/apps` 對應 `runtime_read`；敏感路由：否。 |
| `/api/v1/workspaces/{workspace_id}/codex/apps/{app_name:path}` | `GET` | `runtime_read` | `1024` | 否 | `GET` `/api/v1/workspaces/{workspace_id}/codex/apps/{app_name:path}` 對應 `runtime_read`；敏感路由：否。 |
| `/api/v1/workspaces/{workspace_id}/codex/{resource}/file` | `GET` | `runtime_read` | `1024` | 否 | `GET` `/api/v1/workspaces/{workspace_id}/codex/{resource}/file` 對應 `runtime_read`；敏感路由：否。 |
| `/api/v1/files/tree/children` | `GET` | `runtime_read` | `1022` | 否 | `GET` `/api/v1/files/tree/children` 對應 `runtime_read`；敏感路由：否。 |
| `/api/v1/workspaces/{workspace_id}/codex` | `GET` | `runtime_read` | `1020` | 否 | `GET` `/api/v1/workspaces/{workspace_id}/codex` 對應 `runtime_read`；敏感路由：否。 |
| `/docs/oauth2-redirect` | `GET`, `HEAD` | `runtime_read` | `1019` | 否 | `GET`, `HEAD` `/docs/oauth2-redirect` 對應 `runtime_read`；敏感路由：否。 |
| `/api/v1/files/download` | `GET` | `runtime_read` | `1018` | 否 | `GET` `/api/v1/files/download` 對應 `runtime_read`；敏感路由：否。 |
| `/api/v1/files/archive/{operation_id}` | `GET` | `runtime_read` | `1017` | 否 | `GET` `/api/v1/files/archive/{operation_id}` 對應 `runtime_read`；敏感路由：否。 |
| `/api/v1/files/content` | `GET` | `runtime_read` | `1017` | 否 | `GET` `/api/v1/files/content` 對應 `runtime_read`；敏感路由：否。 |
| `/api/v1/files/history` | `GET` | `runtime_read` | `1017` | 否 | `GET` `/api/v1/files/history` 對應 `runtime_read`；敏感路由：否。 |
| `/api/v1/files/search` | `GET` | `runtime_read` | `1016` | 否 | `GET` `/api/v1/files/search` 對應 `runtime_read`；敏感路由：否。 |
| `/api/v1/files/tree` | `GET` | `runtime_read` | `1014` | 否 | `GET` `/api/v1/files/tree` 對應 `runtime_read`；敏感路由：否。 |
| `/openapi.json` | `GET`, `HEAD` | `runtime_read` | `1012` | 否 | `GET`, `HEAD` `/openapi.json` 對應 `runtime_read`；敏感路由：否。 |
| `/redoc` | `GET`, `HEAD` | `runtime_read` | `1005` | 否 | `GET`, `HEAD` `/redoc` 對應 `runtime_read`；敏感路由：否。 |
| `/docs` | `GET`, `HEAD` | `runtime_read` | `1004` | 否 | `GET`, `HEAD` `/docs` 對應 `runtime_read`；敏感路由：否。 |
| `/` | `GET` | `runtime_read` | `1000` | 否 | `GET` `/` 對應 `runtime_read`；敏感路由：否。 |

| 錯誤碼 | 說明 |
| --- | --- |
| `WORKSPACE_RUNTIME_ACTION_FORBIDDEN` | 穩定授權錯誤碼 `WORKSPACE_RUNTIME_ACTION_FORBIDDEN`。 |
<!-- authorization-contract:runtime:end -->

## 資源 telemetry

Runtime 不提供新的公開使用者 telemetry route。它透過 internal Manager API 批次回報成功活動事件與 `workspace_data`／`runtime_home` 容量量測；回報採 fail-open 與 durable outbox，不能阻塞使用者操作。payload 不包含 prompt、內容、檔名或路徑。完整契約見[平台資源統計與容量治理](/features/platform/resource-statistics-and-capacity)。
