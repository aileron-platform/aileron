---
status: accepted
---

# 將應用中心收斂為 Managed Plugins

Aileron Application Center 只呈現 Aileron Managed Registry working tree 中的 Managed Plugins。外部 Git、ZIP 或 Universal Directory 項目只能在 `Import Plugin` 流程中成為候選並複製進 registry；Aileron 不再註冊、追蹤、同步或直接安裝完整 Marketplace Source。此決策取代 ADR-0003 的 Source Registration 與 Vendoring 模型。

## Considered Options

- 保留 `Add Marketplace` 與外部 catalog lifecycle：能直接追蹤及安裝 upstream，但形成第二種 catalog item、來源狀態與移除語意。
- 只隱藏 `Add Marketplace` UI：短期改動小，但留下無產品入口的 routes、persistence 與安裝分支。
- 只保留 Managed Plugins：建立與匯入得到相同產品物件，Application Center 維持單一模型，因此採用此方案。

## Consequences

- 產品操作使用 `Import Plugin`、`Create Plugin`、`Save`、`Delete Plugin`、`Install and Enable` 與 `Copy to Workspace`；不再使用 Add Marketplace、Vendor、Publish、Draft、Rollback、Sync、Check Update 或獨立 Re-import。
- Import 自動辨識並保留 Plugin Package Format。無法確定有效 package root、format、required manifest 或 path containment 的輸入不是 candidate；component 或 Target Client compatibility 問題只形成 warning。
- Import 可批次選取 candidates，但每個 candidate 獨立原子處理。全域 package ID 重複時，同一 Import confirmation 才提供 `Replace existing`、變更版本或取消；不設獨立 Re-import 入口。
- Create 與 Import 都建立 Managed Plugin，不形成 public/private、created/imported 或其他使用者可見分類。Import provenance 只供說明與稽核，不構成 update channel。
- Plugin card 只表達 Managed Plugin 的名稱、固定 format、版本、target badges 與 validation 狀態；不顯示 Draft、Published、Git Dirty、Remote Ready、Created/Imported 或 Public/Private tags。
- Universal Directory 只是一種 Import Candidate 搜尋來源，不在 Application Center 直接列出或安裝。
- Source Registration、Marketplace Source persistence/API/frontend、Vendoring 名稱與權限、draft/publish/discard lifecycle，以及相關相容層與 migration 全面移除。
- 功能實作交付時必須同步改寫 `docs-site` 的 Marketplace 中英文頁面、側邊欄名稱與 Manager API 契約；正式使用者文件不得繼續描述 Add Marketplace、Marketplace Source、Vendor、draft/publish、immutable release tags 或獨立 Re-import。
