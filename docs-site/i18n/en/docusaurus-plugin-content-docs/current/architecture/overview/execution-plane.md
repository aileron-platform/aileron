---
title: Execution-Plane Lifecycle and Safety
---

# Execution-Plane Lifecycle and Safety

This document describes the internal convergence mechanisms, durable-job model, and security boundaries shared by the Workspace execution plane (Runtime, Terminal, Browser, and Canvas) across lifecycle transitions, Knowledge Base mounts, permission revocation, Browser pairing, and related scenarios. For user-visible behavior such as states, buttons, and common scenarios, see [Workspace Lifecycle](/features/workspace/lifecycle-and-access) and [Workspace and Knowledge Base Permissions](/features/knowledge-base/sharing-and-permissions). For clarification of the management-server inside the Canvas workload that parses manifests and starts renderers, see [Canvas Protocol](/architecture/overview/canvas/protocol).

:::info Implementation and platform verification status
This page describes the portable contract shared by the application, Docker, Workspace CR, Operator, and Helm. Helm rendering, security assertions, arbitrary-UID image preflight, and local tests are only prerequisites; they do not constitute certification on EKS, GKE, AKS, OCP, RKE2, or upstream Kubernetes. Every target environment still requires the conformance runner on the actual cluster, CSI version, CNI, and security policy.
:::

## Control-Plane Availability Gate

Before mounting any Workspace execution-plane Provider, the frontend queries a Manager endpoint that does not depend on a Runtime Pod, Ingress, or WebSocket:

```http
GET /api/v1/workspaces/{workspaceId}/availability
```

File, Git, Terminal, Agent, Thread, Browser, and Canvas queries or connections may be created only when `availability=ready`. While initial availability is unresolved, the frontend hides the notice card behind a 500 ms delay but keeps the gate closed. A notice shown after that threshold remains visible for at least 500 ms on the ready path; known non-ready states and errors bypass the minimum duration. Every other state mounts only a notice page and one Manager availability observer. The observer polls according to bounded `retryAfterMs` and does not automatically retry stable `401`, `403`, `404`, `409`, or `423` responses. If availability is lost mid-session, the observer first cancels execution-plane queries for that Workspace, unmounts Providers, and closes WebSockets before navigating to the notice page. After recovery, it must use the latest `runtimeInstanceId`; it must not reuse an invalidated generation URL, query cache, or credential.

Manager returns `allowedActions` only after authorization. `start`, `retry`, and `rebuild` use this control-plane endpoint; `return` only navigates the frontend back to a safe list and does not call the execution plane. Permanent deletion is not folded into the ordinary lifecycle action list; the availability response's `deletionProjection` expresses the Owner-only `delete`/`retry` actions, backend-confirmed `deletion.phase`, and `404` completion:

```http
POST /api/v1/workspaces/{workspaceId}/availability/actions/{action}
```

### Execution-Plane Drift

Execution-plane drift means that the control plane still claims the current generation is available while that generation's Runtime, Browser, or Canvas Pod or container is absent, partially missing, or has a mismatched workload identity. It is neither Workspace deletion nor temporary provider unobservability. Drift applies only when no lifecycle job is active and the platform has confirmed that physical workloads do not match the current generation.

Drift is a Workspace-wide fail-closed state. The Availability Gate unmounts execution-plane Providers, cancels their queries, and closes WebSockets so the Gateway does not continue forwarding requests to stale hostnames. The platform does not rebuild automatically, does not delete the Workspace database automatically, and offers no start, retry, or rebuild action. The Owner receives only the permanent-delete entry; other users receive only guidance to contact the Owner or platform administrator.

Workspace DELETE applies idempotent absence semantics to missing workloads: an absent Pod or container counts as cleaned, and the workflow continues deleting the remaining execution-plane resources, Workspace control-plane records, persistent data, and permissions. Only an explicit DELETE intent crosses this irreversible boundary; observing drift does not authorize data deletion.

### Frontend Entry Projection Boundary

The frontend projects current facts from identity confirmation, Workspace authorization, and the availability machine into one fixed three-stage Entry Flow: Identity, Workspace, and Execution. This projection does not replace any authority and does not parse provider responses or raw exception messages; the UI exposes only finite statuses, current `allowedActions`, and stable `reasonCode` values.

The Entry Gate does not mount execution-plane Providers, queries, or WebSockets until Workspace authorization and availability are resolved. Only a ready state with a valid generation is handed to the Workspace Shell; subsequent feature lazy loading remains inside the shell content region. Ordinary availability refresh does not take over an already mounted shell. Confirmed revocation, a Workspace identity change, or a failed generation fence clears the old execution plane and re-enters the Gate.

`stopped` is never started automatically by the frontend, `refresh` only re-reads availability, and `rebuild` requires user confirmation. All lifecycle mutations remain governed by the Manager API's `allowedActions` and the existing authorization contract.

Permanent deletion uses `DELETE /api/v1/workspaces/{workspaceId}`; after acceptance, the platform converges Automation cancellation, stop, and delete in order. During deletion the Gate shows phase progress only, failure preserves the Workspace and exposes Owner retry, and `not_found` is the completion signal.

A `401/403` response must not disclose lifecycle, revision, or workload identity. Browser readiness blocks only Browser. KB mount syncing/degraded state affects only `/knowledge` and mount management. Neither condition may incorrectly classify an otherwise healthy Workspace as globally unavailable.

### Machine-Readable Fail-Closed Contract

The table below is generated from `contracts/workspace-availability.json`. Manager, Frontend, and documentation share the same availability values, scopes, stable reason codes, and default authorized actions. Actual buttons still depend only on `allowedActions` returned by the current API response.

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

### Gate Boundaries and Recovery

| Condition | Gate boundary | Notice and recovery |
| --- | --- | --- |
| Access desired/observed revision differs while recycle is active | Global | Show that access is being updated, poll automatically, and do not connect to Runtime |
| Access revision differs and recycle failed | Global | Show the stable reason; offer only authorized retry/rebuild/return |
| Runtime is starting/restarting/stopping | Global | Show the corresponding progress, poll automatically, and create no feature connection |
| Runtime is stopped | Global | Manager, Owner, or Platform Admin may start; Reader may only return |
| Runtime error or unavailable instance | Global | Show the stable reason; offer retry, rebuild, or return as authorized |
| Workspace is deleting | Global | Show deletion in progress; return to a safe page when complete |
| Workspace does not exist | Global | Show missing or deleted without disclosing stale state |
| Request generation differs from current `runtimeInstanceId` | That execution-plane request, followed by reevaluating the global gate | Clear the invalidated generation and refetch availability; after ready, return to the original subroute |
| Browser workload is not Ready | Browser only | Browser shows a component-level notice; other features remain available |
| KB mount is syncing/degraded or its revision has not converged | KB only | KB shows a degraded banner and stable error; core Workspace features remain available |
| Principal is invalid, role is insufficient, or Workspace permission is absent | Global | Show access denied without returning internal Workspace state |

## Durable Jobs and Recovery

Lifecycle, Knowledge Base mount reconciliation, and access recycle use the same durable-job repository:

- State is `queued`, `running`, `succeeded`, `failed`, or `superseded`.
- Every claim has a lease, heartbeat, and new fencing token.
- A newer queued revision terminates the superseded queued lineage, then creates a successor with its own correlation root.
- If a mutation arrives while a job is running, retain the running row and the latest queued successor. If desired state advanced by the time the earlier job completes, it may only be marked `superseded`.
- If broker publication fails, a worker crashes, or a lease expires, a recovery sweep redispatches or reclaims the job.
- A stale claim token cannot perform a destructive side effect or commit observed state.

Celery is used by the execution layer, but a Celery message is not the source of correctness. A worker receives only `job_id` and always rereads the target revision and complete desired state from PostgreSQL. One Celery Beat performs periodic recovery/dispatch. Duplicate delivery still converges to one side-effect owner through the DB claim token, lease, heartbeat, and Workspace lock. This Celery path does not schedule Automation; Automation uses Manager's asyncio/PostgreSQL scheduler.

## Component Revision Convergence

A Workspace represents target and actual state with four desired/observed revision groups: bootstrap, Runtime, Browser, and Canvas. A durable job stores `targetComponent` and `targetRevision`; the worker rechecks the database fence both before and after execution. An earlier revision may only become `superseded`; it cannot overwrite the latest state.

| Event | Revision changed | Scope |
| --- | --- | --- |
| Initial creation | Bootstrap and all three components | Browser and Canvas are released only after Runtime/Terminal are ready |
| Restart Runtime | Runtime | Replace Runtime/Terminal only |
| Restart Browser | Browser | Replace Browser only |
| Restart Canvas | Canvas | Replace Canvas only |
| Attach/detach KB or change alias | Mount candidate and Runtime | Runtime validates the candidate without replacing Browser/Canvas |
| Revoke a Runtime operation | Access and Runtime | Runtime converges access without replacing Browser/Canvas |

A component restart follows this order: increment desired revision and create the component job in one transaction, acquire side-effect ownership with a claim lease, terminate only the targeted workload, create a new workload for that component, verify identity and readiness, then advance observed revision. Failure of Browser or Canvas puts only that component in `Error`; it does not delete the Workspace CR or reclaim healthy sibling components.

Terminal and the agent run inside the Runtime workload; they are not a fourth Deployment or container. If termination of the specified workload cannot be proven, that component remains in `error` and observed revision does not advance.

An attachment mutation accepted while `stopped` or in lifecycle `error` stores the complete candidate snapshot and desired revision for convergence on the next start; attaching does not automatically start the Workspace. New attachment mutations are rejected while `stopping` or `deleting`.

### Last-Known-Good Mount Saga

Every attach, rename, or detach derives a complete `candidate_snapshot` from the last validated `active_snapshot`. Before writing the candidate, Manager validates alias, KB UUID, authorization, PVC/subPath, directories, symlinks, and collisions. Desired revision, audit, and durable job are written in the same transaction as the candidate.

After Runtime/Operator applies the candidate, Manager promotes it to the new active snapshot and advances observed revision only when both the readiness probe and mount verification succeed. Failure preserves the current active snapshot, records a `failed_snapshot` and stable error code, and enters compensation. It is marked degraded only after the active snapshot is confirmed usable. Neither “API accepted” nor “Runtime restart complete” means that the mount was applied.

The Attachment API and Workspace detail expose last-known-good state:

```json
{
  "knowledgeBaseMountSync": {
    "status": "degraded",
    "desiredRevision": 12,
    "observedRevision": 11,
    "lastKnownGoodRevision": 11,
    "errorCode": "WORKSPACE_KB_MOUNT_RECONCILE_FAILED",
    "compensating": false
  }
}
```

The generic Runtime access gate validates the effective principal, the Workspace OperationId mapped from the endpoint action, current `allowedOperations`, lifecycle readiness, access generation, and current `runtimeInstanceId`. Reader receives only a safe read projection; mutation and execution actions require Manager, Owner, or Platform Admin:

```http
GET /api/v1/workspaces/{workspace_id}/runtime-access?action=<action>&runtimeInstanceId=<current-runtime-instance-id>
Authorization: Bearer <token>
```

Mount revision is no longer a global access gate for files, version control, Terminal, Agent, Thread, Browser, or Canvas. Only `/knowledge` and mount-management calls explicitly use the knowledge-mount gate. Ordinary Workspace detail still returns `200` while syncing/degraded, allowing the UI to show localized stable errors, last-known-good revision, and legal recovery actions.

Direct or group share changes, group membership changes, account, Owner, Platform Admin, or Public KB consumer access changes increment generation. Cached URLs and assertions immediately become invalid, and execution-plane sessions that are no longer allowed terminate.

## Zero-Copy Read-Only Mounts

Each Knowledge Base has exactly one canonical filesystem copy:

```text
Canonical KB root
├── <kb-a>/
├── <kb-b>/
└── <kb-c>/
       │
       ├─ Workspace Manager: RW, manages canonical content
       │
       └─ Workspace Runtime: individually mounted RO
          ├── /knowledge/product -> <kb-a>
          └── /knowledge/runbook -> <kb-c>
```

The system creates no Workspace copy and uses no materializer, projector, KBFS sidecar, NFS namespace controller, custom CSI, or FUSE.

### Docker

Manager has RW access to the canonical KB root. Runtime bind-mounts only the validated `<kbId>` host directories at `/knowledge/<alias>`, with every bind mount fixed to `read_only=true`.

### Kubernetes

Manager and Runtime use the same `Filesystem + ReadWriteMany` KB PVC:

- Manager mounts the canonical root with write access.
- Runtime creates `subPath=<kbId>` for each attachment.
- Every Runtime `volumeMount` is fixed to `readOnly: true`.
- Manager, Operator, Workspace CR, Runtime, and PVC reside in the same platform-managed `workspaceRuntimeNamespace`/OpenShift Project.

PVC access mode describes provisioning and scheduling capability, not in-container read-only enforcement. The actual boundary remains `volumeMount.readOnly`.

## Runtime PostgreSQL and Credential Boundary

Runtime state is not written to Workspace/NFS and does not share Manager's platform-table permissions. Every Workspace has a dedicated schema in Manager's PostgreSQL database, derived from Workspace ID and retained across restarts. Every Runtime instance uses a different login. Manager derives the instance password with an HMAC key mounted only into Manager; Runtime never receives that derivation root key.

A Runtime instance login is not a platform DB administration account. It has no `SUPERUSER`, `CREATEDB`, `CREATEROLE`, `INHERIT`, `REPLICATION`, or `BYPASSRLS`; it receives only database `CONNECT`, and its default `search_path` is fixed to its own Workspace schema plus `pg_temp`. The platform grants it no access to Manager tables in the `public` schema. When a new Runtime instance becomes active, Manager terminates connections from the superseded login, transfers ownership of that Workspace schema, and disables and deletes the superseded login.

`AILERON_RUNTIME_CONTROL_TOKEN_FILE` is a separate boundary. Its read-only file contains an opaque token scoped to one Runtime instance, and plaintext is given only to that Runtime. Manager stores only a digest in the database and validates Workspace ID, current Runtime instance, and lifecycle state together. It can call only that Workspace's Manager automation-control endpoints. It is neither a user access token nor a cross-Workspace or platform-wide token.

Kubernetes maintains one `Opaque` Runtime Secret for each Workspace with exactly these values:

| Secret key | Runtime environment variable | Purpose |
| --- | --- | --- |
| `state-database-url` | `AILERON_RUNTIME_STATE_DATABASE_URL_FILE` | PostgreSQL login for the current Runtime instance and fixed Workspace schema |
| `runtime-control-token` | `AILERON_RUNTIME_CONTROL_TOKEN_FILE` | Opaque token for that Workspace's automation-control endpoints |

Only the Runtime container mounts this Secret as a read-only volume, and `*_FILE` variables point to its files. Browser and Canvas receive none of it. Manager's credential-derivation key, Ed25519 private key, platform database credential, and Redis credential are never placed in this Secret. Docker uses the same read-only Secret-file contract.

Lifecycle handling of schema, login, token, and Secret is:

| Event | PostgreSQL schema | Runtime instance login/token | Kubernetes Runtime Secret |
| --- | --- | --- | --- |
| Start | Create if absent; reuse if present | Create a new login and opaque token | Create or update with exactly two fixed keys |
| Runtime component restart | Preserve data and the same schema | Terminate superseded connections and rotate login, password, and token | Update with the new Runtime revision's values |
| Browser/Canvas component restart | Preserve | Unchanged | Unchanged |
| Stop | Preserve for the next start | Terminate connections, set login to `NOLOGIN`, and clear the current token fence | Preserve together with Workspace CR and PVC |
| Delete Workspace | After the target workload is proven absent, run `DROP SCHEMA ... CASCADE` | Terminate connections and delete all Runtime-instance roles for that Workspace | Delete |
| Provisioning failure | Do not expose Runtime entry | Disable the failed Runtime-instance login and token fence | Delete the failed Runtime instance's Secret |

Runtime restart therefore preserves Runtime data while rotating credentials. Browser and Canvas restarts do not touch Runtime database credentials. Stop preserves the CR, PVC, and schema; only delete removes persistent data.

## Browser Connectivity Evidence Ownership

Browser component readiness and Browser TURN connectivity are separate states. Pod probes prove that the
Neko process can serve requests. Operator derives `status.browserConnectivity` from two data paths: backend
relay evidence produced by a sidecar inside the Browser Pod and required external-vantage evidence retained
by Connectivity Evidence Gateway. Every evidence item binds the TURN Reachability Profile revision,
credential revision, observation time, and expiry.

Operator is the only connectivity-state writer. Manager projects CR status into Workspace detail and the
database, then checks `ready` and freshness only when admitting new Browser access. With `turnRest`, Manager
uses the installation-managed shared secret to issue Workspace-scoped, short-lived `iceServers` for every
Browser access. The sidecar inside each Browser Pod also issues fresh short-lived credentials for every
backend probe, with the probe identity bound to the Workspace ID. The Neko container never receives the
TURN REST shared secret.

Frontend never infers TURN readiness. It overrides Neko's startup ICE configuration with the `iceServers`
from the access response and creates one Neko generation for that access during the current visibility
period. On failure, bounded, serialized, fresh-access recovery replaces the entire generation, so every
replacement passes admission again and receives new credentials. A healthy existing session is not
forcibly terminated when later evidence expires.

The source boundaries are `workspace-operator/internal/controller/browser_connectivity.go`,
`workspace-operator/internal/controller/turn_probe.go`,
`workspace-operator/internal/controller/connectivity_evidence_gateway.go`,
`workspace-manager/app/modules/workspace/browser_credential_access.py`,
`workspace-manager/app/modules/workspace/browser_turn_credentials.py`, and
`frontend/src/features/workspace/features/browser/hooks/useBrowserAccessRecovery.ts`.

## Browser Extension Pairing Safety

The Chrome extension never holds a Manager service token, drain private key, or long-lived pairing token. The flow is:

1. The user actively connects from the Workspace UI. Manager first validates the effective principal, the intersection of platform/Workspace roles, access revision, and Browser workload identity for the `browser_automation` action.
2. Manager signs a pairing assertion valid for at most 60 seconds, using Ed25519/EdDSA and a single-use `jti`. Claims bind actor, Workspace, `runtimeInstanceId`, Browser container ID/Pod UID, pairing session, audience, and expiration.
3. The frontend sends an external message only to the extension ID fixed at deployment. When no extension ID is configured, the connection entry is hidden. The extension manifest permits only explicitly configured trusted frontend origins; non-loopback sources must use HTTPS.
4. The pairing assertion is never placed in a URL query, DB, job metadata, browser storage, or log. The extension retains a pending assertion only in memory, transmits it through `Sec-WebSocket-Protocol` while creating the WebSocket, and consumes it immediately.
5. Runtime validates signature, `kid`, issuer, audience, action, Workspace, current `runtimeInstanceId`, expiration, and single-use `jti` through read-only JWKS, then binds the complete signed identity to that relay socket.
6. A second valid extension socket replaces the previous connection. Disconnect, Browser replacement, or access revocation clears the socket, pairing identity, pending CDP requests, and user relay connection. Assertions for invalidated Browser identities, expired assertions, and replayed assertions are always rejected.

The Browser workload may be replaced independently within the same `runtimeInstanceId`. Manager fences identity using Browser desired/observed revision, workload identity, and current Runtime instance together.

## Ed25519 Key Deployment Prerequisites

The Docker development flow creates an Ed25519 private key and public JWKS in the host data directory. Kubernetes does not generate keys for a production environment; two Secrets must already exist in `workspaceRuntimeNamespace`:

| Helm value | Required Secret key | Mounted by |
| --- | --- | --- |
| `runtimeAssertions.privateKeySecretName` | `private-key.pem` | Manager only |
| `runtimeAssertions.publicKeySetSecretName` | `jwks.json` | Manager for pairing validation; Runtime/Terminal for assertion validation |

`runtimeAssertions.activeKid` must exist in the JWKS, and its public key must match `private-key.pem`. If a file is missing, `kid` is duplicated, the active `kid` is unknown, the private key appears in JWKS, or the key pair does not match, Manager refuses to issue an assertion so drain/pairing fails closed. Runtime/Terminal also rejects assertions when JWKS validation cannot succeed.

## Kubernetes Workload Identity Boundary

Each Workspace's Runtime, Browser, and Canvas share one dedicated `workspace-workload-<workspaceId>` ServiceAccount. It has no Role or RoleBinding. The ServiceAccount and all three Pod templates set `automountServiceAccountToken: false`, so code inside a Workspace cannot use a Kubernetes ServiceAccount token as an additional source of authority.

This ServiceAccount isolates Kubernetes API identity only. It does not alter Workspace/KB application authorization or grant additional NFS capability. File visibility remains controlled by “Workspace attachment grant + read-only Runtime `subPath` mount.” NFS/CSI access remains controlled by the PVC, node mount, effective UID/fsGroup, and backend export policy.

Dynamic Workspace Ingress is disabled by default. In that mode, the three workloads can still communicate through cluster-internal Services, and Operator removes Runtime/Browser/Canvas Ingresses. Enabling or disabling Ingress does not require rebuilding the Workspace execution plane. For the external entry point, independently verified StorageClass, and deployment configuration, see [Kubernetes Deployment](/installation/kubernetes).

workspace-operator manages Runtime/Browser/Canvas Deployments and Services, the Workspace RWX PVC, Ingress, and optional CiliumNetworkPolicy from the Workspace CR. Each Deployment uses its own component revision annotation; only Runtime carries the instance, mount, and access fences. Status independently reports observed revision, phase, reason, error, Pod UID, and transition time, with a separate bootstrap state. Stop scales replicas to zero while preserving the CR and PVC. Only delete runs finalizers and persistent-resource cleanup.

## Firewall Desired/Observed Convergence

Manager's Firewall API stores Runtime and Browser rules independently. `PUT /api/v1/workspaces/{workspaceId}/firewall` means only that desired state and a durable firewall command were persisted successfully; it does not prove that CiliumNetworkPolicy was applied. The Firewall resource's `revision` is both desired revision and the CAS base for the next write. Every durable command has a non-reusable delivery ID that must match exactly in the Workspace annotation, Workspace firewall status, and every CNP.

Operator writes a delivery-specific marker into the spec of every top-level Rule in each CNP. The firewall attestor on each node reads endpoint `policy.realized` only through local `/var/run/cilium/cilium.sock`. It proves selected Pod UID, CiliumEndpoint UID/endpoint ID, CNP UID/name/generation, target revision, delivery ID, realized policy revision, agent incarnation, and freshness for every selected endpoint × matching CNP, and verifies that every Rule marker appears in `derived-from-rules` with the same CNP identity. Operator advances observed revision only when every selected endpoint × matching CNP has a fresh, exact attestation. CNP `Valid` condition, generation, resourceVersion, `status.nodes`, or CiliumEndpoint `enforcing` cannot individually prove application.

| `syncStatus` | Meaning | UI behavior |
| --- | --- | --- |
| `pending` | Durable command exists and is waiting for worker claim | Disable duplicate save and poll; do not show success |
| `applying` | Worker has started convergence, but Operator has not confirmed the same revision | Disable duplicate save and poll; do not show success |
| `applied` | Observed has reached desired, and every endpoint × policy local `policy.realized` attestation remains exact and fresh | Show applied |
| `error` | Command, CR apply, or Operator reconciliation failed | Show application failure, preserve desired input and localized stable error, and retry through `POST /api/v1/workspaces/{workspaceId}/firewall/retry` |
| `unavailable` | Deployment does not provide the corresponding firewall capability | Show unavailable instead of pretending that settings were applied |

Runtime and Browser are separate policy groups; enabling either must not relax the other. `specific` accepts only canonical exact hostnames—no wildcard, URL, path, port, or IP—and `github.com` does not imply any subdomain. Disabled mode still permits TCP/UDP 53 to kube-dns but must not generate world or FQDN egress allow rules. Specific mode uses `toFQDNs.matchName`; only all mode may use `toEntities: world`.

## Helm-Only Execution-Plane Resource Baseline

Kubernetes requests/limits for Workspace Runtime, Browser, and Canvas are owned only by Helm values, schema, and rendering contract. Manager writes them to the Workspace CR and Operator applies them unchanged to Deployments. Frontend and Manager API/DB have no per-Workspace resource override and no second Python default.

| Component | CPU request | CPU limit | Memory request | Memory limit |
| --- | ---: | ---: | ---: | ---: |
| Runtime | `500m` | `2000m` | `1Gi` | `3Gi` |
| Browser | `500m` | `2000m` | `1Gi` | `2Gi` |
| Canvas | `100m` | `1000m` | `1Gi` | `2Gi` |

Deployment preflight uses node allocatable capacity and existing requests to confirm that at least one complete execution plane can be scheduled. An upgrade must fail before it starts when no node qualifies.

## Administrator Diagnostic Order

Diagnose along the same revision lineage rather than checking only whether one Pod is Running:

1. Read Manager availability for the stable reason, current `runtimeInstanceId`, access desired/observed revision, and KB last-known-good revision.
2. Inspect lifecycle, mount, access, or firewall durable-job state, target revision, lease, heartbeat, and fencing token. A superseded lineage must not overwrite the latest observed state.
3. Compare Workspace CR spec desired revision with status observed revision, component phase, reason, error code, and workload identity.
4. For firewall diagnosis, first compare the Workspace target delivery ID, CNP UID/generation/Rule marker, and selected Pod/CiliumEndpoint identity. Then inspect the agent incarnation, observed/expires time, realized policy revision, and complete endpoint set in each node attestation. Do not substitute CNP `Valid` or CEP `enforcing`.
5. Compare Runtime and Browser policy groups and the DNS/egress rules for disabled/specific/all.
6. If the DB reports running while the CR/workload no longer exists, let reconciliation create a successor or explicit failure. Do not manually edit the DB into false success.

Use the deployment environment's provided controlled administration interface and namespace for real queries. Documentation must not contain kubeconfig, tokens, hostnames, or other environment secrets.

## Kubernetes Platform Status

The portable contract can be applied to EKS/EFS, GKE/Filestore, AKS/Azure Files, OCP/CephFS or NFS, RKE2/RWX, and upstream Kubernetes with generic NFS or another RWX CSI. Every candidate environment must preserve:

- The same `workspaceRuntimeNamespace` rendering
- Workspace and KB RWX storage contract
- Manager state PVC and minimal namespace RBAC
- Fixed read-only KB mounts, per-component `Recreate` fences, and security-context assertions
- No privileged mode, `anyuid`, Runtime `hostPath`, or fixed `runAsUser`
- Arbitrary-UID image contract for Manager/Runtime

A local runner, Helm render, or image preflight cannot substitute for real platform evidence. EKS, GKE, AKS, OCP, RKE2, and upstream Kubernetes must each complete attach, read-only write denial, cross-node, recycle, failure recovery, and authorization testing on the target cluster and actual CSI/CNI/security policy. Without artifacts from that environment, it may be described only as a candidate configuration conforming to the portable contract, not as conformance-verified or production-certified.

## Rejected Approaches

- Copying a KB into each Workspace: adds data duplication plus synchronization and deletion-consistency problems.
- Filesystem materializer/projector: this requirement does not need Workspace-specific copies.
- KBFS sidecar/FUSE: adds cache, locking, rename, failure, and security-permission concerns.
- Custom CSI driver/NFS namespace controller: existing CSI/NFS drivers already own volume lifecycle.
- Per-user Runtime: increases resource and session-orchestration complexity and conflicts with the product semantics of sharing content inside a Workspace.
- Intersection with each collaborator's direct KB permission: a new member's direct KB ACL would retroactively remove an existing Workspace grant.

## Storage capacity ownership seam

Runtime owns only actual-usage measurement. Manager's `platform_resource_capacity` module owns risk policy, freshness, storage kinds, persisted CR desired-state revisions, quotas, expansion lifecycle, and projection; the Workspace custom-resource module is only a transport adapter. Operator only reconciles CR desired capacity into PVC requests and reports observed revisions, allocated bytes, and stable error codes; it does not own terminal lifecycle policy. Manager does not independently poll PVCs, and Frontend does not infer provisioner capabilities from allocated bytes. See [Platform Resource Statistics and Capacity Governance](/features/platform/resource-statistics-and-capacity).
