---
title: Kubernetes Networking and TURN
description: Network contracts for Service DNS, Ingress, TLS, Cilium, and Browser WebRTC
---

# Kubernetes Networking and TURN

## Internal and Public Routing

Service-to-service traffic uses Kubernetes Service DNS. All Aileron browser traffic uses the single host from `platformPublicOrigin`. The external OIDC Provider keeps its own canonical issuer host, and only Manager Pods access Discovery, JWKS, and the token endpoint.

Frontend Ingress accepts `/`, `/api/v1/...`, and `/workspaces/{uuid}/runtime|browser|canvas/...`.
Frontend's gateway maps only a canonical Workspace UUID and fixed target to namespace-qualified Service DNS; it never accepts a request-supplied upstream. It preserves HTTP streaming, WebSocket Upgrade, subprotocol, Authorization, Cookie, and `X-Forwarded-*` headers.

## Public URL Example

The following example uses `example.com`:

```text
https://aileron.apps.example.com/
```

Corresponding settings:

```yaml
platformPublicOrigin: https://aileron.apps.example.com

ingress:
  enabled: true
  className: nginx
  useDefaultClass: false
  tlsMode: kubernetesSecret
  tlsSecretName: aileron-platform-tls
  annotations:
    nginx.ingress.kubernetes.io/proxy-read-timeout: "3600"
    nginx.ingress.kubernetes.io/proxy-send-timeout: "3600"
    nginx.ingress.kubernetes.io/proxy-http-version: "1.1"
```

The certificate needs to cover only `aileron.apps.example.com`. These annotations are an NGINX example, not product defaults. Other environments may select a controller through `spec.ingressClassName`, a provider annotation, or an explicitly chosen cluster-default IngressClass.

## Cilium

When `cilium.enabled=true`, Operator creates policy from each Workspace firewall desired state. Required infrastructure egress such as DNS, Manager/OIDC-provider control traffic, and TURN is separate from the domain list managed in the UI.

## Explicit TURN Reachability Profile

The platform does not infer TURN from a cloud name, Ingress controller, or homelab label. `turn.profile`
is the only machine-readable contract. It explicitly lists backend/frontend URLs, policy backend, control
and relay destinations, relay UDP range, credential issuer, and evidence freshness:

```yaml
turn:
  enabled: true
  iceServersSecretName: external-turn-ice
  backendIceServersKey: backend-ice-servers-json
  frontendIceServersKey: frontend-ice-servers-json
  credentialRevision: 7
  profile:
    policyBackend: cilium
    backend:
      urls: ["turn:turn.apps.example.com:3478"]
      controlDestination:
        kind: ciliumEntities
        values: [host, remote-node]
      relayDestination:
        kind: ciliumEntities
        values: [host, remote-node]
      relayPortRange: {min: 49160, max: 49259}
    frontend:
      urls: ["turn:turn.apps.example.com:3478"]
    credentialIssuer:
      kind: turnRest
      secretRef: external-turn-ice
      ttlSeconds: 300
    evidence:
      intervalSeconds: 30
      ttlSeconds: 90
      requiredFrontendVantages: [internet]
```

Production external vantages use `turnRest`. Its Secret contains `turn-rest-shared-secret`, and Gateway
generates an expiring timestamp username and HMAC credential according to Coturn TURN REST. `staticSecret`
is restricted to an explicitly classified development or single-site test profile and is not a credential
for a production-required vantage.

`turnRest` also covers the real Browser data path. The Browser Pod sidecar creates a fresh short-lived
credential for every backend probe. The Manager Browser access response returns fresh frontend
`iceServers`, and the frontend uses them for that `RTCPeerConnection` instead of a fixed TURN credential
loaded when Neko started. Bundled Coturn uses `staticSecret`; external TURN uses `turnRest`.

`policyBackend` supports `cilium`, `kubernetes`, and explicit `unenforced`. Destinations must use a
compatible `ciliumEntities`, `cidrs`, `namespacePods`, `fqdns`, or `unenforced` form. Relay destinations
cannot use FQDNs because actual relay addresses must match explicit CIDRs, Pod identity, or a Cilium
entity. Control ports and the relay UDP range produce separate egress rules and are never collapsed into
a permissive world rule.

## Built-in Coturn

With `coturn.enabled=true`, the Chart creates an isolated namespace, a `hostNetwork` Coturn DaemonSet,
a public TURN Service, a Browser ICE Secret, and a probe identity separate from the Browser credential.

```yaml
coturn:
  enabled: true
  namespace: aileron-turn-system
  frontendHost: "turn.{baseDomain}"
  listenerPort: 3478
  realm: aileron
```

`turn.{baseDomain}` may resolve only to nodes running Coturn. Each node and upstream device must allow
the profile listener over TCP/UDP and its relay UDP range. Create the credential Secret selected by
`coturn.auth.existingSecretName` before deployment. Increment `turn.credentialRevision` whenever Browser
or probe credentials rotate.

## External TURN

An external service uses the same TURN Reachability Profile to describe its real endpoint and policy
destination. In the Runtime namespace, create the Secret selected by `turn.existingSecretName` with the
backend/frontend ICE JSON keys and TURN REST shared-secret key referenced by the profile. The release
namespace must also contain the Secret selected by
`connectivityEvidenceGateway.auth.existingSecretName`. It contains `internal-token`, `agent-tokens-json`,
`probe-ice-servers-json`, and one `agent-<vantage>-token` for each host Agent launched by the Chart.
Tokens for externally managed Agents are securely distributed to those hosts by the Secret manager and
do not need a duplicate Kubernetes Secret key. This Chart requires the release and Runtime namespaces
to be the same. Manage all real values outside version control.

This manifest shows the required keys and JSON shapes. A Secret manager must inject every `<...>` value:

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: external-turn-ice
  namespace: workspace-system
type: Opaque
stringData:
  backend-ice-servers-json: >-
    [{"urls":["turn:turn.example.com:3478?transport=udp"]}]
  frontend-ice-servers-json: >-
    [{"urls":["turns:turn.example.com:5349?transport=tcp"]}]
  turn-rest-shared-secret: "<TURN REST shared secret>"
---
apiVersion: v1
kind: Secret
metadata:
  name: aileron-aileron-connectivity-evidence
  namespace: workspace-system
type: Opaque
stringData:
  internal-token: "<operator-to-gateway token>"
  agent-tokens-json: '{"internet":"<internet-agent token>"}'
  probe-ice-servers-json: >-
    [{"urls":["turns:turn.example.com:5349?transport=tcp"]}]
  agent-internet-token: "<internet-agent token>"
```

`agent-tokens-json` is a JSON object keyed by vantage ID. Every `requiredFrontendVantages` entry must have
exactly one matching token. `agent-internet-token` is mounted as a read-only file when the Chart host
Agent uses `vantageId: internet`. The three ICE JSON keys are `RTCIceServer[]`; a `turnRest` profile stores URLs
only because username and credential are generated when access is issued.

The backend endpoint must complete authenticated allocation and a relay round trip from the Browser Pod.
The frontend endpoint must complete the same operation from every required external vantage using its
public DNS, TLS, and transport. DNS lookup, TCP connect, STUN binding, Service readiness, or occasional
direct ICE success is not sufficient evidence.

## Connectivity Evidence Gateway and External Agent

The Chart creates only a namespace-local ClusterIP Gateway Service. It does not create a Gateway Ingress
and has no `connectivityEvidenceGateway.publicHost` Helm value. If an external Agent is required, the
deployment must provide an HTTPS reverse proxy or Ingress outside the Chart and route its chosen host to
that Service. The Agent needs no inbound port, but it needs outbound HTTPS to that Gateway endpoint plus
outbound TCP/UDP to the TURN listener and the actual relay address/range. It uses installation ID, vantage ID,
and a bearer enrollment token to obtain a short-lived challenge and TURN REST probe ICE credential, performs the relay, then submits the nonce, profile revision,
credential revision, observation time, TTL, and relay address. Gateway rejects expired, replayed,
identity-mismatched, or revision-mismatched submissions. Evidence never stores credentials, tokens, or nonces.

```yaml
connectivityEvidenceGateway:
  enabled: true
  installationId: "{releaseNamespace}.{releaseName}"
  hostAgent:
    enabled: false
    vantageId: host
    tls:
      caSecretName: ""
      caSecretKey: ca.crt
```

The Agent uses the Workspace Operator image and starts in `connectivity-external-agent` mode. The Secret
manager writes the token to a file readable only by the Agent identity. The command line and environment
contain only that file path, never the token value:

```bash
docker run --read-only --cap-drop=ALL --restart=unless-stopped \
  --mount type=bind,src=/run/secrets/aileron-connectivity-agent-token,dst=/var/run/secrets/aileron-connectivity-agent-token,readonly \
  -e CONNECTIVITY_EVIDENCE_GATEWAY_URL=https://connectivity.apps.example.com \
  -e AILERON_INSTALLATION_ID=workspace-system.aileron \
  -e CONNECTIVITY_AGENT_VANTAGE_ID=internet \
  -e CONNECTIVITY_AGENT_INTERVAL_SECONDS=30 \
  -e CONNECTIVITY_AGENT_TOKEN_FILE=/var/run/secrets/aileron-connectivity-agent-token \
  ailerondocker/workspace-operator@sha256:<digest> \
  --mode=connectivity-external-agent
```

When the Gateway uses a public CA, the Agent uses the image system trust store. Environments with a
private CA must deliver the CA bundle to the Agent as a read-only Secret or host file. The
Chart-managed `hostAgent` mounts `tls.caSecretName` and `tls.caSecretKey` and sets
`CONNECTIVITY_AGENT_CA_FILE`; an external Docker Agent mounts its own CA file and sets the same
environment variable. The Agent adds the custom CA to the system trust store, still requires TLS
1.2 or newer, and provides no certificate-verification bypass.

The Gateway protocol uses `POST /v1/challenges` and `POST /v1/evidence`. Operator reads
`GET /v1/evidence/{profileRevision}/{vantage}` with the internal token. Agent logs must show periodic
success, and evidence for every required vantage in the Workspace CR must continue to refresh before
`expiresAt`.

Production Agents belong in an actual user network, DMZ, enterprise egress, or platform-managed external
region. Local development or an explicitly classified single-site homelab may enable `hostAgent`, but
Kubernetes node host-network evidence cannot represent the general Internet or every user's last mile.
Each production-required vantage has its own token. Missing evidence never extends an expired evidence TTL.

## Browser Connectivity Readiness and Authorization

Each Browser Pod also runs a probe sidecar without a ServiceAccount token. It tests backend TURN from the
Browser network namespace. Operator pulls sidecar and Gateway evidence, validates profile revision,
credential revision, observation time, and expiry, and then updates Workspace CR
`status.browserConnectivity`. Operator is the single authority for this state. Manager only projects it
and gates new-session admission at `POST /api/v1/workspaces/{workspace_id}/browser/access`.

This state is not Pod liveness and does not terminate an existing healthy session. Normal restart and
stop/start do not rotate Browser credentials. Revocation or explicit rotation rebuilds only Browser and
must not change Runtime or Canvas Pod UIDs. Credentials, agent tokens, and challenge secrets never enter
CRs, ConfigMaps, or logs.

The backend probe TURN REST username is `${expiry}:backend:${workspaceId}`. This identity provides TURN
audit attribution only. Workspace isolation for evidence comes from the dedicated Browser Service endpoint
plus the profile revision, credential revision, observation time, and expiry. Operator does not derive the
evidence Workspace from the username.

## Source Basis

- `helm/aileron/values.schema.json`
- `helm/aileron/templates/connectivity-evidence-gateway.yaml`
- `workspace-operator/internal/controller/turn_profile.go`
- `workspace-operator/internal/controller/turn_probe.go`
- `workspace-operator/internal/controller/connectivity_evidence_gateway.go`
- `workspace-operator/internal/controller/browser_connectivity.go`
