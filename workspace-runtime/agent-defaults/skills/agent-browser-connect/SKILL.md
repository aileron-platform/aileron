---
name: agent-browser-connect
description: "How to connect agent-browser CLI to the workspace-browser container via CDP (Chrome DevTools Protocol). Use this skill whenever you need to establish a browser connection before running browser commands — including when the user mentions CDP, workspace-browser, browser automation setup, cdp-proxy, connecting to a remote Chromium instance, or when a browser command fails because no connection exists. Always use this skill first before any agent-browser operation in a workspace environment."
---

# Connecting agent-browser to workspace-browser

This skill covers establishing a CDP connection between the `agent-browser` CLI (running in workspace-runtime) and the Chromium browser (running in workspace-browser). Once connected, browser operation commands can be issued — but those commands are covered by the `agent-browser` skill.

## Architecture

```
workspace-runtime                          workspace-browser
┌────────────────────┐                    ┌──────────────────────────┐
│  agent-browser CLI │ ── CDP connect ──→ │  cdp-proxy (:9223)       │
│  (Rust daemon)     │                    │    ↓                     │
│                    │ ← WebSocket ─────→ │  Chromium (:9222 internal)│
└────────────────────┘                    │    ↓                     │
                                          │  neko WebRTC (:6080)     │
                                          └──────────────────────────┘
```

- **agent-browser** runs as a daemon process. It starts automatically on the first command and reuses the connection for subsequent commands.
- **cdp-proxy** listens on port 9223 in workspace-browser, forwarding to Chromium's internal port 9222. It rewrites WebSocket URLs based on the request `Host` header so cross-container connections work correctly.
- Containers communicate over a shared Docker network using container names as hostnames.

## How to Connect

The container name varies by environment. **Never hardcode a container name.** Always resolve it from the `WORKSPACE_ID` environment variable.

The browser container naming convention is `workspace-browser-{WORKSPACE_ID}`, and the CDP proxy listens on port 9223.

### Connect command

```bash
agent-browser connect "http://workspace-browser-${WORKSPACE_ID}:9223"
```

Before connecting, you can verify reachability:

```bash
curl -s "http://workspace-browser-${WORKSPACE_ID}:9223/json/version"
```

> **Note:** In production deployments, workspace-manager may also inject `BROWSER_CDP_URL` with the full CDP URL. If set, use it directly: `agent-browser connect "$BROWSER_CDP_URL"`

### Using BrowserContainerDiscovery (Python)

The workspace-runtime codebase provides `BrowserContainerDiscovery` in `app/utils/container_discovery.py` for programmatic access. It reads `WORKSPACE_ID` (and optional `BROWSER_CDP_URL`) to resolve the connection target:

```python
from app.utils.container_discovery import BrowserContainerDiscovery

# Get the CDP endpoint URL (reads env vars automatically)
cdp_url = BrowserContainerDiscovery.get_cdp_endpoint()
# → e.g. "http://workspace-browser-abc123:9223"

# Check if the browser container is reachable
available = BrowserContainerDiscovery.is_browser_available()

# Get full connection info
info = BrowserContainerDiscovery.get_browser_info()
# → BrowserContainerInfo(
#     container_name="workspace-browser-abc123",
#     webrtc_internal_url="http://workspace-browser-abc123:6080",
#     cdp_url="http://workspace-browser-abc123:9223"
#   )
```

To connect from Python:

```python
import asyncio

async def browser_connect():
    cdp_url = BrowserContainerDiscovery.get_cdp_endpoint()
    proc = await asyncio.create_subprocess_exec(
        "agent-browser", "connect", cdp_url,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    await proc.communicate()
```

## Verifying the Connection

After connecting, verify the session is active:

```bash
# Confirms daemon is connected — shows the active CDP WebSocket URL
agent-browser get cdp-url

# Confirms the browser is reachable — shows the current page URL
agent-browser get url
```

## Disconnecting

```bash
# Close the current session and stop the daemon
agent-browser close

# Close all sessions
agent-browser close --all
```

After `close`, any subsequent command requires a fresh `connect`.

## Prerequisites

| Item | Details |
|------|---------|
| agent-browser CLI | Pre-installed via `npm install -g agent-browser` in the workspace-runtime Dockerfile |
| workspace-browser container | Must be running and healthy on the same Docker network |
| CDP proxy (port 9223) | Must be accessible from workspace-runtime |

## Environment Variables

| Variable | Purpose |
|----------|---------|
| `WORKSPACE_ID` | **Required.** Determines the browser container name: `workspace-browser-{WORKSPACE_ID}` |
| `BROWSER_CDP_URL` | Optional. Full CDP URL injected by workspace-manager in production; if set, use directly |
| `AGENT_BROWSER_SESSION` | Name of the session to use |
| `AGENT_BROWSER_DEFAULT_TIMEOUT` | Default timeout for operations (ms) |
| `AGENT_BROWSER_IDLE_TIMEOUT_MS` | How long the daemon stays alive when idle |

## Troubleshooting

If the connection fails, check these in order:

1. **Check WORKSPACE_ID** — Run `echo $WORKSPACE_ID` to confirm it is set. The target container name is `workspace-browser-{WORKSPACE_ID}`.
2. **Is workspace-browser running?** — Verify the container is up and healthy (`docker ps` or check the orchestrator).
3. **Network reachability** — Confirm both containers share the same Docker network. Run `curl -s http://<resolved-container-name>:9223/json/version` from workspace-runtime; you should get a JSON response with `webSocketDebuggerUrl`.
4. **Port 9223** — The cdp-proxy must be listening. If the response is empty or refused, the proxy may not have started yet.
5. **Daemon state** — If agent-browser seems stuck, run `agent-browser close` and reconnect.
