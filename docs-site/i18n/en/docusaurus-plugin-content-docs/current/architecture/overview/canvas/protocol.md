---
title: Canvas Protocol
---

# Canvas Protocol

Aileron Canvas uses a single active canvas declaration: `/workspace/.aileron/canvas.json`. When the file exists, the management server parses the manifest and starts the matching renderer. When the file does not exist, the Canvas tab shows the default canvas.

This page describes the live-preview protocol inside a Workspace. To turn an active Canvas into a long-lived HTTPS site, see
[Production Canvas Publishing Architecture](/architecture/overview/canvas/publishing) and
[Production Canvas Publishing Environment Setup](/installation/canvas-publishing).

:::note What is the management server?
On this page, “management server” means the Express API built into the `workspace-canvas` service (`workspace-canvas/management-server`). It only parses `canvas.json` and starts or stops the static or Next.js renderer; it is **not** Workspace Manager (the `workspace-manager` service). `workspace-canvas` is the independent Canvas component described in [Architecture Overview](/architecture/overview/) and [Execution-Plane Lifecycle and Safety](/architecture/overview/execution-plane), with its own desired/observed revision. Replacing Canvas does not rebuild Runtime or Browser.
:::

This page covers both the manifest contract and the Canvas tab behavior so user-facing docs and architecture docs stay aligned.

## Canvas tab states

The Canvas tab displays the workspace's current active canvas. The visible state is determined by both the manifest and runtime status:

| State | Meaning |
|---|---|
| Active skill canvas | `canvas.json` exists and `owner.skillName` is set. The content is produced by a skill, such as a PPT preview or candidate selector. |
| Active user canvas | `canvas.json` exists and `owner.skillName` is empty, or the whole `owner` object is omitted. The content is provided by a user-created or agent-created canvas. |
| Default canvas | `canvas.json` does not exist. The platform displays the default information screen. |
| Invalid manifest | `canvas.json` exists, but fields, paths, or renderer prerequisites are invalid. The platform shows an error notice and the iframe returns to the default canvas. |
| Runtime unhealthy | The manifest is valid, but renderer startup or execution failed. Runtime status is shown separately from manifest validation errors. |

### Status notice

The status notice above the Canvas tab explains the current content source:

- Skill canvas shows the manifest `title` and `owner.skillName`.
- User canvas shows the manifest `title`.
- Default canvas says there is no active canvas and explains how to create `canvas.json`.
- Invalid manifest shows the manifest error type.
- Runtime unhealthy shows renderer startup or runtime failures.

Platform chrome text follows the current locale. Manifest `title` and `owner.skillName` are user- or skill-provided data and are not translated.

## Detection flow

```text
detectCanvas()
  ├─ /workspace/.aileron/canvas.json exists?
  │    ├─ yes: parse + validate manifest
  │    │    ├─ kind=static: serve contentDir with static handler
  │    │    └─ kind=nextjs: launch Next.js dev server from contentDir
  │    └─ no: serve default-canvas
  └─ return manifestStatus + runtimeStatus
```

The platform uses `canvas.json` as the only source of truth and does not infer canvas type from `.next/` or `*.html`.

## Manifest fields

`/workspace/.aileron/canvas.json` must match this structure:

```json
{
  "version": 1,
  "kind": "static",
  "contentDir": "./canvases/demo",
  "title": "Demo Canvas",
  "owner": {
    "skillName": "ppt-design-flow"
  },
  "routes": [
    { "path": "/", "label": "Home" }
  ],
  "defaultPath": "/"
}
```

| Field | Description |
|---|---|
| `version` | Currently only accepts integer `1`. |
| `kind` | Renderer type. Only `static` and `nextjs` are accepted. |
| `contentDir` | Canvas content directory. Relative paths are resolved from `/workspace/.aileron/`; absolute paths must stay under `/workspace/`. |
| `title` | Canvas display name. It is manifest data; the frontend embeds it in localized copy without translating the string itself. |
| `owner` | Optional attribution metadata. The renderer, bridge, security rules, and deactivate endpoint do not branch on it; its only effect is the copy in the status notice at the top of the Canvas tab. The whole object may be omitted. |
| `owner.skillName` | Optional. When set, the status notice says the canvas is provided by `<skillName>`; when unset (or when the whole `owner` object is omitted), the canvas is shown as user-enabled. |
| `routes` | Route list. Each item contains `path` and `label`. |
| `defaultPath` | Default route. Must match one `routes[].path`. |

## contentDir safety rules

`contentDir` must satisfy these rules:

- The resolved path must stay inside `/workspace/`.
- It must not contain `..` traversal.
- No path segment may pass through a symlink.

`/__aileron/*` is reserved by the platform. Skill or user canvases should not provide files with the same route.

## Renderer kinds

Use `static` when:

- The content consists of static files such as HTML, CSS, JavaScript, and images.
- Refreshing the iframe after an HTML change is enough to see the update.
- Next.js routing, HMR, and a server-side development server are not required.

Use `nextjs` when:

- The content directory is a Next.js app.
- `package.json` has a `next` dependency.
- A Next.js development server and HMR are required.

### Static example

```text
/workspace/.aileron/
├── canvas.json
└── canvases/demo/
    ├── index.html
    ├── app.js
    └── styles.css
```

```json
{
  "version": 1,
  "kind": "static",
  "contentDir": "./canvases/demo",
  "title": "Static Demo",
  "routes": [
    { "path": "/", "label": "Home" },
    { "path": "/review", "label": "Review" }
  ],
  "defaultPath": "/"
}
```

### Next.js example

```text
/workspace/.aileron/
├── canvas.json
└── canvases/next-demo/
    ├── app/page.tsx
    ├── package.json
    └── next.config.js
```

```json
{
  "version": 1,
  "kind": "nextjs",
  "contentDir": "./canvases/next-demo",
  "title": "Next.js Demo",
  "routes": [
    { "path": "/", "label": "Home" }
  ],
  "defaultPath": "/"
}
```

## MCP Artifact Tool

After atomically writing `canvas.json` and the canvas content files, the agent should call `mcp__aileron__show_canvas_artifact` to notify the user. For the complete invocation rules and schema, see [Aileron MCP Tools](/reference/mcp-tools#show_canvas_artifact).

The tool renders a Canvas artifact card in chat. The actual Canvas content is still determined entirely by `/workspace/.aileron/canvas.json`; the tool does not carry HTML, declare the renderer, or replace the manifest.

The tool call only renders the artifact card. The Canvas renderer, route, and content source are all determined by the manifest.

## Agent Workflow Ownership

The always-on Aileron policy has only two responsibilities:

1. Route user-facing web preview tasks to the `aileron-web-canvas` skill.
2. Prevent completion until `canvas.json` exists and `mcp__aileron__show_canvas_artifact` has been called.

The skill exclusively owns the workspace layout, manifest authoring, renderer choice, preview activation, and discovery sequence; the policy does not repeat those details. If a new Canvas brief still lacks decisions that materially change the result, the skill first presents one short line and a prefilled Question Form with at most five questions, before reading files or creating content. If the brief is already specific enough, it starts building directly without forcing another question round.

## Bridge API

The management server injects this script into static, Next.js, and default canvas HTML:

```html
<script src="/__aileron/bridge.js" data-aileron-canvas-bridge="true"></script>
```

The bridge source is `aileron-canvas-bridge`, and the version is `2`. Canvas content can emit events:

```js
window.aileron.bridge.emit("STYLE_SELECTED", { direction: "B" });
```

Every `routePath` reported by the bridge is an absolute path within the Canvas application. For example, the root page is `/`; the public Workspace Gateway prefix `/workspaces/{workspaceId}/canvas` is not part of a Canvas route. The frontend sends the current resolved `light` or `dark` theme through the `SET_THEME` command. The bridge stores it in `window.aileron.theme` and emits an `aileron:themechange` event so the Canvas application can apply it after initialization without interfering with framework hydration.

### Built-in review event family

The platform reserves and handles these events:

- `BRIDGE_READY`
- `ROUTE_CHANGED`
- `TARGET_SELECTED`
- `TARGET_RECTS`
- `BRIDGE_ERROR`

### SKILL_EVENT rules

`window.aileron.bridge.emit(eventType, data)` sends a `SKILL_EVENT`. The constraints are:

- `eventType` must match `^[A-Z][A-Z0-9_]*$`.
- The serialized payload must not exceed 32 KB.
- Repeated emits of the same `eventType` within 200ms are debounced, and only the last one is sent.

If the frontend has no registered handler, it converts `SKILL_EVENT` into a chat draft. When a registered handler matches, it does not fall back to a chat draft.

### Skill interaction example

Skill-owned canvas content can emit a bridge event to return a user's on-canvas choice to the agent:

```js
window.aileron.bridge.emit("STYLE_SELECTED", { direction: "B" });
```

If the frontend has no handler registered for that event, it becomes a chat draft, equivalent to the user sending the payload text back to chat.

### Review notes and injected bridge.js

The management server injects `/__aileron/bridge.js` into static, Next.js, and default canvas HTML. Canvas content can enter review mode and use the same bridge to send target selection, target rectangles, and route change events. Users can click elements inside the iframe and create review notes; review notes can be sent back to chat so the agent can adjust content with a concrete element location and description.

## Route picker

The Canvas route picker is derived from `canvas.json.routes`. Each route needs:

- `path`, such as `/` or `/review`.
- `label`, the display name in the route picker.

`defaultPath` must match one route. Static canvas maps route paths to HTML files in `contentDir`; Next.js canvas delegates routing to the Next.js dev server.

## Programmatic deactivation

An active canvas can be programmatically deactivated with:

```http
DELETE /api/v1/workspaces/{workspaceId}/canvas/manifest
```

This deletes `/workspace/.aileron/canvas.json`, triggers canvas sync, and returns to the default canvas. The operation is idempotent; it succeeds even when the manifest is already absent. This endpoint is available for skills, automation flows, and admin maintenance tools.

## Common errors

| errorCode | Cause | Fix |
|---|---|---|
| `INVALID_MANIFEST` | JSON cannot be parsed or the schema is invalid. | Check required fields, field types, and enums. |
| `STATIC_INDEX_MISSING` | `kind=static`, but `contentDir/index.html` is missing. | Add `index.html` or fix `contentDir`. |
| `NEXTJS_PROJECT_INVALID` | `kind=nextjs`, but `package.json` or the `next` dependency is missing. | Complete the Next.js project structure. |
| `CONTENT_DIR_TRAVERSAL` | `contentDir` contains `..`. | Use a safe path inside `/workspace/`. |
| `CONTENT_DIR_OUTSIDE_WORKSPACE` | Resolved `contentDir` leaves `/workspace/`. | Move content back inside the workspace. |
| `CONTENT_DIR_SYMLINK` | `contentDir` path passes through a symlink. | Use a real directory instead of a symlink. |

## Sync semantics

Canvas sync is proxied by workspace-runtime to the management server:

```http
POST /api/v1/workspaces/{workspaceId}/canvas/sync
```

The management server `/sync` endpoint runs `syncAndStart()`:

1. Reads renderer state and manifest detection before sync.
2. Re-reads `/workspace/.aileron/canvas.json`.
3. Compares manifest signature, renderer kind/source, runtime status, and the Next.js dependency snapshot.
4. Chooses `rendererAction`:
   - `reused`: manifest and renderer conditions did not change, so the existing renderer is reused and the frontend reloads the iframe.
   - `restarted`: manifest, kind, contentDir, routes, title, owner, Next.js dependencies, reset state, or renderer availability changed, so the renderer stops and restarts.

The static renderer reads `contentDir` directly. When only static file contents change and the manifest is unchanged, sync usually returns `reused`; the frontend iframe reload shows the new content.

The Next.js renderer handles source changes through the dev server and HMR. If `package.json` or lockfiles change the dependency signature, sync restarts the renderer and prepares dependencies again.

Only one sync/reset can run at a time. When the management server is busy, it returns `409 CANVAS_SYNC_IN_PROGRESS`.
