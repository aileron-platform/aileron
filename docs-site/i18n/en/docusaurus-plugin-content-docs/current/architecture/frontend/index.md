---
title: Frontend Architecture
---

# Frontend Architecture

This document describes Aileron's frontend module boundaries, Workspace canonical routes, Shared Components taxonomy, and naming and reuse rules. The shared product Shell interface and the three product Adapters are defined in [ProductShell and Semantic Product Regions](/architecture/frontend/product-shell); cross-product Version Control and Repository Setup are defined in [Shared Version Control and Repository Setup](/architecture/overview/version-control).

## Overview

The frontend follows a feature-oriented architecture: each product domain owns its routes, screens, state, and API mappings, while capabilities that are genuinely cross-domain live in `shared`.

The current architecture covers Workspace, Workspace Automation, Shared Components, AI Chat, Knowledge Base, Marketplace, and User Management:

- Workspace route gating, the ProductShell Adapter, Provider, Reducer, and file-tree orchestration are split by single responsibility instead of being concentrated in oversized files.
- `workspace-automation` is the only Automation frontend module.
- Workspace does not depend on `app` internals, and cross-feature dependencies are acyclic.
- Any feature that needs a Workspace runtime identity uses a workspace ID-scoped canonical route; the pre-creation flow, the global selector, global Automation, and the external deep-link adapter are the listed exceptions.
- `workspace/features/*` has clear private sub-feature ownership; domain boundaries are not replaced by formal flattening.
- Shared Components are classified by stable responsibility and exposed through explicit package entries; feature-specific ownership does not leak into shared.
- AI Chat's route page, API, model, storage, realtime, and attachment contracts each have a clear owner; cross-module integration only goes through the root `public.ts`.
- Knowledge Base's lifecycle, files, version control, sharing, workspace attachment, and settings stay under a single feature owner; non-React adapters/models/API snapshots do not mix into `components`.
- Marketplace's center, detail, editor, and settings are private sub-domains of the same module; route pages, storage, models, detail/editor-specific components, and the file workbench adapter each belong to a clear owner.

### Same-origin network contract

Frontend owns no API base URL, public URL, Runtime host, or dynamic port setting. API, OAuth, Runtime, Browser, Canvas, and WebSocket builders compose only `/api/v1/...` and `/workspaces/{uuid}/runtime|browser|canvas/...` relative paths on the current Origin. Nginx and Vite gateways accept only a canonical Workspace UUID and fixed target. Every Workspace gateway request first passes the Manager resource-operation gate for read authorization, then all browser cookies, Authorization, proxy authorization, API key, and CSRF headers are removed before the execution-plane upstream. The Manager API session cookie is scoped to `/api/v1`; a separate HttpOnly gateway session cookie scoped to `/workspaces` supports the authorization subrequest. The gateway preserves required `X-Forwarded-*`, streaming, WebSocket Upgrade, and subprotocol behavior. The only retained Vite build capability flag is `VITE_BROWSER_EXTENSION_ID`.

## Dependency Direction

The formal dependency direction is:

```text
app → features → shared
app → shared
```

Responsibilities per layer:

- `app`: application composition, top-level router, global navigation, and provider composition.
- `features`: product domains, route-visible pages, domain state, and API adapters.
- `shared`: UI primitives, layout primitives, workflows, i18n, API infrastructure, and utilities that carry no product ownership.

The following dependencies are prohibited:

```text
shared ✕→ app
shared ✕→ features
feature ✕→ app internals
feature ✕→ sibling feature internals
```

Top-level modules may only reference each other through the other module's root `public.ts`, never by reaching into its `components`, `hooks`, `model`, `providers`, or `api`. `workspace/features/*` and `marketplace/features/*` are private sub-features of their owning module; a sub-feature may reference its own internals and its module's root-level contracts directly, but not a sibling sub-feature, and it must not create a nested `public.ts` or `index.ts` barrel. A domain capability needed by two or more private sub-features is promoted to a semantic folder at the owning module's root instead of being exported from one of the sub-features.

`frontend/src/architecture/frontendArchitecture.test.ts` parses static import, import type, export, dynamic import, and `require` via TypeScript AST to continuously guard these boundaries: it forbids any feature depending on App, Shared reverse-depending on App/Features, any external consumer reaching into feature internals, and nested features under any `<top-feature>/features` referencing each other. Filesystem rules further require each top-level feature to have only a root `public.ts`, and forbid nested `public.ts(x)` or `index.ts(x)` barrels inside a feature.

### Feature Public Entry and Lazy Loading

`app` and sibling modules must not know a feature's internal page, context, hook, or module file paths. Every feature that needs external consumers defines a minimal public contract in its root `public.ts`:

- `auth/public.ts` exports `RequireAuth`, `PublicRoute`, `AuthProvider`, `useAuth`, `OidcUserProfile`, and `loadLoginPage`, `loadRegisterPage`, `loadCallbackPage`. App Shell, App Provider, Global Navigation, and other modules use the auth contract only from here.
- `knowledge-base/public.ts`, `marketplace/public.ts`, `user-management/public.ts`, and `workspace-automation/public.ts` provide `loadKnowledgeBaseModule`, `loadMarketplaceModule`, `loadUserManagementModule`, and `loadAutomationModule` respectively. Inside the feature boundary, each loader converts the named module component into the `{ default: Component }` shape `React.lazy` needs, without restoring a component default export for this purpose.
- `ai-chat/public.ts` provides `loadAiChatPage` plus Companion, timeline, settings, query key, and integration context — the actual cross-module contracts. Workspace composes `AiChatPage` only through this loader; Workspace Automation obtains thread query and timeline contracts only through the same public entry.
- AppRouter obtains route components or lazy loaders only from each feature's `public.ts`; lazy-loading timing, route boundaries, Suspense fallback, route JSX, and URL contracts stay consistent as a result. A feature may use relative paths internally per actual ownership, without routing back through its own public entry.

This rule is a one-way boundary, not a giant barrel. `public.ts` does not re-export every internal symbol, and no empty entry is created for folder symmetry.

## Primary Product-Domain Module Ownership

| Module | Ownership | Not Responsible For |
|---|---|---|
| `workspace` | Workspace identity, Shell, runtime composition, file management, version control, Workspace Settings, Container, Canvas, and Agent Settings | Global navigation implementation, Automation domain, generic UI primitives |
| `workspace-automation` | `/automation` Dashboard, workspace-scoped Automation page, jobs, executions, scheduling forms, and the Automation API | Workspace Provider, Workspace layout, Workspace's internal route parser |
| `workspace-wizard` | The four-step pre-creation form, branch lookup, creation, and setup polling | Runtime routes and Provider state for an existing Workspace |
| `ai-chat` | Threads, Turns, timelines, Agent event normalization, attachments, and Chat UI | Workspace route/runtime ownership, Automation job lifecycle |
| `auth` | Sign-in, callback, session bootstrap, and the authenticated principal | Workspace or Knowledge Base resource-authorization decisions |
| `marketplace` | Marketplace center, package detail, canonical editor, settings, Registry lifecycle, and user-copy management | Knowledge Base editor, generic editor framework, Workspace runtime ownership |
| `knowledge-base` | Knowledge Base lifecycle, files, version control, sharing, workspace attachment, and settings | Marketplace Registry package lifecycle, Workspace runtime ownership |
| `user-management` | Users, groups, role issues, and member-management flows | Knowledge Base-specific group semantics, global navigation state |

`knowledge-base` is the official folder name; docs and code do not mix `knowledge`, `knowledgeBase` folder spellings, or the `KB` filename abbreviation.

## Authorization Data Boundary

`auth` stores the `admin | member` platform role and backend-generated platform `allowedOperations` returned by `/api/v1/oauth2/session`. Platform routes, queries, and mutations use operation gates directly. Each Workspace and Knowledge Base feature normalizes backend-provided `accessRole`, `accessSource`, complete `accessSources`, and resource `allowedOperations`. An unknown operation, missing field, or malformed value fails closed. The frontend keeps only the known `OperationId` type and never maintains a role-requirement map or derives mutations from role rank.

Global entry points and create buttons are open to every active Member. User Management, Platform Resources, canonical Marketplace publishing and Registry, and Canvas publishing use Admin platform operations. Routes, queries, WebSockets, providers, dialogs, and mutations for an existing resource use backend `allowedOperations`. A structured authorization error or focus/visibility refresh reloads only the active authorization state. A downgrade that preserves read access keeps in-memory drafts but disables submission; complete revocation unmounts content, connections, and drafts. Primary Reader controls remain visible but disabled, with no tooltip or read-only banner, and cannot create a request, dialog, or session first.

## Folder Structure

```text
frontend/src/
  app/
    components/
      navigation/
    routes/
    providers/

  features/
    workspace/
      WorkspaceModule.tsx
      public.ts
      api/
      availability/
      config/
      deep-link/
      hooks/
      integrations/
      routes/
      layout/
        WorkspaceShell.tsx
        WorkspaceShellAdapter.tsx
        WorkspaceFeatureContent.tsx
        WorkspaceSidebar.tsx
        WorkspaceCompanionColumn.tsx
        hooks/
      model/
      providers/
      query/
      realtime/
      selection/
      services/
      storage/
      features/
        agent-settings/
        browser/
        canvas/
        container-management/
        file-management/
        version-control/
        workspace-settings/

    workspace-automation/
      AutomationModule.tsx
      public.ts
      routes/
      pages/
      components/
      hooks/
      api/
      model/
      providers/

    workspace-wizard/
      WorkspaceWizardPage.tsx
      public.ts
      components/
      hooks/
      model/
      services/

    ai-chat/
    auth/
    marketplace/
    knowledge-base/
    user-management/

  # Excerpt of shared paths relevant to this section
  shared/
    components/
      ui/
      layout/
      shell/
      markdown/
      monaco/
      split-pane/
      file-workbench/
      document-workflow/
      document-resource/
      hook-workflow/
      mcp-workflow/
      settings-workflow/
      resource-workflow/
      slash-command-picker/
      version-control/
    api/
    hooks/
    locales/
    services/
    utils/
    …
```

Workspace sub-domains are owned under `features/`; this architecture does not introduce a new layout engine, global state framework, Universal Editor, or Universal Workspace Controller.

`workspace/features/*` denotes private sub-features of the Workspace module, not a second tier of top-level features. Agent Settings, Canvas, Container Management, File Management, Version Control, and Workspace Settings all depend on Workspace routes, runtime, or Provider composition, so they stay at this layer. Only Workspace Automation — which has both an independent top-level entry and cross-module consumers — is promoted to `features/workspace-automation`.

### Workspace Root-Level Ownership

The Workspace root uses semantic folders by responsibility instead of one vague `types` or `utils` catch-all:

- `WorkspaceModule.tsx`: Workspace route composition; `public.ts`: the sole cross-module entry, exporting only proven external contracts.
- `api/`: Workspace lifecycle and runtime HTTP mapping; `storage/`: ProductShell layout and tab persistence.
- `availability/`: the fail-closed pre-mount guard and unavailable page; `config/`: deployment configuration for the browser extension.
- `layout/`: Workspace runtime gate, `WorkspaceShellAdapter`, ProductShell semantic regions, column content presentation, and pure layout models.
- `hooks/`: orchestration across Workspace sub-features, e.g. runtime, route sync, delete fallback, and Git context query adapters.
- `model/`: Workspace domain types and Git context; `services/` owns only the browser-extension pairing transport and is not a generic catch-all.
- `query/`: Workspace-wide query cache orchestration; does not hold feature-specific UI or HTTP mapping.
- `providers/`, `selection/`, and `realtime/`: Workspace state composition, the selected-workspace contract, and realtime event lifecycle, respectively.
- `routes/`, `deep-link/`, and `integrations/`: the URL adapter, external file-link resolution, and thin integration layers over other modules' public contracts, respectively.
- `features/`: Workspace-private domain implementation. Each nested feature may only reference its own internals, the Workspace root-level contract, global `shared`, or another top-level module's `public.ts`.

`features/workspace/features` does not establish a second public API layer. When two nested features need the same Workspace-specific query or orchestration, the minimal contract is promoted to the corresponding root-level folder (`hooks/`, `query/`, `providers/`, etc.) rather than resolved via sibling deep imports or nested barrels.

Provider state holds only UI, layout, navigation, file-management, and context contracts; HTTP response DTOs live in `api/workspaceApiTypes.ts` and are not mixed into Provider state types. General `useWorkspace` consumers obtain it through the `providers/WorkspaceProvider` façade; only the AI Chat integration and file chooser — which are composed by the Provider itself and would form a cycle through the façade — reference the same `WorkspaceContext` owner directly, without creating a second Context instance. The file tabs currently have only one file-management scope, so actions, Context, cache keys, and persistence do not retain a single-value scope abstraction; the Git context ID still isolates primary/worktree tabs, and `workspace_tabs_file-management_<workspaceId>_ctx_<contextId>` is the current key.

The Workspace root `realtime/` owns the Workspace WebSocket manager, terminal policy, xterm instance registry, and terminal store; container-management's React components only consume these domain contracts. `realtime/` does not reach back into `workspace/features/*`, and components do not each independently dispose of the same terminal instance.

### Workspace Layout Ownership

Workspace core presentation always lives in `features/workspace/layout`, not mixed into a generic `components/`:

- `WorkspaceShell.tsx`: the runtime full-page gate, retry/delete actions, and the mount boundary for `WorkspaceShellAdapter`.
- `WorkspaceShellAdapter.tsx`: resolves the Workspace surface, composes `ProductShellBody`, ProductShell preferences, the Version Control Provider, and the Realtime Provider.
- `WorkspaceFeatureContent.tsx`: second/main feature lazy mapping, Suspense fallback, and feature-specific content props; it does not own route or Provider state.
- `WorkspaceSidebar.tsx`, `WorkspaceCompanionColumn.tsx`: Workspace-specific column content presentation; ProductShell provides column geometry, resize, collapse, and fullscreen.
- `layout/hooks/useWorkspaceDocumentSelection.ts`: document dirty/blocked selection; `storage/workspaceShellLayoutStorage.ts`: Workspace layout-preference identity, payload, and persistence.
- `workspaceShellSurfaceModel.ts`, `workspaceSidebarModel.ts`, `agentToolNavigationModel.ts`: pure layout/navigation decisions; they hold no feature state.

`features/workspace/features/*` remains Workspace-private; only genuine core layout may enter `layout/` — a domain panel is not moved into this folder just because the Shell uses it.

### Workspace Wizard Boundary

Workspace Wizard is the pre-creation flow. Since a `workspaceId` does not yet exist, its legal entry is fixed at `/workspaces/workspace-wizard`. It does not depend on `app` internals: `app` only lazy-loads the page from `workspace-wizard/public.ts` and injects the global navigation slot and the authenticated user ID. Internally, the Wizard keeps its form contract in `model/`; steps reference their actual owner directly, without an `index.ts` barrel or an unused Module wrapper.

After the create API succeeds, `createdWorkspaceId` is the only creation result; a readiness retry only re-queries that ID and never POSTs to create another Workspace, without changing the four-step flow's DOM, classes, i18n keys, or normal navigation.

## Workspace Canonical Route

Workspace runtime identity always comes from the URL's `workspaceId`. The formal routes are:

```text
/workspaces/:workspaceId/home
/workspaces/:workspaceId/files
/workspaces/:workspaceId/version-control/:subView?
/workspaces/:workspaceId/workspace-settings/:subView?
/workspaces/:workspaceId/container-management/:subView?
/workspaces/:workspaceId/workspace-automation
/workspaces/:workspaceId/canvas
/workspaces/:workspaceId/browser
/workspaces/:workspaceId/:agentTool/:subView?
```

Routing rules:

1. `/workspaces` navigates to the currently selected workspace's canonical home; it enters the wizard only when there is no workspace.
2. Whenever a scoped route mounts, the selected workspace is synced from the URL's `workspaceId`.
3. Switching the workspace selector navigates to the new workspace's canonical home.
4. Route builders must explicitly receive `workspaceId`; they never infer it implicitly from global state.
5. Query and hash semantics remain unchanged; only feature routes that explicitly include `:subView?` support subviews.
6. `/workspace/*` is the external file-link resolver and is not part of the `/workspaces/...` application route family. It is the sole explicitly retained entry, resolves the file path, and immediately redirects to `/workspaces/:workspaceId/files?open=...`; it does not participate in any other application-route logic.

The only legal entries without a workspace ID fall into four categories:

| Path | Owner | Why No ID |
|---|---|---|
| `/workspaces` | Workspace selection | Resolves the current selection first, then navigates to canonical home or the Wizard |
| `/workspaces/workspace-wizard` | Workspace Wizard | No workspace ID exists before creation |
| `/automation` | Workspace Automation | A global dashboard across Workspaces |
| `/workspace/*` | External deep link adapter | Resolves a file path, then immediately navigates to the scoped files route |

Outside the four entry categories above, every Workspace feature route must include `workspaceId` and use one of the canonical route patterns listed above; route builders do not create other non-ID Workspace subpaths.

The global `/automation` is owned by the top-level `workspace-automation` module and deliberately excludes `workspaceId`; only `/workspaces/:workspaceId/workspace-automation` uses Workspace runtime identity. They are independent route families with separate owners.

## Workspace and Workspace Automation Boundary

`workspace/public.ts` exports only the stable contracts external consumers actually need:

- `loadWorkspaceModule`, for the app router to lazy-load legitimately, so the selection context does not force the entire Workspace chunk to load early.
- `WorkspaceSelectionProvider`, the selection hook, and the read-only `readSelectedWorkspaceId` contract, used by app composition, Global Navigation, and the Marketplace reader; the storage implementation stays private.
- `WorkspaceFileDeepLinkRoute`, for AppRouter to eagerly handle external `/workspace/*` file links without pulling in the full Workspace chunk.
- `fetchWorkspaceList`, for external consumers such as the Knowledge Base attachment candidate list to read a minimal Workspace list. The recent-workspace preference is not a Workspace domain API; it is served uniformly by `shared/api/recentWorkspaceApi.ts` for the Auth callback and the Workspace Provider.

The AI Chat integration adapter is composed inside Workspace; AI Chat does not import the Workspace public surface just to obtain runtime, the file chooser, or Canvas actions. It does not export full Provider state, reducer actions, layout models, or an arbitrary component barrel.

`workspace-automation/public.ts` exports only:

- `loadAutomationModule`, so AppRouter maintains Automation's lazy-loading boundary.
- `WorkspaceAutomationPage`, for Workspace's thin route adapter to compose the workspace-scoped view.

Workspace can render Automation only through this public surface. Workspace Automation never reaches back into Workspace internals; `workspaceId`, `runtimeBaseUrl`, and any needed capability are passed in as props by the route adapter.

The global `/automation` and the workspace-scoped Automation page share the feature-local `AutomationJobTable`, pagination, and execution controller; the scope adapter only expresses workspace-specific fields, copy, and differing cell DOM. Dialog chrome, page layout, and differing lifecycles stay separate — they are not forced together via a universal form or a large set of boolean variants.

The current Workspace Automation boundary is:

- `features/workspace-automation` is the only module; there is no compatibility re-export.
- AppRouter obtains `loadAutomationModule` only from the root `public.ts`; Workspace renders the workspace-scoped page only through the thin `WorkspaceAutomationRoute`, so there is a single route owner.
- The route adapter passes in only the workspace/runtime/locale contract; Workspace Automation does not import Workspace or App internals, and the AI Chat contract flows only through `ai-chat/public.ts`.
- The neutral runtime URL resolver lives at `shared/utils/runtimeUrl.ts`; the global and workspace pages share the feature-local job table and pagination, while data fetching, close lifecycle, dialogs, and page orchestration remain owned by each page.

## AI Chat Architecture

AI Chat is an independent module shared by the Workspace home route and the companion column. It does not import Workspace internals; Workspace injects runtime, file chooser, and Canvas integration, and Workspace Automation uses only the necessary contracts via `ai-chat/public.ts`. The module is classified as follows:

```text
features/ai-chat/
├── AiChatPage.tsx
├── api/
│   ├── threadApi.ts
│   ├── threadApiHttp.ts
│   └── threadQueryKeys.ts
├── attachments/
│   ├── attachmentConstraints.ts
│   ├── attachmentModel.ts
│   └── uploadChatAttachment.ts
├── components/
├── contexts/
├── events/
├── hooks/
├── model/
│   ├── questionFormModel.ts
│   ├── threadCapabilitiesModel.ts
│   ├── threadErrorNoticeModel.ts
│   ├── threadListModel.ts
│   ├── threadModel.ts
│   ├── threadSelectionModel.ts
│   ├── threadSettingsModel.ts
│   ├── threadStatusModel.ts
│   ├── threadTimelineModel.ts
│   └── threadTitleModel.ts
├── realtime/threadEvents.ts
├── storage/aiChatStorage.ts
└── public.ts
```

Classification rules:

- The route-visible component shown at Workspace `home/*` is always named `AiChatPage`; the public lazy loader is `loadAiChatPage`.
- API request types use `Payload`/`Query`; HTTP mapping and query keys live in `api/`; attachment kind, upload response, and operations are owned by `attachments/attachmentModel.ts`.
- The thread itself, capabilities, timeline, and other pure rules are split into `model/` by domain owner. The root does not re-create a meaningless `types.ts`, `utils.ts`, or `constants.ts`, and the module does not add nested barrels.
- `AgentMode` is a frontend TypeScript type name only; the serialized field `claudeMode` and its `execute`/`plan` values are the current contract. The five `aichat.*` storage keys, payloads, read order, and resulting values follow that same contract.
- Home and Companion share the pure precedence of `threadSelectionModel`; the caller supplies already-sorted/filtered threads, and the order of query, saved ID, and first item is unchanged. Page and Companion each own their own selection state, last-thread storage, and removal fallback.
- Pure data parsing, formatting, or error-notice decisions live in `model/*Model.ts`; `components/` holds only render, interaction, and Context/registry presentation owners. Pure models are not moved back into the components folder.

Shared adoption:

- AI Chat uses Shared Markdown, form/dialog primitives, collapsed sidebar controls, Shell width tokens, and the File Workbench drag payload; it does not redo these contracts inside the feature.
- The Home thread column is AI Chat feature-local content. It remains 320–560px, collapses to 64px, is mount-local, and has no separator ARIA; it does not declare a ProductShell region, keeping AI Chat's independent selection lifecycle out of the shared Shell.
- `WorkspaceFileChooserDialog` keeps its quick filter and immediate single-select behavior; it is not replaced by the full File Tree workflow with toolbar/search/multi-select/drag. AI Chat's git diff and the shared version-control diff have different parsers, grids, and loading/empty DOM, and are not forcibly merged.
- The outer Companion is owned by Workspace's ProductShell `companion` region. AI Chat supplies only content, tab, and capability mapping and does not create a second Shell. Message/Tool/Question Form components remain feature-local AI Chat owners.

The sole owner of query keys is `api/threadQueryKeys.ts`; keys needed across features are exposed only via the root `public.ts`. After it succeeds, `useThreads.patchDraft` writes to the canonical workspace-scoped cache the same way create, detail, and realtime do, using `aiChatThreadQueryKey(workspaceId, thread.id)`.

## Knowledge Base Architecture

Knowledge Base is the `/knowledge-bases` module, owning the knowledge base lifecycle, files, Git, sharing, workspace attachment, and settings; external consumers obtain only a lazy module loader or three genuinely cross-module types from the root `public.ts`.

```text
features/knowledge-base/
├── KnowledgeBaseModule.tsx
├── public.ts
├── adapters/
│   └── file-workbench/
│       ├── knowledgeBaseFileTreeDataAdapter.ts
│       └── knowledgeBaseFileWorkbenchAdapter.ts
├── api/
│   ├── knowledgeBaseApi.ts
│   └── knowledgeBaseVersionControlSnapshot.ts
├── components/
│   ├── KnowledgeBaseFilesTab.tsx
│   ├── KnowledgeBaseVersionControlTab.tsx
│   ├── KnowledgeBaseSharingTab.tsx
│   ├── KnowledgeBaseWorkspacesTab.tsx
│   ├── KnowledgeBaseSettingsTab.tsx
│   ├── KnowledgeBaseSidebar.tsx
│   ├── KnowledgeBaseCreateDialog.tsx
│   └── knowledgeBaseNavigation.ts
├── model/
│   ├── formatKnowledgeBaseFileSize.ts
│   ├── knowledgeBaseFileModel.ts
│   ├── knowledgeBaseShellModel.ts
│   └── knowledgeBaseTypes.ts
├── providers/KnowledgeBaseProvider.tsx
└── routes/
    ├── KnowledgeBaseListRoute.tsx
    ├── KnowledgeBaseCreateRoute.tsx
    └── KnowledgeBaseDetailRoute.tsx
```

Classification and naming rules:

- `KnowledgeBaseModule` only composes the Provider, the top-level shell, and nested routes; `KnowledgeBase*Route` is the URL adapter, and detail's visible panes always use `KnowledgeBase*Tab`. React owners use PascalCase; adapter/API/model/view metadata use semantic camelCase; folders use kebab-case.
- `components` holds only React presentation plus the Lucide icon/label metadata the sidebar uses directly. The Shared File Workbench adapter lives in `adapters/file-workbench`; route/navigation decisions live in `model/knowledgeBaseShellModel.ts`; repository status/branches/commits snapshot composition lives in `api/knowledgeBaseVersionControlSnapshot.ts`; file path logic (root, join, parent, name) and file API error/conflict logic live in `model/knowledgeBaseFileModel.ts` — the root `/` semantics differ from the shared tree model's `null` parent contract, so the feature keeps its own owner here.
- No root giant barrel, nested `public.ts`, empty folder, or compatibility re-export is created. App and Workspace consumers only enter `knowledge-base/public.ts`; when Knowledge Base needs a Workspace contract, it references only `workspace/public.ts`.
- Module, route, tab, and provider always use named exports. The Version Control lazy import on the detail route maps a named component into the default shape React.lazy needs, inside the feature, without restoring a component default export.

Shared adoption:

- The top level and detail are mapped to ProductShell by `KnowledgeBaseShellAdapter`. The Knowledge Base sidebar is `navigation` content; Files and Version Control provide `navigator` content as required by the surface, and the detail route owns main content.
- Files fully uses `FileManagementShell`, `FileManagementSidebarWorkflow`, `FileTreePanel`, the shared context menu/dialogs/archive overlays, and `FileViewerWorkbench`. Markdown, images, Mermaid, Drawio, and code are dispatched by the shared viewer; Knowledge Base retains only the API, revision, permission, archive polling, clipboard, and feature error contracts. Parsing the revision from a file operation response is owned uniformly by the shared `file-workbench`'s `adapters/fileResponseAdapter.ts` (`getFileOperationResponseRevision`), shared by Knowledge Base Files and the Shared `useFileTreeManager`.
- Knowledge Base and Workspace both obtain dialog state from `toFileManagementDialogState`, owned and exported by the Shared File Workbench workflow. The state each consumer passes to `FileManagementDialogs` matches field for field.
- Version Control's data query/types come from `@/shared/version-control`, and React presentation from `@/shared/components/version-control`; the feature does not redo the query factory, changes sidebar, diff viewer, or remote workflow.
- Knowledge Base does not provide a ProductShell `companion` region. Its arbitrary file tree, multiple tabs, archive, raw blob, and multi-format viewer are composed from Knowledge Base and File Workbench contracts without introducing the AI Chat quick chooser or an additional fixed document-workflow mode.

The route source-of-truth is `ROUTES.knowledgeBase`; the UI's workspace attachment pane always uses `workspaces(id)` and outputs `/knowledge-bases/:id/workspaces`. The Knowledge Base attachment HTTP endpoints remain `/knowledge-bases/:id/attachments`; the API, payload, and screen route are not mixed up.

## Marketplace Architecture

Marketplace is the `/marketplace` module, owning the package center, detail, canonical editor, settings, registry storage, Registry package CRUD/version-control lifecycle, and the current user's user-copy preflight/one-shot apply flow. After success, users manage the files themselves; the module maintains no enable, disable, update, reinstall, or uninstall lifecycle. App lazy-loads the module only through the root `public.ts`; when Marketplace needs Workspace selection or list contracts, it references only `workspace/public.ts`. `features/marketplace-*` are private sub-domains of the same module, not a second tier of top-level features, and are not flattened for formal symmetry.

```text
features/marketplace/
├── MarketplaceModule.tsx
├── public.ts
├── adapters/
│   ├── marketplaceFileTreeAdapter.ts
│   └── marketplaceFileWorkbenchAdapter.ts
├── api/marketplaceApi.ts
├── components/MarketplaceInstallOutput.tsx
├── model/
│   ├── marketplaceFeatureCounts.ts
│   ├── marketplaceFeatureLabels.ts
│   ├── marketplacePackageActionModel.ts
│   ├── marketplacePermissions.ts
│   └── marketplaceTypes.ts
├── storage/marketplaceStorage.ts
├── utils/downloadBlob.ts
└── features/
    ├── marketplace-center/
    │   └── MarketplaceCenterPage.tsx
    ├── marketplace-detail/
    │   ├── MarketplaceDetailPage.tsx
    │   ├── adapters/marketplaceReadonlyViewerAdapter.ts
    │   ├── components/
    │   └── model/
    │       ├── marketplaceDetailHookModel.ts
    │       └── marketplaceDetailNavigationModel.ts
    ├── marketplace-editor/
    │   ├── MarketplaceEditorPage.tsx
    │   ├── components/MarketplaceEditorHeader.tsx
    │   ├── dialogs/
    │   ├── resources/
    │   ├── marketplaceFileResourceModel.ts
    │   └── marketplaceHookModel.ts
    └── marketplace-settings/
        └── MarketplaceSettingsPage.tsx
```

Classification and naming rules:

- The four owners directly rendered by React Router always use `*Page`; reusable React presentation uses PascalCase `*Section`/`*Dialog`/`*Header`; pure rules use semantic camelCase `*Model.ts`; storage contracts live in `storage/`.
- The formal protocol abbreviation always uses `MCP` in TypeScript identifiers and filenames, including `MarketplaceMCPPage`, `MarketplaceEditorMCPSection`, and `marketplaceMCPServerDialogSchema.ts`; the serialized feature key `mcp`, the JSON field `mcpServers`, API payloads/URLs, and i18n keys use the lowercase contract.
- `MarketplaceCenterPage`, `MarketplaceDetailPage`, `MarketplaceEditorPage`, and `MarketplaceSettingsPage` reference only their own private sub-domain or the Marketplace root contract; sibling imports between the four nested features are forbidden, and no nested `public.ts`/`index.ts` is created.
- Detail-only components, the readonly adapter, hook projections, and navigation models belong to `marketplace-detail`; editor-only headers, the file resource model, and the Marketplace Hook parser/serializer/projection model belong to `marketplace-editor`. Only `MarketplaceInstallOutput`, shared by Center and Detail, and two verbatim-identical pure action helpers stay at the Marketplace root.
- The root is organized by responsibility into `api`, `adapters`, `components`, `model`, `storage`, and `utils`; no vague `constants.ts`, `types.ts`, or giant barrel is created. `'local-user'`, `'current-workspace'`, the three Marketplace storage keys, and the current → remembered → first option → sentinel resolution order are an immutable contract.
- Marketplace does not depend on `app` internals. The authenticated user ID, already held by `AppRouter`'s App state, is passed to the Settings Page through the Module as a required `string | null` prop; the feature does not read App context in reverse.

Shared adoption:

- Center/detail/editor/settings are mapped to ProductShell by `MarketplaceShellAdapter`; global navigation, responsive filters, detail tabs, and editor content are supplied to the appropriate semantic region.
- Detail's read-only file area and Editor Files use Shared File Workbench's tree, sidebar workflow, viewer tabs, code/markdown/image viewers, context menu, dialogs, and resize mechanics. Marketplace retains only the package API, revision, managed-root permission, path mapping, and resource mutation.
- Detail tabs, Center responsive filters, and the File Resource workflow retain their product-owned contracts. Marketplace does not provide a ProductShell `companion` region and does not create a second column-geometry implementation inside the feature.
- Detail's and Center's install/export/delete dialogs keep different owners and DOM. Only verbatim-identical command labels and error mapping are promoted to a Marketplace root pure model; no Universal Marketplace Dialog with a large set of boolean variants is created.
- The Marketplace Hook model includes resource items, Marketplace i18n, and native package JSON projection, and is not promoted to a provider-neutral Shared Hook contract; Detail tabs, Settings Version Control, and the Action Dialog also have no equivalent Shared DOM/state contract, so they are not forcibly replaced.

## Reuse Rules

Code is promoted to global `shared` only when it meets all of the following:

1. At least two independent production consumers use it; test references do not count. A workflow carrying domain semantics generally must span two modules; a domain-free foundational primitive can prove reuse through different production-owned shared packages/features.
2. The behavior and contract are the same, not merely similar in appearance.
3. Domain differences can be isolated through neutral props or an adapter.
4. Extracting it does not require a large number of boolean props or feature-specific branches.

A capability that repeats only within the same module first lives in module-local `components`, `hooks`, or `model`. Shared file-workbench, ProductShell, document-resource, and version-control workflows are not redone at the feature layer.

### Shared Root Classification and Dependency Boundaries

`src/shared` carries only neutral capabilities that do not depend on App, Pages, or any Feature. Shared has no giant root barrel; consumers reference a direct module or that package's public entry by capability. The root-level classification is:

| Category | Ownership | Should Not Contain |
|---|---|---|
| `api` | Cross-module, domain-neutral HTTP clients/adapters, e.g. the base API client, container image, and slash command APIs | Feature endpoints, queries, or mutations for Workspace, Settings, Marketplace, etc. |
| `components` | Primitives, layout, content platforms, and neutral workflows proven reusable across production ownership | Route, permission, runtime identity, or feature-specific orchestration |
| `constants` | Stable constants shared across the whole product, e.g. the canonical route contract | Sizes, states, filters, or query keys for a single feature |
| `contexts`, `hooks` | Product-wide runtime context and thin accessors, e.g. I18n, resolved theme, and container images | Feature stores, controllers, mutations, or one-layer convenience hooks |
| `design-system` | Global tokens, themes, and global selectors that genuinely have production consumers | Unreferenced selectors, feature-specific CSS, or display text |
| `locales` | Equivalent `en`/`zh-TW` key trees, shared terms, and translation sources classified by module semantics | Keys with no production resolver, or translation copies used only by tests |
| `realtime` | Neutral WebSocket connection lifecycle and registry mechanics | Feature event schemas, subscription policy, or domain reconnect orchestration |
| `services/logger` | The single cross-module service: a safe logging contract with module prefixes | A global mutable singleton, runtime level setter, token, auth code, verifier, or full authorization URL |
| `types` | Agentic tool, container image, I18n, slash command, and user contracts genuinely spanning two or more modules | Marketplace, Knowledge Base, Workspace, Settings, or Git owner types |
| `utils` | Small, stateless, domain-neutral helpers such as `cn`, OAuth PKCE, runtime URL, and type guards | File, version-control, or feature-specific formatters/policies |
| `version-control` | VC data contracts, fetchers, query factories, query keys, optimistic cache, and error mapping | React presentation, feature-scoped UI, or owner-specific Git context |

Version Control deliberately keeps two sibling entries rather than duplicating the implementation: `@/shared/version-control` is the UI-free data package; `@/shared/components/version-control` is the React presentation package. Dependencies only flow from presentation to data; data never depends back on components. Consumers that only need query, cache, or types avoid loading the UI dependency; consumers that need a screen use the component entry. Neither is merged into a giant barrel, nor moved purely for similar naming.

Dependency and public-entry rules:

1. `shared` may depend only on `shared`, third-party packages, and platform APIs; it never imports `app`, `pages`, or `features`.
2. Capabilities with a package boundary use named exports: Logger from `@/shared/services/logger`, VC data from `@/shared/version-control`, Shared Components from each package root. Imports inside a package are always relative.
3. `api/*`, `constants/*`, `contexts/*`, `hooks/*`, `types/*`, and small `utils/*` keep semantic direct entries; no root barrel is created for uniformity's sake.
4. Version Control's data entry is separate from the `shared/components/version-control` presentation entry; the UI barrel does not re-export query, optimistic update, error, or domain types.
5. File type, icon, size, and language detection are managed by the File Workbench/viewer owner; Knowledge Base keeps its own display formatter. Different display contracts are not merged just for "sharing".
6. Once a feature contract has only a single owner, it belongs in that feature's `api/`, `model/`, or `storage/`; no shared alias or compatibility re-export is kept.
7. Locale source files are named by module semantics, e.g. `workspaceAutomation.ts`; the runtime translation key follows the UI contract as `automation`. Any dynamic prefix must have its legal set enumerated by a resolver test.
8. Design System keeps only live tokens and selectors; before deleting CSS, JSX/TSX, class composition, the Markdown renderer, and dynamic class builders must all be confirmed to have no consumer.

Shared root filenames follow the same responsibility principle: a single React owner uses PascalCase; multi-symbol mechanics, API, model, adapter, storage, and utility modules use semantic camelCase; hooks use `useXxx`. No `common/`, `lib/`, `misc/`, vague `types.ts`/`utils.ts` is added, and no empty folder is created for symmetry.

### Shared Components Classification and Public Entries

`shared/components` is classified by stable responsibility, not named after the feature currently using it:

| Category | Folder | Ownership |
|---|---|---|
| Design-system primitives | `ui` | shadcn/Radix primitives and product-wide consistent base interactions |
| Presentation and layout primitives | `layout`, `shell`, `split-pane` | Domain-free header/collapsed presentation, multi-column slot/resize state, and generic split panes |
| Content platform | `markdown`, `monaco` | Markdown render/edit and Monaco integration; owns no feature query, route, or mutation |
| File workflow | `file-workbench` | File tree, adapters, archive, dialogs, sidebar workflow, viewer workbench, and split view |
| Document workflow | `document-workflow`, `document-resource` | Pure document-editing mechanics, plus source-backed document query/selection orchestration |
| Neutral domain workflow | `hook-workflow`, `mcp-workflow`, `settings-workflow`, `resource-workflow`, `slash-command-picker`, `version-control` | Interaction flows or presentation used by two or more production consumers with the same contract |

Folder and file rules:

1. Each first-level folder represents exactly one stable responsibility; no shared category is created named `common`, `misc`, or after a current feature name.
2. Small packages stay flat; only large packages use `model/`, `adapters/`, `hooks/`, `primitives/`, `tree/`, `viewer/`, `workflows/`, or `archive/` once responsibilities are clear. No empty folder is created purely for symmetry.
3. A file that is primarily a single owned React component uses PascalCase; vendor/shadcn primitives inside `ui` use kebab-case; an integration/mechanics module containing multiple symbols uses semantic camelCase. Hooks use `useXxx`; pure models, adapters, and storage also use semantic camelCase. No redundant `Shared` prefix is added inside `shared/components`.
4. A shared package may define an explicit public surface via a root `index.ts`; imports inside the package are always relative — it never routes back through its own barrel, and internal modules are never added to the barrel for convenience.
5. Modules still cross each other only through their root `public.ts`; a shared package's `index.ts` does not license deep imports into feature internals.
6. `ui/*`, `layout/*`, `markdown/*`, and `monaco/*` are direct-entry primitives/platform integrations and do not have a giant barrel; only other shared packages with a package entry are bound by the root-entry rule.

`file-workbench` deliberately offers two entries:

- `@/shared/components/file-workbench` is the lightweight main entry, providing tree, adapter, archive, dialogs, and the management workflow.
- `@/shared/components/file-workbench/viewer-entry` is the viewer secondary entry, providing `FileViewerWorkbench`, split view, viewer tab hooks, the corresponding type contracts, and `CodeTextEditor`; viewer context/toolbar stay package-internal.
- The main entry does not re-export the viewer implementation or viewer types; a consumer that needs viewer runtime or its contract must explicitly reference the secondary entry. No path beyond these two entries reaches into internal paths such as `viewer/*`, `tree/*`, or `workflows/*`.

Before adopting a shared component, all of the following must be confirmed:

1. At least two production modules need the same contract, and it is not merely a test or a future assumption.
2. DOM, class, ARIA, interaction, loading/error, keyboard, resize, persistence, and data-transformation semantics are identical.
3. Feature differences can be kept in a neutral prop, slot, or adapter boundary; if feature-name checks, a large number of boolean variants, or route/runtime knowledge are needed, it stays in the feature.
4. A shared contract is adopted directly when it satisfies the need; only a neutral gap needed by two or more production consumers justifies extending the minimal API.

The following responsibilities are explicitly not abstracted into shared:

- Feature routes, runtime identity, API clients, permissions, domain mutations, and feature-specific query identity; adapter-driven generic query orchestration may still be owned by a shared workbench.
- Workspace-specific three/four-column DOM, the 64px collapsed width, 300ms transition, fullscreen, bottom terminal, and feature-hide rules.
- Automation's fixed filter, Marketplace's responsive filter, and the File Chooser modal's lazy tree.
- User Management's detail/filter/pagination, Create User/Package/Knowledge Base dialogs, feature-specific PluginCard/Empty State, and the Workspace/Knowledge Base local-history UI.
- A feature wrapper, dialog chrome, toolbar, empty state, or presenter with only a single production consumer.
- Similar screens that could only be merged with a Universal Editor, Universal Workspace Controller, new layout engine, or schema-driven variant framework.

### File Management and Three/Four-Column Shared Contracts

These two large shared capabilities follow "reuse first, add only when necessary":

- The stable backbone of `shared/components/file-workbench` is the file-tree manager/adapter, `FileManagementSidebarWorkflow`, `FileManagementShell`, dialogs, `FileViewerWorkbench`, and split view. Workspace, Knowledge Base, Marketplace, and Agent Settings keep their own API adapters, permissions, domain mutations, and any necessary feature-specific orchestration such as runtime gating or clipboard/drag-drop.
- The public backbone of `shared/components/shell` is `ProductShell`, its region types, the preferences Adapter, and shared presentation primitives. ProductShell owns semantic-region layout state, resize, collapse, responsive behavior, overflow, and fullscreen; product Adapters provide content, behavior, presentation, and product-state mapping.

Adoption rules:

1. When DOM, class, ARIA, collapsed width, transition, resize, persistence, keyboard, drag/drop, loading/error, and adapter contracts are all identical, adopt the shared component directly.
2. Only a neutral gap needed jointly by two or more production modules justifies adding a minimal shared prop/slot.
3. The Workspace column has its own contract — 64px collapsed width, 300ms transition, feature hide, fullscreen, bottom terminal, and Version Control scope. The Workspace Adapter converts those limits into ProductShell region behavior, and ProductShell executes the geometry and interaction consistently.
4. Marketplace's file sidebar resize mechanics use `useResizableSidebar`: expanded width is 320 and collapsed width is 44; holding the separator from collapsed first shows 320, dragging starts from 240 and clamps to 240/520, and the DOM, class, and ARIA follow the same contract. The shared hook may accept a drag start width, but must not change the current visible width because of it.
5. `FileManagementSidebarWorkflow` and the feature runtime gate have exactly one `loadTree()` owner; a controlled manager is never loaded twice by two effects.
6. Automation's fixed filter, Marketplace's responsive filter, and the File Chooser modal tree are only superficially similar and do not adopt the file-management workflow or a declarative column framework.
7. Layout, toolbar, resolver, and barrel code with zero production callers that overlaps a live workflow is deleted directly, not kept for a future assumption.

The current production adoption and responsibilities are:

| Consumer | Shared Contract | Feature-Local Responsibility | Load Owner / Reason Not Adopted |
|---|---|---|---|
| Workspace Files | sidebar workflow, manager, tree panel, viewer workbench, split view | Runtime identity, clipboard, drag/drop, file mutations, version-control refresh | `loadEnabled=false`; the runtime-ready effect is the sole caller of `loadTree()` |
| Agent Settings | Managed sidebar workflow, viewer workbench | Runtime readiness and the settings-page API | The workflow receives a refresh signal; manager `autoLoad=false` |
| Knowledge Base Files | Page shell, second column, sidebar workflow, viewer workbench | Knowledge Base API, permission, rename/delete contract | `loadEnabled=true`; the workflow is the sole loader, manager `autoLoad=false` |
| Marketplace files | Second column/sidebar workflow/viewer workbench or read-only workbench | Marketplace provider API, read-only or editor mutation | The controlled manager directly satisfies the constrained generic; dialog-state generic narrowing stays at the render-body boundary |
| Workspace File Chooser | File-tree primitives | Modal preset filter, lazy expand, single-file immediate selection | Different interaction contract; the full sidebar workflow is not adopted |

ProductShell composes the three/four-column DOM from the `navigation`, `navigator`, `main`, and `companion` regions that are actually provided. Workspace, Knowledge Base, and Marketplace each supply product mapping through their Adapter and do not create another Shell implementation. Workspace's local `FileEditor` keeps only runtime, mutation, and split-view adapter orchestration — it does not duplicate the workbench.

Workspace-private file-tree orchestration always lives in `features/workspace/features/file-management/hooks`: the main adapter composes the manager, runtime identity, and hidden-file visibility; `workspaceFileTreeModel` does only pure mapping; the interaction hook handles selection, expand, collapse, and drag/drop; the mutation hook handles create, delete, copy, move, upload, download, read, save, and version-control refresh. These responsibilities are not promoted to `shared`, because they depend on Workspace runtime and the version-control domain; the shared manager's capabilities are also not redone here.

The Workspace reducer is split by action ownership into pure reducers for layout, navigation, version control, feature settings, and file management. The root reducer only dispatches via an exhaustive action map, keeping the same `WorkspaceState`/`WorkspaceAction`; slices never call each other, and no second store or mirrored state is added.

## Naming Rules

| Type | Rule |
|---|---|
| Top-level module/folder | kebab-case |
| Owned single React component/filename | PascalCase |
| Vendor/shadcn UI primitive | Uses the vendor-defined kebab-case |
| Multi-symbol integration/mechanics module | Semantic camelCase |
| Hook | `useXxx` |
| Top-level entry | `XxxModule` |
| URL/params adapter | `XxxRoute` |
| Route-visible screen | `XxxPage` |
| Full interactive workbench | `XxxWorkbench` |
| Single-format/content presentation | `XxxViewer` |
| Slot/column/structure that does not directly hold API mutation | `XxxShell` |
| Stateless CSS/size arrangement | `XxxLayout` |
| Reusable stateful flow | `XxxWorkflow` |
| Modal boundary | `XxxDialog` |
| React context owner | `XxxProvider` |
| State orchestration | `useXxxController` |
| Persistence/imperative lifecycle owner | `XxxManager` |
| Pure state/transform | `xxxModel` |
| HTTP mapping | `xxxApi` |
| Contract conversion | `xxxAdapter` |
| Persistence | `xxxStorage` |
| Abbreviations | Established brand/protocol abbreviations keep their formal spelling (e.g. `MCP`); ordinary in-word abbreviations use `Id`, `Url`, `Ssh` |

Top-level modules do not add a meaningless root `types.ts`, `utils.ts`, or `constants.ts`. API types use `Payload`, `Response`, `Query`; form data uses `FormValues`. Components and their filenames use PascalCase consistently; tests share the same name as their production subject. No `index.ts` barrel is added inside a module; the cross-module public entry is uniformly the root `public.ts`. A shared package uses an explicit `index.ts` only at the first package-root level; a necessary secondary entry must have a clear loading boundary, like `file-workbench/viewer-entry.ts`.

## Testing and Verification

Frontend tests and static verification always run inside a container:

```bash
docker compose -f frontend/docker-compose.test.yml run --rm frontend-test npm run test:run
docker compose -f frontend/docker-compose.test.yml run --rm frontend-test npm run typecheck
docker compose -f frontend/docker-compose.test.yml run --rm frontend-test npm run typecheck:shared
docker compose -f frontend/docker-compose.test.yml run --rm frontend-test npm run lint
docker compose -f frontend/docker-compose.test.yml run --rm frontend-test npm run build
docker compose -f frontend/docker-compose.test.yml run --rm frontend-test \
  npm exec --yes madge -- --extensions ts,tsx --ts-config tsconfig.json --circular src/shared
```

- The module dependency direction is continuously guarded by `src/architecture/frontendArchitecture.test.ts`, which parses import, import type, export, dynamic import, and `require` via TypeScript AST.
- i18n consistency is verified by `src/shared/locales/i18nIntegrity.test.ts`.
- The doc site is built separately with `--locale zh-Hant` and `--locale en`, and `.docusaurus` or `build` artifacts are never committed.

## Platform resource data boundaries

Platform Resources exposes Resource Management and Analytics as independent routes. Management routes load only inventory, filters, and mutations; analytics routes load summary, distribution, resource trend, and capacity trend, each with its own loading, error, and retry boundary. Management queries and analytics ranges live independently in their URLs. Chart wrappers remain feature-local and include keyboard- and screen-reader-accessible textual tables. Cross-layer ownership for Runtime telemetry, Manager ingestion, capacity policy, and the data session is defined in [Platform Resources and Runtime Telemetry Architecture](/architecture/overview/platform-resource-observability).
