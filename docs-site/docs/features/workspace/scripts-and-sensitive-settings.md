---
title: 腳本與敏感設定
---

# 腳本與敏感設定

## 目的與入口

由 Workspace 設定或容器管理進入，管理 setup script、環境變數與其他可能含秘密的值。

## 角色與允許操作

讀取要求 `workspace.sensitive_settings.read`，變更要求 `workspace.sensitive_settings.manage`。

## 核心概念

顯示值、遮蔽值、write-only secret 與 execution result 必須分離。

## 主要流程

通過 read gate 後載入；儲存以 revision 防止覆寫，腳本執行另回報結果。

## 畫面狀態與唯讀行為

畫面分別處理 loading、empty、error 與 denied。只有讀取操作時保留可讀內容與一般變更控制項，但停用變更並顯示 i18n 原因；缺少讀取操作時不啟動受保護 query、Provider 或即時連線。

## 限制、失敗與安全

秘密不寫入 log、toast 或文件；缺少 read operation 時不能先載入再遮蔽。

## 原始碼依據

- `frontend/src/features/workspace/features/workspace-settings/`
- `frontend/src/features/workspace/features/container-management/`
- `workspace-manager/app/modules/workspace/`
- `workspace-runtime/app/modules/internal/`

## 相關架構與 API

- [identity-and-access](/architecture/overview/identity-and-access)
- [manager-api](/api/manager-api)
- [runtime-api](/api/runtime-api)
