---
title: Docker 模式
---

# Docker 部署

## 適用情境

- 本機開發與除錯
- 快速體驗完整平台功能
- 不需要 Kubernetes、Operator、Cilium 的情境
- 單機環境部署

## 需求

- [Docker](https://docs.docker.com/get-docker/)（建議 24.0+）
- [Docker Compose](https://docs.docker.com/compose/install/)（V2，通常已內建於 Docker Desktop）
- [Git LFS](https://git-lfs.com/)（選用；知識庫啟用 Git LFS 並管理大型 `raw/` 檔案時需要）
- 至少 4 vCPU
- 至少 8GB 可用記憶體
- 建議 12GB 到 16GB 可用記憶體，以支援較穩定的瀏覽器與 agent 工作流程
- 至少 30GB 可用磁碟空間
- 建議保留 50GB 可用磁碟空間，避免 image、volume 與 workspace 資料快速吃滿

## 服務架構

Docker 模式下，root `docker compose` 管理 control plane 與安裝層 TURN readiness stack。Workspace Manager 再透過 Docker API，為每個啟動中的 Workspace 建立獨立 execution plane：

```text
Frontend / Manager / external OIDC or development IdP fixture
               |
       Workspace Manager + Docker API
               |
       +-------------------------------------+
       | Workspace A: Runtime/Browser/Canvas |
       | Workspace B: Runtime/Browser/Canvas |
       +-------------------------------------+

PostgreSQL 與 Redis 提供 control-plane 基礎設施；Coturn、Connectivity Evidence Gateway 與
host frontend vantage 提供 Browser access 所需的 TURN 路徑證據。
```

### 各服務說明

| 服務 | 映像 | 說明 |
|------|------|------|
| **postgres** | `postgres:15-alpine` | 主要平台資料庫 |
| **redis** | `redis:7-alpine` | 任務佇列 (Celery broker)、結果後端、session 管理 |
| **openldap** | `osixia/openldap:1.5.0` | 本機帳號生命週期開發用 LDAP 目錄 |
| **openldap-seed** | `osixia/openldap:1.5.0` | 一次性建立本機 LDAP 測試資料；成功後結束 |
| **turn-readiness-preflight** | `ailerondocker/workspace-manager:dev` | 驗證 profile、secret bundle、image 與 relay port；失敗時阻止 TURN stack 啟動 |
| **coturn** | `${COTURN_IMAGE}` | TURN control listener 與 relay UDP range |
| **connectivity-evidence-gateway** | `${WORKSPACE_OPERATOR_IMAGE}` | 收集 host frontend vantage 的 challenge/evidence |
| **connectivity-external-agent** | `${WORKSPACE_OPERATOR_IMAGE}` | 使用 host network 從本機 frontend vantage 執行 TURN probe |
| **runtime-assertion-key-init** | `ailerondocker/workspace-manager:dev` | 一次性產生 Runtime assertion 金鑰；成功後結束 |
| **identity-bootstrap** | `ailerondocker/workspace-manager:dev` | 一次性建立本地平台角色與 admin snapshot；不建立 provider 密碼；成功後結束 |
| **workspace-manager** | `ailerondocker/workspace-manager:dev` | 核心管理服務：Workspace CRUD、權限、生命週期與動態 execution-plane provisioning |
| **frontend** | `ailerondocker/workspace-ui:dev` | React + Vite 開發伺服器 |
| **drawio** | `jgraph/drawio` | 內嵌圖表編輯工具 |

這十三個名稱就是 root Compose 的完整 service 清單。Celery worker、Celery Beat 與
Flower 不是獨立 Compose service，而是由 `workspace-manager` 容器內的 Supervisor
共同管理；Flower 只在部署內部網路提供服務。`turn-readiness-preflight`
是一次性 gate，不提供長駐 HTTP endpoint。

下列是 Manager 為每個 Workspace 動態建立的容器，不存在於 root `docker-compose.yml`：

| 容器 | 說明 |
|------|------|
| **workspace-runtime-&lt;workspace-id&gt;** | Agent Runtime、Terminal、檔案與 Git API |
| **workspace-browser-&lt;workspace-id&gt;** | neko WebRTC 瀏覽器與 CDP |
| **workspace-browser-connectivity-probe-&lt;workspace-id&gt;** | 與 Browser 共用 network namespace 的低權限 backend TURN probe；只提供內部 `:8082/v1/evidence` |
| **workspace-canvas-&lt;workspace-id&gt;** | Workspace Canvas 渲染與管理 API |

:::info Git LFS 與知識庫
知識庫的 Git 版本控制是每個 Knowledge Base 的選項；只有在知識庫啟用 Git LFS 時，manager 執行環境才需要可用的 `git lfs` 指令。Docker 映像若要支援大型 PDF、圖片、壓縮檔或其他 `raw/` 來源檔案的 LFS tracking，請確認 `workspace-manager` image 內已安裝 Git LFS。
:::

首次啟動、TURN readiness bundle、確認服務狀態與停止／清理流程請見 [安裝與啟動](./getting-started)。`docker buildx bake --load local` 建置專案 image；`docker compose up --no-build` 只使用既有 image，Runtime、Browser、Canvas 與每個 Browser probe 仍由 Manager 動態建立。

在 Aileron 中，這個完整的 Docker Compose stack 不只是部署方式，也是預設的本地開發模式。日常模組開發應以整套服務一起啟動為前提，再透過開發用掛載與各服務內建的 reload 機制，即時反映程式碼變更。

服務 URL、預設帳號與健康檢查端點請見 [服務位址與帳號](./service-endpoints)。

## 版本與依賴責任

版本控制依來源類型分工，不由 `ops.py` 或 Compose 重複維護：

| 類型 | 唯一來源 | 原則 |
|------|----------|------|
| Python、Node.js、npm、pnpm、uv、Claude Code、Codex、OpenCode、Playwright CLI、Maven 等 image 工具鏈 | root `docker-bake.hcl` | Dockerfile 只接受無預設值的 build argument |
| Frontend 與 Canvas npm 套件 | 各自的 `package.json`、`package-lock.json` | 使用 `npm ci` 重現 lockfile |
| Manager 與 Runtime Python 套件 | 各自的 `pyproject.toml`、`uv.lock` | 使用 frozen lockfile 建置 |
| Go 模組 | 各自的 `go.mod`、`go.sum` | 由 Go module lock 狀態重現 |
| PostgreSQL、Redis、OIDC adapter、Draw.io 等執行期服務 image | `docker-compose.yml` 或 Helm values | 與 application build toolchain 分離管理 |

更新工具鏈版號時，只修改 `docker-bake.hcl`，並同步更新 checksum 類欄位。不要在 Dockerfile、Compose、Makefile、shell script 或 `ops.py` 再放一份數字版號。

可先檢查 Bake 最終解析結果，而不進行建置：

```bash
docker buildx bake --print local
docker buildx bake --print release
```

RKE2 發佈腳本也透過相同 Bake target 解析工具鏈版號，再套用 registry、tag 與 `linux/amd64` 平台；因此本機、CI 與發佈流程不需要各自維護 build argument。

## 環境變數配置

完整的環境變數參考請見 [環境變數參考](./environment-variables)。以下環境變數可透過 shell 或 `.env` 檔案設定，影響整體 docker compose 行為（其餘各服務變數請直接查閱環境變數參考頁）：

| 變數 | 預設值 | 說明 |
|------|--------|------|
| `PLATFORM_PUBLIC_ORIGIN` | `http://localhost:8082` | 唯一瀏覽器公開 Origin；不可含 path 或結尾 `/` |
| `OIDC_ISSUER_URL` | `http://localhost:8080/realms/aileron` | 外部 Provider canonical issuer |
| `OIDC_CLIENT_ID` | `aileron-manager` | Manager confidential client ID |
| `TZ` | `Asia/Taipei` | 系統時區 |
| `HOST_PROJECT_ROOT` | `.` | 專案根目錄在主機上的絕對路徑 |
| `HOST_PLATFORM_SECRETS_DIR` | 無 | PostgreSQL、OIDC client 與平台 Secret 檔案目錄 |
| `HOST_WORKSPACES_DIR` | `./data/workspace-data` | 工作區資料儲存路徑 |
| `HOST_WORKSPACE_SCRIPTS_DIR` | `./data/workspace-scripts` | Workspace scripts 儲存路徑 |
| `HOST_RUNTIME_HOME_DIR` | `./data/runtime-home` | 每個動態 Runtime 的完整使用者 HOME 儲存根目錄 |
| `WORKSPACE_OPERATOR_IMAGE` | `ailerondocker/workspace-operator:dev` | Gateway、host agent 與 Browser probe 使用的既有 Operator image |
| `COTURN_IMAGE` | `ailerondocker/platform-coturn:dev` | Coturn image；必須已存在於本機或由部署者提供 |
| `HOST_TURN_CONFIG_DIR` | `./data/turn-config` | canonical TURN profile 所在的主機目錄 |
| `HOST_TURN_SECRETS_DIR` | `./data/turn-secrets` | TURN REST、backend/frontend ICE、Coturn、Gateway 與 host agent secret bundle 目錄 |
| `TURN_CREDENTIAL_REVISION` | `docker-compose-v1` | 本次安裝的 TURN credential revision |
| `TURN_RELAY_MIN_PORT` / `TURN_RELAY_MAX_PORT` | `49160` / `49180` | 必須與 profile 的 `backend.relayPortRange` 完全一致 |
| `TURN_CONNECTIVITY_GATEWAY_EXTERNAL_PORT` | `18083` | host agent 連線的 Gateway 主機 port |
| `VITE_BROWSER_EXTENSION_ID` | 空 | 經 consumer 證明必要的 Browser extension capability flag |

:::tip .env 檔案
在專案根目錄建立 `.env` 檔案，docker compose 會自動載入。
:::

### 本機 OIDC Secret

啟用 `local-oidc` profile 時，`${HOST_PLATFORM_SECRETS_DIR}` 必須另含
`local-admin-password`、`ldap-admin-password`、`ldap-config-password`、
`ldap-alice-password` 與 `ldap-bob-password`。OpenLDAP 透過 image 原生的 `*_FILE`
介面讀取 mounted Secret；首次初始化完成後，長期 `slapd` 的 argv 與 environment 不含
Secret value。Keycloak 直接匯入包含本機緊急管理員的 `aileron` realm，不建立 master
realm bootstrap administrator，因此不需要額外的 Keycloak admin Secret。

`ldap-admin-password` 與 `ldap-config-password` 代表密碼的精確 bytes，不得包含前後空白
或結尾換行。`local-oidc-config` 會在 OpenLDAP 啟動前驗證此契約，不符合時 fail closed。

### TURN readiness bundle

動態 Browser 不發布個別 WebRTC media port；Neko 使用與 Kubernetes 相同的 TURN-compatible
profile，由 Coturn relay 將瀏覽器端流量送到 Compose network 內的 Browser container。

Docker Compose 會在 Coturn、Gateway、host agent、Manager 與 identity bootstrap 前執行
`turn-readiness-preflight`。以下檔案必須由部署者建立；缺少、空白或不一致時，Compose
會 fail closed：

```text
${HOST_TURN_CONFIG_DIR}/turn-reachability-profile.json
${HOST_TURN_SECRETS_DIR}/turn-rest-shared-secret
${HOST_TURN_SECRETS_DIR}/turn-backend-ice-servers.json
${HOST_TURN_SECRETS_DIR}/turn-frontend-ice-servers.json
${HOST_TURN_SECRETS_DIR}/coturn-auth-secret
${HOST_TURN_SECRETS_DIR}/gateway-internal-token
${HOST_TURN_SECRETS_DIR}/host-agent-token
${HOST_TURN_SECRETS_DIR}/connectivity-agent-tokens.json
```

`turn-rest-shared-secret` 與 `coturn-auth-secret` 必須相同，`connectivity-agent-tokens.json`
必須包含與 `host-agent-token` 相同的 `host` value。profile 必須是唯一的安裝設定來源，
且 `credentialIssuer.kind=turnRest`、`credentialIssuer.secretRef=turn-rest-shared-secret`、
`requiredFrontendVantages` 必須包含 `host`。profile 與 secret 不應提交到 Git。

可使用 repository 內的 profile contract 作為本機起點：

```bash
mkdir -p data/turn-config data/turn-secrets
cp contracts/browser-connectivity/turn-reachability-profile.json \
  data/turn-config/turn-reachability-profile.json
export HOST_PROJECT_ROOT="$PWD"
turn_secret="$(openssl rand -hex 32)"
printf '%s\n' "$turn_secret" > data/turn-secrets/turn-rest-shared-secret
printf '%s\n' '[{"urls":["turn:coturn:3478"]}]' > data/turn-secrets/turn-backend-ice-servers.json
printf '%s\n' '[{"urls":["turn:127.0.0.1:3478"]}]' > data/turn-secrets/turn-frontend-ice-servers.json
printf '%s\n' "$turn_secret" > data/turn-secrets/coturn-auth-secret
printf '%s\n' "$(openssl rand -hex 32)" > data/turn-secrets/gateway-internal-token
agent_token="$(openssl rand -hex 32)"
printf '%s\n' "$agent_token" > data/turn-secrets/host-agent-token
printf '{"host":"%s"}\n' "$agent_token" > data/turn-secrets/connectivity-agent-tokens.json
chmod 600 data/turn-secrets/*
chmod 600 data/turn-config/turn-reachability-profile.json
```

Manager 會以這些 bind-mounted 檔案的 owner UID/GID 啟動每個 Browser connectivity probe，
因此 profile、TURN REST secret 與 backend ICE servers 檔案必須由同一個 owner 建立；Compose
service 本身仍以最小必要 capability 執行。若這些檔案 owner 不同，Browser generation 會 fail
closed。backend ICE servers 使用 Compose network 內的 Coturn 位址，frontend ICE servers 使用
瀏覽器可到達的位址。

`workspace-operator` image 必須包含 `connectivity-evidence-gateway`、
`connectivity-external-agent` 與 `browser-connectivity-probe` 三個 binary mode；Compose
不會在啟動時隱藏建置或拉取替代 image。macOS／Linux 的預設 host vantage 使用 host
network，且 profile 的 frontend TURN URL 必須能由本機瀏覽器與 host agent 同時到達。

## Volume 掛載

### 持久化資料

| 路徑 | 容器路徑 | 說明 |
|------|----------|------|
| `./data/postgres` | `/var/lib/postgresql/data` | PostgreSQL 資料 |
| `./data/redis` | `/data` | Redis 持久化資料 |
| `./data/workspace-data` | `/host/workspace-data` | Manager 管理的 Workspace 專案檔案；動態容器再掛載對應子目錄 |
| `./data/workspace-scripts` | `/host/workspace-scripts` | Manager 管理的 Workspace scripts |
| `./data/runtime-home/<workspace-id>` | 動態 Runtime 的 `/home/developer` | 完整使用者 HOME；保存 agent 登入、設定、XDG state、Maven state 與使用者安裝工具 |
| `./data/turn-config` | `/run/secrets/turn-config` | canonical TURN reachability profile；唯讀掛載 |
| `./data/turn-secrets` | `/run/secrets/turn-secrets` | TURN／Gateway／host agent secrets；唯讀掛載 |

動態 Runtime 會以 16 MiB tmpfs 覆蓋 `${HOME}/.codex/tmp`。這只包含 Codex 程序期
helper alias；登入、設定與 session 仍位於持久化的 `${HOME}/.codex`。tmpfs 必須掛在
`tmp` 層，讓非 root Runtime UID 自行建立與 chmod `tmp/arg0`。

平台內建 CLI 不安裝在持久 HOME。uv、Node.js、npm、pnpm 與 Claude Code 位於系統
路徑；Codex／Playwright CLI 位於 `/opt/aileron/npm`；OpenCode 位於
`/opt/aileron/bin`。因此清空 HOME 只會清除使用者狀態，不會移除 image 內建工具。

### 開發用掛載

以下掛載是本地開發模式的核心。Control-plane service 由 Compose 掛載；Runtime 原始碼與 Terminal 則由 Manager 在建立動態 Runtime 時掛載。

| 路徑 | 容器路徑 | 用途 |
|------|----------|------|
| `./workspace-manager` | `/workspace-manager` | Manager 程式碼熱重載 |
| `./workspace-runtime` | 動態 Runtime 的 `/workspace-runtime` | Manager 建立容器時掛載 Runtime 原始碼 |
| `./workspace-terminal` | 動態 Runtime 的 `/workspace-terminal` | Manager 建立容器時掛載 Terminal 原始碼 |
| `./frontend` | `/app` | Frontend 程式碼熱重載 |
| `/var/run/docker.sock` | `/var/run/docker.sock` | Docker Socket（容器管理用） |

### 開發 Image 與正式 Image 的差異

Aileron 的 Bake target 與 tag 有明確語意：

| 類型 | 範例 tag | 程式碼來源 | 適用部署 |
|------|----------|------------|----------|
| 本機開發 | `dev`、`dev-lite`、`dev-java` | 透過 volume mount 掛入主機程式碼 | Docker Compose 開發模式 |
| Production | `${RELEASE_TAG}` | 程式碼已打包進 image | 正式 Docker image |
| Kubernetes | `${RELEASE_TAG}-kubernetes` | 程式碼已打包，採 non-root target | Kubernetes、Helm、RKE2 |

本機 tag 不包含 CPU architecture。Bake 會依建置平台產生可執行 image；跨平台發佈則由 CI 或 RKE2 發佈流程明確指定 platform。

:::caution Docker Socket 掛載
`workspace-manager` 與每個由 Docker provisioner 建立的 Runtime 都會掛載
`/var/run/docker.sock`；Runtime 不是依個別工具需求選擇性掛載。這等同授予容器控制主機
Docker daemon 的高權限，只適用於受信任的本機開發環境。Kubernetes Runtime 不掛 host
Docker socket；正式環境請使用 Kubernetes 模式。
:::

## 網路配置

所有服務使用同一個 bridge 網路 `aileron-network-dev`。

服務間以容器名稱互相訪問（DNS 解析由 Docker Compose 內建 DNS 處理），例如：

- `postgres:5432`
- `redis:6379`
- `workspace-manager:3001`
- `workspace-runtime-<workspace-id>:3002`
- `connectivity-evidence-gateway:8083`（Compose network 內）
- `coturn:3478`（Compose network 內）

Docker Compose 不安裝 IdP。請設定 installation-owned 外部 Provider 的
`OIDC_ISSUER_URL`；Discovery 固定為 `{issuer}/.well-known/openid-configuration`，文件中的
`issuer` 必須完全相同。`PLATFORM_PUBLIC_ORIGIN` 是瀏覽器唯一入口，callback、logout 與 CORS
都由此值衍生。

## 資源需求

| 服務 | CPU | 記憶體 | 說明 |
|------|-----|--------|------|
| workspace-browser | 2 核心上限 | 2GB 上限 / 1GB 保留 | neko WebRTC 最耗資源 |
| workspace-browser | — | 2GB SHM | 共享記憶體（Chrome 需要） |
| 其他服務 | 無限制 | 無限制 | 視實際使用動態分配 |

:::tip 建議配置
若只是在單機上體驗與驗證基本流程，建議至少使用 `4 vCPU / 8 GB RAM / 30 GB` 可用磁碟。若要較穩定地使用瀏覽器、自動化流程與多個服務並行，建議提升到 `6-8 vCPU / 12-16 GB RAM / 50 GB` 可用磁碟。若同一台主機還會再跑 Harbor、registry、其他大型容器或額外開發服務，則應以 `16 GB RAM` 以上為起點，否則很容易進入 swap 或磁碟不足狀態。
:::

## 常用指令

建置完整本機 image：

```bash
docker buildx bake --load local
```

使用既有 image 啟動，或非破壞性停止並保留資料：

```bash
docker compose up --remove-orphans --no-build -d
make down
```

執行 container 測試並保留同一批 image 作為最終本機成品：

```bash
make verify-local
```

查看日誌：

```bash
docker compose logs -f
docker compose logs -f workspace-manager
docker compose logs -f connectivity-evidence-gateway connectivity-external-agent coturn
docker logs -f workspace-runtime-<workspace-id>
docker logs -f workspace-browser-connectivity-probe-<workspace-id>
```

執行專案唯一的 host 破壞性完整重置：

```bash
make full-reset
```

`docker compose` 只管理 control-plane service；單一 Workspace 的啟動、停止、重啟與刪除必須透過 Manager UI 或 API，不可直接操作動態容器。`ops.py up --build` 仍可作為便利 wrapper，但其內部只依序呼叫 Bake 與 Compose，不擁有版號或架構判斷。`make down` 是保留 volumes、PostgreSQL 與 Workspace 持久資料的非破壞性停止。

啟動時會加上 Compose `--remove-orphans`，用來清除同一 Compose project 中設定檔已不存在的 container。Docker Compose 只會處理同 project label 的 orphan；Manager 動態建立的 Workspace 容器與其他 test project 不在此範圍。

## 完整重置

`full-reset` 是唯一由 host 執行的破壞性本機環境重置。單一 Workspace 的永久刪除必須透過 Manager UI 或 API，不得以 host container 清理取代。

```bash
make full-reset
```

此流程會依序：

1. 刪除所有動態 workspace 容器
2. 停止 docker-compose 所有服務
3. 刪除名稱符合 `aileron` filter 的 Docker volumes
4. 刪除名稱符合 `aileron` filter 的 Docker networks
5. 詢問是否刪除專案 Docker images
6. 清除 `data/` 目錄下的容器產生檔案（postgres、redis、選配 adapter、workspace-data 等）
7. 清除專案與 `/tmp` 的暫存目錄
8. 詢問是否執行 `docker system prune -f --volumes`

只有確認所有動態 Workspace 容器，以及 `data/` 下包含 PostgreSQL、Redis、Workspace data 與 Runtime home 在內的本機持久資料均已清除，`full-reset` 才算完成；任何必要清理失敗都必須以非零狀態結束。

前七步的直接資源查找限於 Aileron workspace/container、名稱符合 `aileron` 的
volume/network、專案 images 與列出的資料目錄。第八步是 Docker 全域 prune；若使用者
確認，Docker 會另外移除它判定為未使用的全域 container、network、image、build cache
與 volume，可能包含其他專案的未使用資源。

:::danger
`full-reset` 會刪除 Aileron 的資料庫資料，包含使用者、工作區設定、模板等；若再確認全域
prune，還可能刪除其他專案的未使用 Docker 資源。執行前確認已備份，並逐項閱讀互動提示。
:::

完整重置後重新啟動：

```bash
docker buildx bake --load local
docker compose up --remove-orphans --no-build -d
```

## 健康檢查

root Compose 的 control-plane service 設定了健康檢查：

| 服務 | 檢查方式 | 間隔 | 初始延遲 |
|------|----------|------|----------|
| postgres | `pg_isready` | 10s | — |
| redis | `redis-cli ping` | 10s | — |
| development-only OIDC fixture（若啟用） | TCP port 8080 | 30s | 60s |
| workspace-manager | HTTP `/health` | 30s | — |
| frontend | HTTP `/` | 30s | — |

動態 execution plane 的健康與各 component revision 由 Manager lifecycle 收斂。Runtime 的 `/health` 使用 `/workspaces/{workspaceId}/runtime/health` same-origin 路徑，不使用獨立 hostname 或 localhost port。

## Docker 與 Kubernetes 的責任分界

| 面向 | Docker 模式 | Kubernetes 模式 |
|------|-------------|-----------------|
| 服務管理 | `docker compose` | Helm + Operator |
| Workspace 生命週期 | Docker container | Pod + internal Service；公開流量經 Frontend gateway |
| 網路隔離 | Docker bridge network | Cilium Network Policy |
| 儲存 | Host volume mount | PVC (Persistent Volume Claim) |
| 認證 | 必要（外部 OIDC 或本機開發 IdP fixture） | 必要（外部 OIDC provider + Ingress TLS） |
| 適合場景 | 開發、測試、Demo | 正式環境、多人協作 |

若需要 Kubernetes 部署，請參閱 [Kubernetes 模式](./kubernetes)。
