---
sidebar_position: 2
title: Runtime API
---

# Workspace Runtime API

Workspace Runtime API 提供每個 workspace 內的 Agent 執行、檔案操作、OpenSpec 工作流狀態與即時串流能力。目前以 Claude Code 相關 API 最完整，但整體介面已朝多 Agent runtime 擴展。

## 互動式文件

- **Swagger UI**：http://localhost:3002/docs
- **ReDoc**：http://localhost:3002/redoc

:::note
每個 workspace 有獨立的 Runtime 實例，端口依容器設定而定。`localhost:3002` 為本地開發預設。
:::

## Base URL

```
http://localhost:3002
```

## 主要端點

### 健康檢查

```
GET /health
```

### 檔案管理

| Method | 路徑 | 說明 |
|--------|------|------|
| `GET` | `/api/v1/files` | 列出目錄內容 |
| `GET` | `/api/v1/files/{path}` | 讀取檔案內容 |
| `PUT` | `/api/v1/files/{path}` | 寫入檔案 |
| `DELETE` | `/api/v1/files/{path}` | 刪除檔案 |
| `POST` | `/api/v1/files/upload` | 上傳檔案 |

### Claude Code 設定

目前這組設定 API 主要服務 Claude Code，其他 agent 的設定模型則會逐步補齊到相同層級。

| Method | 路徑 | 說明 |
|--------|------|------|
| `GET` | `/api/v1/settings` | 取得 Claude Code 設定 |
| `PUT` | `/api/v1/settings` | 更新 Claude Code 設定 |
| `GET` | `/api/v1/settings/hooks` | 取得 hooks 設定 |
| `PUT` | `/api/v1/settings/hooks` | 更新 hooks 設定 |
| `GET` | `/api/v1/settings/mcp` | 取得 MCP 設定 |
| `PUT` | `/api/v1/settings/mcp` | 更新 MCP 設定 |

### Agent Session

| Method | 路徑 | 說明 |
|--------|------|------|
| `POST` | `/api/v1/agent-sessions` | 建立 Agent Session |
| `GET` | `/api/v1/agent-sessions` | 列出 Sessions |
| `GET` | `/api/v1/agent-sessions/{id}` | 取得 Session 詳情 |
| `DELETE` | `/api/v1/agent-sessions/{id}` | 終止 Session |

### OpenSpec

| Method | 路徑 | 說明 |
|--------|------|------|
| `GET` | `/api/v1/workspaces/{workspace_id}/openspec` | 取得 OpenSpec workspace 狀態與可用 workflow actions |

### 版本控制（Git）

| Method | 路徑 | 說明 |
|--------|------|------|
| `GET` | `/api/v1/workspaces/{id}/version-control/status` | Git status |
| `GET` | `/api/v1/workspaces/{id}/version-control/log` | Git log |
| `POST` | `/api/v1/workspaces/{id}/version-control/commit` | Commit |
| `POST` | `/api/v1/workspaces/{id}/version-control/push` | Push |
| `POST` | `/api/v1/workspaces/{id}/version-control/pull` | Pull |
| `GET` | `/api/v1/workspaces/{id}/version-control/branches` | 列出分支 |
| `POST` | `/api/v1/workspaces/{id}/version-control/checkout` | 切換分支 |

### WebSocket

| 端點 | 說明 |
|------|------|
| `WS /api/v1/ws` | 通用 WebSocket（檔案變更、系統狀態） |
| `WS /api/v1/ws/agent-sessions/{id}` | Agent Session 串流輸出 |

#### Agent Session WebSocket 訊息格式

```typescript
// 接收到的訊息
interface AgentMessage {
  type: 'thinking' | 'tool_use' | 'tool_result' | 'text' | 'done' | 'error';
  content?: string;
  tool?: string;
  input?: Record<string, unknown>;
  output?: string;
  error?: string;
}
```

#### 通用 WebSocket 事件

```typescript
// 檔案變更事件
interface FileChangedEvent {
  type: 'file_changed';
  path: string;
  event_type: 'created' | 'modified' | 'deleted';
}

// 系統狀態事件
interface SystemStatsEvent {
  type: 'system_stats';
  stats: {
    cpu_percent: number;
    memory_percent: number;
    disk_percent: number;
  };
}
```

## 腳本管理

| Method | 路徑 | 說明 |
|--------|------|------|
| `GET` | `/api/v1/scripts` | 列出可用腳本 |
| `POST` | `/api/v1/scripts/{name}/run` | 執行腳本 |
