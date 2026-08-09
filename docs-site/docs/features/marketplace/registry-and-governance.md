---
title: Registry 與治理
---

# Registry 與治理

## 目的與入口

platform admin 由 Marketplace Settings 管理 Registry、SSH 金鑰、版本控制與活動紀錄。

## 角色與允許操作

Registry 與治理操作限定 admin；未通過 operation 前不啟動 registry query。

## 核心概念

registry source、同步狀態、package identity 與 audit record 分離。

## 主要流程

新增或更新 registry、驗證連線、同步 catalog、檢查活動紀錄。

## 畫面狀態與唯讀行為

畫面分別處理 loading、empty、error 與 denied。只有讀取操作時保留可讀內容與一般變更控制項，但停用變更並顯示 i18n 原因；缺少讀取操作時不啟動受保護 query、Provider 或即時連線。

## 限制、失敗與安全

SSH private key 與 credential 不回顯；同步失敗保留來源與錯誤，不刪除 last-known-good catalog。

## 原始碼依據

- `frontend/src/features/marketplace/features/marketplace-settings/MarketplaceSettingsPage.tsx`
- `workspace-manager/app/modules/marketplace/workflows/registry_operations.py`
- `workspace-manager/app/modules/marketplace/activity_repository.py`

## 相關架構與 API

- [workspace-manager](/architecture/backend/workspace-manager/)
- [manager-api](/api/manager-api)
