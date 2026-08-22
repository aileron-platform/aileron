---
title: 安裝與啟動
---

# 安裝與啟動

預設的 Docker Compose 方案旨在讓團隊能快速從零開始，建立可用的企業級 agent 工作區平台，而不必先手動組裝所有工具鏈與服務。

## 需求

- [Docker](https://docs.docker.com/get-docker/)
- [Docker Compose](https://docs.docker.com/compose/install/)（通常已內建於 Docker Desktop）

## 標準 Docker 工作流程

本機建置與啟動採用 Docker 的標準介面，不要求先經過專案 Python CLI：

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
chmod 600 data/turn-config/turn-reachability-profile.json data/turn-secrets/*
docker buildx bake --load local
docker compose -f docker-compose.yml -f docker-compose.bundled-data-services.yml \
  up --remove-orphans --no-build -d
```

- `turn-readiness-preflight` 會先驗證 profile、secret bundle、image reference 與 relay port；
  驗證失敗時不會啟動 Coturn、Gateway、host agent 或 Manager。
- 本機流程固定合併 `docker-compose.yml` 與 `docker-compose.bundled-data-services.yml`；
  `docker compose up` 與 `docker compose down` 管理 root Compose 的 control-plane 與 TURN
  readiness services；Runtime、Browser、Canvas 與 Browser connectivity probe 由 Manager
  依 Workspace 動態管理。
- `docker-bake.hcl` 是 image 建置參數與工具鏈版號的唯一來源。
- Dockerfile 只宣告必要的 build argument，不提供數字版號預設值。
- `docker-compose.yml` 只負責執行既有 image，不在啟動時重新建置；
  `WORKSPACE_OPERATOR_IMAGE` 與 `COTURN_IMAGE` 指向的 image 必須已存在。
- `package-lock.json`、`uv.lock` 與 `go.sum` 分別管理應用程式依賴。

也可以使用不含版號邏輯的 Make wrapper：

```bash
make build
make start
```

`python scripts/dev/docker/ops.py` 是 `make` targets 使用的實作 wrapper；`make full-reset` 是文件化的 host 破壞性重置入口。

## 第一次啟動

### Windows PowerShell

```powershell
git clone <your-repo-url>
cd aileron
New-Item -ItemType Directory -Force data/turn-config, data/turn-secrets
Copy-Item contracts/browser-connectivity/turn-reachability-profile.json data/turn-config/turn-reachability-profile.json
$env:HOST_PROJECT_ROOT = (Get-Location).Path
docker buildx bake --load local
docker compose -f docker-compose.yml -f docker-compose.bundled-data-services.yml up --remove-orphans --no-build -d
```

### macOS / Linux

```bash
git clone <your-repo-url>
cd aileron
mkdir -p data/turn-config data/turn-secrets
cp contracts/browser-connectivity/turn-reachability-profile.json data/turn-config/turn-reachability-profile.json
export HOST_PROJECT_ROOT="$PWD"
docker buildx bake --load local
docker compose -f docker-compose.yml -f docker-compose.bundled-data-services.yml \
  up --remove-orphans --no-build -d
```

PowerShell 與 macOS／Linux 都必須另外建立 TURN secret bundle；完整檔名、權限與 token
對應規則請見 [Docker 部署 → TURN readiness bundle](./docker.md#turn-readiness-bundle)。

:::info 建置時間
第一次啟動需要建置所有映像，約需 5～10 分鐘。
:::

## 確認 Control Plane 服務狀態

```bash
docker compose -f docker-compose.yml -f docker-compose.bundled-data-services.yml ps
```

建議等到以下服務全部進入 `healthy` 狀態後，再打開前端：

- `postgres`
- `redis`
- `oidc provider`（外部 provider 由部署者負責）
- `workspace-manager`
- `frontend`

另外確認 `turn-readiness-preflight` 已以 `exited (0)` 結束，且 `coturn`、
`connectivity-evidence-gateway`、`connectivity-external-agent` 都在執行中。這些服務未完成
時，Browser access 不會取得可用的 TURN readiness evidence。

:::warning OIDC provider 尚未就緒
若 OIDC provider 尚未完成 Discovery／JWKS 初始化就嘗試登入，前端會顯示 OIDC 認證失敗。
請先確認外部 provider 的 Discovery 與 JWKS 可由 Manager 存取。
:::

## 停止 Control Plane

### Windows PowerShell

```powershell
docker compose -f docker-compose.yml -f docker-compose.bundled-data-services.yml down --remove-orphans
```

### macOS / Linux

```bash
docker compose -f docker-compose.yml -f docker-compose.bundled-data-services.yml down --remove-orphans
```

此操作只停止 root Compose 管理的 control-plane services，並保留 volumes 與持久化平台
資料。動態 Workspace execution plane 仍由 Manager 管理；需要停止個別 Workspace 時，請先
使用 Manager UI 或 API。

## 常用指令

新手最常用到的幾個指令：

| 操作 | 指令 |
|------|------|
| 建置完整本機 image | `docker buildx bake --load local` |
| 啟動 control-plane services | `make start` |
| 非破壞性停止並保留資料 | `make down` |
| 查看 control-plane logs | `docker compose -f docker-compose.yml -f docker-compose.bundled-data-services.yml logs -f` |

本地建置、完整重置、測試重用與查看單一服務日誌等完整指令請見 [Docker 部署 → 常用指令](./docker.md#常用指令)。

## 重置環境

單一 Workspace 的啟動、停止、component restart 與刪除都必須經由 Manager UI 或 API，才能同步 component revision、Runtime credential 與資料庫狀態。`make down` 只停止本機 stack 並保留資料；`make full-reset` 是唯一由 host 執行的破壞性本機環境重置。

### 完整重置

停止 stack、移除平台 volumes，並清除本機持久化資料。

macOS / Linux：

```bash
make full-reset
```

:::danger 完整重置
`full-reset` 會刪除 Aileron 的動態 Workspace、名稱符合 `aileron` 的 volumes／networks 與
`data/` 持久資料，包含 PostgreSQL。它還會分別詢問是否刪除專案 images，以及是否執行
可能影響其他專案未使用資源的全域 `docker system prune --volumes`。執行前請先確認重要
資料已備份並逐項閱讀提示。只有動態 Workspace 與 PostgreSQL 等本機資料均確認清除後，重置才算完成。
:::

## 完整重置後重新啟動

完整重置後，以同一組標準 Docker 命令重新建置與啟動。

### Windows PowerShell

```powershell
docker buildx bake --load local
docker compose -f docker-compose.yml -f docker-compose.bundled-data-services.yml up --remove-orphans --no-build -d
```

### macOS / Linux

```bash
docker buildx bake --load local
docker compose -f docker-compose.yml -f docker-compose.bundled-data-services.yml \
  up --remove-orphans --no-build -d
```

## 本地模組開發

Docker Compose 是 Aileron 預設的本地開發方式。先啟動 control plane，再由 Manager 為每個 Workspace 動態建立 Runtime、Browser 與 Canvas：

```bash
docker buildx bake --load local
docker compose -f docker-compose.yml -f docker-compose.bundled-data-services.yml \
  up --remove-orphans --no-build -d
```

平台模組與動態 Runtime 會掛載對應的開發目錄，修改後通常可透過 reload 反映：

- `./frontend` → `/app`
- `./workspace-manager` → `/workspace-manager`
- `./workspace-runtime` → `/workspace-runtime`
- `./workspace-terminal` → `/workspace-terminal`

只有在 Dockerfile、`docker-bake.hcl`、系統依賴或 dependency lockfile 改動時，才需要重跑 `docker buildx bake --load local`。一般原始碼修改沿用既有 image。動態 Workspace 容器不是 Compose service，不可以 `docker compose restart workspace-runtime` 繞過 Manager。

若要查看個別服務狀態或追蹤變更是否生效，可搭配：

```bash
docker compose -f docker-compose.yml -f docker-compose.bundled-data-services.yml ps
docker compose -f docker-compose.yml -f docker-compose.bundled-data-services.yml logs -f workspace-manager
docker compose -f docker-compose.yml -f docker-compose.bundled-data-services.yml logs -f frontend
docker logs -f workspace-runtime-<workspace-id>
```

:::tip 初次體驗
第一次使用時先由 Bake 建置一次，再由 Compose 啟動。Compose 只管理 control-plane service，Workspace 生命週期仍以 Manager 為準。
:::

## 下一步

- 服務啟動後，可在 [服務位址與帳號](./service-endpoints.md) 查看所有服務網址、預設帳號與健康檢查端點。
- 想了解 Docker 部署架構、環境變數與 volume 掛載細節，請見 [Docker 部署](./docker.md)。
- 若要改用正式或多人協作的部署方式，Kubernetes 是另一種部署路徑，請見 [Kubernetes 部署](./kubernetes.md)。
