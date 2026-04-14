# Aileron Workspace Runtime

Workspace Runtime runs inside each workspace and provides agent execution, filesystem integration, system monitoring, and WebSocket communication.

## Capabilities

### Claude Code Integration

- settings management
- hooks management
- MCP configuration
- subagent configuration
- slash command support

### Filesystem and Git

- file watching
- sync notifications
- Git integration
- ignore rule handling

### System Monitoring

- CPU, memory, and disk usage
- process lifecycle management
- performance metrics
- resource warnings

### WebSocket Communication

- real-time frontend communication
- agent session event streaming
- heartbeat handling
- queued message delivery

### Developer Tooling

- dependency installation
- language runtime support
- dev server startup
- debugging support

## Stack

- FastAPI
- WebSockets
- Watchdog
- psutil
- Anthropic client integrations
- GitPython

## Layout

```text
workspace-runtime/
├── app/
├── scripts/
├── tests/
├── pyproject.toml
├── Dockerfile
└── README.md
```

## Quick Start

### Inside a Workspace Container

```dockerfile
FROM aileron/workspace-runtime:latest

ENV WORKSPACE_ID=my-workspace
ENV MANAGER_URL=http://workspace-manager:8000

CMD ["/app/scripts/start.sh"]
```

### Local Development

```bash
# recommended
uv pip install -e ".[dev]"

# alternative
pip install -e ".[dev]"

cp .env.example .env
python -m app.main
```

Or:

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 3002
```

## Main Endpoints

- `GET /health`
- `/api/v1/files/*`
- `/api/v1/settings`
- `/api/v1/scripts`
- `/api/v1/agent-sessions/*`
- `/api/v1/workspaces/{workspace_id}/version-control/*`
- `WS /api/v1/ws/agent-sessions/{session_id}`
- `WS /api/v1/ws`

## WebSocket Example

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
  }
};
```

## Key Environment Variables

| Variable | Default | Description |
|---|---|---|
| `WORKSPACE_ID` | `default` | workspace identifier |
| `WORKSPACE_PATH` | `/workspace` | workspace path |
| `MANAGER_URL` | - | Workspace Manager URL |
| `MONITOR_INTERVAL` | `5` | monitoring interval in seconds |

Claude API keys and similar user-specific variables should be configured dynamically through the UI rather than hard-coded here.

## Tests

```bash
pytest
pytest tests/test_file_watcher.py -v
pytest tests/test_websocket.py -v
pytest tests/test_system_monitor.py -v
```

## Security

- container sandboxing
- least-privilege execution
- restricted network access
- scoped filesystem access
