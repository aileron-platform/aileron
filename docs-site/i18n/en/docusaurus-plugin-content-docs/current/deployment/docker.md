---
sidebar_position: 1
title: Docker Mode
---

# Docker Deployment

## When to Use

- Local development and debugging
- Quickly experience the full platform
- Environments without Kubernetes, Operator, or Cilium
- Single-machine deployments

## Requirements

- [Docker](https://docs.docker.com/get-docker/) (24.0+ recommended)
- [Docker Compose](https://docs.docker.com/compose/install/) (V2, typically bundled with Docker Desktop)
- At least 4 vCPU
- At least 8GB available memory
- 12GB to 16GB available memory is recommended for more stable browser and agent workflows
- At least 30GB available disk space
- Keeping 50GB of free disk space is recommended so images, volumes, and workspace data do not fill the host too quickly

## Service Architecture

In Docker mode, `docker compose` manages the following services:

```
┌────────────────────────────────────────────────────────┐
│                     User Browser                        │
└──────────┬────────────┬──────────────┬─────────────────┘
           │:8082       │:3001         │:8080
┌──────────▼───┐ ┌──────▼──────────┐ ┌─▼────────────┐
│   Frontend   │ │Workspace Manager│ │   Keycloak    │
│  (Vite Dev)  │ │   (FastAPI)     │ │  (OAuth2)     │
└──────────────┘ └──┬──────────┬───┘ └───────────────┘
                    │          │
           ┌────────▼──┐  ┌───▼──────────────┐
           │  Celery +  │  │  Workspace       │
           │  Flower    │  │  Runtime :3002    │
           │  :5555     │  │  Terminal :3004   │
           └────────────┘  │  SSH :2222        │
                           └──┬────────┬──────┘
                              │        │
                    ┌─────────▼──┐ ┌───▼──────────┐
                    │  Browser   │ │ Workspace     │
                    │  (neko)    │ │ Canvas :3003 │
                    │  :6080     │ └───────────────┘
                    └────────────┘
        ┌──────────────────────────────────────┐
        │           Infrastructure              │
        │  PostgreSQL :5432 │ Redis :6379       │
        └──────────────────────────────────────┘
```

### Service Overview

| Service | Image | Description |
|---------|-------|-------------|
| **postgres** | `postgres:15-alpine` | Main database for both platform and Keycloak data |
| **redis** | `redis:7-alpine` | Task queue (Celery broker), result backend, session management |
| **keycloak** | `keycloak:25.0.0` | OAuth2/OIDC authentication service with SSO support |
| **workspace-manager** | Local build | Core management service: workspace CRUD, templates, automation scheduling |
| **workspace-runtime** | Local build | Agent runtime: Claude Code is currently the most complete integration, alongside built-in OpenSpec CLI, file monitoring, Git, and system monitoring |
| **workspace-browser** | Local build | WebRTC browser (based on neko) with CDP remote debugging support |
| **workspace-canvas** | Local build | Canvas runtime service for live frontend previews |
| **frontend** | Local build | React + Vite dev server |
| **drawio** | `jgraph/drawio` | Embedded diagram editor |

## Start

```bash
docker compose up -d --build
```

:::info Build Time
The first startup builds all images, roughly 5–10 minutes. Subsequent starts without code changes can use `docker compose up -d` for a fast boot.
:::

In Aileron, this full Docker Compose stack is not only a deployment path but also the default local development mode. Day-to-day module development should keep the full stack running and rely on the development mounts plus each service's built-in reload behavior to pick up code changes.

## Workspace Runtime Base Image Selection

`workspace-runtime` supports two base image flavors:

- `RUNTIME_BASE=universal`: the existing full `codex-universal` base
- `RUNTIME_BASE=lite`: the slimmer `workspace-runtime/base-lite` base

Build the selected base image first, then build `workspace-runtime`:

```bash
# Lite base
make build-runtime-base-lite
make build-workspace-runtime RUNTIME_BASE=lite

# Full universal base
make build-codex-universal
make build-workspace-runtime RUNTIME_BASE=universal
```

If you want to change image tags during local builds:

```bash
make build-runtime-base-lite RUNTIME_BASE_LITE_TAG=mytag
make build-workspace-runtime RUNTIME_BASE=lite RUNTIME_BASE_LITE_TAG=mytag IMAGE_TAG=mytag
```

Docker Compose can also be pointed at a specific prebuilt base image through `WORKSPACE_RUNTIME_BASE_IMAGE`:

```bash
WORKSPACE_RUNTIME_BASE_IMAGE=ailerondocker/workspace-runtime-base-lite:custom docker compose up -d --build
```

## Verify Service Status

```bash
docker compose ps
```

Wait until `postgres`, `redis`, `keycloak`, `workspace-manager`, and `frontend` all reach `healthy` before logging in.

:::warning Keycloak Initialization
Keycloak has a 60-second `start_period`. If you log in before it completes, the frontend shows OIDC errors.
:::

## Service URLs

| Service | URL | Description |
|---------|-----|-------------|
| Frontend | `http://localhost:8082` | Main UI |
| Manager API | `http://localhost:3001` | Workspace Manager REST API |
| Manager Swagger | `http://localhost:3001/docs` | Manager interactive API docs |
| Manager ReDoc | `http://localhost:3001/redoc` | Manager ReDoc API docs |
| Runtime API | `http://localhost:3002` | Workspace Runtime REST API |
| Runtime Swagger | `http://localhost:3002/docs` | Runtime interactive API docs |
| Runtime ReDoc | `http://localhost:3002/redoc` | Runtime ReDoc API docs |
| Terminal | `http://localhost:3004` | Terminal WebSocket service |
| Keycloak Admin | `http://localhost:8080/admin` | Authentication management console |
| Draw.io | `http://localhost:8083` | Diagram editor |
| Flower | `http://localhost:5555` | Celery task monitoring |
| Browser WebSocket | `http://localhost:6080` | neko WebRTC signaling |
| Canvas Runtime | `http://localhost:3003` | Canvas renderer |

## Environment Variables

### Host Environment Variables

The following variables can be set via shell or `.env` file and affect overall docker compose behavior:

| Variable | Default | Description |
|----------|---------|-------------|
| `TZ` | `Asia/Taipei` | System timezone |
| `HOST_PROJECT_ROOT` | `.` | Absolute path to the project root on host |
| `HOST_WORKSPACES_DIR` | `./data/workspace-data` | Workspace data storage path |
| `HOST_SSH_KEYS_DIR` | `./data/ssh-keys` | SSH keys storage path |
| `ANTHROPIC_BASE_URL` | _(empty)_ | Claude API base URL (for custom proxy) |
| `ANTHROPIC_AUTH_TOKEN` | _(empty)_ | Claude API authentication token |

:::tip .env File
Create a `.env` file at the project root and docker compose will load it automatically:

```bash
# .env
TZ=Asia/Taipei
ANTHROPIC_AUTH_TOKEN=sk-ant-xxxxx
HOST_PROJECT_ROOT=/Users/yourname/aileron
```
:::

### Key Service Settings

See [Environment Variables Reference](./environment-variables) for the full list. The most commonly adjusted items are:

**Database (PostgreSQL)**
| Variable | Default | Description |
|----------|---------|-------------|
| `POSTGRES_DB` | `aileron` | Main database name |
| `POSTGRES_USER` | `postgres` | Database user |
| `POSTGRES_PASSWORD` | `postgres` | Database password |

**Redis**
| Variable | Default | Description |
|----------|---------|-------------|
| `--maxmemory` | `256mb` | Maximum memory usage |
| `--maxmemory-policy` | `allkeys-lru` | Memory eviction policy |

**Keycloak**
| Variable | Default | Description |
|----------|---------|-------------|
| `KC_BOOTSTRAP_ADMIN_USERNAME` | `admin` | Admin username |
| `KC_BOOTSTRAP_ADMIN_PASSWORD` | `admin` | Admin password |
| `KC_HOSTNAME_URL` | `http://localhost:8080` | Public URL |

## Volume Mounts

### Persistent Data

| Host Path | Container Path | Description |
|-----------|----------------|-------------|
| `./data/postgres` | `/var/lib/postgresql/data` | PostgreSQL data |
| `./data/redis` | `/data` | Redis persistent data |
| `./data/keycloak` | `/opt/keycloak/data` | Keycloak data |
| `./data/workspace-data` | `/workspace` | Workspace project files |
| `./data/claude-data` | `/home/developer/.claude` | Claude Code session data |
| `./data/template-center` | `/data/template-center` | Template storage |
| `./data/workspace-scripts` | `/scripts` | Workspace scripts |

### Development Mounts

These mounts are the core of the local development workflow. Module directories on the host are mapped directly into containers, so frontend, Manager, Runtime, and Terminal code changes usually become effective inside the running stack without rebuilding everything each time.

| Host Path | Container Path | Purpose |
|-----------|----------------|---------|
| `./workspace-manager` | `/workspace-manager` | Manager code hot reload |
| `./workspace-runtime` | `/workspace-runtime` | Runtime code hot reload |
| `./workspace-terminal` | `/workspace-terminal` | Terminal code hot reload |
| `./frontend` | `/app` | Frontend code hot reload |
| `/var/run/docker.sock` | `/var/run/docker.sock` | Docker socket (for container management) |

:::caution Docker Socket Mount
Both `workspace-manager` and `workspace-runtime` mount the Docker socket so they can dynamically create and manage workspace containers. This design is only appropriate for development environments; use Kubernetes mode for production.
:::

## Network Configuration

All services use a shared bridge network `aileron-network-dev`.

Services communicate via container names (resolved by Docker Compose's built-in DNS), e.g.:
- `postgres:5432`
- `redis:6379`
- `workspace-manager:3001`
- `workspace-runtime:3002`

Keycloak has two network aliases (`localhost` and `keycloak`) so that OIDC token verification inside containers resolves correctly.

## Resource Requirements

| Service | CPU | Memory | Notes |
|---------|-----|--------|-------|
| workspace-browser | Max 2 cores | Max 2GB / Reserved 1GB | neko WebRTC is the most resource-intensive |
| workspace-browser | — | 2GB SHM | Shared memory (required by Chrome) |
| Others | Unlimited | Unlimited | Allocated dynamically |

:::tip Recommended Sizing
For single-machine evaluation and basic workflow validation, plan for at least `4 vCPU / 8 GB RAM / 30 GB` of free disk. For steadier browser usage, automation flows, Keycloak, and multiple services running together, `6-8 vCPU / 12-16 GB RAM / 50 GB` of free disk is a more realistic target. If the same host will also run Harbor, a registry, or other large containers, start at `16 GB RAM` or higher to avoid heavy swap usage and disk pressure.
:::

## Common Commands

```bash
# Start (reuse local images; Compose pulls only if missing)
python scripts/dev/docker/ops.py up

# Pull the latest dev images first, then start
python scripts/dev/docker/ops.py up --pull

# Build images locally, then start (mutually exclusive with --pull)
python scripts/dev/docker/ops.py up --build

# Pin the image arch when running cross-arch (e.g. amd64 emulation on arm64 host)
python scripts/dev/docker/ops.py up --pull --image-arch amd64

# Stop (preserves volumes)
python scripts/dev/docker/ops.py down

# Full reset via the host-side CLI
python scripts/dev/docker/ops.py cleanup

# Stop and remove volumes
docker compose down -v

# Tail all logs
docker compose logs -f

# Tail specific service logs
docker compose logs -f workspace-manager
docker compose logs -f workspace-runtime
docker compose logs -f keycloak

# Restart a single service
docker compose restart workspace-runtime

# Rebuild a single service
docker compose up -d --build workspace-runtime

# Build workspace-runtime against the lite base
make build-workspace-runtime RUNTIME_BASE=lite

# Build workspace-runtime against the universal base
make build-workspace-runtime RUNTIME_BASE=universal
```

For routine host-side operations, prefer `python scripts/dev/docker/ops.py ...`. Keep raw `docker compose` commands for logs, single-service rebuilds, or lower-level debugging.

`ops.py up` overrides the Compose image tags automatically based on the host arch. By default it skips `docker compose pull` and reuses local images; pass `--pull` to refresh from Docker Hub or `--build` to build locally (the two are mutually exclusive). When stdin is a TTY it prompts for the image arch; pass `--no-prompt` plus `--image-arch` / `--runtime-base` for non-interactive use.

## Cleanup

### Remove Workspace Containers Only (Preserve Databases)

```bash
python scripts/dev/docker/ops.py cleanup-workspaces
```

Only removes dynamically created workspace containers, associated volumes, and network. Platform services and databases are untouched.

### Full Cleanup

```bash
python scripts/dev/docker/ops.py cleanup
```

This script will:
1. Delete all dynamic workspace containers
2. Stop all docker-compose services
3. Delete Docker volumes and networks
4. Clear persistent data under `data/` (postgres, redis, keycloak, workspace-data, etc.)
5. Clean temporary directories
6. Optionally run `docker system prune`

:::danger
Full cleanup deletes all database data, including users, workspace settings, templates, etc. Back up before running.
:::

### Start and Stop via the Cross-Platform CLI

```bash
python scripts/dev/docker/ops.py up --build
python scripts/dev/docker/ops.py down
```

Restart after cleanup:

```bash
python scripts/dev/docker/ops.py up --build
```

## Health Checks

All services have health checks configured:

| Service | Check | Interval | Initial Delay |
|---------|-------|----------|---------------|
| postgres | `pg_isready` | 10s | — |
| redis | `redis-cli ping` | 10s | — |
| keycloak | TCP port 8080 | 30s | 60s |
| workspace-manager | HTTP `/health` | 30s | — |
| workspace-runtime | HTTP `/health` | 30s | — |
| workspace-browser | HTTP `/health` | 30s | — |
| workspace-canvas | HTTP `/health` | 15s | — |
| frontend | HTTP `/` | 30s | — |

## Docker vs Kubernetes Responsibilities

| Aspect | Docker Mode | Kubernetes Mode |
|--------|-------------|-----------------|
| Service management | `docker compose` | Helm + Operator |
| Workspace lifecycle | Docker container | Pod + Service + Ingress |
| Network isolation | Docker bridge network | Cilium Network Policy |
| Storage | Host volume mount | PVC (Persistent Volume Claim) |
| Authentication | Optional (Keycloak) | Required (Keycloak + Ingress TLS) |
| Target scenario | Dev, test, demo | Production, multi-user |

For Kubernetes deployment, see [Kubernetes Mode](./kubernetes).
