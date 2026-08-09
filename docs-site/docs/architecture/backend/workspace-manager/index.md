---
title: Workspace Manager
---

# Workspace Manager

## 概覽

Workspace Manager 是 Aileron 的核心服務，負責管理開發工作區的完整生命週期，包括建立、設定、啟動、停止和刪除。

## 核心功能

### 工作區管理

- **CRUD**：建立、讀取、更新、刪除工作區
- **生命週期**：以PostgreSQL durable job管理Docker／Kubernetes的
  create、start、stop、component restart、delete與crash recovery
- **Component revision fence**：Runtime、Browser、Canvas各自保存desired／observed
  revision、phase與workload identity，只替換job指定的元件；完整收斂流程請見
  [Execution-Plane 生命週期與安全機制](/architecture/overview/execution-plane)
- **Marketplace 支援**：管理 agent 套件與 provider 設定
- **網路配置**：防火牆規則和端口映射管理

### 使用者與 Workspace 協作

- **Workspace shares**：以直接分享管理工作區成員
- **權限控制**：基於角色的存取控制（RBAC）
- **User Groups**：集中管理使用者群組與群組成員
- **Knowledge Base attachment**：建立時檢查 Workspace 設定權；Private KB 另需來源 KB
  Manager，Public KB 以 implicit Reader 存取；建立後以 Workspace grant 提供零複製唯讀 mount
- **Runtime action gate**：依current instance、Runtime lifecycle與access observed
  revision，以及`runtime_read`、`runtime_write`、`terminal`、`agent`、`automation`、
  `browser_automation`逐次授權；KB mount observed revision只限制KB相依操作

### 自動化任務

- **Cron 排程**：Cron 表達式支援的定時任務
- **AI 整合**：可驅動 Claude Code、Codex、OpenCode agent workflow 的自動化任務
- **執行監控**：任務執行狀態和結果追蹤

Automation 不由 Celery 排程。Manager 內的單一 `AutomationScheduler` 以 asyncio
週期掃描 PostgreSQL，建立 execution；各 Workspace Runtime 再透過 claim／complete
契約領取及回報執行結果。

### Celery 背景工作

Celery worker 與唯一 Beat 執行 PostgreSQL 已持久化的 Workspace runtime durable job（start、
stop、Runtime／Browser／Canvas restart、delete、Knowledge Base mount reconcile、access recycle），另每日執行 KB
quota reconcile。Celery message 本身不是正確性來源；claim token、
lease、heartbeat 與 recovery 收斂細節請見
[Execution-Plane 生命週期與安全機制 — Durable job 與 recovery](/architecture/overview/execution-plane#durable-job-與-recovery)。

## 身分同步與 User Admin 機制

平台角色與使用者權限模型的使用者可見說明請見 [使用者、群組與權限模型](/features/platform/permissions-and-roles)；本節記錄支撐該模型的內部同步與 saga 機制。

Manager 將授權集中於 `AuthorizationOperationPolicy` 深 module。它解析 OIDC issuer + subject 對應的本地 snapshot、唯一 Owner、direct share、group share、Public KB 與 Platform Admin override，並提供 `require_platform_operation()`、`require_workspace_operation()`、`require_knowledge_base_operation()`、`require_knowledge_base_mount()` 與兩種 `allowed_*_operations()` interface。Router、domain service、Frontend 與 Runtime adapter 不自行比較角色 rank；`allowedOperations`、`accessRole`、`accessSource` 與完整 `accessSources` 都由同一 module 產生。

### 永久刪除 staging

Workspace 與 Knowledge Base 的永久刪除先在 transaction 內完成 authorization、exact-name confirmation、running-state 或 attachment preflight、audit intent 與刪除 fence，再執行外部 Runtime／storage cleanup，最後提交資源刪除結果。任何階段失敗都保留可稽核的失敗狀態，但不建立可還原的資源副本。Platform Admin 必須先透過有原因、通知與 before／after audit 的 Owner 接管流程，才能刪除他人資源。

### Manager Session 與授權新鮮度

Manager 是唯一終止外部 OIDC authorization-code flow 的元件。Callback 完成 ID token、nonce、
PKCE 與必要 UserInfo 驗證後，Manager 只向瀏覽器設定 HttpOnly opaque session cookie；provider
access token、refresh token 與 ID token 都不離開 Manager。每次受保護操作以 session 對應的本地
user snapshot、停用狀態與目前授權資料重新計算權限，不採用 JWT 內的平台角色，也不由前端快取
角色判斷。

### OIDC JIT snapshot sync

使用者不需先在 Aileron 建立帳號。首次成功完成 OIDC callback 時，Manager 以
`(oidc_issuer, oidc_subject)` 建立或更新 member snapshot，保存 username、email、display
name 等 optional claims，並保留本地平台角色。若本地 commit 失敗，請求 fail closed 並留下
可診斷的 `identity_sync_failed` 狀態；Manager 不建立 provider 帳號、不處理密碼，也不呼叫
provider-specific admin API。

### 管理員 Bootstrap

安裝與升級可用 `bootstrap.admin.subject` 收斂一個明確設定的本地平台管理員 snapshot。
Provider credential、群組與登入政策仍由 OIDC provider 管理；重複執行沿用同一個 local user
id，不會建立第二個管理員。一般 User Admin API 只修改本地角色與狀態，不提供 provider
帳號或密碼管理的 break-glass 路徑。

### Audit 與 correlation

身分 snapshot sync、User Admin CRUD、User Group 異動、direct KB share、Workspace attachment／lifecycle／access recycle 與 browser pairing 都會持久化 audit。HTTP request 可帶合法 UUID `X-Correlation-ID`；未提供或格式不合法時，Manager 會產生 UUIDv4 並在 response 回傳。Durable job 的 retry 使用新的 attempt correlation id，但保留最初 mutation 的 root correlation id，讓完整 lineage 可由資料庫追查。Audit metadata 只保存 allowlist 內的狀態、資源 id、revision、instance id 與穩定 reason，不保存密碼、token、JWS、credential、OIDC provider raw response、request body 或 exception payload。

### 部署與維運前提

- OIDC provider 只負責登入與 claims；Aileron 本地資料固定管理 `admin`、`member` 平台角色，並以 `(issuer, subject)` 保持 identity 唯一性。
- Provider 只要完成 Discovery、JWKS、client scope、audience 與 redirect URI 設定，Compose 與 Helm 就能在 Manager 啟動前驗證 OIDC contract。
- OIDC Discovery／JWKS 或 local snapshot bootstrap 失敗時應先修復設定，不應略過 gate 啟動 Manager。
- User Admin 與 User Group list 的搜尋、篩選、排序、分頁與 total 都由 PostgreSQL server-side query 計算。
- EKS、GKE、AKS、OCP、RKE2 與原生 Kubernetes 都是部署目標；各平台的真實 storage、admission、arbitrary UID、唯讀 probe 與 reschedule conformance 未通過前，仍應標示為 target／unverified，而不是已認證。

## 技術架構

| 元件 | 技術 |
|------|------|
| Web 框架 | FastAPI |
| ORM | SQLAlchemy |
| 資料庫 | PostgreSQL |
| 快取／Celery broker | Redis |
| Durable Workspace job／KB 維護 | Celery worker＋Beat |
| Automation 排程 | asyncio scheduler＋PostgreSQL |
| 容器管理 | Docker / Kubernetes |
| 認證 | Provider-neutral OIDC BFF＋opaque Manager session |

## 目錄結構

Workspace Manager 的 normative target 是垂直 domain module；router、model、
repository、contract 與 adapter 由 owning domain 集中管理，不再維護全域水平
taxonomy。完整目錄範本、seam、interface 與測試規則請見
[後端領域模組架構](/architecture/backend/)及
[Python 模組與檔名規則](/reference/python-module-naming)。

Marketplace request、User Copy 跨 Runtime 契約，以及 Workspace Runtime Job 狀態
協定的 owning module 與禁止穿透規則，請見
[後端深層模組與跨執行面契約](/architecture/backend/)。

## 環境變數

### 基礎設定

| 變數名 | 預設值 | 說明 |
|--------|--------|------|
| `DATABASE_URL` | — | Compose Adapter 使用的不含 credential PostgreSQL topology URL；密碼由唯讀 passfile 提供 |
| `DATABASE_URL_FILE` | — | Kubernetes Adapter 使用的完整 PostgreSQL DSN 唯讀 Secret 檔案路徑；設定時優先於 `DATABASE_URL` |
| `REDIS_URL` | — | Redis 連線 URL |
| `DOCKER_HOST` | `unix:///var/run/docker.sock` | Docker 主機 |
| `DEBUG` | `false` | 除錯模式 |

### OIDC 認證設定

| 變數名 | 預設值 | 說明 |
|--------|--------|------|
| `PLATFORM_PUBLIC_ORIGIN` | — | 唯一精確公開 Origin；callback、logout 與 CORS 由此衍生 |
| `OIDC_ISSUER_URL` | — | canonical issuer URL |
| `OIDC_CLIENT_ID` | — | Manager confidential OIDC client ID；必填且由安裝 Adapter 明確提供 |
| `OIDC_CLIENT_SECRET_FILE` | — | OIDC client secret 的唯讀檔案路徑 |
| `OIDC_ALLOWED_ALGORITHMS` | `RS256` | 允許的 JWT 演算法清單 |
| `OIDC_MAX_TOKEN_LIFETIME_SECONDS` | `1800` | token 最長生命週期 |
| `OIDC_REQUIRED_ACR` | _(空)_ | 可選 authentication context |
| `OIDC_JWKS_CACHE_TTL` | `3600` | JWKS cache TTL（秒） |
| `OIDC_DISCOVERY_TIMEOUT_SECONDS` | `5` | Discovery／JWKS timeout（秒） |

Discovery 固定為 `{issuer}/.well-known/openid-configuration`。這些欄位由 Compose 或 Helm Adapter 提供；Manager 目錄不提供獨立 `.env` 安裝表面。

Access token 與 refresh session 的實際 policy 由 OIDC provider 決定；Manager 不簽發平台自有 JWT，
並以 `OIDC_MAX_TOKEN_LIFETIME_SECONDS` 限制 callback 接受的 ID token 生命週期。瀏覽器只持有
Manager opaque session cookie 與 session-bound CSRF token。

:::important 認證不能關閉
Manager 強制使用通用 OIDC 認證，沒有 `ENABLE_AUTH=false` 或其他公開的停用開關。只有
health、metrics、OpenAPI／文件與 OIDC config 等明確豁免路徑可匿名存取。
:::

## 本地開發

```bash
docker compose up -d workspace-manager
```

`workspace-manager` 在本地開發時應優先透過 Docker Compose 啟動，並配合 control-plane Compose stack 一起運作。root Compose project 不包含 Docker provisioner 動態建立的 Workspace execution-plane containers；這些容器的生命週期仍由 Manager UI 或 API 管理。Compose 會將 `./workspace-manager` 掛載到容器內的 `/workspace-manager`，因此程式碼修改通常可透過既有 reload 機制即時生效。

若尚未啟動其他 control-plane 相依服務，建議直接使用：

```bash
docker compose up -d
```

## 測試

```bash
docker buildx bake --load workspace-manager

docker compose -f workspace-manager/docker-compose.test.yml \
  run --rm workspace-manager-test \
  bash -lc 'uv sync --dev && uv run pytest tests -v'

docker compose -f workspace-manager/docker-compose.test.yml \
  run --rm workspace-manager-test \
  bash -lc 'uv sync --dev && \
    uv run black --check app tests && \
    uv run isort --check-only app tests && \
    uv run flake8 --extend-ignore=E501,E402,W293 app tests && \
    uv run mypy app'
```

:::tip 測試環境
專案測試一律在container內執行，避免host依賴與PostgreSQL／Redis版本差異影響證據。
:::

## 監控

Manager 的 `/health`、`/metrics`、OpenAPI 與 Flower 是部署內部端點。瀏覽器只使用 Platform Public Origin 的 `/api/v1/...`。

## 平台資源分析與容量治理

Manager 的 `platform_resource_analytics` module 擁有 activity ledger、daily aggregate、latest capacity observation、daily capacity snapshot 與 Redis cache-aside；Runtime telemetry 由 `/api/v1/internal/workspaces/{workspace_id}/resource-telemetry/batches` ingestion route 接收，並以 batch／event identity 去重。Redis 失敗時 analytics read model 直接回 PostgreSQL。`platform_resource_capacity` module 單獨擁有 threshold、freshness、inventory projection/filter、quota command、expansion-only lifecycle 與 Workspace capacity query/routes。Workspace CR module 只負責 typed domain model 與 Kubernetes wire contract 的轉換。跨執行面 ownership 與 telemetry privacy 請參閱[平台資源與 Runtime Telemetry 架構](/architecture/overview/platform-resource-observability)；使用者可見功能請參閱[平台資源統計與容量治理](/features/platform/resource-statistics-and-capacity)。
