---
sidebar_position: 1
title: Installation & Startup
---

# Installation & Startup

The default Docker Compose setup is intended to get teams from zero to a usable enterprise-style agent workspace quickly, without requiring every user to assemble toolchains and services manually.

## Requirements

- [Docker](https://docs.docker.com/get-docker/)
- [Docker Compose](https://docs.docker.com/compose/install/) (typically bundled with Docker Desktop)

## First Launch

```bash
git clone <your-repo-url>
cd aileron
docker compose up -d --build
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

## Common Commands

| Operation | Command |
|-----------|---------|
| Start all services | `docker compose up -d` |
| Rebuild images and start | `docker compose up -d --build` |
| Stop all services | `docker compose down` |
| Tail all logs | `docker compose logs -f` |
| Tail a specific service log | `docker compose logs -f workspace-manager` |

## Cleanup

Remove workspace containers only (preserve databases):

```bash
./scripts/dev/docker/cleanup-workspaces.sh
```

Full cleanup (databases, volumes, containers):

```bash
./scripts/dev/docker/cleanup.sh
```

:::danger Full Cleanup
`cleanup.sh` deletes all Docker volumes, including PostgreSQL data. Make sure important data is backed up before running it.
:::

Restart after cleanup:

```bash
docker compose up -d --build
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
For first-time users, use Docker Compose directly. It is the fastest way to experience the full platform without rebuilding the environment service by service.
:::
