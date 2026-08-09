---
title: Codex 設定
---

# Codex 設定

## 目的與入口

在 Agent 設定選擇 Codex，管理其支援的 Skills、MCP、Settings 與其他 CLI 資源。

## 角色與允許操作

沿用 Agent 設定的 Workspace 與 sensitive-settings operations。

## 核心概念

Codex provider 有自己的 agent runtime 名稱與設定位置；Frontend 使用 provider id，不以顯示文字判斷。

## 主要流程

選擇資源與 scope、載入、驗證並以 revision 儲存。

## 畫面狀態與唯讀行為

畫面分別處理 loading、empty、error 與 denied。只有讀取操作時保留可讀內容與一般變更控制項，但停用變更並顯示 i18n 原因；缺少讀取操作時不啟動受保護 query、Provider 或即時連線。

## 限制、失敗與安全

外部路徑、非目錄與 symlink conflict 必須 fail closed，不能覆寫。

## 原始碼依據

- `workspace-runtime/app/modules/cli_settings/`
- `frontend/src/features/workspace/features/agent-settings/`

## 相關架構與 API

- [agent-runtime-terminology](/architecture/backend/workspace-runtime/agent-runtime-terminology)
- [runtime-api](/api/runtime-api)
