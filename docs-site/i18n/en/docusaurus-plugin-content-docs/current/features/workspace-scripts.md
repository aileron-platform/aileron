---
sidebar_position: 6
title: Workspace Scripts
---

# Workspace Scripts

Workspace scripts keep helper scripts, initialization files, and team runbooks separate from project code. Runtime containers mount them at `/scripts`.

## Startup Entrypoints

| Scenario | Recommended entrypoint |
|----------|------------------------|
| Start the local stack | `python scripts/dev/docker/ops.py up` |
| Rebuild and start the stack | `python scripts/dev/docker/ops.py up --build` |
| Stop the stack | `python scripts/dev/docker/ops.py down` |
| Clean workspace resources | `python scripts/dev/docker/ops.py cleanup-workspaces` |
| Full cleanup | `python scripts/dev/docker/ops.py cleanup` |
| macOS / Linux legacy cleanup wrappers | `./scripts/dev/docker/cleanup.sh`, `./scripts/dev/docker/cleanup-workspaces.sh` |
| Windows PowerShell legacy cleanup wrappers | `.\scripts\dev\docker\cleanup.ps1`, `.\scripts\dev\docker\cleanup-workspaces.ps1` |

`ops.py` is the primary cross-platform host-side CLI. The `.sh` and `.ps1` wrappers remain available for cleanup workflows.

## Runtime Startup Script

The default runtime service starts with:

```yaml
command: /workspace-runtime/start_services.sh
```

Workspace-specific initialization scripts are generated or installed by Manager, stored in the data directory, and mounted into runtime when needed.

## Mounted Paths

| Host path | Runtime path | Description |
|-----------|--------------|-------------|
| `./data/workspace-scripts/default-workspace` | `/scripts` | Default workspace scripts |
| `./data/init-scripts/<workspaceId>` | runtime initialization source | Workspace startup scripts |
| `./workspace-runtime/scripts` | `/workspace-runtime/scripts` | Runtime service scripts |

## Supported File Types

Workspace scripts are file collections. Common files include:

| Extension | Usage |
|-----------|-------|
| `.sh` | Linux/macOS shell scripts, best for runtime execution |
| `.ps1` | PowerShell scripts for Windows host workflows or template content |
| `.md` | Runbooks and instructions |
| `.json` / `.yaml` | Configuration or sample payloads |

Runtime containers are Linux-based, so scripts intended to run inside runtime should prefer `.sh`. PowerShell scripts are useful for Windows host-side operations or template delivery.

## Template Scripts

Template `scripts` scope is installed into a workspace at:

```text
/scripts/<templateName>/
```

Manager template APIs manage the template `scripts` scope. Runtime script APIs manage installed or user-created workspace scripts.

See [Runtime API](/api/runtime-api#scripts) for endpoint details.
