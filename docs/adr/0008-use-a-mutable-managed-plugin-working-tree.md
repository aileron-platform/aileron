---
status: accepted
---

# 使用可變的 Managed Plugin Working Tree

Create、Import、Plugin Replacement 與 Editor Save 直接改變 Aileron Managed Registry working tree，並立即反映在 Application Center；不存在 draft、publish 或 immutable release lifecycle。Marketplace 不替使用者 commit、tag 或 push Git，repository publication 由使用者透過既有版本控制流程自行完成。

## Considered Options

- 每次變更產生不可變 release：可保留 rollback 與精確歷史，但會恢復使用者明確不要的 publish/version lifecycle。
- 維持 draft 與 published 雙狀態：能區分 working tree 和 remote，但增加 Application Center 狀態與操作。
- 以 working tree 作唯一 managed artifact：模型直接且符合現有 Git 使用方式，因此採用此方案。

## Consequences

- Create 預設版本為 `1.0.0`；Import 使用合法 manifest version，否則為 `1.0.0`；Editor Save 預設目前版本。Plugin Version 是可變 SemVer metadata，不是 artifact identity。
- 相同版本可在明確確認後以新內容破壞性覆寫。確認畫面提供檔案差異及 overwrite、change version、cancel；不自動增加 patch version，不保存舊 artifact，也不提供 rollback。
- Replacement 維持既有全域 package ID 與 Plugin Package Format，重新正規化 manifest name/version，並以新來源取代 current provenance；舊 provenance 只保留在 audit。
- Working Tree Mutation Audit 保存 operator、time、old/new digest、version、provenance 與 file-change summary，但不是 backup。
- Marketplace editor mutations 採 last-write-wins，不使用 expected revision、revision conflict、force overwrite 或 stale UI 提示；User Copy 的 digest-bound preflight/apply 保護不受影響。
- `Copy to Workspace` 立即讀取 working tree。`Install and Enable` 則交由 Target Client CLI 從 remote Git 解析；Aileron 不預查或警告 working tree 與 remote 的差異，因此 CLI 可能安裝舊內容，或因 remote 尚無內容而自然失敗。
- Managed Plugin 即使因 Files 編輯而 validation error，仍留在 Application Center。CLI Install 可嘗試並由 CLI 判定；User Copy preflight 阻擋無法安全投影的內容。
- Delete 只移除 working tree 與 catalog，不修改 remote Git、不 uninstall Workspace Plugin、不移除既有 Standalone Agent Resources，且不保留可回復內容。Git 操作使內容重新出現時，catalog refresh 可再次納入。
- Marketplace 不處理 Git commit/push、concurrent edit coordination、remote consistency、rollback 或舊 API/data 相容。
