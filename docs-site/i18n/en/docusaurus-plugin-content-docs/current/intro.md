---
slug: /
sidebar_position: 1
title: Introduction
---

# Aileron

**Standardized AI Agent Workspaces for Enterprise Teams.**

Aileron is an enterprise AI agent workspace platform designed to help organizations adopt agents in ways that align with internal governance, access policies, and infrastructure requirements.

By providing standardized, ready-to-use workspaces, integrated tooling, and built-in workflow capabilities, Aileron reduces the effort required for users to set up environments and start working productively.

Today, **Claude Code** provides the most complete end-to-end experience in Aileron, including chat execution, streaming output, settings management, automation, and OpenSpec workflow integration. At the same time, the platform is evolving toward a multi-agent architecture, with **OpenCode**, **Gemini**, and **Codex** integrations being expanded over time.

## 🛡️ Why Aileron?

### Governance-Aligned Workspaces

Centralized Marketplace packages, access controls, and standardized runtime capabilities make it easier to introduce agents in ways that fit enterprise operating models instead of bypassing them.

### Simplified Workspace Setup

Users do not need to manually assemble complex local environments before they can start. Aileron provides ready-to-use workspaces with preconfigured tools, services, and workflow integrations.

### Governed Marketplace Tooling

A central **Marketplace** lets teams review, import, and install Slash Commands, MCP Servers, install flows, and environment variables while keeping tooling and workflow conventions consistent.

### Lower Adoption Barriers For Non-Technical Users

One important reason to choose Aileron is that it significantly reduces the friction involved in setting up AI agent environments and using CLI-based tools. In many teams, these workflows still depend on engineering knowledge and a fair amount of manual setup, which creates unnecessary barriers for non-technical users. Aileron provides a more consistent and approachable operating model so product, operations, design, and business roles can participate earlier without needing to master the underlying tooling first. That reduces reliance on engineering support and lets teams focus more on real adoption, workflow validation, and cross-functional collaboration.

### Hybrid & Pluggable Runtime

Claude Code CLI / SDK is currently the default and most complete execution engine, while MCP bridges internal services and tools. The platform is decoupled from any single model provider, and is steadily expanding toward OpenCode, Gemini, Codex, and other agent runtimes.

### Enterprise-Grade Auth & Governance

Native **Keycloak OAuth2 / OIDC** integration brings SSO, role-based access, and user quotas. All platform services flow through unified authentication so platform teams can keep governance and access control in one place.

### OpenSpec As A Built-In Workflow

OpenSpec is now integrated as a built-in workspace capability rather than just a set of side commands. Users can browse `openspec/` documents inside the workspace, inspect the current change context, and launch proposal, explore, apply, and archive workflows directly from the chat composer.

## 🧩 Key Features

| Feature | Description |
|---------|-------------|
| Workspace Lifecycle | Create, start, stop, and delete workspaces across Docker Compose and Kubernetes (workspace-operator + CRDs) |
| Multi-Agent Runtime Model | Claude Code is currently the most complete integration, with OpenCode, Gemini, and Codex support expanding over time |
| OpenSpec Workflow | Browse OpenSpec documents natively in the workspace, track change state, and launch workflow actions from the chat composer |
| Marketplace Packages | Review, import, and install Slash Commands, MCP Servers, env vars, and install flows across teams |
| Multi-form Runtimes | Terminal (Go-based PTY), Chrome/Browser, and Canvas Runtime — all usable as agent-controllable execution surfaces |
| File Explorer & Git | Real-time file monitoring, version control operations, branch management |
| Scheduler / Automation | Cron-based tasks can drive agent workflows; Claude Code currently has the most complete automation experience |
| Keycloak OAuth2 / OIDC | Enterprise-grade authentication with SSO and role-based access |
| Policy Controls | Workspace and browser domain policies can be managed separately, with Cilium-based enforcement in Kubernetes |

## Agent Support Status

| Agent | Status | Notes |
|-------|--------|-------|
| Claude Code | Fully supported | The most complete experience today, including chat, settings, automation, and OpenSpec workflow integration |
| Gemini | Partial support | Settings and integration foundations exist; end-to-end parity is still being built out |
| OpenCode | Partial support | Settings and integration foundations exist; more workflow and execution support is planned |
| Codex | Partial support | Settings and integration foundations exist; more execution and governance support is planned |

## Project Status

Aileron is currently being built in **100% Vibe Coding** mode. That lets the project move quickly across multi-agent workspaces, OpenSpec workflows, and governance features, but it also means some functionality, docs, and UX are still evolving rapidly.

If you're trying the project, contributions are welcome:

- Test features and report issues
- Submit fixes or pull requests
- Share real-world workflows and requirements

## Roadmap

- Close capability gaps across OpenCode, Gemini, Codex, and other agents
- Deepen the native OpenSpec workflow experience inside the workspace
- Expand team collaboration and governance features
- Introduce worktree-oriented development flows for better parallelism and isolation

## 🛠️ Tech Stack

- **Runtime**: Claude Code CLI / OpenSpec CLI, with broader multi-agent CLI integrations expanding over time
- **Orchestrator**: Python + FastAPI (workspace-manager / workspace-runtime)
- **Interface**: React-based Web UI, Go-based Web Terminal
- **Integration**: Chrome Extension (WXT/MV3), Canvas Workspace, MCP Servers
- **Platform**: Docker Compose, Kubernetes (Helm + workspace-operator), Cilium
- **Infrastructure**: PostgreSQL, Redis, Keycloak

## Deployment Modes

```
┌─────────────────────────────────────────────────────────────────┐
│                            Aileron                             │
├────────────────────────┬────────────────────────────────────────┤
│     Docker mode        │           Kubernetes mode              │
│                        │                                        │
│  docker compose        │  Helm chart → platform services        │
│  Local dev & demo      │  workspace-operator → workspace CRs    │
│                        │  Cilium → firewall policy              │
└────────────────────────┴────────────────────────────────────────┘
```

See [Deployment](/deployment/docker) for details.

## System Architecture

```
┌──────────────────────────────────────────────────┐
│                    Frontend (React)              │
│   Workspace List │ Chat Panel │ File Explorer    │
│   Git │ Settings │ Automation Dashboard          │
└─────────────────────────┬────────────────────────┘
                          │ REST / WebSocket
┌─────────────────────────▼────────────────────────┐
│              Workspace Manager (FastAPI)         │
│   Workspace CRUD │ Marketplace │ Automation      │
│   Auth (Keycloak) │ Teams │ Docker/K8s Provisioner │
└──────────┬──────────────────────┬────────────────┘
           │ HTTP                 │ Docker / K8s API
┌──────────▼──────┐    ┌──────────▼──────────────┐
│ Workspace       │    │  Container / Pod        │
│ Runtime         │    │  (workspace-runtime)    │
│ (FastAPI)       │◄───►  Agent Runtime │ Files   │
│                 │    │  OpenSpec │ Git │ Terminal │
└─────────────────┘    └─────────────────────────┘
           │
┌──────────▼──────────────────────────────────────┐
│                 Infrastructure                  │
│   PostgreSQL │ Redis │ Keycloak │ Cilium        │
└─────────────────────────────────────────────────┘
```

## Quick Start

```bash
git clone <your-repo-url>
cd aileron
python scripts/dev/docker/ops.py up --build
```

This default setup is intended to get teams from zero to a usable agent workspace quickly, without requiring every user to assemble the full environment manually.

For full installation instructions, see the [Installation Guide](/quick-start/installation).
