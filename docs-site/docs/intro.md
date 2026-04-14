---
slug: /
sidebar_position: 1
title: 簡介
---

# Aileron

**企業級 AI 代理的強韌編排平台（The Hardened Orchestration Layer for Enterprise AI Agents）**

Aileron 是一個專為企業環境設計的多 Agent workspace 與編排平台。它以容器化技術、Model Context Protocol (MCP)、可治理的模板中心，以及逐步擴充的 Agent 執行架構為核心，解決現有 AI 開發工具在**資安監控、環境隔離與大規模部署**上的痛點，讓團隊可以放心地把 AI Agent 引入日常工作流。

目前 Aileron 以 **Claude Code** 提供最完整的端到端體驗，包含對話執行、串流輸出、設定管理、自動化與 OpenSpec workflow 整合。同時，平台已朝多 Agent 架構演進，正逐步補齊 **OpenCode**、**Gemini**、**Codex** 等 agent 的整合能力。

## 🛡️ 為什麼選擇 Aileron？

### 安全隔離沙盒（Containerized Sandbox）

所有 AI 執行的指令（例如 Bash、Read、Write、Git）都在獨立的 Docker 容器或 Kubernetes Pod 中運作，搭配 **Cilium 網路政策**與 workspace / browser 分組的 domain allowlist，有效防止 Agent 誤刪檔案、逃逸宿主機或存取未授權資源。每個 workspace 都有獨立的 runtime、檔案系統與網路界線。

### 統一規範模板（Standardized Templates）

透過**模板中心**預先定義不同情境的 Slash Commands、MCP Servers、安裝流程與環境變數，讓團隊可以一鍵建立符合公司規範的工作區。模板確保開發風格一致、權限可控，並把安全策略內建到每一個 Agent 的起手式中。

### 雲地混合彈性（Hybrid & Pluggable Runtime）

目前以 Claude Code CLI / SDK 為預設且功能最完整的執行引擎，並透過 MCP 協定串接內部服務與工具。平台架構與模型解耦，可依治理需求搭配不同雲端或地端模型，並逐步擴展到 OpenCode、Gemini、Codex 等不同 agent 執行路徑。

### 企業級認證與治理

原生整合 **Keycloak OAuth2 / OIDC**，支援 SSO、角色權限與使用者配額；平台層服務（Manager、Runtime、Terminal、Browser）全部走統一認證，審計與追蹤不再需要額外接線。

### OpenSpec 原生工作流

OpenSpec 已整合為 Aileron 的 workspace 內建能力，而不只是附屬命令集合。使用者可以直接在 workspace 中瀏覽 `openspec/` 文件、查看目前 change 狀態，並從 chat composer 直接發動 proposal、explore、apply、archive 等 workflow。

## 🧩 主要功能

| 功能 | 說明 |
|------|------|
| Workspace 生命週期管理 | 建立、啟動、停止、刪除工作區，同時支援 Docker Compose 與 Kubernetes（workspace-operator + CRD） |
| 多 Agent 執行架構 | 以 Claude Code 為目前最完整整合，並持續擴充 OpenCode、Gemini、Codex 等 agent 支援 |
| OpenSpec 工作流 | 在 workspace 中原生瀏覽 OpenSpec 文件、掌握 change 狀態，並從 chat composer 發動 workflow actions |
| 模板化工作區 | Slash Commands、MCP Server、環境變數、安裝流程一次設定，團隊共用 |
| 多型態 Runtime | Terminal (Go-based PTY)、Chrome/Browser、Next.js，皆可作為 Agent 可操作的執行載體 |
| 檔案總管與 Git | 即時檔案監控、版本控制操作、分支管理 |
| Scheduler / Automation | Cron 定時任務可結合 agent workflow 執行，目前以 Claude Code 體驗最完整 |
| Keycloak OAuth2 / OIDC | 企業級認證，支援 SSO 與角色權限 |
| 防火牆政策 | 以 Cilium 為基礎的 domain allowlist，workspace 與 browser 分組管理 |

## Agent 支援狀態

| Agent | 狀態 | 說明 |
|------|------|------|
| Claude Code | 完整支援 | 目前功能最完整，包含聊天、設定管理、自動化與 OpenSpec workflow 整合 |
| Gemini | 部分支援 | 已有設定與整合基礎，端到端能力持續補齊中 |
| OpenCode | 部分支援 | 已有設定與整合基礎，後續會擴充更多 workflow 與執行能力 |
| Codex | 部分支援 | 已有設定與整合基礎，後續會補齊更多執行與治理能力 |

## 專案狀態

Aileron 目前以 **100% Vibe Coding** 的方式快速開發與演進。這讓我們能更快驗證多 Agent workspace、OpenSpec workflow 與企業治理能力，但也代表部分功能、文件與使用體驗仍會持續調整。

如果你正在試用這個專案，歡迎協助：

- 測試功能與回報問題
- 提交修正建議或 PR
- 分享實際使用情境與需求

## Roadmap

- 補齊 OpenCode、Gemini、Codex 等 agent 的能力一致性
- 持續強化 OpenSpec 在 workspace 內的原生工作流體驗
- 擴展更完整的團隊協作與治理能力
- 導入 worktree 導向的開發流程，支援更自然的多任務並行與隔離

## 🛠️ 技術棧

- **Runtime**：Claude Code CLI / OpenSpec CLI，並逐步擴展多 Agent CLI 整合
- **Orchestrator**：Python + FastAPI（workspace-manager / workspace-runtime）
- **Interface**：React-based Web UI、Go-based Web Terminal
- **Integration**：Chrome Extension (WXT/MV3)、Next.js Workspace、MCP Servers
- **Platform**：Docker Compose、Kubernetes (Helm + workspace-operator)、Cilium
- **Infrastructure**：PostgreSQL、Redis、Keycloak

## 部署模式

```
┌─────────────────────────────────────────────────────────────────┐
│                            Aileron                             │
├────────────────────────┬────────────────────────────────────────┤
│     Docker 模式        │            Kubernetes 模式             │
│                        │                                        │
│  docker compose        │  Helm chart → platform services        │
│  本地開發、快速體驗    │  workspace-operator → workspace CRs    │
│                        │  Cilium → firewall policy              │
└────────────────────────┴────────────────────────────────────────┘
```

詳見 [部署說明](/deployment/docker)。

## 系統架構

```
┌──────────────────────────────────────────────────┐
│                    Frontend (React)              │
│   Workspace List │ Chat Panel │ File Explorer    │
│   Git │ Settings │ Automation Dashboard          │
└─────────────────────────┬────────────────────────┘
                          │ REST / WebSocket
┌─────────────────────────▼────────────────────────┐
│              Workspace Manager (FastAPI)         │
│   Workspace CRUD │ Templates │ Automation        │
│   Auth (Keycloak) │ Teams │ Docker/K8s Provisioner │
└──────────┬──────────────────────┬────────────────┘
           │ HTTP                 │ Docker / K8s API
┌──────────▼──────┐    ┌──────────▼──────────────┐
│ Workspace       │    │  Container / Pod        │
│ Runtime         │    │  (workspace-runtime)    │
│ (FastAPI)       │◄───►  Agent Runtime │ Files   │
│                 │    │  OpenSpec │ Git │ Terminal │
└─────────────────┘    └─────────────────────────┘
           │
┌──────────▼──────────────────────────────────────┐
│                 Infrastructure                  │
│   PostgreSQL │ Redis │ Keycloak │ Cilium        │
└─────────────────────────────────────────────────┘
```

## 快速開始

```bash
git clone <your-repo-url>
cd aileron
docker compose up -d --build
```

完整安裝說明請看 [安裝指南](/quick-start/installation)。
