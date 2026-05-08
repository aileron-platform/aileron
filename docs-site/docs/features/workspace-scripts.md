---
sidebar_position: 6
title: Workspace Scripts
---

# Workspace Scripts

Workspace scripts 用來把輔助腳本、初始化腳本與團隊常用操作放進 workspace。它和專案程式碼分開管理，預設掛載到 runtime 的 `/scripts`。

## 啟動入口分工

| 場景 | 建議入口 |
|------|----------|
| 啟動完整本機 stack | `python scripts/dev/docker/ops.py up` |
| 重建後啟動完整 stack | `python scripts/dev/docker/ops.py up --build` |
| 停止 stack | `python scripts/dev/docker/ops.py down` |
| 清理 workspace 資源 | `python scripts/dev/docker/ops.py cleanup-workspaces` |
| 完整清理 | `python scripts/dev/docker/ops.py cleanup` |

`ops.py` 是目前正式的跨平台 host-side CLI，所有啟動、停止與清理流程都以 `ops.py` 為準。

## Runtime 啟動腳本

Docker Compose 的 default runtime 使用：

```yaml
command: /workspace-runtime/start_services.sh
```

這個腳本負責啟動 runtime 內的主要服務。每個 workspace 的自訂初始化腳本會由 Manager 產生或安裝到資料目錄，再透過 volume 掛載給 runtime 使用。

## 掛載位置

Docker 開發環境預設使用：

| Host path | Runtime path | 說明 |
|-----------|--------------|------|
| `./data/workspace-scripts/default-workspace` | `/scripts` | default workspace 的腳本目錄 |
| `./data/init-scripts/<workspaceId>` | runtime 初始化來源 | workspace 建立或重建時使用的初始化腳本 |
| `./workspace-runtime/scripts` | `/workspace-runtime/scripts` | runtime 服務本身的工具與啟動腳本 |

Manager 會透過以下環境變數解析 host 與容器內路徑：

| 變數 | 預設值 |
|------|--------|
| `HOST_WORKSPACE_SCRIPTS_DIR` | `./data/workspace-scripts` |
| `MANAGER_WORKSPACE_SCRIPTS_DIR` | `/host/workspace-scripts` |
| `INIT_SCRIPTS_ROOT` | `/data/init-scripts` |

## 支援的檔案型態

Workspace scripts 是檔案集合，不限制只能放單一語言。常見內容包含：

| 副檔名 | 用途 |
|--------|------|
| `.sh` | Linux/macOS shell 腳本，適合 runtime 內執行 |
| `.ps1` | PowerShell 腳本，適合 Windows 操作說明或跨平台內容 |
| `.md` | 操作說明或 runbook |
| `.json` / `.yaml` | 設定檔、範例 payload、工具設定 |

:::tip
runtime 容器以 Linux 為主，實際自動啟動或 runtime 內執行的腳本應優先使用 `.sh`。`.ps1` 適合 host-side Windows 操作或跨平台操作說明。
:::

## Runtime Script API

Runtime API 提供 `/api/v1/scripts` 檔案集合端點，可讀寫、搬移、複製與刪除腳本內容。完整端點請參考 [Runtime API](/api/runtime-api#scripts)。

常見用途：

- 在 UI 中瀏覽 workspace scripts tree。
- 編輯 shell script 或 runbook。
- 讓 agent 在 `/scripts` 下找到團隊標準操作。

## 建議做法

- 需要被 runtime 自動執行或 agent 使用的腳本，放在 `/scripts`。
- 需要管理整個 Docker stack 時，使用 `python scripts/dev/docker/ops.py`。
- 需要清理舊 workspace 資源時，可使用 `ops.py cleanup-workspaces`，或在特定 shell 環境使用 legacy `.sh` / `.ps1` wrapper。
- 腳本內容應避免寫入機密；需要 token 或密碼時，透過環境變數或平台設定注入。
