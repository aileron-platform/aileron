---
title: Helm Values Reference
description: Grouped index of Aileron Kubernetes production values
---

# Helm Values Reference

This page lists the primary production deployment settings. `helm/aileron/values.yaml` is the source of truth for all defaults. The production profile fails closed on required fields and does not infer persistence purposes from global settings.

## Global and Security

| Key | Purpose |
| --- | --- |
| `global.imagePullSecrets` | Optional; same-named existing Registry Secrets in each workload namespace; built-in Coturn uses a separate namespace |
| `security.requireStrongSecrets` | Enable production hardening: HTTPS, Ingress, immutable image digests, and explicit StorageClasses |
| `platformSecrets.existingSecretName` | Existing platform Secret shared by Manager and PostgreSQL |
| `platformSecrets.databaseUrlKey` | Secret key containing Manager's complete PostgreSQL DSN |
| `platformSecrets.runtimeDatabaseCredentialKey` | Secret key containing the Manager-only HMAC key for Runtime instance credentials |
| `platformSecrets.postgresUsernameKey` / `platformSecrets.postgresPasswordKey` | Secret keys for the bundled PostgreSQL identity |
| `runtimeAssertions.*` | References to existing assertion signer and JWKS Secrets |
| `browserCredentials.*` | Existing Browser keyring Secret, key, and rotation revision in the Runtime namespace |

## Authentication

| Key | Purpose |
| --- | --- |
| `platformPublicOrigin` | Sole exact public platform Origin; callback, logout, CORS, and every browser-visible path derive from it |
| `oidc.issuerUrl` | Required canonical HTTPS issuer of the external provider |
| `oidc.clientId` | Manager confidential OIDC client ID |
| `oidc.clientSecretName` / `oidc.clientSecretKey` | Manager-only existing client Secret reference |
| `oidc.caSecretName` / `oidc.caSecretKey` | Optional Manager-only provider CA Secret reference |
| `bootstrap.admin.*` | Seeds a local platform-admin snapshot by issuer + subject; the OIDC provider owns credentials |

The Chart neither deploys nor manages an IdP and does not inject OIDC configuration into Runtime,
Terminal, or Operator. Frontend signs in only through the Manager BFF session. See
[External OIDC Installation](../installation/oidc.md).

## Storage

| Key | Purpose |
| --- | --- |
| `kubernetes.workspaceData.storageClassName` | RWX/Delete class for the working tree shared by all three components |
| `kubernetes.runtimeHome.storageClassName` | Dedicated RWO/Delete class for Runtime HOME by default |
| `kubernetes.runtimeHome.accessMode` | One value: `ReadWriteOnce` by default or `ReadWriteMany` |
| `kubernetes.knowledgeBases.storageClassName` | Canonical RWX/Retain class for Knowledge Bases |
| `kubernetes.managerState.storageClassName` | RWO/Retain class for Manager state |
| `postgres.persistence.storageClassName` | RWO/Retain class for PostgreSQL |
| `redis.persistence.storageClassName` | RWO/Retain class for Redis |
| `kubernetes.platformStorageGid` | Shared storage GID for non-root workloads |
| `kubernetes.storageVerification.workspaceStorageClassName` | Disposable Delete class dedicated to the Workspace RWX probe |
| `kubernetes.storageVerification.managerStateStorageClassName` | Disposable Delete class dedicated to the Manager-state RWO probe |
| `kubernetes.storageVerification.workspaceSize` | Workspace RWX probe capacity; positive Kubernetes quantity, default `1Gi` |
| `kubernetes.storageVerification.managerStateSize` | Manager-state RWO probe capacity; positive Kubernetes quantity, default `1Gi` |

The two probe sizes can be set independently for cloud storage-tier minimums
without changing production PVC capacities. Verification classes must differ
from production classes and use `reclaimPolicy: Delete`.
`helm/aileron/tests/values/platform-*.yaml` files are Helm render-contract
fixtures only. They neither create provider StorageClasses nor prove
certification for EKS, GKE, AKS, OCP, RKE2, or upstream Kubernetes.

## Images

| Key | Purpose |
| --- | --- |
| `frontend.image.*` | Frontend image |
| `workspaceManager.image.*` | Manager Kubernetes image |
| `workspaceOperator.image.*` | Operator image |
| `workspaceOperator.runtimeImage.*` | Runtime Kubernetes image |
| `kubernetes.browserImage.*` | Browser Kubernetes image |
| `kubernetes.canvasImage.*` | Canvas Kubernetes image |
| `postgres.image.*` | PostgreSQL platform image |
| `redis.image.*` | Redis platform image |

Each image object provides `repository`, `digest`, and `tag`. In production, set `digest: sha256:...` and keep `tag: ""`; the Chart renders only `repository@sha256:...`. Preflight separately verifies that the manifest targets the required architecture.

## Routing

| Key | Purpose |
| --- | --- |
| `platformPublicOrigin` | Shared Origin for Frontend, Manager API, OAuth, Runtime, Browser, Canvas, and WebSocket traffic |
| `ingress.enabled` | Fixed platform Ingress |
| `ingress.className` | Optional `spec.ingressClassName` |
| `ingress.useDefaultClass` | Explicitly accept the cluster default IngressClass |
| `ingress.tlsMode` | `disabled`, `kubernetesSecret`, or `controllerManaged` |
| `ingress.tlsSecretName` | Existing TLS Secret in the Runtime namespace |
| `ingress.annotations` | Provider annotations for the single platform Ingress |
| `cilium.enabled` | Workspace network policy |

`ingress.enabled` is disabled by default so generic values cannot accidentally create a public cloud Load Balancer. Production profiles must explicitly select their Ingress controller and TLS mode. Frontend's gateway reaches internal Services through fixed `/workspaces/{uuid}/runtime|browser|canvas` paths; no Workspace public host is created.

## Firewall

| Key | Purpose |
| --- | --- |
| `firewall.seed.workspace` | Initial Runtime/Canvas settings for a new Workspace |
| `firewall.seed.browser` | Initial Browser settings for a new Workspace |
| `*.egressMode` | `blocked`, `allowlist`, or `unrestricted` |
| `*.allowedDomains` | Exact hostnames written at creation for `allowlist`; the other modes require an empty array |

Seeds initialize only new Workspaces. A Helm upgrade does not overwrite existing Workspaces.

## TURN

| Key | Purpose |
| --- | --- |
| `turn.enabled` | Enable TURN |
| `turn.existingSecretName` | Existing Browser ICE and TURN REST shared-secret Secret in the Runtime namespace |
| `turn.backendIceServersKey` | Backend ICE JSON key |
| `turn.frontendIceServersKey` | Frontend ICE JSON key |
| `turn.credentialRevision` | Secret rotation revision |
| `turn.profile.policyBackend` | `cilium`, `kubernetes`, or `unenforced` |
| `turn.profile.backend` | Browser Pod URLs, control/relay destinations, and relay port range |
| `turn.profile.frontend.urls` | Public TURN URLs used by required external vantages |
| `turn.profile.credentialIssuer` | Always `turnRest`; defines the Secret ref and short-lived credential TTL |
| `turn.profile.evidence` | Probe interval, evidence TTL, and required frontend vantages |
| `coturn.enabled` | Deploy built-in Coturn; when false, external TURN satisfies the same profile |
| `coturn.frontendHost` | Public TURN DNS template in built-in mode |
| `coturn.image` | Built-in Coturn image reference |
| `coturn.namespace` | Namespace for built-in Coturn; private images require the Secret selected by `global.imagePullSecrets` to exist there |
| `connectivityEvidenceGateway.*` | Gateway installation identity, public host, probe identity, and agent enrollment settings |
| `connectivityEvidenceGateway.hostAgent.*` | Host-network vantage for local development or an explicitly classified single-site environment; private CAs are mounted with `tls.caSecretName` and `tls.caSecretKey`; disabled by default |

Built-in Coturn credentials, external TURN Browser/probe ICE JSON, the Gateway internal token, and each
vantage token must come from namespace-scoped existing Secrets. `turnRest` ICE JSON contains URLs only;
Manager access and the Browser sidecar issue short-lived credentials when used. The Registry Secret is a
separate namespace-scoped contract.

## Production Canvas Publishing

Canvas publishing is an optional Workspace Skill and is not configured by global Aileron Helm values.
The Workspace environment supplies `AILERON_PUBLISH_*` values, including provider endpoints,
Project path, credentials, OCI repositories and immutable base image references. See
[Canvas 發佈管理員設定](/installation/canvas-publishing-admin)。

## Workspace Bootstrap and Lifecycle

The Workspace CR represents state through its bootstrap revision/status and the separate desired/observed revisions for Runtime, Browser, and Canvas. Runtime bootstrap always runs Git, agent defaults, custom setup, and supervisor in that order. Browser and Canvas are released from their gates only after the initial bootstrap succeeds.

Agent defaults are seeded once from `/opt/aileron/agent-defaults` in the Runtime image into each of Codex's, Claude's, and OpenCode's own Client User Scope (`${CODEX_HOME:-$HOME/.codex}/skills`, `${CLAUDE_CONFIG_DIR:-$HOME/.claude}/skills`, and `$HOME/.config/opencode/skills`); each Target Client keeps an independent copy, with no symbolic links. The marker is stored at `${HOME}/.local/state/aileron/bootstrap`. Pod restarts and image upgrades do not overwrite user changes or restore content that a user deleted.

Custom setup runs as the Runtime's non-root UID with a timeout, output limits, and stable error states.

## Workspace storage and observability

`kubernetes.workspaceData.size` and `kubernetes.runtimeHome.size` set the initial desired capacity for a new Workspace's two PVCs; lowering values never shrinks existing PVCs. Workspace CRD `spec.storage` uses integer bytes, and Operator converts bytes to Kubernetes quantities at one adapter. Platform `TZ` controls daily statistic buckets, while Runtime reports actual usage on a fixed interval.
