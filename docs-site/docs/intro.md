---
slug: /
title: 簡介
---

# Aileron

**企業級 AI 代理的強韌編排平台（The Hardened Orchestration Layer for Enterprise AI Agents）**

Aileron 是一個專為企業環境設計的多 Agent workspace 與編排平台。它以容器化技術、Model Context Protocol (MCP)、可治理的 Marketplace，以及完整的多 Agent 執行架構為核心，解決現有 AI 開發工具在**資安監控、環境隔離與大規模部署**上的痛點，讓團隊可以放心地把 AI Agent 引入日常工作流。

目前 Aileron 已將 **Claude Code**、**OpenCode** 與 **Codex** 作為第一級 Agent 執行引擎完整支援，包含對話執行、串流輸出、設定管理與自動化。平台以多 Agent 架構為核心，讓團隊可以依照任務、模型供應商與治理需求選擇合適的 Agent 執行路徑。

## 🛡️ 為什麼選擇 Aileron？

### 安全隔離沙盒（Containerized Sandbox）

所有 AI 執行的指令（例如 Bash、Read、Write、Git）都在獨立的 Docker 容器或 Kubernetes Pod 中運作，每個 workspace 都有獨立的 runtime、檔案系統與網路界線。Docker 模式由 Runtime 套用 iptables egress 規則，Kubernetes 模式則由 workspace-operator 產生 Cilium 網路政策；兩種模式都分開管理 workspace 與 browser 的 domain allowlist，以降低 Agent 非預期存取檔案或外部資源的風險。

### 兩條一次性 Marketplace 路徑

**Marketplace** 提供兩條彼此獨立的一次性路徑：Plugin artifact 先發佈到團隊 private GitLab repository，再由相容 Target Client 的標準 CLI 安裝並啟用；user-copy 則把相容資源一次性投影到 Workspace Runtime HOME 的 user scope。成功後 standalone resources 由使用者自行更新或移除，Marketplace 不建立安裝後 lifecycle。

### 降低非技術使用門檻

Aileron 之所以值得選擇，其中一個重要原因，是它大幅簡化了 AI agent 環境建置與 CLI 工具使用的門檻。過去這類流程常仰賴工程背景與繁瑣設定，對非技術人員並不友善；Aileron 則透過更一致、直覺的操作方式，降低學習成本與導入阻力，讓產品、營運、設計或業務等角色也能更快參與實際使用。這不僅減少對工程團隊的依賴，也讓整個團隊能把更多時間投入在應用落地、流程驗證與協作效率提升上。

### 雲地混合彈性（Hybrid & Pluggable Runtime）

Claude Code、OpenCode 與 Codex 都是 workspace 內完整支援的第一級 Agent 執行引擎，並透過 MCP 協定串接內部服務與工具。平台架構與模型解耦，可依治理需求搭配不同雲端或地端模型與 Agent CLI。

### 企業級認證與治理

原生整合外部 **OIDC**，支援 SSO、角色權限與使用者配額。Manager 是唯一 provider trust
boundary；Frontend 使用 opaque session，Runtime 與 Terminal 使用短效 Execution Grant，
讓 execution plane 不接觸 provider token。

## 🧩 主要功能

| 功能 | 說明 |
|------|------|
| [Workspace 生命週期管理](/features/workspace/lifecycle-and-access) | 建立、啟動、停止、刪除工作區，支援 Docker 動態 provisioner 與 Kubernetes（workspace-operator + CRD） |
| [多 Agent 執行架構](/features/workspace/ai-agent/) | 完整支援 Claude Code、OpenCode、Codex 等 Agent 執行路徑 |
| [Marketplace 套件](/features/marketplace) | Plugin artifact 經 private GitLab 發佈後由相容 Target Client CLI 一次性安裝並啟用；user-copy 投影 standalone resources 到 Workspace user scope |
| [多型態 Runtime](/architecture/backend/workspace-runtime/) | Terminal (Go-based PTY)、Chrome/Browser、Next.js，皆可作為 Agent 可操作的執行載體 |
| [檔案總管與 Git](/api/runtime-api#檔案管理) | 檔案讀寫、local history、版本控制操作與分支管理 |
| [Scheduler / Automation](/features/automation) | Cron 定時任務可結合 Claude Code、OpenCode、Codex Agent 工作流程執行 |
| [外部 OIDC](/installation/oidc) | Manager BFF 企業級 SSO、opaque session 與 execution-plane Grant |
| 防火牆政策 | Docker 使用 Runtime-local iptables，Kubernetes 使用 Cilium；兩者都將 workspace 與 browser domain allowlist 分組管理 |
| [Knowledge Base](/features/knowledge-base/) | 保存團隊知識、專案規範與操作手冊，可授權共享並零複製唯讀掛載到 Workspace |
| [Question Form](/features/workspace/ai-agent/ai-chat) | 讓 agent 在聊天中提出結構化選項表單，取代要求使用者手動輸入選項文字 |

## Agent 支援狀態

| Agent | 狀態 | 說明 |
|------|------|------|
| Claude Code | 完整支援 | 支援聊天、設定管理與自動化 |
| OpenCode | 完整支援 | 支援聊天、設定管理與自動化 |
| Codex | 完整支援 | 支援聊天、設定管理與自動化 |

## 專案狀態

Aileron 目前以 **100% Vibe Coding** 的方式快速開發與演進。這讓我們能更快驗證多 Agent workspace 與企業治理能力，但也代表部分功能、文件與使用體驗仍會持續調整。

如果你正在試用這個專案，歡迎協助：

- 測試功能與回報問題
- 提交修正建議或 PR
- 分享實際使用情境與需求

## Roadmap

- 持續強化 Claude Code、OpenCode、Codex 的跨 Agent 體驗一致性
- 擴展更完整的團隊協作與治理能力
- 導入 worktree 導向的開發流程，支援更自然的多任務並行與隔離

## 🛠️ 技術棧

- **Runtime**：Claude Code CLI / OpenCode CLI / Codex CLI
- **Orchestrator**：Python + FastAPI（workspace-manager / workspace-runtime）
- **Interface**：React-based Web UI、Go-based Web Terminal
- **Integration**：Chrome Extension (WXT/MV3)、Next.js Workspace、MCP Servers
- **Platform**：Docker + Docker Compose + iptables、Kubernetes (Helm + workspace-operator) + Cilium
- **Infrastructure**：PostgreSQL、Redis、外部 OIDC provider

## 部署模式

```text
┌─────────────────────────────────────────────────────────────────┐
│                            Aileron                             │
├────────────────────────┬────────────────────────────────────────┤
│     Docker 模式        │            Kubernetes 模式             │
│                        │                                        │
│  docker compose        │  Helm chart → platform services        │
│    → platform services │  workspace-operator → workspace CRs    │
│  Docker SDK → Workspace│  Cilium → firewall policy              │
│    containers          │                                        │
│  iptables → firewall   │                                        │
└────────────────────────┴────────────────────────────────────────┘
```

詳見 [安裝說明](/installation/docker)。

## 系統架構

Aileron 採用 Frontend、Workspace Manager、Workspace Runtime 三層微服務架構，Manager 負責 Workspace CRUD、Marketplace、Automation 與 Docker／Kubernetes provisioning，Runtime 則在每個 Workspace 容器內提供 Agent 執行、檔案與 Git 操作。完整元件圖與資料流請見 [架構概覽](/architecture/overview/)。

## 快速開始

```bash
git clone <your-repo-url>
cd aileron
docker buildx bake --load local
docker compose up --remove-orphans --no-build -d
```

完整安裝說明請看 [安裝指南](/installation/getting-started)。
