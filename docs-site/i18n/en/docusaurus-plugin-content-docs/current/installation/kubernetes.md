---
title: RKE2 HomeLab Installation
description: Deploy and upgrade RKE2 HomeLab through its sole three-phase installer
---

# RKE2 HomeLab Installation

This page documents only the verified RKE2 HomeLab production contract. The sole top-level entry point is
`scripts/deploy/rke2/install.py`; manual Namespace or Secret creation and direct Helm execution must not replace
the installer. Other Kubernetes providers do not yet have the same complete installation and recovery proof, so
this page does not present a speculative generic path.

Review these topics before deployment:

- [Storage Design](./kubernetes-storage.md)
- [Image Builds and Private Registries](./kubernetes-images.md)
- [Networking, Ingress, TLS, and TURN](./kubernetes-networking.md)
- [Workspace Firewall](./kubernetes-firewall.md)
- [Helm Values Reference](/reference/helm-values.md)

## Prerequisites

- Use a clean checkout and a full 40-character Git SHA. Deployment and images target `linux/amd64`.
- Build the deployment Python runtime from the hashes in tracked
  `scripts/deploy/rke2/requirements.txt`. CI installs that same production lock in a pinned Python 3.9,
  linux/amd64 stage, runs `pip check`, and imports `jsonschema` and `yaml`.
- Use stable Helm `>=3.13.0,<4.0.0`. Preflight verifies server-side dry-run, atomic upgrade, history limit,
  and rollback cleanup capabilities instead of inferring them from a major version.
- The fixed private root is `/root/aileron-private` with mode `0700`. The private root, every installation-owned
  directory beneath it, and every mode-`0600` kubeconfig, inventory, TLS, CA, dockerconfig, or other private input
  must be owned by the installer's effective UID. Symbolic links and hard links are rejected.
- Kubeconfig `current-context` must equal the requested context and contain only inline CA plus either an inline
  token or inline client certificate/key. External or dynamic references such as `certificate-authority`,
  `client-certificate`, `client-key`, `tokenFile`, `exec`, and `auth-provider` are rejected.
- Every Aileron image is published as an immutable digest for the target commit, with a trusted published image
  inventory.
- StorageClass, Cilium, Ingress, DNS, Apps TLS, OIDC TLS, TURN, and Registry trust satisfy the HomeLab profile.
  Registry CA, Apps ingress CA, and OIDC CA are independent inputs and never fall back to one another.

The complete argument and private-input paths are defined by `scripts/deploy/rke2/INSTALL.md` in the repository.

## Identity Modes

- `bundledKeycloak`: the installer manages bundled Keycloak plus `workspace-system`,
  `aileron-turn-system`, `aileron-backend-attestor-system`, and `aileron-identity-system`.
- `externalOidc`: the installer manages `workspace-system`, `aileron-turn-system`, and the retained
  `aileron-backend-attestor-system`; `aileron-identity-system` must be absent, and the external issuer must expose
  standard OIDC Discovery and JWKS.

Bundled mode creates separate Aileron platform-administrator, Keycloak Console administrator, and
break-glass accounts. The HomeLab platform administrator defaults to `admin` / `admin123` for isolated
testing only; general Kubernetes installations generate a strong random password. See
[OIDC and Identity Plane Installation](./oidc.md#bundled-accounts-and-passwords) for roles, password
policy, and private-artifact locations.

Future LDAP support remains at the identity-provider federation boundary: LDAP owns account lifecycle, Keycloak
or an external IdP exposes OIDC application login, and this project owns only application authorization while
retaining a local emergency administrator. The installer does not bind directly to LDAP or pre-import an entire
directory, so running Docker or HomeLab without LDAP does not close the future support path.

## Retained Backend Attestor Prerequisite

A full rebuild retains both `aileron-acceptance-system` and `aileron-backend-attestor-system`; neither is a reset
target. The backend-attestor Namespace is owned by `aileron-installer`, uses the exact PSA profile
`enforce=privileged`, `audit=restricted`, and `warn=restricted`, and has one fixed `harbor-rke-creds` image pull
Secret. The Harbor dockerconfig must contain only the exact registry entry selected by the command. Credentials
must never enter logs or evidence.

Before the first signed pre-reset snapshot, create a mode-`0600` canonical JSON execution profile outside the
repository. The profile uses schema `aileron-backend-execution-profile/v1`: NFS targets are constrained by a
pinned IPv4 address and approved mount roots, while local-path targets are constrained by a live node hostname,
node UID, and approved mount roots. At least one target type is required. The tracked
`scripts/deploy/rke2/backend-execution-profile.example.json` may be used as a starting point, but every
placeholder and `_comment` must be removed and the document canonicalized against the schema before use.

The dedicated preparer validates and performs Kubernetes server-side dry-runs by default:

```bash
python3 scripts/deploy/rke2/prepare_backend_attestor.py \
  --kubeconfig /root/aileron-private/kubeconfig \
  --harbor-dockerconfig /root/aileron-private/harbor/dockerconfig.json \
  --execution-profile /root/aileron-private/inputs/backend-execution-profile.json \
  --context rke \
  --registry harbor.rke.soez.tw
```

Exit `78` means the prerequisite is not Ready. Only then rerun the exact arguments with `--apply`, followed by
the validation command above. Apply uses UID and resourceVersion preconditions to create or converge the
Namespace and pull Secret, then publishes the profile's exact bytes write-once at
`/root/aileron-private/backend-attestor/execution-profile.json`. The Namespace is a durable prerequisite and is
not deleted if a later Secret step fails. A different installed profile or any Namespace/Secret owner, UID, PSA,
type, data-key, or registry-credential drift fails closed.

## Sole Three-Phase Workflow

All three commands use the exact same commit, context, Identity selection, and complete private inputs, including
the external `--execution-profile` described above:

```bash
python3 scripts/deploy/rke2/install.py validate <complete-installation-arguments>
python3 scripts/deploy/rke2/install.py prepare-cluster <complete-installation-arguments> --confirm-create-namespaces
python3 scripts/deploy/rke2/install.py apply <complete-installation-arguments>
```

### `validate`

`validate` does not persist Kubernetes changes or phase artifacts in the stable private tree. When a target
Namespace is absent, the installer performs a server-side dry-run of the fixed manifest containing the installer
owner and complete PSA labels, then exits `78` to require `prepare-cluster`. Namespace-scoped Secret or Helm
validation must not be reported as successful without a real namespace scope.

### `prepare-cluster`

The only durable mutation in this phase is a Namespace. Every ownership, UID, resourceVersion, and server-side
dry-run check completes before the first mutation. An existing Namespace may only have its complete PSA profile
converged by the installer. The exact profile removes every undeclared `pod-security.kubernetes.io/*` label while
preserving non-PSA labels. After all server-side dry-runs and before the first mutation, the installer rereads the
complete target inventory; a newly appeared previously absent target or forbidden external-OIDC Identity Namespace
stops with zero mutations. After mutation, a fresh query must prove that:

- The Namespace UID was not replaced.
- Owner and exact PSA labels match.
- `status.phase` is exactly `Active`.
- `metadata.deletionTimestamp` is absent.

Any allowlisted target, or a stale Identity Namespace in external OIDC mode, fails closed while Terminating. This
phase must not create a Secret, Helm release, or application data.

### `apply`

`apply` first completes the same validation. Identity and Core Secret dry-runs, Helm server-side dry-runs, and the
full Core preflight must all pass before the Secret transaction begins. Immediately before the first Secret
mutation, the installer revalidates every Namespace UID, owner, PSA profile, `Active` phase, and deletion
timestamp. Replacement, drift, or termination stops with zero Secret or release mutations.

Namespaces are durable prerequisites outside the transaction. A later deployment or recovery failure does not
automatically delete safely prepared Namespaces.

## Global Lock and Private-Input Snapshots

The installer acquires a non-blocking flock directly on the effective-UID-owned, mode-`0700` private-root directory descriptor and
matches its device and inode to the path. It creates no `installation.lock` or other stable lock artifact, so a
first `validate` or `prepare-cluster` contention failure does not pollute the stable private tree.

Each external file and its private parent directories must be owned by that same effective UID. The file is read
from one `O_NOFOLLOW` descriptor using `fstat → read → fstat`, then published as a
mode-`0600` snapshot with `O_EXCL` and file plus directory fsync. The source path is never read again after the
snapshot; replacing it cannot affect the current phase. `validate` and `prepare-cluster` use an automatically
removed private phase directory. `apply` uses commit-scoped write-once snapshots and rejects different content on
retry.

Kubeconfig is first saved as a raw snapshot. The installer then runs
`kubectl config view --raw --flatten --minify` against that raw snapshot and the original context to create a
second mode-`0600` snapshot. API server and CA must match before and after flattening. Cluster UID and every later
Kubernetes or Helm command are pinned to the flattened snapshot and never reread the original kubeconfig.

## Secret and Release Transaction

The installer expands an exact allowlist from the Identity mode and canonical Secret registry. Before mutation it
records each Secret's `existing` or `absent` pre-state. A complete existing Secret is stored only in a mode-`0600`
private snapshot, while the inventory contains no Secret value. Recovery touches only allowlisted objects, and
every replace or delete fails closed through UID and resourceVersion preconditions.

Core preflight verifies images, TLS, Namespaces, network security, Helm capabilities, DaemonSet and
Deployment/StatefulSet/Job capacity, plus Runtime, Browser, and Canvas capacity for a new Workspace. Only then may
Identity be installed or upgraded, OIDC readiness verified, and the live Core preflight rerun before Core
deployment. An untrusted Core rollback, Secret restore, or Identity recovery can never produce a successful
deployment claim.

## Acceptance

Ready Pods, Bound PVCs, and a `deployed` Helm status are only minimum health signals, not complete deployment
evidence. Complete acceptance trusts only `scripts/deploy/rke2/deployment-acceptance-contract.json` and its
code-owned digest, and it must create a new `oidcWorkspace` through the normal OIDC API and UI flow.

The causal DAG proves the signed 11-image release set, clean reset, Identity and OIDC, Runtime, Terminal, Browser,
Canvas, WebSocket, TURN, Workspace lifecycle, component restart, and soak. The images actually used by live
workloads require separate Pod `imageID` evidence; `imageRelease` does not itself claim live-rollout attestation.
All private inputs, raw reports, bundles, and sidecars remain as mode-`0600` files in code-owned mode-`0700`
directories. Secrets, tokens, passwords, and private keys must never enter Git, reports, or logs.

The current v8 causal order is fixed as: signed image inventory → `cleanReset --reset-phase pre-reset`
snapshot/epoch → non-mutating `suites` and `offlineOidcConformance` (which may run in parallel) → reset → signed
post-reset `cleanReset` report → the three top-level `install.py` phases → `imageRelease` → `identity` in bundled
mode → `oidcWorkspace` → the remaining Workspace reports. Before reading signed backend inputs or performing any
mutation, the reset executor validates both root reports' canonical JSON, HMAC, sources, and observations against
the same commit, run, context, and trust root, then binds their digests and `finishedAt` values into execution
state; drift on resume stops execution. Every active non-root producer derives the immediate predecessors for the
current authentication mode directly from the v8 `causalEdges`, then validates all of them with the same canonical,
HMAC, identity, source, observation, and freshness validator before its own side effects. Workspace predecessors must
also match the exact current Workspace ID and subject. Existing `cleanReset` reruns and final bundle validation reuse
the same validator.

Every producer derives the sole `/root/aileron-private/evidence/<full SHA>/<deployment run ID>/` from the full
commit and deployment run ID. Before any trust or cluster query, it publishes the CLI kubeconfig write-once as
`kubeconfig.raw`, then creates `kubeconfig` with an explicit
`kubectl --kubeconfig <raw snapshot> --context <context> config view --raw --flatten --minify --output=json`.
The raw and flattened selected-identity digests must match, and an interrupted resume accepts only exact bytes for
both files. Source replacement, identity drift, or an existing-snapshot mismatch stops before the first trust
query. Every later reset-inventory collector, backend attestor, Job, restart, browser lifecycle, kubectl, and Helm
call uses only that flattened path, with explicit kubeconfig and context flags.

The bundle builder and final validator expose no `--kubeconfig`; they load only that canonical raw/flattened pair
from the same commit/run directory. The bundle's second validation receives that same flattened path:

```bash
python3 scripts/deploy/rke2/acceptance_bundle.py \
  --expected-commit "$FULL_GIT_SHA" \
  --deployment-run-id "$DEPLOYMENT_RUN_ID" \
  --context rke
python3 scripts/deploy/rke2/acceptance_evidence.py \
  --expected-commit "$FULL_GIT_SHA" \
  --deployment-run-id "$DEPLOYMENT_RUN_ID" \
  --context rke
```

### Tracked OIDC Browser Acceptance

The sole active Workspace-acceptance flow is the tracked
`frontend/e2e/homelab-acceptance.mjs` executed by the fixed
`scripts/deploy/rke2/acceptance_producer.py`. The Producer must prove a clean checkout, HEAD at the full
acceptance commit, and probe bytes equal to that commit's Git object before building a full-SHA-tagged
Playwright image and executing it by image ID. `oidcWorkspace` uses the real OIDC Authorization Code and PKCE
login to create a Workspace. After the Frontend callback, it uses only the opaque Manager session; every
authenticated mutation carries the memory-only CSRF token obtained by that session and the correct `Origin`.

The `terminal`, `http`, `websocket`, and `browser` sections verify the production Gateway, execution grant,
protocol round trip, and Browser UI through that Workspace and OIDC session. The Workspace-scoped `turn`
attestor proves an actual TURN relay. Only after all of those reports succeed may `workspaceLifecycle` use the
same session and CSRF token to perform component restart, stop, the Stopped observation, start, and the
Running/Ready observation. These tracked OIDC Browser probes and the TURN attestor are the sole active lifecycle
acceptance entry point, with causal order fixed by
`scripts/deploy/rke2/deployment-acceptance-contract.json`.

### Bundled Keycloak Browser Input

The current bundled-Keycloak HomeLab has no LDAP and uses `--use-break-glass-login` to build its Browser
acceptance input from the fixed, installation-owned Keycloak bootstrap-administrator and break-glass credential
sources:

```bash
python3 scripts/deploy/rke2/prepare_browser_input.py \
  --expected-commit "$FULL_GIT_SHA" \
  --deployment-run-id "$DEPLOYMENT_RUN_ID" \
  --use-break-glass-login
```

The output is the fixed
`/root/aileron-private/acceptance-inputs/<full SHA>/<deployment run ID>/browser-input.json`, a mode-`0600`
write-once canonical JSON file; the CLI exposes no arbitrary output path. When Keycloak LDAP federation is
enabled, supply one complete pair of private login credential files without `--use-break-glass-login`:

```bash
python3 scripts/deploy/rke2/prepare_browser_input.py \
  --expected-commit "$FULL_GIT_SHA" \
  --deployment-run-id "$DEPLOYMENT_RUN_ID" \
  --login-username-file "$LOGIN_USERNAME_FILE" \
  --login-password-file "$LOGIN_PASSWORD_FILE"
```

Both login files must reside in the owner-only private tree and pass regular-file, owner, mode, symlink, and
hardlink checks. LDAP manages account lifecycle, while Keycloak performs federation and OIDC authentication.
Aileron continues to receive users through the same OIDC, JIT-provisioning, and application-authorization seam,
with its local break-glass administrator retained.

Epochs, reset snapshots, reports, and bundles must be strict UTF-8 JSON with no duplicate object key at any depth,
and their raw bytes must exactly equal sorted compact canonical JSON plus one trailing newline. Reordering fields,
changing whitespace, removing the newline, or using duplicate keys to create a semantically equivalent document
cannot pass the signature or write-once evidence gate. The tracked acceptance contract remains format-bound by its
code-owned digest, while its parser also rejects duplicate keys.

The clean-reset snapshot binds each exact PV name, UID, and backend-locator digest to the execution profile,
retained Namespace and pull-Secret UIDs, and signed image inventory. The reset executor may start per-target
backend cleanup only after authoritative live inventory proves the three resettable Namespaces, Workspaces, PVCs,
and target PVs absent. It journals each target before execution, then publishes the canonical aggregate write-once
at `/root/aileron-private/reset/<commit>/<run-id>/backend-cleanup-results.json`. Once the journal is complete, a
missing or noncanonical aggregate, or a digest mismatch, fails closed; the file is never reconstructed from the
journal.

The post-reset producer accepts only the same commit, run ID, and manually approved snapshot SHA-256. It validates
the signed cleanup aggregate, then re-verifies every backend path with independent attestor Jobs that have
read-only mounts. The producer has no cleanup surface and does not trust the aggregate's self-reported
`allAbsent`. Any target identity, execution resource, image, Job provenance, or live Kubernetes-absence drift
fails closed.

## Upgrade and Recovery

An upgrade repeats `validate → prepare-cluster → apply` with the new full SHA and signed image inventory; do not
run Helm upgrade directly. Installer Secret, Core, and Identity transaction contracts perform recovery; do not
replace them with a manual Helm rollback. Database, CRD, or PVC contract recovery also requires the matching data
snapshot, CRDs, and image digests, followed by the full acceptance suite.
