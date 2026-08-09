---
title: 自動化中心
---

# 自動化中心

## 目的與入口

自動化中心是任務、觸發條件與執行記錄的 canonical 產品面；入口為 `/automation`。

## 角色與允許操作

平台 member 可進入；任務對特定 Workspace 執行時仍須具備 `workspace.automation.execute`。

## 核心概念

Job 定義何時與在哪個 Workspace 執行；Execution 是一次 durable attempt；Thread 保存 Agent 對話資料。

## 主要流程

建立或編輯 job、設定 cron/webhook、觸發 execution、追蹤狀態並查看 AI Chat timeline。

## 畫面狀態與唯讀行為

畫面分別處理 loading、empty、error 與 denied。只有讀取操作時保留可讀內容與一般變更控制項，但停用變更並顯示 i18n 原因；缺少讀取操作時不啟動受保護 query、Provider 或即時連線。

## 限制、失敗與安全

取消、重試與 runner recovery 必須以 durable state 為準；失去 Workspace 授權時暫停任務並取消非終態執行。

## 原始碼依據

- `frontend/src/features/workspace-automation/AutomationModule.tsx::AutomationModule`
- `frontend/src/features/workspace-automation/providers/AutomationProvider.tsx`
- `workspace-manager/app/modules/automation/`

## 相關架構與 API

- [ai-chat](/architecture/overview/ai-chat)
- [automation-runner-recovery](/installation/automation-runner-recovery)
- [manager-api](/api/manager-api)
