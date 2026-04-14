---
sidebar_position: 1
title: 安裝與啟動
---

# 安裝與啟動

## 需求

- [Docker](https://docs.docker.com/get-docker/)
- [Docker Compose](https://docs.docker.com/compose/install/)（通常已內建於 Docker Desktop）

## 第一次啟動

```bash
git clone <your-repo-url>
cd aileron
docker compose up -d --build
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

## 常用指令

| 操作 | 指令 |
|------|------|
| 啟動所有服務 | `docker compose up -d` |
| 重建映像後啟動 | `docker compose up -d --build` |
| 停止所有服務 | `docker compose down` |
| 查看所有日誌 | `docker compose logs -f` |
| 查看特定服務日誌 | `docker compose logs -f workspace-manager` |

## 清除環境

清除工作區容器（保留資料庫）：

```bash
./scripts/dev/docker/cleanup-workspaces.sh
```

完整清除所有資料（資料庫、volumes、容器）：

```bash
./scripts/dev/docker/cleanup.sh
```

:::danger 完整清除
`cleanup.sh` 會刪除所有 Docker volumes，包含 PostgreSQL 資料。執行前確認已備份重要資料。
:::

清除後重新啟動：

```bash
docker compose up -d --build
```

## 本地模組開發

若需要單獨開發某個服務：

```bash
# 前端
cd frontend && npm install && npm run dev

# Workspace Manager
cd workspace-manager && uv sync && uv run uvicorn app.main:app --reload --port 3001

# Workspace Runtime
cd workspace-runtime && uv sync && uv run uvicorn app.main:app --reload --port 3002
```

:::tip 初次體驗
如果是第一次使用，建議直接用 Docker Compose 啟動，不需要先跑本地模組開發。
:::
