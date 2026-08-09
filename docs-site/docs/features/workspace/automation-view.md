---
title: 工作區自動化檢視
---

# 工作區自動化檢視

## 目的與入口

由 Workspace 導覽進入，只顯示目前 Workspace 的任務與執行；任務定義與執行的 canonical 文件屬於自動化中心。

## 角色與允許操作

入口要求 `workspace.automation.execute`；平台 Automation Center 仍以平台 member gate 進入。

## 核心概念

Workspace view 是 filter 與 context，不是第二份 automation domain。

## 主要流程

以 Workspace ID 篩選任務與執行，開啟相同的建立、編輯與執行詳情流程。

## 畫面狀態與唯讀行為

畫面分別處理 loading、empty、error 與 denied。只有讀取操作時保留可讀內容與一般變更控制項，但停用變更並顯示 i18n 原因；缺少讀取操作時不啟動受保護 query、Provider 或即時連線。

## 限制、失敗與安全

切換 Workspace 時清除舊選取與 query identity，避免顯示前一 Workspace 執行。

## 原始碼依據

- `frontend/src/features/workspace-automation/AutomationModule.tsx::AutomationModule`
- `frontend/src/features/workspace-automation/providers/AutomationProvider.tsx`
- `workspace-manager/app/modules/automation/`

## 相關架構與 API

- [ai-chat](/architecture/overview/ai-chat)
- [automation](/features/automation/)
- [manager-api](/api/manager-api)
