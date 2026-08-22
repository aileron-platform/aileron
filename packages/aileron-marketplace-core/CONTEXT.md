# Aileron Marketplace

本文件定義 Aileron 中 Managed Plugin、Plugin Package Format、編輯、delivery 與 Workspace 安裝的身分及生命週期邊界，避免將外部候選、Managed Registry working tree 與 Target Client 狀態混為同一事實。

## 語言

**Application Center**：
Aileron 中瀏覽、建立、匯入、編輯及 delivery Managed Plugins 的產品介面；它只列出 Aileron Managed Registry working tree 中的 Plugin，不呈現 public/private 或建立來源分類。
_避免：Marketplace Aggregator、Public Plugin Directory、Private Plugins Page_

**Universal Directory**：
由 OpenAI 維護、供 ChatGPT 與 Codex 共用的公開 Plugin 目錄；Application Center 只在 Import Plugin 流程中搜尋它並產生 Plugin Import Candidates，不直接列出或安裝其中項目。
_避免：官方 Marketplace repository、OpenAI Git repository_

**Aileron Managed Registry**：
由 Aileron 管理、保存所有 Managed Plugin working trees 與 catalog 的唯一權威 Git repository。
_避免：Import cache、本機 Plugin 目錄_

**Catalog Plugin**：
由 Managed Plugin Working Tree 宣告、可立即出現在 Application Center 的 Plugin 項目；它不具有 Draft/Published lifecycle，也不表示 remote Git 已包含該內容或已安裝到任何 Workspace。卡片可顯示固定 Plugin Package Format、Plugin Version、Target Client badges 與 validation 狀態，但不顯示 Draft、Published、Git Dirty、Remote Ready、Created/Imported 或 Public/Private tags。外部 Plugin 在完成 Plugin Import 前只會是 Plugin Import Candidate。
_避免：Installed Plugin、Import Candidate、Remote-ready Plugin、Lifecycle Tag、Origin Tag_

**Agent Plugin**：
符合 Agent Plugins 標準，以 Plugin root 的 `plugin.json` 宣告 package identity，並依標準 well-known locations 提供 Skills、MCP servers 與其他 components 的 Plugin Package Format。
_避免：Agent provider、通用安裝器_

**Plugin Package Format**：
Plugin artifact 遵循的結構與 manifest 契約，例如 `agent-plugin/1.0.0`、`codex-native` 或 `claude-native`；它不代表負責安裝或執行 Plugin 的 Agent Client，且在 Plugin 建立或匯入後不可原地變更。
_避免：Provider、Target Client_

**Target Client**：
在目標 Workspace 中負責驗證、安裝、啟用及載入 Plugin 的相容 Agent Client；同一 Plugin Package Format 可被多個 Target Client 支援。
_避免：Plugin Package Format、Marketplace Source_

**Client User Scope**：
Target Client 綁定於作業系統使用者或 client configuration root 的設定範圍。在 Aileron Workspace Runtime 中，它對應該 Workspace 專屬且持久化的 Runtime HOME，並由同一 Workspace 的所有使用者與 sessions 共用，不對應單一 Aileron human user。
_避免：Aileron User Scope、Personal Plugin、Cross-workspace scope_

**Agent Defaults**：
Aileron 在 Workspace Runtime HOME 首次初始化時，分別投影至 Codex、Claude 與 OpenCode Client User Scope 的內建 Skills。每個 Target Client 持有獨立副本；初始化只建立缺少的預設 Skill，完成後內容由 Workspace 擁有，不再由映像升級、Runtime 重啟或持續同步機制覆寫或補回。
_避免：Project Defaults、Shared Skills Symlink、Managed Skill Installation、Continuously Reconciled Defaults_

**Workspace Plugin Scope**：
Aileron 對 Plugin 安裝影響範圍的產品語意；目前由 Workspace 專屬 Runtime HOME 中的 Client User Scope 實現。
_避免：Target Client project scope、Target Client local scope、Aileron User Scope_

**Plugin Artifact**：
一個 Managed Plugin 依其 Plugin Package Format 組成的 canonical 內容與 manifest 集合；Target Client CLI 從 remote Git 解析它，User Copy 則從 Managed Plugin Working Tree 解析它。
_避免：Catalog metadata、Installed Plugin_

**Declared Plugin Resource**：
Plugin Artifact 所包含或宣告、可供 catalog 預覽的 Skill、MCP server 或其他資源；它不表示 Target Client 已安裝、啟用或載入該資源。
_避免：Enabled Resource、Loaded Resource、Effective Resource_

**Installed Plugin**：
由特定 Managed Plugin、Plugin Version 與 Target Client CLI remote resolution 安裝到單一 Workspace Target Client scope 的 Plugin。
_避免：Catalog Plugin、User Copy_

**Plugin Enablement**：
Target Client 的持久設定允許 Installed Plugin 在新 session 中使用；產品語言中的「啟動 Plugin」專指此狀態。
_避免：Plugin Installation、Session Loading、Activation_

**Session Loading**：
特定 Agent Client session 已載入 Enabled Plugin 資源的執行期事實；Plugin Enablement 不表示既有 session 已即時載入。
_避免：Plugin Enablement、Installation success_

**Managed Plugin**：
Aileron Managed Registry working tree 中可由 Application Center 編輯及 delivery 的 Plugin；Create Plugin 與 Plugin Import 都建立同一種 Managed Plugin，不形成可見的來源分類。經 Import 建立者仍保存 upstream provenance，但不會自動變動。
_避免：Private Plugin、Vendored Plugin、Public Plugin_

**Plugin Import**：
選取一個或一批外部 Plugin Artifact，保留其 Plugin Package Format 與 upstream provenance，並複製至 Aileron Managed Registry 形成 Managed Plugins 的操作。每個 candidate 是獨立原子單位，使用者指定的全域 package ID 與 Plugin Version 會正規化寫入 format manifest；單一失敗不回滾其他成功 candidates，也不留下半成品。若選定 identity 已存在，Import confirmation 才提供 Plugin Replacement，不設獨立 Re-import 入口。
_避免：Add Marketplace、Marketplace Source Registration、Package Format Conversion_

**Plugin Replacement**：
Plugin Import 發現選定 identity 已存在後，讓使用者明確以 Import Candidate 取代既有 Managed Plugin working tree 的衝突處理；新 artifact 必須維持相同 Plugin Package Format，既有全域 package ID 會重新正規化寫入 manifest，使用者先確認檔案差異，再原子建立或覆寫指定 Plugin Version。覆寫相同版本時，既有 working-tree artifact 會被破壞性取代且不可回復；current upstream provenance 由新 input 取代。
_避免：Re-import Entry、Upstream Update、Sync_

**Plugin Import Candidate**：
從單次 Git、ZIP 或 Universal Directory import input 掃描得出的外部 Plugin Artifact 候選；它必須具有可確定且結構有效的 package root 與 Plugin Package Format，尚未進入 catalog，也不是可安裝或可編輯的 Plugin。獨立 component 或 Target Client compatibility 問題只形成 warnings。
_避免：Marketplace Source、Catalog Plugin、Vendored Plugin_

**Upstream Plugin Reference**：
經 Plugin Import 建立的 Managed Plugin 保存的原始來源、artifact locator 與 revision provenance，只作稽核及來源說明；它不是可同步、可檢查更新或會自動變更內容的連結。
_避免：Registered Source、Live Subscription、Update Channel_

**Authoring Capability**：
Manager 依 Plugin Package Format 宣告、可由結構化編輯器理解及修改的資源能力，狀態為 read-write、read-only 或 unsupported；Target Client 支援與 actor permission 可進一步縮小可見能力，但不能擴張 package format 未定義的能力。Frontend 與 backend mutations 共用此 contract。
_避免：Editor Tab、Target Client Feature、Declared Plugin Resource_

**Catalog Plugin Identity**：
由 Application Center 全域唯一 package ID 組成的 Managed Plugin 穩定識別；manifest name、display name、Plugin Package Format、Target Client 與 repository path 均不是 identity。
_避免：Manifest name、Display name、Source Identity_

**Managed Plugin Working Tree**：
Aileron Managed Registry 中目前可編輯的 Plugin Artifact；Create、Import、Plugin Replacement 與 Editor Save 直接改變此內容，不存在獨立 Draft status。Marketplace 不替使用者 commit、tag 或 push；User Copy 可立即使用 working tree，但 Target Client CLI 只能取得使用者另行 commit 及 push 後的 remote Git 內容。
_避免：Draft、Published Release、Remote Repository_

**Plugin Delivery Snapshot**：
一次 delivery 實際解析到的 Plugin Artifact 內容身分；CLI installation 由 Target Client 自行解析 remote Git repository，User Copy 則以 Managed Plugin Working Tree 的 source digest 綁定。兩種 delivery mode 不保證取得相同內容。
_避免：Plugin Version、Catalog State、Desired State_

**Plugin Installation Identity**：
Workspace、Target Client 與 Catalog Plugin Identity 的組合，識別由該 client 擁有的一個 Plugin installation lifecycle。
_避免：Plugin Release Identity、Manifest name_

**Target Client Compatibility**：
特定 Plugin Artifact 能否由 Target Client 接受及處理的 client-owned 判定；它與 Aileron 為 catalog 顯示而讀取 package metadata 是不同事實。
_避免：Schema validity、Universal compatibility_

**Plugin Command Result**：
Target Client CLI 單次 invocation 的不可變結果，包含 operation、stage、argv display、exit code、stdout、stderr、truncation 與時間資訊；它是 audit evidence，不是 Installed/Enabled desired state。
_避免：Combined CLI message、Plugin state、Current-session output_

**Catalog Variant**：
同一 Managed Plugin 中由 Target Client 與固定 Plugin Package Format 界定的 delivery option；多個 variants 共用一份 canonical artifact，並呈現在同一 Application Center 項目內。client-native marketplace metadata 只是它的衍生 projection。
_避免：Managed Plugin、Provider entry、Independent Plugin Copy_

**Plugin Installation**：
要求目標 Workspace 的 Target Client CLI 從指定 remote Git repository 安裝 Plugin 的操作；CLI 實際解析到的內容可能落後於 Managed Plugin Working Tree，Aileron 不預先比對或推導一致性。
_避免：Plugin Import、User Copy_

**Managed Plugin Deletion**：
從 Aileron Managed Registry working tree 與 Application Center 移除一個 Managed Plugin 的操作；它不修改 remote Git、不 uninstall Workspace Plugins、不刪除 User Copy 形成的 Standalone Agent Resources，且不保存可回復 artifact。
_避免：Plugin Uninstall、User Copy Cleanup、Git Commit_

**Working Tree Mutation Audit**：
Create、Import、Plugin Replacement 或 Editor Save 對 Managed Plugin Working Tree 的稽核證據，包含操作者、時間、版本、來源 provenance、舊新 digest 與檔案變更摘要；它不保存被覆寫 artifact，也不提供 restore。
_避免：Backup、Git History、Rollback Snapshot_

**User Copy**：
由 Aileron 將 Plugin Artifact 中可投影的資源一次性寫入 Target Client 的 Client User Scope；在 Workspace Runtime 中其影響範圍是整個 Workspace。完成後資源脫離 Plugin lifecycle，不具有安裝、啟用、升級或解除安裝狀態。
_避免：Plugin Installation、Installed Plugin、Personal Copy_

**User Copy Projection**：
由 Plugin Package Format 與 Target Client 共同決定的 Aileron-owned 轉換契約，定義哪些來源資源可成為哪些 standalone target resources；它不表示 Target Client CLI 相容性。
_避免：Provider compatibility、Plugin installation adapter_

**Standalone Agent Resource**：
User Copy 寫入 Client User Scope 後由 Target Client 獨立發現的資源；它保留來源 provenance，但不再由原 Plugin 的生命週期管理。
_避免：Installed Plugin Resource、Enabled Plugin Resource_

**Plugin Version**：
Plugin manifest 與 catalog 顯示使用的 mutable SemVer 欄位；使用者可明確以新內容破壞性覆寫相同版本。它不代表 Git 已 commit/push、不識別歷史 artifact，也不保證 CLI installation 與 User Copy 取得相同內容。
_避免：Release Identity、Artifact Digest、Delivery Availability_
