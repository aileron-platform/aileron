# 隔離式 Docker Compose E2E

此測試依 `contracts/platform-configuration/contract.json` 的 Compose 契約，從空白資料目錄啟動一套完全隔離的平台，並以公開 HTTP／WebSocket 介面驗證：

- 本機 OIDC Authorization Code + PKCE、JIT Manager session bootstrap；
- 唯一乾淨 Keycloak volume 首次啟動後執行一次真實 restart，重新健康後以 Admin Console HTML form 驗證管理員登入，再驗本機 OIDC 登入；
- Workspace 建立後排入正式 `workspace_start` operation，並等候 Runtime、Browser、Canvas 收斂；
- Runtime、Browser、Canvas 的同源 gateway；
- Browser access API 與 TURN credential；
- 使用 Execution Grant 的 Thread WebSocket Upgrade；
- Runtime 元件重啟確實產生新 instance，以及 Manager session logout 與 IdP logout handoff。

## 隔離保證

- 每次執行產生唯一 Compose project、network、安裝識別與 Workspace UUID。
- 執行時從 root Compose 產生一份標準、可由 `yaml.safe_load` 解析的隔離 Compose 文件；固定 `container_name` 全部移除、host TCP port 由 Docker 自動配置，Coturn 只留在測試 network。
- 原始碼透過暫存 mirror root 的唯讀來源連結重用；PostgreSQL、Redis、Keycloak、Workspace 與 Secret 資料全部建立於 repository 外的 `/tmp/aileron-compose-e2e/<run-id>/`，結束或收到中斷訊號時刪除。
- 啟動時會安全清除沒有對應 Compose container 的舊測試暫存目錄；repository 內不建立 `.state` 或產生後的 Compose 文件。
- 正式 acceptance producer 先確認 exact clean commit；Runner 再以固定 amd64 base digest 建立本次專用的 development image，並驗證每個 image 的 `Architecture` 與 `org.opencontainers.image.revision`。乾淨 Docker daemon 若缺少 helper 或 sidecar，preflight 只會以 `linux/amd64` pull 帶有 exact `@sha256` 的 reference；本次 source image 必須由 Runner build，mutable reference 一律拒絕。E2E 啟動階段固定帶 `--no-build --pull never`，不接受舊的 mutable development tag。
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
  -e COMPOSE_E2E_SOURCE_REVISION="$(git rev-parse HEAD)" \
  docker:27-cli@sha256:f56779b4e86550493153cc8642c9c8e40b5d934e43cb5b4ea463aea5245c5c01 \
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
  -e COMPOSE_E2E_SOURCE_REVISION="$(git rev-parse HEAD)" \
  docker:27-cli@sha256:f56779b4e86550493153cc8642c9c8e40b5d934e43cb5b4ea463aea5245c5c01 \
  sh scripts/test/compose-e2e/run.sh --preflight-only
```

`/tmp/aileron-compose-e2e` 必須以相同絕對路徑掛入，讓 runner 與 Docker daemon 看見同一份暫存資料；host repository 路徑則透過 `COMPOSE_E2E_HOST_REPO_ROOT` 明確傳入，供巢狀 Docker 建立唯讀 bind mount。正式 acceptance producer 會在執行前、每個 suite 後與整批結束時驗證 exact clean HEAD，且一定執行唯一 Compose project 的 `down --volumes --remove-orphans`。Docker／Compose 不可用、來源缺漏、image revision 不符、唯一名稱未生效或仍有固定 host port 時都會 fail closed。

## OIDC 自動化邊界

測試不啟用 LDAP，只使用 disposable local OIDC profile 的本機緊急管理員，透過 Keycloak HTML form 完成標準 Authorization Code + PKCE S256 flow，並驗證 restart 後 Admin Console 登入、JIT session、Workspace、元件重啟與 logout；不接受 Resource Owner Password Grant、不讀取 host cookie，也不接觸外部 IdP 帳密。provider-neutral offline conformance 另驗證未來替換 OIDC provider 的 issuer/discovery/JIT seam；logout 與 Runtime restart 只由本段真正執行生命週期操作的 Compose E2E 證明，不歸入 offline conformance capability。若任一契約改變，測試會直接失敗，不會繞過身份驗證。
