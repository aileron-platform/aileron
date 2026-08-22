---
title: Workspace Manager
---

# Workspace Manager

## Overview

Workspace Manager is Aileron's core service. It manages the complete lifecycle of development Workspaces, including creation, configuration, start, stop, and deletion.

## Core Features

### Workspace Management

- **CRUD**: create, read, update, and delete Workspaces
- **Lifecycle**: use PostgreSQL durable jobs to manage Docker/Kubernetes create, start, stop, component restart, delete, and crash recovery
- **Component revision fence**: Runtime, Browser, and Canvas each retain desired/observed revision, phase, and workload identity. Only the component targeted by the job is replaced. For the complete convergence flow, see [Execution-Plane Lifecycle and Safety](/architecture/overview/execution-plane)
- **Marketplace support**: manage agent packages, package formats, and target-client settings
- **Network configuration**: manage firewall rules and port mappings

### User and Workspace Collaboration

- **Workspace shares**: manage Workspace members through direct shares
- **Permission control**: role-based access control (RBAC)
- **User Groups**: centrally manage user groups and their members
- **Knowledge Base attachment**: check Workspace configuration permission during creation; a private KB additionally requires source-KB Manager access, while a public KB grants implicit Reader access. The resulting Workspace grant provides a zero-copy, read-only mount
- **Runtime action gate**: authorize every action against the current instance, Runtime lifecycle, access observed revision, and one of `runtime_read`, `runtime_write`, `terminal`, `agent`, `automation`, or `browser_automation`. KB mount observed revision restricts only KB-dependent operations

### Automation Tasks

- **Cron scheduling**: scheduled tasks using Cron expressions
- **AI integration**: automation tasks that can drive Claude Code, Codex, and OpenCode agent workflows
- **Execution monitoring**: track task execution status and results

Automation is not scheduled by Celery. A single `AutomationScheduler` in Manager periodically scans PostgreSQL with asyncio and creates executions. Each Workspace Runtime then claims and completes work through the claim/complete contract.

### Celery Background Work

Celery workers and a single Beat execute PostgreSQL-persisted Workspace Runtime durable jobs (start, stop, Runtime/Browser/Canvas restart, delete, Knowledge Base mount reconciliation, and access recycle). They also run daily KB quota reconciliation. The Celery message itself is not the source of correctness. For claim tokens, leases, heartbeats, and recovery convergence, see [Execution-Plane Lifecycle and Safety — Durable Jobs and Recovery](/architecture/overview/execution-plane#durable-jobs-and-recovery).

## Identity Synchronization and User Administration

For a user-visible explanation of platform roles and the user authorization model, see [Users, Groups, and Permission Model](/features/platform/permissions-and-roles). This section records the internal synchronization and saga mechanisms that support that model.

Manager centralizes authorization in the deep `AuthorizationOperationPolicy` module. It resolves the
local snapshot keyed by OIDC issuer + subject, unique Owner, direct shares, group shares, Public KB
access, and the Platform Admin override. Its interface exposes `require_platform_operation()`,
`require_workspace_operation()`, `require_knowledge_base_operation()`, `require_knowledge_base_mount()`,
and both `allowed_*_operations()` methods. Routers, domain services, the Frontend, and Runtime
adapters never compare role ranks. The same module produces `allowedOperations`, `accessRole`,
`accessSource`, and complete `accessSources`.

### Permanent-Deletion Staging

Workspace and Knowledge Base permanent deletion first performs authorization, exact-name confirmation, running-state or attachment preflight, audit intent, and the deletion fence in a transaction. It then performs external Runtime and storage cleanup before committing the deleted resource state. A failed stage remains auditable but does not create a recoverable resource copy. Platform Admin must first take ownership through a reasoned, notified, before-and-after audited flow before deleting another user's resource.

### Manager Session and Authorization Freshness

Manager is the only component that terminates the external OIDC authorization-code flow. After the
callback validates the ID token, nonce, PKCE, and required UserInfo response, Manager sets only an
HttpOnly opaque session cookie in the browser. Provider access tokens, refresh tokens, and ID tokens
never leave Manager. Every protected operation recomputes authorization from the session's local user
snapshot, disabled state, and current authorization data. It never trusts a platform role from a JWT
or a role decision cached by the frontend.

### OIDC JIT Snapshot Sync

Users do not need a pre-created Aileron account. On the first successful OIDC callback, Manager
creates or updates a member snapshot keyed by `(oidc_issuer, oidc_subject)`,
stores optional username, email, and display-name claims, and preserves the local platform role. If
the local commit fails, the request fails closed and leaves a diagnosable `identity_sync_failed`
state; Manager does not create provider accounts, handle passwords, or call a provider-specific
administration API.

### Administrator Bootstrap

Installation and upgrade can use `bootstrap.admin.subject` to converge one explicitly configured
local platform-administrator snapshot. The provider owns credentials, groups, and sign-in policy;
repeated runs reuse the same local user ID and do not create a second administrator. The ordinary
User Admin API changes only local roles and state and provides no provider-account or password
break-glass path.

### Audit and Correlation

Identity snapshot sync, User Admin CRUD, User Group mutations, direct KB sharing, Workspace attachment/lifecycle/access recycle, and browser pairing all persist audit entries. An HTTP request may supply a valid UUID in `X-Correlation-ID`. If it is missing or invalid, Manager generates a UUIDv4 and returns it in the response. A durable-job retry uses a new attempt correlation ID while retaining the original mutation's root correlation ID, so the complete lineage remains traceable in the database. Audit metadata stores only allowlisted state, resource IDs, revisions, instance IDs, and stable reasons. It never stores passwords, tokens, JWS values, credentials, raw OIDC-provider responses, request bodies, or exception payloads.

### Deployment and Operational Prerequisites

- The OIDC provider owns sign-in and claims; Aileron locally manages the `admin` and `member` platform roles and keeps identity unique by `(issuer, subject)`.
- Once Discovery, JWKS, client scopes, audience, and redirect URIs are configured, Compose and Helm validate the OIDC contract before Manager starts.
- If OIDC Discovery/JWKS or local snapshot bootstrap fails, repair the configuration instead of bypassing the gate and starting Manager.
- User Admin and User Group list search, filtering, sorting, pagination, and totals are calculated by PostgreSQL server-side queries.
- EKS, GKE, AKS, OCP, RKE2, and upstream Kubernetes are deployment targets. Until real storage, admission, arbitrary UID, read-only probe, and rescheduling conformance passes on a platform, it must remain labeled target/unverified rather than certified.

## Technical Architecture

| Component | Technology |
|------|------|
| Web framework | FastAPI |
| ORM | SQLAlchemy |
| Database | PostgreSQL |
| Cache/Celery broker | Redis |
| Durable Workspace jobs/KB maintenance | Celery worker + Beat |
| Automation scheduling | asyncio scheduler + PostgreSQL |
| Container management | Docker / Kubernetes |
| Authentication | Provider-neutral OIDC BFF + opaque Manager session |

## Directory Structure

Workspace Manager's normative target is a vertical domain-module structure.
Routers, models, repositories, contracts, and adapters remain together under
their owning domain instead of a global horizontal taxonomy. See
[Backend Domain Module Architecture](/architecture/backend/) and
[Python Module and Filename Rules](/reference/python-module-naming) for the
directory template, seams, interfaces, and test rules.

For the owning modules and no-bypass rules of Marketplace requests, the User
Copy cross-Runtime contract, and Workspace Runtime Job state, see
[Backend Deep Modules and Cross-Execution-Plane Contracts](/architecture/backend/).

## Environment Variables

### Basic Settings

| Variable | Default | Description |
|--------|--------|------|
| `DATABASE_URL` | — | Credential-free PostgreSQL topology URL used by the Compose adapter; a read-only passfile supplies the password |
| `DATABASE_URL_FILE` | — | Read-only Secret file containing the complete PostgreSQL DSN for the Kubernetes adapter; takes precedence over `DATABASE_URL` when configured |
| `REDIS_URL` | — | Redis connection URL |
| `DOCKER_HOST` | `unix:///var/run/docker.sock` | Docker host |
| `DEBUG` | `false` | Debug mode |

### OIDC Authentication Settings

| Variable | Default | Description |
|--------|--------|------|
| `PLATFORM_PUBLIC_ORIGIN` | — | Sole exact public Origin; callback, logout, and CORS derive from it |
| `OIDC_ISSUER_URL` | — | Canonical issuer URL |
| `OIDC_CLIENT_ID` | — | Required Manager confidential OIDC client ID supplied explicitly by the installation adapter |
| `OIDC_CLIENT_SECRET_FILE` | — | Read-only file path containing the OIDC client secret |
| `OIDC_ALLOWED_ALGORITHMS` | `RS256` | Allowed JWT algorithm list |
| `OIDC_MAX_TOKEN_LIFETIME_SECONDS` | `1800` | Maximum token lifetime |
| `OIDC_REQUIRED_ACR` | _(empty)_ | Optional authentication context |
| `OIDC_JWKS_CACHE_TTL` | `3600` | JWKS cache TTL in seconds |
| `OIDC_DISCOVERY_TIMEOUT_SECONDS` | `5` | Discovery/JWKS timeout in seconds |

Discovery is always `{issuer}/.well-known/openid-configuration`. Compose or Helm supplies these fields; the Manager directory has no independent `.env` installation surface.

The OIDC provider owns access-token and refresh-session policy. Manager does not issue an
Aileron-signed JWT and uses `OIDC_MAX_TOKEN_LIFETIME_SECONDS` to bound the ID-token lifetime accepted
at callback. The browser holds only the opaque Manager session cookie and a session-bound CSRF token.

:::important Authentication cannot be disabled
Manager always requires generic OIDC authentication. There is no `ENABLE_AUTH=false` or other public disable switch. Only explicitly exempt routes such as health, metrics, OpenAPI/documentation, and OIDC configuration allow anonymous access.
:::

## Local Development

```bash
docker compose up -d workspace-manager
```

For local development, start `workspace-manager` through Docker Compose and run it with the control-plane Compose stack. The root Compose project does not include dynamic Workspace execution-plane containers created by the Docker provisioner; manage those containers through the Manager UI or API. Compose mounts `./workspace-manager` at `/workspace-manager` inside the container, so the existing reload mechanism normally applies source changes immediately.

If the other control-plane dependencies are not already running, start them with:

```bash
docker compose up -d
```

## Testing

```bash
docker buildx bake --load workspace-manager

docker compose -f workspace-manager/docker-compose.test.yml \
  run --rm workspace-manager-test \
  bash -lc 'uv sync --dev && uv run pytest tests -v'

docker compose -f workspace-manager/docker-compose.test.yml \
  run --rm workspace-manager-test \
  bash -lc 'uv sync --dev && \
    uv run black --check app tests && \
    uv run isort --check-only app tests && \
    uv run flake8 --extend-ignore=E501,E402,W293 app tests && \
    uv run mypy app'
```

:::tip Test environment
Project tests always run inside containers so that host dependencies and PostgreSQL/Redis version differences do not affect the evidence.
:::

## Monitoring

Manager's `/health`, `/metrics`, OpenAPI documents, and Flower are deployment-internal endpoints. Browsers only use `/api/v1/...` on Platform Public Origin.

## Platform resource analytics and capacity governance

The `platform_resource_analytics` module owns the activity ledger, daily aggregates, latest capacity observations, daily capacity snapshots, and Redis cache-aside behavior. The Runtime telemetry ingestion route `/api/v1/internal/workspaces/{workspace_id}/resource-telemetry/batches` validates batches and deduplicates by batch and event identity. Redis failures fall back to PostgreSQL for the analytics read model. The `platform_resource_capacity` module exclusively owns thresholds, freshness, inventory projection/filter semantics, quota commands, the expansion-only lifecycle, and Workspace capacity queries/routes. The Workspace CR module only translates typed domain models to and from the Kubernetes wire contract. For cross-plane ownership and telemetry privacy, see [Platform Resources and Runtime Telemetry Architecture](/architecture/overview/platform-resource-observability); for the user-facing capability, see [Platform Resource Statistics and Capacity Governance](/features/platform/resource-statistics-and-capacity).
