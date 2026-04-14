# Workspace Terminal Service

High-performance WebSocket terminal service for Aileron, implemented in Go.

## Features

- WebSocket real-time communication
- multi-tab terminal management
- PTY support
- Redis token authentication
- permission controls
- terminal resize handling
- concurrency-safe internals
- graceful shutdown

## Stack

- Go 1.21+
- Gin
- `creack/pty`
- `go-redis/v9`
- `zap`
- `gorilla/websocket`

## Quick Start

### Local Development

```bash
go mod download
docker run -d -p 6379:6379 redis:7-alpine
cp .env.example .env
go run ./cmd/server/main.go
```

### Docker Compose

```bash
docker compose up -d
docker compose logs -f terminal-service
docker compose down
```

### Makefile

```bash
make build
make run
make test
make docker-up
make docker-down
```

## Environment Variables

| Variable | Description | Default |
|---|---|---|
| `TERMINAL_PORT` | service port | `8745` |
| `LOG_LEVEL` | log level | `info` |
| `REDIS_HOST` | Redis host | `localhost` |
| `REDIS_PORT` | Redis port | `6379` |
| `REDIS_DB` | Redis database index | `0` |
| `MAX_TABS_PER_WORKSPACE` | max tabs per workspace | `10` |
| `SESSION_TIMEOUT` | session timeout in seconds | `300` |
| `PTY_BUFFER_SIZE` | PTY buffer size | `1024` |

## API

### WebSocket

```text
ws://localhost:8745/ws/terminal?token={token}&workspace_id={workspace_id}
```

### Health Check

```text
GET /health
```

## WebSocket Message Format

```json
{
  "type": "message_type",
  "tab_id": "tab_id",
  "data": {},
  "timestamp": 1699900000
}
```

Client-to-server message types:

- `create_tab`
- `close_tab`
- `switch_tab`
- `list_tabs`
- `input`
- `resize`
- `clear`

Server-to-client message types:

- `connected`
- `tab_created`
- `tab_closed`
- `tab_switched`
- `tab_list`
- `output`
- `resized`
- `error`
