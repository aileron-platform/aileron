---
title: Manager API
---

# Workspace Manager API

本頁列出目前程式碼已註冊的主要端點。完整 schema與response仍以該部署版本的OpenAPI為準。

## Base URL

```text
/api/v1
```

Browser client 只在目前 Platform Public Origin 組合此相對路徑。Manager 的 Service DNS 與 port 只供部署內部使用。

## 認證

Manager 強制使用通用 OIDC 認證，沒有 `ENABLE_AUTH=false` 或其他公開的關閉設定。受保護請求由 JWT middleware 驗證；`/health`、`/health/oidc`、`/metrics`、`/docs`、`/redoc`、`/openapi.json` 與 OAuth2 流程是明確認證豁免路徑。OIDC issuer、audience、簽章、生命週期與可選 ACR 由 `OIDC_*` 設定決定。

```http
Authorization: Bearer <jwt_token>
```

授權不直接信任 JWT 中的平台角色；Manager 使用本地、有效且已同步的 user snapshot，並透過中央 `AuthorizationOperationPolicy` 判斷 platform operation 或資源 operation。Workspace 與 Knowledge Base operation 只依有效資源角色，不與平台功能權限取交集。完整契約請見 [使用者、群組與權限模型](/features/platform/permissions-and-roles)。

## 健康檢查

Manager 的 `GET /health` 是部署內部 probe，不是瀏覽器公開 API。

```json
{
  "status": "healthy",
  "service": "workspace-manager",
  "version": "<current-version>",
  "timestamp": "<ISO-8601 UTC timestamp>"
}
```

## Workspace 管理

| Method | 路徑 | 說明 |
| --- | --- | --- |
| `GET` | `/api/v1/workspaces` | 列出可存取的Workspace |
| `POST` | `/api/v1/workspaces` | 建立Workspace；`runtime`必填，並在同一transaction建立durable start job |
| `GET` | `/api/v1/workspaces/{workspace_id}` | 取得Workspace詳情、revision與current runtime job |
| `PUT` | `/api/v1/workspaces/{workspace_id}` | 更新Workspace設定；需Workspace manager |
| `DELETE` | `/api/v1/workspaces/{workspace_id}` | 以完整名稱確認提出單一永久刪除 intent；平台自動收斂 Automation 取消、停止與刪除，需 Workspace Owner |
| `GET` | `/api/v1/workspaces/{workspace_id}/sensitive-settings` | 取得遮罩後的敏感設定狀態；Reader 以上可讀 |
| `PUT` | `/api/v1/workspaces/{workspace_id}/sensitive-settings` | 保留、清除或取代敏感設定；需 Workspace Manager 以上 |

Public create／update payload不接受`provisioner`、`targetNamespace`、`setupScript`、`envVars`或`acpCliArgs`。Provisioner由部署設定決定，建立後不可由public API修改。

Workspace list、summary 與 detail 使用安全 allowlist projection，不回傳 setup script、環境變數、ACP args、credential、token 或 header。授權成功的資源回應必須包含 `accessRole`、`accessSource`、完整 `accessSources` 與後端產生的 `allowedOperations`；前端不得由角色自行重建 operation 矩陣。

敏感設定 GET 只回傳 secret 的遮罩與 `isConfigured`，不回傳 plaintext。PUT 省略欄位表示保留、明確 `null` 表示清除、提供新值表示取代；遮罩字串不能作為新值送回。Request／response log、錯誤 detail 與 audit metadata 都會先 redaction。

### Durable lifecycle

| Method | 路徑 | 說明 |
| --- | --- | --- |
| `POST` | `/api/v1/workspaces/{workspace_id}/start` | 回`202`並建立或重送`workspace_start` |
| `POST` | `/api/v1/workspaces/{workspace_id}/stop` | 回`202`並建立或重送`workspace_stop`；保留Workspace CR與PVC |
| `POST` | `/api/v1/workspaces/{workspace_id}/components/{component}/restart` | 回`202`並只增加指定元件revision；`component`為`runtime`、`browser`或`canvas` |

Lifecycle response包含：

```json
{
  "workspaceId": "<workspace-id>",
  "status": "running",
  "component": "browser",
  "targetRevision": 3,
  "jobId": "<job-id>",
  "correlationId": "<correlation-id>",
  "rootCorrelationId": "<root-correlation-id>"
}
```

Start、stop、retry、rebuild 與 component restart 需要 Workspace Manager 以上；永久刪除只允許實際 Owner。DELETE intent 接受後由平台獨立完成，重複請求沿用進行中流程，失敗後才可重新確認名稱並重試；只有 Workspace 確認不存在時才算成功。元件重啟不會更換其他元件的 workload identity。

## Knowledge Base attachment

| Method | 路徑 | 說明 |
| --- | --- | --- |
| `GET` | `/api/v1/workspaces/{workspace_id}/knowledge-bases` | 列出Workspace全部attachment及mount sync state |
| `POST` | `/api/v1/workspaces/{workspace_id}/knowledge-bases` | 建立唯讀attachment；回`202` |
| `PATCH` | `/api/v1/workspaces/{workspace_id}/knowledge-bases/{attachment_id}` | 修改alias；回`202` |
| `DELETE` | `/api/v1/workspaces/{workspace_id}/knowledge-bases/{attachment_id}` | 建立完整candidate並以`pending_removal`表示待移除；回`202` |
| `POST` | `/api/v1/workspaces/{workspace_id}/knowledge-base-mount-sync/retry` | 重試failed mount revision；回`202` |
| `GET` | `/api/v1/knowledge-bases/{kb_id}/attachments` | KB manager查看可見使用項目、總數與hidden count |

建立attachment的request：

```json
{
  "kbId": "<knowledge-base-uuid>",
  "mountAlias": "product-docs"
}
```

修改alias的request：

```json
{
  "mountAlias": "runbooks"
}
```

Payload沒有`mode`欄位，且extra field會被拒絕。所有Runtime mount固定唯讀。KB-centric attachment POST、PATCH與DELETE不存在。

Mutation response包含attachment與同步狀態：

```json
{
  "attachment": {
    "id": "<attachment-id>",
    "kbId": "<knowledge-base-id>",
    "mountAlias": "product-docs",
    "status": "pending"
  },
  "knowledgeBaseMountSync": {
    "status": "syncing",
    "desiredRevision": 3,
    "observedRevision": 2,
    "lastKnownGoodRevision": 2,
    "errorCode": null,
    "compensating": false
  }
}
```

詳細權限與delegated grant語意請參考[Workspace 與知識庫權限](/features/knowledge-base/sharing-and-permissions)。

## Runtime access 與 Browser pairing

### Instance-bound runtime access

```http
GET /api/v1/workspaces/{workspace_id}/runtime-access?action=<action>&runtimeInstanceId=<current-id>
Authorization: Bearer <token>
```

允許的 action 為 `runtime_read`、`runtime_write`、`workspace_settings`、`terminal`、`agent`、`automation` 與 `browser_automation`。中央 policy 將 action 映射到 Workspace OperationId；成功回 `204` 前，服務會檢查有效 principal、目前 `allowedOperations`、Runtime access revision、lifecycle 與 current generation。Reader 只允許安全 read projection；mutation 與 execution action 需要 Manager 以上。KB mount syncing／degraded 不屬於全域 Runtime access gate。

常見拒絕：

| HTTP | 錯誤碼 | 意義 |
| --- | --- | --- |
| `403` | `WORKSPACE_RUNTIME_ACTION_FORBIDDEN` | 目前 Workspace operation 不允許該 action |
| `422` | `WORKSPACE_RUNTIME_ACTION_INVALID` | action或`runtimeInstanceId`缺少／格式錯誤 |
| `423` | `WORKSPACE_RUNTIME_ACCESS_RECYCLE_IN_PROGRESS` | access revision尚未收斂 |
| `423` | `WORKSPACE_RUNTIME_ACCESS_RECYCLE_FAILED` | access recycle失敗 |
| `423` | `WORKSPACE_RUNTIME_INSTANCE_MISMATCH` | caller不是current generation |

### Browser extension pairing

```http
POST /api/v1/workspaces/{workspace_id}/browser-extension-pairing-assertions
Authorization: Bearer <token>
```

request不帶body。Manager先以`browser_automation`檢查current actor、generation與Browser workload identity，再回最長60秒、Ed25519簽章、single-use的pairing assertion：

```json
{
  "assertion": "<compact-jws>",
  "runtimeInstanceId": "<current-generation-id>"
}
```

Response設定`Cache-Control: no-store`與`Pragma: no-cache`。assertion不得放入URL query、DB、job metadata、browser storage或log。

## Workspace 其他端點

| Method | 路徑 | 說明 |
| --- | --- | --- |
| `GET` | `/api/v1/workspaces/{workspace_id}/runtime-logs` | 取得Runtime日誌 |
| `GET` | `/api/v1/workspaces/{workspace_id}/availability` | 取得control-plane availability、stable reason與允許的recovery action |
| `POST` | `/api/v1/workspaces/{workspace_id}/availability/actions/{action}` | 執行availability response允許的recovery action |
| `GET`／`PUT` | `/api/v1/workspaces/{workspace_id}/firewall` | 取得或取代Workspace firewall desired state |
| `POST` | `/api/v1/workspaces/{workspace_id}/firewall/retry` | 重試失敗的firewall convergence |
| `POST` | `/api/v1/workspaces/{workspace_id}/browser/access` | 取得 Browser relay credential；需 Workspace Manager 以上 |
| `POST` | `/api/v1/workspaces/{workspace_id}/browser/credentials/rotate` | 輪替目前Browser workload credential |
| `GET`／`POST` | `/api/v1/workspaces/{workspace_id}/shares` | 列出或新增 user／group share；角色只接受 Reader／Manager |
| `PATCH`／`DELETE` | `/api/v1/workspaces/{workspace_id}/shares/{share_id}` | 更新或移除單一分享 |

Browser access 以 `status.browserConnectivity.admission` 為權威；`ready`，或最後成功 evidence
仍在 TTL 內且 projection 為 `allowed` 的 `degraded`，都可核發 access。`pending`／`not_ready`
的 `denied` projection 對應 `409 BROWSER_CONNECTIVITY_NOT_READY`；admission 當下已到期而投影為
`not_ready`／`denied` 的 evidence 也對應相同 409。只有 `unavailable`
對應 `503 BROWSER_CONNECTIVITY_UNAVAILABLE`。拒絕回應不會包含 Browser credential，client
只能使用 bounded retry，不得改呼叫未受 gate 保護的 endpoint。

成功 response 包含 `browserUrl`、Neko `password`、`credentialRevision` 與 `iceServers`。
`turnRest` profile 的 `iceServers` 具有本次 access 專用的短效 username/credential；前端必須用它
建立 `RTCPeerConnection`，不能改用快取或 Neko 啟動時的固定 ICE 設定。

`/health`只表示Manager HTTP process可回應；`availability`才是指定Workspace execution
plane的authoritative control-plane gate。Client只能執行availability response列出的action。
Firewall `PUT`只代表desired state與durable command已保存，不代表policy已套用；應持續讀取
firewall state直到`syncStatus`成為`applied`或`error`。完整狀態與recovery語意請見
[Execution-Plane 生命週期與安全機制](/architecture/overview/execution-plane)。

`runtime-logs` 是已保存的 provisioning／lifecycle event 查詢，不是串流 container
stdout。它接受 `limit`（預設 `100`，範圍 `1`–`500`）與選用的精確 `stage` filter，
並依 `createdAt` 新到舊回傳：

```json
[
  {
    "id": "<log-id>",
    "workspaceId": "<workspace-id>",
    "stage": "provisioning",
    "message": "<localized-message>",
    "metadata": {},
    "createdAt": "2026-07-27T12:00:00Z"
  }
]
```

需要實際 Runtime container／Pod stdout 時，請依
[部署診斷](/installation/troubleshooting.md#workspace-元件狀態不一致) 使用 Docker 或
Kubernetes log 指令。

## Workspace 設定

| Method | 路徑 | 最低權限 | 說明 |
| --- | --- | --- | --- |
| `POST` | `/api/v1/workspaces/{workspace_id}/setup/sync` | Workspace Manager | 啟動Workspace初始化同步 |
| `GET` | `/api/v1/workspaces/{workspace_id}/setup/status` | Workspace Reader | 查詢初始化同步狀態 |
| `GET` | `/api/v1/workspaces/temp/setup/git-branches?git_url=...` | 有效 Member | 建立前查詢遠端Git分支 |
| `GET`／`PUT` | `/api/v1/users/{user_id}/settings` | self | 讀取或更新自己的個人設定；不得以路徑中的其他 `user_id` 存取 |
| `POST` | `/api/v1/users/{user_id}/ssh-keys/generate` | self | 產生並儲存自己的 SSH key pair |
| `POST`／`GET` | `/api/v1/users/{user_id}/settings/codex/*` | self | 管理自己的 Codex 登入狀態 |
| `POST` | `/api/v1/users/{user_id}/settings/sync` | self＋各目標 Workspace Manager | 將個人設定同步至自己可管理且執行中的 Workspace Runtime |
| `POST` | `/api/v1/users/{user_id}/settings/sync/{workspace_id}` | self＋Workspace Manager | 將個人設定同步至 Runtime |

所有角色都能管理自己的個人設定、Codex 登入與 SSH key；背景 Runtime 收斂只有在目前 Workspace 的 `allowedOperations` 允許設定 mutation 時執行，否則只保存 Manager 端個人設定。

## Container Images

| Method | 路徑 | 最低權限 | 說明 |
| --- | --- | --- | --- |
| `GET` | `/api/v1/container-images` | 有效 Member | 列出可用的 Workspace Runtime container image |
| `GET` | `/api/v1/container-images/{image_id}` | 有效 Member | 取得單一 image 詳情 |
| `POST` | `/api/v1/container-images/reload` | Platform Admin | 重新載入全平台 image 清單設定 |

## OAuth

Manager 提供兩組 OAuth 路由：`/api/v1/oauth/*` 管理 agent integration credential；
`/api/v1/oauth2/*` 是平台登入 BFF。只有 Manager 執行 Authorization Code + PKCE、provider
token exchange 與 validation；Browser 只持有 opaque HttpOnly session。

| Method | 路徑 | 說明 |
| --- | --- | --- |
| `GET` | `/api/v1/oauth/info` | 查詢 provider OAuth 設定資訊 |
| `POST` | `/api/v1/oauth/exchange` | 以 authorization code 交換 token |
| `POST` | `/api/v1/oauth/authenticate` | 執行 OAuth 認證並保存憑證 |
| `POST` | `/api/v1/oauth/refresh` | 刷新既有 OAuth token |
| `GET` | `/api/v1/oauth/health` | OAuth 服務健康檢查 |
| `GET` | `/api/v1/oauth2/login` | 建立 OIDC transaction 並 redirect provider |
| `GET` | `/api/v1/oauth2/callback` | Manager 交換 code、驗證 provider response 並建立 opaque session |
| `GET` | `/api/v1/oauth2/session` | 取得本地 user、canonical OIDC `subject`、`platformRole`、`allowedOperations`、expiry 與 memory-only CSRF token |
| `POST` | `/api/v1/oauth2/logout` | 驗證 session、Origin 與 CSRF 後撤銷本地 session |

成功 callback 建立的 Manager Session 是延續認證證據。Session 有效期間的受保護 API 只
使用本機 Session、User 與 operation policy，不呼叫 IdP。Session 缺少、過期、撤銷或
principal binding 不一致時回傳 `401 MANAGER_SESSION_REQUIRED`，Frontend 才執行一次 OIDC
重新登入；本機使用者或平台 operation 不允許時回傳
`403 PLATFORM_AUTHORIZATION_DENIED`，保留 Session 且不重新登入。

## Marketplace

Marketplace 管理應用中心的 Managed Plugins、Plugin 安裝、User Copy 與 Registry 版本控制，功能細節請見 [應用中心](/features/marketplace)。

| Method | 路徑 | 說明 |
| --- | --- | --- |
| `GET` | `/api/v1/marketplace/packages` | 列出套件 |
| `POST` | `/api/v1/marketplace/packages` | 建立套件 |
| `GET` | `/api/v1/marketplace/package-formats` | 列出 package format、相容 Target Client 與 authoring capabilities |
| `GET`／`PUT`／`DELETE` | `/api/v1/marketplace/packages/{target_client}/{package_id}` | 取得、更新或刪除單一套件 |
| `GET` | `/api/v1/marketplace/packages/{target_client}/{package_id}/export` | 匯出套件 |
| `POST` | `/api/v1/marketplace/packages/refresh` | 重新整理套件清單快取 |
| `POST` | `/api/v1/marketplace/imports/scan` | 掃描 Git 或已上傳來源的 Plugin 候選項目 |
| `POST` | `/api/v1/marketplace/imports/upload` | 上傳 ZIP 作為暫時的 import source |
| `POST` | `/api/v1/marketplace/imports` | 將選取項目匯入 Managed Registry；重複項目需明確 Replace |
| `POST` | `/api/v1/marketplace/plugins/install` | 由目標 Workspace 的 Target Client CLI 從設定的 Registry Git repository 安裝並啟用 |
| `POST` | `/api/v1/marketplace/user-copies/preflight` | 唯讀規劃一次性 user-scope merge，列出資源、重複項目與阻擋原因 |
| `POST` | `/api/v1/marketplace/user-copies` | 依 preflight digest 與使用者核准的覆寫清單執行一次性 merge |
| `GET`／`PUT` | `/api/v1/marketplace/settings` | 取得或更新 Marketplace 設定 |
| `GET` | `/api/v1/marketplace/activities` | 依 `workspaceId`、`packageFormat`、`targetClient`、`packageId`、`action`、`status` 篩選並分頁取得 Marketplace 操作紀錄 |
| `GET` | `/api/v1/marketplace/activities/{activity_id}` | 依權限取得單筆活動、User Copy proof 與完整 CLI 命令收據 |

### Plugin 安裝契約

`POST /api/v1/marketplace/plugins/install` 接受 `targetClient`、`packageFormat`、`packageId`、`version` 與 `workspaceId`。Manager 傳遞設定的 Registry Git URL 與目前 branch，不檢查 remote 是否已包含 working-tree 內容；目標 Runtime 必須自行具備 repository 讀取憑證。接著 Runtime 執行 Claude Code
或 Codex 的標準 CLI 流程。Codex 的 `plugin add` 代表安裝並啟用；Claude Code 依序執行 marketplace add、plugin install 與明確的 plugin enable。每個命令結果分開保存 argv、stage、exit code、起訖時間、原始 byte 數與 stdout/stderr；輸出採 256 KiB head+tail 保留且不做內容遮罩。mutation 命令成功後，readback 失敗只回覆 `state-unconfirmed` warning。安裝及啟用是否成功以 target-client CLI 的 terminal result 為準；成功 mutation 若 audit 經三次寫入仍失敗，回覆 `audit-persistence-failed` warning 而不反轉成功結果。

這個端點只負責驗證指定 release 並完成 CLI 命令，不建立 Aileron installation、ownership、
drift、reconcile、uninstall 或 cleanup 狀態。後續 plugin 管理由使用者透過原生 CLI
自行處理。

### Import 契約

Import source 為 `{ targetClient, sourceKind, source }`。Scan 回覆 server 端偵測的 package ID、version、format、Target Client、validation 與 duplicate 狀態。Import request 的每個 candidate 以 `import: { version, overwrite }` 表達使用者選擇；重複 package ID 只有在 `overwrite=true` 時可 Replace。來源不會註冊成持續追蹤的物件。失敗 candidate 包含 `errorCode`、`stage`、`source`、`destination` 與 `category`。

### Copy to user scope 契約

User-copy 是一次性的 user-scope merge。呼叫端必須先呼叫
`POST /api/v1/marketplace/user-copies/preflight`；結果狀態為 `ready`、
`confirmation-required` 或 `blocked`，並包含：

- `resources`：預計建立、合併或保持不變的資源。
- `skippedResources`：exact projection 無法表達的 component；存在任一項時必須確認 partial copy。
- `conflicts`：需要使用者逐項確認覆寫的重複資源。
- `blockingIssues`：使本次操作無法繼續的問題。
- `sourceDigest`、`profileDigest`、`projectionDigest`、`materializationDigest`：鎖定 preflight
  時看到的套件內容、source profile、exact projection 與實體化結果。

實際套用時，`POST /api/v1/marketplace/user-copies` 帶入 `catalogPluginId`、`releaseRevision`、
`packageFormat`、`targetClient`、`workspaceId`、三個 expected digests、`acceptPartialCopy`
與使用者確認過的 `overwriteApprovals`。若來源、projection 或目標狀態改變，服務拒絕套用並要求重新 preflight；成功結果回覆 package format、target client，以及 created、merged、unchanged、overwritten、skipped 數量。

成功後不會留下 installation row、來源追蹤、ownership、drift、reconcile、uninstall、
cleanup 或背景生命週期。後續檔案與設定完全由使用者自行管理；Marketplace 也不會因為
套件被刪除或修改而回收 user-copy 產生的內容。

Marketplace 另擁有一整組獨立的 Git 版本控制 API（`/api/v1/marketplace/version-control/*`：status、stage、unstage、commit、commits、diff、branches、remote、fetch、pull、push、clone、force-unlock、git-identity、ssh-key 等），管理套件倉庫本身的版本控制，語意與 Knowledge Base 的 Git 端點類似但服務不同資源。

Member 可讀取 catalog、安裝及管理自己的 user-scope copy；建立、匯入、編輯、刪除與 Registry 管理只允許 Platform Admin。完整規則請見 [應用中心](/features/marketplace)。

Activity response 使用 `{ items, total, page, pageSize, totalPages }`，依
`createdAt DESC, id DESC` 穩定排序；狀態固定為
`succeeded | failed`。Activity 僅供稽核，不作為 installation
或任何後續生命週期的權威狀態。

## 自動化任務

Automation 排程由 Manager process 內的單一 asyncio scheduler 掃描 PostgreSQL；
Workspace Runtime 透過 claim／complete 契約執行。這組 API 不使用 Celery 排程；Celery
worker／Beat 是另一條路徑，負責 Workspace durable job（start、stop、restart、delete、
KB mount sync、access recycle）、Manager Session expiry cleanup 與 KB quota reconcile，claim／lease／heartbeat
收斂細節請見
[Execution-Plane 生命週期與安全機制 — Durable job 與 recovery](/architecture/overview/execution-plane#durable-job-與-recovery)。

| Method | 路徑 | 說明 |
| --- | --- | --- |
| `GET` | `/api/v1/automation/jobs` | 列出自動化任務 |
| `POST` | `/api/v1/automation/jobs` | 建立任務 |
| `GET` | `/api/v1/automation/jobs/{job_id}` | 取得任務 |
| `PATCH` | `/api/v1/automation/jobs/{job_id}` | 更新任務 |
| `DELETE` | `/api/v1/automation/jobs/{job_id}` | 刪除任務 |
| `POST` | `/api/v1/automation/jobs/{job_id}/pause` | 暫停排程任務 |
| `POST` | `/api/v1/automation/jobs/{job_id}/resume` | 恢復排程任務 |
| `POST` | `/api/v1/automation/jobs/{job_id}/run` | 建立手動任務執行 |
| `POST` | `/api/v1/automation/webhook/{job_id}` | 由已設定的webhook觸發任務 |
| `GET` | `/api/v1/automation/jobs/{job_id}/executions` | 列出任務執行 |
| `GET` | `/api/v1/automation/executions` | 跨任務列出可見的executions |
| `GET` | `/api/v1/automation/executions/{execution_id}` | 取得單一execution |
| `POST` | `/api/v1/automation/executions/{execution_id}/cancel` | 取消執行 |
| `GET` | `/api/v1/automation/metrics` | 取得Automation摘要metrics |
| `GET` | `/api/v1/automation/calendar` | 取得Automation calendar資料 |

## 使用者與群組管理

| Method | 路徑 | 說明 |
| --- | --- | --- |
| `GET` | `/api/v1/users` | 搜尋可分享的使用者 |
| `GET` | `/api/v1/users/{user_id}/profile` | 取得使用者 profile（唯讀） |
| `GET`／`PUT` | `/api/v1/users/me/recent-workspace` | 取得或更新最近使用Workspace |
| `GET` | `/api/v1/admin/users` | 依 server-side query、filter、sort 與分頁列出本地使用者 snapshot |
| `GET` | `/api/v1/admin/users/roles` | 列出 `admin`、`member` 兩個可授予的平台角色及 i18n key |
| `GET` | `/api/v1/admin/users/{user_id}` | 取得單一本地使用者 snapshot |
| `PUT` | `/api/v1/admin/users/{user_id}/role` | 完整取代平台角色 |
| `GET`／`POST` | `/api/v1/admin/user-groups` | 列出或建立User Group |
| `GET`／`PATCH`／`DELETE` | `/api/v1/admin/user-groups/{group_id}` | 取得、更新或以 transactional cascade 刪除 User Group |
| `GET`／`POST` | `/api/v1/admin/user-groups/{group_id}/members` | 列出或新增群組成員 |
| `GET` | `/api/v1/admin/user-groups/{group_id}/member-candidates` | 以 server-side query 列出成員候選人 |
| `POST` | `/api/v1/admin/user-groups/{group_id}/members/batch-remove` | 批次移除群組成員 |
| `DELETE` | `/api/v1/admin/user-groups/{group_id}/members/{user_id}` | 移除單一群組成員 |

所有 `/api/v1/admin/users*` 與 `/api/v1/admin/user-groups*` 端點都要求有效且新鮮的
`admin` 平台角色。使用者由 OIDC token 首次驗證時 JIT 建立；admin API 不建立 provider
帳號、不處理密碼，也不呼叫 provider admin API。`PUT /api/v1/admin/users/{user_id}/role`
只替換本地平台角色，並以 audit 與最後一位可用 admin invariant 保護變更。

### Server-side list contract

使用者、群組、群組成員與候選人列表都回傳相同分頁外框：

```json
{
  "items": [],
  "total": 0,
  "page": 1,
  "pageSize": 25
}
```

`page` 從 1 開始，`pageSize` 最大 100。搜尋、filter、排序、total 與分頁都由資料庫完成；
呼叫端不得抓固定前 25 筆後再做本地分頁。未知 query key、同名 query 重複、非法 CSV
enum、boolean、排序或頁碼會回穩定的 invalid-page 錯誤碼。

批次新增成員回 `{addedUserIds, skippedUserIds, failedUsers}`，批次移除回
`{removedUserIds, skippedUserIds, failedUsers}`。Request 內的 `userIds` 必須是 1 至 100 個
不重複的本地 user id；已存在或已移除的項目進入 `skippedUserIds`，不可授權或不存在的
項目逐筆出現在 `failedUsers`。

完整角色、User Group、direct Knowledge Base 與 Workspace grant 語意請參考
[使用者、群組與權限模型](/features/platform/permissions-and-roles)。

## Platform Resources

只有 Platform Admin 可使用獨立的全域資源 API；一般 Workspace／Knowledge Base 清單不混入全平台資源。

| Method | 路徑 | 說明 |
| --- | --- | --- |
| `GET` | `/api/v1/platform-resources/workspaces` | 以 `q`、`page`、`pageSize` 查詢全平台 Workspace 的安全摘要與 Owner projection |
| `GET` | `/api/v1/platform-resources/knowledge-bases` | 以 `q`、`page`、`pageSize` 查詢全平台 Knowledge Base 的安全摘要與 visibility |
| `POST` | `/api/v1/platform-resources/workspaces/{workspace_id}/owner-reassignment` | 重新指派 Workspace Owner |
| `POST` | `/api/v1/platform-resources/knowledge-bases/{knowledge_base_id}/owner-reassignment` | 重新指派 Knowledge Base Owner |

Owner reassignment request：

```json
{
  "targetUserId": "<existing-manager-user-id>",
  "reason": "<3-500 character audit reason>"
}
```

目標使用者必須是有效、可授權且已具該資源 Manager 關係的使用者。成功後，仍有效的原 Owner 降為 Manager；已停用的原 Owner 移除存取。服務在同一流程寫入 before／after audit，提交後通知原 Owner，並對受影響 Workspace 發布 access recycle。通知或 recycle 發佈失敗會使用穩定 error code 回報，已提交的 ownership 不會回滾。

## 錯誤格式

Attachment、runtime access 與 lifecycle 契約使用穩定錯誤碼，通常位於 FastAPI 的
`detail` 物件：

```json
{
  "detail": {
    "errorCode": "KB_MOUNT_ALIAS_INVALID",
    "correlationId": "<correlation-id>"
  }
}
```

User Admin 與 User Group API 則固定使用 top-level envelope：

```json
{
  "errorCode": "USER_ADMIN_INVALID_REQUEST",
  "correlationId": "<correlation-id>",
  "details": {
    "fields": ["email"]
  }
}
```

`details` 只在安全的 validation 情境出現，不含密碼、token、OIDC provider raw response 或
exception payload。Workspace 與 Knowledge Base 的授權拒絕固定使用下列結構：

```json
{
  "detail": {
    "errorCode": "WORKSPACE_OPERATION_DENIED",
    "message": "經 i18n 處理的訊息",
    "details": {}
  }
}
```

授權拒絕的狀態碼語意固定為：未認證回 `401`；caller 與資源沒有可見關係，或資源不存在時
回 `404`；資源可見但指定 operation 不允許時回 `403`。呼叫端只能以 `errorCode` 判斷授權
結果並對應 i18n，不得解析或直接顯示 backend `message`／`details`。其他非授權端點仍依各自
OpenAPI 契約處理。

| 狀態碼 | 說明 |
| --- | --- |
| `200`／`201`／`202`／`204` | 成功、已建立、已接受或無response body |
| `400`／`422` | 請求格式或欄位契約錯誤 |
| `401` | 未認證或控制面assertion無效 |
| `403` | 資源可見，但指定 operation 不允許 |
| `404` | 資源不存在、ID 組合不符，或 caller 與資源沒有可見關係 |
| `409` | lifecycle、attachment或刪除衝突 |
| `423` | execution plane正在收斂或fail closed |
| `500`／`503` | 伺服器或必要相依服務不可用 |

<!-- authorization-contract:workspace:start -->
<!-- generated by docs-site/scripts/check-authorization-contract.mjs -->
| OperationId | 最低資源角色 | 僅限平台管理員 | 說明 |
| --- | --- | --- | --- |
| `workspace.detail.read` | `reader` | `false` | Reader 以上可讀取 Workspace 詳情。 |
| `workspace.content.write` | `manager` | `false` | Manager 以上可變更 Workspace 內容。 |
| `workspace.lifecycle.execute` | `manager` | `false` | Manager 以上可執行完整 lifecycle。 |
| `workspace.metadata.write` | `manager` | `false` | Manager 以上可更新 metadata。 |
| `workspace.access.manage` | `manager` | `false` | Manager 以上可管理 direct／group share。 |
| `workspace.attachment.write` | `manager` | `false` | Manager 以上可管理 Knowledge Base 掛載。 |
| `workspace.firewall.read` | `reader` | `false` | Reader 以上可查看 Firewall。 |
| `workspace.firewall.manage` | `manager` | `false` | Manager 以上可管理 Firewall。 |
| `workspace.sensitive_settings.read` | `reader` | `false` | Reader 以上可查看遮罩後的敏感設定。 |
| `workspace.sensitive_settings.manage` | `manager` | `false` | Manager 以上可更新敏感設定。 |
| `workspace.terminal.use` | `manager` | `false` | Manager 以上可使用 Terminal。 |
| `workspace.agent_chat.use` | `manager` | `false` | Manager 以上可使用 AI Chat。 |
| `workspace.automation.execute` | `manager` | `false` | Manager 以上可執行 Automation。 |
| `workspace.browser_automation.use` | `manager` | `false` | Manager 以上可使用 Browser automation。 |
| `workspace.delete` | `owner` | `false` | 只有實際 Owner 可永久刪除 Workspace。 |

| 錯誤碼 | 說明 |
| --- | --- |
| `WORKSPACE_ACCESS_DENIED` | 穩定授權錯誤碼 `WORKSPACE_ACCESS_DENIED`。 |
| `WORKSPACE_OPERATION_DENIED` | 穩定授權錯誤碼 `WORKSPACE_OPERATION_DENIED`。 |
| `WORKSPACE_DELETE_CONFLICT` | Workspace 刪除與目前生命週期狀態衝突。 |

| 平台資源錯誤碼 | 說明 |
| --- | --- |
| `PLATFORM_RESOURCE_INVALID_REQUEST` | Platform Resources 請求欄位或格式無效。 |
| `PLATFORM_RESOURCE_NOT_FOUND` | 指定的 Workspace 或 Knowledge Base 不存在。 |
| `PLATFORM_RESOURCE_OWNER_NOT_FOUND` | 找不到目前的 Owner identity。 |
| `PLATFORM_RESOURCE_TARGET_NOT_AUTHORIZABLE` | 目標使用者無效、已停用，或其 identity snapshot 不可授權。 |
| `PLATFORM_RESOURCE_TARGET_MANAGER_REQUIRED` | 目標使用者尚未具備該資源的 Manager 關係。 |
| `PLATFORM_RESOURCE_OWNER_UNCHANGED` | 目標使用者已是目前的 Owner。 |
| `PLATFORM_RESOURCE_OWNER_NOTIFICATION_FAILED` | Ownership 已提交，但通知原 Owner 失敗。 |
| `PLATFORM_RESOURCE_ACCESS_RECYCLE_FAILED` | Ownership 已提交，但發布 access recycling 失敗。 |
<!-- authorization-contract:workspace:end -->

## 平台資源統計與容量 API

Platform Admin 可分別讀取 Workspace／Knowledge Base 的 `summary`、`resource-trend` 與 `capacity-trend`；三個 endpoint 獨立失敗，不共用單一頁面錯誤狀態。治理 API 包含 Knowledge Base quota 更新／重設、Workspace capacity expansion 建立與狀態查詢。具有 `workspace.detail.read` 的使用者可讀取 `/workspaces/{workspaceId}/capacity?range=7d`。Runtime 批次回報使用 internal identity 驗證，詳見[平台資源統計與容量治理](/features/platform/resource-statistics-and-capacity)。
