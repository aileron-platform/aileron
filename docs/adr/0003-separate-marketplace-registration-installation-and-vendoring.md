---
status: superseded by ADR-0006
---

# 分離 Marketplace Source 註冊、Plugin 安裝與 Plugin Vendoring

Aileron 將 Marketplace Source Registration、Plugin Installation 與 Plugin Vendoring 定義為三個獨立操作。Git URL 的來源管理註冊並追蹤完整 Marketplace Source；從該來源選擇 Plugin 只發生在安裝階段；只有使用者明確建立內部衍生版本時，才把內容複製到 Aileron Managed Registry。這個邊界避免目前「scan、select、import」同時暗示來源註冊、內容複製與安裝，並讓公開來源與 private source 依 Marketplace Source identity 共存。

## Considered Options

- 保留單一 Import 流程：操作較少，但無法判斷結果是可同步來源、內部 fork，或 Workspace 安裝。
- 掃描 Git repository 後只複製選定 Plugin：適合 vendoring，但會失去 Marketplace Source 的同步與來源生命週期，不能稱為加入 Marketplace。
- 分離三個操作：使用者意圖、授權、失敗階段、移除與稽核都能分別表達，因此採用此方案。

## Consequences

- `Add Marketplace Source` 以 existing Git credentials 存取 repository，不在 URL、manifest 或 Marketplace 設定保存 credential；驗證後以原子且可重試的操作註冊來源。
- `Install Plugin` 以 Marketplace Source identity、Plugin name 與 immutable version 識別安裝；移除 Plugin 與移除 Marketplace Source 是不同操作，移除來源前必須列出受影響的安裝。
- `Vendor Plugin` 必須要求新的內部 Plugin name、SemVer、upstream repository、baseline、授權與內部維護者資料。與 upstream 共存時不得沿用相同 Plugin name。
- Private Marketplace Source 的建議 repository 由 `.agents/plugins/marketplace.json` 與 `plugins/<plugin-name>/` 組成，catalog 以相對路徑指向 Plugin root；內部預設名稱為 `aileron-internal`，Superpowers fork 預設名稱為 `superpowers-internal`。
- 發布使用不可變 Git tag，upstream 更新只能經審查 PR、內容與權限檢查及 container tests；升級與 rollback 都必須指定版本。
- 每個操作回報明確的 stage、source、destination 與底層錯誤分類，前後端只傳遞 i18n key 與結構化參數，不再以單一 `copyFailed` 吞掉 clone、驗證、授權、寫入、發布或安裝錯誤。
- 實作時必須同步更新 Marketplace API、前端流程、i18n、container tests 與 `docs-site` 的正式現況契約；完成實作前，`docs-site` 維持描述現行行為。
