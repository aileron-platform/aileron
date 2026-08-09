---
title: 平台總覽
---

# 平台總覽

## 目的與入口

平台總覽集中說明跨產品權限、角色、資源統計與容量治理；入口包含平台資源頁及各產品的授權狀態。

## 角色與允許操作

平台 member 可使用一般產品；platform admin 另可使用使用者管理、平台資源與治理操作。實際資格以 platform `allowedOperations` 為準。

## 核心概念

`PlatformRole`、`OperationId` 與平台資源觀測是三個不同概念：角色展開操作，觀測提供資源事實，治理再依事實做判斷。

## 主要流程

登入後由 `/api/v1/oauth2/session` 取得平台操作；Global Navigation 只顯示可進入的產品，平台資源頁再載入管理或分析資料。

## 畫面狀態與唯讀行為

畫面分別處理 loading、empty、error 與 denied。只有讀取操作時保留可讀內容與一般變更控制項，但停用變更並顯示 i18n 原因；缺少讀取操作時不啟動受保護 query、Provider 或即時連線。

## 限制、失敗與安全

平台狀態不可由 JWT 或前端角色表推導；觀測資料過期時必須顯示 stale／unknown，不能當成正常。

## 原始碼依據

- `frontend/src/app/AppRouter.tsx::AppRouter`
- `frontend/src/app/components/navigation/GlobalNavigation.tsx`
- `workspace-manager/app/modules/authorization/operation_policy.py`
- `workspace-manager/app/modules/platform_resource_analytics/`

## 相關架構與 API

- [identity-and-access](/architecture/overview/identity-and-access)
- [platform-resource-observability](/architecture/overview/platform-resource-observability)
- [manager-api](/api/manager-api)
