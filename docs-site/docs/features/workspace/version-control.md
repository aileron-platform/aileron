---
title: 版本控制
---

# 版本控制

## 目的與入口

由工作區導覽的「檔案變更」與「變更記錄」進入，處理 repository setup、diff、commit、branch 與同步。

## 角色與允許操作

讀取要求 `workspace.detail.read`；寫入 Git 與工作樹要求 `workspace.content.manage`。

## 核心概念

repository target interface、operation lock、revision 與產品 Adapter 共同定義單一 Git 操作邊界。

## 主要流程

先確認或建立 repository，再選擇 changes/history；寫入操作在 target lock 內執行並回傳新 revision。

## 畫面狀態與唯讀行為

畫面分別處理 loading、empty、error 與 denied。只有讀取操作時保留可讀內容與一般變更控制項，但停用變更並顯示 i18n 原因；缺少讀取操作時不啟動受保護 query、Provider 或即時連線。

## 限制、失敗與安全

clone、fetch、push 與衝突錯誤保持可診斷；不得在未鎖定 target 上並行寫入。

## 原始碼依據

- `frontend/src/shared/version-control/`
- `frontend/src/features/workspace/integrations/version-control/`
- `workspace-runtime/app/modules/version_control/`
- `packages/aileron-git-core/`

## 相關架構與 API

- [version-control](/architecture/overview/version-control)
- [runtime-api](/api/runtime-api)
