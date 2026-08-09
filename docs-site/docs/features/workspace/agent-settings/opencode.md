---
title: OpenCode 設定
---

# OpenCode 設定

## 目的與入口

在 Agent 設定選擇 OpenCode，管理其支援的 CLI 設定資源。

## 角色與允許操作

沿用 Agent 設定的 Workspace 與 sensitive-settings operations。

## 核心概念

OpenCode 的檔名、scope 與可用資源由 Runtime adapter 定義，不套用 Claude Code 路徑。

## 主要流程

選擇資源與 scope、載入、驗證並儲存。

## 畫面狀態與唯讀行為

畫面分別處理 loading、empty、error 與 denied。只有讀取操作時保留可讀內容與一般變更控制項，但停用變更並顯示 i18n 原因；缺少讀取操作時不啟動受保護 query、Provider 或即時連線。

## 限制、失敗與安全

provider 不支援的資源不顯示，也不啟動 query。

## 原始碼依據

- `workspace-runtime/app/modules/cli_settings/`
- `frontend/src/features/workspace/features/agent-settings/`

## 相關架構與 API

- [agent-runtime-terminology](/architecture/backend/workspace-runtime/agent-runtime-terminology)
- [runtime-api](/api/runtime-api)
