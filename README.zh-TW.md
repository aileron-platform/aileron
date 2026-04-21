# ✈️ Aileron

[English](./README.md)

> **為企業團隊打造的標準化 AI Agent 工作區平台**

Aileron 是一個為企業打造的 AI Agent 工作區平台，協助組織在符合內部規範、權限治理與基礎設施要求的前提下導入 Agent，並大幅簡化使用者建立開發環境、接入工具鏈與開始工作的流程。

文件網站：https://aileron-platform.github.io/aileron/

---

## 願景

Aileron 目標成為企業導入 AI Agents 的標準工作區編排層，讓組織可以在既有規範與治理框架下，穩定擴展 Agent-driven development。

---

## Demo｜產品畫面

| Web Terminal | Agent Login |
|---|---|
| [![Web Terminal Demo](https://img.youtube.com/vi/7ddBnS7sr0M/hqdefault.jpg)](https://youtu.be/7ddBnS7sr0M) | [![Agent Login Demo](https://img.youtube.com/vi/FAUb1JKzJO8/hqdefault.jpg)](https://youtu.be/FAUb1JKzJO8) |
| Create Workspace | Template Center & AI Chat |
| [![Create Workspace Demo](https://img.youtube.com/vi/G8AXGd0_Xwo/hqdefault.jpg)](https://youtu.be/G8AXGd0_Xwo) | [![Template Center & AI Chat Demo](https://img.youtube.com/vi/pl0H4j07IsU/hqdefault.jpg)](https://youtu.be/pl0H4j07IsU) |

---

## 為什麼是 Aileron？

企業在導入 AI Agents 時，真正的挑戰通常不只是模型能力，而是如何讓 Agent 的使用方式符合企業內部規範，同時避免每位使用者都要自行配置複雜的開發環境。

Aileron 的目標是同時解決這兩個問題：

- 讓 Agent 更容易被企業採用
- 讓使用者更容易開始工作

---

## 核心能力

- **符合企業規範的工作區**  
  透過集中設定、模板、權限與標準化能力，讓 Agent 使用方式更容易符合企業內部規範。

- **簡化環境建立**  
  使用者不需要從零組裝本機開發環境，即可快速進入可工作的 Agent Workspace。

- **標準化工具鏈與工作流**  
  將 MCP、Slash Commands、工作流程與整合能力平台化，降低團隊間差異。

- **整合式工作介面**  
  在同一個工作區中整合 Chat Panel、檔案管理、Git 與 Web Terminal，降低操作切換成本。

- **企業級驗證與治理**  
  透過 Keycloak 與團隊治理能力，整合 SSO、角色權限與平台控管需求。

- **OpenSpec 內建工作流**  
  OpenSpec 不只是外部文件，而是工作區中的原生能力，可直接在工作區中瀏覽與操作。

---

## Agent 支援狀態

目前 Aileron 以 **Claude Code** 提供最完整的整合體驗，並持續擴展其他 Agent 能力。

- `Claude Code`：目前最完整
- `OpenCode`：持續擴充中
- `Gemini`：持續擴充中
- `Codex`：持續擴充中

---

## 技術架構

Aileron 採用現代化微服務架構：

- **Frontend**：React 管理介面、Workspace Shell 與 Web Terminal
- **Workspace Manager**：負責編排與生命週期管理的 FastAPI 服務
- **Workspace Runtime**：提供 Agent 執行環境的容器化執行層
- **Workspace Terminal**：Go 實作的終端與 WebSocket 服務
- **Workspace Operator**：Kubernetes 動態工作區佈建元件
- **Agent Tools**：整合 Claude Code 與相關工作區工具能力
- **Infrastructure**：
  - **PostgreSQL**：關聯式資料儲存
  - **Redis**：快取與任務協調
  - **Keycloak**：身分驗證與存取控制
  - **Draw.io / Flower**：圖表與任務監控

---

## 快速開始

### 需求

- Docker
- Docker Compose v2
- 建議至少 **8GB RAM**

### 正式 Host CLI

`python scripts/dev/docker/ops.py` 是目前正式的 host-side CLI，作為本機 Docker 操作的跨平台標準入口，用來統一：

- stack 啟動與停止
- workspace 清理與完整清理
- runtime / manager container 測試觸發

第一次操作前，建議先查看可用子命令與範例：

```bash
python scripts/dev/docker/ops.py --help
python scripts/dev/docker/ops.py test --help
```

### 啟動 Stack

#### Windows PowerShell

```powershell
git clone <your-repo-url>
cd aileron
python .\scripts\dev\docker\ops.py up --build
```

#### macOS / Linux

```bash
git clone <your-repo-url>
cd aileron
python scripts/dev/docker/ops.py up --build
```

> 首次建置可能需要 **5–10 分鐘**。

### 健康檢查

```bash
docker compose ps
```

等到所有服務狀態顯示為 `healthy` 再開始操作。Keycloak 啟動通常需要約 1 分鐘。

建議至少確認以下服務：

- `postgres`
- `redis`
- `keycloak`
- `workspace-manager`
- `frontend`

若 `keycloak` 尚未完成初始化，前端可能出現 OIDC 驗證錯誤；請等到 `healthy` 後再登入。

### 停止 Stack

#### Windows PowerShell

```powershell
python .\scripts\dev\docker\ops.py down
```

#### macOS / Linux

```bash
python scripts/dev/docker/ops.py down
```

此操作會停止本機 stack，但保留 volumes 與既有持久化資料。

### 清理流程

日常重置 workspace 時優先使用 `cleanup-workspaces`；只有在需要完整重建本機環境時才使用 `cleanup`。

#### Workspace 清理

只移除動態建立的 workspace 容器與相關暫時性資源，保留主要平台服務與資料庫。

Windows PowerShell：

```powershell
python .\scripts\dev\docker\ops.py cleanup-workspaces
```

macOS / Linux：

```bash
python scripts/dev/docker/ops.py cleanup-workspaces
```

若偏好平台對應 wrapper，也可使用：

```powershell
.\scripts\dev\docker\cleanup-workspaces.ps1
```

```bash
./scripts/dev/docker/cleanup-workspaces.sh
```

#### 完整清理

停止 stack、移除平台 volumes 與本機產生資料，將開發環境重置為乾淨狀態。

Windows PowerShell：

```powershell
python .\scripts\dev\docker\ops.py cleanup
```

macOS / Linux：

```bash
python scripts/dev/docker/ops.py cleanup
```

若偏好平台對應 wrapper，也可使用：

```powershell
.\scripts\dev\docker\cleanup.ps1
```

```bash
./scripts/dev/docker/cleanup.sh
```

> `cleanup` 屬於破壞性操作，會移除 Docker volumes 與持久化平台資料，包含 PostgreSQL 資料。

### 清理後重新啟動

不論是 `cleanup-workspaces` 或 `cleanup`，清理完成後都可用正式 CLI 重新啟動：

#### Windows PowerShell

```powershell
python .\scripts\dev\docker\ops.py up --build
```

#### macOS / Linux

```bash
python scripts/dev/docker/ops.py up --build
```

---

## 服務入口與預設帳號

| 服務 | URL | Username | Password |
|---|---|---:|---:|
| Aileron Frontend | http://localhost:8082 | admin | admin123 |
| Keycloak Admin | http://localhost:8080/admin | admin | admin |
| Manager API | http://localhost:3001 | - | - |
| Flower | http://localhost:5555 | - | - |
| Draw.io | http://localhost:8083 | - | - |

---

## 部署模式

### Docker Compose

適合本機開發與小型團隊：

- 使用 `docker compose` 啟動完整平台
- 提供快速、可重複的工作區建立方式
- 降低首次體驗與本機環境準備成本

### Kubernetes

適合正式環境與可擴展部署：

- 核心平台服務透過 **Helm** 部署
- 動態工作區資源由 **workspace-operator** 管理

```bash
helm lint helm/aileron
helm template test-release helm/aileron

helm install aileron ./helm/aileron \
  --namespace aileron \
  --create-namespace
```

#### Knowledge Base 儲存需求

Kubernetes 模式下，Knowledge Base 會多一塊共享儲存：

- `kubernetes.knowledgeBases.pvcName` 會建立專用的 `knowledge-bases-pvc`
- `workspace-manager` 會把這顆 PVC 掛到 `/host/knowledge-bases`
- `workspace-operator` 會把每個 attach 的 KB 以 `subPath=<kbId>` 掛進 runtime Pod 的 `/knowledge/<alias>`

本機單節點開發預設使用：

```yaml
kubernetes:
  knowledgeBases:
    storageClassName: hostpath
```

這是 dev fallback，不代表真正的多節點 RWX 共用儲存。

正式環境請改用共享型 RWX StorageClass，例如 NFS：

```bash
helm upgrade --install aileron ./helm/aileron \
  --namespace aileron \
  --create-namespace \
  -f helm/values-rke.yaml
```

在 Kubernetes 啟用 Knowledge Base 前，至少確認：

- 叢集可以提供 `ReadWriteMany`，或你明確接受單節點 `hostpath` fallback
- `knowledge-bases-pvc` 狀態為 `Bound`
- `workspace-manager` Pod 已掛上 `/host/knowledge-bases`
- operator 建立的 runtime Pod 能透過 `knowledge-bases` volume 掛出 `/knowledge/<alias>`

### Public Domain Routing

若需公開網域對外提供服務，需額外設定：

- `publicRouting.*` Helm values
- frontend / workspace-manager / keycloak 的固定 DNS
- workspace runtime / browser / nextjs 的 wildcard 或等效 DNS
- TLS 憑證

---

## 常用指令

| 任務 | 指令 |
|---|---|
| Start stack | `python scripts/dev/docker/ops.py up` |
| Rebuild and start stack | `python scripts/dev/docker/ops.py up --build` |
| View manager logs | `docker compose logs -f workspace-manager` |
| View runtime logs | `docker compose logs -f workspace-runtime` |
| Stop services | `python scripts/dev/docker/ops.py down` |
| Cleanup workspaces | `python scripts/dev/docker/ops.py cleanup-workspaces` |
| Full reset（破壞性操作） | `python scripts/dev/docker/ops.py cleanup` |

> `python scripts/dev/docker/ops.py` 是正式的跨平台 CLI 入口，適用於啟動、停止、清理與測試操作。
>
> 日常重置 workspace 請優先使用 `cleanup-workspaces`；只有需要刪除持久化資料與 volumes 時才使用 `cleanup`。
>
> macOS / Linux 的 legacy wrapper：`./scripts/dev/docker/cleanup.sh`、`./scripts/dev/docker/cleanup-workspaces.sh`
>
> Windows PowerShell 的 legacy wrapper：`.\scripts\dev\docker\cleanup.ps1`、`.\scripts\dev\docker\cleanup-workspaces.ps1`

---

## 專案結構

```text
aileron/
├── frontend/              # React frontend
├── workspace-manager/     # Orchestration service (FastAPI)
├── workspace-runtime/     # Secure agent runtime
├── workspace-terminal/    # Terminal / WebSocket service
├── workspace-operator/    # Kubernetes workspace operator
├── workspace-chrome/      # Browser integration module
├── workspace-nextjs/      # Frontend integration module
├── keycloak-realm/        # IAM configuration
├── scripts/               # Dev / test / ops scripts
├── openspec/              # OpenSpec changes and specs
├── data/                  # Local persistence (gitignored)
└── helm/                  # Kubernetes deployment charts
```

---

## 測試

本專案提供 container-based 測試入口，建議優先使用：

```bash
make test-all
make test-frontend
make test-manager
make test-runtime
```

也可使用既有腳本：

```bash
python scripts/dev/docker/ops.py test manager
python scripts/dev/docker/ops.py test runtime
```

或使用 Makefile 的跨平台便利入口：

```bash
make test-manager-cli
make test-runtime-cli
```

---

## 專案狀態

Aileron 目前仍在快速演進中，功能、文件與整體體驗會持續調整。歡迎透過 issue、PR 與實際使用回饋一起完善這個平台。

---

## 授權

本專案採用 **Apache License 2.0**。

詳情請參考 [LICENSE](./LICENSE)。
