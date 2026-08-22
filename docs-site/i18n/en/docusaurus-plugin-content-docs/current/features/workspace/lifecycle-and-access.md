---
title: Lifecycle and Access
---

# Lifecycle and Access

## Purpose and Entry Point

Enter from the workspace list, wizard, or lifecycle controls to create, start, stop, restart, reset, or permanently delete a workspace.

## Unified Entry Flow

The workspace entry projects three fixed stages in order: Identity, Workspace, and Execution. Protected Workspace Providers, queries, and execution-plane connections do not start until identity and workspace access are resolved; access revocation also fails closed.

All three stages use the same Entry Gate and fixed geometry. Brief waits do not show the progress panel; when it is shown, it remains visible for a minimum duration and the navigation position does not move. After the workspace opens, lazy feature loading uses an in-shell content skeleton instead of replacing the entire entry surface.

## Roles and Allowed Operations

Lifecycle operations require `workspace.lifecycle.execute` (manager); permanent deletion requires `workspace.delete` (owner).

## Core Concepts

Requested action, operation state, observed availability, and generation are distinct. Buttons use the API response’s current `allowedActions`.

### Execution-plane drift

A Workspace enters execution-plane drift when the control plane claims that the current generation is available but its Pods or containers are absent, partially missing, or have a mismatched identity. Drift does not mean that the Workspace has been deleted. Control-plane records, persistent data, and permissions remain intact; the platform neither rebuilds automatically nor deletes data merely because drift was detected.

During drift, the Entry Gate fails closed and does not mount Runtime, Thread, Terminal, Browser, Canvas, or any other execution-plane Provider, query, or WebSocket. An Owner with `workspace.delete` sees only the permanent-delete entry. Users without deletion permission are told to contact the Workspace Owner or platform administrator; start, retry, and rebuild are not offered.

## Primary Workflow

After submission, track durable state until observed state converges. The Owner submits one DELETE intent with the complete Workspace name, and the platform converges Automation cancellation, execution-plane cleanup, and deletion of Workspace control-plane records, persistent data, and permissions. An already absent Pod or container satisfies that cleanup item and does not block convergence of the remaining deletion scope.

Frontend reads availability through `GET /api/v1/workspaces/{workspaceId}/availability` and invokes only response-approved actions through `POST /api/v1/workspaces/{workspaceId}/availability/actions/{action}`.

## Permanent-deletion projection

Settings and the Availability Gate use the complete Workspace name for confirmation; the platform rechecks the current name when accepting the request and creates no deletion job when loading or matching the name fails. One in-flight intent exists per Workspace, duplicate requests reuse it, and only a failed attempt may be retried after reconfirming the name through the same DELETE endpoint. Other writes are locked after acceptance, and a timeout or partial cleanup is not success.

The Availability Gate exposes the backend-confirmed `deletion.phase` without a percentage. Deletion completes only when the Workspace is absent and the API confirms `404`; the frontend then clears queries, navigates to the fallback, and shows success. Failure preserves the Workspace and persistent data and exposes retry to the Owner. The Knowledge Base entity is always preserved; only the Workspace attachment relation is removed at the final deletion commit.

## View States and Read-only Behavior

The view projects loading, empty, error, denied, and lifecycle states as `pending`, `active`, `complete`, `action_required`, `uncertain`, and `failed`. Executable actions come only from the current API response’s `allowedActions`; `stopped` never starts automatically, `rebuild` requires explicit confirmation for normally recoverable failures, and execution-plane drift never offers rebuild. With read-only operations, readable content and normal mutation controls remain visible while mutations are disabled with an i18n reason. Without read access, protected queries, providers, and realtime connections do not start.

Control-plane or identity-service failures expose only a stable `reasonCode`; provider details, exception messages, and raw internal responses never reach the user interface. Background refresh does not reopen the Entry Gate. Switching workspaces clears old content before projecting the new workspace identity.

## Constraints, Failures, and Safety

A timeout, stale generation, or temporarily unobservable provider remains uncertain or retryable and never appears successful or immediately becomes execution-plane drift. Drift applies only after the current generation's workload is confirmed absent, partially missing, or identity-mismatched while no lifecycle job is active.

## Source Basis

<!-- workspace-availability-contract:start -->
<!-- generated by docs-site/scripts/check-workspace-availability-contract.mjs -->
| Stable reason code | Availability | Scope | HTTP | Retryable | Default authorized actions |
| --- | --- | --- | --- | --- | --- |
| `WORKSPACE_AUTHENTICATION_REQUIRED` | `blocked` | `workspace` | `401` | No | — |
| `WORKSPACE_ACCESS_DENIED` | `blocked` | `workspace` | `403` | No | `return` |
| `WORKSPACE_READY` | `ready` | `workspace` | `200` | No | — |
| `WORKSPACE_RUNTIME_ACCESS_RECYCLE_IN_PROGRESS` | `transitioning` | `workspace` | `423` | No | `return` |
| `WORKSPACE_RUNTIME_ACCESS_RECYCLE_FAILED` | `blocked` | `workspace` | `423` | Yes | `retry`, `rebuild`, `return` |
| `WORKSPACE_RUNTIME_STARTING` | `transitioning` | `workspace` | `423` | No | `return` |
| `WORKSPACE_RUNTIME_RESTARTING` | `transitioning` | `workspace` | `423` | No | `return` |
| `WORKSPACE_RUNTIME_STOPPING` | `transitioning` | `workspace` | `423` | No | `return` |
| `WORKSPACE_RUNTIME_STOPPED` | `stopped` | `workspace` | `423` | No | `start`, `return` |
| `WORKSPACE_RUNTIME_ERROR` | `blocked` | `workspace` | `423` | Yes | `retry`, `rebuild`, `return` |
| `WORKSPACE_RUNTIME_INSTANCE_UNAVAILABLE` | `blocked` | `workspace` | `423` | Yes | `rebuild`, `return` |
| `WORKSPACE_DELETING` | `deleting` | `workspace` | `423` | No | `return` |
| `WORKSPACE_NOT_FOUND` | `not_found` | `workspace` | `404` | No | `return` |
| `WORKSPACE_AVAILABILITY_ACTION_NOT_ALLOWED` | `blocked` | `workspace` | `409` | No | `return` |
| `WORKSPACE_AVAILABILITY_ACTION_ACCEPTED` | `transitioning` | `workspace` | `202` | No | `return` |
| `WORKSPACE_RUNTIME_INSTANCE_MISMATCH` | `transitioning` | `workspace` | `423` | No | `return` |
| `WORKSPACE_BROWSER_WORKLOAD_NOT_READY` | `ready` | `browser` | `423` | No | — |
| `WORKSPACE_EXECUTION_PLANE_DRIFT` | `blocked` | `workspace` | `409` | No | — |
| `WORKSPACE_EXECUTION_PLANE_OBSERVATION_UNAVAILABLE` | `transitioning` | `workspace` | `503` | No | — |
| `WORKSPACE_KB_MOUNT_SYNC_IN_PROGRESS` | `ready` | `knowledge_mount` | `409` | No | — |

### Workspace permanent-deletion projection

| Deletion phase | Availability | Allowed actions | Semantics |
| --- | --- | --- | --- |
| `queued` | `deleting` | — | The delete intent was accepted and is waiting for the deletion worker. |
| `cancelling_automations` | `deleting` | — | Cancel queued and running Automation and wait for a confirmed terminal result. |
| `stopping_runtime` | `deleting` | — | Stop the execution plane; do not remove the Workspace before stop is confirmed. |
| `deleting_resources` | `deleting` | — | Clean Workspace-owned resources and commit permanent deletion. |
| `finalizing` | `deleting` | — | Commit the final Workspace/Knowledge Base relation cleanup and verify completion. |

| Projection state | Availability | Allowed actions | Semantics |
| --- | --- | --- | --- |
| Deletion entry | `ready`, `transitioning`, `stopped`, `blocked` | `delete` | The Workspace exists; the Owner may submit the DELETE intent. |
| Failure outcome | `blocked` | `retry` | Preserve the Workspace and persistent data; the Owner may reconfirm the name and retry with DELETE. |
| Completion outcome | `not_found` | — | The Workspace returns 404; only this outcome permits query cleanup, fallback navigation, and success. |
<!-- workspace-availability-contract:end -->

- `frontend/src/features/workspace/WorkspaceModule.tsx`
- `workspace-manager/app/modules/workspace/availability.py`
- `workspace-manager/app/modules/workspace/`
- `contracts/workspace-availability.json`

## Related Architecture and APIs

- [execution-plane](/architecture/overview/execution-plane)
- [manager-api](/api/manager-api)
