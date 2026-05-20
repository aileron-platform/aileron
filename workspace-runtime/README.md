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

### Codex Runtime Defaults

Workspace Runtime reads Codex CLI state from the mounted
`/home/developer/.codex` directory. Workspace provisioning creates the
platform-managed default `config.toml` in that mounted agent state before the
runtime container starts, while sandbox and approval policy continue to come
from Workspace Runtime execution settings.

### Draw.io Integration

Draw.io is optional. `DRAWIO_ENABLED` defaults to `true` to preserve existing
deployments; set it to `false` when a workspace does not run the Draw.io
container. `DRAWIO_EXTERNAL_URL` is the browser-facing URL, while
`DRAWIO_INTERNAL_URL` is used by runtime health checks. Tune
`DRAWIO_HEALTHCHECK_TIMEOUT_SECONDS` and `DRAWIO_HEALTHCHECK_TTL_SECONDS` to
control the health check timeout and cache duration.

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

### Image Build

`workspace-runtime` can now be built against two different base images:

- `RUNTIME_BASE=universal`: published `ailerondocker/codex-universal:<channel>-<arch>` image from Docker Hub
- `RUNTIME_BASE=lite`: slimmer `workspace-runtime/base-lite`

The runtime image pins `@google/gemini-cli` to `0.40.0` so Gemini extension
subprocess tests exercise a stable extension enable/disable CLI contract.

Build commands:

```bash
# Build the slim base, then build workspace-runtime on top of it
make build-runtime-base-lite
make build-workspace-runtime RUNTIME_BASE=lite

# Pull the full universal base from Docker Hub, then build workspace-runtime on top of it
make build-codex-universal
make build-workspace-runtime RUNTIME_BASE=universal
```

If you need custom tags:

```bash
make build-runtime-base-lite RUNTIME_BASE_LITE_TAG=mytag
make build-workspace-runtime RUNTIME_BASE=lite RUNTIME_BASE_LITE_TAG=mytag IMAGE_TAG=mytag
```

### Inside a Workspace Container

```dockerfile
FROM ailerondocker/workspace-runtime:latest-codex-amd64

ENV WORKSPACE_ID=my-workspace
ENV MANAGER_URL=http://workspace-manager:8000

CMD ["/app/scripts/start.sh"]
```

Workspace runtime startup does not install project dependencies from `/workspace`.
If a project needs dependencies, run the package manager explicitly after the
workspace is available. Web Canvas dependencies are handled by the separate
Canvas runtime from its `/web-canvas` snapshot.

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

Container-based test workflow remains available through:

```bash
make test-all
```

## Security

- container sandboxing
- least-privilege execution
- restricted network access
- scoped filesystem access
