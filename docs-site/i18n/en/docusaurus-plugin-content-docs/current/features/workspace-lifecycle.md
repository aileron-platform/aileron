---
sidebar_position: 1
title: Workspace Lifecycle
---

# Workspace Lifecycle Management

Workspace lifecycle management in Aileron is not only about provisioning containers. It is the mechanism that lets enterprises provide standardized, ready-to-use agent environments to users without requiring manual local setup.

## Lifecycle States

```
          ┌──────────┐
          │ creating │  ← POST /workspaces
          └────┬─────┘
               │
          ┌────▼─────┐
          │ running  │  ← Container/Pod ready
          └────┬─────┘
               │
     ┌─────────┼─────────┐
     │         │         │
┌────▼──┐ ┌───▼──────┐ ┌──▼──────┐
│stopped│ │restarting│ │deleting │
└───────┘ └──────────┘ └─────────┘
```

## Supported Provisioners

| Provisioner | Description |
|-------------|-------------|
| `docker` | Create containers using Docker (default for local dev) |
| `kubernetes` | Create Pods and related resources using Kubernetes |

Each workspace chooses its provisioner at creation time, depending on whether the organization is optimizing for local setup or production infrastructure.

## Creating a Workspace

Use the frontend UI or call the API directly:

```bash
curl -X POST http://localhost:3001/api/v1/workspaces \
  -H "Content-Type: application/json" \
  -d '{
    "name": "my-workspace",
    "template_id": "...",
    "provisioner": "docker"
  }'
```

### Creating from a Template

A Template defines the workspace's:
- Container image
- Default environment variables
- Install steps
- Firewall configuration
- Feature tags

This makes workspace creation repeatable and easier to align with team-wide conventions and internal requirements.

## Container Composition

Each workspace includes the following containers/services:

| Service | Description |
|---------|-------------|
| `workspace-runtime` | Main execution environment (FastAPI + Claude Code) |
| `workspace-terminal` | In-browser terminal |
| `workspace-chrome` | Headless Chrome (browser preview) |
| `workspace-nextjs` (optional) | Next.js dev server |

## Firewall Configuration

Each workspace can configure:

| Setting | Description |
|---------|-------------|
| `workspace_firewall_network_access_enabled` | Enable workspace network access |
| `workspace_firewall_domain_access_mode` | Domain access mode (allowlist / deny) |
| `workspace_firewall_allowed_domains` | List of domains the workspace may reach |
| `browser_firewall_network_access_enabled` | Enable browser network access |
| `browser_firewall_domain_access_mode` | Browser domain access mode |
| `browser_firewall_allowed_domains` | List of domains the browser may reach |

:::note
In Kubernetes mode, firewall policies are implemented via Cilium NetworkPolicy. The system's default `allowedDomains` are merged with workspace-specific settings during the reconcile phase to produce the final effective policy.
:::

## Lifecycle Operations

### Stop Workspace

Stops the workspace container; data is preserved.

### Start (Restart) Workspace

Starts a previously stopped workspace.

### Delete Workspace

Deletes the workspace and all associated resources. Docker and Kubernetes modes expose a consistent operation from the frontend UI.

### Restart Individual Services

The following services can be restarted individually:
- `runtime`
- `browser`
- `nextjs`

## Kubernetes Workspace Resources

In Kubernetes mode, the workspace-operator reconciles the following resources for each workspace:

- Runtime Pod / Deployment
- Browser Pod / Deployment
- Next.js Pod / Deployment (optional)
- Services
- PersistentVolumeClaim (PVC)
- Cilium NetworkPolicy (firewall)
- `Workspace` Custom Resource (CR)
