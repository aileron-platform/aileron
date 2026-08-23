---
title: Kubernetes Images and Private Registries
description: Kubernetes targets, immutable digests, Registry CA, and image-pull contracts
---

# Kubernetes Images and Private Registries

## Image Contract

- Image platforms must match the target node architecture.
- Runtime, Browser, Canvas, and Manager must use their Kubernetes-specific targets.
- Kubernetes targets run as numeric non-root users and accept any non-root UID injected by the platform.
- The Runtime Kubernetes target does not start SSH, mount the Docker socket, or install dependencies at startup.
- Production values use `repository@sha256:<digest>`, not floating tags.
- The image revision label must match the commit of a clean Git checkout.

## Registry Authentication Contract

`global.imagePullSecrets` is an optional input, not a mandatory production
security control:

- The Helm release namespace must equal
  `kubernetes.workspaceRuntimeNamespace`; the Chart rejects mismatches during
  rendering.
- A Secret-based external private Registry requires one
  `kubernetes.io/dockerconfigjson` Secret in this shared namespace. Secrets are
  namespaced resources, and the Chart does not copy Registry credentials across
  namespaces.
- Chart-managed Pods use the configured list directly.
- Workspace Operator centralizes the same list on each Workspace ServiceAccount.
  Runtime, Browser, and Canvas Deployments reference that ServiceAccount rather
  than duplicating the list in every Pod template.
- EKS/ECR, GKE/Artifact Registry, and AKS/ACR may use node or kubelet identity
  instead. In that mode, keep `global.imagePullSecrets: []` and do not create a
  Secret containing a short-lived Registry token.
- Conformance verifies the ServiceAccount and actual Pod when a Secret is
  configured. Without one, success is determined by whether the workload can
  pull the immutable digest.

Do not hardcode Harbor, ECR, Artifact Registry, or ACR names in Operator code,
and do not maintain the pull-secret list in both Workspace Deployment templates
and ServiceAccounts.

Official references:
[Kubernetes ServiceAccount admission](https://kubernetes.io/docs/reference/access-authn-authz/service-accounts-admin/),
[EKS with ECR](https://docs.aws.amazon.com/AmazonECR/latest/userguide/ECR_on_EKS.html),
[GKE with Artifact Registry](https://docs.cloud.google.com/artifact-registry/docs/integrate-gke),
and [AKS with ACR](https://learn.microsoft.com/en-us/azure/aks/cluster-container-registry-integration).

## Build and Push

```bash
test -z "$(git status --porcelain)"

printf '%s' "${HARBOR_PASSWORD}" |
  docker login "${HARBOR_REGISTRY}" \
    --username "${HARBOR_USERNAME}" \
    --password-stdin

RELEASE_TAG="${RELEASE_TAG}" \
IMAGE_NAMESPACE="${HARBOR_REGISTRY}/${HARBOR_PROJECT}" \
  docker buildx bake --push release
```

The build host or CI must target the node architecture, select Kubernetes image targets, and resolve the pushed immutable digests from the Registry into deployment values. Do not change only the tag when moving an image between architectures.

## Verify the Manifest

```bash
docker buildx imagetools inspect \
  "${HARBOR_REGISTRY}/${HARBOR_PROJECT}/workspace-chrome@sha256:<digest>"
```

A valid result contains `linux/amd64`, has a digest visible in the Registry, and
matches the deployment values exactly.

## Registry CA and imagePullSecret

- The build host's Docker daemon must trust the Registry CA.
- The container runtime on every Kubernetes node must trust the same CA.
- With Secret-based external Registry authentication, the shared Runtime
  namespace must contain the configured imagePullSecret.
- With built-in TURN and a private Coturn image, `coturn.namespace` must also contain a Secret with the name selected by `global.imagePullSecrets`. Secrets do not cross namespaces, and the Chart does not copy them.
- CA trust is a node responsibility; imagePullSecret handles Registry authentication within the namespace.
- Do not use an insecure registry or skip TLS verification.

For RKE2, prepare namespaces and Secrets only through [Kubernetes Installation — `prepare-cluster`](./kubernetes.md#prepare-cluster). After changing CA or Registry settings, pull the digest on every node, then rerun `validate`, `prepare-cluster`, and `apply` in order. Do not create Secrets or run a Helm upgrade directly.

Deployment verification should pull every digest from the Registry again and verify the target architecture, a numeric non-root user, and the Git revision label. Completing the build and push does not permit skipping verification.
