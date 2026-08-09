---
title: Claude Code 設定
---

# Claude Code 設定

## 目的與入口

在 Agent 設定選擇 Claude Code，管理其 Agents、Skills、Commands、MCP 與 Settings。

## 角色與允許操作

沿用 Agent 設定的 Workspace 與 sensitive-settings operations。

## 核心概念

Claude Code 專用設定與共用 CLI settings adapter 分工；scope 與檔案位置由 Runtime resolver 決定。

## 主要流程

選擇資源類型與 scope、載入、編輯並以 revision 儲存。

## 畫面狀態與唯讀行為

畫面分別處理 loading、empty、error 與 denied。只有讀取操作時保留可讀內容與一般變更控制項，但停用變更並顯示 i18n 原因；缺少讀取操作時不啟動受保護 query、Provider 或即時連線。

## 限制、失敗與安全

不假設 host HOME；user scope 使用 Runtime 為目前使用者解析的 managed HOME。

## 原始碼依據

- `workspace-runtime/app/modules/claude_code/`
- `workspace-runtime/app/modules/cli_settings/`
- `frontend/src/features/workspace/features/agent-settings/`

## 相關架構與 API

- [agent-runtime-terminology](/architecture/backend/workspace-runtime/agent-runtime-terminology)
- [runtime-api](/api/runtime-api)
