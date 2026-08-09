# 隔離式 Docker Compose E2E

此測試依 `PLATFORM-CONFIGURATION-DESIGN.md` 的 Compose E2E 驗證列，從空白資料目錄啟動一套完全隔離的平台，並以公開 HTTP／WebSocket 介面驗證：

- 本機 OIDC authorization-code login 與 Manager session bootstrap；
- Workspace 建立後排入正式 `workspace_start` operation，並等候 Runtime、Browser、Canvas 收斂；
- Runtime、Browser、Canvas 的同源 gateway；
- Browser access API 與 TURN credential；
- 使用 Execution Grant 的 Thread WebSocket Upgrade。

## 隔離保證

- 每次執行產生唯一 Compose project、network、安裝識別與 Workspace UUID。
- 執行時從 root Compose 產生一份標準、可由 `yaml.safe_load` 解析的隔離 Compose 文件；固定 `container_name` 全部移除、host TCP port 由 Docker 自動配置，Coturn 只留在測試 network。
- 原始碼透過暫存 mirror root 的唯讀來源連結重用；PostgreSQL、Redis、LDAP、Keycloak、Workspace 與 Secret 資料全部建立於 repository 外的 `/tmp/aileron-compose-e2e/<run-id>/`，結束或收到中斷訊號時刪除。
- 啟動時會安全清除沒有對應 Compose container 的舊測試暫存目錄；repository 內不建立 `.state` 或產生後的 Compose 文件。
- E2E 執行本身只使用已存在的 image，執行命令固定帶 `--no-build --pull never`；執行前必須先以目前 worktree 建立本次要驗證的 image。
- E2E runner 與 frontend 共用 network namespace，使用 loopback `http://127.0.0.1:8082` 作為唯一 Platform Public Origin，確保 Compose 測試也遵守 HTTP 僅限 loopback 的安全契約。
- 清理只針對唯一 Compose project，以及本次 Workspace UUID 的 `aileron.workspace_id` label；不使用全域 prune、名稱前綴掃描或 root stack 的 `down`。
- 執行前記錄既有 running container，結束時確認它們仍在執行。

## 執行

所有測試邏輯都在 container 內執行。請從 repository 根目錄執行：

```bash
docker run --rm \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v /tmp/aileron-compose-e2e:/tmp/aileron-compose-e2e \
  -v "$PWD:/repo:ro" \
  -w /repo \
  -e COMPOSE_E2E_HOST_REPO_ROOT="$PWD" \
  docker:27-cli \
  sh scripts/test/compose-e2e/run.sh
```

只驗證隔離設定、必要 image 與 resolved Compose，不啟動服務：

```bash
docker run --rm \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v /tmp/aileron-compose-e2e:/tmp/aileron-compose-e2e \
  -v "$PWD:/repo:ro" \
  -w /repo \
  -e COMPOSE_E2E_HOST_REPO_ROOT="$PWD" \
  docker:27-cli \
  sh scripts/test/compose-e2e/run.sh --preflight-only
```

`/tmp/aileron-compose-e2e` 必須以相同絕對路徑掛入，讓 runner 與 Docker daemon 看見同一份暫存資料；host repository 路徑則透過 `COMPOSE_E2E_HOST_REPO_ROOT` 明確傳入，供巢狀 Docker 建立唯讀 bind mount。Preflight 會驗證這些路徑，若未正確掛載便 fail closed。Docker／Compose 不可用、來源缺漏、唯一名稱未生效、仍有固定 host port，或任一必要 image 不存在時，同樣不會啟動服務。

## OIDC 自動化邊界

測試只使用 disposable local OIDC profile 的本機緊急管理員，透過 Keycloak HTML form 完成標準 authorization-code flow；不接受 Resource Owner Password Grant、不讀取 host cookie，也不接觸外部 IdP 帳密。若 Keycloak form 或 callback 契約改變，測試會直接失敗，不會繞過身份驗證。
