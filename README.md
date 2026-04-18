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

### Installation

```bash
git clone <your-repo-url>
cd aileron
docker compose up -d --build
```

> The first build may take **5–10 minutes**.

### Workspace Runtime Base Selection

`workspace-runtime` now supports two base image options:

- `RUNTIME_BASE=universal`: uses the existing full `codex-universal` base
- `RUNTIME_BASE=lite`: uses the slimmer `workspace-runtime/base-lite` base

Build the base image first, then build `workspace-runtime` with the desired flavor:

```bash
# Lite base
make build-runtime-base-lite
make build-workspace-runtime RUNTIME_BASE=lite

# Full universal base
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
| Restart stack | `docker compose up -d --build` |
| Build runtime with lite base | `make build-workspace-runtime RUNTIME_BASE=lite` |
| Build runtime with universal base | `make build-workspace-runtime RUNTIME_BASE=universal` |
| View manager logs | `docker compose logs -f workspace-manager` |
| View runtime logs | `docker compose logs -f workspace-runtime` |
| Stop services | `docker compose down` |
| Clear workspaces | `./scripts/dev/docker/cleanup-workspaces.sh` |
| Full reset (destructive) | `./scripts/dev/docker/cleanup.sh` |

> `cleanup.sh` removes all data and databases.

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
./scripts/test/run-all-tests.sh manager
./scripts/test/run-all-tests.sh runtime
```

---

## Project Status

Aileron is still evolving quickly, and the product, docs, and overall experience will continue to change. Feedback, issues, and pull requests are welcome.

---

## License

This project is distributed under the **Apache License 2.0**.

See [LICENSE](./LICENSE) for details.
