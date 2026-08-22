---
title: Terminal
---

# Terminal

## 目的與入口

由 AI Agent／Terminal 或容器管理進入，建立可重連、保留目前工作目錄的互動式 shell session。

## 角色與允許操作

Terminal 使用要求 `workspace.terminal.use`；敏感容器設定另要求 sensitive-settings operations。

## 核心概念

Terminal session、連線與 tab 是不同概念；同一 session 的連線共享 shell 狀態與最後確認的 working directory。

## 主要流程

建立 session、附加 WebSocket、執行命令；prompt 恢復時更新 working directory，重連或重啟沿用最後確認值。

## 畫面狀態與唯讀行為

畫面分別處理 loading、empty、error 與 denied。只有讀取操作時保留可讀內容與一般變更控制項，但停用變更並顯示 i18n 原因；缺少讀取操作時不啟動受保護 query、Provider 或即時連線。

## 限制、失敗與安全

無效 working directory 才回到 Workspace 預設路徑；斷線不等於刪除 session。

## 原始碼依據

- `frontend/src/features/workspace/features/container-management/`
- `workspace-runtime/app/modules/internal/router.py`
- `workspace-terminal/`

## 相關架構與 API

- [workspace-runtime](/architecture/backend/workspace-runtime/)
- [runtime-api](/api/runtime-api)
