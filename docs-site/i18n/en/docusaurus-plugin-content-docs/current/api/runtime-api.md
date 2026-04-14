---
sidebar_position: 2
title: Runtime API
---

# Workspace Runtime API

The Workspace Runtime API exposes per-workspace agent execution, file operations, OpenSpec workflow state, and real-time streaming capabilities. Today, the Claude Code-related APIs are the most complete, but the overall surface is expanding toward a broader multi-agent runtime model.

## Interactive Documentation

- **Swagger UI**: http://localhost:3002/docs
- **ReDoc**: http://localhost:3002/redoc

:::note
Each workspace has its own Runtime instance; the port depends on the container configuration. `localhost:3002` is the default for local development.
:::

## Base URL

```
http://localhost:3002
```

## Main Endpoints

### Health Check

```
GET /health
```

### File Management

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v1/files` | List directory contents |
| `GET` | `/api/v1/files/{path}` | Read file contents |
| `PUT` | `/api/v1/files/{path}` | Write to a file |
| `DELETE` | `/api/v1/files/{path}` | Delete a file |
| `POST` | `/api/v1/files/upload` | Upload a file |

### Claude Code Settings

These settings APIs primarily serve Claude Code today. Equivalent settings coverage for other agents will be expanded over time.

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v1/settings` | Get Claude Code settings |
| `PUT` | `/api/v1/settings` | Update Claude Code settings |
| `GET` | `/api/v1/settings/hooks` | Get hook settings |
| `PUT` | `/api/v1/settings/hooks` | Update hook settings |
| `GET` | `/api/v1/settings/mcp` | Get MCP settings |
| `PUT` | `/api/v1/settings/mcp` | Update MCP settings |

### Agent Session

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/agent-sessions` | Create an agent session |
| `GET` | `/api/v1/agent-sessions` | List sessions |
| `GET` | `/api/v1/agent-sessions/{id}` | Get session details |
| `DELETE` | `/api/v1/agent-sessions/{id}` | Terminate a session |

### OpenSpec

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v1/workspaces/{workspace_id}/openspec` | Get OpenSpec workspace state and available workflow actions |

### Version Control (Git)

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v1/workspaces/{id}/version-control/status` | Git status |
| `GET` | `/api/v1/workspaces/{id}/version-control/log` | Git log |
| `POST` | `/api/v1/workspaces/{id}/version-control/commit` | Commit |
| `POST` | `/api/v1/workspaces/{id}/version-control/push` | Push |
| `POST` | `/api/v1/workspaces/{id}/version-control/pull` | Pull |
| `GET` | `/api/v1/workspaces/{id}/version-control/branches` | List branches |
| `POST` | `/api/v1/workspaces/{id}/version-control/checkout` | Switch branches |

### WebSocket

| Endpoint | Description |
|----------|-------------|
| `WS /api/v1/ws` | General WebSocket (file changes, system stats) |
| `WS /api/v1/ws/agent-sessions/{id}` | Agent session streaming output |

#### Agent Session WebSocket Message Format

```typescript
// Incoming message
interface AgentMessage {
  type: 'thinking' | 'tool_use' | 'tool_result' | 'text' | 'done' | 'error';
  content?: string;
  tool?: string;
  input?: Record<string, unknown>;
  output?: string;
  error?: string;
}
```

#### General WebSocket Events

```typescript
// File change event
interface FileChangedEvent {
  type: 'file_changed';
  path: string;
  event_type: 'created' | 'modified' | 'deleted';
}

// System stats event
interface SystemStatsEvent {
  type: 'system_stats';
  stats: {
    cpu_percent: number;
    memory_percent: number;
    disk_percent: number;
  };
}
```

## Script Management

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v1/scripts` | List available scripts |
| `POST` | `/api/v1/scripts/{name}/run` | Run a script |
