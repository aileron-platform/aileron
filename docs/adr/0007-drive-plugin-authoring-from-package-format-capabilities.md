---
status: accepted
---

# 由 Plugin Package Format 能力驅動編輯功能

結構化編輯器能修改什麼，由 Manager 的 package-format adapter 宣告 `read-write`、`read-only` 或 `unsupported` Authoring Capability；實際可見功能再取 package-format capability、所有 Catalog Variants 的 Target Client 支援與 actor permission 交集。Frontend 只渲染這份 contract，backend mutations 以同一 contract 執行授權與能力檢查。

## Considered Options

- 依 Target Client 寫死 tabs：容易實作，但同一 client 支援多種 package formats 時會顯示錯誤功能。
- Frontend 與 backend 各自維護矩陣：能獨立演進，但必然產生可見與可寫能力漂移。
- 由 package-format adapter 提供單一能力 contract：需要明確 adapter seam，但能使 UI 與 mutation 規則一致，因此採用此方案。

## Consequences

- Create 流程先選 Plugin Package Format，再選一個或多個相容 Target Clients，最後取得正確 scaffold；format 建立或匯入後不可原地轉換。
- 同一 Managed Plugin 只有一份 canonical artifact，可有多個 `(targetClient, packageFormat)` Catalog Variants；Application Center 只顯示一張卡片與 target badges。
- Catalog Plugin Identity 是跨 format/client 全域唯一 package ID。Manifest name 一律正規化為該 ID；display name、format、targets 與 repository path 都不是 identity。
- 多 target plugin 的結構化能力採所有 targets 的交集；client-only extension 仍可透過 Files 編輯。Files 可查看及修改完整 artifact，包括未知或不受支援的內容。
- `unsupported` 功能隱藏，直接 URL 轉回 Basic 並顯示一次原因；`read-only` 可見但不可 mutation。Backend 對不支援 mutation 回覆 `marketplace.authoring.capability_not_supported`。
- Agent Plugin 1.0 第一階段只提供 Basic、MCP、Skills 與 Files，不提供 Output Styles、agents、commands 或 hooks 的結構化編輯。
- Basic 可增減相容 Catalog Variants 而不複製 artifact；移除 variant 不會 uninstall 已安裝的 Workspace Plugin。
