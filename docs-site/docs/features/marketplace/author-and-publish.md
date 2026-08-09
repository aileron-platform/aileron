---
title: 製作與發佈
---

# 製作與發佈

## 目的與入口

platform admin 由套件 editor 製作內容、管理檔案與版本控制，並發佈 catalog 版本。

## 角色與允許操作

內容寫入與發佈都是 admin-only platform operation。

## 核心概念

draft、revision、working tree 與 published package 分離；儲存各文件不代表整包已發佈。

## 主要流程

建立或開啟 draft、編輯檔案、解決 revision conflict、提交與發佈。

## 畫面狀態與唯讀行為

畫面分別處理 loading、empty、error 與 denied。只有讀取操作時保留可讀內容與一般變更控制項，但停用變更並顯示 i18n 原因；缺少讀取操作時不啟動受保護 query、Provider 或即時連線。

## 限制、失敗與安全

發布前驗證 manifest、路徑與 provider；衝突不得靜默覆寫。

## 原始碼依據

- `frontend/src/features/marketplace/features/marketplace-editor/MarketplaceEditorPage.tsx`
- `workspace-manager/app/modules/marketplace/`
- `packages/aileron-marketplace-core/`

## 相關架構與 API

- [version-control](/architecture/overview/version-control)
- [manager-api](/api/manager-api)
