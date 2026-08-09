# HomeLab 驗收設定

這份文件只描述如何在 `rke2-homelab` 驗收 Skill-driven Canvas publishing。它不是平台
產品契約；GitLab、OCI registry、Argo CD、Kubernetes、DNS 與 CA 的實際位址必須依環境
替換，不可把 HomeLab hostname、IP 或 token 寫入 Skill source。

## 管理員一次性準備

管理員需要準備：

1. GitLab group 與一個「空的」Workspace Project；Project 名稱由 Workspace 環境中的
   `AILERON_PUBLISH_GITLAB_PROJECT_PATH` 指定。
2. GitLab API token：可查詢該 Project、推送 repository、設定 masked CI variables、觸發
   API pipeline。Skill 不建立 Project。
3. 受信任的 GitLab Runner：validate/build job 不取得 OCI push password；package job 才能
   取得 package-scoped push credential。
4. OCI registry 的 site image/chart repository、push robot 與 Kubernetes pull Secret。
5. 已建立的 Argo CD AppProject、API account、repository credential、Workspace namespace、
   standard IngressClass、TLS Secret 與 DNS record。
6. immutable runtime base 與 Next.js builder image digest。

Argo CD AppProject 建議只允許：

- 該環境的 OCI Helm chart repository；
- Workspace namespace；
- Deployment、Service、Ingress 三種 namespace resource；
- 不允許 cluster-scoped resource。

## Workspace 環境變數

所有初始設定都放在 Workspace process environment。至少需要：

```text
AILERON_PUBLISH_BUILD_PROVIDER=gitlab
AILERON_PUBLISH_DEPLOY_PROVIDER=argocd
AILERON_PUBLISH_WORKSPACE_ID=<workspace-id>
AILERON_PUBLISH_GITLAB_API=https://gitlab.example/api/v4
AILERON_PUBLISH_GITLAB_PROJECT_PATH=group/workspace-project
AILERON_PUBLISH_GITLAB_TOKEN=<gitlab-token>
AILERON_PUBLISH_ARGOCD_URL=https://argocd.example
AILERON_PUBLISH_ARGOCD_TOKEN=<argocd-token>
AILERON_PUBLISH_ARGOCD_PROJECT=canvas-sites
AILERON_PUBLISH_OCI_REGISTRY=registry.example
AILERON_PUBLISH_OCI_SITE_REPOSITORY=canvas/sites
AILERON_PUBLISH_OCI_CHART_REPOSITORY=canvas/charts
AILERON_PUBLISH_OCI_PUSH_USERNAME=<package-robot>
AILERON_PUBLISH_OCI_PUSH_PASSWORD=<package-secret>
AILERON_PUBLISH_BASE_DOMAIN=canvas.example
AILERON_PUBLISH_DESTINATION_NAMESPACE=<precreated-workspace-namespace>
AILERON_PUBLISH_RUNTIME_BASE=registry.example/base/runtime@sha256:<64-hex>
AILERON_PUBLISH_NEXTJS_BUILDER=registry.example/base/builder@sha256:<64-hex>
AILERON_PUBLISH_IMAGE_PULL_SECRET_NAME=canvas-pull
AILERON_PUBLISH_TLS_SECRET_NAME=canvas-tls
AILERON_PUBLISH_INGRESS_CLASS_NAME=nginx
AILERON_PUBLISH_RELEASE_VERSION=2026.08.04
```

Token 由使用者向平台管理員索取並設定到 Workspace；不要把 token 放入 `.aileron`、Git
repository、Helm values 或對話紀錄。

## Containerized 驗收順序

在 `develop` 合併後，將分支同步至 `rke2-homelab`，再執行：

1. container 內執行 Skill contract tests 與 scripts compile check；
2. `bootstrap.py --check` 驗證 GitLab Project、Argo AppProject 與 scaffold；
3. `bootstrap.py --ensure` 初始化唯一 managed repository；
4. 建立 static Canvas，執行 `publish.py`，確認 Git branch、API pipeline、image digest、
   OCI chart、Argo Application、Pod、Ingress 與 `/_aileron/publication.json`；
5. 修改 static source 再發佈，確認同一 `siteId` branch 與 Application 更新；
6. 使用另一 Workspace namespace 重複測試，確認 namespace、chart path、Application 不交叉；
7. 執行 `unpublish.py`，確認只刪除該站台 Application，並由 Argo prune 站台資源；
8. 執行 `status.py`，確認 provider evidence 與 HTTPS endpoint 一致；
9. 測試 Pipeline failed、Argo timeout、registry 失敗與 Git optimistic-concurrency conflict。

所有驗收輸出都必須遮罩 token、password、Authorization header 與含 credential 的 URL。
