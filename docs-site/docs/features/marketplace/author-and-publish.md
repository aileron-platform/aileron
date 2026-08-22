---
title: 建立與匯入
---

# 建立與匯入

Platform admin 可在應用中心選擇 package format、相容的 Target Client、package ID、顯示名稱與版本來建立 Plugin。建立成功即寫入 Managed Registry working tree 並可編輯、安裝或複製，不需要另外發佈。

`Import Plugin` 接受 Git repository 或 ZIP 封存檔。Manager 會在 server 端重新掃描來源，列出可匯入的 Plugin 與偵測到的 format；使用者選取候選項目並確認版本後，內容才會複製到 Managed Registry。

Package ID 在應用中心內必須唯一。若匯入發現重複 ID，必須明確選擇 Replace；相同版本也可覆寫，系統不保留 rollback。更新 upstream 內容的方式是再次使用 Import 並 Replace，沒有獨立 Re-import 或自動同步。

應用中心不會自動執行 Git commit、tag 或 push。Working tree 內容可立即用於 User Copy；CLI 安裝則依 CLI 從設定的 Git repository 取得內容，尚未由使用者自行 commit/push 的內容會自然無法被遠端 CLI 取得。
