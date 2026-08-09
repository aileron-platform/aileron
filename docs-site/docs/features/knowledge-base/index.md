---
title: 知識庫（Knowledge Base）
---

# 知識庫（Knowledge Base）

## 目的與入口

知識庫中心管理可跨 Workspace 使用的檔案與版本內容，入口為 `/knowledge-base`。

## 角色與允許操作

平台 member 可列出與建立；resource reader 可讀 detail，manager 可管理內容／設定／分享，owner 可永久刪除。

## 核心概念

知識庫資源、Git repository、分享來源與 Workspace usage 分離；掛載 mutation 屬於 Workspace 設定。

## 主要流程

建立知識庫、管理檔案與版本、設定分享，再由 Workspace 設定掛載。

## 畫面狀態與唯讀行為

畫面分別處理 loading、empty、error 與 denied。只有讀取操作時保留可讀內容與一般變更控制項，但停用變更並顯示 i18n 原因；缺少讀取操作時不啟動受保護 query、Provider 或即時連線。

## 限制、失敗與安全

刪除前檢查 owner 與 Workspace usage；public 存取只授予 reader，不授予寫入。

## 原始碼依據

- `frontend/src/features/knowledge-base/KnowledgeBaseModule.tsx::KnowledgeBaseModule`
- `frontend/src/features/knowledge-base/routes/KnowledgeBaseDetailRoute.tsx::KnowledgeBaseDetailRoute`
- `workspace-manager/app/modules/knowledge_base/`

## 相關架構與 API

- [identity-and-access](/architecture/overview/identity-and-access)
- [manager-api](/api/manager-api)
