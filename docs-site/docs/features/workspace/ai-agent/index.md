---
title: AI Agent
---

# AI Agent

## 目的與入口

AI Agent 區整合 AI Chat 與 Terminal；兩者共享 Workspace context，但有獨立 operation、session 與失敗狀態。

## 角色與允許操作

AI Chat 要求 `workspace.agent_chat.use`；Terminal 要求 `workspace.terminal.use`，目前兩者最低資源角色皆為 manager。

## 核心概念

Chat thread／turn 與 Terminal session 是不同生命週期；Agent provider 設定也不等同 Chat 使用資格。

## 主要流程

選擇 Workspace 後依允許操作進入 Chat 或 Terminal；Runtime unavailable 時不建立 session。

## 畫面狀態與唯讀行為

畫面分別處理 loading、empty、error 與 denied。只有讀取操作時保留可讀內容與一般變更控制項，但停用變更並顯示 i18n 原因；缺少讀取操作時不啟動受保護 query、Provider 或即時連線。

## 限制、失敗與安全

即時連線中斷需可重連；缺少操作或 generation 變更時立即停止受保護連線。

## 原始碼依據

- `frontend/src/features/ai-chat/`
- `frontend/src/features/workspace/features/container-management/`
- `workspace-runtime/app/modules/thread/`
- `workspace-runtime/app/modules/internal/router.py`

## 相關架構與 API

- [ai-chat](/architecture/overview/ai-chat)
- [workspace-runtime](/architecture/backend/workspace-runtime/)
- [runtime-api](/api/runtime-api)
