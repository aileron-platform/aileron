---
title: Kubernetes Storage Design
description: RWX, RWO, Delete, Retain, and POSIX contracts for Aileron data
---

# Kubernetes Storage Design

## Volume Matrix

| Data | Mounted by | Mount path | Mode | Reclaim |
| --- | --- | --- | --- | --- |
| Workspace working tree | Runtime, Browser, Canvas | `/workspace` | RWX | Delete when the Workspace is deleted |
| Runtime HOME | Runtime only | `/home/developer` | RWO by default; optional RWX | Delete when the Workspace is deleted |
| Knowledge Base | Manager RW; Runtime attachment RO | `/host/knowledge-bases`, `/knowledge/<alias>` | RWX | Retain |
| Manager state | Manager, worker, beat | `/state` | RWO | Retain |
| PostgreSQL | PostgreSQL | Image data path | RWO | Retain |
| Redis | Redis | Image data path | RWO | Retain |

Browser and Canvas must not mount Runtime HOME. Operator creates `workspace-runtime-home-pvc-<workspace-id>` for each Workspace and mounts it directly at `/home/developer`. It preserves CLI logins and settings, XDG data/state, Maven state, the bootstrap journal, and one-time agent-default markers. The working tree stores user repositories and files.

The three Target Clients — Codex, Claude, and OpenCode — each own an independent
Client User Scope path under Runtime HOME: `${CODEX_HOME:-$HOME/.codex}/skills`,
`${CLAUDE_CONFIG_DIR:-$HOME/.claude}/skills`, and `$HOME/.config/opencode/skills`.
All three are directories under the same Runtime HOME PVC, mounted and reclaimed
together with it — they are not separate Volumes, and none of them is an
isolated personal space per human user; all users and sessions of that
Workspace share them.

`/home/developer/.codex/tmp` is the only intentionally overlaid temporary
subpath and uses a 16 MiB memory-backed `emptyDir`. Codex creates `tmp/arg0` and
sets it to mode `0700` for the current Runtime UID. Do not mount the volume root
directly at `tmp/arg0`, because a non-root Runtime could not adjust its
ownership. This path contains only process-lifetime helper aliases, not
persistent login, settings, or session state.

Runtime HOME has one Runtime writer, and the Runtime Deployment uses Recreate
plus Pod UID fencing. `ReadWriteOnce` is therefore the default, least-privilege
mode. Platforms that require a shared filesystem may set
`kubernetes.runtimeHome.accessMode` to `ReadWriteMany`; the Chart accepts only
one of these two values.

## Cross-Platform Mapping Principles

| Platform | Workspace/Knowledge Base (RWX) | Runtime HOME/platform state (RWO by default) |
| --- | --- | --- |
| EKS | EFS CSI | EBS CSI |
| GKE | Filestore multishare CSI | Persistent Disk CSI |
| AKS | Custom Azure Files NFS CSI StorageClass | Azure Disk CSI |
| OCP | CephFS | Ceph RBD |
| Upstream Kubernetes | NFS CSI, CephFS, or another POSIX RWX CSI | Block CSI; node-local CSI is for test environments only |

These backends are capability mappings, not hardcoded names. Each environment
injects its own StorageClasses. SMB, a fixed GID, NFS root squash, and node-local
volumes must not be treated as universal product contracts.

`helm/aileron/tests/values/platform-*.yaml` files verify only that Helm renders
each platform contract. They are not deployable provider profiles or evidence
that a platform is certified. The GKE fixture uses
`enterprise-multishare-rwx`; the AKS fixture's
`azurefile-nfs-premiumv2-custom` represents an administrator-created Azure
Files StorageClass with `protocol: nfs`, not the built-in SMB class. The
upstream Kubernetes fixture's `csi-rwo` is also a capability placeholder and
must be replaced with the cluster's real RWO CSI class.

See the provider documentation for
[GKE Filestore multishare](https://cloud.google.com/kubernetes-engine/docs/concepts/multishares)
and [AKS Azure Files NFS](https://learn.microsoft.com/azure/aks/create-volume-azure-files#use-nfs-protocol-with-azure-files).

A successful fixture render proves only that values reach the intended PVCs
and workloads. Before declaring EKS, GKE, AKS, OCP, RKE2, or upstream Kubernetes
usable, run full conformance against the real CSI, CNI, admission, and security
policies in the target cluster.

## NFS CSI and POSIX Contract

- Use NFS CSI StorageClasses; the shared NFS subdirectory provisioner does not need to be changed.
- Keep the export configured with `root_squash`.
- The group of the NFS base root must equal `kubernetes.platformStorageGid`.
- The recommended base-root mode is `2770`, preserving setgid and disallowing writes by others.
- Applications write as non-root UIDs with a shared fsGroup and do not modify the volume root.
- Helm declares the fsGroup, StorageClass, access mode, and reclaim intent.
- CSI and the StorageClass create and reclaim volumes or subdirectories.
- The NFS server or platform administrator owns the base-root GID, mode, setgid bit, and export policy.

## Helm Storage Verification

When `kubernetes.storageVerification.enabled=true`, the Chart performs install-time checks with disposable Delete StorageClasses. This Job only verifies storage; it neither creates a platform root nor repairs permissions. On failure, correct the StorageClass, NFS base root, or `platformStorageGid`; do not add root privileges to the application workload.

Workspace RWX and Manager-state RWO verification sizes are controlled by
`kubernetes.storageVerification.workspaceSize` and
`kubernetes.storageVerification.managerStateSize`, each defaulting to `1Gi`.
Both accept positive Kubernetes quantities such as `1Gi` or `100Gi`. Cloud
backends can have different minimum capacities, so override them independently.
For example, the AKS render fixture uses `100Gi` for the RWX probe and `1Gi` for
the RWO probe; deployment values must still match the selected Azure Files tier.

Both `*StorageClassName` values in a production provider profile must point to
verification-only classes with `reclaimPolicy: Delete`, distinct from the
production Workspace and Manager-state classes. Fixture names ending in
`-delete` communicate this render contract only; the platform administrator
must create the StorageClasses and verify their real reclaim policies before
installation.

## Workspace PVC expansion

Workspace Project Data and Runtime HOME use separate dedicated PVCs. To allow Platform Admin expansion, the matching StorageClass must set `allowVolumeExpansion: true`. The system only increases requests and remains `applying` until PVC status capacity reaches the requested bytes. The Docker profile does not provide per-workspace hard quotas.
