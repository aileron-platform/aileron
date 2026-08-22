---
status: accepted
---

# 將 Agent Plugin 生命週期委派給相容 Target Client

> ADR-0008 已取代本決策中 managed immutable release 與 source publication 的假設；Target Client CLI 擁有安裝與啟用生命週期的邊界仍然有效。

Aileron 將 `agent-plugin/1.0.0` 視為與 `codex-native`、`claude-native` 並列的 Plugin Package Format，而不是新的 provider；Target Client 是另一個獨立維度。首個實測目標是 Codex 0.147，但 Aileron 不另設 client version gate；實際安裝能力與錯誤由 Workspace 內執行的 client CLI 判定。未來只為提供 Agent Plugin CLI 契約的 client 增加 adapter，不把 Agent Plugin 投射成其他 client 的 native package。這保留標準 artifact 與 client-owned lifecycle 的邊界，同時避免 Aileron 建立另一套會與 client 狀態漂移的安裝真相。

## Considered Options

- 以 Agent Plugin 作為 provider：路由簡單，但混淆 package contract 與實際執行、保存設定的 client。
- 由 Aileron 保存 desired state 並自行判定成功：可統一 UI，但會產生與 client CLI、filesystem 不一致的第二套權威狀態。
- 由相容 Target Client 擁有狀態，Aileron 編排並驗證結果：需要 format/client capability adapter 與分階段錯誤，但能保留單一真相，因此採用此方案。

## Consequences

- CLI 與 client filesystem/configuration 是安裝及啟用狀態的權威；Aileron persistence 只保存 audit、cache 與 projection，不保存 desired state。
- 每個 catalog entry 都必須明確宣告 `packageFormat` 與 `targetClient`。`provider` 視為從未存在，從 API、persistence、routes、frontend、runtime adapter 與測試全面移除；不保留 alias、legacy inference、migration、`unknown` 狀態或其他相容程式碼。
- Agent Plugin artifact 維持 canonical package layout；Aileron 只為 catalog metadata 與 resource projection 讀取 root `plugin.json`，不改寫 artifact 或產生永久 native wrapper。安裝時的 format、component 與 extension 支援由 Target Client CLI 處理。
- Catalog identity 由 source 與 catalog entry 組成；release identity 再加入不可變來源 revision；installation identity 由 Workspace、Target Client 與 catalog identity 組成。Manifest `name` 不作 Aileron 全域 primary key。
- `targetClient` 與 `packageFormat` 保存於 Aileron canonical catalog 的 variant 層；同一 family 可有多個 variant。Target Client native marketplace metadata 是由 canonical catalog 產生的 projection，不是另一份權威 catalog。
- Aileron 不維護 client version capability matrix，也不自行解釋 client-specific extensions。CLI 拒絕 package、component 或 extension 時，Aileron 保留其 exit code、stdout 與 stderr 並回覆 UI。
- Catalog validation 只阻擋 Aileron 自己擁有的來源授權、credential input 與 package path containment 問題；manifest、schema、component 與 client compatibility 只顯示 warning，是否安裝由 CLI 決定。
- Installed/Enabled 狀態只取自 Target Client 的 plugin-list CLI；filesystem/cache 只供 Declared Plugin Resource 的唯讀投射，不得推導 client state。
- `packageFormat` 決定 catalog metadata 與 Declared Plugin Resource 使用哪一份 manifest；同時存在其他格式的 manifest 時不合併、不覆寫，只顯示 ambiguity warning，最後仍由 CLI 決定是否接受。
- 同一 Plugin family 可包含相同 Target Client 的多種 package format；variant identity 使用 `(targetClient, packageFormat)`，不再只以 provider 區分。
- 使用者看到單一 `Install and enable` 操作；其中每個 marketplace、install 與 enable CLI invocation 都產生獨立的 command result，包含 stage、exit code、stdout、stderr。CLI 輸出不做秘密或路徑遮罩，但維持 byte/line 上限、`truncated` 標誌，並移除 ANSI、NUL 與非文字控制字元。UI 以 install/enable 回覆為主，其餘 stage 放在可展開診斷，不串接成一段輸出。
- 每個 command result 以 `operationId` 關聯 Workspace-scoped Marketplace audit 並持久保存。保存期限沿用現有 audit 行為：Aileron 應用層不設定到期時間或自動清理，資料持續保留到外部資料庫生命週期政策或明確資料刪除為止。當次操作者及該 Workspace 的 owner/manager 可在後續查看；reader 不可讀取 raw CLI output。
- Command results 使用獨立的 append-only child records，以 `operationId` 與 sequence 關聯 Marketplace activity；activity list 只回傳摘要，detail endpoint 才載入輸出。每個 stdout 與 stderr 各保存最多 256 KiB，截斷時保留前 128 KiB 與後 128 KiB，並記錄 `originalByteCount` 與 `truncated`。
- Command result 保存 normalized `argvDisplay`、stage、exit code、開始與結束時間；不捕捉 process environment。Workspace 刪除後保留 `workspaceIdSnapshot` 與 command results，但 raw output 只允許 platform admin 查看，不把 orphaned record 轉成原操作者的個人 activity。
- CLI mutation 成功後若 audit persistence 失敗，Aileron 先有限次重試；仍失敗時不推翻 client state，回覆成功並附加高可見度的 `audit-persistence-failed` warning。
- CLI timeout 沒有可判定的 exit result，操作回報 `command-timeout`／`outcome-unconfirmed`，不得猜測成功或失敗；後續 inventory refresh 獨立呈現 client 回報的 Installed/Enabled 狀態。
- 相同 Plugin Installation Identity 的 mutation 以 `(workspace, targetClient, catalogPlugin)` 序列化；競爭請求回覆 `operation-in-progress`，不得讓 install、enable、disable 或 uninstall command stages 交錯。
- 整體成功由必要的 mutation CLI commands 決定。Codex 0.147 的 `plugin add` 同時安裝並啟用；Claude 的 install 成功後一律再執行 `claude plugin enable`。任一必要 mutation command 非零退出即失敗，並保留先前已完成的部分狀態，不自動 uninstall。
- Marketplace/plugin list 只在操作後更新 client inventory；readback timeout、格式變更或暫時不一致回報 `state-unconfirmed` warning，不得推翻 mutation CLI 已回報的成功。Inventory 隨後仍如實呈現 client 回覆的 installed/enabled 狀態。
- Catalog 可從 Plugin Artifact 顯示 Declared Plugin Resources；安裝結果只呈現 CLI commands 與 client inventory 的 Installed/Enabled 狀態，不宣稱既有 session 已完成 Session Loading。
- Enablement 失敗時，使用者可依 CLI 回覆執行 `Retry enable` 或明確 `Uninstall`。
- Enable、disable、uninstall 與 plugin data retention 都使用 Target Client 提供的 CLI 語意與選項；Aileron 不直接修改 client config、cache 或 data directory。
- 明確的互動式 Install 可在 preflight 揭露並取得同意後覆寫 package 或 marketplace 的 `defaultEnabled: false`；managed 或自動化流程不得靜默覆寫。
- 「安裝同時啟動」指 Plugin Installation 後立即完成 Plugin Enablement。它保證新 session 可使用，不承諾 restart、hot reload，或既有 session 已完成 Session Loading。
- CLI installation 使用 Aileron Managed Registry 的 remote Git repository；其 working tree、版本及 publication 行為由 ADR-0008 定義。
