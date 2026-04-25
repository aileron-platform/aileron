---
sidebar_position: 5
title: Production Deployment
---

# Production Deployment Guide

This guide covers security, reliability, and performance considerations when deploying Aileron to production.

:::warning
The platform is currently in alpha (v0.1.0-alpha). The items below are recommendations; adjust per your organization's security and compliance requirements.
:::

## Pre-Deployment Checklist

### Required

- [ ] All default passwords changed (PostgreSQL, Redis, Keycloak, JWT Secret)
- [ ] TLS certificates configured (Ingress or reverse proxy)
- [ ] DNS records created (at minimum for static service hosts, with workspace hosts covered by wildcard or automated records)
- [ ] Keycloak Redirect URIs updated for the production domain
- [ ] `VITE_` variables contain no secrets
- [ ] Docker socket mount removed (use Kubernetes mode)
- [ ] Database connection uses encryption (`sslmode=require`)

### Recommended

- [ ] Container images pinned to specific tags (not `latest` or `dev`)
- [ ] Resource limits/requests configured
- [ ] Persistent storage configured (PVC with appropriate StorageClass)
- [ ] Monitoring and alerting in place
- [ ] Backup strategy established
- [ ] Log collection configured

## Security Hardening

### Password and Secret Management

**Never use default passwords.** The following must be changed:

```yaml
# values.yaml - production example
postgres:
  auth:
    password: "<strong-random-password>"

keycloak:
  auth:
    adminUser: admin
    adminPassword: "<strong-random-password>"

workspaceManager:
  env:
    SECRET_KEY: "<random-256-bit-key>"
    ACCESS_TOKEN_EXPIRE_MINUTES: "60"     # Shorten token lifetime
    REFRESH_TOKEN_EXPIRE_DAYS: "1"
```

Use Kubernetes Secrets rather than plaintext values in values.yaml:

```bash
# Create a secret
kubectl create secret generic aileron-secrets \
  --from-literal=DATABASE_PASSWORD='<password>' \
  --from-literal=SECRET_KEY='<key>' \
  --from-literal=KEYCLOAK_ADMIN_PASSWORD='<password>' \
  -n aileron
```

:::tip External Secret Management
Combine with [External Secrets Operator](https://external-secrets.io/) or [Sealed Secrets](https://sealed-secrets.netlify.app/) to sync from AWS Secrets Manager, HashiCorp Vault, etc.
:::

### TLS / HTTPS

All public-facing services must use HTTPS:

```yaml
publicRouting:
  scheme: https

ingress:
  annotations:
    cert-manager.io/cluster-issuer: "letsencrypt-prod"
    nginx.ingress.kubernetes.io/ssl-redirect: "true"
  tls:
    - secretName: aileron-tls
      hosts:
        - example.com
        - "*.example.com"
```

Keycloak should be updated accordingly:

```yaml
keycloak:
  env:
    KC_HOSTNAME_STRICT: "true"
    KC_HOSTNAME_STRICT_HTTPS: "true"
    KC_PROXY_HEADERS: xforwarded
```

### Container Image Security

- Use a private registry; configure `global.imagePullSecrets`
- Pin image tags to commit SHAs or semantic versions — avoid `latest`
- Scan images regularly (Trivy, Snyk, etc.)

```yaml
global:
  imagePullSecrets:
    - name: registry-credentials

frontend:
  image:
    repository: your-registry.com/workspace-ui
    tag: v0.1.0
    pullPolicy: IfNotPresent
```

### Network Security

- Enable Cilium for network isolation between workspaces
- Restrict access to the Keycloak Admin Console
- Keep workspace domain allowlists as precise as possible

```yaml
cilium:
  enabled: true

firewall:
  defaults:
    workspace:
      allowedDomains:
        - github.com
        - api.github.com
        - registry.npmjs.org
        - pypi.org
        - api.anthropic.com
    browser:
      allowedDomains:
        - github.com
```

## Resource Planning

### Current live cluster settings (April 13, 2026, `aileron` namespace)

These are the actual `resources.requests` / `resources.limits` currently observed in the cluster:

| Workload | Container | Requests | Limits |
|---------|-----------|----------|--------|
| `aileron-aileron-workspace-manager` | `workspace-manager` | CPU `500m` / Memory `1Gi` | CPU `2` / Memory `2Gi` |
| `aileron-aileron-frontend` | `frontend` | Not set | Not set |
| `aileron-aileron-keycloak` | `keycloak` | Not set | Not set |
| `aileron-aileron-workspace-operator` | `workspace-operator` | Not set | Not set |
| `aileron-aileron-coturn` | `coturn` | Not set | Not set |
| `aileron-aileron-postgres` | `postgres` | Not set | Not set |
| `aileron-aileron-redis` | `redis` | Not set | Not set |
| `workspace-runtime-default-workspace` | `runtime` | Not set | Not set |
| `workspace-browser-default-workspace` | `browser` | Not set | Not set |
| `workspace-canvas-default-workspace` | `canvas` | Not set | Not set |

:::note
At the moment, only `workspace-manager` has explicit requests / limits in the live cluster. The other platform services and the current default workspace deployments do not yet set container resources in their Pod specs.
:::

### Platform Service Recommendations

| Service | CPU Request | CPU Limit | Memory Request | Memory Limit |
|---------|-------------|-----------|----------------|--------------|
| Frontend | 100m | 500m | 128Mi | 256Mi |
| Workspace Manager | 250m | 1000m | 256Mi | 512Mi |
| Workspace Operator | 100m | 500m | 128Mi | 256Mi |
| Keycloak | 500m | 1000m | 512Mi | 1Gi |
| PostgreSQL | 250m | 1000m | 256Mi | 1Gi |
| Redis | 100m | 500m | 128Mi | 256Mi |
| CoTURN | 100m | 500m | 64Mi | 128Mi |

### Workspace Pod Recommendations

| Component | CPU Request | CPU Limit | Memory Request | Memory Limit |
|-----------|-------------|-----------|----------------|--------------|
| Runtime | 500m | 2000m | 512Mi | 2Gi |
| Browser (neko) | 1000m | 2000m | 1Gi | 2Gi |
| Canvas Runtime | 250m | 1000m | 256Mi | 512Mi |

### Resource configuration entry points in the chart

The Helm chart already exposes the following values:

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

keycloak:
  resources: {}

coturn:
  resources: {}

kubernetes:
  workspaceDefaults:
    runtime:
      resources:
        requests:
          cpu: 500m
          memory: 2Gi
        limits:
          cpu: 2000m
          memory: 4Gi
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
          cpu: 500m
          memory: 1Gi
        limits:
          cpu: 2000m
          memory: 2Gi
```

:::caution Chart defaults vs live cluster
Although `kubernetes.workspaceDefaults.*.resources` already has defaults in the chart, and the current `aileron-aileron-platform-config` ConfigMap contains the corresponding JSON values, the existing `workspace-runtime-default-workspace`, `workspace-browser-default-workspace`, and `workspace-canvas-default-workspace` Deployments still show `resources: {}`. Treat the actual Deployment / Pod spec as the source of truth when verifying resource enforcement.
:::

```yaml
# Set resource limits in values.yaml
workspaceManager:
  resources:
    requests:
      cpu: 250m
      memory: 256Mi
    limits:
      cpu: 1000m
      memory: 512Mi
```

### How to inspect the current K8s resource settings

Inspect platform services and StatefulSets:

```bash
kubectl get deploy,statefulset -n aileron \
  -o jsonpath='{range .items[*]}{.kind}{"\t"}{.metadata.name}{"\t"}{range .spec.template.spec.containers[*]}{.name}{": requests="}{.resources.requests.cpu}{"/"}{.resources.requests.memory}{", limits="}{.resources.limits.cpu}{"/"}{.resources.limits.memory}{"; "}{end}{"\n"}{end}'
```

Inspect the current workspace Deployments:

```bash
kubectl get deploy workspace-runtime-default-workspace \
  workspace-browser-default-workspace \
  workspace-canvas-default-workspace \
  -n aileron -o yaml
```

Inspect whether the workspace default resources are present in platform config:

```bash
kubectl get configmap aileron-aileron-platform-config -n aileron \
  -o jsonpath='{.data.RUNTIME_K8S_RUNTIME_RESOURCES}{"\n"}{.data.RUNTIME_K8S_BROWSER_RESOURCES}{"\n"}{.data.RUNTIME_K8S_CANVAS_RESOURCES}{"\n"}'
```

### Storage Planning

| Purpose | Recommended Size | Access Mode | Notes |
|---------|------------------|-------------|-------|
| PostgreSQL | 20–50Gi | ReadWriteOnce | Scale with workspace count and history |
| Redis | 5–10Gi | ReadWriteOnce | Task queue and cache |
| Workspace data | 10–50Gi/workspace | ReadWriteOnce | Code and Claude data |

## External Service Integration

In production, consider using managed/external services rather than Helm-managed ones:

### External PostgreSQL

```yaml
postgres:
  enabled: false  # Disable bundled PostgreSQL

workspaceManager:
  env:
    DATABASE_URL: "postgresql://user:pass@rds-instance.region.rds.amazonaws.com:5432/aileron?sslmode=require"
```

### External Redis

```yaml
redis:
  enabled: false  # Disable bundled Redis

workspaceManager:
  env:
    REDIS_URL: "rediss://user:pass@redis-cluster.region.cache.amazonaws.com:6379"
    CELERY_BROKER_URL: "rediss://user:pass@redis-cluster.region.cache.amazonaws.com:6379/0"
    CELERY_RESULT_BACKEND: "rediss://user:pass@redis-cluster.region.cache.amazonaws.com:6379/1"
```

### External Keycloak

If you already have an enterprise Keycloak or another OIDC provider:

```yaml
keycloak:
  enabled: false  # Disable bundled Keycloak

workspaceManager:
  env:
    KEYCLOAK_SERVER_URL: "https://sso.company.com"
    KEYCLOAK_REALM: "aileron"
    KEYCLOAK_CLIENT_ID: "your-client-id"
```

## Backup Strategy

### Database Backup

```bash
# Back up PostgreSQL
kubectl exec -n aileron statefulset/aileron-postgres -- \
  pg_dump -U postgres aileron > backup-$(date +%Y%m%d).sql

# Schedule with a CronJob
```

### Keycloak Realm Backup

```bash
# Export realm settings
ADMIN_TOKEN=$(curl -s -X POST "https://keycloak.example.com/realms/master/protocol/openid-connect/token" \
  -d "client_id=admin-cli" \
  -d "username=admin" \
  -d "password=$ADMIN_PASSWORD" \
  -d "grant_type=password" | jq -r '.access_token')

curl -X POST "https://keycloak.example.com/admin/realms/aileron/partial-export?exportClients=true&exportGroupsAndRoles=true" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -o realm-backup-$(date +%Y%m%d).json
```

### Workspace Data Backup

- Use VolumeSnapshot on PVCs (if supported by the CSI driver)
- Or use Velero for cluster-wide backups

## Monitoring

### Health Check Endpoints

| Service | Endpoint |
|---------|----------|
| Workspace Manager | `GET /health` |
| Workspace Runtime | `GET /health` |
| Keycloak | `GET /health/ready` |
| PostgreSQL | `pg_isready` |
| Redis | `redis-cli ping` |

### Metrics

- **Keycloak**: `GET /metrics` (Prometheus format, requires `KC_METRICS_ENABLED=true`)
- **Celery Flower**: `http://<manager>:5555/api/tasks` (task monitoring)
- **Workspace Manager**: `/docs` endpoint can be used for API availability checks

### Recommended Alerts

| Condition | Severity | Notes |
|-----------|----------|-------|
| Pod CrashLoopBackOff | Critical | Service failure |
| Keycloak unhealthy | Critical | Affects all logins |
| PostgreSQL unhealthy | Critical | Database outage |
| Redis unhealthy | High | Task queue outage |
| PVC usage > 80% | Warning | Storage almost full |
| Rising Celery task failures | Warning | Automation failures |

## Upgrade Workflow

### Helm Chart Upgrade

```bash
# 1. Review changes
helm diff upgrade aileron helm/aileron \
  --namespace aileron \
  -f production-values.yaml

# 2. Back up
kubectl exec -n aileron statefulset/aileron-postgres -- \
  pg_dump -U postgres aileron > pre-upgrade-backup.sql

# 3. Execute the upgrade
helm upgrade aileron helm/aileron \
  --namespace aileron \
  -f production-values.yaml

# 4. Verify
kubectl get pods -n aileron
kubectl logs -n aileron deployment/aileron-workspace-manager --tail=50
```

### Database Migrations

```bash
# Run migrations (if provided)
./scripts/db/run-migrations.sh
```

:::caution
Always back up the database before upgrading. CRD updates require extra care — `helm upgrade` does not automatically update CRDs. If CRD schemas have changed:

```bash
kubectl apply -f helm/aileron/crds/
```
:::
