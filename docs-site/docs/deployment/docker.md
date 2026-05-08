---
sidebar_position: 1
title: Docker 模式
---

# Docker 部署

## 適用情境

- 本機開發與除錯
- 快速體驗完整平台功能
- 不需要 Kubernetes、Operator、Cilium 的情境
- 單機環境部署

## 需求

- [Docker](https://docs.docker.com/get-docker/)（建議 24.0+）
- [Docker Compose](https://docs.docker.com/compose/install/)（V2，通常已內建於 Docker Desktop）
- [Git LFS](https://git-lfs.com/)（選用；知識庫啟用 Git LFS 並管理大型 `raw/` 檔案時需要）
- 至少 4 vCPU
- 至少 8GB 可用記憶體
- 建議 12GB 到 16GB 可用記憶體，以支援較穩定的瀏覽器與 agent 工作流程
- 至少 30GB 可用磁碟空間
- 建議保留 50GB 可用磁碟空間，避免 image、volume 與 workspace 資料快速吃滿

## 服務架構

Docker 模式下，`docker compose` 管理以下服務：

```
┌────────────────────────────────────────────────────────┐
│                     使用者瀏覽器                         │
└──────────┬────────────┬──────────────┬─────────────────┘
           │:8082       │:3001         │:8080
┌──────────▼───┐ ┌──────▼──────────┐ ┌─▼────────────┐
│   Frontend   │ │Workspace Manager│ │   Keycloak    │
│  (Vite Dev)  │ │   (FastAPI)     │ │  (OAuth2)     │
└──────────────┘ └──┬──────────┬───┘ └───────────────┘
                    │          │
           ┌────────▼──┐  ┌───▼──────────────┐
           │  Celery +  │  │  Workspace       │
           │  Flower    │  │  Runtime :3002    │
           │  :5555     │  │  Terminal :3004   │
           └────────────┘  │  SSH :2222        │
                           └──┬────────┬──────┘
                              │        │
                    ┌─────────▼──┐ ┌───▼──────────┐
                    │  Browser   │ │ Workspace     │
                    │  (neko)    │ │ Next.js :3003 │
                    │  :6080     │ └───────────────┘
                    └────────────┘
        ┌──────────────────────────────────────┐
        │          基礎設施                      │
        │  PostgreSQL :5432 │ Redis :6379       │
        └──────────────────────────────────────┘
```

### 各服務說明

| 服務 | 映像 | 說明 |
|------|------|------|
| **postgres** | `postgres:15-alpine` | 主要資料庫，存放平台與 Keycloak 資料 |
| **redis** | `redis:7-alpine` | 任務佇列 (Celery broker)、結果後端、session 管理 |
| **keycloak** | `keycloak:25.0.0` | OAuth2/OIDC 認證服務，支援 SSO |
| **workspace-manager** | 本地建置 | 核心管理服務：workspace CRUD、模板、自動化排程 |
| **workspace-runtime** | 本地建置 | Agent Runtime：目前以 Claude Code 最完整，並內建 OpenSpec CLI、檔案監控、Git、系統監控 |
| **workspace-browser** | 本地建置 | WebRTC 瀏覽器（基於 neko），支援 CDP 遠端偵錯 |
| **workspace-nextjs** | 本地建置 | Next.js 預覽服務，用於即時預覽前端變更 |
| **frontend** | 本地建置 | React + Vite 開發伺服器 |
| **drawio** | `jgraph/drawio` | 內嵌圖表編輯工具 |

:::info Git LFS 與知識庫
Team Wiki Knowledge Base 的 Git 版本控制是每個知識庫的選項；只有在知識庫啟用 Git LFS 時，manager 執行環境才需要可用的 `git lfs` 指令。Docker 映像若要支援大型 PDF、圖片、壓縮檔或其他 `raw/` 來源檔案的 LFS tracking，請確認 `workspace-manager` image 內已安裝 Git LFS。
:::

## 啟動

```bash
docker compose up -d --build
```

:::info 建置時間
第一次啟動需要建置所有映像，約需 5～10 分鐘。後續啟動若無程式碼變更，使用 `docker compose up -d` 即可秒速啟動。
:::

在 Aileron 中，這個完整的 Docker Compose stack 不只是部署方式，也是預設的本地開發模式。日常模組開發應以整套服務一起啟動為前提，再透過開發用掛載與各服務內建的 reload 機制，即時反映程式碼變更。

## 確認服務狀態

```bash
docker compose ps
```

建議等到 `postgres`、`redis`、`keycloak`、`workspace-manager`、`frontend` 都進入 `healthy` 狀態後再登入。

:::warning Keycloak 初始化
Keycloak 有 60 秒的 `start_period`。若尚未完成初始化就嘗試登入，前端會顯示 OIDC 認證失敗。
:::

## 服務位址

| 服務 | URL | 說明 |
|------|-----|------|
| Frontend | `http://localhost:8082` | 主操作介面 |
| Manager API | `http://localhost:3001` | Workspace Manager REST API |
| Manager Swagger | `http://localhost:3001/docs` | Manager 互動式 API 文件 |
| Manager ReDoc | `http://localhost:3001/redoc` | Manager ReDoc API 文件 |
| Runtime API | `http://localhost:3002` | Workspace Runtime REST API |
| Runtime Swagger | `http://localhost:3002/docs` | Runtime 互動式 API 文件 |
| Runtime ReDoc | `http://localhost:3002/redoc` | Runtime ReDoc API 文件 |
| Terminal | `http://localhost:3004` | Terminal WebSocket 服務 |
| Keycloak Admin | `http://localhost:8080/admin` | 認證管理後台 |
| Draw.io | `http://localhost:8083` | 圖表編輯器 |
| Flower | `http://localhost:5555` | Celery 任務監控 |
| Browser WebSocket | `http://localhost:6080` | neko WebRTC signaling |
| Next.js Preview | `http://localhost:3003` | Next.js 開發伺服器 |

## 環境變數配置

### 主機環境變數

以下環境變數可透過 shell 或 `.env` 檔案設定，影響整體 docker compose 行為：

| 變數 | 預設值 | 說明 |
|------|--------|------|
| `TZ` | `Asia/Taipei` | 系統時區 |
| `HOST_PROJECT_ROOT` | `.` | 專案根目錄在主機上的絕對路徑 |
| `HOST_WORKSPACES_DIR` | `./data/workspace-data` | 工作區資料儲存路徑 |
| `HOST_SSH_KEYS_DIR` | `./data/ssh-keys` | SSH 金鑰儲存路徑 |
| `ANTHROPIC_BASE_URL` | _(空)_ | Claude API Base URL（自訂 proxy 時使用） |
| `ANTHROPIC_AUTH_TOKEN` | _(空)_ | Claude API 認證 Token |

:::tip .env 檔案
在專案根目錄建立 `.env` 檔案，docker compose 會自動載入：

```bash
# .env
TZ=Asia/Taipei
ANTHROPIC_AUTH_TOKEN=sk-ant-xxxxx
HOST_PROJECT_ROOT=/Users/yourname/aileron
```
:::

### 各服務關鍵設定

完整的環境變數參考請見 [環境變數參考](./environment-variables)，以下列出最常調整的項目：

**資料庫 (PostgreSQL)**
| 變數 | 預設值 | 說明 |
|------|--------|------|
| `POSTGRES_DB` | `aileron` | 主資料庫名稱 |
| `POSTGRES_USER` | `postgres` | 資料庫使用者 |
| `POSTGRES_PASSWORD` | `postgres` | 資料庫密碼 |

**Redis**
| 變數 | 預設值 | 說明 |
|------|--------|------|
| `--maxmemory` | `256mb` | 最大記憶體用量 |
| `--maxmemory-policy` | `allkeys-lru` | 記憶體淘汰策略 |

**Keycloak**
| 變數 | 預設值 | 說明 |
|------|--------|------|
| `KC_BOOTSTRAP_ADMIN_USERNAME` | `admin` | 管理員帳號 |
| `KC_BOOTSTRAP_ADMIN_PASSWORD` | `admin` | 管理員密碼 |
| `KC_HOSTNAME_URL` | `http://localhost:8080` | 對外 URL |

## Volume 掛載

### 持久化資料

| 路徑 | 容器路徑 | 說明 |
|------|----------|------|
| `./data/postgres` | `/var/lib/postgresql/data` | PostgreSQL 資料 |
| `./data/redis` | `/data` | Redis 持久化資料 |
| `./data/keycloak` | `/opt/keycloak/data` | Keycloak 資料 |
| `./data/workspace-data` | `/workspace` | 工作區專案檔案 |
| `./data/claude-data` | `/home/developer/.claude` | Claude Code session 資料 |
| `./data/workspace-scripts` | `/scripts` | 工作區腳本 |

### 開發用掛載

以下掛載是本地開發模式的核心。主機上的模組目錄會直接映射到容器內，因此前端、Manager、Runtime、Terminal 的程式碼修改通常可直接在容器內生效，不需要每次都重建整個 stack。

| 路徑 | 容器路徑 | 用途 |
|------|----------|------|
| `./workspace-manager` | `/workspace-manager` | Manager 程式碼熱重載 |
| `./workspace-runtime` | `/workspace-runtime` | Runtime 程式碼熱重載 |
| `./workspace-terminal` | `/workspace-terminal` | Terminal 程式碼熱重載 |
| `./frontend` | `/app` | Frontend 程式碼熱重載 |
| `/var/run/docker.sock` | `/var/run/docker.sock` | Docker Socket（容器管理用） |

### 開發 Image 與正式 Image 的差異

Aileron 的 Docker tag 有明確語意：

| Tag 類型 | 用途 | 程式碼來源 | 適用部署 |
|----------|------|------------|----------|
| `dev-*` | 本地開發與除錯 | 透過 volume mount 掛入主機程式碼 | Docker Compose 開發模式 |
| `latest-*` | 正式或類正式環境 | 已打包在 image 內 | Kubernetes、Helm、正式部署 |

以 `workspace-runtime` 為例，`dev-lite-amd64` 會使用 Dockerfile 的 development target。這類 image 預期由 `docker compose` 將 `./workspace-runtime` 掛載到容器內，因此 image 本身不一定包含完整的 `/workspace-runtime/app` 程式碼。

正式環境請使用 `latest-lite-amd64` 或同系列 `latest-*` tag。這類 image 使用 production target，會把 runtime 程式碼打包進 image，容器啟動時不依賴主機 volume mount。

:::caution Docker Socket 掛載
`workspace-manager` 與 `workspace-runtime` 都掛載了 Docker Socket，使其能動態建立和管理 workspace 容器。此設計僅適合開發環境，生產環境請使用 Kubernetes 模式。
:::

## 網路配置

所有服務使用同一個 bridge 網路 `aileron-network-dev`。

服務間以容器名稱互相訪問（DNS 解析由 Docker Compose 內建 DNS 處理），例如：
- `postgres:5432`
- `redis:6379`
- `workspace-manager:3001`
- `workspace-runtime:3002`

Keycloak 額外設定了 `localhost` 和 `keycloak` 兩個 network alias，以便容器內的 OIDC token 驗證能正確進行。

## 資源需求

| 服務 | CPU | 記憶體 | 說明 |
|------|-----|--------|------|
| workspace-browser | 2 核心上限 | 2GB 上限 / 1GB 保留 | neko WebRTC 最耗資源 |
| workspace-browser | — | 2GB SHM | 共享記憶體（Chrome 需要） |
| 其他服務 | 無限制 | 無限制 | 視實際使用動態分配 |

:::tip 建議配置
若只是在單機上體驗與驗證基本流程，建議至少使用 `4 vCPU / 8 GB RAM / 30 GB` 可用磁碟。若要較穩定地使用瀏覽器、自動化流程、Keycloak 與多個服務並行，建議提升到 `6-8 vCPU / 12-16 GB RAM / 50 GB` 可用磁碟。若同一台主機還會再跑 Harbor、registry、其他大型容器或額外開發服務，則應以 `16 GB RAM` 以上為起點，否則很容易進入 swap 或磁碟不足狀態。
:::

## 常用指令

```bash
# 啟動整個 stack（沿用本地 image；本地缺對應 tag 時 Compose 會自行 pull）
python scripts/dev/docker/ops.py up

# 先抓最新 dev image 再啟動
python scripts/dev/docker/ops.py up --pull

# 本地 build 後啟動（與 --pull 互斥）
python scripts/dev/docker/ops.py up --build

# 跨 arch 時固定 image 架構（例：在 arm64 主機上跑 amd64 模擬）
python scripts/dev/docker/ops.py up --pull --image-arch amd64

# 停止（保留 volumes）
python scripts/dev/docker/ops.py down

# 完整清理
python scripts/dev/docker/ops.py cleanup

# 停止並刪除 volumes
docker compose down -v

# 查看所有服務日誌
docker compose logs -f

# 查看特定服務日誌
docker compose logs -f workspace-manager
docker compose logs -f workspace-runtime
docker compose logs -f keycloak

# 重啟單一服務
docker compose restart workspace-runtime

# 重建單一服務
docker compose up -d --build workspace-runtime
```

日常整體操作請優先使用 `python scripts/dev/docker/ops.py ...`；`docker compose` 則保留給查看日誌、重啟單一服務、重建單一服務與低層除錯。

`ops.py up` 會依主機架構自動覆寫 Compose 使用的 image tag。預設會跳過 `docker compose pull`，沿用本地既有 image；加 `--pull` 會先抓最新 dev image，加 `--build` 則改為本地 build（兩者互斥）。stdin 是 TTY 時會詢問 image 架構，非互動模式請加 `--no-prompt` 並指定 `--image-arch` / `--runtime-base`。

## 清除

### 清除工作區容器（保留資料庫）

```bash
python scripts/dev/docker/ops.py cleanup-workspaces
```

僅移除動態建立的 workspace 容器、相關 volume 與 network。平台服務和資料庫不受影響。

### 完整清除

```bash
python scripts/dev/docker/ops.py cleanup
```

此流程會依序：
1. 刪除所有動態 workspace 容器
2. 停止 docker-compose 所有服務
3. 刪除 Docker volumes 和 networks
4. 清除 `data/` 目錄下的持久化資料（postgres、redis、keycloak、workspace-data 等）
5. 清除臨時目錄
6. 可選執行 Docker system prune

:::danger
完整清除會刪除所有資料庫資料，包含使用者、工作區設定、模板等。執行前確認已備份。
:::

清除後重新啟動：

```bash
python scripts/dev/docker/ops.py up --build
```

## 健康檢查

所有服務皆設定了健康檢查：

| 服務 | 檢查方式 | 間隔 | 初始延遲 |
|------|----------|------|----------|
| postgres | `pg_isready` | 10s | — |
| redis | `redis-cli ping` | 10s | — |
| keycloak | TCP port 8080 | 30s | 60s |
| workspace-manager | HTTP `/health` | 30s | — |
| workspace-runtime | HTTP `/health` | 30s | — |
| workspace-browser | HTTP `/health` | 30s | — |
| workspace-nextjs | HTTP `/health` | 15s | — |
| frontend | HTTP `/` | 30s | — |

## Docker 與 Kubernetes 的責任分界

| 面向 | Docker 模式 | Kubernetes 模式 |
|------|-------------|-----------------|
| 服務管理 | `docker compose` | Helm + Operator |
| Workspace 生命週期 | Docker container | Pod + Service + Ingress |
| 網路隔離 | Docker bridge network | Cilium Network Policy |
| 儲存 | Host volume mount | PVC (Persistent Volume Claim) |
| 認證 | 可選（Keycloak） | 必要（Keycloak + Ingress TLS） |
| 適合場景 | 開發、測試、Demo | 正式環境、多人協作 |

若需要 Kubernetes 部署，請參閱 [Kubernetes 模式](./kubernetes)。
