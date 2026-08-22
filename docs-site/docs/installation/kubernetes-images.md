---
title: Kubernetes 映像與私有 Registry
description: Kubernetes targets、不可變 digest、平台 Registry identity 與 image pull 契約
---

# Kubernetes 映像與私有 Registry

## 映像契約

- 映像平台必須符合目標 node architecture，不可假設所有 Kubernetes node 都使用相同架構。
- Runtime、Browser、Canvas 與 Manager 必須使用 Kubernetes 專用 target。
- Kubernetes target 使用 numeric non-root user，並可接受平台注入的任意 non-root UID。
- Runtime Kubernetes target 不啟動 SSH、不掛 Docker socket，也不在啟動時安裝 dependency。
- production values 使用 `repository@sha256:<digest>`，不使用浮動 tag。
- image revision label 必須對應 clean Git checkout 的 commit。

## Registry 認證契約

`global.imagePullSecrets` 是選填輸入，不是 production security 的必要條件：

- Helm release namespace 必須等於 `kubernetes.workspaceRuntimeNamespace`；Chart 會在
  render 階段拒絕不一致的設定。
- 外部私有 Registry 必須在這個共同 namespace 建立一份
  `kubernetes.io/dockerconfigjson` Secret。Secret 是 namespaced resource，Chart
  不會跨 namespace 複製 Registry credential。
- Chart-managed Pod 直接使用該清單。
- Workspace Operator 把相同清單集中設定在每個 Workspace 專用 ServiceAccount；
  Runtime、Browser、Canvas Deployment 只引用該 ServiceAccount。共同 namespace
  必須能解析該 Secret，Kubernetes ServiceAccount admission 才能把清單注入實際 Pod。
- EKS／ECR、GKE／Artifact Registry、AKS／ACR 可改由 node／kubelet identity 授權；
  此時保持 `global.imagePullSecrets: []`，不要建立短期 Registry token Secret。
- Conformance 有提供 Secret 時，會驗證 ServiceAccount 與實際 Pod；未提供時則以 workload
  能否成功 pull immutable digest 為準。

不要在 Operator 寫入 Harbor、ECR、Artifact Registry 或 ACR 名稱，也不要同時在
Workspace Deployment template 與 ServiceAccount 維護兩份 pull secret 清單。

官方參考：
[Kubernetes ServiceAccount admission](https://kubernetes.io/docs/reference/access-authn-authz/service-accounts-admin/)、
[EKS 使用 ECR](https://docs.aws.amazon.com/AmazonECR/latest/userguide/ECR_on_EKS.html)、
[GKE 使用 Artifact Registry](https://docs.cloud.google.com/artifact-registry/docs/integrate-gke)、
[AKS 整合 ACR](https://learn.microsoft.com/en-us/azure/aks/cluster-container-registry-integration)。

## 建置與推送

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

建置主機或 CI 必須使用與目標 node 相容的平台、選用 Kubernetes target，並從 registry
解析推送後的 immutable digest 寫入 deployment values。不要為不同架構只改 tag。

## 驗證 manifest

```bash
docker buildx imagetools inspect \
  "${HARBOR_REGISTRY}/${HARBOR_PROJECT}/workspace-chrome@sha256:<digest>"
```

成功條件是 manifest 包含 `linux/amd64`，digest 可由 Registry 查得，且與 deployment values
完全一致。

## Registry CA 與 imagePullSecret

- 建置端 Docker daemon 必須信任 Registry CA。
- 每個 Kubernetes node 的 container runtime 必須信任同一 CA。
- 使用 Secret-based 外部 Registry 認證時，共同 Runtime namespace 必須有設定的
  imagePullSecret。
- 使用 built-in TURN 與 private Coturn image 時，`coturn.namespace` 也必須有與
  `global.imagePullSecrets` 同名的 Secret；Secret 不會跨 namespace 共用或由 Chart 複製。
- CA trust 是節點責任；imagePullSecret 只負責 namespace 內的 Secret-based Registry 認證。
- 不可用 insecure registry 或跳過 TLS 驗證。

RKE2 HomeLab 的 namespace 與 Secret 準備只能透過 [Kubernetes 安裝 —
`prepare-cluster`](./kubernetes.md#prepare-cluster) 執行。更新 CA 或 Registry 設定後，先在
每個 node 實際 pull digest，再依序重跑 `validate`、`prepare-cluster` 與 `apply`；不可直接
建立 Secret 或執行 Helm upgrade。

部署驗證應再次從 Registry pull 每個 digest，核對目標架構、numeric non-root user 與
Git revision label；只完成 build/push 不代表可以略過驗證。
