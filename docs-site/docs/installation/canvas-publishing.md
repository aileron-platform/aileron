---
title: Canvas Skill 發佈總覽
description: 以 Workspace Skill、GitLab Pipeline、OCI Helm chart、Argo CD 與 Kubernetes 發佈 Aileron Web Canvas
---

# Canvas Skill 發佈總覽

Canvas 預覽與正式發佈是兩條不同流程。預覽只在 Aileron Web Canvas 中執行；使用者明確
要求發佈時，才由可選的 `aileron-canvas-publish` Skill 把目前來源推送到 GitLab，透過
GitLab API 觸發 Pipeline，產生不可變 site image 與 OCI Helm chart，最後以 Argo CD 部署。

本方案不要求所有環境都存在 Argo CD。Skill contract 將 build/deploy provider 分開；初始
只提供 `gitlab` + `argocd`，未來可增加 GitHub、Azure DevOps 或直接 Helm provider，而不
改動 Canvas、Workspace Manager 或核心平台 API。

## 邊界

- 管理員建立 GitLab Project、AppProject、namespace、registry、DNS、TLS 與 runner 權限。
- Skill 不建立 GitLab Project，不管理平台全域 token，也不要求 Aileron Publishing Service。
- 使用者把管理員提供的 `AILERON_PUBLISH_*` 設定放在 Workspace 環境變數；token/password
  永不寫入 Git、`.aileron` 或 Result Envelope。
- 每個 Workspace 一個 GitLab Project；每個站台一個 UUID `siteId` 與
  `sites/<siteId>` 長期 branch。
- Git manifest 保存站台 identity；Helm chart 是 Kubernetes 部署的 canonical artifact。

## 文件入口

- [管理員設定與權限](./canvas-publishing-admin.md)：建立 GitLab、OCI、Argo CD、Kubernetes、
  DNS/TLS 與 Workspace environment contract。
- [Workspace 使用者操作](./canvas-publishing-user.md)：從 Canvas 預覽發佈、查詢、回滾與撤下。

## 生命週期

```text
Canvas preview
    -> Skill check/bootstrap
    -> Git push sites/<siteId>
    -> GitLab API pipeline
    -> immutable image + immutable OCI Helm chart
    -> Argo CD Application
    -> Kubernetes Ingress
    -> HTTPS /_aileron/publication.json verification
```

Pipeline 只接受 `AILERON_PUBLISH_TRIGGER=skill` 的 API trigger。validate/build stage 不取得
OCI push credential；package stage 才能推送 artifact。Argo CD Application 只允許受限的
Deployment、Service、Ingress，且不會自動建立 namespace。
