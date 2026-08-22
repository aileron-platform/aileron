---
title: Production Deployment
---

# Production Deployment Guide

This guide covers the security, reliability, and performance considerations for deploying Aileron to production.

:::warning
The platform has not formally released. The following guidance is a recommended baseline; adapt the deployment to your organization's security and compliance requirements.
:::

## Atomic deployment for platform resource statistics

Deploy the Manager schema, Runtime telemetry, Workspace CRD and Operator, and Frontend as one release. Apply the CRD first, then deploy Operator, Manager, Runtime, and Frontend. Manager falls back to PostgreSQL when Redis is unavailable, but hourly aggregation, daily capacity snapshots, and retention pruning still require healthy schedulers.

## Pre-deployment Checklist

### Required

- [ ] Every credential and key comes from a controlled Secret (PostgreSQL, OIDC client, Runtime assertion signer, Browser credential keyring, and Runtime database credential key)
- [ ] TLS certificates are configured at Ingress or the reverse proxy
- [ ] The single DNS record for `platformPublicOrigin` points to the Ingress or load balancer, and TLS covers that host
- [ ] With split DNS, internal and external resolvers have separately verified the Platform Public Origin endpoint
- [ ] OIDC provider redirect URIs, audience, and issuer use the production domain and client
- [ ] No environment variable beginning with `VITE_` contains secrets
- [ ] No Docker socket is mounted; Kubernetes mode is used
- [ ] Dedicated databases, non-superuser permissions, Redis logical connections, TLS trust, and rotation are configured according to [External Data Services](./external-data-services.md)

### Recommended

- [ ] Container images use immutable digests and their manifest architecture matches target nodes
- [ ] Resource limits and requests are configured
- [ ] Persistent storage uses PVCs with appropriate StorageClasses
- [ ] If Knowledge Bases will enable Git LFS, `git-lfs` is installed in the `workspace-manager` image
- [ ] Monitoring and alerting are ready
- [ ] A backup strategy exists
- [ ] Log collection is configured

## Security Hardening

### Credential and Secret Management

The OIDC provider owns sign-in credentials. Aileron stores only non-secret validation settings and
provider client parameters. The following is a deployment override and contains no provider password
or provider-admin API credential:

```yaml
# values-production.yaml is only for the deployment host; never commit it
# This is a deployment override, not a complete platform overlay
security:
  requireStrongSecrets: true

platformSecrets:
  existingSecretName: aileron-platform-secrets
  databaseUrlKey: database-url
  runtimeDatabaseCredentialKey: runtime-database-credential-key
  postgresUsernameKey: postgres-username
  postgresPasswordKey: postgres-password

oidc:
  issuerUrl: https://login.example.com/realms/aileron
  clientId: aileron-manager
  clientSecretName: aileron-oidc-client
  clientSecretKey: client-secret

bootstrap:
  admin:
    enabled: true
    subject: "<provider-subject>"
    username: admin
    email: admin@aileron.com
```

`bootstrap.admin.subject` creates only the Manager-local administrator snapshot. The provider owns
credentials, groups, and sign-in policy.

See [OIDC and Identity Plane Installation](./oidc.md) for the production OIDC and local
administrator-snapshot contract. When `bootstrap.admin.enabled=true`, both `install` and `upgrade`
must wait for the snapshot bootstrap Job to succeed. The Job does not create provider accounts,
handle passwords, or put provider credentials into Pod arguments or environment variables.

The OIDC provider policy owns provider-token lifetimes. Only Manager validates issuer, audience,
signature, and `OIDC_MAX_TOKEN_LIFETIME_SECONDS` during callback. To change token or SSO-session
policy, use the provider's controlled settings and verify the PKCE flow; do not configure a removed
Aileron JWT-lifetime override.

The Chart only mounts these existing Secret references; it neither creates nor stores Secret values. This
fragment demonstrates Secret references and bootstrap overrides; it is not a complete values file that can be installed by itself. The
platform overlay must also provide immutable digests for every Aileron component, purpose-specific
StorageClasses, production domains, the selected Registry authentication mode, Ingress, TURN, and network-isolation
settings. Store deployment values on the deployment host with `0600` permissions and delete them
securely after installation.

The command below follows the two-values flow in [Kubernetes Quick Installation](./kubernetes.md).
Every cluster must point `PLATFORM_VALUES` to its own generated and verified platform overlay:

```bash
chmod 0600 values-production.yaml
export PLATFORM_VALUES=/run/aileron/platform-values.yaml

helm upgrade --install aileron ./helm/aileron \
  --namespace workspace-system \
  --create-namespace \
  --values "${PLATFORM_VALUES}" \
  --values values-production.yaml \
  --atomic \
  --wait \
  --wait-for-jobs \
  --timeout 15m
```

:::tip External Secret management
Use External Secrets or the deployment flow to create existing Secrets referenced by the Chart. Values contain only Secret names and keys, never Secret values.
:::

### TLS / HTTPS

Every public HTTP and WebSocket service must use HTTPS. TURN is not HTTP; its Reachability Profile
explicitly selects `turn:` over TCP/UDP or `turns:` over TLS and exposes only the declared listener and
relay range:

```yaml
platformPublicOrigin: https://aileron.apps.example.com

ingress:
  enabled: true
  className: "<ingress-class>"
  useDefaultClass: false
  tlsMode: kubernetesSecret
  tlsSecretName: aileron-platform-tls
  annotations: {}
```

The TLS Secret must already exist in the shared Runtime namespace and cover the
single Platform Public Origin host. Provider annotations belong in
the environment's deployment profile; product values and Operator code do not
assume NGINX, AWS, GCP, or Azure. When the cloud Ingress controller manages the
certificate, use `tlsMode: controllerManaged`, keep `tlsSecretName: ""`, and
place the certificate reference in provider annotations or IngressClass policy.

In `externalOidc` mode, verify the production issuer and client:

```yaml
oidc:
  issuerUrl: https://login.example.com/realms/aileron
  clientId: aileron-frontend
```

### Container Image Security

- Use a private Registry. Configure `global.imagePullSecrets` for an external
  Secret-based Registry, or use kubelet/node managed identity for a supported
  cloud-native Registry.
- Production deployments use immutable digests only, never tags.
- Scan images regularly for vulnerabilities with tools such as Trivy or Snyk.

With built-in TURN and Secret-based Registry authentication, Coturn runs in a
separate `coturn.namespace`; the selected `global.imagePullSecrets` name must
exist in both the Runtime and Coturn namespaces. RKE2 HomeLab must prepare them
through [Kubernetes Installation — `prepare-cluster`](./kubernetes.md#prepare-cluster),
without manually creating copies.

```yaml
global:
  imagePullSecrets:
    - name: registry-credentials

frontend:
  image:
    repository: your-registry.com/workspace-ui
    digest: sha256:<64-hex-digest>
    tag: ""
    pullPolicy: IfNotPresent
```

When EKS/ECR, GKE/Artifact Registry, or AKS/ACR already has node pull
authorization, use `global.imagePullSecrets: []`. Pod workload identity and
kubelet image-pull identity are separate contracts and must be verified
independently.

### Network Security

- Enable Cilium for network isolation between Workspaces.
- Restrict access to the external provider administration surface.
- Keep each Workspace domain allowlist as precise as possible.

```yaml
cilium:
  enabled: true

firewall:
  seed:
    workspace:
      egressMode: allowlist
      allowedDomains:
        - github.com
        - api.github.com
        - registry.npmjs.org
        - pypi.org
        - api.anthropic.com
        - chatgpt.com
        - api.openai.com
        - auth.openai.com
    browser:
      egressMode: allowlist
      allowedDomains:
        - github.com
```

`firewall.seed` is written to the database only when a new Workspace is created. Users can later remove seeded domains in the UI; Helm upgrades and service restarts do not restore them. See [Kubernetes Workspace Firewall](./kubernetes-firewall.md) for the complete contract.

### Production TURN

Every Kubernetes, OpenShift, and private-enterprise deployment supplies an explicit TURN Reachability
Profile. Built-in Coturn DNS resolves only to Coturn nodes and node firewalls allow its listener and relay
UDP range. External TURN uses the profile to describe separate Browser Pod and public endpoint destinations.

Production support requires backend relay evidence from the Browser Pod sidecar and frontend relay evidence
submitted through Connectivity Evidence Gateway by every required external vantage. Evidence matches the
current profile and credential revisions and remains within TTL; the external-vantage credential issuer is
`turnRest`. Service health, an open port, STUN binding,
or occasional direct ICE success is not TURN conformance. See
[Kubernetes Networking and TURN](./kubernetes-networking.md) for configuration and acceptance.

## Resource Planning

### Current Resource Contract

The Helm Chart deploys a fixed control plane. Workspace Operator creates Runtime, Browser, and Canvas Deployments dynamically from each `Workspace` CR. The platform does not create Workspaces automatically; users create only the Workspaces they need through the UI or API.

### Recommended Platform-Service Configuration

| Service | CPU Request | CPU Limit | Memory Request | Memory Limit |
|------|-------------|-----------|----------------|--------------|
| Frontend | 100m | 500m | 128Mi | 256Mi |
| Workspace Manager | 250m | 1000m | 256Mi | 512Mi |
| Workspace Operator | 100m | 500m | 128Mi | 256Mi |
| Bundled OIDC adapter (optional) | 500m | 1000m | 512Mi | 1Gi |
| PostgreSQL | 250m | 1000m | 256Mi | 1Gi |
| Redis | 100m | 500m | 128Mi | 256Mi |

### Recommended Workspace-Pod Configuration

| Component | CPU Request | CPU Limit | Memory Request | Memory Limit |
|------|-------------|-----------|----------------|--------------|
| Runtime | 500m | 2000m | 1Gi | 3Gi |
| Browser (neko) | 500m | 2000m | 1Gi | 2Gi |
| Canvas | 100m | 1000m | 1Gi | 2Gi |

### Resource Configuration Currently Supported by the Chart

The Helm Chart supports these values:

```yaml
frontend:
  resources: {}

workspaceManager:
  resources:
    requests:
      cpu: 500m
      memory: 1Gi
    limits:
      cpu: 2000m
      memory: 2Gi

workspaceOperator:
  resources: {}

postgres:
  resources: {}

redis:
  resources: {}

kubernetes:
  workspaceDefaults:
    runtime:
      resources:
        requests:
          cpu: 500m
          memory: 1Gi
        limits:
          cpu: 2000m
          memory: 3Gi
    browser:
      resources:
        requests:
          cpu: 500m
          memory: 1Gi
        limits:
          cpu: 2000m
          memory: 2Gi
    canvas:
      resources:
        requests:
          cpu: 100m
          memory: 1Gi
        limits:
          cpu: 1000m
          memory: 2Gi
```

```yaml
# Configure resource limits in values.yaml
workspaceManager:
  resources:
    requests:
      cpu: 250m
      memory: 256Mi
    limits:
      cpu: 1000m
      memory: 512Mi
```

### Inspect the Effective Kubernetes Resource Configuration

Inspect platform services and StatefulSets:

```bash
kubectl get deploy,statefulset -n workspace-system \
  -o jsonpath='{range .items[*]}{.kind}{"\t"}{.metadata.name}{"\t"}{range .spec.template.spec.containers[*]}{.name}{": requests="}{.resources.requests.cpu}{"/"}{.resources.requests.memory}{", limits="}{.resources.limits.cpu}{"/"}{.resources.limits.memory}{"; "}{end}{"\n"}{end}'
```

Inspect the dynamic Deployments for one Workspace:

```bash
kubectl get deploy -n workspace-system \
  -l 'aileron.io/workspace-id=<workspace-id>' \
  -o yaml
```

Check whether default Workspace resources were written to the platform configuration:

```bash
kubectl get configmap aileron-platform-config -n workspace-system \
  -o jsonpath='{.data.RUNTIME_K8S_RUNTIME_RESOURCES}{"\n"}{.data.RUNTIME_K8S_BROWSER_RESOURCES}{"\n"}{.data.RUNTIME_K8S_CANVAS_RESOURCES}{"\n"}'
```

### Storage Planning

| Purpose | Recommended size | Access Mode | Description |
|------|----------|-------------|------|
| PostgreSQL | 20–50 Gi | ReadWriteOnce | Depends on the number of Workspaces and history retained |
| Redis | 5–10 Gi | ReadWriteOnce | Task queue and cache |
| Workspace working tree | 10–50 Gi/Workspace | ReadWriteMany | Repository and working files; must support cross-node recreation |
| Runtime HOME | 2–10 Gi/Workspace | ReadWriteOnce by default; optional ReadWriteMany | CLI login, agent settings, XDG, and bootstrap state |
| Knowledge Base | 20–100 Gi | ReadWriteMany | Written by Manager and mounted read-only by multiple Runtimes through `subPath` |
| Manager state | 20–50 Gi | ReadWriteOnce | Marketplace Registry and other persistent Manager state |

## Identity service boundary

The core `helm/aileron` Chart manages platform PostgreSQL and Redis but does not deploy or manage an
OIDC provider. In `bundledKeycloak` mode, the installer manages Keycloak and Identity PostgreSQL as
an independent `helm/aileron-identity` release. In `externalOidc` mode, it installs no Identity
Plane. Manager's issuer and client settings come only from the standard adapter projection.

Neither mode may replace formal OIDC values with unmanaged environment overrides. If Bundled
Keycloak later connects to an enterprise LDAP directory, that integration remains inside Keycloak
User Federation. Aileron receives no LDAP setting or credential.

## Backup Strategy

### Database Backup

Both the platform and Identity databases require scheduled backups and restore drills. With
`postgres.enabled=true`, backup tooling uses the chart-managed credential Secret and CA. With
`postgres.enabled=false`, the external data-service operator follows the provider's snapshot, PITR,
or `pg_dump` contract. A backup operation must not assume access to the `postgres` superuser or put
credentials in argv or backup filenames. Record recoverable backup and restore-drill evidence before
every upgrade.

### Identity provider backup

Bundled Keycloak uses explicit `aileron-identity` backup and restore operations for Identity
PostgreSQL and the realm. Backup and restore cannot run together, and a normal install never
restores implicitly. External OIDC follows its provider's supported backup contract. Aileron Core
does not provide a provider-specific administration API.
The Identity chart owns the backup PVC; the HomeLab profile uses `aileron-nfs-rwx-retain` with
`ReadWriteMany`. Restore acceptance must run the real dump/restore workflow in
`identity-installation/backup_restore_smoke.py` with an exact destructive confirmation. Helm render
output is not restore evidence.

### Workspace Data Backup

- Use VolumeSnapshot for PVCs when supported by the CSI driver.
- Alternatively, use Velero for cluster-level backups.

## Monitoring

### Health-Check Endpoints

| Service | Endpoint |
|------|------|
| Workspace Manager | `GET /health` |
| Workspace Runtime | `GET /health` |
| OIDC provider | External provider readiness contract |
| PostgreSQL | `pg_isready` |
| Redis | `redis-cli ping` |

### Metrics

- **Celery Flower**: Celery task monitoring is available only on the deployment-internal network
- **Workspace Manager**: Use `GET /health` to monitor whether the HTTP service responds

Manager OIDC readiness checks Discovery and JWKS reachability. External-provider health and metrics
follow the provider contract.

### Recommended Alert Rules

| Condition | Severity | Description |
|------|--------|------|
| Pod CrashLoopBackOff | Critical | Service failed to start |
| OIDC provider unhealthy | Critical | Identity service outage affecting all sign-ins |
| PostgreSQL unhealthy | Critical | Database outage |
| Redis unhealthy | High | Task-queue outage |
| PVC usage > 80% | Warning | Storage is nearly exhausted |
| Increased Celery task failure rate | Warning | Workspace Runtime durable jobs or Knowledge Base maintenance is failing |

## Upgrade Procedure

### Consistent Authorization-Contract Deployment

The platform-role and resource-role contract treats Manager, Runtime, Frontend, the Helm schema, the
database, and the OIDC issuer settings as one indivisible deployment unit. Never run mutually
incompatible contracts across services.

1. Create database and OIDC-provider configuration snapshots from the same point in time.
2. Stop external traffic and enter maintenance mode.
3. Apply the current schema, `admin/member` platform roles, and `reader/manager/owner` resource-role contract to a fresh database and the current OIDC issuer.
4. Deploy Manager, Runtime, Frontend, and the Helm schema as one set.
5. Wait for DB, the OIDC provider, Manager, and Runtime readiness before creating smoke accounts, ownership, and shares.
6. Restore traffic only after positive and negative HTTP and UI smoke tests for platform and resource roles pass.

If any readiness or smoke check fails, keep traffic disabled and restore the matching database and
OIDC-provider configuration snapshots. Never handle only one service.

### Helm Chart Upgrade

```bash
# 1. Inspect changes
helm diff upgrade aileron helm/aileron \
  --namespace workspace-system \
  -f "${PLATFORM_VALUES}" \
  -f values-production.yaml

# 2. Create a recoverable backup through the external or bundled PostgreSQL runbook

# 3. Upgrade
kubectl apply -f helm/aileron/crds/
helm upgrade aileron helm/aileron \
  --namespace workspace-system \
  -f "${PLATFORM_VALUES}" \
  -f values-production.yaml \
  --atomic --wait --wait-for-jobs

# 4. Verify
kubectl get pods -n workspace-system
kubectl logs -n workspace-system \
  --selector='app.kubernetes.io/instance=aileron,app.kubernetes.io/component=workspace-manager' \
  --all-containers \
  --tail=50
```

Whenever `bootstrap.admin.enabled=true`, `helm upgrade` runs the local administrator-snapshot
bootstrap and maps `bootstrap.admin.subject` to the configured OIDC issuer + subject. It never creates,
resets, or overwrites a provider password. Rotate provider credentials through the provider's own
workflow, then finish the upgrade with `--wait-for-jobs` and verify OIDC sign-in and `/api/v1/oauth2/session`.

:::caution
Always back up the database before upgrading. `helm upgrade` does not update CRDs automatically, so apply `helm/aileron/crds/` first. The database must match the current schema; when incompatible, verify snapshot recovery and install with a fresh database.
:::
