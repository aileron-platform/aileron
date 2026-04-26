---
sidebar_position: 3
title: Workspace Runtime
---

# Workspace Runtime

## 概覽

Workspace Runtime 是運行在每個開發工作區容器內的服務，提供 Agent 執行整合、OpenSpec CLI 能力、檔案監控、系統監控和 WebSocket 通訊等功能。目前以 Claude Code 的整合最完整。

## 核心功能

### Agent 執行整合
- **設定管理**：Agent 設定的讀取與更新，目前以 Claude Code 最完整
- **Hooks 管理**：自訂 hooks 設定與管理
- **MCP 整合**：MCP 伺服器設定管理
- **子代理管理**：Claude Code 子代理設定
- **斜線命令**：自訂斜線命令管理
- **OpenSpec CLI**：提供 workspace 內建的 OpenSpec workflow 基礎能力

### 檔案系統管理
- **即時監控**：使用 Watchdog 監控檔案變更
- **同步通知**：透過 WebSocket 推送檔案變更事件
- **版本控制**：Git 整合和操作
- **智慧忽略**：自動忽略 `node_modules`、`.git`、`__pycache__` 等

### 系統監控
- **資源監控**：CPU、記憶體、磁碟使用率（psutil）
- **程序管理**：開發程序生命週期管理
- **效能指標**：系統效能指標收集

### WebSocket 通訊
- **即時雙向通訊**：與前端的即時通訊
- **事件廣播**：Agent Session 事件推送
- **心跳機制**：連線狀態維護

## 技術架構

| 元件 | 技術 |
|------|------|
| Web 框架 | FastAPI |
| 即時通訊 | WebSockets |
| 檔案監控 | Watchdog |
| 系統監控 | psutil |
| AI 客戶端 | Anthropic SDK / 多 Agent CLI 整合 |
| 版本控制 | GitPython |

## Image Variants

Workspace Runtime 支援兩種 base image flavor：

| Flavor | 適用場景 | 說明 |
|--------|----------|------|
| `lite` | 預設的 agent workspace | 保留 agent CLI、Python、Node.js、Git、Docker CLI、常用 shell 工具與 OpenSpec CLI，適合平台預設工作區 |
| `codex` | 需要完整多語言工具鏈的 workspace | 使用 codex-universal base，包含更完整的語言 runtime 與開發工具，映像較大 |

`base-lite` 會包含平台執行所需的基本工具：

- Shell 與建置工具：`bash`、`build-essential`、`make`、`pkg-config`
- 版本控制與檔案工具：`git`、`git-lfs`、`ripgrep`、`fd`、`rsync`
- 語言與套件基礎：Python 3、Node.js、`pnpm`、`uv`
- 系統工具：`curl`、`wget`、`jq`、`sudo`、`openssh-client`

`base-lite` 不包含 Java runtime / JDK，也不包含 Go compiler 或 `/usr/local/go`。Java 或完整多語言開發需求應使用 `codex` flavor。

`terminal-service` 是 Go binary，但 Go toolchain 不會進入 runtime image。`workspace-runtime/Dockerfile` 會在獨立的 `golang:1.23` builder stage 編譯 binary，再把 `/opt/terminal-service/bin/terminal-service` 複製到 `development` 與 `production` image。

本機建置預設使用 `lite`：

```bash
make build-runtime-base
make build-workspace-runtime
```

需要切換到 codex-universal base 時，明確指定 `RUNTIME_BASE=universal`：

```bash
RUNTIME_BASE=universal make build-runtime-base
RUNTIME_BASE=universal make build-workspace-runtime
```

## 目錄結構

```
workspace-runtime/
├── app/
│   ├── config/            # 配置模組
│   ├── core/              # 核心功能
│   ├── database/          # 資料庫連線
│   ├── middleware/        # 中間件
│   ├── models/            # 資料模型
│   ├── modules/           # 功能模組（主要路由）
│   ├── routers/           # 共用路由
│   ├── services/          # 業務邏輯
│   ├── translations/      # 多語系資源
│   └── utils/             # 工具函數
├── scripts/               # 啟動腳本
├── tests/
├── pyproject.toml
└── Dockerfile
```

## 環境變數

| 變數名 | 預設值 | 說明 |
|--------|--------|------|
| `WORKSPACE_ID` | `default` | 工作區識別碼 |
| `WORKSPACE_PATH` | `/workspace` | 工作區路徑 |
| `MANAGER_URL` | — | Workspace Manager URL |
| `MONITOR_INTERVAL` | `5` | 系統監控間隔（秒） |

:::note Agent Credentials
目前最常見的是透過前端「環境變數」設定頁面動態注入 Claude API Key。隨著更多 agent 整合補齊，其他執行器所需憑證也應採用相同方式注入，不應寫死在容器環境變數中。
:::

## WebSocket 事件

連接 WebSocket：

```javascript
const ws = new WebSocket('ws://localhost:3002/api/v1/ws');

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  switch (data.type) {
    case 'file_changed':
      console.log('檔案變更:', data.path);
      break;
    case 'system_stats':
      console.log('系統狀態:', data.stats);
      break;
    case 'agent_output':
      console.log('Agent 輸出:', data.content);
      break;
  }
};
```

## 本地開發

```bash
docker compose up -d workspace-runtime
```

`workspace-runtime` 的本地開發也應以 Docker Compose 為主，並與整體平台服務一起運作。Compose 會將 `./workspace-runtime` 掛載到容器內的 `/workspace-runtime`，因此程式碼調整通常能透過既有 reload 機制直接反映。

若需要驗證完整 agent workflow、WebSocket、檔案監控與其他跨服務行為，建議直接啟動完整 stack：

```bash
docker compose up -d
```

## 測試

```bash
# 執行所有測試
pytest

# 執行特定測試
pytest tests/test_file_watcher.py -v
pytest tests/test_websocket.py -v
pytest tests/test_system_monitor.py -v
```

## 監控指標

### 系統指標
- CPU 使用率（即時百分比）
- 記憶體使用量與可用量
- 磁碟空間使用情況
- 網路 I/O 統計

### 應用指標
- 檔案變更次數
- WebSocket 活躍連線數
- 錯誤率

## API 端點

| 端點 | 說明 |
|------|------|
| `GET /health` | 健康檢查 |
| `GET /api/v1/files/*` | 檔案管理 |
| `GET /api/v1/settings` | Claude Code 設定 |
| `PUT /api/v1/settings` | 更新 Claude Code 設定 |
| `GET /api/v1/scripts` | Claude Code 腳本 |
| `POST /api/v1/agent-sessions` | 建立 Agent Session |
| `GET /api/v1/agent-sessions/{id}` | 查詢 Session 狀態 |
| `WS /api/v1/ws/agent-sessions/{id}` | Agent Session WebSocket |
| `GET /api/v1/workspaces/{workspace_id}/openspec` | 取得 OpenSpec workspace 狀態與 actions |
| `WS /api/v1/ws` | 通用 WebSocket |
