---
title: Agent 設定
---

# Agent 設定

## 目的與入口

由 Workspace 導覽的 Agent 設定進入，共用入口涵蓋 Agents、Skills、Commands、MCP、Settings 與 Subagents，再依 provider 顯示差異。

## 角色與允許操作

一般設定依 Workspace detail/content operations；可能回傳秘密或原始 scope 值的頁面依 sensitive-settings read/manage。

## 核心概念

project、local、user scope 與 provider 是獨立維度；路徑解析由 Runtime provider adapter 決定。

## 主要流程

先選 provider 與設定類型，再選 scope、讀取並以 revision 儲存；user scope 內容需維持每位使用者隔離。

## 畫面狀態與唯讀行為

畫面分別處理 loading、empty、error 與 denied。只有讀取操作時保留可讀內容與一般變更控制項，但停用變更並顯示 i18n 原因；缺少讀取操作時不啟動受保護 query、Provider 或即時連線。

## 限制、失敗與安全

秘密值不可先載入再遮蔽；同名自訂內容、外部路徑與 symlink conflict 不得被預設內容覆寫。

## 原始碼依據

- `frontend/src/features/workspace/features/agent-settings/`
- `workspace-runtime/app/modules/cli_settings/`
- `workspace-runtime/app/modules/claude_code/`

## 相關架構與 API

- [workspace-runtime](/architecture/backend/workspace-runtime/)
- [runtime-api](/api/runtime-api)
