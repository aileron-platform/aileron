---
sidebar_position: 2
title: Workspace Manager
---

# Workspace Manager

## 概覽

Workspace Manager 是 Aileron 的核心服務，負責管理開發工作區的完整生命週期，包括建立、設定、啟動、停止和刪除。

## 核心功能

### 工作區管理
- **CRUD**：建立、讀取、更新、刪除工作區
- **容器管理**：Docker / Kubernetes / Podman 容器生命週期控制
- **範本支援**：基於預設範本快速建立工作區
- **網路配置**：防火牆規則和端口映射管理

### 團隊協作
- **多用戶支援**：工作區成員管理
- **權限控制**：基於角色的存取控制（RBAC）
- **團隊管理**：團隊建立和成員邀請

### 範本中心
- **範本管理**：專案範本的建立和管理
- **特徵標記**：範本特徵分類和篩選
- **版本控制**：範本版本管理

### 自動化任務
- **Cron 排程**：Cron 表達式支援的定時任務
- **AI 整合**：可驅動 agent workflow 的自動化任務，目前以 Claude Code 最完整
- **執行監控**：任務執行狀態和結果追蹤

## 技術架構

| 元件 | 技術 |
|------|------|
| Web 框架 | FastAPI |
| ORM | SQLAlchemy |
| 資料庫 | PostgreSQL |
| 快取 / 佇列 | Redis |
| 背景任務 | Celery |
| 容器管理 | Docker / Kubernetes / Podman |
| 認證 | Keycloak JWT |

## 目錄結構

```
workspace-manager/
├── app/
│   ├── celery/            # Celery 背景任務設定
│   ├── config/            # 配置模組
│   ├── core/              # 核心功能
│   ├── db/                # 資料庫連線與遷移
│   ├── jinja_templates/   # Jinja2 模板
│   ├── middleware/        # 中間件
│   ├── models/            # SQLAlchemy 資料模型
│   ├── modules/           # 功能模組
│   ├── routers/           # API 路由
│   ├── services/          # 業務邏輯層
│   ├── tasks.py           # Celery 任務定義
│   ├── translations/      # 多語系資源
│   └── utils/             # 工具函數
├── scripts/               # 部署腳本
├── tests/                 # 測試
├── pyproject.toml
└── Dockerfile
```

## 環境變數

### 基礎設定

| 變數名 | 預設值 | 說明 |
|--------|--------|------|
| `DATABASE_URL` | — | PostgreSQL 連線 URL |
| `REDIS_URL` | — | Redis 連線 URL |
| `SECRET_KEY` | — | JWT 簽名密鑰 |
| `DOCKER_HOST` | `unix:///var/run/docker.sock` | Docker 主機 |
| `DEBUG` | `false` | 除錯模式 |

### Keycloak 認證設定（可選）

| 變數名 | 預設值 | 說明 |
|--------|--------|------|
| `ENABLE_AUTH` | `false` | 啟用 Keycloak OAuth2/OIDC |
| `KEYCLOAK_SERVER_URL` | — | Keycloak 伺服器 URL（含 realm） |
| `KEYCLOAK_REALM` | `aileron` | Keycloak realm 名稱 |
| `KEYCLOAK_CLIENT_ID` | — | OAuth2 客戶端 ID |
| `KEYCLOAK_CLIENT_SECRET` | — | OAuth2 客戶端密鑰 |
| `JWT_ALGORITHM` | `RS256` | JWT 驗證算法 |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | `30` | Access token 有效期（分鐘） |

### 啟用 Keycloak 認證

1. 設定 `ENABLE_AUTH=true`
2. 設定 Keycloak 相關環境變數
3. 重新啟動服務

:::note
啟用認證後，所有 API 端點將要求有效的 JWT token。
:::

## 本地開發

```bash
cd workspace-manager

# 安裝依賴（使用 uv）
uv sync

# 啟動服務
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 3001
```

## 測試

```bash
# 執行所有測試
pytest

# 執行測試並生成覆蓋率報告
pytest --cov=app --cov-report=html

# 容器化測試（推薦）
make test-workspaces

# lint 與靜態檢查
make lint-workspaces
```

:::tip 容器化測試
建議優先使用容器化測試，避免本機缺少 PostgreSQL headers 或 Python 依賴造成驗證失敗。
:::

## 監控

| 服務 | URL | 說明 |
|------|-----|------|
| 健康端點 | `http://localhost:3001/health` | 確認服務與 DB / Redis 狀態 |
| Swagger UI | `http://localhost:3001/docs` | 互動式 API 文件 |
| ReDoc | `http://localhost:3001/redoc` | 靜態 API 文件 |
| Flower | `http://localhost:5555` | Celery 任務監控 |
