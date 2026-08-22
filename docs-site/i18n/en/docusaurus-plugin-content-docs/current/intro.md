---
slug: /
title: Introduction
---

# Aileron

**The Hardened Orchestration Layer for Enterprise AI Agents**

Aileron is a multi-agent workspace and orchestration platform built for enterprise environments. It combines containerized execution, the Model Context Protocol (MCP), a governed Marketplace, and a first-class multi-agent runtime architecture to address the security monitoring, environment isolation, and large-scale deployment challenges of existing AI development tools. Teams can introduce AI agents into everyday workflows with confidence.

Aileron fully supports **Claude Code**, **OpenCode**, and **Codex** as first-class agent engines, including chat execution, streaming output, settings management, and automation. Its multi-agent architecture lets teams choose the appropriate execution path for each task, model provider, and governance requirement.

## 🛡️ Why Aileron?

### Containerized Sandboxes

Every command executed by an AI agent, including Bash, Read, Write, and Git operations, runs inside an isolated Docker container or Kubernetes Pod. Each workspace has its own runtime, filesystem, and network boundary. In Docker mode, the Runtime applies iptables egress rules. In Kubernetes mode, workspace-operator generates Cilium network policies. Both modes manage workspace and browser domain allowlists separately to reduce unintended file or external-resource access.

### Two One-Shot Marketplace Paths

The **Marketplace** provides two independent one-shot paths. Plugin artifacts are published to the team's private GitLab repository and then installed and enabled by a compatible target-client CLI. User-copy projects compatible standalone resources into the Workspace Runtime HOME user scope once. After success, users update or remove those resources themselves; Marketplace creates no post-installation lifecycle.

### Lower Adoption Barriers for Non-Technical Users

Aileron substantially reduces the effort required to set up AI agent environments and use CLI-based tools. These workflows traditionally depend on engineering expertise and complicated configuration, which makes them difficult for non-technical users. Aileron provides a more consistent and approachable experience so product, operations, design, and business teams can participate sooner. This reduces reliance on engineering support and lets teams focus on adoption, workflow validation, and collaboration.

### Hybrid and Pluggable Runtime

Claude Code, OpenCode, and Codex all run as fully supported, first-class agent engines inside a workspace and connect to internal services and tools through MCP. The platform is decoupled from any single model provider and can use cloud-hosted or on-premises models and agent CLIs according to governance needs.

### Enterprise Authentication and Governance

Native external **OIDC** integration provides SSO, role-based access, and user quotas. Manager is the
only provider trust boundary. Frontend uses an opaque session, while Runtime and Terminal use
short-lived Execution Grants so the execution plane never receives provider tokens.

## 🧩 Key Features

| Feature | Description |
|------|------|
| [Workspace lifecycle management](/features/workspace/lifecycle-and-access) | Create, start, stop, and delete workspaces through the dynamic Docker provisioner or Kubernetes with workspace-operator and CRDs |
| [Multi-agent runtime architecture](/features/workspace/ai-agent/) | Fully supported Claude Code, OpenCode, and Codex execution paths |
| [Marketplace packages](/features/marketplace) | One-shot installation and enablement by a compatible target-client CLI, or standalone-resource projection into Workspace user scope |
| [Multiple runtime surfaces](/architecture/backend/workspace-runtime/) | Go-based Terminal PTY, Chrome/Browser, and Next.js surfaces that agents can operate |
| [File Explorer and Git](/api/runtime-api#file-management) | File operations, local history, version-control operations, and branch management |
| [Scheduler and Automation](/features/automation) | Cron-based tasks that run Claude Code, OpenCode, or Codex agent workflows |
| [External OIDC](/installation/oidc) | Manager BFF enterprise SSO, opaque sessions, and execution-plane Grants |
| Firewall policies | Runtime-local iptables in Docker and Cilium in Kubernetes, with separate workspace and browser domain allowlists |
| [Knowledge Base](/features/knowledge-base/) | Team knowledge, project standards, and runbooks with permission-based sharing and zero-copy read-only Workspace mounts |
| [Question Form](/features/workspace/ai-agent/ai-chat) | Structured multiple-choice forms that agents can present in chat instead of asking users to type option text |

## Agent Support

| Agent | Status | Description |
|------|------|------|
| Claude Code | Fully supported | Chat, settings management, and automation |
| OpenCode | Fully supported | Chat, settings management, and automation |
| Codex | Fully supported | Chat, settings management, and automation |

## Project Status

Aileron is currently evolving rapidly through **100% Vibe Coding**. This makes it possible to validate multi-agent workspaces and enterprise governance capabilities quickly, but some features, documentation, and user experiences will continue to change.

If you are evaluating the project, contributions are welcome:

- Test features and report issues.
- Submit fixes or pull requests.
- Share real-world use cases and requirements.

## Roadmap

- Continue improving consistency across Claude Code, OpenCode, and Codex.
- Expand team collaboration and governance capabilities.
- Introduce worktree-oriented development for more natural parallel and isolated tasks.

## 🛠️ Technology Stack

- **Runtime**: Claude Code CLI / OpenCode CLI / Codex CLI
- **Orchestrator**: Python + FastAPI (`workspace-manager` / `workspace-runtime`)
- **Interface**: React-based Web UI and Go-based Web Terminal
- **Integration**: Chrome Extension (WXT/MV3), Next.js Workspace, and MCP Servers
- **Platform**: Docker, Docker Compose, and iptables; Kubernetes (Helm + workspace-operator) and Cilium
- **Infrastructure**: PostgreSQL, Redis, and an external OIDC provider

## Deployment Modes

```text
┌─────────────────────────────────────────────────────────────────┐
│                            Aileron                              │
├────────────────────────┬────────────────────────────────────────┤
│      Docker mode       │            Kubernetes mode             │
│                        │                                        │
│  docker compose        │  Helm chart → platform services        │
│    → platform services │  workspace-operator → workspace CRs    │
│  Docker SDK → Workspace│  Cilium → firewall policy              │
│    containers          │                                        │
│  iptables → firewall   │                                        │
└────────────────────────┴────────────────────────────────────────┘
```

See [Installation](/installation/docker) for details.

## System Architecture

Aileron uses a three-layer architecture consisting of Frontend, Workspace Manager, and Workspace Runtime. Manager handles Workspace CRUD, Marketplace, Automation, and Docker or Kubernetes provisioning. Each Workspace Runtime provides agent execution, file operations, and Git operations inside the Workspace container. See the [Architecture Overview](/architecture/overview/) for the complete component diagram and data flow.

## Quick Start

```bash
git clone <your-repo-url>
cd aileron
docker buildx bake --load local
docker compose up --remove-orphans --no-build -d
```

See the [Installation Guide](/installation/getting-started) for complete instructions.
