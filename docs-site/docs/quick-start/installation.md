---
sidebar_position: 1
title: 安裝與啟動
---

# 安裝與啟動

預設的 Docker Compose 方案旨在讓團隊能快速從零開始，建立可用的企業級 agent 工作區平台，而不必先手動組裝所有工具鏈與服務。

## 需求

- [Docker](https://docs.docker.com/get-docker/)
- [Docker Compose](https://docs.docker.com/compose/install/)（通常已內建於 Docker Desktop）

## 標準 Host CLI

`python scripts/dev/docker/ops.py` 是目前正式的 host-side CLI，用於本機 Docker 操作。文件中的分工原則如下：整體 stack 的啟動、停止、清理與測試執行，優先使用 `ops.py`；模組開發時的即時觀察、單一服務重建與低層除錯，則使用 `docker compose`。

第一次使用前，先查看可用子指令：

```bash
python scripts/dev/docker/ops.py --help
python scripts/dev/docker/ops.py test --help
```

## 第一次啟動

### Windows PowerShell

```powershell
git clone <your-repo-url>
cd aileron
python .\scripts\dev\docker\ops.py up --build
```

### macOS / Linux

```bash
git clone <your-repo-url>
cd aileron
python scripts/dev/docker/ops.py up --build
```

:::info 建置時間
第一次啟動需要建置所有映像，約需 5～10 分鐘。
:::

## 確認服務狀態

```bash
docker compose ps
```

建議等到以下服務全部進入 `healthy` 狀態後，再打開前端：

- `postgres`
- `redis`
- `keycloak`（初始化較慢，約 60 秒）
- `workspace-manager`
- `frontend`

:::warning Keycloak 尚未就緒
若 Keycloak 尚未完成初始化就嘗試登入，前端會顯示 OIDC 認證失敗。請等到 `keycloak` 狀態為 `healthy`。
:::

## 停止整個 Stack

### Windows PowerShell

```powershell
python .\scripts\dev\docker\ops.py down
```

### macOS / Linux

```bash
python scripts/dev/docker/ops.py down
```

此操作只會停止 stack，保留 volumes 與持久化平台資料。

## 常用指令

| 操作 | 指令 |
|------|------|
| 啟動所有服務 | `python scripts/dev/docker/ops.py up` |
| 重建映像後啟動 | `python scripts/dev/docker/ops.py up --build` |
| 停止所有服務 | `python scripts/dev/docker/ops.py down` |
| 清理工作區資源 | `python scripts/dev/docker/ops.py cleanup-workspaces` |
| 完整清理 | `python scripts/dev/docker/ops.py cleanup` |
| 查看所有日誌 | `docker compose logs -f` |
| 查看特定服務日誌 | `docker compose logs -f workspace-manager` |

## 清理環境

日常重置 workspace 時優先使用 `cleanup-workspaces`；只有在需要完整重建本機環境時才使用 `cleanup`。

### Workspace 清理

移除動態 workspace 容器與相關暫時資源，同時保留主要平台 stack 與資料庫。

Windows PowerShell：

```powershell
python .\scripts\dev\docker\ops.py cleanup-workspaces
```

macOS / Linux：

```bash
python scripts/dev/docker/ops.py cleanup-workspaces
```

若仍需使用舊版平台專用 wrapper，可參考 `scripts/dev/docker/` 目錄中的既有腳本；文件中的主要路徑以 `python scripts/dev/docker/ops.py` 為準。

### 完整清理

停止 stack、移除平台 volumes，並清除本機持久化資料。

Windows PowerShell：

```powershell
python .\scripts\dev\docker\ops.py cleanup
```

macOS / Linux：

```bash
python scripts/dev/docker/ops.py cleanup
```

:::danger 完整清理
`cleanup` 會刪除所有 Docker volumes，包含 PostgreSQL 資料。執行前請先確認重要資料已備份。
:::

若仍需使用舊版平台專用 wrapper，可參考 `scripts/dev/docker/` 目錄中的既有腳本；文件中的主要路徑以 `python scripts/dev/docker/ops.py` 為準。

## 清理後重新啟動

不論執行 `cleanup-workspaces` 或 `cleanup`，清理完成後都可透過標準 host-side CLI 重新啟動。

### Windows PowerShell

```powershell
python .\scripts\dev\docker\ops.py up --build
```

### macOS / Linux

```bash
python scripts/dev/docker/ops.py up --build
```

## 本地模組開發

Docker Compose 本身就是 Aileron 預設的本地開發方式。進行模組開發時，應先完整啟動整個 stack，而不是把主要服務獨立拉到宿主機執行：

```bash
docker compose up -d
```

在這個模式下，開發中的模組目錄會直接掛載到對應容器內，修改後通常可即時反映，不需要每次都重新建置整個環境：

- `./frontend` → `/app`
- `./workspace-manager` → `/workspace-manager`
- `./workspace-runtime` → `/workspace-runtime`
- `./workspace-terminal` → `/workspace-terminal`

這代表前端、Manager、Runtime、Terminal 的程式碼變更，會透過既有的開發用掛載與 reload 機制直接反映到容器內。只有在 Dockerfile、系統依賴或映像層內容改動時，才需要再執行 `docker compose up -d --build`。

若要查看個別服務狀態或追蹤變更是否生效，可搭配：

```bash
docker compose ps
docker compose logs -f workspace-manager
docker compose logs -f workspace-runtime
docker compose logs -f frontend
```

:::tip 初次體驗
第一次使用時，先用 `ops.py` 完成環境啟動與清理；進入日常開發後，再使用 `docker compose ps`、`docker compose logs -f`、`docker compose up -d --build <service>` 這類指令追蹤與調整單一服務。
:::
