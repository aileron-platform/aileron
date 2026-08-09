---
title: 工作區
---

# 工作區

## 目的與入口

工作區是 AI 開發的主要產品面，入口為 `/workspace`、建立精靈與 `/workspace/:workspaceId/*`。

## 角色與允許操作

平台 member 可建立與列出工作區；資源 reader 可讀 detail，manager 可執行多數互動與管理，owner 另可永久刪除。

## 核心概念

工作區結合控制平面 availability 與執行平面 generation；功能入口依每個 Workspace 的 `allowedOperations` 過濾。

## 主要流程

根路徑載入可見清單並選擇第一個或既有選取；可使用 AI Chat 時進入 Chat，否則進入檔案管理。

## 畫面狀態與唯讀行為

畫面分別處理 loading、empty、error 與 denied。只有讀取操作時保留可讀內容與一般變更控制項，但停用變更並顯示 i18n 原因；缺少讀取操作時不啟動受保護 query、Provider 或即時連線。

## 限制、失敗與安全

availability 未 ready、generation 失效或授權資料不完整時，不掛載 Runtime 功能。

## 原始碼依據

- `frontend/src/features/workspace/WorkspaceModule.tsx::WorkspaceRootResolver`
- `frontend/src/features/workspace/layout/workspaceNavigationModel.ts`
- `frontend/src/features/workspace/model/workspacePermissions.ts::resolveWorkspacePermissions`
- `contracts/workspace-availability.json`

## 相關架構與 API

- [frontend](/architecture/frontend/)
- [execution-plane](/architecture/overview/execution-plane)
- [manager-api](/api/manager-api)
- [runtime-api](/api/runtime-api)
