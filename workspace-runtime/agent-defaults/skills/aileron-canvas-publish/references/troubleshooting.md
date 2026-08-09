# Canvas 發佈疑難排解

| errorCode | 意義 | 處理方式 |
|---|---|---|
| `PUBLISHING_CONFIG_MISSING` | Workspace 的 `AILERON_PUBLISH_*` 不完整 | 依 `details.missing` 向平台管理員補齊環境變數，不要把 token 貼到對話 |
| `PUBLISHING_PROVIDER_UNSUPPORTED` | 目前 Kit 尚未提供指定 provider | 使用 `gitlab` + `argocd`，或安裝對應 provider Kit |
| `GITLAB_PROJECT_MISSING` | 管理員尚未建立指定的空 Project | 請管理員建立 Project；Skill 不會自動建立 Project |
| `PUBLISHING_PROJECT_NOT_EMPTY` | Project 不是空的，也不是 managed repository | 換用空 Project 或由管理員清理後再 bootstrap |
| `PUBLISHING_BOOTSTRAP_REQUIRED` | repository 尚未有目前版本 scaffold | 執行 `bootstrap.py --ensure` |
| `PUBLISHING_CI_VARIABLES_INCOMPLETE` | Skill-owned GitLab CI variables 遺失或值／scope 不一致 | 執行 `bootstrap.py --ensure`，再重新 `bootstrap.py --check` |
| `MANAGED_SCAFFOLD_DRIFT` | Skill-owned 檔案被修改 | 比對 scaffold，修正後重試；不要由 Skill 靜默覆寫 |
| `PUBLISHING_VERSION_MISMATCH` | Skill/Kit release set 不一致 | 先確認版本，再明確執行 `upgrade.py` |
| `CANVAS_MANIFEST_INVALID` | `.aileron/canvas.json` 不合法 | 重新從 Web Canvas 預覽產生 manifest |
| `PUBLISHING_SOURCE_SECRET` | 來源包含 credential-like 檔案 | 移除 `.env`、key、pem、p12 或 symlink 後重試 |
| `NEXTJS_LOCKFILE_REQUIRED` | Next.js 缺少 lockfile | 提交與 package manager 一致的 lockfile |
| `NEXTJS_STANDALONE_REQUIRED` | Next.js 沒有 standalone output | 在 next config 設定 `output: 'standalone'` |
| `GIT_OPERATION_FAILED` | clone、commit、fetch 或 push 失敗 | 檢查 GitLab token scope、branch protection、CA 與 runner 網路 |
| `PUBLISHING_SOURCE_CONFLICT` | 同一 `sites/<siteId>` branch 已被其他流程更新 | 重新讀取 Canvas source 後重試，不要強制 push |
| `GITLAB_API_ERROR` | GitLab API 呼叫失敗 | 檢查 API URL、token 權限、TLS CA 與 Project path |
| `PIPELINE_FAILED` | API-triggered Pipeline 失敗 | 讀取失敗 job 的摘要，修正 source/build/registry 問題後再 publish |
| `PUBLISHING_PIPELINE_TIMEOUT` | Pipeline 超過等待時間，狀態未知 | 執行 `status.py`；不要重複觸發直到確認 provider state |
| `GITLAB_PIPELINE_STATUS_UNKNOWN` | GitLab 回傳未支援的 Pipeline 狀態 | 保留目前 pointer，稍後重試 `status.py` |
| `ARGOCD_API_ERROR` | Argo CD API 呼叫失敗 | 檢查 URL、token RBAC、repository credential 與 CA |
| `ARGOCD_APPLICATION_UNHEALTHY` | Application 已同步但健康檢查失敗 | 檢查 Pod、Ingress、image pull 與 TLS；確認上一個 verified Publication |
| `UNPUBLISH_PRUNE_PENDING` | Application deletion 尚未完成 | 重試 `status.py`，確認 Argo prune 完成 |
| `PUBLICATION_HISTORY_MISSING` | 本地 pointer 沒有指定 Publication | 只能回滾仍在 Workspace history 的 Publication；先保留檔案再查 provider |
| `PUBLICATION_VERIFICATION_MISMATCH` | HTTPS manifest 明確回報錯誤 Publication | 若有 verified history，`status.py` 會先自動恢復；否則檢查 Application 與 source |

任何排查都不得輸出 token、password、完整 CI trace 或含認證資訊的 remote URL。
