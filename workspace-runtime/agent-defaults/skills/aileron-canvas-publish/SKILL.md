---
name: aileron-canvas-publish
description: 將 Aileron Web Canvas 的 static 或 Next.js standalone 來源，透過 Workspace 環境中的 provider token 推送到 GitLab，觸發 GitLab Pipeline 建置不可變 image 與 OCI Helm chart，再由 Argo CD 部署到 Kubernetes。使用者提到發佈、上線、deploy、正式網址、發佈狀態、回滾或撤下 Canvas 網站時使用。
license: MIT
metadata:
  author: aileron
  version: "2.0"
---

# Aileron Canvas Publish

此 Skill 是可選的 Workspace 能力。Canvas 預覽不會自動發佈，也不需要 Aileron 平台提供
Publishing API。Skill 只透過目前 Workspace process environment 呼叫已由管理員準備好的
GitLab 與 Argo CD API。

## 信任與邊界

- 管理員預先建立一個空的 GitLab Project；Skill 只負責 bootstrap repository scaffold，
  不建立 Project，也不建立 Argo CD AppProject、Kubernetes namespace 或 TLS/DNS 資源。
- 憑證只從 Workspace 的 `AILERON_PUBLISH_*` 環境變數讀取，不讀取 `.env`、平台全域設定檔或
  Aileron Manager 設定。Token/password 不會寫入 Git、Result Envelope 或輸出。
- 初始 provider 組合是 `gitlab` + `argocd`。其他 Git provider 或直接 Helm deploy 必須以
  新 provider script 實作，不改變本 Skill 的 provider-neutral Result Envelope。
- 每個 Workspace 使用一個 GitLab Project；每個站台使用 Skill 產生的 UUID `siteId` 與
  長期存在的 `sites/<siteId>` branch。Git manifest 是站台 identity 的來源。
- 只接受 managed `static` 與 `nextjs-standalone`。Next.js 必須有 lockfile、
  `packageManager` 與 `output: 'standalone'`。

## 操作順序

### 1. 檢查環境

先執行：

```sh
python3 scripts/bootstrap.py --check
```

這會檢查 Workspace 環境、GitLab Project、受限的 Argo CD AppProject、repository scaffold、
OCI image digest 與必要的固定資源。若 Project 不存在，回報 `GITLAB_PROJECT_MISSING`，請
使用者向平台管理員取得已建立的 Project；不要自行建立 Project。

### 2. 首次準備 repository

若檢查回報需要 bootstrap，執行：

```sh
python3 scripts/bootstrap.py --ensure
```

這會把本 Skill 內的固定 scaffold 推送到管理員建立的空 Project，並同步 Skill-owned 的
CI variables。OCI push password 只設定給 `package` environment，validate/build job 不會取得
artifact push credential。

### 3. 發佈目前 Canvas

```sh
python3 scripts/publish.py --workspace /workspace
```

Skill 會：

1. 讀取 `/workspace/.aileron/canvas.json`，將來源複製到 `sites/<siteId>` branch；
2. 套用固定的 symlink、credential-like file、`.env`、build output 與特殊檔案過濾；
3. 以 `project identity + siteId + source commit` 產生 deterministic `pub-...`；
4. 透過 GitLab API 觸發唯一允許的 `AILERON_PUBLISH_TRIGGER=skill` Pipeline；
5. 等待 image/chart Pipeline 成功，建立或更新一個 Argo CD Application，回傳 `DEPLOYING`；
6. 將來源 commit、Publication ID 與 deployment action ID 寫入本地 pointer，方便後續查詢。

Pipeline 產物是 immutable site image 與 immutable OCI Helm chart；Argo CD 以 chart
`targetRevision` 部署，不直接從 Git 讀取 Kubernetes manifest。

### 4. 查詢狀態

```sh
python3 scripts/status.py --workspace /workspace
```

若回傳 `READY`，只回報 Result Envelope 中的正式 HTTPS URL。`UNKNOWN`、`VERIFYING` 或
`DEPLOYING` 時依 `nextOperation` 重試 `status`；Pipeline 失敗時不要重複推送相同來源，先
修正錯誤後再執行 `publish`。

### 5. 回滾、升級與撤下

已存在於 OCI registry 的 Publication 可以指定回滾：

```sh
python3 scripts/rollback.py --workspace /workspace --publication-id pub-<32-hex>
```

Skill Kit 或 managed scaffold 的版本變更必須明確執行：

```sh
python3 scripts/upgrade.py
```

只有使用者明確要求撤下時才執行：

```sh
python3 scripts/unpublish.py --workspace /workspace
```

撤下只刪除目前站台的 Argo CD Application，保留 Git branch、OCI artifact 與本地 identity
history；確認 Argo CD 已完成 prune 前，不聲稱 Kubernetes resource 已經消失。

## Result Envelope

每個 script stdout 都只輸出一個 JSON 物件，包含：

`schemaVersion`、`operation`、`status`、`phase`，以及可選的 `siteId`、`publicationId`、
`deploymentActionId`、`evidence`、`errorCode`、`retryable`、`nextOperation`、`details`。

固定狀態為 `PREPARING`、`BUILDING`、`ARTIFACT_READY`、`DEPLOYING`、`VERIFYING`、`READY`、
`FAILED`、`RECOVERING`、`UNKNOWN`、`UNPUBLISHED`。不要把 traceback、完整 CI trace 或任何
credential 貼到回覆。

## Progressive loading

- 管理員要準備 GitLab、OCI registry、Argo CD、Kubernetes namespace、Ingress、TLS、DNS 或
  HomeLab 驗收時，讀 `references/homelab-setup.md`。
- 需要依 error code 排查時，讀 `references/troubleshooting.md`。
- 一般發佈不需要預先載入上述 reference。
