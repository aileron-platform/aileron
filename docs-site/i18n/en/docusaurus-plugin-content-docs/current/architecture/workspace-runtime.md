---
sidebar_position: 3
title: Workspace Runtime
---

# Workspace Runtime

## Overview

Workspace Runtime is the service that runs inside each development workspace container, providing agent execution integration, built-in OpenSpec CLI capability, file monitoring, system monitoring, and WebSocket communication. Claude Code is currently the most complete integration.

## Core Features

### Agent Execution Integration
- **Settings management**: read and update agent settings, with Claude Code currently the most complete
- **Hooks management**: configure and manage custom hooks
- **MCP integration**: manage MCP server configuration
- **Sub-agent management**: Claude Code sub-agent settings
- **Slash commands**: manage custom slash commands
- **OpenSpec CLI**: provide built-in OpenSpec workflow foundations inside the workspace

### File System Management
- **Real-time monitoring**: file change monitoring using Watchdog
- **Sync notifications**: push change events via WebSocket
- **Version control**: Git integration and operations
- **Smart ignore**: automatically ignores `node_modules`, `.git`, `__pycache__`, etc.

### System Monitoring
- **Resource monitoring**: CPU, memory, disk usage (psutil)
- **Process management**: development process lifecycle
- **Performance metrics**: system performance metrics collection

### WebSocket Communication
- **Real-time bidirectional communication**: with the frontend
- **Event broadcasting**: Agent session event pushes
- **Heartbeat**: connection state maintenance

## Technical Architecture

| Component | Technology |
|-----------|------------|
| Web framework | FastAPI |
| Real-time comms | WebSockets |
| File monitoring | Watchdog |
| System monitoring | psutil |
| AI client | Anthropic SDK / broader multi-agent CLI integrations |
| Version control | GitPython |

## Directory Structure

```
workspace-runtime/
├── app/
│   ├── config/            # Configuration modules
│   ├── core/              # Core functionality
│   ├── database/          # Database connection
│   ├── middleware/        # Middleware
│   ├── models/            # Data models
│   ├── modules/           # Feature modules (main routes)
│   ├── routers/           # Shared routes
│   ├── services/          # Business logic
│   ├── translations/      # i18n resources
│   └── utils/             # Utility functions
├── scripts/               # Startup scripts
├── tests/
├── pyproject.toml
└── Dockerfile
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `WORKSPACE_ID` | `default` | Workspace identifier |
| `WORKSPACE_PATH` | `/workspace` | Workspace path |
| `MANAGER_URL` | — | Workspace Manager URL |
| `MONITOR_INTERVAL` | `5` | System monitor interval (seconds) |

:::note Agent Credentials
Today, the most common case is injecting the Claude API key dynamically through the frontend's "Environment Variables" settings page. As more agent integrations are filled out, credentials for other runtimes should follow the same pattern rather than being hardcoded in container environment variables.
:::

## WebSocket Events

Connect via WebSocket:

```javascript
const ws = new WebSocket('ws://localhost:3002/api/v1/ws');

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  switch (data.type) {
    case 'file_changed':
      console.log('File changed:', data.path);
      break;
    case 'system_stats':
      console.log('System stats:', data.stats);
      break;
    case 'agent_output':
      console.log('Agent output:', data.content);
      break;
  }
};
```

## Local Development

```bash
docker compose up -d workspace-runtime
```

`workspace-runtime` should also be developed primarily through Docker Compose together with the rest of the platform services. Compose mounts `./workspace-runtime` into `/workspace-runtime` inside the container, so code changes are usually reflected through the existing reload behavior.

If you need to validate full agent workflows, WebSocket behavior, file watching, or other cross-service flows, start the full stack:

```bash
docker compose up -d
```

## Testing

```bash
# Run all tests
pytest

# Run specific tests
pytest tests/test_file_watcher.py -v
pytest tests/test_websocket.py -v
pytest tests/test_system_monitor.py -v
```

## Monitoring Metrics

### System Metrics
- CPU usage (real-time percentage)
- Memory used and available
- Disk space usage
- Network I/O statistics

### Application Metrics
- File change counts
- Active WebSocket connections
- Error rate

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /health` | Health check |
| `GET /api/v1/files/*` | File management |
| `GET /api/v1/settings` | Claude Code settings |
| `PUT /api/v1/settings` | Update Claude Code settings |
| `GET /api/v1/scripts` | Claude Code scripts |
| `POST /api/v1/agent-sessions` | Create agent session |
| `GET /api/v1/agent-sessions/{id}` | Get session status |
| `WS /api/v1/ws/agent-sessions/{id}` | Agent session WebSocket |
| `GET /api/v1/workspaces/{workspace_id}/openspec` | Get OpenSpec workspace state and actions |
| `WS /api/v1/ws` | General WebSocket |
