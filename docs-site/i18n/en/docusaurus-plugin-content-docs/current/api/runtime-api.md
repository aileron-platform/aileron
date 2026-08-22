---
title: Runtime API
---

# Workspace Runtime API

The Workspace Runtime API provides AI Chat threads, agent execution, file operations, and real-time events inside each Workspace. Claude Code, Codex, and OpenCode all use the same multi-agent Runtime interface.

## Interactive Documentation

- **Swagger UI**: `/workspaces/{workspaceId}/runtime/docs`
- **ReDoc**: `/workspaces/{workspaceId}/runtime/redoc`

:::note
Each Workspace has an independent Runtime instance and revision. Start the Workspace through Manager, then use `/workspaces/{workspaceId}/runtime/...` on the current Platform Public Origin. Browsers receive no Runtime host or port.
:::

## Base URL

```text
/workspaces/{workspaceId}/runtime
```

## Runtime Access Gate

Except for exact public health and signed internal routes, Runtime accepts only a Manager-signed
Workspace Execution Access Grant with audience `workspace-runtime`. Runtime locally uses public JWKS
to verify signature, the fixed 60-second lifetime, token kind, explicit action, `workspaceId`,
`runtimeInstanceId`, and `runtimeAccessRevision`. Any mismatch fails closed. A general Runtime action
is not globally gated by the Knowledge Base mount revision; only `/knowledge` and mount-management
operations explicitly check mount state.

| Path or Method | Action |
| --- | --- |
| General `GET` or `HEAD` | `runtime_read` |
| General write method | `runtime_write` |
| Claude, Codex, or OpenCode raw settings and MCP environment variables or headers | `workspace_settings` |
| Thread REST reads and mutations, plus agent sessions | `agent` |
| Thread events WebSocket handshake | `runtime_read` |
| Automation | `automation` |
| Client Browser Relay | `browser_automation` |

Each action maps to a central Workspace OperationId. Reader can reach only a safe read projection. `runtime_write`, `workspace_settings`, `terminal`, `agent`, `automation`, and `browser_automation` require Manager, Owner, or Platform Admin. See [Users, Groups, and Permissions](/features/platform/permissions-and-roles) for the complete rules and `403` or `423` semantics.

Runtime classifies actions through a closed route-by-method inventory. Exact sensitive routes and sensitive wildcards take precedence over general mutation and read routes. An unknown or multiply matched family, Manager timeout, or failed verification is denied before Runtime calls an upstream handler. A Runtime URL is location information, not an authorization credential, and every request is verified again.

Frontend first uses its opaque Manager session to request a Grant from
`POST /api/v1/workspaces/{workspaceId}/execution-grants`. Manager authorizes every action before
issuing it. Runtime never receives an external OIDC token and does not call Manager per request. An
Execution Grant is reusable during its lifetime. Manager-to-Runtime internal commands and pairing
use a different token kind, audience, verifier, and one-time replay state. Neither interface accepts
a frontend-provided role as authorization.

Direct or group share changes, group membership changes, account disablement, Owner reassignment,
Platform Admin demotion, and Public-to-Private KB changes increment the runtime access revision. An
old Grant fails its revision fence. A cached Runtime URL or an unexpired Grant with an old revision
cannot bypass verification.

## Main Endpoints

### Health Check

```http
GET /health
```

### File Management

| Method | Path | Description |
|--------|------|------|
| `GET` | `/api/v1/files/tree` | Get the directory tree |
| `GET` | `/api/v1/files/tree/children` | Lazily load child nodes |
| `GET` | `/api/v1/files/search` | Search files |
| `GET` / `PUT` | `/api/v1/files/content` | Read or write one file |
| `POST` | `/api/v1/files/content/batch` | Write multiple files in one request |
| `GET` | `/api/v1/files/download` | Download a file |
| `POST` / `DELETE` | `/api/v1/files` | Create or delete a file or directory |
| `POST` | `/api/v1/files/upload` | Upload files |
| `POST` | `/api/v1/files/copy` | Copy a file or directory |
| `POST` | `/api/v1/files/move` | Move or rename an entry |
| `POST` | `/api/v1/files/batch-delete` | Delete multiple entries |
| `POST` / `GET` | `/api/v1/files/archive`, `/api/v1/files/archive/{operation_id}` | Start an archive operation and query its progress |
| `GET` | `/api/v1/files/archive/{operation_id}/download` | Download a completed ZIP archive |
| `POST` / `GET` | `/api/v1/files/extract`, `/api/v1/files/extract/{operation_id}` | Start an extraction operation and query its progress |
| `GET` | `/api/v1/files/history` | Get file-change history |
| `POST` | `/api/v1/files/history/{entry_id}/restore` | Restore a historical version |

### Agent and CLI Settings

These APIs manage agent settings inside a Workspace, including rules, hooks, MCP servers, skills, slash commands, and subagents for Claude Code, Codex, and OpenCode.

| Method | Path | Description |
|--------|------|------|
| `GET` | `/api/v1/workspaces/{workspace_id}/claude-code/settings` | Get Claude Code settings |
| `PUT` | `/api/v1/workspaces/{workspace_id}/claude-code/settings` | Update Claude Code settings |
| `GET` | `/api/v1/workspaces/{workspace_id}/codex` | Get supported Codex setting fields |
| `GET` / `PUT` | `/api/v1/workspaces/{workspace_id}/codex/config` | Get or update Codex config |
| `GET` | `/api/v1/workspaces/{workspace_id}/{tool}/mcp-servers` | Get MCP server settings |
| `PUT` | `/api/v1/workspaces/{workspace_id}/{tool}/mcp-servers/{scope}/{server_name}` | Update an MCP server |
| `GET` | `/api/v1/workspaces/{workspace_id}/{tool}/skills/tree` | Get the skills file tree |
| `GET` | `/api/v1/workspaces/{workspace_id}/{tool}/slash-commands` | List slash commands |
| `GET` | `/api/v1/workspaces/{workspace_id}/cli-settings/{tool}/prompt-invocations` | Get an invocation-ready Commands and Skills catalog |

`tool` is `claude-code`, `codex`, or `opencode`. Supported scopes and writable resources vary
by provider; use the current Runtime OpenAPI document for complete request and response schemas.

The prompt invocation catalog is the shared read contract for AI Chat and Automation. Runtime
aggregates Commands and Skills for the selected tool and returns formatted `invocation` values,
stable item IDs, available scopes, a content revision, and source errors. A partial source failure
returns `200` with `completeness: degraded`; a failure of every source returns `503`. Runtime
revalidates sources for every request instead of reusing a cached source inventory. Prompt
Invocation Pickers reload the catalog whenever they open, and Picker consumers use the
Runtime-owned `invocation` without formatting it themselves.

Raw settings, MCP environment variables, HTTP headers, API keys, and tokens are sensitive settings. Their reads and writes always use the `workspace_settings` action; general `runtime_read` or `agent` authorization cannot expose those values.

### AI Chat Threads

Thread metadata and history are separate. History uses only the Message Item timeline. See [AI Chat Frontend and Backend Architecture](/architecture/overview/ai-chat#reading-and-pagination) for the complete mechanism.

| Method | Path | Description |
|--------|------|------|
| `GET` | `/api/v1/threads` | List threads |
| `POST` | `/api/v1/threads/draft` | Create a draft thread |
| `GET` | `/api/v1/threads/{thread_id}` | Get thread details |
| `PATCH` | `/api/v1/threads/{thread_id}/draft` | Update a draft |
| `POST` | `/api/v1/threads/{thread_id}/submit` | Submit a draft and start an agent |
| `POST` | `/api/v1/threads/{thread_id}/messages` | Append a message |
| `GET` | `/api/v1/threads/{thread_id}/timeline` | Read Message Item history with `beforeSequence` |
| `POST` | `/api/v1/threads/{thread_id}/timeline/items/batch-get` | Refresh up to 200 known timeline items |
| `GET` | `/api/v1/threads/{thread_id}/messages/{message_id}/tool-result` | Load a complete tool result on demand |
| `POST` | `/api/v1/threads/{thread_id}/questions/{message_id}/answer` | Answer an interactive question |
| `POST` | `/api/v1/threads/{thread_id}/stop` | Stop the current Turn; starts the next queued message if one is waiting, otherwise the thread ends as canceled |
| `POST` | `/api/v1/threads/{thread_id}/retry` | Retry a thread |
| `POST` | `/api/v1/threads/{thread_id}/archive` | Archive a thread |
| `GET` | `/api/v1/threads/{thread_id}/attachments` | List attachments |
| `POST` | `/api/v1/threads/{thread_id}/attachments` | Upload an attachment |

### Version Control (Git)

| Method | Path | Description |
|--------|------|------|
| `GET` | `/api/v1/workspaces/{id}/version-control/status` | Get Git status |
| `GET` | `/api/v1/workspaces/{id}/version-control/changes` | Get Git changes |
| `POST` | `/api/v1/workspaces/{id}/version-control/changes/numstat` | Query change numstat |
| `GET` | `/api/v1/workspaces/{id}/version-control/commits` | List Git commits |
| `GET` | `/api/v1/workspaces/{id}/version-control/commits/{commit_id}` | Get commit details |
| `GET` | `/api/v1/workspaces/{id}/version-control/commits/{commit_id}/files` | List commit files |
| `GET` | `/api/v1/workspaces/{id}/version-control/diff` | Get a Git diff |
| `GET` | `/api/v1/workspaces/{id}/version-control/blob` | Read a Git blob |
| `POST` | `/api/v1/workspaces/{id}/version-control/stage` | Stage changes |
| `POST` | `/api/v1/workspaces/{id}/version-control/unstage` | Unstage changes |
| `POST` | `/api/v1/workspaces/{id}/version-control/discard` | Discard changes |
| `POST` | `/api/v1/workspaces/{id}/version-control/commit` | Create a commit |
| `POST` | `/api/v1/workspaces/{id}/version-control/push` | Push |
| `POST` | `/api/v1/workspaces/{id}/version-control/pull` | Pull |
| `POST` | `/api/v1/workspaces/{id}/version-control/fetch` | Fetch |
| `GET` | `/api/v1/workspaces/{id}/version-control/branches` | List branches |
| `POST` | `/api/v1/workspaces/{id}/version-control/branches/{branch_name}/checkout` | Switch to or create a branch |
| `GET` | `/api/v1/workspaces/{id}/version-control/operation-status` | Get the current Git operation state |
| `POST` | `/api/v1/workspaces/{id}/version-control/force-unlock` | Force-unlock the current Git operation |

### WebSocket

| Endpoint | Description |
|------|------|
| `WS /api/v1/threads/events` | Thread invalidation and event notifications |

#### Thread WebSocket Connection

Browsers use the same WebSocket subprotocol credential as Terminal and never put the token in the URL:

```javascript
const encodedToken = btoa(token)
  .replaceAll('+', '-')
  .replaceAll('/', '_')
  .replace(/=+$/, '');
const threadEventsUrl = new URL(
  `/workspaces/${workspaceId}/runtime/api/v1/threads/events`,
  window.location.origin,
);
threadEventsUrl.protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
const ws = new WebSocket(
  threadEventsUrl,
  ['aileron-thread-v1', `bearer.${encodedToken}`],
);
```

Browser clients compose only this fixed relative path from the current page Origin. They receive no Runtime host, port, or upstream URL.

Runtime selects and echoes only the `aileron-thread-v1` application protocol. It never echoes the `bearer.<base64url(token)>` credential protocol. Non-browser callers may instead set `Authorization: Bearer <token>` directly on the upgrade request. A request must use exactly one credential mechanism.

Runtime validates the token, checks `runtime_read` against the current Workspace and instance, and accepts the connection only after both pass. A `token` or `access_token` query parameter, internal token, simultaneous header and subprotocol credentials, missing application protocol, or duplicate or malformed credential fails closed with `4401`. Insufficient permission uses `4403`, unsettled Runtime access or a lifecycle lock uses `4423`, and an unavailable Manager authorization check uses `4503`.

## Canvas

Canvas endpoints are scoped to a Workspace under `/api/v1/workspaces/{workspace_id}/canvas/*`. See [Canvas Protocol](/architecture/overview/canvas/protocol) for the manifest contract and lifecycle.

| Method | Path | Description |
|--------|------|------|
| `GET` | `/api/v1/workspaces/{workspace_id}/canvas/detect` | Detect the Canvas project type |
| `GET` | `/api/v1/workspaces/{workspace_id}/canvas/routes` | List available routes |
| `GET` | `/api/v1/workspaces/{workspace_id}/canvas/health` | Get Canvas dev-server health |
| `GET` | `/api/v1/workspaces/{workspace_id}/canvas/logs` | Get Canvas runtime logs |
| `POST` | `/api/v1/workspaces/{workspace_id}/canvas/sync` | Synchronize and start Canvas |
| `POST` | `/api/v1/workspaces/{workspace_id}/canvas/reset` | Reset Canvas state |
| `GET` / `POST` | `/api/v1/workspaces/{workspace_id}/canvas/review-notes` | List or create a review note |
| `PATCH` | `/api/v1/workspaces/{workspace_id}/canvas/review-notes/{note_id}/status` | Update a review-note status |
| `POST` | `/api/v1/workspaces/{workspace_id}/canvas/review-notes/{note_id}/replies` | Reply to a review note |
| `DELETE` | `/api/v1/workspaces/{workspace_id}/canvas/review-notes/{note_id}` | Delete a review note |
| `DELETE` | `/api/v1/workspaces/{workspace_id}/canvas/manifest` | Disable the Canvas manifest |

## Third-Party Tool Integrations

| Method | Path | Description |
|--------|------|------|
| `POST` | `/api/v1/audio/transcriptions` | Transcribe audio to text |

## Client Browser Relay

The Client Browser Relay proxies CDP (Chrome DevTools Protocol) connections between the browser extension and Runtime. See [Execution-Plane Lifecycle and Safety — Browser Extension Pairing Safety](/architecture/overview/execution-plane#browser-extension-pairing-safety) for authorization and pairing.

| Method | Path | Description |
|--------|------|------|
| `GET` | `/api/v1/client-browser-relay/health` | Health check |
| `GET` | `/api/v1/client-browser-relay` | Query relay status |
| `GET` / `POST` | `/api/v1/client-browser-relay/pages` | List or create relayable pages |
| `DELETE` | `/api/v1/client-browser-relay/pages/{name}` | Delete a named page |
| `WS` | `/api/v1/client-browser-relay/cdp`, `/api/v1/client-browser-relay/cdp/{client_id}` | Connect a CDP client |
| `WS` | `/api/v1/client-browser-relay/extension` | Connect the browser extension |

<!-- authorization-contract:runtime:start -->
<!-- generated by docs-site/scripts/check-authorization-contract.mjs -->
| Route template | Methods | Action | Priority | Sensitive | Description |
| --- | --- | --- | --- | --- | --- |
| `/api/v1/workspaces/{workspace_id}/claude-code/mcp-servers/{scope}/{server_name}/export` | `GET` | `workspace_settings` | `4043` | Yes | `GET` `/api/v1/workspaces/{workspace_id}/claude-code/mcp-servers/{scope}/{server_name}/export` maps to `workspace_settings`; sensitive: Yes. |
| `/api/v1/workspaces/{workspace_id}/claude-code/mcp-servers/{scope}/{server_name}/toggle` | `PATCH` | `workspace_settings` | `4043` | Yes | `PATCH` `/api/v1/workspaces/{workspace_id}/claude-code/mcp-servers/{scope}/{server_name}/toggle` maps to `workspace_settings`; sensitive: Yes. |
| `/api/v1/workspaces/{workspace_id}/agent-settings/cache/refresh` | `POST` | `workspace_settings` | `4041` | Yes | `POST` `/api/v1/workspaces/{workspace_id}/agent-settings/cache/refresh` maps to `workspace_settings`; sensitive: Yes. |
| `/api/v1/workspaces/{workspace_id}/opencode/mcp-servers/{scope}/{server_name}/export` | `GET` | `workspace_settings` | `4040` | Yes | `GET` `/api/v1/workspaces/{workspace_id}/opencode/mcp-servers/{scope}/{server_name}/export` maps to `workspace_settings`; sensitive: Yes. |
| `/api/v1/workspaces/{workspace_id}/opencode/mcp-servers/{scope}/{server_name}/toggle` | `PATCH` | `workspace_settings` | `4040` | Yes | `PATCH` `/api/v1/workspaces/{workspace_id}/opencode/mcp-servers/{scope}/{server_name}/toggle` maps to `workspace_settings`; sensitive: Yes. |
| `/api/v1/workspaces/{workspace_id}/claude-code/mcp-servers` | `GET` | `workspace_settings` | `4037` | Yes | `GET` `/api/v1/workspaces/{workspace_id}/claude-code/mcp-servers` maps to `workspace_settings`; sensitive: Yes. |
| `/api/v1/workspaces/{workspace_id}/claude-code/mcp-servers/{scope}` | `GET`, `POST` | `workspace_settings` | `4037` | Yes | `GET`, `POST` `/api/v1/workspaces/{workspace_id}/claude-code/mcp-servers/{scope}` maps to `workspace_settings`; sensitive: Yes. |
| `/api/v1/workspaces/{workspace_id}/claude-code/mcp-servers/{scope}/{server_name}` | `DELETE`, `GET`, `PUT` | `workspace_settings` | `4037` | Yes | `DELETE`, `GET`, `PUT` `/api/v1/workspaces/{workspace_id}/claude-code/mcp-servers/{scope}/{server_name}` maps to `workspace_settings`; sensitive: Yes. |
| `/api/v1/workspaces/{workspace_id}/claude-code/settings/raw` | `GET`, `PUT` | `workspace_settings` | `4037` | Yes | `GET`, `PUT` `/api/v1/workspaces/{workspace_id}/claude-code/settings/raw` maps to `workspace_settings`; sensitive: Yes. |
| `/api/v1/workspaces/{workspace_id}/codex/mcp-servers/{scope}/{server_name}/export` | `GET` | `workspace_settings` | `4037` | Yes | `GET` `/api/v1/workspaces/{workspace_id}/codex/mcp-servers/{scope}/{server_name}/export` maps to `workspace_settings`; sensitive: Yes. |
| `/api/v1/workspaces/{workspace_id}/codex/mcp-servers/{scope}/{server_name}/toggle` | `PATCH` | `workspace_settings` | `4037` | Yes | `PATCH` `/api/v1/workspaces/{workspace_id}/codex/mcp-servers/{scope}/{server_name}/toggle` maps to `workspace_settings`; sensitive: Yes. |
| `/api/v1/workspaces/{workspace_id}/claude-code/mcp-import` | `POST` | `workspace_settings` | `4036` | Yes | `POST` `/api/v1/workspaces/{workspace_id}/claude-code/mcp-import` maps to `workspace_settings`; sensitive: Yes. |
| `/api/v1/workspaces/{workspace_id}/claude-code/settings` | `GET`, `PUT` | `workspace_settings` | `4034` | Yes | `GET`, `PUT` `/api/v1/workspaces/{workspace_id}/claude-code/settings` maps to `workspace_settings`; sensitive: Yes. |
| `/api/v1/workspaces/{workspace_id}/opencode/mcp-servers` | `GET` | `workspace_settings` | `4034` | Yes | `GET` `/api/v1/workspaces/{workspace_id}/opencode/mcp-servers` maps to `workspace_settings`; sensitive: Yes. |
| `/api/v1/workspaces/{workspace_id}/opencode/mcp-servers/{scope}` | `GET`, `POST` | `workspace_settings` | `4034` | Yes | `GET`, `POST` `/api/v1/workspaces/{workspace_id}/opencode/mcp-servers/{scope}` maps to `workspace_settings`; sensitive: Yes. |
| `/api/v1/workspaces/{workspace_id}/opencode/mcp-servers/{scope}/{server_name}` | `DELETE`, `GET`, `PUT` | `workspace_settings` | `4034` | Yes | `DELETE`, `GET`, `PUT` `/api/v1/workspaces/{workspace_id}/opencode/mcp-servers/{scope}/{server_name}` maps to `workspace_settings`; sensitive: Yes. |
| `/api/v1/workspaces/{workspace_id}/opencode/mcp-import` | `POST` | `workspace_settings` | `4033` | Yes | `POST` `/api/v1/workspaces/{workspace_id}/opencode/mcp-import` maps to `workspace_settings`; sensitive: Yes. |
| `/api/v1/workspaces/{workspace_id}/codex/mcp-servers` | `GET` | `workspace_settings` | `4031` | Yes | `GET` `/api/v1/workspaces/{workspace_id}/codex/mcp-servers` maps to `workspace_settings`; sensitive: Yes. |
| `/api/v1/workspaces/{workspace_id}/codex/mcp-servers/{scope}` | `GET`, `POST` | `workspace_settings` | `4031` | Yes | `GET`, `POST` `/api/v1/workspaces/{workspace_id}/codex/mcp-servers/{scope}` maps to `workspace_settings`; sensitive: Yes. |
| `/api/v1/workspaces/{workspace_id}/codex/mcp-servers/{scope}/{server_name}` | `DELETE`, `GET`, `PUT` | `workspace_settings` | `4031` | Yes | `DELETE`, `GET`, `PUT` `/api/v1/workspaces/{workspace_id}/codex/mcp-servers/{scope}/{server_name}` maps to `workspace_settings`; sensitive: Yes. |
| `/api/v1/workspaces/{workspace_id}/codex/mcp-import` | `POST` | `workspace_settings` | `4030` | Yes | `POST` `/api/v1/workspaces/{workspace_id}/codex/mcp-import` maps to `workspace_settings`; sensitive: Yes. |
| `/api/v1/workspaces/{workspace_id}/codex/config` | `GET`, `PUT` | `workspace_settings` | `4026` | Yes | `GET`, `PUT` `/api/v1/workspaces/{workspace_id}/codex/config` maps to `workspace_settings`; sensitive: Yes. |
| `/api/v1/workspaces/{workspace_id}/codex/config/{section}` | `GET`, `PUT` | `workspace_settings` | `4026` | Yes | `GET`, `PUT` `/api/v1/workspaces/{workspace_id}/codex/config/{section}` maps to `workspace_settings`; sensitive: Yes. |
| `/api/v1/workspaces/{workspace_id}/codex/plugins/{plugin_id:path}/mcp-servers/{server_id:path}/policy` | `PATCH` | `workspace_settings` | `3544` | Yes | `PATCH` `/api/v1/workspaces/{workspace_id}/codex/plugins/{plugin_id:path}/mcp-servers/{server_id:path}/policy` maps to `workspace_settings`; sensitive: Yes. |
| `/api/v1/threads/by-automation-execution/{execution_id}` | `GET` | `agent` | `3035` | No | `GET` `/api/v1/threads/by-automation-execution/{execution_id}` maps to `agent`; sensitive: No. |
| `/api/v1/threads/{thread_id}/timeline/items/batch-get` | `POST` | `agent` | `3034` | No | `POST` `/api/v1/threads/{thread_id}/timeline/items/batch-get` maps to `agent`; sensitive: No. |
| `/api/v1/threads/{thread_id}/messages/{message_id}/tool-result` | `GET` | `agent` | `3031` | No | `GET` `/api/v1/threads/{thread_id}/messages/{message_id}/tool-result` maps to `agent`; sensitive: No. |
| `/api/v1/client-browser-relay/pages` | `GET`, `POST` | `browser_automation` | `3030` | No | `GET`, `POST` `/api/v1/client-browser-relay/pages` maps to `browser_automation`; sensitive: No. |
| `/api/v1/client-browser-relay/pages/{name}` | `DELETE` | `browser_automation` | `3030` | No | `DELETE` `/api/v1/client-browser-relay/pages/{name}` maps to `browser_automation`; sensitive: No. |
| `/api/v1/threads/{thread_id}/questions/{message_id}/answer` | `POST` | `agent` | `3027` | No | `POST` `/api/v1/threads/{thread_id}/questions/{message_id}/answer` maps to `agent`; sensitive: No. |
| `/api/v1/threads/{thread_id}/queued-messages/{queued_message_id}` | `DELETE` | `agent` | `3027` | No | `DELETE` `/api/v1/threads/{thread_id}/queued-messages/{queued_message_id}` maps to `agent`; sensitive: No. |
| `/api/v1/client-browser-relay` | `GET` | `browser_automation` | `3025` | No | `GET` `/api/v1/client-browser-relay` maps to `browser_automation`; sensitive: No. |
| `/api/v1/audio/transcriptions` | `POST` | `agent` | `3024` | No | `POST` `/api/v1/audio/transcriptions` maps to `agent`; sensitive: No. |
| `/api/v1/threads/{thread_id}/attachments` | `GET`, `POST` | `agent` | `3023` | No | `GET`, `POST` `/api/v1/threads/{thread_id}/attachments` maps to `agent`; sensitive: No. |
| `/api/v1/threads/{thread_id}/attachments/{attachment_id}` | `DELETE` | `agent` | `3023` | No | `DELETE` `/api/v1/threads/{thread_id}/attachments/{attachment_id}` maps to `agent`; sensitive: No. |
| `/api/v1/threads/{thread_id}/messages` | `POST` | `agent` | `3020` | No | `POST` `/api/v1/threads/{thread_id}/messages` maps to `agent`; sensitive: No. |
| `/api/v1/threads/{thread_id}/timeline` | `GET` | `agent` | `3020` | No | `GET` `/api/v1/threads/{thread_id}/timeline` maps to `agent`; sensitive: No. |
| `/api/v1/threads/{thread_id}/archive` | `POST` | `agent` | `3019` | No | `POST` `/api/v1/threads/{thread_id}/archive` maps to `agent`; sensitive: No. |
| `/api/v1/threads/{thread_id}/submit` | `POST` | `agent` | `3018` | No | `POST` `/api/v1/threads/{thread_id}/submit` maps to `agent`; sensitive: No. |
| `/api/v1/threads/draft` | `POST` | `agent` | `3017` | No | `POST` `/api/v1/threads/draft` maps to `agent`; sensitive: No. |
| `/api/v1/threads/{thread_id}/draft` | `PATCH` | `agent` | `3017` | No | `PATCH` `/api/v1/threads/{thread_id}/draft` maps to `agent`; sensitive: No. |
| `/api/v1/threads/{thread_id}/retry` | `POST` | `agent` | `3017` | No | `POST` `/api/v1/threads/{thread_id}/retry` maps to `agent`; sensitive: No. |
| `/api/v1/threads/{thread_id}/stop` | `POST` | `agent` | `3016` | No | `POST` `/api/v1/threads/{thread_id}/stop` maps to `agent`; sensitive: No. |
| `/api/v1/threads` | `GET` | `agent` | `3012` | No | `GET` `/api/v1/threads` maps to `agent`; sensitive: No. |
| `/api/v1/threads/{thread_id}` | `DELETE`, `GET` | `agent` | `3012` | No | `DELETE`, `GET` `/api/v1/threads/{thread_id}` maps to `agent`; sensitive: No. |
| `/api/v1/workspaces/{workspace_id}/version-control/conflicts/mark-resolved` | `POST` | `runtime_write` | `2052` | No | `POST` `/api/v1/workspaces/{workspace_id}/version-control/conflicts/mark-resolved` maps to `runtime_write`; sensitive: No. |
| `/api/v1/workspaces/{workspace_id}/claude-code/skills/conflicts/preflight` | `POST` | `runtime_write` | `2050` | No | `POST` `/api/v1/workspaces/{workspace_id}/claude-code/skills/conflicts/preflight` maps to `runtime_write`; sensitive: No. |
| `/api/v1/workspaces/{workspace_id}/claude-code/slash-commands/{scope}/content` | `DELETE`, `PUT` | `runtime_write` | `2047` | No | `DELETE`, `PUT` `/api/v1/workspaces/{workspace_id}/claude-code/slash-commands/{scope}/content` maps to `runtime_write`; sensitive: No. |
| `/api/v1/workspaces/{workspace_id}/opencode/skills/conflicts/preflight` | `POST` | `runtime_write` | `2047` | No | `POST` `/api/v1/workspaces/{workspace_id}/opencode/skills/conflicts/preflight` maps to `runtime_write`; sensitive: No. |
| `/api/v1/workspaces/{workspace_id}/version-control/branches/publish` | `POST` | `runtime_write` | `2045` | No | `POST` `/api/v1/workspaces/{workspace_id}/version-control/branches/publish` maps to `runtime_write`; sensitive: No. |
| `/api/v1/workspaces/{workspace_id}/version-control/operation/cancel` | `POST` | `runtime_write` | `2045` | No | `POST` `/api/v1/workspaces/{workspace_id}/version-control/operation/cancel` maps to `runtime_write`; sensitive: No. |
| `/api/v1/workspaces/{workspace_id}/version-control/remote-branches` | `POST` | `runtime_write` | `2045` | No | `POST` `/api/v1/workspaces/{workspace_id}/version-control/remote-branches` maps to `runtime_write`; sensitive: No. |
| `/api/v1/workspaces/{workspace_id}/claude-code/skills/batch-delete` | `POST` | `runtime_write` | `2044` | No | `POST` `/api/v1/workspaces/{workspace_id}/claude-code/skills/batch-delete` maps to `runtime_write`; sensitive: No. |
| `/api/v1/workspaces/{workspace_id}/codex/skills/conflicts/preflight` | `POST` | `runtime_write` | `2044` | No | `POST` `/api/v1/workspaces/{workspace_id}/codex/skills/conflicts/preflight` maps to `runtime_write`; sensitive: No. |
| `/api/v1/workspaces/{workspace_id}/opencode/slash-commands/{scope}/content` | `DELETE`, `PUT` | `runtime_write` | `2044` | No | `DELETE`, `PUT` `/api/v1/workspaces/{workspace_id}/opencode/slash-commands/{scope}/content` maps to `runtime_write`; sensitive: No. |
| `/api/v1/workspaces/{workspace_id}/version-control/branches/create` | `POST` | `runtime_write` | `2044` | No | `POST` `/api/v1/workspaces/{workspace_id}/version-control/branches/create` maps to `runtime_write`; sensitive: No. |
| `/api/v1/workspaces/{workspace_id}/version-control/branches/delete` | `POST` | `runtime_write` | `2044` | No | `POST` `/api/v1/workspaces/{workspace_id}/version-control/branches/delete` maps to `runtime_write`; sensitive: No. |
| `/api/v1/workspaces/{workspace_id}/version-control/branches/rename` | `POST` | `runtime_write` | `2044` | No | `POST` `/api/v1/workspaces/{workspace_id}/version-control/branches/rename` maps to `runtime_write`; sensitive: No. |
| `/api/v1/workspaces/{workspace_id}/version-control/branches/switch` | `POST` | `runtime_write` | `2044` | No | `POST` `/api/v1/workspaces/{workspace_id}/version-control/branches/switch` maps to `runtime_write`; sensitive: No. |
| `/api/v1/workspaces/{workspace_id}/version-control/changes/numstat` | `POST` | `runtime_write` | `2044` | No | `POST` `/api/v1/workspaces/{workspace_id}/version-control/changes/numstat` maps to `runtime_write`; sensitive: No. |
| `/api/v1/workspaces/{workspace_id}/version-control/conflicts/abort` | `POST` | `runtime_write` | `2044` | No | `POST` `/api/v1/workspaces/{workspace_id}/version-control/conflicts/abort` maps to `runtime_write`; sensitive: No. |
| `/api/v1/workspaces/{workspace_id}/version-control/commits/revert` | `POST` | `runtime_write` | `2043` | No | `POST` `/api/v1/workspaces/{workspace_id}/version-control/commits/revert` maps to `runtime_write`; sensitive: No. |
| `/api/v1/workspaces/{workspace_id}/claude-code/subagents/{scope}/content` | `DELETE`, `PUT` | `runtime_write` | `2042` | No | `DELETE`, `PUT` `/api/v1/workspaces/{workspace_id}/claude-code/subagents/{scope}/content` maps to `runtime_write`; sensitive: No. |
| `/api/v1/workspaces/{workspace_id}/version-control/force-unlock` | `POST` | `runtime_write` | `2042` | No | `POST` `/api/v1/workspaces/{workspace_id}/version-control/force-unlock` maps to `runtime_write`; sensitive: No. |
| `/api/v1/workspaces/{workspace_id}/codex/slash-commands/{scope}/content` | `DELETE`, `PUT` | `runtime_write` | `2041` | No | `DELETE`, `PUT` `/api/v1/workspaces/{workspace_id}/codex/slash-commands/{scope}/content` maps to `runtime_write`; sensitive: No. |
| `/api/v1/workspaces/{workspace_id}/opencode/skills/batch-delete` | `POST` | `runtime_write` | `2041` | No | `POST` `/api/v1/workspaces/{workspace_id}/opencode/skills/batch-delete` maps to `runtime_write`; sensitive: No. |
| `/api/v1/workspaces/{workspace_id}/canvas/review-notes/{note_id}/replies` | `POST` | `runtime_write` | `2040` | No | `POST` `/api/v1/workspaces/{workspace_id}/canvas/review-notes/{note_id}/replies` maps to `runtime_write`; sensitive: No. |
| `/api/v1/workspaces/{workspace_id}/claude-code/slash-commands/{scope}` | `POST` | `runtime_write` | `2040` | No | `POST` `/api/v1/workspaces/{workspace_id}/claude-code/slash-commands/{scope}` maps to `runtime_write`; sensitive: No. |
| `/api/v1/workspaces/{workspace_id}/version-control/lfs/convert` | `POST` | `runtime_write` | `2040` | No | `POST` `/api/v1/workspaces/{workspace_id}/version-control/lfs/convert` maps to `runtime_write`; sensitive: No. |
| `/api/v1/workspaces/{workspace_id}/version-control/lfs/preview` | `POST` | `runtime_write` | `2040` | No | `POST` `/api/v1/workspaces/{workspace_id}/version-control/lfs/preview` maps to `runtime_write`; sensitive: No. |
| `/api/v1/workspaces/{workspace_id}/canvas/review-notes/{note_id}/status` | `PATCH` | `runtime_write` | `2039` | No | `PATCH` `/api/v1/workspaces/{workspace_id}/canvas/review-notes/{note_id}/status` maps to `runtime_write`; sensitive: No. |
| `/api/v1/workspaces/{workspace_id}/claude-code/memory/{scope}/content` | `DELETE`, `PUT` | `runtime_write` | `2039` | No | `DELETE`, `PUT` `/api/v1/workspaces/{workspace_id}/claude-code/memory/{scope}/content` maps to `runtime_write`; sensitive: No. |
| `/api/v1/workspaces/{workspace_id}/claude-code/output-styles/{scope}` | `POST` | `runtime_write` | `2039` | No | `POST` `/api/v1/workspaces/{workspace_id}/claude-code/output-styles/{scope}` maps to `runtime_write`; sensitive: No. |
| `/api/v1/workspaces/{workspace_id}/claude-code/output-styles/{scope}/{file_name}` | `DELETE`, `PUT` | `runtime_write` | `2039` | No | `DELETE`, `PUT` `/api/v1/workspaces/{workspace_id}/claude-code/output-styles/{scope}/{file_name}` maps to `runtime_write`; sensitive: No. |
| `/api/v1/workspaces/{workspace_id}/claude-code/skills/content` | `PUT` | `runtime_write` | `2039` | No | `PUT` `/api/v1/workspaces/{workspace_id}/claude-code/skills/content` maps to `runtime_write`; sensitive: No. |
| `/api/v1/workspaces/{workspace_id}/claude-code/skills/extract` | `POST` | `runtime_write` | `2039` | No | `POST` `/api/v1/workspaces/{workspace_id}/claude-code/skills/extract` maps to `runtime_write`; sensitive: No. |
| `/api/v1/workspaces/{workspace_id}/opencode/subagents/{scope}/content` | `DELETE`, `PUT` | `runtime_write` | `2039` | No | `DELETE`, `PUT` `/api/v1/workspaces/{workspace_id}/opencode/subagents/{scope}/content` maps to `runtime_write`; sensitive: No. |
| `/api/v1/workspaces/{workspace_id}/claude-code/skills/upload` | `POST` | `runtime_write` | `2038` | No | `POST` `/api/v1/workspaces/{workspace_id}/claude-code/skills/upload` maps to `runtime_write`; sensitive: No. |
| `/api/v1/workspaces/{workspace_id}/codex/skills/batch-delete` | `POST` | `runtime_write` | `2038` | No | `POST` `/api/v1/workspaces/{workspace_id}/codex/skills/batch-delete` maps to `runtime_write`; sensitive: No. |
| `/api/v1/workspaces/{workspace_id}/claude-code/hooks/import` | `POST` | `runtime_write` | `2037` | No | `POST` `/api/v1/workspaces/{workspace_id}/claude-code/hooks/import` maps to `runtime_write`; sensitive: No. |
| `/api/v1/workspaces/{workspace_id}/codex/plugins/{plugin_id:path}/hook-trust` | `PATCH` | `runtime_write` | `2037` | No | `PATCH` `/api/v1/workspaces/{workspace_id}/codex/plugins/{plugin_id:path}/hook-trust` maps to `runtime_write`; sensitive: No. |
| `/api/v1/workspaces/{workspace_id}/opencode/slash-commands/{scope}` | `POST` | `runtime_write` | `2037` | No | `POST` `/api/v1/workspaces/{workspace_id}/opencode/slash-commands/{scope}` maps to `runtime_write`; sensitive: No. |
| `/api/v1/workspaces/{workspace_id}/version-control/discard` | `POST` | `runtime_write` | `2037` | No | `POST` `/api/v1/workspaces/{workspace_id}/version-control/discard` maps to `runtime_write`; sensitive: No. |
| `/api/v1/workspaces/{workspace_id}/version-control/unstage` | `POST` | `runtime_write` | `2037` | No | `POST` `/api/v1/workspaces/{workspace_id}/version-control/unstage` maps to `runtime_write`; sensitive: No. |
| `/api/v1/workspaces/{workspace_id}/claude-code/skills/move` | `POST` | `runtime_write` | `2036` | No | `POST` `/api/v1/workspaces/{workspace_id}/claude-code/skills/move` maps to `runtime_write`; sensitive: No. |
| `/api/v1/workspaces/{workspace_id}/opencode/skills/content` | `PUT` | `runtime_write` | `2036` | No | `PUT` `/api/v1/workspaces/{workspace_id}/opencode/skills/content` maps to `runtime_write`; sensitive: No. |
| `/api/v1/workspaces/{workspace_id}/opencode/skills/extract` | `POST` | `runtime_write` | `2036` | No | `POST` `/api/v1/workspaces/{workspace_id}/opencode/skills/extract` maps to `runtime_write`; sensitive: No. |
| `/api/v1/workspaces/{workspace_id}/version-control/commit` | `POST` | `runtime_write` | `2036` | No | `POST` `/api/v1/workspaces/{workspace_id}/version-control/commit` maps to `runtime_write`; sensitive: No. |
| `/api/v1/workspaces/{workspace_id}/version-control/remote` | `PUT` | `runtime_write` | `2036` | No | `PUT` `/api/v1/workspaces/{workspace_id}/version-control/remote` maps to `runtime_write`; sensitive: No. |
| `/api/v1/workspaces/{workspace_id}/claude-code/claude-md` | `PUT` | `runtime_write` | `2035` | No | `PUT` `/api/v1/workspaces/{workspace_id}/claude-code/claude-md` maps to `runtime_write`; sensitive: No. |
| `/api/v1/workspaces/{workspace_id}/claude-code/subagents/{scope}` | `POST` | `runtime_write` | `2035` | No | `POST` `/api/v1/workspaces/{workspace_id}/claude-code/subagents/{scope}` maps to `runtime_write`; sensitive: No. |
| `/api/v1/workspaces/{workspace_id}/opencode/skills/upload` | `POST` | `runtime_write` | `2035` | No | `POST` `/api/v1/workspaces/{workspace_id}/opencode/skills/upload` maps to `runtime_write`; sensitive: No. |
| `/api/v1/workspaces/{workspace_id}/version-control/clone` | `POST` | `runtime_write` | `2035` | No | `POST` `/api/v1/workspaces/{workspace_id}/version-control/clone` maps to `runtime_write`; sensitive: No. |
| `/api/v1/workspaces/{workspace_id}/version-control/fetch` | `POST` | `runtime_write` | `2035` | No | `POST` `/api/v1/workspaces/{workspace_id}/version-control/fetch` maps to `runtime_write`; sensitive: No. |
| `/api/v1/workspaces/{workspace_id}/version-control/stage` | `POST` | `runtime_write` | `2035` | No | `POST` `/api/v1/workspaces/{workspace_id}/version-control/stage` maps to `runtime_write`; sensitive: No. |
| `/api/v1/workspaces/{workspace_id}/codex/slash-commands/{scope}` | `POST` | `runtime_write` | `2034` | No | `POST` `/api/v1/workspaces/{workspace_id}/codex/slash-commands/{scope}` maps to `runtime_write`; sensitive: No. |
| `/api/v1/workspaces/{workspace_id}/version-control/init` | `POST` | `runtime_write` | `2034` | No | `POST` `/api/v1/workspaces/{workspace_id}/version-control/init` maps to `runtime_write`; sensitive: No. |
| `/api/v1/workspaces/{workspace_id}/version-control/pull` | `POST` | `runtime_write` | `2034` | No | `POST` `/api/v1/workspaces/{workspace_id}/version-control/pull` maps to `runtime_write`; sensitive: No. |
| `/api/v1/workspaces/{workspace_id}/version-control/push` | `POST` | `runtime_write` | `2034` | No | `POST` `/api/v1/workspaces/{workspace_id}/version-control/push` maps to `runtime_write`; sensitive: No. |
| `/api/v1/workspaces/{workspace_id}/canvas/review-notes` | `POST` | `runtime_write` | `2033` | No | `POST` `/api/v1/workspaces/{workspace_id}/canvas/review-notes` maps to `runtime_write`; sensitive: No. |
| `/api/v1/workspaces/{workspace_id}/canvas/review-notes/{note_id}` | `DELETE` | `runtime_write` | `2033` | No | `DELETE` `/api/v1/workspaces/{workspace_id}/canvas/review-notes/{note_id}` maps to `runtime_write`; sensitive: No. |
| `/api/v1/workspaces/{workspace_id}/claude-code/plugins/{plugin_id:path}` | `PATCH` | `runtime_write` | `2033` | No | `PATCH` `/api/v1/workspaces/{workspace_id}/claude-code/plugins/{plugin_id:path}` maps to `runtime_write`; sensitive: No. |
| `/api/v1/workspaces/{workspace_id}/codex/overview/trust` | `PATCH` | `runtime_write` | `2033` | No | `PATCH` `/api/v1/workspaces/{workspace_id}/codex/overview/trust` maps to `runtime_write`; sensitive: No. |
| `/api/v1/workspaces/{workspace_id}/codex/rules/validate` | `POST` | `runtime_write` | `2033` | No | `POST` `/api/v1/workspaces/{workspace_id}/codex/rules/validate` maps to `runtime_write`; sensitive: No. |
| `/api/v1/workspaces/{workspace_id}/codex/skills/content` | `PUT` | `runtime_write` | `2033` | No | `PUT` `/api/v1/workspaces/{workspace_id}/codex/skills/content` maps to `runtime_write`; sensitive: No. |
| `/api/v1/workspaces/{workspace_id}/codex/skills/extract` | `POST` | `runtime_write` | `2033` | No | `POST` `/api/v1/workspaces/{workspace_id}/codex/skills/extract` maps to `runtime_write`; sensitive: No. |
| `/api/v1/workspaces/{workspace_id}/opencode/skills/move` | `POST` | `runtime_write` | `2033` | No | `POST` `/api/v1/workspaces/{workspace_id}/opencode/skills/move` maps to `runtime_write`; sensitive: No. |
| `/api/v1/workspaces/{workspace_id}/version-control/lfs` | `POST` | `runtime_write` | `2033` | No | `POST` `/api/v1/workspaces/{workspace_id}/version-control/lfs` maps to `runtime_write`; sensitive: No. |
| `/api/v1/workspaces/{workspace_id}/claude-code/memory/{scope}` | `POST` | `runtime_write` | `2032` | No | `POST` `/api/v1/workspaces/{workspace_id}/claude-code/memory/{scope}` maps to `runtime_write`; sensitive: No. |
| `/api/v1/workspaces/{workspace_id}/claude-code/skills` | `DELETE`, `POST` | `runtime_write` | `2032` | No | `DELETE`, `POST` `/api/v1/workspaces/{workspace_id}/claude-code/skills` maps to `runtime_write`; sensitive: No. |
| `/api/v1/workspaces/{workspace_id}/codex/hooks/{scope}/disable` | `POST` | `runtime_write` | `2032` | No | `POST` `/api/v1/workspaces/{workspace_id}/codex/hooks/{scope}/disable` maps to `runtime_write`; sensitive: No. |
| `/api/v1/workspaces/{workspace_id}/codex/skills/upload` | `POST` | `runtime_write` | `2032` | No | `POST` `/api/v1/workspaces/{workspace_id}/codex/skills/upload` maps to `runtime_write`; sensitive: No. |
| `/api/v1/workspaces/{workspace_id}/opencode/agents-md` | `PUT` | `runtime_write` | `2032` | No | `PUT` `/api/v1/workspaces/{workspace_id}/opencode/agents-md` maps to `runtime_write`; sensitive: No. |
| `/api/v1/workspaces/{workspace_id}/opencode/subagents/{scope}` | `POST` | `runtime_write` | `2032` | No | `POST` `/api/v1/workspaces/{workspace_id}/opencode/subagents/{scope}` maps to `runtime_write`; sensitive: No. |
| `/api/v1/workspaces/{workspace_id}/claude-code/hooks/{scope}` | `DELETE`, `PUT` | `runtime_write` | `2031` | No | `DELETE`, `PUT` `/api/v1/workspaces/{workspace_id}/claude-code/hooks/{scope}` maps to `runtime_write`; sensitive: No. |
| `/api/v1/workspaces/{workspace_id}/codex/hooks/{scope}/enable` | `POST` | `runtime_write` | `2031` | No | `POST` `/api/v1/workspaces/{workspace_id}/codex/hooks/{scope}/enable` maps to `runtime_write`; sensitive: No. |
| `/api/v1/workspaces/{workspace_id}/codex/hooks/{scope}/entry` | `DELETE`, `PUT` | `runtime_write` | `2030` | No | `DELETE`, `PUT` `/api/v1/workspaces/{workspace_id}/codex/hooks/{scope}/entry` maps to `runtime_write`; sensitive: No. |
| `/api/v1/workspaces/{workspace_id}/codex/skills/move` | `POST` | `runtime_write` | `2030` | No | `POST` `/api/v1/workspaces/{workspace_id}/codex/skills/move` maps to `runtime_write`; sensitive: No. |
| `/api/v1/workspaces/{workspace_id}/canvas/manifest` | `DELETE` | `runtime_write` | `2029` | No | `DELETE` `/api/v1/workspaces/{workspace_id}/canvas/manifest` maps to `runtime_write`; sensitive: No. |
| `/api/v1/workspaces/{workspace_id}/codex/agents-md` | `PUT` | `runtime_write` | `2029` | No | `PUT` `/api/v1/workspaces/{workspace_id}/codex/agents-md` maps to `runtime_write`; sensitive: No. |
| `/api/v1/workspaces/{workspace_id}/codex/rules/file` | `DELETE`, `PUT` | `runtime_write` | `2029` | No | `DELETE`, `PUT` `/api/v1/workspaces/{workspace_id}/codex/rules/file` maps to `runtime_write`; sensitive: No. |
| `/api/v1/workspaces/{workspace_id}/codex/subagents` | `DELETE`, `POST`, `PUT` | `runtime_write` | `2029` | No | `DELETE`, `POST`, `PUT` `/api/v1/workspaces/{workspace_id}/codex/subagents` maps to `runtime_write`; sensitive: No. |
| `/api/v1/workspaces/{workspace_id}/opencode/skills` | `DELETE`, `POST` | `runtime_write` | `2029` | No | `DELETE`, `POST` `/api/v1/workspaces/{workspace_id}/opencode/skills` maps to `runtime_write`; sensitive: No. |
| `/api/v1/files/conflicts/preflight` | `POST` | `runtime_write` | `2028` | No | `POST` `/api/v1/files/conflicts/preflight` maps to `runtime_write`; sensitive: No. |
| `/api/v1/workspaces/{workspace_id}/codex/plugins/{plugin_id:path}` | `PATCH` | `runtime_write` | `2027` | No | `PATCH` `/api/v1/workspaces/{workspace_id}/codex/plugins/{plugin_id:path}` maps to `runtime_write`; sensitive: No. |
| `/api/v1/workspaces/{workspace_id}/canvas/reset` | `POST` | `runtime_write` | `2026` | No | `POST` `/api/v1/workspaces/{workspace_id}/canvas/reset` maps to `runtime_write`; sensitive: No. |
| `/api/v1/workspaces/{workspace_id}/codex/skills` | `DELETE`, `POST` | `runtime_write` | `2026` | No | `DELETE`, `POST` `/api/v1/workspaces/{workspace_id}/codex/skills` maps to `runtime_write`; sensitive: No. |
| `/api/v1/workspaces/{workspace_id}/canvas/sync` | `POST` | `runtime_write` | `2025` | No | `POST` `/api/v1/workspaces/{workspace_id}/canvas/sync` maps to `runtime_write`; sensitive: No. |
| `/api/v1/workspaces/{workspace_id}/codex/hooks/{scope}` | `PUT` | `runtime_write` | `2025` | No | `PUT` `/api/v1/workspaces/{workspace_id}/codex/hooks/{scope}` maps to `runtime_write`; sensitive: No. |
| `/api/v1/files/history/{entry_id}/restore` | `POST` | `runtime_write` | `2024` | No | `POST` `/api/v1/files/history/{entry_id}/restore` maps to `runtime_write`; sensitive: No. |
| `/api/v1/workspaces/{workspace_id}/codex/{resource}/file` | `DELETE`, `PUT` | `runtime_write` | `2024` | No | `DELETE`, `PUT` `/api/v1/workspaces/{workspace_id}/codex/{resource}/file` maps to `runtime_write`; sensitive: No. |
| `/api/v1/files/batch-delete` | `POST` | `runtime_write` | `2022` | No | `POST` `/api/v1/files/batch-delete` maps to `runtime_write`; sensitive: No. |
| `/api/v1/files/content/batch` | `POST` | `runtime_write` | `2022` | No | `POST` `/api/v1/files/content/batch` maps to `runtime_write`; sensitive: No. |
| `/api/v1/files/archive` | `POST` | `runtime_write` | `2017` | No | `POST` `/api/v1/files/archive` maps to `runtime_write`; sensitive: No. |
| `/api/v1/files/content` | `PUT` | `runtime_write` | `2017` | No | `PUT` `/api/v1/files/content` maps to `runtime_write`; sensitive: No. |
| `/api/v1/files/extract` | `POST` | `runtime_write` | `2017` | No | `POST` `/api/v1/files/extract` maps to `runtime_write`; sensitive: No. |
| `/api/v1/files/upload` | `POST` | `runtime_write` | `2016` | No | `POST` `/api/v1/files/upload` maps to `runtime_write`; sensitive: No. |
| `/api/v1/files/paste` | `POST` | `runtime_write` | `2015` | No | `POST` `/api/v1/files/paste` maps to `runtime_write`; sensitive: No. |
| `/api/v1/files/move` | `POST` | `runtime_write` | `2014` | No | `POST` `/api/v1/files/move` maps to `runtime_write`; sensitive: No. |
| `/api/v1/files` | `DELETE`, `POST` | `runtime_write` | `2010` | No | `DELETE`, `POST` `/api/v1/files` maps to `runtime_write`; sensitive: No. |
| `/api/v1/workspaces/{workspace_id}/cli-settings/claude-code/prompt-invocations` | `GET` | `runtime_read` | `1056` | No | `GET` `/api/v1/workspaces/{workspace_id}/cli-settings/claude-code/prompt-invocations` maps to `runtime_read`; sensitive: No. |
| `/api/v1/workspaces/{workspace_id}/cli-settings/opencode/prompt-invocations` | `GET` | `runtime_read` | `1053` | No | `GET` `/api/v1/workspaces/{workspace_id}/cli-settings/opencode/prompt-invocations` maps to `runtime_read`; sensitive: No. |
| `/api/v1/workspaces/{workspace_id}/cli-settings/codex/prompt-invocations` | `GET` | `runtime_read` | `1050` | No | `GET` `/api/v1/workspaces/{workspace_id}/cli-settings/codex/prompt-invocations` maps to `runtime_read`; sensitive: No. |
| `/api/v1/workspaces/{workspace_id}/claude-code/slash-commands/{scope}/content` | `GET` | `runtime_read` | `1047` | No | `GET` `/api/v1/workspaces/{workspace_id}/claude-code/slash-commands/{scope}/content` maps to `runtime_read`; sensitive: No. |
| `/api/v1/workspaces/{workspace_id}/version-control/operation-status` | `GET` | `runtime_read` | `1046` | No | `GET` `/api/v1/workspaces/{workspace_id}/version-control/operation-status` maps to `runtime_read`; sensitive: No. |
| `/api/v1/workspaces/{workspace_id}/claude-code/skills/tree/children` | `GET` | `runtime_read` | `1044` | No | `GET` `/api/v1/workspaces/{workspace_id}/claude-code/skills/tree/children` maps to `runtime_read`; sensitive: No. |
| `/api/v1/workspaces/{workspace_id}/opencode/slash-commands/{scope}/content` | `GET` | `runtime_read` | `1044` | No | `GET` `/api/v1/workspaces/{workspace_id}/opencode/slash-commands/{scope}/content` maps to `runtime_read`; sensitive: No. |
| `/api/v1/workspaces/{workspace_id}/claude-code/subagents/{scope}/content` | `GET` | `runtime_read` | `1042` | No | `GET` `/api/v1/workspaces/{workspace_id}/claude-code/subagents/{scope}/content` maps to `runtime_read`; sensitive: No. |
| `/api/v1/workspaces/{workspace_id}/version-control/commits/{commit_id}/files` | `GET` | `runtime_read` | `1042` | No | `GET` `/api/v1/workspaces/{workspace_id}/version-control/commits/{commit_id}/files` maps to `runtime_read`; sensitive: No. |
| `/api/v1/workspaces/{workspace_id}/codex/slash-commands/{scope}/content` | `GET` | `runtime_read` | `1041` | No | `GET` `/api/v1/workspaces/{workspace_id}/codex/slash-commands/{scope}/content` maps to `runtime_read`; sensitive: No. |
| `/api/v1/workspaces/{workspace_id}/opencode/skills/tree/children` | `GET` | `runtime_read` | `1041` | No | `GET` `/api/v1/workspaces/{workspace_id}/opencode/skills/tree/children` maps to `runtime_read`; sensitive: No. |
| `/api/v1/workspaces/{workspace_id}/claude-code/slash-commands` | `GET` | `runtime_read` | `1040` | No | `GET` `/api/v1/workspaces/{workspace_id}/claude-code/slash-commands` maps to `runtime_read`; sensitive: No. |
| `/api/v1/workspaces/{workspace_id}/claude-code/slash-commands/{scope}` | `GET` | `runtime_read` | `1040` | No | `GET` `/api/v1/workspaces/{workspace_id}/claude-code/slash-commands/{scope}` maps to `runtime_read`; sensitive: No. |
| `/api/v1/workspaces/{workspace_id}/codex/managed-requirements` | `GET` | `runtime_read` | `1040` | No | `GET` `/api/v1/workspaces/{workspace_id}/codex/managed-requirements` maps to `runtime_read`; sensitive: No. |
| `/api/v1/workspaces/{workspace_id}/version-control/repository` | `GET` | `runtime_read` | `1040` | No | `GET` `/api/v1/workspaces/{workspace_id}/version-control/repository` maps to `runtime_read`; sensitive: No. |
| `/api/v1/workspaces/{workspace_id}/claude-code/memory/{scope}/content` | `GET` | `runtime_read` | `1039` | No | `GET` `/api/v1/workspaces/{workspace_id}/claude-code/memory/{scope}/content` maps to `runtime_read`; sensitive: No. |
| `/api/v1/workspaces/{workspace_id}/claude-code/output-styles` | `GET` | `runtime_read` | `1039` | No | `GET` `/api/v1/workspaces/{workspace_id}/claude-code/output-styles` maps to `runtime_read`; sensitive: No. |
| `/api/v1/workspaces/{workspace_id}/claude-code/output-styles/{scope}` | `GET` | `runtime_read` | `1039` | No | `GET` `/api/v1/workspaces/{workspace_id}/claude-code/output-styles/{scope}` maps to `runtime_read`; sensitive: No. |
| `/api/v1/workspaces/{workspace_id}/claude-code/output-styles/{scope}/{file_name:path}` | `GET` | `runtime_read` | `1039` | No | `GET` `/api/v1/workspaces/{workspace_id}/claude-code/output-styles/{scope}/{file_name:path}` maps to `runtime_read`; sensitive: No. |
| `/api/v1/workspaces/{workspace_id}/claude-code/skills/content` | `GET` | `runtime_read` | `1039` | No | `GET` `/api/v1/workspaces/{workspace_id}/claude-code/skills/content` maps to `runtime_read`; sensitive: No. |
| `/api/v1/workspaces/{workspace_id}/claude-code/skills/plugins` | `GET` | `runtime_read` | `1039` | No | `GET` `/api/v1/workspaces/{workspace_id}/claude-code/skills/plugins` maps to `runtime_read`; sensitive: No. |
| `/api/v1/workspaces/{workspace_id}/opencode/subagents/{scope}/content` | `GET` | `runtime_read` | `1039` | No | `GET` `/api/v1/workspaces/{workspace_id}/opencode/subagents/{scope}/content` maps to `runtime_read`; sensitive: No. |
| `/api/v1/workspaces/{workspace_id}/codex/skills/tree/children` | `GET` | `runtime_read` | `1038` | No | `GET` `/api/v1/workspaces/{workspace_id}/codex/skills/tree/children` maps to `runtime_read`; sensitive: No. |
| `/api/v1/workspaces/{workspace_id}/version-control/branches` | `GET` | `runtime_read` | `1038` | No | `GET` `/api/v1/workspaces/{workspace_id}/version-control/branches` maps to `runtime_read`; sensitive: No. |
| `/api/v1/workspaces/{workspace_id}/version-control/contexts` | `GET` | `runtime_read` | `1038` | No | `GET` `/api/v1/workspaces/{workspace_id}/version-control/contexts` maps to `runtime_read`; sensitive: No. |
| `/api/v1/workspaces/{workspace_id}/claude-code/hooks/export` | `GET` | `runtime_read` | `1037` | No | `GET` `/api/v1/workspaces/{workspace_id}/claude-code/hooks/export` maps to `runtime_read`; sensitive: No. |
| `/api/v1/workspaces/{workspace_id}/opencode/slash-commands` | `GET` | `runtime_read` | `1037` | No | `GET` `/api/v1/workspaces/{workspace_id}/opencode/slash-commands` maps to `runtime_read`; sensitive: No. |
| `/api/v1/workspaces/{workspace_id}/opencode/slash-commands/{scope}` | `GET` | `runtime_read` | `1037` | No | `GET` `/api/v1/workspaces/{workspace_id}/opencode/slash-commands/{scope}` maps to `runtime_read`; sensitive: No. |
| `/api/v1/workspaces/{workspace_id}/version-control/changes` | `GET` | `runtime_read` | `1037` | No | `GET` `/api/v1/workspaces/{workspace_id}/version-control/changes` maps to `runtime_read`; sensitive: No. |
| `/api/v1/workspaces/{workspace_id}/version-control/commits` | `GET` | `runtime_read` | `1037` | No | `GET` `/api/v1/workspaces/{workspace_id}/version-control/commits` maps to `runtime_read`; sensitive: No. |
| `/api/v1/workspaces/{workspace_id}/version-control/commits/{commit_id}` | `GET` | `runtime_read` | `1037` | No | `GET` `/api/v1/workspaces/{workspace_id}/version-control/commits/{commit_id}` maps to `runtime_read`; sensitive: No. |
| `/api/v1/workspaces/{workspace_id}/claude-code/skills/tree` | `GET` | `runtime_read` | `1036` | No | `GET` `/api/v1/workspaces/{workspace_id}/claude-code/skills/tree` maps to `runtime_read`; sensitive: No. |
| `/api/v1/workspaces/{workspace_id}/opencode/skills/content` | `GET` | `runtime_read` | `1036` | No | `GET` `/api/v1/workspaces/{workspace_id}/opencode/skills/content` maps to `runtime_read`; sensitive: No. |
| `/api/v1/workspaces/{workspace_id}/version-control/remote` | `GET` | `runtime_read` | `1036` | No | `GET` `/api/v1/workspaces/{workspace_id}/version-control/remote` maps to `runtime_read`; sensitive: No. |
| `/api/v1/workspaces/{workspace_id}/version-control/status` | `GET` | `runtime_read` | `1036` | No | `GET` `/api/v1/workspaces/{workspace_id}/version-control/status` maps to `runtime_read`; sensitive: No. |
| `/api/v1/workspaces/{workspace_id}/claude-code/claude-md` | `GET` | `runtime_read` | `1035` | No | `GET` `/api/v1/workspaces/{workspace_id}/claude-code/claude-md` maps to `runtime_read`; sensitive: No. |
| `/api/v1/workspaces/{workspace_id}/claude-code/subagents` | `GET` | `runtime_read` | `1035` | No | `GET` `/api/v1/workspaces/{workspace_id}/claude-code/subagents` maps to `runtime_read`; sensitive: No. |
| `/api/v1/workspaces/{workspace_id}/claude-code/subagents/{scope}` | `GET` | `runtime_read` | `1035` | No | `GET` `/api/v1/workspaces/{workspace_id}/claude-code/subagents/{scope}` maps to `runtime_read`; sensitive: No. |
| `/api/v1/workspaces/{workspace_id}/codex/subagents/detail` | `GET` | `runtime_read` | `1035` | No | `GET` `/api/v1/workspaces/{workspace_id}/codex/subagents/detail` maps to `runtime_read`; sensitive: No. |
| `/api/v1/workspaces/{workspace_id}/codex/slash-commands` | `GET` | `runtime_read` | `1034` | No | `GET` `/api/v1/workspaces/{workspace_id}/codex/slash-commands` maps to `runtime_read`; sensitive: No. |
| `/api/v1/workspaces/{workspace_id}/codex/slash-commands/{scope}` | `GET` | `runtime_read` | `1034` | No | `GET` `/api/v1/workspaces/{workspace_id}/codex/slash-commands/{scope}` maps to `runtime_read`; sensitive: No. |
| `/api/v1/workspaces/{workspace_id}/version-control/blob` | `GET` | `runtime_read` | `1034` | No | `GET` `/api/v1/workspaces/{workspace_id}/version-control/blob` maps to `runtime_read`; sensitive: No. |
| `/api/v1/workspaces/{workspace_id}/version-control/diff` | `GET` | `runtime_read` | `1034` | No | `GET` `/api/v1/workspaces/{workspace_id}/version-control/diff` maps to `runtime_read`; sensitive: No. |
| `/api/v1/workspaces/{workspace_id}/canvas/review-notes` | `GET` | `runtime_read` | `1033` | No | `GET` `/api/v1/workspaces/{workspace_id}/canvas/review-notes` maps to `runtime_read`; sensitive: No. |
| `/api/v1/workspaces/{workspace_id}/claude-code/plugins` | `GET` | `runtime_read` | `1033` | No | `GET` `/api/v1/workspaces/{workspace_id}/claude-code/plugins` maps to `runtime_read`; sensitive: No. |
| `/api/v1/workspaces/{workspace_id}/claude-code/plugins/{plugin_id:path}` | `GET` | `runtime_read` | `1033` | No | `GET` `/api/v1/workspaces/{workspace_id}/claude-code/plugins/{plugin_id:path}` maps to `runtime_read`; sensitive: No. |
| `/api/v1/workspaces/{workspace_id}/codex/skills/content` | `GET` | `runtime_read` | `1033` | No | `GET` `/api/v1/workspaces/{workspace_id}/codex/skills/content` maps to `runtime_read`; sensitive: No. |
| `/api/v1/workspaces/{workspace_id}/opencode/skills/tree` | `GET` | `runtime_read` | `1033` | No | `GET` `/api/v1/workspaces/{workspace_id}/opencode/skills/tree` maps to `runtime_read`; sensitive: No. |
| `/api/v1/workspaces/{workspace_id}/version-control/lfs` | `GET` | `runtime_read` | `1033` | No | `GET` `/api/v1/workspaces/{workspace_id}/version-control/lfs` maps to `runtime_read`; sensitive: No. |
| `/api/v1/workspaces/{workspace_id}/claude-code/memory` | `GET` | `runtime_read` | `1032` | No | `GET` `/api/v1/workspaces/{workspace_id}/claude-code/memory` maps to `runtime_read`; sensitive: No. |
| `/api/v1/workspaces/{workspace_id}/codex/hooks-scopes` | `GET` | `runtime_read` | `1032` | No | `GET` `/api/v1/workspaces/{workspace_id}/codex/hooks-scopes` maps to `runtime_read`; sensitive: No. |
| `/api/v1/workspaces/{workspace_id}/opencode/agents-md` | `GET` | `runtime_read` | `1032` | No | `GET` `/api/v1/workspaces/{workspace_id}/opencode/agents-md` maps to `runtime_read`; sensitive: No. |
| `/api/v1/workspaces/{workspace_id}/opencode/subagents` | `GET` | `runtime_read` | `1032` | No | `GET` `/api/v1/workspaces/{workspace_id}/opencode/subagents` maps to `runtime_read`; sensitive: No. |
| `/api/v1/workspaces/{workspace_id}/opencode/subagents/{scope}` | `GET` | `runtime_read` | `1032` | No | `GET` `/api/v1/workspaces/{workspace_id}/opencode/subagents/{scope}` maps to `runtime_read`; sensitive: No. |
| `/api/v1/workspaces/{workspace_id}/claude-code/hooks` | `GET` | `runtime_read` | `1031` | No | `GET` `/api/v1/workspaces/{workspace_id}/claude-code/hooks` maps to `runtime_read`; sensitive: No. |
| `/api/v1/workspaces/{workspace_id}/claude-code/hooks/{scope}` | `GET` | `runtime_read` | `1031` | No | `GET` `/api/v1/workspaces/{workspace_id}/claude-code/hooks/{scope}` maps to `runtime_read`; sensitive: No. |
| `/api/v1/workspaces/{workspace_id}/codex/skills/tree` | `GET` | `runtime_read` | `1030` | No | `GET` `/api/v1/workspaces/{workspace_id}/codex/skills/tree` maps to `runtime_read`; sensitive: No. |
| `/api/v1/workspaces/{workspace_id}/codex/agents-md` | `GET` | `runtime_read` | `1029` | No | `GET` `/api/v1/workspaces/{workspace_id}/codex/agents-md` maps to `runtime_read`; sensitive: No. |
| `/api/v1/workspaces/{workspace_id}/codex/rules/file` | `GET` | `runtime_read` | `1029` | No | `GET` `/api/v1/workspaces/{workspace_id}/codex/rules/file` maps to `runtime_read`; sensitive: No. |
| `/api/v1/workspaces/{workspace_id}/codex/subagents` | `GET` | `runtime_read` | `1029` | No | `GET` `/api/v1/workspaces/{workspace_id}/codex/subagents` maps to `runtime_read`; sensitive: No. |
| `/api/v1/workspaces/{workspace_id}/codex/overview` | `GET` | `runtime_read` | `1028` | No | `GET` `/api/v1/workspaces/{workspace_id}/codex/overview` maps to `runtime_read`; sensitive: No. |
| `/api/v1/workspaces/{workspace_id}/canvas/detect` | `GET` | `runtime_read` | `1027` | No | `GET` `/api/v1/workspaces/{workspace_id}/canvas/detect` maps to `runtime_read`; sensitive: No. |
| `/api/v1/workspaces/{workspace_id}/canvas/health` | `GET` | `runtime_read` | `1027` | No | `GET` `/api/v1/workspaces/{workspace_id}/canvas/health` maps to `runtime_read`; sensitive: No. |
| `/api/v1/workspaces/{workspace_id}/canvas/routes` | `GET` | `runtime_read` | `1027` | No | `GET` `/api/v1/workspaces/{workspace_id}/canvas/routes` maps to `runtime_read`; sensitive: No. |
| `/api/v1/workspaces/{workspace_id}/codex/plugins` | `GET` | `runtime_read` | `1027` | No | `GET` `/api/v1/workspaces/{workspace_id}/codex/plugins` maps to `runtime_read`; sensitive: No. |
| `/api/v1/workspaces/{workspace_id}/codex/plugins/{plugin_id:path}` | `GET` | `runtime_read` | `1027` | No | `GET` `/api/v1/workspaces/{workspace_id}/codex/plugins/{plugin_id:path}` maps to `runtime_read`; sensitive: No. |
| `/api/v1/files/archive/{operation_id}/download` | `GET` | `runtime_read` | `1025` | No | `GET` `/api/v1/files/archive/{operation_id}/download` maps to `runtime_read`; sensitive: No. |
| `/api/v1/workspaces/{workspace_id}/canvas/logs` | `GET` | `runtime_read` | `1025` | No | `GET` `/api/v1/workspaces/{workspace_id}/canvas/logs` maps to `runtime_read`; sensitive: No. |
| `/api/v1/workspaces/{workspace_id}/codex/hooks/{scope}` | `GET` | `runtime_read` | `1025` | No | `GET` `/api/v1/workspaces/{workspace_id}/codex/hooks/{scope}` maps to `runtime_read`; sensitive: No. |
| `/api/v1/workspaces/{workspace_id}/codex/rules` | `GET` | `runtime_read` | `1025` | No | `GET` `/api/v1/workspaces/{workspace_id}/codex/rules` maps to `runtime_read`; sensitive: No. |
| `/api/v1/workspaces/{workspace_id}/codex/{resource}/files` | `GET` | `runtime_read` | `1025` | No | `GET` `/api/v1/workspaces/{workspace_id}/codex/{resource}/files` maps to `runtime_read`; sensitive: No. |
| `/api/v1/workspaces/{workspace_id}/codex/apps` | `GET` | `runtime_read` | `1024` | No | `GET` `/api/v1/workspaces/{workspace_id}/codex/apps` maps to `runtime_read`; sensitive: No. |
| `/api/v1/workspaces/{workspace_id}/codex/apps/{app_name:path}` | `GET` | `runtime_read` | `1024` | No | `GET` `/api/v1/workspaces/{workspace_id}/codex/apps/{app_name:path}` maps to `runtime_read`; sensitive: No. |
| `/api/v1/workspaces/{workspace_id}/codex/{resource}/file` | `GET` | `runtime_read` | `1024` | No | `GET` `/api/v1/workspaces/{workspace_id}/codex/{resource}/file` maps to `runtime_read`; sensitive: No. |
| `/api/v1/files/tree/children` | `GET` | `runtime_read` | `1022` | No | `GET` `/api/v1/files/tree/children` maps to `runtime_read`; sensitive: No. |
| `/api/v1/workspaces/{workspace_id}/codex` | `GET` | `runtime_read` | `1020` | No | `GET` `/api/v1/workspaces/{workspace_id}/codex` maps to `runtime_read`; sensitive: No. |
| `/docs/oauth2-redirect` | `GET`, `HEAD` | `runtime_read` | `1019` | No | `GET`, `HEAD` `/docs/oauth2-redirect` maps to `runtime_read`; sensitive: No. |
| `/api/v1/files/download` | `GET` | `runtime_read` | `1018` | No | `GET` `/api/v1/files/download` maps to `runtime_read`; sensitive: No. |
| `/api/v1/files/archive/{operation_id}` | `GET` | `runtime_read` | `1017` | No | `GET` `/api/v1/files/archive/{operation_id}` maps to `runtime_read`; sensitive: No. |
| `/api/v1/files/content` | `GET` | `runtime_read` | `1017` | No | `GET` `/api/v1/files/content` maps to `runtime_read`; sensitive: No. |
| `/api/v1/files/history` | `GET` | `runtime_read` | `1017` | No | `GET` `/api/v1/files/history` maps to `runtime_read`; sensitive: No. |
| `/api/v1/files/search` | `GET` | `runtime_read` | `1016` | No | `GET` `/api/v1/files/search` maps to `runtime_read`; sensitive: No. |
| `/api/v1/files/tree` | `GET` | `runtime_read` | `1014` | No | `GET` `/api/v1/files/tree` maps to `runtime_read`; sensitive: No. |
| `/openapi.json` | `GET`, `HEAD` | `runtime_read` | `1012` | No | `GET`, `HEAD` `/openapi.json` maps to `runtime_read`; sensitive: No. |
| `/redoc` | `GET`, `HEAD` | `runtime_read` | `1005` | No | `GET`, `HEAD` `/redoc` maps to `runtime_read`; sensitive: No. |
| `/docs` | `GET`, `HEAD` | `runtime_read` | `1004` | No | `GET`, `HEAD` `/docs` maps to `runtime_read`; sensitive: No. |
| `/` | `GET` | `runtime_read` | `1000` | No | `GET` `/` maps to `runtime_read`; sensitive: No. |

| Error code | Description |
| --- | --- |
| `WORKSPACE_RUNTIME_ACTION_FORBIDDEN` | Stable authorization error code `WORKSPACE_RUNTIME_ACTION_FORBIDDEN`. |
<!-- authorization-contract:runtime:end -->

## Resource telemetry

Runtime exposes no new public user telemetry route. It sends successful activity events and `workspace_data` or `runtime_home` measurements to the internal Manager batch API. Delivery is fail-open through a durable outbox and never blocks user operations. Payloads contain no prompts, content, filenames, or paths. See [Platform Resource Statistics and Capacity Governance](/features/platform/resource-statistics-and-capacity).
