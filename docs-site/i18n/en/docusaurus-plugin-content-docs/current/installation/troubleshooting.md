---
title: Deployment Troubleshooting
description: Common diagnostic flows for Kubernetes, Docker, and platform services
---

# Deployment Troubleshooting

Capture the actual state before changing configuration. Redact any Secret, token, cookie, internal address, or user data from output before sharing it.

## Helm Installation or Upgrade Fails

```bash
helm status aileron -n workspace-system
helm history aileron -n workspace-system
helm get values aileron -n workspace-system -o yaml
kubectl get events -n workspace-system \
  --sort-by='.lastTimestamp'
kubectl get jobs,pods -n workspace-system
```

Run lint, rendering, and server-side dry-run again to determine whether the failure occurred during values validation, API admission, a hook Job, or workload readiness.

## A Pod Cannot Start

```bash
kubectl get pods -n workspace-system -o wide
kubectl describe pod -n workspace-system <pod-name>
kubectl logs -n workspace-system <pod-name> --all-containers
kubectl logs -n workspace-system <pod-name> --all-containers --previous
```

Use the events to distinguish:

- `ErrImagePull` / `ImagePullBackOff`: Check the digest, imagePullSecret, Registry CA, and node networking.
- `CreateContainerConfigError`: Check Secret keys, ConfigMap keys, and the security context.
- `CrashLoopBackOff`: Compare current and previous logs, termination reason, and exit code.
- `Pending`: Check resources, taints, affinity, PVCs, and the StorageClass binding mode.

## A PVC Is Pending or Permissions Fail

```bash
kubectl get storageclass
kubectl get pvc,pv -n workspace-system
kubectl describe pvc -n workspace-system <pvc-name>
kubectl get events -n workspace-system \
  --field-selector involvedObject.kind=PersistentVolumeClaim
```

Do not run `chown` on the volume root from an application image, add a privileged initContainer, or disable NFS `root_squash`. Return to [Kubernetes Storage Design](./kubernetes-storage.md) and verify the StorageClass, GID, setgid bit, and export policy.

## Workspace Component State Is Inconsistent

```bash
kubectl get workspace -n workspace-system <workspace-name> -o yaml
kubectl get deployment,pod,service,ingress \
  -n workspace-system \
  -l aileron.io/workspace-id=<workspace-id>
```

Runtime, Browser, and Canvas are independent components. Inspect the phase, desired/observed revision, Pod UID, and reason for each item in `status.components`. Before the initial bootstrap completes, it is expected that Browser and Canvas do not yet exist. After bootstrap, an error in one component must not rebuild other healthy components.

When Runtime bootstrap fails:

```bash
kubectl logs -n workspace-system \
  --selector='aileron.io/workspace-id=<workspace-id>,aileron.io/component=workspace-runtime' \
  --all-containers \
  --tail=200
kubectl get pod -n workspace-system \
  -l aileron.io/workspace-id=<workspace-id> \
  -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.status.containerStatuses[*].state.terminated.reason}{"\t"}{.status.containerStatuses[*].state.terminated.message}{"\n"}{end}'
```

Use the stable error code to inspect Git, agent defaults, custom setup, or bootstrap state in Runtime HOME. Do not hide the failure by rebuilding the other two components.

## Firewall Is Not Applied

First obtain the desired revision from the Manager firewall API, then compare the Workspace CR and Cilium policy:

```bash
kubectl get workspace -n workspace-system <workspace-name> -o yaml
kubectl get ciliumnetworkpolicy -n workspace-system \
  -l aileron.io/workspace-id=<workspace-id> \
  -o yaml
kubectl logs -n workspace-system \
  --selector='app.kubernetes.io/instance=aileron,app.kubernetes.io/component=workspace-operator' \
  --all-containers \
  --tail=200
```

`applying` means that the observed revision has not caught up with the desired revision. Handle an `error` according to its error code. A firewall update must not change the Runtime, Browser, or Canvas Pod UID.

## Ingress, TLS, or WebSocket Fails

```bash
kubectl get ingress -n workspace-system
kubectl describe ingress -n workspace-system <ingress-name>
kubectl get secret -n workspace-system aileron-platform-tls \
  -o jsonpath='{.type}{"\n"}'
curl -vkI https://aileron.apps.example.com/
```

Confirm that Platform Public Origin DNS, certificate SANs, IngressClass, and WebSocket timeout settings agree. Verify that `/api/v1` and `/workspaces/{uuid}/runtime|browser|canvas` enter Frontend's gateway through the same Ingress. Do not use public URLs for in-cluster service communication.

## Browser WebRTC or TURN Fails

Set the installation names first. These examples do not assume a fixed release or namespace:

```bash
export RELEASE_NAMESPACE=<release-namespace>
export RELEASE_NAME=<release-name>
export AILERON_FULLNAME=<chart-fullname>
export WORKSPACE_ID=<workspace-id>
export WORKSPACE_RESOURCE=workspace-${WORKSPACE_ID}
```

`AILERON_FULLNAME` must be the fullname rendered by the Helm chart. `fullnameOverride` takes precedence.
Otherwise, `nameOverride` (or the chart name when it is unset) supplies the name segment: when the release
name already contains that segment, the fullname is the release name; in all other cases it is
`<release-name>-<effective-chart-name>`. Do not append `-aileron` unconditionally.

Check these four layers in order. Do not use retries in a later layer to hide a failure in an earlier one.

### 1. Control Plane and Admission

```bash
kubectl get workspace -n "${RELEASE_NAMESPACE}" "${WORKSPACE_RESOURCE}" \
  -o jsonpath='{.status.browserConnectivity}{"\n"}'
kubectl logs -n "${RELEASE_NAMESPACE}" \
  deployment/${AILERON_FULLNAME}-workspace-operator \
  --tail=200
kubectl logs -n "${RELEASE_NAMESPACE}" \
  deployment/${AILERON_FULLNAME}-workspace-manager \
  --tail=200
```

Using the same authenticated actor, call `/api/v1/workspaces/${WORKSPACE_ID}/availability` and
`POST /api/v1/workspaces/${WORKSPACE_ID}/browser/access`. `ready`, or `degraded` with a TTL-valid
`allowed` admission projection, can issue access. `pending` and `not_ready` map to
`409 BROWSER_CONNECTIVITY_NOT_READY`. Evidence found expired at admission time is also projected as
`not_ready` / `denied` and returns the same 409. Only `unavailable` maps to
`503 BROWSER_CONNECTIVITY_UNAVAILABLE`.

### 2. Browser Pod Backend Probe

```bash
kubectl get secret -n "${RELEASE_NAMESPACE}" <turn-secret-name> \
  -o jsonpath='{.metadata.resourceVersion}{"\n"}'
kubectl logs -n "${RELEASE_NAMESPACE}" \
  --selector="aileron.io/workspace-id=${WORKSPACE_ID},aileron.io/component=workspace-browser" \
  -c connectivity-probe \
  --tail=200
kubectl get deployment -n "${RELEASE_NAMESPACE}" \
  -l "aileron.io/workspace-id=${WORKSPACE_ID},aileron.io/component=workspace-browser" \
  -o jsonpath='{range .items[0].spec.template.spec.containers[?(@.name=="connectivity-probe")].env[?(@.name=="TURN_PROBE_IDENTITY")]}{.value}{"\n"}{end}'
kubectl get ciliumnetworkpolicy -n "${RELEASE_NAMESPACE}" \
  -l "aileron.io/workspace-id=${WORKSPACE_ID}" \
  -o yaml
```

Compare `profileRevision`, `credentialRevision`, `observedAt`, `expiresAt`, and `backendState`.
`TURN_PROBE_IDENTITY` must be `backend:${WORKSPACE_ID}`. The issued TURN REST username is
`${expiry}:backend:${WORKSPACE_ID}` and provides TURN audit attribution only.
`BACKEND_TURN_PATH_NOT_READY` means the sidecar cannot complete authenticated allocation and a relay round
trip from the Browser network namespace. `BACKEND_EVIDENCE_UNAVAILABLE` means the sidecar evidence endpoint
cannot be read. Then check TURN DNS, TLS, listener, relay UDP range, and the control/relay egress rules.

### 3. Frontend External Vantage

```bash
kubectl logs -n "${RELEASE_NAMESPACE}" \
  deployment/${AILERON_FULLNAME}-connectivity-evidence-gateway \
  --tail=200
kubectl get workspace -n "${RELEASE_NAMESPACE}" "${WORKSPACE_RESOURCE}" \
  -o jsonpath='{.status.browserConnectivity.frontendState}{"\n"}{.status.browserConnectivity.expiresAt}{"\n"}'
```

On the Agent host, inspect `connectivity-external-agent` logs and verify installation ID, vantage ID,
Gateway HTTPS, the TURN listener, and the relay range. `FRONTEND_TURN_PATH_NOT_READY` means at least one
required vantage has no matching, unexpired evidence. Inspect the Coturn DaemonSet in `coturn.namespace`
only when `coturn.enabled=true`; external TURN does not create that resource.

When aggregate state is insufficient, use an authorized control-plane execution context that holds the
internal token and read `GET /v1/evidence/{profileRevision}/{vantage}` separately for every
`requiredFrontendVantages` entry. Verify `vantageId`, `profileRevision`, `credentialRevision`,
`observedAt`, `expiresAt`, relay address, and success state in each response. Never print the internal
token into shell history, logs, or troubleshooting documents.

### 4. Neko Session and Frontend Recovery

```bash
kubectl logs -n "${RELEASE_NAMESPACE}" \
  --selector="aileron.io/workspace-id=${WORKSPACE_ID},aileron.io/component=workspace-browser" \
  -c browser \
  --tail=200
```

In Browser DevTools, verify in order that `/browser/access` succeeds and returns access-scoped
`iceServers`, the Neko WebSocket upgrades, a relay ICE candidate/selected pair exists, WebRTC reaches
`connected`, and the data channel opens. Treat a timeout as a single Neko generation failure only after
the first three layers pass. `net::ERR_NETWORK_CHANGED` triggers bounded recovery, but frontend reconnect
must not hide expired evidence or an unreachable TURN path. Increment `turn.credentialRevision` whenever
the TURN Secret rotates.

## PostgreSQL or Redis Performance

```bash
kubectl get pvc,pod -n workspace-system -o wide
kubectl describe pvc -n workspace-system <pvc-name>
kubectl top pod -n workspace-system
```

Confirm that PostgreSQL, Redis, and Manager state each use a local RWO Retain StorageClass and that the Pod runs on the node that owns its volume. Recovering a failed node with local volumes depends on platform backup and restore; it does not have the cross-node portability of shared storage.

## Docker Mode

```bash
docker compose ps
docker compose logs --tail=200 workspace-manager
docker logs --tail=200 workspace-runtime-<workspace-id>
```

Check Docker Compose Browser TURN readiness in this order:

```bash
docker compose ps turn-readiness-preflight coturn \
  connectivity-evidence-gateway connectivity-external-agent workspace-manager
docker compose logs --tail=200 turn-readiness-preflight
docker compose logs --tail=200 coturn connectivity-evidence-gateway connectivity-external-agent
docker compose logs --tail=200 workspace-manager
docker logs --tail=200 workspace-browser-connectivity-probe-<workspace-id>
```

`turn-readiness-preflight` must be `exited (0)`. Otherwise, first verify
`${HOST_TURN_CONFIG_DIR}/turn-reachability-profile.json`, the complete Secret bundle in
`${HOST_TURN_SECRETS_DIR}`, `WORKSPACE_OPERATOR_IMAGE`, `COTURN_IMAGE`, and the profile relay port
range. Do not copy a Secret or token into logs; share only file names, permissions, and redacted
error codes.

Next, verify that the host agent can reach the local Gateway's
`${TURN_CONNECTIVITY_GATEWAY_EXTERNAL_PORT:-18083}` over the host network, that the Gateway reads
the same TURN REST Secret as Coturn, and that the Browser probe uses the same
`TURN_CREDENTIAL_REVISION`. If only Browser access fails, inspect the Workspace's
`browser_connectivity_state`, `browser_connectivity_reason`, `browser_connectivity_backend_*`, and
`browser_connectivity_frontend_*` typed fields. Do not replace evidence diagnosis by rebuilding the
Browser.

Docker admission uses the same projection contract:

| State | Browser access behavior |
| --- | --- |
| `ready` with an `allowed` admission projection | Issue Browser access and a short-lived TURN credential |
| `degraded` with an `allowed` admission projection and unexpired `expiresAt` | Continue to issue access; investigate the frontend failure across the host agent, Gateway, and TURN path |
| `pending` / `not_ready`, or expired `expiresAt` | `409 BROWSER_CONNECTIVITY_NOT_READY` |
| `unavailable` | `503 BROWSER_CONNECTIVITY_UNAVAILABLE` |

Runtime tests must use the test service in `workspace-runtime/docker-compose.test.yml`. Docker
volumes and Kubernetes PVCs have different responsibilities, but both modes use the same bootstrap
order, TURN readiness preflight, and one-time defaults contract.
