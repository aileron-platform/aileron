# ✈️ Aileron
[![OpenSSF Scorecard](https://api.securityscorecards.dev/projects/github.com/aileron-platform/aileron/badge)](https://securityscorecards.dev/viewer/?uri=github.com/aileron-platform/aileron)
[![License](https://img.shields.io/github/license/aileron-platform/aileron)](https://github.com/aileron-platform/aileron/blob/develop/LICENSE)

[Traditional Chinese](./README.zh-TW.md)

> **Standardized AI Agent Workspaces for Enterprise Teams**

Aileron is an AI agent workspace platform for enterprises, designed to help organizations adopt agents in ways that align with internal governance, access policies, and infrastructure requirements, while significantly reducing the effort required for users to set up environments, connect tools, and start working.

Documentation: https://aileron-platform.github.io/aileron/

---

## Vision

Aileron aims to become the standard workspace orchestration layer for enterprise AI agents, enabling organizations to scale agent-driven development within existing governance and operational boundaries.

---

## Demo

| Web Terminal | Agent Login |
|---|---|
| [![Web Terminal Demo](https://img.youtube.com/vi/7ddBnS7sr0M/hqdefault.jpg)](https://youtu.be/7ddBnS7sr0M) | [![Agent Login Demo](https://img.youtube.com/vi/FAUb1JKzJO8/hqdefault.jpg)](https://youtu.be/FAUb1JKzJO8) |
| Create Workspace | Marketplace & AI Chat |
| [![Create Workspace Demo](https://img.youtube.com/vi/G8AXGd0_Xwo/hqdefault.jpg)](https://youtu.be/G8AXGd0_Xwo) | [![Marketplace & AI Chat Demo](https://img.youtube.com/vi/pl0H4j07IsU/hqdefault.jpg)](https://youtu.be/pl0H4j07IsU) |

---

## Why Aileron?

When enterprises adopt AI agents, the hard part is rarely just model capability. The real challenge is making agent usage align with internal governance while avoiding the need for every user to assemble a complex development environment by hand.

Aileron is built to solve both sides of that problem:

- make agents easier for enterprises to adopt
- make workspaces easier for users to start using

---

## Core Capabilities

- **Governance-Aligned Workspaces**  
  Centralized Marketplace packages, permissions, and standardized capabilities help align agent usage with enterprise governance.

- **Simplified Workspace Setup**  
  Users can start from ready-to-use agent workspaces instead of assembling local environments from scratch.

- **Standardized Tooling and Workflows**  
  MCP, slash commands, workflows, and integrations are standardized at the platform level to reduce team-to-team drift.

- **Unified Workspace Surfaces**  
  Chat, file management, Git, and web terminal capabilities are integrated into the same workspace experience.

- **Enterprise Authentication and Governance**  
  Standard OIDC authentication provides SSO and centralized platform control through an installation-owned external provider.

---

## Agent Support Status

Aileron fully supports **Claude Code**, **OpenCode**, and **Codex** as first-class agent engines.

- `Claude Code`: fully supported
- `OpenCode`: fully supported
- `Codex`: fully supported

---

## Tech Stack

Aileron is built on a modern microservices architecture:

- **Frontend**: React-based management UI, workspace shell, and web terminal experience
- **Workspace Manager**: FastAPI service for orchestration and lifecycle management
- **Workspace Runtime**: secure containerized execution runtime for agents
- **Workspace Terminal**: Go-based terminal / WebSocket service
- **Workspace Operator**: Kubernetes-native dynamic workspace provisioning
- **Agent Tools**: first-class Claude Code, OpenCode, and Codex integrations with related workspace tooling
- **Infrastructure**:
  - **PostgreSQL**: relational persistence
  - **Redis**: caching and task coordination
  - **OIDC provider**: external identity and access management contract
  - **Flower**: task monitoring

---

## Quick Start

### Prerequisites

- Docker
- Docker Compose v2
- Recommended: **8GB RAM**

### Standard Host CLI

`python scripts/dev/docker/ops.py` is the formal host-side CLI for local Docker operations. It is the standard cross-platform entrypoint for:

- stack startup and shutdown
- workspace cleanup and full cleanup
- runtime / manager container test execution

Inspect the available subcommands and examples before your first run:

```bash
python scripts/dev/docker/ops.py --help
python scripts/dev/docker/ops.py test --help
```

### Start The Stack

#### Windows PowerShell

```powershell
git clone <your-repo-url>
cd aileron
python .\scripts\dev\docker\ops.py up --build
```

#### macOS / Linux

```bash
git clone <your-repo-url>
cd aileron
python scripts/dev/docker/ops.py up --build
```

`up` first materialises the inputs Compose mounts — `.env` from `.env.example`,
plus the platform and TURN secrets — then builds and starts the stack. It is
idempotent, so an existing `.env` or secret is never rotated. Run
`python scripts/dev/docker/ops.py bootstrap` on its own to create those inputs
without starting anything.

> A cold first build produces 11 images and can take **45–60 minutes**.
> Subsequent builds reuse the Bake cache and finish in minutes.

### Workspace Runtime Base Selection

`workspace-runtime` builds on top of the slimmer `workspace-runtime/base-images/lite` base image.

Build the base image first, then build `workspace-runtime` on top of it:

```bash
make build-runtime-base-lite
make build-workspace-runtime
```

You can also override tags while building:

```bash
make build-runtime-base-lite RUNTIME_BASE_LITE_TAG=mytag
make build-workspace-runtime RUNTIME_BASE_LITE_TAG=mytag IMAGE_TAG=mytag
```

### Health Check

```bash
docker compose ps
```

Wait until the platform services report `healthy` before using the platform. When the optional bundled identity adapter is enabled, it may take about 1 minute to become ready.

Recommended services to verify before login:

- `postgres`
- `redis`
- `workspace-manager`
- `frontend`

If the bundled adapter is enabled and still starting, the frontend can show an OIDC authentication error. Wait until it reports `healthy`; external OIDC deployments do not require the bundled adapter.

### Stop The Stack

#### Windows PowerShell

```powershell
python .\scripts\dev\docker\ops.py down
```

#### macOS / Linux

```bash
python scripts/dev/docker/ops.py down
```

`down` is non-destructive: it stops the local stack while preserving volumes, PostgreSQL data, and persistent Workspace data.

### Full Reset

`full-reset` is the only destructive reset supported from the host. It removes dynamic Workspaces, platform volumes, and local persistent data under `data/`, including PostgreSQL. The reset succeeds only after all required resources have been removed.

macOS / Linux:

```bash
make full-reset
```

> **Warning:** Do not delete an individual Workspace Pod or container directly. Permanently delete a Workspace through the Manager UI or API so the execution plane, Workspace database records, persistent data, and permissions converge through the same idempotent `DELETE` workflow.

### Restart After a Full Reset

After `full-reset`, restart the platform through the standard host CLI:

#### Windows PowerShell

```powershell
python .\scripts\dev\docker\ops.py up --build
```

#### macOS / Linux

```bash
python scripts/dev/docker/ops.py up --build
```

---

## Access

| Service | URL | Username | Password |
|---|---|---:|---:|
| Aileron Frontend (bundled adapter bootstrap user) | http://localhost:8082 | admin | admin123 |
| Optional bundled OIDC adapter admin | http://localhost:8080/admin | keycloak-admin | `keycloak-bootstrap-admin-password` Secret |
| Manager API (same origin) | http://localhost:8082/api/v1 | - | - |

---

## Deployment Modes

### Docker Compose

Best for local development and small teams:

- starts the full platform with `docker compose`
- provides a fast and repeatable workspace setup flow
- reduces first-run and local environment setup overhead

### Kubernetes

Designed for production environments:

- core platform services are deployed through **Helm**
- dynamic workspace resources are managed by the **workspace-operator**

```bash
helm lint helm/aileron --namespace workspace-system
helm template test-release helm/aileron --namespace workspace-system
```

#### Knowledge Base Storage

Knowledge Bases add one more shared storage surface in Kubernetes mode:

- `kubernetes.knowledgeBases.pvcName` creates a dedicated `knowledge-bases-pvc`
- `workspace-manager` mounts that PVC at `/host/knowledge-bases`
- `workspace-operator` mounts each attached KB into runtime pods through `/knowledge/<alias>` with `subPath=<kbId>`

For local single-node development, the default chart uses:

```yaml
kubernetes:
  knowledgeBases:
    storageClassName: hostpath
```

This is a practical fallback, but not true multi-node RWX storage.

For production, switch to a shared RWX StorageClass such as NFS:

```bash
export PLATFORM_VALUES=/run/aileron/platform-values.yaml

helm upgrade --install aileron ./helm/aileron \
  --namespace workspace-system \
  --create-namespace \
  -f "${PLATFORM_VALUES}"
```

Minimum checks before enabling Knowledge Bases in Kubernetes:

- the cluster can provision `ReadWriteMany` storage, or you explicitly accept the single-node `hostpath` fallback
- `knowledge-bases-pvc` is `Bound`
- `workspace-manager` pod has `/host/knowledge-bases` mounted
- runtime pods can mount `/knowledge/<alias>` through the operator-managed `knowledge-bases` volume

### Public Domain Routing

Set one exact `platformPublicOrigin` in Helm values and point that host to the Frontend Ingress. The
same Origin serves the SPA, `/api/v1/...`, OAuth, and fixed
`/workspaces/{workspaceId}/runtime|browser|canvas/...` paths. Runtime, Browser, and Canvas remain
internal Services and need no public Workspace DNS names. Configure the external OIDC Provider's
canonical `oidc.issuerUrl` separately.

### Production Security Checklist

The default `docker-compose.yml` and `.env.example` files are tuned for local
development and are **not safe to use as-is in production**. Before exposing
the stack beyond your local machine, make sure to:

- Store PostgreSQL, OIDC, Runtime assertion, TURN, and other credentials in installation-owned Secret
  files. The root `.env` contains only host paths; services consume read-only `*_FILE` references.
- Do not publish the Postgres (`5432`) and Redis (`6379`) ports to the host
  network; keep them on the internal Docker/Kubernetes network only.
- Configure `PLATFORM_PUBLIC_ORIGIN`, `OIDC_ISSUER_URL`, and `OIDC_CLIENT_ID`. Discovery derives from
  the issuer; callback, logout, CORS, and CSRF Origin derive from Platform Public Origin.
- Workspace `terminal` and `browser-relay` WebSocket endpoints require
  short-lived, audience-bound Execution Grants. Keep these ports on the
  cluster network and expose them only through the supported frontend route.

---

## Common Commands

| Task | Command |
|---|---|
| Start stack | `python scripts/dev/docker/ops.py up` |
| Rebuild and start stack | `python scripts/dev/docker/ops.py up --build` |
| Build runtime base + image | `make build-runtime-base build-workspace-runtime` |
| View manager logs | `docker compose logs -f workspace-manager` |
| View runtime logs | `docker compose logs -f workspace-runtime` |
| Stop services and preserve data | `make down` |
| Full local reset (destructive) | `make full-reset` |

> `down` preserves data, while `full-reset` is the only destructive host reset. Permanently delete individual Workspaces through the Manager UI or API.

---

## Project Structure

```text
aileron/
├── frontend/              # React frontend
├── workspace-manager/     # Orchestration service (FastAPI)
├── workspace-runtime/     # Secure agent runtime
├── workspace-terminal/    # Terminal / WebSocket service
├── workspace-operator/    # Kubernetes workspace operator
├── workspace-chrome/      # Browser integration module
├── workspace-canvas/      # Frontend integration module
├── local-oidc/            # Docker bundled Keycloak OIDC (no LDAP seed)
├── scripts/               # Dev / test / ops scripts
├── data/                  # Local persistence (gitignored)
└── helm/                  # Kubernetes deployment charts
```

---

## Testing

This project provides container-based test entry points. Prefer these workflows:

```bash
make test-all
make test-frontend
make test-manager
make test-runtime
```

You can also use the existing test scripts:

```bash
python scripts/dev/docker/ops.py test manager
```

Or use the Makefile convenience targets:

```bash
make test-manager-cli
```

---

## Project Status

Aileron is still evolving quickly, and the product, docs, and overall experience will continue to change. Feedback, issues, and pull requests are welcome.

---

## License

This project is distributed under the **Apache License 2.0**.

See [LICENSE](./LICENSE) for details.
