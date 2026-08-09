---
title: 執行記錄
---

# 執行記錄

## 目的與入口

在自動化中心查看全域或單一任務的執行，開啟詳情、取消或檢視 Agent timeline。

## 角色與允許操作

執行可見性與控制沿用目標 Workspace 的 automation operation。

## 核心概念

queued、claimed、running、completed、failed、cancelled 是 durable execution state；UI 連線狀態不是執行結果。

## 主要流程

由清單開啟 execution，透過輪詢／事件更新狀態；詳情以共用 AI Chat item mapper 顯示 thread。

## 畫面狀態與唯讀行為

畫面分別處理 loading、empty、error 與 denied。只有讀取操作時保留可讀內容與一般變更控制項，但停用變更並顯示 i18n 原因；缺少讀取操作時不啟動受保護 query、Provider 或即時連線。

## 限制、失敗與安全

runner 中斷後由 claim/recovery 契約接手；不得因頁面關閉把 running 標成 failed。

## 原始碼依據

- `frontend/src/features/workspace-automation/components/execution/ExecutionDetailDialog.tsx`
- `workspace-manager/app/modules/automation/router.py`
- `workspace-manager/app/modules/automation/repository.py`
- `workspace-manager/app/modules/automation/execution.py`

## 相關架構與 API

- [ai-chat](/architecture/overview/ai-chat)
- [automation-runner-recovery](/installation/automation-runner-recovery)
- [manager-api](/api/manager-api)
