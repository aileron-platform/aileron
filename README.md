# ✈️ Aileron

[繁體中文](./README.zh-TW.md)

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
| Create Workspace | Template Center & AI Chat |
| [![Create Workspace Demo](https://img.youtube.com/vi/G8AXGd0_Xwo/hqdefault.jpg)](https://youtu.be/G8AXGd0_Xwo) | [![Template Center & AI Chat Demo](https://img.youtube.com/vi/pl0H4j07IsU/hqdefault.jpg)](https://youtu.be/pl0H4j07IsU) |

---

## Why Aileron?

When enterprises adopt AI agents, the hard part is rarely just model capability. The real challenge is making agent usage align with internal governance while avoiding the need for every user to assemble a complex development environment by hand.

Aileron is built to solve both sides of that problem:

- make agents easier for enterprises to adopt
- make workspaces easier for users to start using

---

## Core Capabilities

- **Governance-Aligned Workspaces**  
  Centralized configuration, templates, permissions, and standardized capabilities help align agent usage with enterprise governance.

- **Simplified Workspace Setup**  
  Users can start from ready-to-use agent workspaces instead of assembling local environments from scratch.

- **Standardized Tooling and Workflows**  
  MCP, slash commands, workflows, and integrations are standardized at the platform level to reduce team-to-team drift.

- **Unified Workspace Surfaces**  
  Chat, file management, Git, and web terminal capabilities are integrated into the same workspace experience.

- **Enterprise Authentication and Governance**  
  Keycloak-based authentication and governance features provide SSO, role-based access, and centralized platform control.

- **Built-In OpenSpec Workflow**  
  OpenSpec is treated as a first-class workspace capability rather than an external documentation flow.

---

## Agent Support Status

Aileron currently offers the most complete integration for **Claude Code**, while continuing to expand support for other agents.

- `Claude Code`: most complete support today
- `OpenCode`: expanding support
- `Gemini`: expanding support
- `Codex`: expanding support

---

## Tech Stack

Aileron is built on a modern microservices architecture:

- **Frontend**: React-based management UI, workspace shell, and web terminal experience
- **Workspace Manager**: FastAPI service for orchestration and lifecycle management
- **Workspace Runtime**: secure containerized execution runtime for agents
- **Workspace Terminal**: Go-based terminal / WebSocket service
- **Workspace Operator**: Kubernetes-native dynamic workspace provisioning
- **Agent Tools**: native integration with Claude Code and related workspace tooling
- **Infrastructure**:
  - **PostgreSQL**: relational persistence
  - **Redis**: caching and task coordination
  - **Keycloak**: identity and access management
  - **Draw.io / Flower**: diagramming and task monitoring

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

> The first build may take **5–10 minutes**.

### Workspace Runtime Base Selection

`workspace-runtime` now supports two base image options:

- `RUNTIME_BASE=universal`: pulls the published `ailerondocker/codex-universal` base from Docker Hub
- `RUNTIME_BASE=lite`: uses the slimmer `workspace-runtime/base-lite` base

Pull or build the base image first, then build `workspace-runtime` with the desired flavor:

```bash
# Lite base
make build-runtime-base-lite
make build-workspace-runtime RUNTIME_BASE=lite

# Full universal base from Docker Hub
make build-codex-universal
make build-workspace-runtime RUNTIME_BASE=universal
```

You can also override tags while building:

```bash
make build-runtime-base-lite RUNTIME_BASE_LITE_TAG=mytag
make build-workspace-runtime RUNTIME_BASE=lite RUNTIME_BASE_LITE_TAG=mytag IMAGE_TAG=mytag
```

### Health Check

```bash
docker compose ps
```

Wait until all services report `healthy` before using the platform. Keycloak may take about 1 minute to become ready.

Recommended services to verify before login:

- `postgres`
- `redis`
- `keycloak`
- `workspace-manager`
- `frontend`

If `keycloak` is still starting, the frontend can show an OIDC authentication error. Wait until it reports `healthy`.

### Stop The Stack

#### Windows PowerShell

```powershell
python .\scripts\dev\docker\ops.py down
```

#### macOS / Linux

```bash
python scripts/dev/docker/ops.py down
```

This stops the local stack while preserving volumes and persisted data.

### Cleanup Workflows

Use `cleanup-workspaces` for routine workspace resets. Use `cleanup` only when you need a full environment reset.

#### Workspace Cleanup

Removes dynamic workspace containers and related transient resources, while preserving the main platform services and databases.

Windows PowerShell:

```powershell
python .\scripts\dev\docker\ops.py cleanup-workspaces
```

macOS / Linux:

```bash
python scripts/dev/docker/ops.py cleanup-workspaces
```

Legacy wrapper scripts remain available if you prefer shell-specific entrypoints:

```powershell
.\scripts\dev\docker\cleanup-workspaces.ps1
```

```bash
./scripts/dev/docker/cleanup-workspaces.sh
```

#### Full Cleanup

Stops the stack, removes platform volumes and generated local data, and resets the local environment.

Windows PowerShell:

```powershell
python .\scripts\dev\docker\ops.py cleanup
```

macOS / Linux:

```bash
python scripts/dev/docker/ops.py cleanup
```

Legacy wrapper scripts remain available here as well:

```powershell
.\scripts\dev\docker\cleanup.ps1
```

```bash
./scripts/dev/docker/cleanup.sh
```

> `cleanup` is destructive. It removes Docker volumes and persisted platform data, including PostgreSQL data.

### Restart After Cleanup

After either cleanup flow, start the stack again with the standard host-side CLI:

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
| Aileron Frontend | http://localhost:8082 | admin | admin123 |
| Keycloak Admin | http://localhost:8080/admin | admin | admin |
| Manager API | http://localhost:3001 | - | - |
| Flower | http://localhost:5555 | - | - |
| Draw.io | http://localhost:8083 | - | - |

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
helm lint helm/aileron
helm template test-release helm/aileron

helm install aileron ./helm/aileron \
  --namespace aileron \
  --create-namespace
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
helm upgrade --install aileron ./helm/aileron \
  --namespace aileron \
  --create-namespace \
  -f helm/values-rke.yaml
```

Minimum checks before enabling Knowledge Bases in Kubernetes:

- the cluster can provision `ReadWriteMany` storage, or you explicitly accept the single-node `hostpath` fallback
- `knowledge-bases-pvc` is `Bound`
- `workspace-manager` pod has `/host/knowledge-bases` mounted
- runtime pods can mount `/knowledge/<alias>` through the operator-managed `knowledge-bases` volume

### Public Domain Routing

To expose the platform through public domains, configure:

- `publicRouting.*` in Helm values
- fixed DNS records for frontend / workspace-manager / keycloak
- wildcard or equivalent DNS for workspace runtime / browser / nextjs services
- valid TLS certificates

---

## Common Commands

| Task | Command |
|---|---|
| Start stack | `python scripts/dev/docker/ops.py up` |
| Rebuild and start stack | `python scripts/dev/docker/ops.py up --build` |
| Build runtime with lite base | `make build-workspace-runtime RUNTIME_BASE=lite` |
| Build runtime with universal base | `make build-workspace-runtime RUNTIME_BASE=universal` |
| View manager logs | `docker compose logs -f workspace-manager` |
| View runtime logs | `docker compose logs -f workspace-runtime` |
| Stop services | `python scripts/dev/docker/ops.py down` |
| Cleanup workspaces | `python scripts/dev/docker/ops.py cleanup-workspaces` |
| Full reset (destructive) | `python scripts/dev/docker/ops.py cleanup` |

> `python scripts/dev/docker/ops.py` is the primary cross-platform CLI for startup, shutdown, cleanup, and test execution.
>
> Use `cleanup-workspaces` for routine workspace cleanup. Use `cleanup` only when you need to delete persisted platform data and volumes.
>
> On macOS / Linux, the legacy wrappers remain available: `./scripts/dev/docker/cleanup.sh` and `./scripts/dev/docker/cleanup-workspaces.sh`.
>
> On Windows PowerShell, the legacy wrappers remain available: `.\scripts\dev\docker\cleanup.ps1` and `.\scripts\dev\docker\cleanup-workspaces.ps1`.

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
├── workspace-nextjs/      # Frontend integration module
├── keycloak-realm/        # IAM configuration
├── scripts/               # Dev / test / ops scripts
├── openspec/              # OpenSpec changes and specs
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
python scripts/dev/docker/ops.py test runtime
```

Or use the Makefile convenience targets:

```bash
make test-manager-cli
make test-runtime-cli
```

---

## Project Status

Aileron is still evolving quickly, and the product, docs, and overall experience will continue to change. Feedback, issues, and pull requests are welcome.

---

## License

This project is distributed under the **Apache License 2.0**.

See [LICENSE](./LICENSE) for details.
