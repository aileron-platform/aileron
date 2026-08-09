---
title: 應用市集（Marketplace）
---

# 應用市集（Marketplace）

## 目的與入口

應用市集是瀏覽、安裝、編輯與治理套件的產品面，入口為 `/marketplace/packages`。

## 角色與允許操作

member 與 admin 可瀏覽、匯出及安裝；發佈、內容管理、刪除與 Registry 管理限定 admin。

## 核心概念

catalog package、provider、user copy、draft 與 registry source 是不同實體。

## 主要流程

從 catalog 選擇套件，安裝為使用者副本；admin 可開啟 editor 編輯並發佈。

## 畫面狀態與唯讀行為

畫面分別處理 loading、empty、error 與 denied。只有讀取操作時保留可讀內容與一般變更控制項，但停用變更並顯示 i18n 原因；缺少讀取操作時不啟動受保護 query、Provider 或即時連線。

## 限制、失敗與安全

clone/import 失敗需維持明確狀態；display-only 重複合併不能取代 canonical identity 修正。

## 原始碼依據

- `frontend/src/features/marketplace/MarketplaceModule.tsx::MarketplaceModule`
- `frontend/src/features/marketplace/model/marketplacePermissions.ts::resolveMarketplacePermissions`
- `workspace-manager/app/modules/marketplace/`
- `packages/aileron-marketplace-core/`

## 相關架構與 API

- [frontend](/architecture/frontend/)
- [manager-api](/api/manager-api)
