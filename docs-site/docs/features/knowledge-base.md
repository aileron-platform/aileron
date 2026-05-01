---
sidebar_position: 5
title: Knowledge Base
---

# Knowledge Base

Knowledge Base 用來保存可重複掛載到 workspace 的團隊知識、專案規範、操作手冊與查詢索引。它不是單一 workspace 的臨時檔案，而是由 Manager 管理、可授權共享，並可依 workspace 設定掛載到 runtime。

## 核心概念

| 概念 | 說明 |
|------|------|
| Knowledge Base | 一個獨立知識庫，包含檔案、wiki、metadata 與維護狀態 |
| Owner | 建立者，具備完整管理權限 |
| Share | 授權其他使用者以 viewer、editor 或 manager 角色存取 |
| Attachment | 將 knowledge base 掛載到指定 workspace 的設定 |
| Mount alias | runtime 內的掛載名稱，最終路徑為 `/knowledge/<alias>` |
| Mode | 掛載模式，`ro` 為唯讀，`rw` 為可讀寫 |

## 儲存位置

Docker 開發環境預設把知識庫放在：

```text
./data/knowledge-bases/<kbId>
```

Manager 容器會透過 `MANAGER_KNOWLEDGE_BASES_DIR=/host/knowledge-bases` 存取這個目錄。Kubernetes 部署則透過 Helm values 的 `kubernetes.knowledgeBases.*` 建立共享 PVC，再由 workspace-operator 將已 attach 的知識庫掛進 runtime Pod。

典型目錄結構：

```text
<kbId>/
├── AGENTS.md
├── purpose.md
├── schema.md
├── wiki/
│   ├── index.md
│   ├── overview.md
│   └── log.md
└── .aileron-kb/
    ├── ingest-cache.json
    ├── ingest-queue.json
    ├── graph-cache.json
    ├── reviews.json
    ├── sources-metadata.json
    └── wiki-index.json
```

## 內容與 Metadata

| 路徑 | 用途 |
|------|------|
| `AGENTS.md` | 提供 agent 使用知識庫時的指令與邊界 |
| `purpose.md` | 描述知識庫目標、適用範圍與維護原則 |
| `schema.md` | 描述內容分類、欄位與命名規則 |
| `wiki/` | 面向人與 agent 的主要知識內容 |
| `.aileron-kb/ingest-cache.json` | 已 ingest 內容的快取狀態 |
| `.aileron-kb/ingest-queue.json` | 待處理 ingest 任務 |
| `.aileron-kb/graph-cache.json` | 知識圖譜或索引快取 |
| `.aileron-kb/reviews.json` | 待審查或已審查項目 |
| `.aileron-kb/sources-metadata.json` | 來源檔案 metadata |
| `.aileron-kb/wiki-index.json` | wiki 頁面索引 |

:::note
`.aileron-kb/` 是系統維護區。除非在除錯索引或修復資料，日常內容維護應優先編輯 `wiki/`、`purpose.md`、`schema.md` 與來源檔案。
:::

## 權限與共享

Knowledge Base 以使用者為中心管理可見範圍。常見角色如下：

| 角色 | 能力 |
|------|------|
| `viewer` | 讀取內容與 attach 資訊 |
| `editor` | 編輯內容，通常可用 `rw` 模式掛載 |
| `manager` | 管理描述、共享、掛載與刪除 |
| `owner` | 建立者，具備最高權限 |

當使用者只有 viewer 權限時，workspace attach 通常應採用 `ro` 模式，避免 runtime 端寫入共享知識內容。

## 掛載到 Workspace

Workspace 可透過設定頁或 API attach knowledge base。掛載後 runtime 內會看到：

```text
/knowledge/<mountAlias>
```

Docker 模式下，Manager 會從 `./data/knowledge-bases/<kbId>` 準備 host volume。Kubernetes 模式下，operator 會用共享 PVC 與 `subPath=<kbId>` 掛載到 runtime Pod。

常見流程：

1. 建立 knowledge base。
2. 上傳或編輯 wiki 與來源檔案。
3. 將 knowledge base attach 到 workspace，設定 alias 與 mode。
4. 重啟或 reconcile runtime，讓掛載狀態生效。
5. 在 agent 或 terminal 中使用 `/knowledge/<alias>` 讀取知識內容。

## API 摘要

Manager API 提供兩組入口：

| 類型 | 路徑 |
|------|------|
| Knowledge Base 管理 | `/api/v1/knowledge-bases` |
| Workspace 掛載管理 | `/api/v1/workspaces/{workspace_id}/knowledge-bases` |

完整端點請參考 [Manager API](/api/manager-api#knowledge-base)。

## 維運檢查

Docker 模式：

```bash
docker compose exec workspace-manager ls -la /host/knowledge-bases
docker compose logs -f workspace-manager
```

Kubernetes 模式：

```bash
kubectl get pvc -n aileron knowledge-bases-pvc
kubectl describe pvc -n aileron knowledge-bases-pvc
```

若 workspace 內看不到 `/knowledge/<alias>`，先確認 attach 設定存在，再確認 runtime 是否已重啟或被 operator reconcile。
