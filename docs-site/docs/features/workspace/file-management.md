---
title: 檔案管理
---

# 檔案管理

## 目的與入口

由工作區導覽的「檔案管理」進入，瀏覽、建立、編輯、重新命名、搬移、上傳與刪除工作區檔案。

## 角色與允許操作

讀取要求 `workspace.detail.read`；變更要求 `workspace.content.manage`。

## 核心概念

canonical path、revision 與 selection identity 共同避免過期寫入；檔案工作台由 shared file-workbench 與 Workspace adapter 組成。Workspace、Knowledge Base、Marketplace 與 Agent Settings 的檔案管理入口共用相同的衝突、檔案樹同步與檔案 tab 收斂契約。

## 主要流程

選擇目錄或檔案、載入內容、以 expected revision 儲存。上傳、貼上、解壓縮、建立、重新命名與搬移先執行 preflight；只有確認目標實際存在衝突時才開啟共用衝突 Dialog。沒有衝突時維持一般忙碌狀態並直接執行，不顯示衝突畫面。

衝突 Dialog 以批次結果逐項處理 keep both、replace 或 skip；取消／關閉時不提交變更、不更新檔案樹、不改變 tab、剪貼簿或選取狀態。建立同名資源、重新命名或搬移到既有目的路徑也使用同一套流程，replace 只在明確確認後執行。

檔案或目錄刪除前，若有未儲存的相關 tab 會先顯示確認；成功刪除後關閉該路徑及其子孫路徑的 tab。批次操作只收斂成功項目，失敗項目保留在檔案樹與 tab 中並顯示個別原因。重新命名或搬移則將相關 tab（包含目錄子孫）重新映射到新路徑並保留開啟狀態與內容。

上傳、貼上、解壓縮或 replace 成功後，受影響的已開啟檔案 tab 重新讀取後端內容與 revision，不保留覆寫前的草稿。每次變更提交後都重新取得後端權威檔案樹與版本控制狀態；同步失敗不撤銷已提交變更，畫面保留最後一次有效檔案樹並提供重試。

## 畫面狀態與唯讀行為

畫面分別處理 loading、empty、error 與 denied。只有讀取操作時保留可讀內容與一般變更控制項，但停用變更並顯示 i18n 原因；缺少讀取操作時不啟動受保護 query、Provider 或即時連線。

## 限制、失敗與安全

所有路徑需限制在 managed root，拒絕 traversal、symlink escape 與不合法名稱。

## 原始碼依據

- `frontend/src/features/workspace/features/file-management/`
- `frontend/src/shared/components/file-workbench/`
- `workspace-runtime/app/modules/file_system/`
- `packages/aileron-file-core/`

## 相關架構與 API

- [frontend](/architecture/frontend/)
- [runtime-api](/api/runtime-api)
