---
title: Manager API
---

# Workspace Manager API

This page lists the primary endpoints currently registered by the application. The OpenAPI document for the deployed version remains authoritative for complete schemas and responses.

## Base URL

```text
/api/v1
```

Browser clients compose only this relative path on the current Platform Public Origin. Manager Service DNS and port remain deployment-internal.

## Authentication

Manager always requires generic OIDC authentication. There is no public `ENABLE_AUTH=false` setting or other authentication bypass. The JWT middleware validates protected requests. `/health`, `/health/oidc`, `/metrics`, `/docs`, `/redoc`, `/openapi.json`, and the OAuth2 flow are explicit authentication exemptions. OIDC issuer, audience, signature, lifetime, and optional ACR checks come from `OIDC_*` settings.

```http
Authorization: Bearer <jwt_token>
```

Manager does not authorize from the platform role in the JWT alone. It requires a valid, synchronized local user snapshot and evaluates every platform or resource operation through the central `AuthorizationOperationPolicy`. Workspace and Knowledge Base operations depend only on the effective resource role and are not intersected with platform feature permissions. See [Users, Groups, and Permissions](/features/platform/permissions-and-roles) for the complete contract.

## Health Check

Manager's `GET /health` is a deployment-internal probe, not a browser-visible API.

```json
{
  "status": "healthy",
  "service": "workspace-manager",
  "version": "<current-version>",
  "timestamp": "<ISO-8601 UTC timestamp>"
}
```

## Workspace Management

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/api/v1/workspaces` | List accessible Workspaces |
| `POST` | `/api/v1/workspaces` | Create a Workspace; `runtime` is required and a durable start job is created in the same transaction |
| `GET` | `/api/v1/workspaces/{workspace_id}` | Get Workspace details, revisions, and the current Runtime job |
| `PUT` | `/api/v1/workspaces/{workspace_id}` | Update Workspace settings; requires Workspace manager |
| `DELETE` | `/api/v1/workspaces/{workspace_id}` | Submit one permanent-deletion intent with complete-name confirmation; the platform converges Automation cancellation, stop, and deletion; requires Workspace Owner |
| `GET` | `/api/v1/workspaces/{workspace_id}/sensitive-settings` | Get masked sensitive-setting state; requires Workspace Reader or higher |
| `PUT` | `/api/v1/workspaces/{workspace_id}/sensitive-settings` | Preserve, clear, or replace sensitive settings; requires Workspace Manager or higher |

Public create and update payloads do not accept `provisioner`, `targetNamespace`, `setupScript`, `envVars`, or `acpCliArgs`. The deployment configuration selects the provisioner, and public APIs cannot change it after creation.

Workspace lists, summaries, and details use a safe allowlist projection and never return setup scripts, environment variables, ACP arguments, credentials, tokens, or headers. Successfully authorized resource responses include `accessRole`, `accessSource`, complete `accessSources`, and backend-generated `allowedOperations`; the frontend must not reconstruct an operation matrix from roles.

Sensitive-settings GET responses expose only masks and `isConfigured` for secrets, never plaintext. In PUT, an omitted field is preserved, explicit `null` clears it, and a supplied value replaces it; a mask cannot be submitted as a new value. Request and response logs, error details, and audit metadata are redacted.

### Durable Lifecycle

| Method | Path | Description |
| --- | --- | --- |
| `POST` | `/api/v1/workspaces/{workspace_id}/start` | Return `202` and create or redeliver `workspace_start` |
| `POST` | `/api/v1/workspaces/{workspace_id}/stop` | Return `202` and create or redeliver `workspace_stop`; retain the Workspace CR and PVC |
| `POST` | `/api/v1/workspaces/{workspace_id}/components/{component}/restart` | Return `202` and increment only the selected component revision; `component` is `runtime`, `browser`, or `canvas` |

A lifecycle response contains:

```json
{
  "workspaceId": "<workspace-id>",
  "status": "running",
  "component": "browser",
  "targetRevision": 3,
  "jobId": "<job-id>",
  "correlationId": "<correlation-id>",
  "rootCorrelationId": "<root-correlation-id>"
}
```

Start, stop, retry, rebuild, and component restart require Workspace Manager or higher. Permanent deletion requires the actual Owner. After a DELETE intent is accepted, the platform completes it independently; duplicate requests reuse the in-flight attempt, and only a failed attempt may be retried after reconfirming the name. Success requires confirmed Workspace absence. Restarting one component does not replace another component's workload identity.

## Knowledge Base Attachments

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/api/v1/workspaces/{workspace_id}/knowledge-bases` | List every Workspace attachment and mount-sync state |
| `POST` | `/api/v1/workspaces/{workspace_id}/knowledge-bases` | Create a read-only attachment; returns `202` |
| `PATCH` | `/api/v1/workspaces/{workspace_id}/knowledge-bases/{attachment_id}` | Change the alias; returns `202` |
| `DELETE` | `/api/v1/workspaces/{workspace_id}/knowledge-bases/{attachment_id}` | Build a complete candidate with `pending_removal`; returns `202` |
| `POST` | `/api/v1/workspaces/{workspace_id}/knowledge-base-mount-sync/retry` | Retry a failed mount revision; returns `202` |
| `GET` | `/api/v1/knowledge-bases/{kb_id}/attachments` | Let a KB manager inspect visible usages, total count, and hidden count |

Create-attachment request:

```json
{
  "kbId": "<knowledge-base-uuid>",
  "mountAlias": "product-docs"
}
```

Change-alias request:

```json
{
  "mountAlias": "runbooks"
}
```

The payload has no `mode` field, and extra fields are rejected. Every Runtime mount is read-only. There are no KB-centric attachment `POST`, `PATCH`, or `DELETE` routes.

A mutation response contains the attachment and synchronization state:

```json
{
  "attachment": {
    "id": "<attachment-id>",
    "kbId": "<knowledge-base-id>",
    "mountAlias": "product-docs",
    "status": "pending"
  },
  "knowledgeBaseMountSync": {
    "status": "syncing",
    "desiredRevision": 3,
    "observedRevision": 2,
    "lastKnownGoodRevision": 2,
    "errorCode": null,
    "compensating": false
  }
}
```

See [Workspace and Knowledge Base Permissions](/features/knowledge-base/sharing-and-permissions) for permission and delegated-grant semantics.

## Runtime Access and Browser Pairing

### Instance-Bound Runtime Access

```http
GET /api/v1/workspaces/{workspace_id}/runtime-access?action=<action>&runtimeInstanceId=<current-id>
Authorization: Bearer <token>
```

Allowed actions are `runtime_read`, `runtime_write`, `workspace_settings`, `terminal`, `agent`, `automation`, and `browser_automation`. Central policy maps each action to a Workspace OperationId. Before returning `204`, the service checks an active principal, current `allowedOperations`, Runtime access revision, lifecycle state, and generation. Reader receives only a safe read projection; mutation and execution actions require Manager or higher. A syncing or degraded KB mount does not globally block Runtime access.

Common rejections:

| HTTP | Error Code | Meaning |
| --- | --- | --- |
| `403` | `WORKSPACE_RUNTIME_ACTION_FORBIDDEN` | Current Workspace operations do not permit the action |
| `422` | `WORKSPACE_RUNTIME_ACTION_INVALID` | The action or `runtimeInstanceId` is missing or malformed |
| `423` | `WORKSPACE_RUNTIME_ACCESS_RECYCLE_IN_PROGRESS` | The access revision has not converged |
| `423` | `WORKSPACE_RUNTIME_ACCESS_RECYCLE_FAILED` | Access recycling failed |
| `423` | `WORKSPACE_RUNTIME_INSTANCE_MISMATCH` | The caller is not the current generation |

### Browser Extension Pairing

```http
POST /api/v1/workspaces/{workspace_id}/browser-extension-pairing-assertions
Authorization: Bearer <token>
```

The request has no body. Manager checks the current actor, generation, and Browser workload identity with `browser_automation`, then returns an Ed25519-signed, single-use pairing assertion with a maximum 60-second lifetime:

```json
{
  "assertion": "<compact-jws>",
  "runtimeInstanceId": "<current-generation-id>"
}
```

The response sets `Cache-Control: no-store` and `Pragma: no-cache`. Never place an assertion in a URL query, database, job metadata, browser storage, or log.

## Other Workspace Endpoints

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/api/v1/workspaces/{workspace_id}/runtime-logs` | Get Runtime logs |
| `GET` | `/api/v1/workspaces/{workspace_id}/availability` | Get control-plane availability, its stable reason, and permitted recovery actions |
| `POST` | `/api/v1/workspaces/{workspace_id}/availability/actions/{action}` | Run a recovery action permitted by the availability response |
| `GET` / `PUT` | `/api/v1/workspaces/{workspace_id}/firewall` | Get or replace the Workspace firewall desired state |
| `POST` | `/api/v1/workspaces/{workspace_id}/firewall/retry` | Retry failed firewall convergence |
| `POST` | `/api/v1/workspaces/{workspace_id}/browser/access` | Get a Browser relay credential; requires Workspace Manager or higher |
| `POST` | `/api/v1/workspaces/{workspace_id}/browser/credentials/rotate` | Rotate the current Browser workload credential |
| `GET` / `POST` | `/api/v1/workspaces/{workspace_id}/shares` | List or add user or group shares; accepts only Reader or Manager |
| `PATCH` / `DELETE` | `/api/v1/workspaces/{workspace_id}/shares/{share_id}` | Update or remove one share |

Browser access accepts only evidence with `status.browserConnectivity.state=ready`, a valid expiry,
and matching revisions. `pending`, `degraded`, and `not_ready` map to
`409 BROWSER_CONNECTIVITY_NOT_READY`. `unavailable`, or ready evidence found expired at admission time,
maps to `503 BROWSER_CONNECTIVITY_UNAVAILABLE`. Neither response includes a Browser credential. Clients
use bounded retries and never bypass the gate through another endpoint.

A successful response contains `browserUrl`, the Neko `password`, `credentialRevision`, and `iceServers`.
For a `turnRest` profile, `iceServers` contains a short-lived username and credential scoped to that
access. The frontend uses it to create the `RTCPeerConnection` and never substitutes cached or Neko
startup ICE settings.

`/health` only means the Manager HTTP process responds; `availability` is the authoritative
control-plane gate for one Workspace execution plane. A client may run only actions returned by
the availability response. Firewall `PUT` means only that the desired state and durable command
were persisted; it does not prove that policy was applied. Continue reading firewall state until
`syncStatus` becomes `applied` or `error`. See
[Execution-Plane Lifecycle and Safety](/architecture/overview/execution-plane) for the complete state and
recovery contract.

`runtime-logs` queries persisted provisioning and lifecycle events; it does not stream container
stdout. It accepts `limit` (default `100`, range `1`–`500`) and an optional exact `stage` filter,
then returns entries from newest to oldest by `createdAt`:

```json
[
  {
    "id": "<log-id>",
    "workspaceId": "<workspace-id>",
    "stage": "provisioning",
    "message": "<localized-message>",
    "metadata": {},
    "createdAt": "2026-07-27T12:00:00Z"
  }
]
```

For actual Runtime container or Pod stdout, use the Docker or Kubernetes log commands in
[Deployment Troubleshooting](/installation/troubleshooting.md#workspace-component-state-is-inconsistent).

## Workspace Settings

| Method | Path | Minimum authorization | Description |
| --- | --- | --- | --- |
| `POST` | `/api/v1/workspaces/{workspace_id}/setup/sync` | Workspace Manager | Start Workspace initialization synchronization |
| `GET` | `/api/v1/workspaces/{workspace_id}/setup/status` | Workspace Reader | Get Workspace initialization synchronization state |
| `GET` | `/api/v1/workspaces/temp/setup/git-branches?git_url=...` | Active Member | Query remote Git branches before creation |
| `GET` / `PUT` | `/api/v1/users/{user_id}/settings` | Self | Read or update the caller's personal settings; another `user_id` in the path is denied |
| `POST` | `/api/v1/users/{user_id}/ssh-keys/generate` | Self | Generate and store the caller's SSH key pair |
| `POST` / `GET` | `/api/v1/users/{user_id}/settings/codex/*` | Self | Manage the caller's Codex sign-in state |
| `POST` | `/api/v1/users/{user_id}/settings/sync` | Self and Manager of every target Workspace | Sync personal settings to every manageable, running Workspace Runtime |
| `POST` | `/api/v1/users/{user_id}/settings/sync/{workspace_id}` | Self and Workspace Manager | Sync personal settings to Runtime |

Every role can manage its own personal settings, Codex sign-in, and SSH key. Background Runtime convergence runs only when current Workspace `allowedOperations` permit a settings mutation; otherwise Manager stores only the personal setting.

## Container Images

| Method | Path | Minimum authorization | Description |
| --- | --- | --- | --- |
| `GET` | `/api/v1/container-images` | Active Member | List available Workspace Runtime container images |
| `GET` | `/api/v1/container-images/{image_id}` | Active Member | Get image details |
| `POST` | `/api/v1/container-images/reload` | Platform Admin | Reload the platform-wide image list |

## OAuth

Manager provides two OAuth route groups. `/api/v1/oauth/*` manages agent-integration credentials,
while `/api/v1/oauth2/*` is the platform login BFF. Only Manager performs Authorization Code + PKCE,
provider token exchange, and validation. The Browser holds only an opaque HttpOnly session.

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/api/v1/oauth/info` | Get provider OAuth configuration |
| `POST` | `/api/v1/oauth/exchange` | Exchange an authorization code for a token |
| `POST` | `/api/v1/oauth/authenticate` | Authenticate with OAuth and save credentials |
| `POST` | `/api/v1/oauth/refresh` | Refresh an existing OAuth token |
| `GET` | `/api/v1/oauth/health` | Check OAuth service health |
| `GET` | `/api/v1/oauth2/login` | Create an OIDC transaction and redirect to the provider |
| `GET` | `/api/v1/oauth2/callback` | Exchange the code, validate the provider response, and create an opaque session |
| `GET` | `/api/v1/oauth2/session` | Get local user, `platformRole`, `allowedOperations`, expiry, and a memory-only CSRF token |
| `POST` | `/api/v1/oauth2/logout` | Validate session, Origin, and CSRF, then revoke the local session |

The Manager Session created by a successful callback is continuing authentication evidence. During
a valid Session, protected APIs use only the local Session, User, and operation policy without IdP
calls. Missing, expired, revoked, or principal-mismatched Sessions return
`401 MANAGER_SESSION_REQUIRED`, and Frontend starts OIDC reauthentication once. A denied local user
or platform operation returns `403 PLATFORM_AUTHORIZATION_DENIED`, preserves the Session, and does
not trigger reauthentication.

## Marketplace

Marketplace manages package import, editing, installation entry points, and Registry version control. See [Marketplace](/features/marketplace) for the full workflow.

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/api/v1/marketplace/packages` | List packages |
| `POST` | `/api/v1/marketplace/packages` | Create a package |
| `GET` / `PUT` / `DELETE` | `/api/v1/marketplace/packages/{provider}/{package_id}` | Get, update, or delete one package |
| `DELETE` | `/api/v1/marketplace/packages/{provider}/{package_id}/draft` | Discard a package draft |
| `GET` | `/api/v1/marketplace/packages/{provider}/{package_id}/export` | Export a package |
| `POST` | `/api/v1/marketplace/packages/refresh` | Refresh the package-list cache |
| `POST` | `/api/v1/marketplace/import/scan` | Scan a local source for import candidates |
| `POST` | `/api/v1/marketplace/import/upload` | Upload files for package import |
| `POST` | `/api/v1/marketplace/import` | Import scanned or uploaded candidates into the Registry |
| `POST` | `/api/v1/marketplace/plugins/install` | Publish a package to the deployment's configured Git origin (private GitLab is required by the standard deployment), then run the provider's standard plugin installation CLI in the target Workspace |
| `POST` | `/api/v1/marketplace/user-copies/preflight` | Read-only planning for a one-shot user-scope merge, including resources, duplicates, and blockers |
| `POST` | `/api/v1/marketplace/user-copies` | Apply a one-shot merge with the preflight digests and user-approved overwrites |
| `GET` / `PUT` | `/api/v1/marketplace/settings` | Get or update Marketplace settings |
| `GET` | `/api/v1/marketplace/activities` | Filter and paginate Marketplace activity by `workspaceId`, `provider`, `packageId`, `action`, and `status` |

### Plugin Installation Contract

`POST /api/v1/marketplace/plugins/install` accepts `provider`, `packageId`, the package `revision`, and `workspaceId`. Manager publishes that revision to a provider-compatible Git origin. The standard deployment requires that origin to be a private GitLab repository, but the service does not query GitLab or validate repository visibility. Manager's registry SSH key is not passed to Runtime, so the target Runtime must have its own credentials for reading the repository. Runtime then executes the standard Claude Code or Codex CLI installation flow. The terminal result contains `status`, `stage`, `exitCode`, `cliMessage`, `stdout`, `stderr`, and `truncated`. Provider CLI terminal output is authoritative for success and error details.

The endpoint only completes that publication and CLI command. It does not create Aileron installation, ownership, drift, reconciliation, uninstallation, or cleanup state. Users manage the plugin afterward through the native provider CLI.

### Copy to User Scope Contract

User-copy is a one-shot merge into user scope. The caller must first invoke `POST /api/v1/marketplace/user-copies/preflight`. Its status is `ready`, `confirmation-required`, or `blocked`, and it includes:

- `resources`: resources that would be created, merged, or left unchanged.
- `conflicts`: duplicate resources that require explicit overwrite confirmation.
- `blockingIssues`: problems that prevent the operation from proceeding.
- `sourceDigest`, `profileDigest`, and `materializationDigest`: digests that bind the package content, Runtime profile, and materialized result observed during preflight.

To apply the merge, `POST /api/v1/marketplace/user-copies` requires the package and Workspace identity plus `expectedSourceDigest`, `expectedMaterializationDigest`, and the user's `overwriteApprovals`. If the source or target state changed after preflight, the service rejects the apply and requires a new preflight. A successful response includes the operation identity, status, Provider, package, Workspace, and the created, merged, unchanged, and overwritten counts.

Success leaves no installation row, source tracking, ownership, drift, reconciliation, uninstallation, cleanup, or background lifecycle. Files and settings become ordinary user-managed resources. Marketplace will not reclaim user-copy content when the source package is edited or deleted.

Marketplace also has a separate Git version-control API under `/api/v1/marketplace/version-control/*`, including status, stage, unstage, commit, commits, diff, branches, remote, fetch, pull, push, clone, force-unlock, Git identity, and SSH keys. It manages the package Registry itself. Its semantics resemble the Knowledge Base Git endpoints but operate on a different resource.

Members can read the catalog, install, and manage their own user-scope copy. Canonical publishing, management, deletion, Registry, and Canvas publishing require Platform Admin. See [Marketplace](/features/marketplace) for the complete contract.

Activity responses use `{ items, total, page, pageSize, totalPages }`, ordered stably by `createdAt DESC, id DESC`. Status is either `succeeded` or `failed`. Activity is an audit trail, not authoritative installation or lifecycle state.

## Automation Jobs

One asyncio scheduler in the Manager process scans PostgreSQL for Automation schedules, while Workspace Runtime executes them through a claim and complete contract. These APIs do not use Celery for scheduling. Celery worker and Beat form a separate path for durable Workspace jobs such as start, stop, restart, delete, KB mount synchronization, access recycling, Manager Session expiry cleanup, and KB quota reconciliation. See [Execution-Plane Lifecycle and Safety — Durable Jobs and Recovery](/architecture/overview/execution-plane#durable-jobs-and-recovery) for claim, lease, and heartbeat convergence.

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/api/v1/automation/jobs` | List Automation jobs |
| `POST` | `/api/v1/automation/jobs` | Create a job |
| `GET` | `/api/v1/automation/jobs/{job_id}` | Get a job |
| `PATCH` | `/api/v1/automation/jobs/{job_id}` | Update a job |
| `DELETE` | `/api/v1/automation/jobs/{job_id}` | Delete a job |
| `POST` | `/api/v1/automation/jobs/{job_id}/pause` | Pause a scheduled job |
| `POST` | `/api/v1/automation/jobs/{job_id}/resume` | Resume a scheduled job |
| `POST` | `/api/v1/automation/jobs/{job_id}/run` | Start a manual job execution |
| `POST` | `/api/v1/automation/webhook/{job_id}` | Trigger a job through its configured webhook |
| `GET` | `/api/v1/automation/jobs/{job_id}/executions` | List job executions |
| `GET` | `/api/v1/automation/executions` | List visible executions across jobs |
| `GET` | `/api/v1/automation/executions/{execution_id}` | Get one execution |
| `POST` | `/api/v1/automation/executions/{execution_id}/cancel` | Cancel an execution |
| `GET` | `/api/v1/automation/metrics` | Get Automation summary metrics |
| `GET` | `/api/v1/automation/calendar` | Get Automation calendar data |

## User and Group Management

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/api/v1/users` | Search for users that can receive a share |
| `GET` | `/api/v1/users/{user_id}/profile` | Get a user profile (read-only) |
| `GET` / `PUT` | `/api/v1/users/me/recent-workspace` | Get or update the most recently used Workspace |
| `GET` | `/api/v1/admin/users` | List local user snapshots with server-side query, filters, sorting, and pagination |
| `GET` | `/api/v1/admin/users/roles` | List the two assignable platform roles, `admin` and `member`, and their i18n keys |
| `GET` | `/api/v1/admin/users/{user_id}` | Get one local user snapshot |
| `PUT` | `/api/v1/admin/users/{user_id}/role` | Replace the complete platform role |
| `GET` / `POST` | `/api/v1/admin/user-groups` | List or create User Groups |
| `GET` / `PATCH` / `DELETE` | `/api/v1/admin/user-groups/{group_id}` | Get, update, or delete a User Group with a transactional cascade |
| `GET` / `POST` | `/api/v1/admin/user-groups/{group_id}/members` | List or add group members |
| `GET` | `/api/v1/admin/user-groups/{group_id}/member-candidates` | Query member candidates with server-side filtering |
| `POST` | `/api/v1/admin/user-groups/{group_id}/members/batch-remove` | Remove multiple group members |
| `DELETE` | `/api/v1/admin/user-groups/{group_id}/members/{user_id}` | Remove one group member |

Every `/api/v1/admin/users*` and `/api/v1/admin/user-groups*` endpoint requires a valid, fresh `admin` platform role. Manager creates a user on first successful OIDC token validation; the admin API does not create provider accounts, handle passwords, or call a provider-admin API. `PUT /api/v1/admin/users/{user_id}/role` replaces only the local platform role and is protected by audit and the last-usable-admin invariant.

### Server-Side List Contract

User, group, group-member, and candidate lists return the same pagination envelope:

```json
{
  "items": [],
  "total": 0,
  "page": 1,
  "pageSize": 25
}
```

`page` starts at 1 and `pageSize` is at most 100. The database performs search, filtering, sorting, total calculation, and pagination. Callers must not fetch a fixed first 25 rows and paginate them locally. Unknown query keys, duplicate keys, invalid CSV enums, booleans, sorting, or page values return stable invalid-page error codes.

Batch member addition returns `{addedUserIds, skippedUserIds, failedUsers}` and batch removal returns `{removedUserIds, skippedUserIds, failedUsers}`. Request `userIds` must contain 1 to 100 unique local user IDs. Existing or already removed entries appear in `skippedUserIds`, while unauthorized or nonexistent entries appear individually in `failedUsers`.

See [Users, Groups, and Permission Model](/features/platform/permissions-and-roles) for complete platform roles, User Group, direct Knowledge Base, and Workspace grant semantics.

## Platform Resources

Only Platform Admin can use the separate global-resource API. Normal Workspace and Knowledge Base lists never mix in every platform resource.

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/api/v1/platform-resources/workspaces` | Query safe Workspace summaries and Owner projections with `q`, `page`, and `pageSize` |
| `GET` | `/api/v1/platform-resources/knowledge-bases` | Query safe Knowledge Base summaries and visibility with `q`, `page`, and `pageSize` |
| `POST` | `/api/v1/platform-resources/workspaces/{workspace_id}/owner-reassignment` | Reassign a Workspace Owner |
| `POST` | `/api/v1/platform-resources/knowledge-bases/{knowledge_base_id}/owner-reassignment` | Reassign a Knowledge Base Owner |

Owner reassignment request:

```json
{
  "targetUserId": "<existing-manager-user-id>",
  "reason": "<3-500 character audit reason>"
}
```

The target must be active, authorizable, and already have a Manager relationship to the resource. On success, an active previous Owner becomes Manager; a disabled previous Owner loses access. The service records before-and-after audit data in the same flow, then notifies the previous Owner and publishes access recycling for affected Workspaces after commit. Notification or recycle publication failures use stable error codes; committed ownership is not rolled back to the previous Owner.

## Error Formats

Attachment, Runtime access, and lifecycle contracts use stable error codes, usually in the FastAPI `detail` object:

```json
{
  "detail": {
    "errorCode": "KB_MOUNT_ALIAS_INVALID",
    "correlationId": "<correlation-id>"
  }
}
```

User Admin and User Group APIs always use a top-level envelope:

```json
{
  "errorCode": "USER_ADMIN_INVALID_REQUEST",
  "correlationId": "<correlation-id>",
  "details": {
    "fields": ["email"]
  }
}
```

`details` is present only for safe validation contexts. It never includes passwords, tokens, raw OIDC-provider responses, or exception payloads. Workspace and Knowledge Base authorization denials always use this structure:

```json
{
  "detail": {
    "errorCode": "WORKSPACE_OPERATION_DENIED",
    "message": "localized message",
    "details": {}
  }
}
```

Authorization status semantics are fixed: unauthenticated requests return `401`; requests for a missing resource or from a caller with no visible resource relationship return `404`; and requests for a visible resource whose operation is not allowed return `403`. Callers must branch only on `errorCode` and map it to i18n. They must not parse or directly display backend `message` or `details`. Other non-authorization endpoints continue to follow their own OpenAPI contracts.

| Status | Description |
| --- | --- |
| `200` / `201` / `202` / `204` | Success, created, accepted, or no response body |
| `400` / `422` | Invalid request shape or field contract |
| `401` | Unauthenticated or invalid control-plane assertion |
| `403` | Resource is visible, but the requested operation is not allowed |
| `404` | Resource is missing, IDs do not match, or the caller has no visible relationship |
| `409` | Lifecycle, attachment, or deletion conflict |
| `423` | Execution plane is converging or has failed closed |
| `500` / `503` | Server or required dependency unavailable |

<!-- authorization-contract:workspace:start -->
<!-- generated by docs-site/scripts/check-authorization-contract.mjs -->
| OperationId | Minimum resource role | Platform Admin only | Description |
| --- | --- | --- | --- |
| `workspace.detail.read` | `reader` | `false` | Reader or higher can read Workspace details. |
| `workspace.content.write` | `manager` | `false` | Manager or higher can mutate Workspace content. |
| `workspace.lifecycle.execute` | `manager` | `false` | Manager or higher can execute complete lifecycle operations. |
| `workspace.metadata.write` | `manager` | `false` | Manager or higher can update metadata. |
| `workspace.access.manage` | `manager` | `false` | Manager or higher can manage direct and group shares. |
| `workspace.attachment.write` | `manager` | `false` | Manager or higher can manage Knowledge Base mounts. |
| `workspace.firewall.read` | `reader` | `false` | Reader or higher can view the firewall. |
| `workspace.firewall.manage` | `manager` | `false` | Manager or higher can manage the firewall. |
| `workspace.sensitive_settings.read` | `reader` | `false` | Reader or higher can view masked sensitive settings. |
| `workspace.sensitive_settings.manage` | `manager` | `false` | Manager or higher can update sensitive settings. |
| `workspace.terminal.use` | `manager` | `false` | Manager or higher can use Terminal. |
| `workspace.agent_chat.use` | `manager` | `false` | Manager or higher can use AI Chat. |
| `workspace.automation.execute` | `manager` | `false` | Manager or higher can execute Automation. |
| `workspace.browser_automation.use` | `manager` | `false` | Manager or higher can use Browser automation. |
| `workspace.delete` | `owner` | `false` | Only the actual Owner can permanently delete a Workspace. |

| Error code | Description |
| --- | --- |
| `WORKSPACE_ACCESS_DENIED` | Stable authorization error code `WORKSPACE_ACCESS_DENIED`. |
| `WORKSPACE_OPERATION_DENIED` | Stable authorization error code `WORKSPACE_OPERATION_DENIED`. |
| `WORKSPACE_DELETE_CONFLICT` | Workspace deletion conflicts with the current lifecycle state. |

| Platform Resources error code | Description |
| --- | --- |
| `PLATFORM_RESOURCE_INVALID_REQUEST` | Invalid Platform Resources request fields or shape. |
| `PLATFORM_RESOURCE_NOT_FOUND` | The specified Workspace or Knowledge Base was not found. |
| `PLATFORM_RESOURCE_OWNER_NOT_FOUND` | The current Owner identity was not found. |
| `PLATFORM_RESOURCE_TARGET_NOT_AUTHORIZABLE` | The target user is invalid, disabled, or has a non-authorizable identity snapshot. |
| `PLATFORM_RESOURCE_TARGET_MANAGER_REQUIRED` | The target user does not already have a Manager relationship to the resource. |
| `PLATFORM_RESOURCE_OWNER_UNCHANGED` | The target user is already the current Owner. |
| `PLATFORM_RESOURCE_OWNER_NOTIFICATION_FAILED` | Ownership was committed, but notifying the previous Owner failed. |
| `PLATFORM_RESOURCE_ACCESS_RECYCLE_FAILED` | Ownership was committed, but publishing access recycling failed. |
<!-- authorization-contract:workspace:end -->

## Platform resource statistics and capacity API

Platform Admins can read independent Workspace or Knowledge Base `summary`, `resource-trend`, and `capacity-trend` endpoints. A failure in one endpoint does not become a page-wide error. Governance APIs update or reset Knowledge Base quotas and create or inspect Workspace capacity expansions. Users with `workspace.detail.read` can call `/workspaces/{workspaceId}/capacity?range=7d`. Runtime batch ingest uses internal identity validation. See [Platform Resource Statistics and Capacity Governance](/features/platform/resource-statistics-and-capacity).
