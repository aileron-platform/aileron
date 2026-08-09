---
title: 任務與觸發條件
---

# 任務與觸發條件

## 目的與入口

在自動化中心建立與編輯任務，設定 Workspace、Agent 指令、cron 或 webhook trigger。

## 角色與允許操作

建立與執行需具備目標 Workspace 的 `workspace.automation.execute`。

## 核心概念

Job、trigger、schedule、webhook secret 與 execution queue 是不同狀態。

## 主要流程

驗證表單、建立 job、啟用 trigger；cron 依設定時區排程，webhook 驗證 secret 後入列。

## 畫面狀態與唯讀行為

畫面分別處理 loading、empty、error 與 denied。只有讀取操作時保留可讀內容與一般變更控制項，但停用變更並顯示 i18n 原因；缺少讀取操作時不啟動受保護 query、Provider 或即時連線。

## 限制、失敗與安全

避免重複 trigger 與超額並行；webhook secret 不可再次明文顯示。

## 原始碼依據

- `frontend/src/features/workspace-automation/components/`
- `workspace-manager/app/modules/automation/router.py`
- `workspace-manager/app/modules/automation/jobs.py`
- `workspace-manager/app/modules/automation/scheduler.py`

## 相關架構與 API

- [workspace-manager](/architecture/backend/workspace-manager/)
- [manager-api](/api/manager-api)
