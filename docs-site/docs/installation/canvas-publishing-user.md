---
title: Canvas 發佈使用者操作
description: 使用 Workspace Skill 發佈、查詢、回滾與撤下 Canvas 站台
---

# Canvas 發佈使用者操作

使用者先在 Web Canvas 查看預覽；只有明確要求正式發佈時才使用
`aileron-canvas-publish` Skill。你需要向平台管理員取得 Workspace 的
`AILERON_PUBLISH_*` 環境變數，Skill 不會從 prompt 接收或儲存 token。

## 發佈

先檢查：

```sh
python3 scripts/bootstrap.py --check
```

首次使用若回報 `PUBLISHING_BOOTSTRAP_REQUIRED`，執行：

```sh
python3 scripts/bootstrap.py --ensure
```

然後發佈目前 Canvas：

```sh
python3 scripts/publish.py --workspace /workspace
```

Skill 會自動產生 UUID `siteId`、固定 hostname、`sites/<siteId>` branch、Publication ID，
並觸發 GitLab API Pipeline。相同 Workspace 後續發佈會更新同一 site branch 與 Application；
不會建立第二個站台。

## 狀態與網址

```sh
python3 scripts/status.py --workspace /workspace
```

Result Envelope 可能回傳：

- `BUILDING`：Pipeline 尚未完成；
- `ARTIFACT_READY`：image/chart 已完成，仍需 Application；
- `DEPLOYING`：Argo CD 正在同步；
- `VERIFYING`：正在確認 Argo health 與 HTTPS manifest；
- `READY`：`details.url` 是正式網址；
- `FAILED`：依 `errorCode` 修正來源或平台設定；
- `UNKNOWN`：provider timeout，先查詢狀態，不要重複觸發。

Skill 以 `https://<hostname>/_aileron/publication.json` 確認 `siteId`、Publication ID 與來源
commit 一致後，才回報 `READY`。

## 回滾

若本地 publication history 有仍可用的 immutable chart：

```sh
python3 scripts/rollback.py \
  --workspace /workspace \
  --publication-id pub-<32-hex>
```

回滾只更新目前站台的 Argo CD Application target revision，不會修改其他 Workspace 或建立
新的 repository。完成後重複執行 `status.py`。

## 撤下

只有明確要求撤下目前站台時執行：

```sh
python3 scripts/unpublish.py --workspace /workspace
```

這會刪除目前 `siteId` 的 Argo CD Application，保留 Git branch、OCI artifacts 與 identity
history。Argo CD prune 尚未完成前，狀態可能是 `UNKNOWN`；不要手動刪除其他 Application。

## 機密與錯誤

不要貼出 token、password、完整 CI trace 或 credential URL。常見錯誤包含：

- `PUBLISHING_CONFIG_MISSING`：Workspace environment 不完整；
- `PUBLISHING_CI_VARIABLES_INCOMPLETE`：Skill-owned CI variables 尚未同步，重新執行 `bootstrap.py --ensure`；
- `GITLAB_PROJECT_MISSING`：管理員尚未建立指定 Project；
- `PUBLISHING_SOURCE_CONFLICT`：同一 site branch 同時被其他操作更新；
- `MANAGED_SCAFFOLD_DRIFT`：管理員需要審查 managed files；
- `PIPELINE_FAILED`：先查 Pipeline 的失敗 job，再修正 source/build；
- `ARGOCD_APPLICATION_UNHEALTHY`：管理員檢查 namespace、image pull、Ingress 與 TLS。
