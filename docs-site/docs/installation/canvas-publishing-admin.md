---
title: Canvas 發佈管理員設定
description: 為 Workspace Skill 準備 GitLab、OCI registry、Argo CD、Kubernetes 與權限
---

# Canvas 發佈管理員設定

管理員只需準備平台資源與權限；不需要在 Aileron Manager 增加 Canvas publishing 全域設定。
每個 Workspace 的 API URL、Project path、token 與 registry 設定由使用者以 Workspace
環境變數提供。

## 必要資源

| 元件 | 管理員責任 |
|---|---|
| GitLab | 建立一個空的 private Project；授予 API token 查詢、推送、設定 masked CI variables 與觸發 API pipeline 的權限 |
| GitLab Runner | 提供受信任 Docker build runner；只讓 `package` environment 取得 OCI push credential |
| OCI registry | 提供 site image 與 Helm chart repository、push robot、Kubernetes pull robot；禁止重用既有 image tag 與 chart version |
| Argo CD | 建立 AppProject、API account 與 OCI repository credential；限制 namespace 與 resource kinds |
| Kubernetes | 預先建立一個 Workspace namespace、image pull Secret、TLS Secret 與 IngressClass |
| DNS/TLS | `*.<base-domain>` 指向 Ingress，TLS Secret 涵蓋站台 hostname |

GitLab Project 不可預先放入使用者來源或自訂 CI；Skill 會在 `bootstrap.py --ensure` 推送
版本化 managed scaffold。請將 `main` 與 `sites/*` 設為 Protected Branch，只允許這個 Workspace
的 Skill token push、觸發 pipeline 與更新受管 CI variables；不要讓一般使用者或未受信任的
Runner 修改 `.gitlab-ci.yml`、`ci/`、`chart/`。Project 不存在時，Skill 只回報
`GITLAB_PROJECT_MISSING`。

## Base image 專案

Kit 的 `assets/kit/manifest.json` 與 `assets/kit/checksums.sha256` 是 Release Set 的版本與校驗
入口；管理員應先在固定 Git tag/commit 取得整個 Skill，再依 checksum 驗證 assets。Kit 的
`assets/runtime-base` 可放在管理員專用的 GitLab Project。該 Project 的 CI masked
variables 使用 `PUBLISHING_OCI_REGISTRY`、`PUBLISHING_OCI_BASE_REPOSITORY`、
`PUBLISHING_OCI_USERNAME`、`PUBLISHING_OCI_PASSWORD` 與固定 digest 的
`PUBLISHING_NODE_IMAGE`，只允許手動或 API pipeline 建置 runtime base 與 Next.js builder。
Pipeline 只推送 commit SHA tag，管理員驗證輸出的 digest 後，再填入 Workspace 的
`AILERON_PUBLISH_RUNTIME_BASE` 與 `AILERON_PUBLISH_NEXTJS_BUILDER`。

## Argo CD AppProject

AppProject 應只允許每個環境的 OCI chart repository、指定 Kubernetes namespace，以及：

- `apps/Deployment`；
- `Service`；
- `networking.k8s.io/Ingress`；
- 不允許 cluster-scoped resource；
- `CreateNamespace=false`。

API account 至少需要查詢、建立、更新與刪除指定 project 下的 Application，以及查詢
AppProject。Argo CD repo-server 必須能以 repository credential 讀取 OCI chart。

## Workspace environment contract

管理員把下列值提供給 Workspace 使用者；敏感值應透過 Workspace 的安全環境變數設定機制
輸入：

```text
AILERON_PUBLISH_BUILD_PROVIDER=gitlab
AILERON_PUBLISH_DEPLOY_PROVIDER=argocd
AILERON_PUBLISH_WORKSPACE_ID=<workspace-id>
AILERON_PUBLISH_GITLAB_API=https://gitlab.example/api/v4
AILERON_PUBLISH_GITLAB_PROJECT_PATH=<group>/<workspace-project>
AILERON_PUBLISH_GITLAB_TOKEN=<gitlab-api-token>
AILERON_PUBLISH_ARGOCD_URL=https://argocd.example
AILERON_PUBLISH_ARGOCD_TOKEN=<argocd-api-token>
AILERON_PUBLISH_ARGOCD_PROJECT=<argocd-appproject>
AILERON_PUBLISH_OCI_REGISTRY=<registry-host>
AILERON_PUBLISH_OCI_SITE_REPOSITORY=<site-repository-prefix>
AILERON_PUBLISH_OCI_CHART_REPOSITORY=<chart-repository-prefix>
AILERON_PUBLISH_OCI_PUSH_USERNAME=<package-robot>
AILERON_PUBLISH_OCI_PUSH_PASSWORD=<package-secret>
AILERON_PUBLISH_BASE_DOMAIN=<canvas-domain>
AILERON_PUBLISH_DESTINATION_NAMESPACE=<precreated-namespace>
AILERON_PUBLISH_RUNTIME_BASE=<registry>/<path>@sha256:<64-hex>
AILERON_PUBLISH_NEXTJS_BUILDER=<registry>/<path>@sha256:<64-hex>
AILERON_PUBLISH_IMAGE_PULL_SECRET_NAME=<pull-secret>
AILERON_PUBLISH_TLS_SECRET_NAME=<tls-secret>
AILERON_PUBLISH_INGRESS_CLASS_NAME=<ingress-class>
AILERON_PUBLISH_RELEASE_VERSION=<skill-kit-release>
```

私有 CA 可用 `AILERON_PUBLISH_CA_PEM` 傳入 PEM 內容或 Runtime 可讀的 CA file path。不要
把 CA、token 或 password 寫入 repository。

## 初始化與升級

在已設定 Workspace environment 的 Runtime container 內執行：

```sh
python3 scripts/bootstrap.py --check
python3 scripts/bootstrap.py --ensure
```

`--check` 是唯讀檢查；`--ensure` 只會初始化空 Project 與設定 Skill-owned CI variables。
OCI push username/password 的 GitLab environment scope 是 `package`，因此 validate/build job
不會取得 push credential；Skill-owned CI variables 也都設為 `protected`，只在受保護的
`main` 與 `sites/*` branch 可用。

Skill、scaffold、runtime base、Next.js builder 與 chart schema 必須視為同一 Release Set。更新
Release Set 後，管理員先重新驗證 digest，再明確執行：

```sh
python3 scripts/upgrade.py
```

若 managed scaffold 被人工修改，Skill 會停止並回報 `MANAGED_SCAFFOLD_DRIFT`，不會靜默覆蓋。
