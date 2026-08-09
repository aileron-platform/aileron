---
title: 容器管理
---

# 容器管理

## 目的與入口

由 Workspace 的容器管理進入，查看 Runtime、Terminal 與防火牆相關狀態。

## 角色與允許操作

Runtime／敏感設定使用 sensitive-settings operations；防火牆讀取與變更分別使用 `workspace.firewall.read/manage`。

## 核心概念

desired firewall、observed firewall、Runtime generation 與 Terminal session 是不同狀態。

## 主要流程

讀取目前狀態、提交設定變更並等待 observed state；Terminal 另以 session 流程建立。

## 畫面狀態與唯讀行為

畫面分別處理 loading、empty、error 與 denied。只有讀取操作時保留可讀內容與一般變更控制項，但停用變更並顯示 i18n 原因；缺少讀取操作時不啟動受保護 query、Provider 或即時連線。

## 限制、失敗與安全

Runtime unavailable 時停用操作；不得把敏感環境變數回傳給無 read operation 的使用者。

## 原始碼依據

- `frontend/src/features/workspace/features/container-management/`
- `workspace-manager/app/modules/workspace/firewall.py`
- `workspace-runtime/app/modules/internal/`
- `workspace-runtime/app/modules/internal/router.py`

## 相關架構與 API

- [execution-plane](/architecture/overview/execution-plane)
- [manager-api](/api/manager-api)
- [runtime-api](/api/runtime-api)
