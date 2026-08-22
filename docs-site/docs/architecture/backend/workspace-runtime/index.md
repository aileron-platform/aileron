---
title: Workspace Runtime
---

# Workspace Runtime

## 概覽

Workspace Runtime 是運行在每個開發工作區容器內的服務，提供 Agent 執行整合、檔案管理與 local history、Git、Thread event WebSocket 及 Automation 執行等功能。Claude Code、Codex 與 OpenCode 都透過這個 runtime 執行。

## 核心功能

### Agent 執行整合

- **設定管理**：Claude Code、Codex、OpenCode 設定的讀取與更新
- **Hooks 管理**：自訂 hooks 設定與管理
- **MCP 整合**：MCP 伺服器設定管理
- **子代理管理**：Claude Code 子代理設定
- **斜線命令**：自訂斜線命令管理

從前端送出訊息、三種 Agent 事件正規化、Thread 持久化、WebSocket 到前端 timeline 的完整邊界，請見 [AI Chat 前後端架構](/architecture/overview/ai-chat)。

### 檔案系統管理

- **檔案操作**：目錄樹、搜尋、讀寫、上傳、複製、搬移、archive 與 extract
- **Local history**：列出檔案異動歷史並還原指定版本
- **版本控制**：Git 整合和操作
- **Knowledge Base**：將Workspace attachment以`/knowledge/{alias}`零複製唯讀提供；
  Runtime不能把KB切換成可寫模式

### Automation 執行

- **Claim／complete**：以instance-scoped control token向Manager claim工作並回報結果
- **Lease／heartbeat**：執行期間更新lease，讓Manager可辨識失聯execution
- **狀態保存**：Automation execution與Thread state保存在Workspace-scoped Runtime PostgreSQL schema

### WebSocket 通訊

- **Thread event channel**：向前端推送Thread invalidation與執行狀態事件
- **重新連線**：Frontend在斷線重連後重新取得authoritative timeline
- **認證**：Browser以WebSocket subprotocol攜帶Bearer credential，不把token放入URL

### 授權與 Generation

- **Action gate**：HTTP 與 WebSocket 依封閉 route inventory 映射成 `runtime_read`、`runtime_write`、
  `workspace_settings`、`terminal`、`agent`、`automation` 或 `browser_automation`。一般使用者
  request 會把原始 bearer credential、Workspace、instance 與 exact action 送到 Manager
  `/runtime-access` 逐次驗證；Reader 只允許安全 read projection，其他 action 需要 Manager、
  Owner 或 Platform Admin
- **Instance fence**：驗證`runtimeInstanceId`、Runtime lifecycle與access observed
  revision；Manager無法確認時fail closed。KB mount observed revision只由KB相依操作檢查，
  不封鎖一般Runtime API
- **共置Terminal**：Terminal與agent都在Runtime workload內；Runtime identity消失即
  同時fence這些程序
- **Signed drain 與 pairing**：只接受 Manager 的短效 Ed25519 assertion，並驗證
  audience、user／Workspace／instance、generation、action、期限、single-use `jti` 與 replay state

Runtime route classifier 使用 machine-readable route × method inventory。精確敏感 route 與敏感 wildcard 優先於一般 mutation／read；Claude、Codex、OpenCode raw settings 與 MCP env／headers 都歸入 `workspace_settings`。未知或多重命中、Manager timeout／不可達時，middleware 在呼叫 handler 前拒絕。

Direct／group share、群組成員、帳號狀態、Owner 或 Platform Admin access 發生變更時，Manager 提升 generation；Runtime 立即拒絕已失效的 internal assertion，並終止不再允許的 Terminal、Agent、Automation、Browser 與其他 execution session。Runtime 不接受由前端傳入的角色或 operation list。

完整的component revision收斂、drain與fencing流程請見[Execution-Plane 生命週期與安全機制](/architecture/overview/execution-plane)。

## Agent 設定檔案模組

Claude Code、Codex、OpenCode 三種 agent 的設定檔讀寫邏輯，由 `workspace-runtime/app/modules/claude_code/`（Claude 專用）與 `workspace-runtime/app/modules/cli_settings/`（Claude／Codex／OpenCode 共用）的路徑解析模組負責。各功能對應的來源模組：

| 功能 | 來源模組 |
| --- | --- |
| CLAUDE.md、Settings、Memory 附件、Output Styles、Plugins／Marketplace | `cli_settings/agents_md`、`claude_code/settings`、`claude_code/memory`、`claude_code/output_styles`、`claude_code/plugins` |
| MCP Servers（三種 agent 共用） | `claude_code/mcp`、`cli_settings/mcp` |
| Hooks（Claude 專用路徑） | `claude_code/hooks` |
| Skills（三種 agent 共用） | `cli_settings/skills` |
| Subagents、Slash Commands（依 agent 掛載共用或專用 router） | `cli_settings/subagents`、`cli_settings/slash_commands`、`claude_code/slash_commands` |
| Codex 專屬（Config、Rules、Hooks、Apps、Memories、Plugins、Subagents、Prompts、Managed Requirements） | `cli_settings/codex/settings.py::CodexAgentSettings`；共用路徑 contract 位於 `cli_settings/user_scope/paths.py` |

使用者可見的檔案位置對照表請見 [Agent 設定檔案位置與 Scope 對照](/features/workspace/agent-settings/)。

Claude Code 的 Hooks 與 Slash Commands 走專屬的 `claude_code/hooks`、`claude_code/slash_commands` 模組；CLAUDE.md、Subagents 與 Skills 則分別使用 `cli_settings/agents_md`、`cli_settings/subagents` 與 `cli_settings/skills`。Codex 的專屬資源由 `cli_settings/codex` 統一提供。

## 技術架構

| 元件 | 技術 |
|------|------|
| Web 框架 | FastAPI |
| 即時通訊 | Thread event WebSocket |
| Runtime state | PostgreSQL + SQLAlchemy |
| AI 客戶端 | Claude Agent SDK、Codex SDK、OpenCode ACP |
| 版本控制 | GitPython |

## Image Variants

Workspace Runtime 支援兩種 base image flavor：

| Flavor | 適用場景 | 說明 |
|--------|----------|------|
| `lite` | 預設的 agent workspace | 保留 agent CLI、Python、Node.js、Git、Docker CLI 與常用 shell 工具，適合平台預設工作區 |
| `java` | 需要 Java / Maven 的 workspace | 以 `lite` 為底，額外安裝 Eclipse Temurin JDK 21 與 Apache Maven 3.9.x |

`base-images/lite` 會包含平台執行所需的基本工具：

- Shell 與建置工具：`bash`、`build-essential`、`make`、`pkg-config`
- 版本控制與檔案工具：`git`、`git-lfs`、`ripgrep`、`fd`、`rsync`
- 語言與套件基礎：Python 3、Node.js、`pnpm`、`uv`
- 系統工具：`curl`、`wget`、`jq`、`sudo`、`openssh-client`

`base-images/lite` 不包含 Java runtime / JDK，也不包含 Go compiler 或 `/usr/local/go`。Java 開發需求應使用 `java` flavor（`base-images/java21`）。

`terminal-service` 是 Go binary，但 Go toolchain 不會進入 runtime image。`workspace-runtime/Dockerfile` 會使用 `docker-bake.hcl` 指定的 Go builder stage 編譯 binary，再把 `/opt/terminal-service/bin/terminal-service` 複製到 `development`、`production` 與 `kubernetes` image。

Flavor與部署target是兩個不同維度。Docker單機使用`development`／`production` target；
Kubernetes與OCP必須使用額外的`kubernetes` target及`${RELEASE_TAG}-kubernetes` tag。後者在
build-time完成dependency install，以numeric non-root預設使用者啟動，支援平台注入的
arbitrary UID與read-only root filesystem，且不啟動`sshd`或掛載Docker socket。

單獨建置 `lite` flavor：

```bash
make build-runtime-base
make build-workspace-runtime
```

`lite` 與 `java` 兩種 flavor 由 root Bake target 統一建置：

```bash
docker buildx bake --load \
  runtime-base-lite runtime-base-java \
  workspace-runtime-lite workspace-runtime-java
```

Python、Node.js、npm、pnpm、uv、Claude Code、Codex、OpenCode 與 Playwright CLI 的版號都只定義在 root `docker-bake.hcl`。Runtime Dockerfile 不提供數字版號預設值；完整責任分工請見 [Docker 部署的版本與依賴責任](/installation/docker#版本與依賴責任)。

## HOME 與持久化契約

Runtime 直接持久化標準使用者 HOME，不再另外建立第二層持久化根目錄：

| 部署模式 | HOME | 持久化來源 |
| --- | --- | --- |
| Docker | `/home/developer` | `HOST_RUNTIME_HOME_DIR/<workspace-id>` 直接 bind mount |
| Kubernetes | `/home/developer` | `workspace-runtime-home-pvc-<workspace-id>` 直接 PVC mount |

完整 HOME 會保存 Claude、Codex、OpenCode 登入與設定、XDG data/state、Maven
`${HOME}/.m2` 及使用者自行安裝的工具。標準衍生路徑如下：

| 用途 | 路徑 |
| --- | --- |
| Codex | `${HOME}/.codex` |
| XDG config | `${HOME}/.config` |
| XDG data | `${HOME}/.local/share` |
| XDG state | `${HOME}/.local/state` |
| Marketplace operation journal | `${HOME}/.local/state/aileron/marketplace-operations` |

`${HOME}/.codex/tmp` 是程序暫存例外：Docker 使用 tmpfs，Kubernetes 使用 16 MiB memory
`emptyDir`，兩者都掛在 `tmp` 層而不是 `tmp/arg0`。如此 Codex 可由目前 Runtime UID
建立並調整 `arg0` helper 目錄；`${HOME}/.codex` 的其他狀態仍完整持久化。

映像提供的可執行檔不寫入 HOME：uv、Node.js、npm、pnpm 與 Claude Code 位於系統
路徑；Codex／Playwright CLI 位於 `/opt/aileron/npm`；OpenCode 位於
`/opt/aileron/bin`。因此空白的新 HOME、Docker container 重建或 Kubernetes Pod
重建都不會遮蔽映像內工具。

## 目錄結構

Workspace Runtime 使用垂直 domain module；每個 module 擁有自己的 domain ownership，
水平 `services`、`models` 等責任放回對應 owning domain。完整目錄範本、seam、interface
與測試規則請見
[後端領域模組架構](/architecture/backend/)及
[Python 模組與檔名規則](/reference/python-module-naming)。

Thread lifecycle、Codex Agent Settings、Workspace File／Version Control operation
seam，以及 User Copy typed contract 的 owning module 與禁止穿透規則，請見
[後端深層模組與跨執行面契約](/architecture/backend/)。版本控制的 target、lock scope 與
Repository Setup interface 請見[共用版本控制與 Repository Setup](/architecture/overview/version-control)。

## 環境變數

| 變數名 | 預設值 | 說明 |
|--------|--------|------|
| `AILERON_WORKSPACE_ID` | 必填 | 工作區識別碼 |
| `AILERON_WORKSPACE_PATH` | 必填 | 工作區路徑 |
| `AILERON_RUNTIME_DATABASE_CONNECTION_FILE` | 必填 | current Workspace generation 的 Runtime database connection 唯讀 Secret 檔案 |
| `AILERON_RUNTIME_CONTROL_TOKEN_FILE` | 必填 | current Runtime instance 呼叫 Manager control API 的 token 唯讀 Secret 檔案 |
| `HOME` | `/home/developer` | Docker 與 Kubernetes 直接掛載並完整持久化的標準使用者 HOME |
| `CODEX_HOME` | `${HOME}/.codex` | Codex 設定、登入與 session 目錄 |
| `XDG_CONFIG_HOME` | `${HOME}/.config` | OpenCode 等工具的標準設定目錄 |
| `XDG_DATA_HOME` | `${HOME}/.local/share` | OpenCode 等工具的標準資料目錄 |
| `XDG_STATE_HOME` | `${HOME}/.local/state` | Runtime bootstrap 與應用程式狀態根目錄 |
| `MARKETPLACE_OPERATION_JOURNAL_DIR` | `${XDG_STATE_HOME}/aileron/marketplace-operations` | Marketplace operation journal、target-client mutation gate 與 user-copy transactional recovery 目錄 |
| `AILERON_MANAGER_INTERNAL_URL` | 必填 | Workspace Manager 內部 Service URL |
| `AILERON_PLATFORM_PUBLIC_ORIGIN` | 必填 | 唯一精確平台公開 Origin |
| `AILERON_RUNTIME_INSTANCE_ID` | — | current execution-plane generation UUID |
| `AILERON_RUNTIME_ACCESS_REVISION` | — | 此 Runtime 已套用的 access revision |
| `AILERON_KB_MOUNT_REVISION` | — | 此 Runtime 已套用的 KB mount revision |
| `MANAGER_ACCESS_TIMEOUT_SECONDS` | `5` | Runtime向Manager驗證action的timeout |
| `AILERON_RUNTIME_ASSERTION_PUBLIC_KEY_SET_FILE` | 必填 | Manager assertion public JWKS 檔案 |
| `AILERON_RUNTIME_ASSERTION_ISSUER` | 必填 | assertion 預期 issuer |

Browser、Canvas 與 worktree 的平台欄位同樣使用 `AILERON_*`。所有 Secret 只透過絕對路徑的唯讀檔案交付；Workspace 使用者環境不得使用 `AILERON_*` 前綴。

此目錄只保存 target-client mutation 的 operation journal 與 user-copy 交易復原資料，不是安裝狀態。操作成功後，Runtime 不保留 installation、ownership、provenance、baseline、drift、reconcile、uninstall 或 cleanup lifecycle。

:::note Agent Credentials
Claude Code、Codex、OpenCode 所需的 API key、token 與登入狀態應透過前端設定頁面動態注入，不應寫死在容器環境變數中。
:::

## WebSocket 事件

Thread WebSocket不把token放進URL。Browser沿用Terminal的subprotocol模式，送出
`aileron-thread-v1`及`bearer.<base64url(token)>`；Runtime只選擇並echo application
protocol，不echo credential protocol，再以還原的Bearer token執行`runtime_read`驗證。
非browser client也可在upgrade直接使用`Authorization: Bearer <token>`。query token、
兩種credential同時出現、格式錯誤及internal token都會fail closed。完整端點與close
code語意請參考[Runtime API](/api/runtime-api#websocket)。

## 本地開發

```bash
docker buildx bake --load local
docker compose up --remove-orphans --no-build -d
```

root Compose 只啟動 control plane。登入後透過 Manager 建立或啟動 Workspace，Manager 才會建立對應的 Runtime generation。Docker 開發模式會將 `./workspace-runtime` 掛載到動態 Runtime 內的 `/workspace-runtime`，因此程式碼調整通常能透過 reload 機制反映。

動態Runtime不是Compose service，不要使用`docker compose restart workspace-runtime`。請經由Manager的Runtime component restart只替換Runtime／Terminal；Browser與Canvas使用各自的component restart。stop保留工作目錄與持久資料，delete才清除。

Manager 建立每個 Workspace Runtime container 時，固定使用 image 內的啟動腳本：

```yaml
command: "/start_services.sh"
working_dir: "/workspace-runtime"
```

每個 Workspace 的自訂初始化腳本由 Manager 產生或安裝到資料目錄，再掛載給當前 Runtime generation；root Compose 不會啟動固定的 default Runtime。

## 測試

```bash
docker buildx bake --load workspace-runtime-lite

docker compose -f workspace-runtime/docker-compose.test.yml \
  run --rm workspace-runtime-test \
  bash -lc 'uv sync --all-extras && uv run pytest tests -v'

docker compose -f workspace-runtime/docker-compose.test.yml \
  run --rm workspace-runtime-test \
  bash -lc 'uv sync --all-extras && \
    uv run ruff check app tests && \
    uv run black --check app tests && \
    uv run mypy app && \
    uv run vulture'
```

## 可觀測性

Runtime 提供 `GET /health` 作為服務健康檢查，並以 structured application log 記錄啟動、
Agent、Automation 與 API 錯誤。資源統計由 `ResourceTelemetryReporter` 產生低敏感度的
activity 與 capacity observation；它不是檔案監控事件串流，也不傳送 prompt、內容、檔名或路徑。
CPU、記憶體、磁碟、network I/O 與容器／Pod 資源仍由部署平台的監控能力觀察。完整的
Reporter、outbox、Manager ingestion、deduplication 與 privacy contract 請見
[平台資源與 Runtime Telemetry 架構](/architecture/overview/platform-resource-observability)。

## API 端點

| 端點 | 說明 |
|------|------|
| `GET /health` | 健康檢查 |
| `GET /api/v1/files/*` | 檔案管理 |
| `GET /api/v1/workspaces/{workspace_id}/claude-code/settings` | Claude Code 設定 |
| `PUT /api/v1/workspaces/{workspace_id}/claude-code/settings` | 更新 Claude Code 設定 |
| `GET /api/v1/threads` | 列出 AI Chat threads |
| `POST /api/v1/threads/draft` | 建立 draft thread |
| `POST /api/v1/threads/{thread_id}/submit` | 送出 thread 並啟動 agent |
| `POST /api/v1/threads/{thread_id}/messages` | 追加訊息 |
| `POST /api/v1/threads/{thread_id}/questions/{message_id}/answer` | 回答互動式問題 |
| `WS /api/v1/threads/events` | Thread 事件 WebSocket |
| `GET /api/v1/workspaces/{workspace_id}/version-control/status` | Git status |
| `GET /api/v1/workspaces/{workspace_id}/version-control/commits` | Git commits |

## 容量探測與回報

`CapacityProbe` 只量測 Workspace 專案根目錄與 `/home/developer`，不追蹤 symlink，也不把
`/knowledge/<alias>` 納入 Workspace Project Data 或 Runtime HOME。`ResourceTelemetryReporter`
在 startup、每 15 分鐘、檔案 mutation 後的 delayed probe 與 shutdown drain 管理 observation；
事件先寫入 durable outbox，再以 at-least-once batch 呼叫 Manager：

```text
POST /api/v1/internal/workspaces/{workspace_id}/resource-telemetry/batches
```

Probe 具 bounded timeout 與 non-overlap lock。probe、outbox 或 transport failure 會保留
retry 資料並記錄 telemetry metric，不阻擋 File、Git、Thread、Automation 或其他 Runtime
operation。跨執行面資料流與 payload 欄位請見[平台資源與 Runtime Telemetry 架構](/architecture/overview/platform-resource-observability)。
