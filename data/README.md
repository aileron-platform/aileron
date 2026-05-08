# Data Directory

This directory stores all persistent Aileron data.

## Layout

```text
data/
├── postgres/              # PostgreSQL data files
├── redis/                 # Redis persistence
├── workspaces/            # Workspace Runtime data
│   ├── default-workspace/
│   └── {workspace-id}/
├── claude-data/           # Claude Code related data
├── workspace-manager/
│   └── projects/
├── init-scripts/          # Initialization scripts
└── ssh-keys/              # SSH keys
```

## Directory Notes

- `postgres/`: database files managed by PostgreSQL
- `redis/`: Redis persistence data such as RDB and AOF
- `workspaces/`: one directory per workspace, including project code and config
- `claude-data/`: MCP, hooks, subagents, and other Claude Code data
- `workspace-manager/projects/`: project files managed by Workspace Manager
- `init-scripts/`: SQL and other bootstrap scripts
- `ssh-keys/`: keys used for Git and remote connections

## Important Notes

1. Do not edit files inside `postgres/` or `redis/` manually.
2. Back up `workspaces/` regularly.
3. Make sure container users have the expected read and write permissions.
4. Data files under this directory are intentionally excluded from Git.

## Docker Compose Mounts

```yaml
# PostgreSQL
- ./data/postgres:/var/lib/postgresql/data

# Redis
- ./data/redis:/data

# Workspace Manager
- ./data/workspace-manager/projects:/workspace-manager/projects
- ./data/init-scripts:/data/init-scripts

# Workspace Runtime
- ./data/ssh-keys:/workspace-runtime/ssh_keys:ro
- ./data/workspaces/{workspace-id}:/workspace
```

## Related Environment Variables

```bash
HOST_WORKSPACES_DIR=./data/workspaces
HOST_CLAUDE_DATA_DIR=./data/claude-data
HOST_SSH_KEYS_DIR=./data/ssh-keys
```
