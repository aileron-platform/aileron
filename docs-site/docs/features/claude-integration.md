---
sidebar_position: 2
title: Claude Code 整合
---

# Claude Code 整合

## 概覽

Aileron 深度整合 Claude Code，讓你可以直接在瀏覽器介面中執行 Claude Code Agent，進行程式碼生成、分析、重構等任務。

同時，Aileron 並不只面向 Claude Code。平台已朝多 Agent 架構演進，並正逐步補齊 OpenCode、Gemini、Codex 等不同 agent 的整合能力。不過就目前產品狀態而言，**Claude Code 仍是功能最完整、體驗最成熟的 agent 整合**。

## Agent 支援狀態

| Agent | 狀態 | 說明 |
|------|------|------|
| Claude Code | 完整支援 | 目前最完整，包含聊天、設定、Automation、OpenSpec workflow 整合 |
| Gemini | 部分支援 | 已有設定與基礎整合，端到端能力持續擴充中 |
| OpenCode | 部分支援 | 已有設定與基礎整合，後續會擴充更多 workflow 與執行能力 |
| Codex | 部分支援 | 已有設定與基礎整合，後續會補齊更多執行與治理能力 |

## 功能

### Agent Session

每次執行 Claude Code 都會建立一個 Agent Session：

```
前端 Chat Panel
  │  建立 Session
  ▼
Workspace Runtime
  │  執行 claude CLI
  │  串流輸出（stdout/stderr）
  ▼
WebSocket → 前端
  │  即時顯示 thinking / tool use / output
```

### 支援的 Permission Modes

| 模式 | 說明 |
|------|------|
| `default` | 標準模式，工具呼叫需確認 |
| `acceptEdits` | 自動接受檔案編輯 |
| `dontAsk` | 不詢問，自動執行所有操作 |
| `auto` | 完全自動化模式 |

### Claude Code 設定管理

透過 workspace 設定頁面可管理：

- **Model 選擇**：指定 Claude 模型
- **Hooks**：自訂 pre/post hook 指令
- **MCP 伺服器**：設定 MCP server 連線
- **子代理設定**：Claude Code sub-agent 設定
- **斜線命令**：自訂 `/` 命令
- **環境變數**：注入 `ANTHROPIC_API_KEY` 等執行環境變數

### 環境變數注入

Claude API Key 與其他敏感設定透過前端「環境變數」頁面動態設定，注入到 workspace runtime 容器中，不需要硬編碼在映像或 docker-compose 裡。

## Chat Panel

前端 Chat Panel 提供：

- **串流輸出**：即時顯示 Claude 的 thinking process 與工具呼叫
- **工具呼叫視覺化**：展示 file read/write、bash 執行等操作
- **Permission Mode 切換**：在對話中切換授權模式
- **Session 管理**：查看歷史 Session、繼續或建立新 Session

## WebSocket Agent Session

```javascript
// 連接 Agent Session WebSocket
const ws = new WebSocket(
  `ws://localhost:3002/api/v1/ws/agent-sessions/${sessionId}`
);

ws.onmessage = (event) => {
  const msg = JSON.parse(event.data);
  // msg.type: 'thinking' | 'tool_use' | 'tool_result' | 'text' | 'done' | 'error'
};
```

## 與 Automation 整合

Claude Code 可透過 Automation 功能排程執行，詳見 [自動化任務](./automation)。目前 Automation 體驗也以 Claude Code 最完整，其他 agent 的排程與工作流能力將在後續版本持續補齊。
