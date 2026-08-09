---
title: 檔案與版本控制
---

# 檔案與版本控制

## 目的與入口

由知識庫詳情的檔案、檔案變更與變更記錄進入，管理 canonical content 與 Git 歷程。

## 角色與允許操作

讀取要求 detail read；內容與 Git 寫入要求 `knowledge_base.content.manage`。

## 核心概念

知識庫與 Workspace 共用 shared file-workbench、file/version-control interface 與檔案管理語意，但由不同 target adapter 解析 repository。所有檔案管理入口都遵循相同的衝突、檔案樹同步與檔案 tab 收斂契約。

## 主要流程

選擇檔案、編輯並以 revision 儲存；版本控制操作在 knowledge-base target lock 中執行。上傳、貼上、解壓縮、建立、重新命名與搬移先執行 preflight，只有實際目標衝突才開啟共用衝突 Dialog；無衝突時直接執行。衝突 Dialog 的 keep both、replace、skip 與取消邊界一致，取消不會提交變更或改變檔案樹、tab、剪貼簿與選取狀態。

刪除前會針對未儲存的相關 tab 顯示確認；成功刪除後關閉該路徑及子孫路徑 tab。批次操作只收斂成功項目，失敗項目保留並顯示原因。重新命名或搬移成功後，相關檔案 tab 映射到新路徑並保留開啟狀態與內容；replace 成功後，受影響 tab 重新載入後端的新內容與 revision。

每次變更提交後重新取得後端權威檔案樹與版本控制狀態。檔案樹同步失敗不撤銷已提交內容，介面保留最後有效快照並提供重試入口。

## 畫面狀態與唯讀行為

畫面分別處理 loading、empty、error 與 denied。只有讀取操作時保留可讀內容與一般變更控制項，但停用變更並顯示 i18n 原因；缺少讀取操作時不啟動受保護 query、Provider 或即時連線。

## 限制、失敗與安全

Workspace 掛載為唯讀或受治理的使用面，不能繞過知識庫 content operation 修改 canonical content。

## 原始碼依據

- `frontend/src/features/knowledge-base/components/`
- `frontend/src/shared/components/file-workbench/`
- `workspace-manager/app/modules/knowledge_base/`
- `packages/aileron-git-core/`

## 相關架構與 API

- [version-control](/architecture/overview/version-control)
- [manager-api](/api/manager-api)
