---
sidebar_position: 5
title: Team Wiki Knowledge Base
---

# Team Wiki Knowledge Base

Team Wiki Knowledge Base 將知識庫作為團隊內部 wiki 管理。每個知識庫會維持固定目錄結構，讓來源資料、wiki 內容、報告、索引狀態與選用的 Git 版本控制能放在同一個知識庫根目錄中。

## 目錄結構

新建知識庫會初始化下列目錄與檔案：

| 路徑 | 用途 |
|------|------|
| `raw/` | 保存原始來源檔案，例如 Markdown、文字、PDF、圖片、Office 檔或網頁剪貼內容 |
| `normalized/` | 保存 manager 可直接標準化的文字來源；PDF 等複雜格式由 wiki index job 的 agent 處理 |
| `wiki/` | 團隊 wiki 主內容，包含 `index.md`、`overview.md`、`log.md` 與 source summary |
| `reports/` | 保存 lint report 與 graph snapshot 等可審閱報告 |
| `.aileron-kb/` | 保存知識庫內部狀態，例如 ingest queue、source hash cache 與 job metadata |
| `AGENTS.md`、`purpose.md`、`schema.md` | 提供 agent 寫入 wiki 時必須遵守的知識庫規則、用途與 frontmatter schema |

## 來源與 Wiki Index

知識庫支援多種來源輸入：

- 檔案上傳會保存到 `raw/`，並依格式建立 provenance 與 hash metadata。
- Markdown、純文字、CSV 與可直接解析的 Office 文件會產生第一版 `normalized/` 內容。
- PDF、圖片與其他需要 OCR、caption 或版面理解的格式只由 manager 保存原始檔與 metadata，後續交給 wiki index job 的 agent 讀取與整理。
- 網頁剪貼可匯入 Markdown 內容與相關資產，資產保存於 `raw/assets/`。

Wiki index 會讀取來源資料、`purpose.md`、`schema.md`、`wiki/index.md` 與 `wiki/overview.md`，再更新 wiki 頁面、source summary、`wiki/log.md` 與索引狀態。預設會依 source hash 跳過未變更來源；需要重跑時可用 force index。

## 排程條件

Wiki index 可以由排程中心建立週期性任務。建立排程前必須符合下列條件：

- 目標 workspace 存在且使用者對 workspace 具有 editor 以上權限。
- 目標知識庫存在且使用者對知識庫具有 editor 以上權限。
- 知識庫已 share 或 attach 到該 workspace。
- Attachment 模式必須是 `rw`，唯讀 attachment 只能查閱，不能建立 wiki index 排程。

排程 job metadata 會標示 `jobType = knowledge_base.wiki_index` 與 `knowledgeBaseId`。執行前 manager 會重新驗證知識庫、workspace attachment、權限與唯讀狀態，避免排程建立後權限被收回仍可寫入 wiki。

## 選用 Git 與 Git LFS

Git 版本控制是每個知識庫的選項，不是必要條件。未啟用 Git 時，知識庫仍可 ingest、query、lint 與瀏覽 graph；Git API 會回傳版本控制未啟用的錯誤。

啟用 Git 後，知識庫支援：

- repository status、檔案變更、stage、unstage、discard 與 commit。
- 變更記錄、commit files、diff 與指定 revision 的 blob 檢視。
- branch、remote、fetch、pull、push、revert 與 rollback。
- wiki index 或 query save-to-wiki 完成後自動 commit，execution metadata 會記錄 changed files 與 commit id。

知識庫不提供 worktree 操作。大型原始檔建議啟用 Git LFS，系統會建立 `.gitattributes`，將 `raw/` 下常見大型格式交給 LFS tracking。

## 圖形化關聯圖

每個知識庫都有 Graph tab，用來視覺化 wiki 頁面與來源之間的關係。Graph 會掃描 `wiki/**/*.md`，解析 frontmatter、page type、sources 與 wikilinks，並建立 nodes / edges。

關聯權重會綜合下列 signals：

- Direct wikilink：頁面明確連到另一個 wiki 頁面。
- Source overlap：多個頁面引用同一批來源資料。
- Common neighbor / Adamic-Adar：頁面在圖上有共同鄰居。
- Type affinity：頁面類型之間的關聯，例如 concept、source、decision、question。

前端會依 page type 顯示 node 顏色，依 link count 或 relevance degree 調整 node size，並依 edge weight 調整 edge 粗細。Graph 支援搜尋、zoom、fit-to-screen、hover/select highlight、edge reason 檢視與 node click 開啟 wiki page preview。
