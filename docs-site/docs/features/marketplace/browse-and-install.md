---
title: 瀏覽與安裝
---

# 瀏覽與安裝

應用中心只列出 Managed Registry 中的 Plugin。卡片顯示名稱、package format、版本、Target Client 與 validation 狀態，不顯示 Draft、Published、Git Dirty、Remote Ready、Created／Imported 或 Public／Private 標籤。

Plugin Installation 將完整 artifact 交給相容 Target Client CLI。CLI 的命令輸出與 terminal result 是安裝及啟用結果的權威；Aileron 只把回覆呈現在 UI 並保存 audit，不另行推導 client state。Codex 需要在新 session 載入新安裝能力。

User Copy 使用目前 Managed Registry working tree，依明確的 `(packageFormat, targetClient)` projection，把可投影資源一次性寫入 Workspace Runtime HOME 的 client user scope。Preflight 會列出 projected、skipped、conflict 與 blocking resources；partial copy 與 overwrite 仍需使用者確認。成功產物是 Workspace 共享的 standalone agent resources，不是 installed plugin，也不會自動同步後續更新。

刪除應用中心 Plugin 不會執行 remote cleanup、CLI uninstall 或 User Copy cleanup。若 CLI 使用的 Git repository 已找不到該 Plugin，後續安裝會由 CLI 自然回報錯誤。
