---
sidebar_position: 2
title: Kubernetes Mode
---

# Kubernetes Deployment

## When to Use

- Production or multi-user deployments
- Managing platform services with Helm
- Dynamic workspace scheduling via `workspace-operator`
- Per-workspace network isolation (Cilium)
- Public-facing access with Ingress / TLS

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                     Ingress Controller                       │
│  example.com → frontend                                      │
│  workspace-manager.example.com → manager                     │
│  keycloak.example.com → keycloak                             │
│  workspace-runtime-{id}.example.com → runtime pod            │
│  workspace-browser-{id}.example.com → browser pod            │
└────────┬──────────┬──────────┬──────────────────────────────┘
         │          │          │
   ┌─────▼────┐ ┌───▼────┐ ┌──▼───────┐   ┌──────────────┐
   │ Frontend  │ │Manager │ │Keycloak  │   │  Workspace   │
   │ Deploy    │ │Deploy  │ │Deploy    │   │  Operator    │
   └──────────┘ └───┬────┘ └──────────┘   │  Deploy      │
                    │                      └──────┬───────┘
              ┌─────▼──────┐                      │ reconcile
              │ Celery +   │               ┌──────▼───────┐
              │ Flower     │               │ Workspace CR │
              └────────────┘               │ (CRD)        │
                                           └──────┬───────┘
              ┌────────────┐                      │ creates
              │ PostgreSQL │               ┌──────▼───────┐
              │ StatefulSet│               │ Runtime Pod  │
              └────────────┘               │ Browser Pod  │
              ┌────────────┐               │ Next.js Pod  │
              │   Redis    │               │ Service      │
              │ StatefulSet│               │ Ingress      │
              └────────────┘               │ CiliumPolicy │
              ┌────────────┐               └──────────────┘
              │  CoTURN    │
              │ Deployment │
              └────────────┘
```

## Helm Management Scope

The Helm chart manages the following platform services:

| Resource Type | Items |
|---------------|-------|
| **Deployment** | frontend, workspace-manager, workspace-operator, keycloak, coturn |
| **StatefulSet** | postgres, redis |
| **Service** | All service ClusterIPs, CoTURN NodePort |
| **Ingress** | Unified ingress for frontend, workspace-manager, keycloak |
| **ConfigMap** | platform-config, workspace-routing, firewall-defaults, keycloak-realm, frontend-nginx |
| **Secret** | Database passwords, Keycloak password |
| **RBAC** | workspace-operator ClusterRole, workspace-manager Role, ServiceAccounts |
| **CRD** | `workspaces.platform.aileron.io` |
| **Job** | postgres-bootstrap (database initialization) |

:::note
Dynamic resources per workspace (Pods, Services, Ingresses, CiliumNetworkPolicies) are not managed by Helm directly — they are reconciled by the workspace-operator based on the Workspace CR.
:::

## Requirements

- Kubernetes cluster (1.26+ recommended)
- `kubectl`
- `helm` (3.12+ recommended)
- Ingress Controller (nginx by default)
- Manageable DNS (workspace hosts must resolve; use wildcard DNS or automate per-host records)
- TLS certificate (for public deployment, optionally with cert-manager)
- `Cilium` (for full per-workspace firewall)
- Shared storage (ReadWriteMany PVC or equivalent)

## Helm Chart Location

```
helm/aileron/
├── Chart.yaml
├── values.yaml
├── crds/
│   └── platform.aileron.io_workspaces.yaml
├── templates/
│   ├── _helpers.tpl
│   ├── frontend-deployment.yaml
│   ├── workspace-manager-deployment.yaml
│   ├── workspace-operator-deployment.yaml
│   ├── keycloak-deployment.yaml
│   ├── coturn-deployment.yaml
│   ├── postgres-statefulset.yaml
│   ├── redis-statefulset.yaml
│   ├── ingress.yaml
│   ├── platform-configmap.yaml
│   ├── workspace-routing-configmap.yaml
│   ├── firewall-defaults-configmap.yaml
│   ├── workspace-manager-rbac.yaml
│   ├── workspace-operator-rbac.yaml
│   └── ... (other services / secrets / jobs)
└── files/
    └── realm.json
```

## Installation

### Validate the Chart

```bash
# Lint
helm lint helm/aileron

# Render templates
helm template test-release helm/aileron
```

### Install

```bash
helm install aileron helm/aileron \
  --namespace aileron \
  --create-namespace
```

### Install with Custom Values

```bash
# Copy defaults and edit
cp helm/aileron/values.yaml my-values.yaml
# Edit my-values.yaml ...

helm install aileron helm/aileron \
  --namespace aileron \
  --create-namespace \
  -f my-values.yaml
```

### Upgrade

```bash
helm upgrade aileron helm/aileron \
  --namespace aileron
```

### Uninstall

```bash
helm uninstall aileron --namespace aileron
```

:::caution CRDs Are Not Auto-Removed
`helm uninstall` does not remove CRDs. To fully clean up:

```bash
kubectl delete crd workspaces.platform.aileron.io
```
:::

## Public Routing Configuration

Kubernetes mode uses host-based routing (subdomain style) rather than path-based ingress.

Current behavior:

- Helm creates one platform Ingress for Frontend, Workspace Manager, and Keycloak
- `workspace-operator` creates one separate Ingress each for `workspace-runtime`, `workspace-browser`, and `workspace-nextjs` whenever a workspace is created

So workspace traffic is not routed through a single wildcard Ingress rule. The operator expands the host patterns with `workspaceId` and creates explicit Ingress hosts.

### Helm Values

| Value | Default | Description |
|-------|---------|-------------|
| `publicRouting.scheme` | `http` | `http` or `https` |
| `publicRouting.baseDomain` | `aileron.local` | Base domain |
| `publicRouting.frontendHost` | `{baseDomain}` | Frontend host |
| `publicRouting.workspaceManagerHost` | `workspace-manager.{baseDomain}` | Manager host |
| `publicRouting.keycloakHost` | `keycloak.{baseDomain}` | Keycloak host |
| `publicRouting.runtimeHostPattern` | `workspace-runtime-{workspaceId}.{baseDomain}` | Runtime host pattern |
| `publicRouting.browserHostPattern` | `workspace-browser-{workspaceId}.{baseDomain}` | Browser host pattern |
| `publicRouting.nextjsHostPattern` | `workspace-nextjs-{workspaceId}.{baseDomain}` | Next.js host pattern |

`{baseDomain}` and `{workspaceId}` are placeholders that Helm templates resolve at deploy time.

### Example

Using `example.com` as the example domain:

```bash
helm upgrade --install aileron helm/aileron \
  --namespace aileron \
  --create-namespace \
  --set publicRouting.scheme=https \
  --set publicRouting.baseDomain=example.com \
  --set publicRouting.frontendHost='{baseDomain}' \
  --set publicRouting.workspaceManagerHost='workspace-manager.{baseDomain}' \
  --set publicRouting.keycloakHost='keycloak.{baseDomain}' \
  --set publicRouting.runtimeHostPattern='workspace-runtime-{workspaceId}.{baseDomain}' \
  --set publicRouting.browserHostPattern='workspace-browser-{workspaceId}.{baseDomain}' \
  --set publicRouting.nextjsHostPattern='workspace-nextjs-{workspaceId}.{baseDomain}'
```

Public host mapping:

| Service | Host |
|---------|------|
| Frontend | `https://example.com` |
| Workspace Manager | `https://workspace-manager.example.com` |
| Keycloak | `https://keycloak.example.com` |
| Workspace Runtime | `https://workspace-runtime-<workspaceId>.example.com` |
| Workspace Browser | `https://workspace-browser-<workspaceId>.example.com` |
| Workspace Next.js | `https://workspace-nextjs-<workspaceId>.example.com` |

Each new workspace gets its own set of URLs from these patterns. For example, `default-workspace` becomes:

- `workspace-runtime-default-workspace.example.com`
- `workspace-browser-default-workspace.example.com`
- `workspace-nextjs-default-workspace.example.com`

## DNS & TLS Requirements

### DNS Records

Required DNS records:

| Type | Name | Target | Purpose |
|------|------|--------|---------|
| A / CNAME | `example.com` | Ingress IP | Frontend |
| A / CNAME | `workspace-manager.example.com` | Ingress IP | Manager API |
| A / CNAME | `keycloak.example.com` | Ingress IP | Authentication |
| A / CNAME | `*.example.com` or automated `workspace-*-<workspaceId>.example.com` records | Ingress IP | All workspace subdomains |

:::tip
Kubernetes currently creates explicit Ingress hosts for each workspace component, such as `workspace-runtime-default-workspace.example.com`. A wildcard DNS record is the simplest way to cover these dynamic hosts, but you can also create per-host A/CNAME records automatically with tools such as ExternalDNS.
:::

### TLS Setup

With cert-manager for automatic certificate management:

```yaml
# values.yaml
ingress:
  enabled: true
  className: "nginx"
  annotations:
    cert-manager.io/cluster-issuer: "letsencrypt-prod"
  tls:
    - secretName: aileron-tls
      hosts:
        - example.com
        - "*.example.com"
```

:::caution Workspace TLS behavior
`values.yaml` `ingress.tls` only applies to the Helm-managed platform Ingress. The workspace Ingresses created by `workspace-operator` currently include host/path rules and nginx annotations, but do not set `spec.tls`. If workspace subdomains must use HTTPS, the ingress controller usually needs to serve a wildcard or default certificate, or the operator must be extended to configure TLS on those Ingresses.
:::

Or manually create a TLS Secret:

```bash
kubectl create secret tls aileron-tls \
  --cert=fullchain.pem \
  --key=privkey.pem \
  -n aileron
```

## Internal vs External URLs

:::important
`internalUrl` and `externalUrl` have distinct roles. Do not mix them up.
:::

| Type | Purpose | Use Case |
|------|---------|----------|
| `internalUrl` | Cluster-internal Service DNS | pod-to-pod, service-to-service calls |
| `externalUrl` | Public Ingress URL | Browser, OIDC redirect, WebSocket, preview |

Internal URL examples:

```
http://workspace-manager.<namespace>.svc.cluster.local:3001
http://workspace-runtime-<workspaceId>.<namespace>.svc.cluster.local:3002
http://workspace-browser-<workspaceId>.<namespace>.svc.cluster.local:6080
http://workspace-nextjs-<workspaceId>.<namespace>.svc.cluster.local:3003
```

The workspace-routing ConfigMap records the full routing contract, including service name templates and port mappings:

| Setting | Value |
|---------|-------|
| `RUNTIME_SERVICE_NAME_TEMPLATE` | `workspace-runtime-{workspaceId}` |
| `BROWSER_SERVICE_NAME_TEMPLATE` | `workspace-browser-{workspaceId}` |
| `NEXTJS_SERVICE_NAME_TEMPLATE` | `workspace-nextjs-{workspaceId}` |
| `RUNTIME_SERVICE_PORT` | `3002` |
| `BROWSER_SERVICE_PORT` | `6080` |
| `NEXTJS_SERVICE_PORT` | `3003` |

## Workspace CRD

The Workspace Operator uses a custom CRD `workspaces.platform.aileron.io` to manage workspaces:

```yaml
apiVersion: platform.aileron.io/v1alpha1
kind: Workspace
metadata:
  name: ws-example
  namespace: workspace-system
spec:
  workspaceId: "my-workspace"
  ownerId: "user-123"
  provisioner: kubernetes
  runtime:
    imageKey: default
    image: ailerondocker/workspace-runtime:latest
    resources: {}
  browser:
    enabled: true
    image: ailerondocker/workspace-browser:latest
  nextjs:
    enabled: true
    image: ailerondocker/workspace-nextjs:latest
  workspacePath: /workspace
  targetNamespace: workspace-system
  git:
    url: "https://github.com/example/repo.git"
    branch: main
  envVars:
    - key: NODE_ENV
      value: production
  firewall:
    workspace:
      networkAccessEnabled: true
      domainAccessMode: specific
      allowedDomains:
        - github.com
        - api.anthropic.com
    browser:
      networkAccessEnabled: true
      domainAccessMode: specific
      allowedDomains:
        - google.com
```

### CRD Status

The Operator writes workspace status to `.status`:

| Field | Description |
|-------|-------------|
| `status.phase` | Overall workspace phase |
| `status.targetNamespace` | Namespace where pods are actually deployed |
| `status.components.runtime.phase` | Runtime pod phase |
| `status.components.runtime.internalUrl` | Runtime internal URL |
| `status.components.runtime.externalUrl` | Runtime external URL |
| `status.components.browser.*` | Browser pod phase and URLs |
| `status.components.nextjs.*` | Next.js pod phase and URLs |
| `status.firewall.*.effectiveAllowedDomains` | Effective domain allowlist |

### Operations Triggers

Use `spec.operations` to trigger component restarts:

```yaml
spec:
  operations:
    restartWorkspaceAt: "2026-04-09T10:00:00Z"   # Restart entire workspace
    restartRuntimeAt: "2026-04-09T10:00:00Z"      # Restart runtime only
    restartBrowserAt: "2026-04-09T10:00:00Z"      # Restart browser only
    restartNextjsAt: "2026-04-09T10:00:00Z"       # Restart nextjs only
```

## Kubernetes Settings

| Helm Value | Env Variable | Default | Description |
|------------|--------------|---------|-------------|
| `kubernetes.provisioner` | `RUNTIME_PROVISIONER` | `kubernetes` | Default provisioner |
| `kubernetes.defaultNamespace` | `RUNTIME_K8S_NAMESPACE` | `workspace-system` | Default namespace |
| `kubernetes.allowedNamespaces` | `RUNTIME_K8S_ALLOWED_NAMESPACES` | `[workspace-system, default]` | Allowed namespaces |
| `kubernetes.serviceType` | `RUNTIME_K8S_SERVICE_TYPE` | `ClusterIP` | Service type |
| `kubernetes.nodePort` | `RUNTIME_K8S_NODE_PORT` | _(empty)_ | NodePort |
| `kubernetes.nodeAddress` | `RUNTIME_K8S_NODE_ADDRESS` | `127.0.0.1` | Node address |
| `kubernetes.pvcName` | `RUNTIME_K8S_PVC_NAME` | `workspace-runtime-pvc` | PVC name |
| `kubernetes.runtimeImage` | `RUNTIME_K8S_IMAGE` | `ailerondocker/workspace-runtime:latest` | Runtime image |
| `kubernetes.browserImage` | `RUNTIME_K8S_BROWSER_IMAGE` | `ailerondocker/workspace-browser:latest` | Browser image |
| `kubernetes.nextjsImage` | `RUNTIME_K8S_NEXTJS_IMAGE` | `ailerondocker/workspace-nextjs:latest` | Next.js image |
| `kubernetes.watchNamespace` | `WATCH_NAMESPACE` | _(empty, all namespaces)_ | Operator watch namespace |

### Overriding Namespace and Allowlist

```bash
helm upgrade --install aileron helm/aileron \
  --namespace aileron \
  --create-namespace \
  --set kubernetes.defaultNamespace=workspace-system \
  --set kubernetes.allowedNamespaces[0]=workspace-system \
  --set kubernetes.allowedNamespaces[1]=team-a \
  --set kubernetes.allowedNamespaces[2]=team-b
```

## RBAC & Service Accounts

### Workspace Operator

The Operator needs **ClusterRole**-level permissions to manage workspace resources across namespaces:

| API Group | Resources | Verbs |
|-----------|-----------|-------|
| `""` (core) | pods, services, PVC, events, configmaps, secrets | All |
| `apps` | deployments, statefulsets | All |
| `networking.k8s.io` | ingresses | All |
| `cilium.io` | ciliumnetworkpolicies | All (only when cilium is enabled) |
| `platform.aileron.io` | workspaces, workspaces/status, workspaces/finalizers | All |

### Workspace Manager

The Manager only needs **Role**-level permissions (limited to the workspace namespace):

| API Group | Resources | Verbs |
|-----------|-----------|-------|
| `platform.aileron.io` | workspaces | All |

## Storage & Persistence

### Platform Service Persistence

| Service | Default Size | Access Mode | Purpose |
|---------|--------------|-------------|---------|
| PostgreSQL | 10Gi | ReadWriteOnce | Database |
| Redis | 5Gi | ReadWriteOnce | Cache and task queue |

```yaml
# values.yaml example
postgres:
  persistence:
    enabled: true
    size: 20Gi
    storageClass: "fast-ssd"

redis:
  persistence:
    enabled: true
    size: 5Gi
```

### Workspace Storage

Workspaces use PVC mounts for their working directories. The Operator configures mounts automatically based on `kubernetes.pvcName`:

```yaml
kubernetes:
  pvcName: workspace-runtime-pvc
```

:::tip Shared Storage
If multiple workspaces need to share base images or tools, use a ReadWriteMany StorageClass (NFS, CephFS, EFS, etc.).
:::

### Knowledge Base Storage

Knowledge Bases use a dedicated shared PVC managed by the Helm chart:

```yaml
kubernetes:
  knowledgeBases:
    pvcName: knowledge-bases-pvc
    size: 20Gi
    accessModes:
      - ReadWriteMany
    storageClassName: hostpath
```

Mount flow:

- Helm creates `knowledge-bases-pvc`
- `workspace-manager` mounts it at `/host/knowledge-bases`
- `workspace-operator` mounts each attached KB into runtime Pods at `/knowledge/<alias>` using `subPath=<kbId>`

Local development guidance:

- the default `hostpath` value is a single-node fallback for local clusters
- it is acceptable for Docker Desktop or local Kubernetes smoke testing
- it is not a substitute for real multi-node RWX shared storage

Production guidance:

- switch `kubernetes.knowledgeBases.storageClassName` to a real RWX shared class such as `nfs`
- `helm/values-rke.yaml` already contains this override
- verify `knowledge-bases-pvc` is `Bound` before validating KB attach / mount flows

Recommended checks:

```bash
kubectl get pvc -n aileron knowledge-bases-pvc
kubectl describe pvc -n aileron knowledge-bases-pvc
kubectl describe deployment -n aileron aileron-workspace-manager
```

## CoTURN (WebRTC TURN Server)

The workspace-browser uses [neko](https://github.com/m1k1o/neko) to stream the desktop via WebRTC. In Kubernetes, multiple NAT layers exist between the neko pod and the user's browser — a TURN server is required to relay WebRTC media.

### Why TURN Is Required

WebRTC uses ICE to find a working path between peers:

```
Browser (client) ←── WebSocket signaling ──→ neko pod (K8s)
      │                                             │
      └──── direct (host candidate) ───────────────┘
            pod IP (10.x.x.x) unreachable → fails
      │                                             │
      └──── TURN relay ─── coturn ────────────────┘
            both sides get relay address → succeeds
```

Without TURN, ICE only has host candidates (pod-internal IPs), and the browser cannot reach them. The browser component stays stuck at **Connecting...**.

### Architecture

```
[Browser]                   [K8s Node]
    │  turn:nodeIP:nodePort      │
    │──────────────────────────→│ NodePort 30479
    │                            │  ↓ (kube-proxy)
    │                         [coturn pod]
    │                         hostNetwork: true
    │                         port 3478 bound to nodeIP
    │                         relay: nodeIP:49152-65535
    │←─── relay at nodeIP:49xxx ─┘
    │
[neko pod]
    │  turn:nodeIP:nodePort
    │──────────────────────────→ [coturn] (reachable inside K8s)
    │←─── relay at nodeIP:49yyy ─┘
    │
Both relay addresses are on nodeIP — coturn bridges them → WebRTC connected
```

### Why `hostNetwork: true`

TURN relay uses ephemeral UDP ports (default 49152–65535). **NodePort cannot map this entire range** — one NodePort per port is impractical. With `hostNetwork: true`:

- The coturn pod shares the node's network namespace
- Relay ports bind directly to the node IP and are reachable externally
- The signaling port (3478) is also directly on the node IP

This is the standard pattern for deploying TURN servers in NodePort-only Kubernetes clusters.

### `host` vs `frontendHost`

neko v3 separates ICE server configuration into **backend** (neko pod → TURN) and **frontend** (browser → TURN). This allows different addresses in environments where the same IP is not reachable from both sides:

| Setting | Used by | Description |
|---------|---------|-------------|
| `coturn.host` | neko pod (backend) | IP pods use to reach TURN — the node IP |
| `coturn.frontendHost` | User's browser (frontend) | IP browsers use to reach TURN. Defaults to `host` if not set. |

:::info Production
In production, the browser connects directly to the node IP (`host`). **`frontendHost` does not need to be set** — it falls back to `host` automatically.
:::

:::info Local development (Docker Desktop)
Docker Desktop only exposes NodePort services to the Mac browser via `localhost`, not via the VM IP (`192.168.65.3`) directly. Therefore:
- `host` = `192.168.65.3` (the node IP, reachable from pods)
- `frontendHost` = `127.0.0.1` (reachable from the Mac browser via Docker Desktop's localhost proxy)
:::

### Helm Values

| Helm Value | Default | Description |
|------------|---------|-------------|
| `coturn.enabled` | `true` | Enable TURN server |
| `coturn.port` | `3478` | coturn listening port (inside container) |
| `coturn.nodePort` | `30478` | K8s NodePort |
| `coturn.host` | `192.168.65.3` | Externally reachable node IP (backend) |
| `coturn.frontendHost` | `""` (same as `host`) | IP browsers use to reach TURN (frontend) |
| `coturn.username` | `aileron` | TURN username |
| `coturn.credential` | `aileron-turn-secret` | TURN credential (use a strong secret in production) |
| `coturn.realm` | `aileron.localhost` | TURN realm |

### Configuration Examples

**Production (NodePort, node has a public IP):**

```yaml
coturn:
  host: "203.0.113.10"      # node's public IP
  nodePort: 30479
  username: "aileron"
  credential: "your-strong-secret-here"
  # frontendHost not needed — defaults to host
```

Firewall must allow:
- `nodePort` (default 30479): UDP + TCP for TURN signaling
- `49152–65535`: UDP for TURN relay media

**Local development (Docker Desktop):**

```yaml
coturn:
  host: "192.168.65.3"      # Docker Desktop node IP (reachable from pods)
  frontendHost: "127.0.0.1" # Mac browser reaches TURN via localhost proxy
  nodePort: 30479
```

**Multi-node clusters:**

`hostNetwork: true` means only one coturn instance per node (port 3478 conflict). Pin coturn to a dedicated node using `nodeSelector`:

```bash
# Label the designated TURN node
kubectl label node <turn-node> role=turn

# In values.yaml, add:
# coturn.nodeSelector.role: turn
```

Set `coturn.host` to that specific node's IP.

### Verifying TURN Connectivity

A successful connection shows in the browser pod log:

```
ICE connection state changed: connected
peer connection state changed: connected
set webrtc connected: connected=true
```

If the browser is stuck at **Connecting...**, check in order:

1. **Is coturn advertising the correct relay address?**

   ```bash
   kubectl logs -n aileron deployment/aileron-coturn | grep "Relay address"
   # Must show node IP (e.g. 203.0.113.10), NOT pod IP (10.x.x.x)
   ```

   Pod IP in the relay address means `hostNetwork: true` is missing or `--external-ip` is not set.

2. **Is UDP 49152–65535 open on the firewall?**

3. **Local dev only:** Is `frontendHost` set to `127.0.0.1` (not the Docker Desktop VM IP)?

## Ingress Configuration

The default configuration uses the nginx ingress controller with long timeouts required for WebSockets:

```yaml
ingress:
  enabled: true
  className: "nginx"
  annotations:
    nginx.ingress.kubernetes.io/proxy-read-timeout: "3600"
    nginx.ingress.kubernetes.io/proxy-send-timeout: "3600"
    nginx.ingress.kubernetes.io/proxy-http-version: "1.1"
```

The Helm chart auto-generates Ingress rules for:
- Frontend (`frontendHost`)
- Workspace Manager (`workspaceManagerHost`)
- Keycloak (`keycloakHost`)

:::note
Dynamic workspace Ingresses (runtime, browser, nextjs) are created by the Operator during reconciliation. Each workspace gets its own hosts and Ingress objects, separate from the Helm-managed platform Ingress.
:::

## Firewall Defaults

In Kubernetes mode, the platform installs a firewall-defaults ConfigMap separated into workspace and browser groups:

### Default Allowed Domains

**Workspace Runtime:**
- `github.com`, `api.github.com`, `objects.githubusercontent.com`, `raw.githubusercontent.com`
- `registry.npmjs.org`, `npmjs.com`
- `pypi.org`, `files.pythonhosted.org`
- `api.anthropic.com`

**Workspace Browser:**
- `github.com`
- `google.com`, `gstatic.com`, `googleapis.com`

### Overriding Firewall Defaults

```bash
helm upgrade --install aileron helm/aileron \
  --namespace aileron \
  --set firewall.defaults.workspace.allowedDomains[0]=github.com \
  --set firewall.defaults.workspace.allowedDomains[1]=registry.npmjs.org \
  --set firewall.defaults.browser.allowedDomains[0]=google.com \
  --set firewall.defaults.browser.allowedDomains[1]=gstatic.com
```

The Operator and Manager read this ConfigMap via the `FIREWALL_DEFAULTS_CONFIGMAP_NAME` env variable. Once Cilium is enabled, the Operator creates a `CiliumNetworkPolicy` per workspace.

```yaml
# Enable Cilium
cilium:
  enabled: true
```

## Helm Values Reference

### Global

| Value | Default | Description |
|-------|---------|-------------|
| `global.imagePullSecrets` | `[]` | Image pull secrets |
| `global.storageClass` | `""` | Default StorageClass |

### Service Toggles

| Value | Default | Description |
|-------|---------|-------------|
| `frontend.enabled` | `true` | Enable Frontend |
| `workspaceManager.enabled` | `true` | Enable Manager |
| `workspaceOperator.enabled` | `true` | Enable Operator |
| `postgres.enabled` | `true` | Enable PostgreSQL |
| `redis.enabled` | `true` | Enable Redis |
| `keycloak.enabled` | `true` | Enable Keycloak |
| `coturn.enabled` | `true` | Enable CoTURN |

### Service Images

| Value | Default |
|-------|---------|
| `frontend.image.repository` | `ailerondocker/workspace-ui` |
| `frontend.image.tag` | `latest` |
| `workspaceManager.image.repository` | `ailerondocker/workspace-manager` |
| `workspaceManager.image.tag` | `latest` |
| `workspaceOperator.image.repository` | `ailerondocker/workspace-operator` |
| `workspaceOperator.image.tag` | `latest` |

### Credentials

| Value | Default | Description |
|-------|---------|-------------|
| `postgres.auth.username` | `postgres` | DB user |
| `postgres.auth.password` | `postgres` | DB password |
| `postgres.auth.appDatabase` | `aileron` | Application DB |
| `postgres.auth.keycloakDatabase` | `keycloak` | Keycloak DB |
| `keycloak.auth.adminUser` | `admin` | Keycloak admin |
| `keycloak.auth.adminPassword` | `admin` | Keycloak password |
| `workspaceManager.env.SECRET_KEY` | _(dev default)_ | JWT signing key |

### Kubernetes Storage

| Value | Default | Description |
|-------|---------|-------------|
| `kubernetes.pvcName` | `workspace-runtime-pvc` | Workspace working directory PVC |
| `kubernetes.knowledgeBases.pvcName` | `knowledge-bases-pvc` | Dedicated shared PVC name for Knowledge Bases |
| `kubernetes.knowledgeBases.size` | `20Gi` | Knowledge Base PVC capacity |
| `kubernetes.knowledgeBases.accessModes` | `[ReadWriteMany]` | Knowledge Base PVC access modes |
| `kubernetes.knowledgeBases.storageClassName` | `hostpath` | Local dev fallback; switch to a shared RWX class such as `nfs` for production |

## Verifying the Deployment

After installation, run the following checks:

```bash
# Check all pod statuses
kubectl get pods -n aileron

# Check services
kubectl get svc -n aileron

# Check ingress
kubectl get ingress -n aileron

# Verify CRD is installed
kubectl get crd workspaces.platform.aileron.io

# View Workspace CRs (if any)
kubectl get workspaces -A

# Check ConfigMaps
kubectl get configmap -n aileron

# View logs for specific services
kubectl logs -n aileron deployment/aileron-workspace-manager
kubectl logs -n aileron deployment/aileron-workspace-operator
```

## Current Limitations

- How dynamic workspace hosts are served (single Ingress, Gateway API, or a custom controller) depends on your cluster's ingress capabilities
- Fully public domain routing requires DNS and TLS to be set up; otherwise Keycloak/OIDC, preview, and WebSockets will not work externally
- Enabling per-workspace domain allowlists requires `Cilium`
- CoTURN `host` must be set to the node's actual routable IP. Production deployments do not need `frontendHost` (it defaults to `host`). Local Docker Desktop development requires `frontendHost: "127.0.0.1"` because Docker Desktop only proxies NodePort services through localhost, not via the VM IP directly.
