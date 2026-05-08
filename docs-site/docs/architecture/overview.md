---
sidebar_position: 1
title: 架構概覽
---

# 架構概覽

Aileron 採用微服務架構，各服務職責明確、可獨立部署。

目前平台以 Claude Code 提供最完整的 agent 體驗，但整體架構並不侷限於單一工具，而是朝多 Agent workspace platform 演進，並已納入 OpenSpec 內建 workflow 能力。

## 系統元件

```
┌─────────────────────────────────────────────────────────────────┐
│                        使用者（瀏覽器）                          │
└───────────────────────────────┬─────────────────────────────────┘
                                │ HTTPS / WebSocket
┌───────────────────────────────▼─────────────────────────────────┐
│                    Frontend (React + Vite)                       │
│  ┌─────────────┐ ┌──────────────┐ ┌─────────────────────────┐  │
│  │ Workspace   │ │ Chat Panel   │ │ File Explorer / Git /   │  │
│  │ List / Mgmt │ │ (Agent Chat) │ │ Settings / Automation   │  │
│  └─────────────┘ └──────────────┘ └─────────────────────────┘  │
└───────────────────────────────┬─────────────────────────────────┘
                                │ REST API
┌───────────────────────────────▼─────────────────────────────────┐
│              Workspace Manager (Python / FastAPI)                │
│  ┌──────────────┐ ┌──────────────┐ ┌───────────────────────┐   │
│  │ Workspace    │ │ Marketplace  │ │ Automation / Celery   │   │
│  │ CRUD + Auth  │ │ + Settings   │ │ Scheduler             │   │
│  └──────────────┘ └──────────────┘ └───────────────────────┘   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │        Docker / Kubernetes / Podman Provisioner          │   │
│  └──────────────────────────────────────────────────────────┘   │
└──────────┬────────────────────────────┬────────────────────────┘
           │ REST                        │ Container API
           │                   ┌─────────▼────────────┐
           │                   │  Container / Pod      │
┌──────────▼──────────┐        │                      │
│  Workspace Runtime  │        │  workspace-terminal  │
│  (FastAPI)          │◄──────►│  workspace-chrome    │
│  per workspace      │        │  workspace-nextjs    │
│  Agent Runtime API  │        │                      │
│  OpenSpec / Sessions│        │                      │
│  File Watch / Git   │        └──────────────────────┘
│  System Monitor     │
│  WebSocket          │
└─────────────────────┘
           │
┌──────────▼──────────────────────────────────────────┐
│                    Infrastructure                    │
│  ┌──────────────┐  ┌──────────┐  ┌───────────────┐  │
│  │  PostgreSQL  │  │  Redis   │  │   Keycloak    │  │
│  │  (main DB)   │  │  (cache/ │  │  (OAuth2/OIDC)│  │
│  │              │  │   queue) │  │               │  │
│  └──────────────┘  └──────────┘  └───────────────┘  │
└─────────────────────────────────────────────────────┘
```

## 服務說明

### Frontend
React + Vite 前端應用，提供完整的 workspace 管理介面，包含：
- Workspace 建立、管理、設定
- Agent 聊天面板（目前以 Claude Code 體驗最完整，支援串流）
- 檔案總管與 Git 操作
- OpenSpec 導覽與 workflow actions
- Automation Dashboard
- Keycloak OIDC 整合

### Workspace Manager
核心後端服務（FastAPI），負責：
- Workspace CRUD 與生命週期管理
- 多 provisioner 支援（Docker、Kubernetes、Podman）
- Marketplace 套件管理
- 團隊管理與治理能力
- 自動化任務（Celery + Redis）
- 認證（Keycloak JWT 驗證）

### Workspace Runtime
每個 workspace 容器內部的服務（FastAPI），負責：
- Agent 執行與串流（目前以 Claude Code 最完整）
- OpenSpec CLI 與 workflow 狀態整合
- 檔案系統監控（Watchdog）
- Git 操作
- 系統資源監控（psutil）
- WebSocket 即時通訊

### Workspace 附屬服務

| 服務 | 說明 |
|------|------|
| `workspace-terminal` | 在瀏覽器中提供終端機存取 |
| `workspace-chrome` | Headless Chromium，供 browser preview 使用 |
| `workspace-nextjs` | 選用的 Next.js dev server |

## 目錄結構

```
aileron/
├── frontend/               # React + Vite 前端
├── workspace-manager/      # 核心管理服務（Python/FastAPI）
├── workspace-runtime/      # Workspace 執行環境（Python/FastAPI）
├── workspace-terminal/     # 終端機服務
├── workspace-chrome/       # Chrome 瀏覽器服務
├── workspace-nextjs/       # Next.js 服務
├── workspace-operator/     # Kubernetes Operator
├── helm/                   # Helm chart（Kubernetes 部署）
├── keycloak-realm/         # Keycloak realm 設定
├── scripts/                # 部署與維護腳本
├── data/                   # 本地開發資料（gitignored）
└── docker-compose.yml      # Docker Compose 設定
```

## 資料流

### Workspace 建立流程

```
Frontend
  │  POST /api/v1/workspaces
  ▼
Workspace Manager
  │  選擇 Provisioner（Docker / K8s）
  │  建立容器/Pod
  │  儲存 workspace 記錄至 PostgreSQL
  ▼
Container / Pod
  │  workspace-runtime 啟動
  │  向 Manager 報告狀態
  ▼
Frontend
  │  WebSocket 接收狀態更新
  ▼
（可使用 Chat、Files、Terminal）
```

### Agent 執行流程

```
Frontend (Chat Panel)
  │  POST /api/v1/agent-sessions
  ▼
Workspace Runtime
  │  建立 Agent Session
  │  執行對應 Agent CLI
  │  串流輸出
  ▼
WebSocket → Frontend
  │  即時顯示輸出
```
