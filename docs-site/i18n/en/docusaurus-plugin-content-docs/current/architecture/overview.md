---
sidebar_position: 1
title: Architecture Overview
---

# Architecture Overview

Aileron uses a microservices architecture with clearly separated, independently deployable services. The architecture is designed to help enterprises deliver governed, repeatable agent workspaces while keeping environment setup simpler for end users.

Today, Claude Code provides the most complete agent experience in the platform, but the overall architecture is not tied to a single tool. It is evolving toward a broader multi-agent workspace platform, with OpenSpec already integrated as a built-in workflow capability.

## System Components

```
┌─────────────────────────────────────────────────────────────────┐
│                        User (Browser)                           │
└───────────────────────────────┬─────────────────────────────────┘
                                │ HTTPS / WebSocket
┌───────────────────────────────▼─────────────────────────────────┐
│                    Frontend (React + Vite)                       │
│  ┌─────────────┐ ┌──────────────┐ ┌─────────────────────────┐  │
│  │ Workspace   │ │ Chat Panel   │ │ File Explorer / Git /   │  │
│  │ List / Mgmt │ │ (Agent Chat) │ │ Settings / Automation   │  │
│  └─────────────┘ └──────────────┘ └─────────────────────────┘  │
└───────────────────────────────┬─────────────────────────────────┘
                                │ REST API
┌───────────────────────────────▼─────────────────────────────────┐
│              Workspace Manager (Python / FastAPI)                │
│  ┌──────────────┐ ┌──────────────┐ ┌───────────────────────┐   │
│  │ Workspace    │ │ Marketplace  │ │ Automation / Celery   │   │
│  │ CRUD + Auth  │ │ + Settings   │ │ Scheduler             │   │
│  └──────────────┘ └──────────────┘ └───────────────────────┘   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │           Docker / Kubernetes Provisioner            │   │
│  └──────────────────────────────────────────────────────────┘   │
└──────────┬────────────────────────────┬────────────────────────┘
           │ REST                        │ Container API
           │                   ┌─────────▼────────────┐
           │                   │  Container / Pod      │
┌──────────▼──────────┐        │                      │
│  Workspace Runtime  │        │  workspace-terminal  │
│  (FastAPI)          │◄──────►│  workspace-chrome    │
│  per workspace      │        │  workspace-canvas    │
│  Agent Runtime API  │        │                      │
│  OpenSpec / Sessions│        │                      │
│  File Watch / Git   │        └──────────────────────┘
│  System Monitor     │
│  WebSocket          │
└─────────────────────┘
           │
┌──────────▼──────────────────────────────────────────┐
│                    Infrastructure                    │
│  ┌──────────────┐  ┌──────────┐  ┌───────────────┐  │
│  │  PostgreSQL  │  │  Redis   │  │   Keycloak    │  │
│  │  (main DB)   │  │  (cache/ │  │  (OAuth2/OIDC)│  │
│  │              │  │   queue) │  │               │  │
│  └──────────────┘  └──────────┘  └───────────────┘  │
└─────────────────────────────────────────────────────┘
```

## Services

### Frontend
A React + Vite frontend providing the complete workspace management UI:
- Workspace creation, management, and settings
- Agent chat panel (Claude Code is currently the most complete experience, with streaming)
- File explorer and Git operations
- OpenSpec navigation and workflow actions
- Automation dashboard
- Keycloak OIDC integration

### Workspace Manager
The core backend (FastAPI) responsible for:
- Workspace CRUD and lifecycle management
- Multi-provisioner support (Docker, Kubernetes)
- Marketplace package management
- Team management and governance features
- Automation tasks (Celery + Redis)
- Authentication (Keycloak JWT verification)

In practice, this is the layer that lets platform teams define how workspaces should be created and governed without forcing every user to repeat the same setup manually.

### Workspace Runtime
Runs inside each workspace container (FastAPI) and handles:
- Agent execution and streaming (Claude Code is currently the most complete integration)
- OpenSpec CLI and workflow state integration
- File system monitoring (Watchdog)
- Git operations
- System resource monitoring (psutil)
- Real-time WebSocket communication

### Workspace Sidecars

| Service | Description |
|---------|-------------|
| `workspace-terminal` | Provides terminal access in the browser |
| `workspace-chrome` | Headless Chromium for browser preview |
| `workspace-canvas` | Optional Canvas renderer |

## Directory Layout

```
aileron/
├── frontend/               # React + Vite frontend
├── workspace-manager/      # Core management service (Python/FastAPI)
├── workspace-runtime/      # Workspace execution environment (Python/FastAPI)
├── workspace-terminal/     # Terminal service
├── workspace-chrome/       # Chrome browser service
├── workspace-canvas/       # Canvas service
├── workspace-operator/     # Kubernetes operator
├── helm/                   # Helm chart (Kubernetes deployment)
├── keycloak-realm/         # Keycloak realm configuration
├── scripts/                # Deployment and maintenance scripts
├── data/                   # Local dev data (gitignored)
└── docker-compose.yml      # Docker Compose configuration
```

## Data Flow

### Workspace Creation

```
Frontend
  │  POST /api/v1/workspaces
  ▼
Workspace Manager
  │  Select provisioner (Docker / K8s)
  │  Create container/Pod
  │  Save workspace record to PostgreSQL
  ▼
Container / Pod
  │  workspace-runtime starts
  │  Reports status back to Manager
  ▼
Frontend
  │  Receives status via WebSocket
  ▼
(User can now use chat, files, terminal)
```

### Agent Execution

```
Frontend (Chat Panel)
  │  POST /api/v1/agent-sessions
  ▼
Workspace Runtime
  │  Creates agent session
  │  Runs the selected agent CLI
  │  Streams output
  ▼
WebSocket → Frontend
  │  Real-time display
```
