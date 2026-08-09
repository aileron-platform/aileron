---
title: ProductShell and Semantic Product Regions
---

# ProductShell and Semantic Product Regions

This page defines the shared product workspace Shell for Workspace, Knowledge Base, and Marketplace. `ProductShell` is the only shared Shell interface. Each product resolves its routes, authorization, active feature, and content through an Adapter before passing semantic regions to the Shell. The Shell understands semantic regions, geometry, interaction state, and layout preferences; it does not understand product names or feature rules.

## Interface

`frontend/src/shared/components/shell/ProductShell.tsx` accepts these `ProductShell` props:

| Interface field | Responsibility |
|---|---|
| `topBar` | Global navigation content; optional |
| `header` | Product page header; optional |
| `body` | One of the `regions` or `state` Shell body shapes |
| `preferences` | Layout preference Adapter with identity, load, and save |
| `display` | Main-content expanded or Companion fullscreen state; optional |

`body.kind = 'regions'` requires `main` and may provide `navigation`, `navigator`, and `companion`. `body.kind = 'state'` provides one complete product state for loading, denied, or error content. The state remains inside `ProductShell`; a product Adapter does not bypass the Shell with an early return.

## Semantic regions

| Region | Interface responsibility | Optional | Content owner |
|---|---|---:|---|
| `navigation` | Product-level navigation and primary feature selection | Yes | Product Adapter |
| `navigator` | File tree, list, settings category, or operation entry for the active feature | Yes | Product Adapter |
| `main` | Primary content, detail, editor, or workbench | No | Product Adapter |
| `companion` | Chat, Terminal, or another supporting workspace | Yes | Product Adapter |

Each column region provides `content`, `behavior`, and `presentation`:

- `content` receives collapsed state and produces region content.
- `behavior` declares `collapsible`, `resizable`, `defaultWidth`, `minWidth`, and `maxWidth`.
- `presentation` provides the accessible label, chrome variant, responsive policy, and header slots.

A Companion additionally declares side and bottom size policies, `side | bottom` placement, collapsed content, collapse/expand/resize labels, and a reveal request id. The product supplies content and capability; the Shell executes placement, sizing, collapse, resize, and main-content coordination.

## Shell implementation

The `ProductShell` implementation owns all shared geometry and interaction:

- It composes the body from the actual `topBar`, optional `header`, `navigation`, `navigator`, `main`, and `companion` regions.
- It clamps widths and heights from region behavior and preserves a usable minimum main-content width and height.
- It manages column and Companion resize, collapse, responsive hiding, overflow, scrolling, focus cursor state, and fullscreen.
- It exposes stable test surfaces through `data-shell-region`, `data-shell-body`, and `data-shell-state`.
- `main-expanded` renders only the main content; `companion-fullscreen` renders only the Companion, with Escape handled by the display Adapter.
- Main and content containers use `min-w-0`, `min-h-0`, and local overflow boundaries so content cannot move horizontal scrolling to the document.

The Shell does not accept a product name, route, capability, resource role, API response, or feature-specific condition. Decisions requiring those facts belong in the product Adapter or product surface model.

## Layout preferences

`ProductShellPreferencesAdapter` is the external seam for Shell preferences:

```ts
interface ProductShellPreferencesAdapter {
  identity: string;
  load(): ProductShellPreferences | null;
  save(preferences: ProductShellPreferences): void;
}
```

The Shell uses `identity` for the active scope, loads the initial value, and saves layout changes with debounce. `ProductShellPreferences` stores collapsed, width, height, and placement for `navigation`, `navigator`, and `companion`; every loaded value is clamped by region behavior.

The product Adapter owns identity and persistence policy:

- Workspace uses Workspace runtime identity and the Workspace layout storage contract.
- Knowledge Base and Marketplace do not mount a preferences Adapter, so they use Shell defaults without persisting layout state.

## Product Adapters

### Workspace

`frontend/src/features/workspace/layout/WorkspaceShellAdapter.tsx` first resolves product state through `resolveWorkspaceShellSurface()` and then creates a `ProductShellBody`:

- `navigation` is the Workspace sidebar.
- `navigator` exists according to the active feature, sub-view, Reader capability, Terminal page, and main-expanded state.
- `main` is Workspace feature content.
- `companion` mounts when Runtime exists and Chat or Terminal capability is available. Terminal supports side or bottom placement, and Chat supports fullscreen.
- Workspace Provider, Version Control Provider, Realtime Provider, and File Workbench orchestration remain in the Workspace Adapter or its product owners; they do not enter the Shell.

`WorkspaceShellSurfaceModel` is a pure decision interface containing the active agent tool, navigator presence, main-expanded state, active Companion tab, Companion placement, and fullscreen result. It does not render DOM or execute API mutations.

### Knowledge Base

`frontend/src/features/knowledge-base/components/KnowledgeBaseShellAdapter.tsx` maps the Knowledge Base surface to `ProductShellBody`:

- List and detail content may provide `navigation`, `navigator`, and `main`.
- Loading, permission-denied, and error content uses `body.kind = 'state'` and can still provide a product header.
- Knowledge Base provides no Companion, so the Shell creates no empty Companion region.
- Knowledge Base route, query, permission, and API mapping for Files, Version Control, sharing, Workspace attachment, and settings remain in the Knowledge Base owner.

### Marketplace

`frontend/src/features/marketplace/components/MarketplaceShellAdapter.tsx` maps catalog, detail, editor, and settings surfaces to the same `ProductShellBody` interface. Marketplace provides no Companion.

The current Marketplace Settings region contract is:

| Region | Content |
|---|---|
| `navigation` | Settings categories; the active Version Control item expands the `changes` and `history` submenu |
| `navigator` | Complete general settings, SSH key, and activity content, or the Version Control branch, sync, file-changes, or history list |
| `main` | Version Control Diff or Commit detail; other settings do not create an empty third region |

The Version Control submenu is represented by `section=versionControl&submenu=changes|history`; missing `submenu` selects `changes`. Marketplace owns the route parser, query, selection, and authorization; the Shell only renders the resolved result.

## Content and state contract

A product Adapter must resolve route, resource role, platform operation, and Runtime availability before selecting regions or state:

- Unresolved data is not passed to the Shell for inference.
- `state` content fills the available main area and manages scrolling within its own boundary.
- An absent region creates no placeholder, empty column, or reserved space.
- Product capability models decide whether read-only controls are visible or disabled; the Shell does not authorize operations.
- i18n labels, ARIA labels, error messages, and operation copy come from product or shared locale contracts and are not hard-coded in the Shell.

## Module ownership and forbidden dependencies

| Module | May depend on | Must not own |
|---|---|---|
| `shared/components/shell` | Neutral region types, layout preferences, UI primitives, and i18n accessors | Product routes, feature names, resource roles, API queries, or product capabilities |
| Workspace Adapter | Workspace Provider, surface model, Workspace content, and Workspace preferences | A second column geometry system or product-owned resize handle |
| Knowledge Base Adapter | Knowledge Base route, permission, and content contracts | A Companion or another Shell implementation |
| Marketplace Adapter | Marketplace surface, settings route/query, and content contracts | A nested Shell, second mode rail, or product-owned column sizing |

Cross-product imports still use each feature's root `public.ts`. The Shell is not a transport for feature-domain data. Only genuinely neutral Shell types, preferences, and presentation contracts belong in shared.

## Source index

| Responsibility | Current owner |
|---|---|
| Shared Shell interface and implementation | `frontend/src/shared/components/shell/ProductShell.tsx`, `productShellTypes.ts` |
| Shared preference normalization | `frontend/src/shared/components/shell/productShellPreferences.ts` |
| Workspace surface decision | `frontend/src/features/workspace/layout/workspaceShellSurfaceModel.ts` |
| Workspace Adapter | `frontend/src/features/workspace/layout/WorkspaceShellAdapter.tsx` |
| Knowledge Base Adapter | `frontend/src/features/knowledge-base/components/KnowledgeBaseShellAdapter.tsx` |
| Marketplace Adapter | `frontend/src/features/marketplace/components/MarketplaceShellAdapter.tsx` |
| Cross-product visual/interaction fixture | `frontend/e2e/fixtures/product-shell.tsx`, `frontend/e2e/product-shell.spec.ts` |
| Architecture boundary test | `frontend/src/architecture/frontendArchitecture.test.ts` |

## Verification contract

The Shell test surface verifies both interface behavior and product Adapters:

- Shared unit tests cover region behavior, clamping, preferences, resize, collapse, placement, and fullscreen.
- Workspace, Knowledge Base, and Marketplace tests cover surface models, state bodies, region presence, and capability mapping.
- The Product Shell E2E fixture verifies region ownership, viewport boundaries, document overflow, dialog/menu boundaries, and shared product interaction.
- The frontend architecture test verifies that shared does not depend on features, features use public entries, and `ProductShell` is the cross-product Shell seam.
- All frontend tests, typecheck, lint, build, and E2E verification run in the project test container.

