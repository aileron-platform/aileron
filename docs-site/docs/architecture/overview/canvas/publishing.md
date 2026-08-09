---
title: Canvas Skill 發佈架構
description: Canvas 從 Workspace 預覽經 GitLab Pipeline、OCI Helm chart、Argo CD 與 Kubernetes 發佈的 provider-neutral 架構
---

# Canvas Skill 發佈架構

Canvas 預覽與正式發佈是不同生命週期。正式發佈是 Workspace 的可選 Skill；Aileron Manager
不持有 publishing token，也不注入平台全域 publishing profile。

```text
Workspace Canvas preview
        │ 明確呼叫 Skill
        ▼
Workspace environment: AILERON_PUBLISH_*
        │
        ├─ GitLab API: bootstrap/check/push/trigger pipeline
        │                  │
        │                  ├─ validate/build: 不持有 OCI push credential
        │                  └─ package: immutable image + OCI Helm chart
        │
        └─ Argo CD API: one Application per site
                              │ OCI chart sync
                              ▼
             precreated namespace / Deployment / Service / Ingress
                              │
                              ▼
              HTTPS /_aileron/publication.json verification
```

## 固定 identity 與資源

| 資源 | identity | 說明 |
|---|---|---|
| GitLab Project | Workspace 設定的 `gitlabProjectPath` | 管理員預先建立；Skill 不建立 Project |
| source branch | `sites/<siteId>` | 每個站台一個 UUID，長期保留並以 optimistic concurrency 更新 |
| Git manifest | `.aileron/publishing/site-manifest.json` | 保存 siteId、workspace、build type、hostname 與 release pointer |
| Publication | `pub-` + project/site/source commit hash | 同一來源在不同 Project 也不會碰撞 |
| Argo CD Application | `canvas-site-<siteId-hash>` | 每個站台一個 Application，target 為 immutable OCI chart version |
| runtime namespace | 管理員預先建立 | Argo 使用 `CreateNamespace=false` |

Git branch 只保存來源與 managed manifest；Kubernetes YAML 不是 Git deployment source。Helm
chart 是 Kubernetes 部署的 canonical unit，image 使用 registry digest，chart 使用不可重用
的 Publication version。

## 發佈資料流

1. Skill `check` 讀取 Workspace environment，確認 GitLab Project、AppProject policy、digest、
   hostname 固定值與 repository scaffold；namespace、DNS、TLS、IngressClass 與 registry
   retention 由管理員準備並在 HomeLab E2E 驗收。
2. `publish` 從 `.aileron/canvas.json` 解析 static 或 Next.js standalone source，拒絕 symlink、
   credential-like file、`.env`、build cache 與 Workspace 外部路徑。
3. Skill 以 Git API authentication 推送 `sites/<siteId>` branch，再用 GitLab API 以
   `AILERON_PUBLISH_TRIGGER=skill` 觸發 pipeline。
4. validate stage 驗證 branch、manifest、source commit 與 pipeline variables；build stage
   建立靜態輸出或 locked Next.js standalone 輸出。
5. package stage 取得限定 `package` environment 的 OCI credential，推送 immutable site image
   與 immutable OCI Helm chart。artifact 不覆蓋既有 Publication。
6. Skill 等待 Pipeline 成功後建立或更新 Argo Application，啟用 automated sync、prune、
   selfHeal，並限制 `CreateNamespace=false`。
7. `status` 交叉檢查 GitLab Pipeline、Argo `Synced/Healthy`、target revision 與 HTTPS
   `/_aileron/publication.json`，全部一致才回報 `READY`。

## Provider-neutral contract

Skill 的 provider client 只負責 provider API 操作，結果統一成 versioned Result Envelope：

```json
{
  "schemaVersion": 1,
  "operation": "publish",
  "status": "DEPLOYING",
  "phase": "DEPLOYING",
  "siteId": "<uuid>",
  "publicationId": "pub-<32-hex>",
  "deploymentActionId": "<uuid>",
  "nextOperation": "status"
}
```

provider token、password、Authorization header 與含 credential URL 不得進入 envelope。
初始狀態固定為 `PREPARING`、`BUILDING`、`ARTIFACT_READY`、`DEPLOYING`、`VERIFYING`、
`READY`、`FAILED`、`RECOVERING`、`UNKNOWN`、`UNPUBLISHED`。

## 安全邊界

- AppProject 只允許指定 OCI chart repository、Workspace namespace 與 Deployment、Service、
  Ingress；不允許 cluster-scoped resource。
- published Pod 使用 non-root、read-only root filesystem、drop all capabilities、
  `RuntimeDefault` seccomp、無 privileged、無 hostPath、無 service-account token。
- Next.js build 必須使用 lockfile 與固定 package manager；建置輸入只來自 Skill 推送的 source
  branch。
- `main` 與 `sites/*` 必須是 Protected Branch，Runner 必須是受信任且只執行 managed scaffold；
  OCI registry 必須拒絕重用既有 Publication tag/version。
- `/_aileron/publication.json` 是 no-store verification endpoint，不可依賴 browser 或 proxy cache。
- unpublish 只刪除該 site 的 Application，保留 source branch、artifact 與 history；Argo prune
  未完成時狀態為 `UNKNOWN`。
- explicit `upgrade` 才能更新 managed scaffold；既有 scaffold drift 會 fail closed。

環境準備請參考 [Canvas 發佈管理員設定](/installation/canvas-publishing-admin)，使用者操作請參考
[Canvas 發佈使用者操作](/installation/canvas-publishing-user)。
