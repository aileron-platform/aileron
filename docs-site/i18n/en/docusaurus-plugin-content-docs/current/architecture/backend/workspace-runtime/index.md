---
title: Workspace Runtime
---

# Workspace Runtime

## Overview

Workspace Runtime is the service that runs inside each development Workspace container. It provides Agent execution integration, file management and local history, Git, the Thread event WebSocket, and Automation execution. Claude Code, Codex, and OpenCode all execute through this runtime.

## Core Features

### Agent Execution Integration

- **Settings management**: read and update Claude Code, Codex, and OpenCode settings
- **Hooks management**: configure and manage custom hooks
- **MCP integration**: manage MCP server configuration
- **Subagent management**: Claude Code subagent settings
- **Slash commands**: manage custom slash commands

For the complete boundary from a frontend message through three-agent event normalization, Thread persistence, WebSocket delivery, and the frontend timeline, see [AI Chat Frontend and Backend Architecture](/architecture/overview/ai-chat).

### File-System Management

- **File operations**: directory trees, search, read/write, upload, copy, move, archive, and extract
- **Local history**: list file-change history and restore a selected version
- **Version control**: Git integration and operations
- **Knowledge Base**: expose Workspace attachments zero-copy and read-only at `/knowledge/{alias}`; Runtime cannot switch a KB to writable mode

### Automation Execution

- **Claim and complete**: claim work from Manager with an instance-scoped control token and report the result
- **Lease and heartbeat**: refresh the lease during execution so Manager can detect a lost execution
- **State persistence**: store Automation execution and Thread state in the Workspace-scoped Runtime PostgreSQL schema

### WebSocket Communication

- **Thread event channel**: push Thread invalidation and execution-state events to the frontend
- **Reconnect**: refetch the authoritative timeline after the frontend reconnects
- **Authentication**: browsers carry the Bearer credential in a WebSocket subprotocol, never in the URL

### Authorization and Generation

- **Action gate**: map HTTP and WebSocket routes from the closed inventory to
  `runtime_read`, `runtime_write`, `workspace_settings`, `terminal`, `agent`,
  `automation`, or `browser_automation`. For ordinary user requests, forward the
  original bearer credential, Workspace, instance, and exact action to Manager
  `/runtime-access` for per-request validation. Reader receives only a safe read
  projection; every other action requires Manager, Owner, or Platform Admin
- **Instance fence**: validate `runtimeInstanceId`, Runtime lifecycle, and access observed revision. Fail closed when Manager cannot confirm them. KB mount observed revision is checked only by KB-dependent operations and does not block ordinary Runtime APIs
- **Co-located Terminal**: Terminal and the agent both run in the Runtime workload. Losing the Runtime identity fences those processes together
- **Signed drain and pairing**: accept only short-lived Ed25519 assertions from Manager and validate audience, user, Workspace, instance, generation, action, expiration, single-use `jti`, and replay state

The Runtime route classifier consumes the machine-readable route-by-method inventory. Exact sensitive routes and sensitive wildcards take precedence over general mutations and reads. Claude, Codex, and OpenCode raw settings and MCP environment variables or headers map to `workspace_settings`. Unknown or multiply matched routes and Manager timeout or unavailability are rejected before the middleware calls the handler.

Direct or group share changes, group membership changes, account status, Owner changes, and Platform Admin access changes increment generation. Runtime immediately rejects invalidated internal assertions and terminates Terminal, Agent, Automation, Browser, and other execution sessions that are no longer allowed. Runtime never accepts a frontend-provided role or operation list.

For complete component revision convergence, draining, and fencing, see [Execution-Plane Lifecycle and Safety](/architecture/overview/execution-plane).

## Agent Settings-File Modules

Settings-file read/write logic for Claude Code, Codex, and OpenCode is owned by `workspace-runtime/app/modules/claude_code/` for Claude-specific behavior and by the shared Claude/Codex/OpenCode path-resolution modules in `workspace-runtime/app/modules/cli_settings/`. Feature ownership maps to source modules as follows:

| Feature | Source modules |
| --- | --- |
| CLAUDE.md, Settings, Memory attachments, Output Styles, Plugins/Marketplace | `cli_settings/agents_md`, `claude_code/settings`, `claude_code/memory`, `claude_code/output_styles`, `claude_code/plugins` |
| MCP Servers shared by all three agents | `claude_code/mcp`, `cli_settings/mcp` |
| Hooks on Claude-specific paths | `claude_code/hooks` |
| Skills shared by all three agents | `cli_settings/skills` |
| Subagents and Slash Commands, using shared or dedicated routers by agent | `cli_settings/subagents`, `cli_settings/slash_commands`, `claude_code/slash_commands` |
| Codex-specific Config, Rules, Hooks, Apps, Memories, Plugins, Subagents, Prompts, and Managed Requirements | `cli_settings/codex/settings.py::CodexAgentSettings`; the shared path contract is in `cli_settings/user_scope/paths.py` |

For the user-visible file-location matrix, see [Agent Settings File Locations and Scope Mapping](/features/workspace/agent-settings/).

Claude Code Hooks and Slash Commands use the dedicated `claude_code/hooks` and `claude_code/slash_commands` modules. CLAUDE.md, Subagents, and Skills use `cli_settings/agents_md`, `cli_settings/subagents`, and `cli_settings/skills` respectively. `cli_settings/codex` provides Codex-specific resources.

## Technical Architecture

| Component | Technology |
|------|------|
| Web framework | FastAPI |
| Realtime communication | Thread event WebSocket |
| Runtime state | PostgreSQL + SQLAlchemy |
| AI client | Claude Agent SDK, Codex SDK, and OpenCode ACP |
| Version control | GitPython |

## Image Variants

Workspace Runtime supports two base-image flavors:

| Flavor | Use case | Description |
|--------|----------|------|
| `lite` | Default agent Workspace | Includes agent CLIs, Python, Node.js, Git, Docker CLI, and common shell tools; suitable for the platform's default Workspace |
| `java` | Workspace requiring Java/Maven | Based on `lite` with Eclipse Temurin JDK 21 and Apache Maven 3.9.x added |

`base-images/lite` includes the basic tools required by the platform:

- Shell and build tools: `bash`, `build-essential`, `make`, `pkg-config`
- Version-control and file tools: `git`, `git-lfs`, `ripgrep`, `fd`, `rsync`
- Language and package foundations: Python 3, Node.js, `pnpm`, `uv`
- System tools: `curl`, `wget`, `jq`, `sudo`, `openssh-client`

`base-images/lite` does not include a Java runtime/JDK, a Go compiler, or `/usr/local/go`. Use the `java` flavor (`base-images/java21`) for Java development.

`terminal-service` is a Go binary, but the Go toolchain is not included in the runtime image. `workspace-runtime/Dockerfile` uses the Go builder stage configured by `docker-bake.hcl` to compile the binary and copies `/opt/terminal-service/bin/terminal-service` into the `development`, `production`, and `kubernetes` images.

Flavor and deployment target are independent dimensions. A standalone Docker deployment uses the `development`/`production` target. Kubernetes and OCP require the additional `kubernetes` target and `${RELEASE_TAG}-kubernetes` tag. That target installs dependencies at build time, starts with a numeric non-root default user, supports an arbitrary UID injected by the platform and a read-only root filesystem, and does not start `sshd` or mount a Docker socket.

Build the `lite` flavor by itself:

```bash
make build-runtime-base
make build-workspace-runtime
```

The root Bake targets build both `lite` and `java`:

```bash
docker buildx bake --load \
  runtime-base-lite runtime-base-java \
  workspace-runtime-lite workspace-runtime-java
```

Versions of Python, Node.js, npm, pnpm, uv, Claude Code, Codex, OpenCode, and Playwright CLI are defined only in the root `docker-bake.hcl`. Runtime Dockerfiles provide no numeric version defaults. For complete ownership boundaries, see [Docker Deployment Version and Dependency Ownership](/installation/docker#version-and-dependency-ownership).

## HOME and Persistence Contract

Runtime directly persists the standard user HOME; it does not create a second persistence root:

| Deployment mode | HOME | Persistence source |
| --- | --- | --- |
| Docker | `/home/developer` | Direct bind mount of `HOST_RUNTIME_HOME_DIR/<workspace-id>` |
| Kubernetes | `/home/developer` | Direct mount of `workspace-runtime-home-pvc-<workspace-id>` |

The complete HOME preserves Claude, Codex, and OpenCode login and settings, XDG data/state, Maven `${HOME}/.m2`, and user-installed tools. Standard derived paths are:

| Purpose | Path |
| --- | --- |
| Codex | `${HOME}/.codex` |
| XDG config | `${HOME}/.config` |
| XDG data | `${HOME}/.local/share` |
| XDG state | `${HOME}/.local/state` |
| Marketplace operation journal | `${HOME}/.local/state/aileron/marketplace-operations` |

`${HOME}/.codex/tmp` is the process-temporary exception. Docker uses tmpfs, and
Kubernetes uses a 16 MiB memory-backed `emptyDir`; both mount the `tmp` layer,
not `tmp/arg0`. Codex can therefore create the `arg0` helper directory and
adjust it for the current Runtime UID, while all other `${HOME}/.codex` state
remains persisted.

Image-provided executables do not write to HOME. uv, Node.js, npm, pnpm, and Claude Code are on system paths; Codex and Playwright CLI are under `/opt/aileron/npm`; OpenCode is under `/opt/aileron/bin`. A fresh empty HOME, Docker container rebuild, or Kubernetes Pod rebuild therefore does not hide tools built into the image.

## Directory Structure

Workspace Runtime uses a vertical domain-module structure. Each module owns its
domain, while responsibilities named `services` or `models` belong inside their
owning domain. See
[Backend Domain Module Architecture](/architecture/backend/) and
[Python Module and Filename Rules](/reference/python-module-naming) for the
directory template, seams, interfaces, and test rules.

For the owning modules and no-bypass rules of Thread lifecycle, Codex Agent
Settings, the Workspace File/Version Control operation seam, and the User Copy
typed contract, see
[Backend Deep Modules and Cross-Execution-Plane Contracts](/architecture/backend/).
For Version Control targets, lock scopes, and the Repository Setup interface, see
[Shared Version Control and Repository Setup](/architecture/overview/version-control).

## Environment Variables

| Variable | Default | Description |
|--------|--------|------|
| `AILERON_WORKSPACE_ID` | Required | Workspace identifier |
| `AILERON_WORKSPACE_PATH` | Required | Workspace path |
| `AILERON_RUNTIME_STATE_DATABASE_URL_FILE` | Required | Read-only Secret file containing the current Runtime instance's Workspace-scoped PostgreSQL URL |
| `AILERON_RUNTIME_CONTROL_TOKEN_FILE` | Required | Read-only Secret file containing the current Runtime instance's Manager control token |
| `HOME` | `/home/developer` | Standard user HOME directly mounted and fully persisted by Docker and Kubernetes |
| `CODEX_HOME` | `${HOME}/.codex` | Codex configuration, login, and session directory |
| `XDG_CONFIG_HOME` | `${HOME}/.config` | Standard configuration directory for OpenCode and other tools |
| `XDG_DATA_HOME` | `${HOME}/.local/share` | Standard data directory for OpenCode and other tools |
| `XDG_STATE_HOME` | `${HOME}/.local/state` | Root for Runtime bootstrap and application state |
| `MARKETPLACE_OPERATION_JOURNAL_DIR` | `${XDG_STATE_HOME}/aileron/marketplace-operations` | Marketplace operation journal, provider mutation gate, and user-copy transactional recovery directory |
| `AILERON_MANAGER_INTERNAL_URL` | Required | Internal Workspace Manager Service URL |
| `AILERON_PLATFORM_PUBLIC_ORIGIN` | Required | Sole exact Platform Public Origin |
| `AILERON_RUNTIME_INSTANCE_ID` | — | UUID of the current execution-plane generation |
| `AILERON_RUNTIME_ACCESS_REVISION` | — | Runtime access revision applied by this Runtime |
| `AILERON_KB_MOUNT_REVISION` | — | KB mount revision applied by this Runtime |
| `MANAGER_ACCESS_TIMEOUT_SECONDS` | `5` | Timeout for Runtime action validation with Manager |
| `AILERON_RUNTIME_ASSERTION_PUBLIC_KEY_SET_FILE` | Required | Public JWKS file for Manager assertions |
| `AILERON_RUNTIME_ASSERTION_ISSUER` | Required | Expected assertion issuer |

Browser, Canvas, and worktree platform fields use the same `AILERON_*` namespace. Every Secret is delivered through an absolute read-only file path, and Workspace-user environments may not use the `AILERON_*` prefix.

This directory stores only the operation journal for provider mutations and transactional recovery data for user-copy; it is not installation state. After a successful operation, Runtime retains no installation, ownership, provenance, baseline, drift, reconciliation, uninstall, or cleanup lifecycle.

:::note Agent Credentials
API keys, tokens, and login state required by Claude Code, Codex, and OpenCode should be injected dynamically through frontend settings pages. They must not be hardcoded in container environment variables.
:::

## WebSocket Events

The Thread WebSocket does not put a token in the URL. A browser uses the same subprotocol mechanism as Terminal, sending `aileron-thread-v1` and `bearer.<base64url(token)>`. Runtime selects and echoes only the application protocol, never the credential protocol, then validates `runtime_read` using the restored Bearer token. A non-browser client may instead send `Authorization: Bearer <token>` directly during the upgrade. Query tokens, simultaneous use of both credential forms, malformed credentials, and internal tokens all fail closed. For endpoint and close-code semantics, see [Runtime API](/api/runtime-api#websocket).

## Local Development

```bash
docker buildx bake --load local
docker compose up --remove-orphans --no-build -d
```

The root Compose stack starts only the control plane. After sign-in, create or start a Workspace through Manager; Manager then creates the corresponding Runtime generation. Docker development mode mounts `./workspace-runtime` at `/workspace-runtime` inside the dynamic Runtime, so the reload mechanism normally reflects source changes.

A dynamic Runtime is not a Compose service. Do not run `docker compose restart workspace-runtime`. Use Manager's Runtime component restart to replace only Runtime/Terminal; Browser and Canvas use their own component restarts. Stop preserves the working directory and persistent data; only delete removes them.

When Manager creates a Workspace Runtime container, it always uses the startup script from the image:

```yaml
command: "/start_services.sh"
working_dir: "/workspace-runtime"
```

Manager generates or installs each Workspace's custom initialization script in its data directory and mounts it into the current Runtime generation. The root Compose stack does not start a fixed default Runtime.

## Testing

```bash
docker buildx bake --load workspace-runtime-lite

docker compose -f workspace-runtime/docker-compose.test.yml \
  run --rm workspace-runtime-test \
  bash -lc 'uv sync --all-extras && uv run pytest tests -v'

docker compose -f workspace-runtime/docker-compose.test.yml \
  run --rm workspace-runtime-test \
  bash -lc 'uv sync --all-extras && \
    uv run ruff check app tests && \
    uv run black --check app tests && \
    uv run mypy app && \
    uv run vulture'
```

## Observability

Runtime exposes `GET /health` for service health and emits structured application logs for
startup, Agent, Automation, and API failures. Resource statistics are produced by
`ResourceTelemetryReporter` as low-sensitivity activity and capacity observations. This is not a
file-monitoring event stream and it does not send prompts, content, filenames, or paths. Observe
CPU, memory, disk, network I/O, and container or Pod resources through the deployment platform.
For the complete Reporter, outbox, Manager ingestion, deduplication, and privacy contract, see
[Platform Resources and Runtime Telemetry Architecture](/architecture/overview/platform-resource-observability).

## API Endpoints

| Endpoint | Description |
|------|------|
| `GET /health` | Health check |
| `GET /api/v1/files/*` | File management |
| `GET /api/v1/workspaces/{workspace_id}/claude-code/settings` | Claude Code settings |
| `PUT /api/v1/workspaces/{workspace_id}/claude-code/settings` | Update Claude Code settings |
| `GET /api/v1/threads` | List AI Chat threads |
| `POST /api/v1/threads/draft` | Create a draft thread |
| `POST /api/v1/threads/{thread_id}/submit` | Submit the thread and start the agent |
| `POST /api/v1/threads/{thread_id}/messages` | Append a message |
| `POST /api/v1/threads/{thread_id}/questions/{message_id}/answer` | Answer an interactive question |
| `WS /api/v1/threads/events` | Thread events WebSocket |
| `GET /api/v1/workspaces/{workspace_id}/version-control/status` | Git status |
| `GET /api/v1/workspaces/{workspace_id}/version-control/commits` | Git commits |

## Capacity probing and reporting

`CapacityProbe` measures only the Workspace project root and `/home/developer`, does not follow
symlinks, and excludes `/knowledge/<alias>` from Workspace Project Data and Runtime HOME.
`ResourceTelemetryReporter` manages observations at startup, every 15 minutes, after delayed probes
following file mutations, and during shutdown drain. It writes events to a durable outbox before
sending at-least-once batches to Manager:

```text
POST /api/v1/internal/workspaces/{workspace_id}/resource-telemetry/batches
```

The probe has a bounded timeout and a non-overlap lock. Probe, outbox, or transport failures retain
retry data and record telemetry metrics without blocking File, Git, Thread, Automation, or other
Runtime operations. For the cross-plane flow and payload fields, see
[Platform Resources and Runtime Telemetry Architecture](/architecture/overview/platform-resource-observability).
