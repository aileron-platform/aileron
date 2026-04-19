---
sidebar_position: 1
title: Installation & Startup
---

# Installation & Startup

The default Docker Compose setup is intended to get teams from zero to a usable enterprise-style agent workspace quickly, without requiring every user to assemble toolchains and services manually.

## Requirements

- [Docker](https://docs.docker.com/get-docker/)
- [Docker Compose](https://docs.docker.com/compose/install/) (typically bundled with Docker Desktop)

## Standard Host CLI

`python scripts/dev/docker/ops.py` is the formal host-side CLI for local Docker operations. Use it as the primary cross-platform entrypoint for startup, shutdown, cleanup, and test execution.

Inspect the available subcommands before your first run:

```bash
python scripts/dev/docker/ops.py --help
python scripts/dev/docker/ops.py test --help
```

## First Launch

### Windows PowerShell

```powershell
git clone <your-repo-url>
cd aileron
python .\scripts\dev\docker\ops.py up --build
```

### macOS / Linux

```bash
git clone <your-repo-url>
cd aileron
python scripts/dev/docker/ops.py up --build
```

:::info Build Time
The first startup needs to build all images and takes about 5–10 minutes.
:::

## Verify Service Status

```bash
docker compose ps
```

Wait until the following services are `healthy` before opening the frontend:

- `postgres`
- `redis`
- `keycloak` (initialization is slow, about 60 seconds)
- `workspace-manager`
- `frontend`

:::warning Keycloak Not Ready
If you attempt to log in before Keycloak finishes initialization, the frontend will show an OIDC authentication error. Wait until `keycloak` is `healthy`.
:::

## Stop The Stack

### Windows PowerShell

```powershell
python .\scripts\dev\docker\ops.py down
```

### macOS / Linux

```bash
python scripts/dev/docker/ops.py down
```

This stops the stack while preserving volumes and persisted platform data.

## Common Commands

| Operation | Command |
|-----------|---------|
| Start all services | `python scripts/dev/docker/ops.py up` |
| Rebuild images and start | `python scripts/dev/docker/ops.py up --build` |
| Stop all services | `python scripts/dev/docker/ops.py down` |
| Cleanup workspace resources | `python scripts/dev/docker/ops.py cleanup-workspaces` |
| Full cleanup | `python scripts/dev/docker/ops.py cleanup` |
| Tail all logs | `docker compose logs -f` |
| Tail a specific service log | `docker compose logs -f workspace-manager` |

## Cleanup

Use `cleanup-workspaces` for routine workspace resets. Use `cleanup` only when you need a full local environment reset.

### Workspace Cleanup

Removes dynamic workspace containers and related transient resources while preserving the main platform stack and databases.

Windows PowerShell:

```powershell
python .\scripts\dev\docker\ops.py cleanup-workspaces
```

macOS / Linux:

```bash
python scripts/dev/docker/ops.py cleanup-workspaces
```

Legacy shell wrappers remain available if you prefer platform-specific entrypoints:

```powershell
.\scripts\dev\docker\cleanup-workspaces.ps1
```

```bash
./scripts/dev/docker/cleanup-workspaces.sh
```

### Full Cleanup

Stops the stack, removes platform volumes, and clears persisted local data.

Windows PowerShell:

```powershell
python .\scripts\dev\docker\ops.py cleanup
```

macOS / Linux:

```bash
python scripts/dev/docker/ops.py cleanup
```

:::danger Full Cleanup
`cleanup` deletes all Docker volumes, including PostgreSQL data. Make sure important data is backed up before running it.
:::

Legacy shell wrappers remain available for the full cleanup flow:

```powershell
.\scripts\dev\docker\cleanup.ps1
```

```bash
./scripts/dev/docker/cleanup.sh
```

## Restart After Cleanup

After either cleanup flow, restart the stack with the standard host-side CLI.

### Windows PowerShell

```powershell
python .\scripts\dev\docker\ops.py up --build
```

### macOS / Linux

```bash
python scripts/dev/docker/ops.py up --build
```

## Local Module Development

If you want to develop a single service locally:

```bash
# Frontend
cd frontend && npm install && npm run dev

# Workspace Manager
cd workspace-manager && uv sync && uv run uvicorn app.main:app --reload --port 3001

# Workspace Runtime
cd workspace-runtime && uv sync && uv run uvicorn app.main:app --reload --port 3002
```

:::tip First Experience
For first-time users, start with the host-side CLI. It provides the supported cross-platform path without forcing you to learn the lower-level Docker commands up front.
:::
