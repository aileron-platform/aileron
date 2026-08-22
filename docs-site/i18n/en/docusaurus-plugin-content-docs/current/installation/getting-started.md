---
title: Install and Start
---

# Install and Start

The default Docker Compose setup helps a team build a usable enterprise agent workspace platform from scratch without first assembling every toolchain and service manually.

## Requirements

- [Docker](https://docs.docker.com/get-docker/)
- [Docker Compose](https://docs.docker.com/compose/install/) (usually included with Docker Desktop)

## Standard Docker Workflow

Local builds and startup use standard Docker interfaces. You do not need to go through the project's Python CLI first:

```bash
docker buildx bake --load local
docker compose -f docker-compose.yml -f docker-compose.bundled-data-services.yml \
  up --remove-orphans --no-build -d
```

- The local workflow always merges `docker-compose.yml` with
  `docker-compose.bundled-data-services.yml`. `docker compose up` and `docker compose down` manage only the control-plane services in the root
  Compose project. Manager controls Runtime, Browser, and Canvas dynamically for each Workspace.
- `docker-bake.hcl` is the single source of truth for image build parameters and toolchain versions.
- Dockerfiles declare only required build arguments and provide no numeric version defaults.
- `docker-compose.yml` runs existing images and does not rebuild them during startup.
- `package-lock.json`, `uv.lock`, and `go.sum` manage application dependencies for their respective ecosystems.

You can also use the Make wrappers, which contain no version logic:

```bash
make build
make start
```

`python scripts/dev/docker/ops.py` is the implementation wrapper used by `make` targets. `make full-reset` is the documented host-side destructive reset entry point.

## First Startup

### Windows PowerShell

```powershell
git clone <your-repo-url>
cd aileron
docker buildx bake --load local
docker compose -f docker-compose.yml -f docker-compose.bundled-data-services.yml up --remove-orphans --no-build -d
```

### macOS / Linux

```bash
git clone <your-repo-url>
cd aileron
docker buildx bake --load local
docker compose -f docker-compose.yml -f docker-compose.bundled-data-services.yml \
  up --remove-orphans --no-build -d
```

:::info Build time
The first startup builds every image and takes approximately 5–10 minutes.
:::

## Check Control-Plane Service Status

```bash
docker compose -f docker-compose.yml -f docker-compose.bundled-data-services.yml ps
```

Wait until all of these services are `healthy` before opening the Frontend:

- `postgres`
- `redis`
- `oidc provider` (the external provider is operator-managed)
- `workspace-manager`
- `frontend`

:::warning The OIDC provider is not ready
If you try to sign in before OIDC Discovery/JWKS is available, the Frontend reports an OIDC
authentication failure. Verify that Manager can reach external-provider Discovery and JWKS.
:::

## Stop the Control Plane

### Windows PowerShell

```powershell
docker compose -f docker-compose.yml -f docker-compose.bundled-data-services.yml down --remove-orphans
```

### macOS / Linux

```bash
docker compose -f docker-compose.yml -f docker-compose.bundled-data-services.yml down --remove-orphans
```

This stops only the control-plane services managed by the root Compose project and preserves volumes
and persistent platform data. Dynamic Workspace execution planes remain under Manager control; use
the Manager UI or API first when an individual Workspace must be stopped.

## Common Commands

The commands most often used by new contributors are:

| Operation | Command |
|------|------|
| Build all local images | `docker buildx bake --load local` |
| Start control-plane services | `make start` |
| Stop non-destructively and preserve data | `make down` |
| Follow all control-plane logs | `docker compose -f docker-compose.yml -f docker-compose.bundled-data-services.yml logs -f` |

For the complete command set, including local builds, full reset, test reuse, and individual service logs, see [Docker Deployment → Common Commands](./docker.md#common-commands).

## Reset the Environment

Starting, stopping, restarting a component, or deleting an individual Workspace must go through the Manager UI or API so component revisions, Runtime credentials, and database state remain synchronized. `make down` only stops the local stack and preserves data; `make full-reset` is the only destructive local-environment reset available from the host.

### Full Reset

Stop the stack, remove platform volumes, and clear locally persisted data.

macOS / Linux:

```bash
make full-reset
```

:::danger Full reset
`full-reset` removes Aileron dynamic Workspaces, volumes and networks whose names match `aileron`, and persistent data under `data/`, including PostgreSQL. It separately asks whether to delete project images and whether to run a global `docker system prune --volumes` that can affect unused resources from other projects. Back up important data and read every prompt before continuing. The reset completes only after dynamic Workspaces and local data such as PostgreSQL are confirmed absent.
:::

## Restart After the Full Reset

After a full reset, rebuild and start with the same standard Docker commands.

### Windows PowerShell

```powershell
docker buildx bake --load local
docker compose -f docker-compose.yml -f docker-compose.bundled-data-services.yml up --remove-orphans --no-build -d
```

### macOS / Linux

```bash
docker buildx bake --load local
docker compose -f docker-compose.yml -f docker-compose.bundled-data-services.yml \
  up --remove-orphans --no-build -d
```

## Local Module Development

Docker Compose is Aileron's default local development environment. Start the control plane first; Manager then creates Runtime, Browser, and Canvas dynamically for each Workspace:

```bash
docker buildx bake --load local
docker compose -f docker-compose.yml -f docker-compose.bundled-data-services.yml \
  up --remove-orphans --no-build -d
```

Platform modules and dynamic Runtimes mount their corresponding development directories, so built-in reload mechanisms usually reflect changes:

- `./frontend` → `/app`
- `./workspace-manager` → `/workspace-manager`
- `./workspace-runtime` → `/workspace-runtime`
- `./workspace-terminal` → `/workspace-terminal`

Run `docker buildx bake --load local` again only after changing a Dockerfile, `docker-bake.hcl`, system dependencies, or a dependency lockfile. Normal source edits reuse existing images. Dynamic Workspace containers are not Compose services; do not bypass Manager with `docker compose restart workspace-runtime`.

To inspect individual service status or follow whether changes take effect:

```bash
docker compose -f docker-compose.yml -f docker-compose.bundled-data-services.yml ps
docker compose -f docker-compose.yml -f docker-compose.bundled-data-services.yml logs -f workspace-manager
docker compose -f docker-compose.yml -f docker-compose.bundled-data-services.yml logs -f frontend
docker logs -f workspace-runtime-<workspace-id>
```

:::tip First experience
On first use, build once with Bake and then start with Compose. Compose manages only control-plane services; Manager remains responsible for the Workspace lifecycle.
:::

## Next Steps

- After startup, see [Service Endpoints and Accounts](./service-endpoints.md) for service URLs, default accounts, and health-check endpoints.
- For Docker deployment architecture, environment variables, and volume-mount details, see [Docker Deployment](./docker.md).
- For production or multi-user deployment, use the alternative [Kubernetes Deployment](./kubernetes.md) path.
