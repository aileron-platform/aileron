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

`python scripts/dev/docker/ops.py` is the formal host-side CLI for local Docker operations. The intended split is: use `ops.py` for full-stack lifecycle actions such as startup, shutdown, cleanup, and test execution; use raw `docker compose` for day-to-day development tasks such as inspecting logs, rebuilding a single service, or lower-level debugging.

Inspect the available subcommands before your first run:

```bash
python scripts/dev/docker/ops.py --help
python scripts/dev/docker/ops.py test --help
```

`python scripts/dev/docker/ops.py up` switches the Compose image tags automatically based on the host arch. By default it reuses local images and skips `docker compose pull`. Three modes:

- (default) Reuse local images (Compose still pulls if a tag is missing)
- `--pull` to refresh from Docker Hub `dev` tags before starting
- `--build` to build from the current repo locally before starting (mutually exclusive with `--pull`)

For non-interactive use, add `--no-prompt` and pin the arch:

```bash
python scripts/dev/docker/ops.py up --pull --no-prompt --image-arch amd64
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
| Start all services (reuse local images) | `python scripts/dev/docker/ops.py up` |
| Pull latest dev images, then start | `python scripts/dev/docker/ops.py up --pull` |
| Rebuild images locally and start | `python scripts/dev/docker/ops.py up --build` |
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

If you still need the older platform-specific wrappers, refer to the existing scripts under `scripts/dev/docker/`; the primary documented path is `python scripts/dev/docker/ops.py`.

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

If you still need the older platform-specific wrappers, refer to the existing scripts under `scripts/dev/docker/`; the primary documented path is `python scripts/dev/docker/ops.py`.

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

Docker Compose is the default local development mode for Aileron. For module development, start the full stack first instead of pulling core services out to run directly on the host:

```bash
docker compose up -d
```

In this mode, the development module directories are mounted directly into their corresponding containers, so changes usually take effect immediately without rebuilding the full environment every time:

- `./frontend` → `/app`
- `./workspace-manager` → `/workspace-manager`
- `./workspace-runtime` → `/workspace-runtime`
- `./workspace-terminal` → `/workspace-terminal`

That means frontend, Manager, Runtime, and Terminal code changes flow through the existing development mounts and reload mechanisms inside the containers. You only need `docker compose up -d --build` when Dockerfiles, system dependencies, or image-layer contents change.

To inspect service state or confirm that changes have been picked up, use:

```bash
docker compose ps
docker compose logs -f workspace-manager
docker compose logs -f workspace-runtime
docker compose logs -f frontend
```

:::tip First Experience
For first-time users, use `ops.py` to bring the environment up and tear it down. Once the stack is running, switch to commands like `docker compose ps`, `docker compose logs -f`, and `docker compose up -d --build <service>` for service-level development work.
:::
