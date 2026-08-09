---
title: 使用情況與容量
---

# 使用情況與容量

## 目的與入口

由知識庫詳情查看被哪些 Workspace 使用及目前容量；掛載與解除掛載仍回到 Workspace 設定。

## 角色與允許操作

detail reader 可查看一般使用資訊；治理與容量操作依 platform-resource 或 knowledge-base management operations。

## 核心概念

Workspace usage、有效 quota、容量 observation 與 platform risk 是不同資料。

## 主要流程

載入使用 Workspace 與容量摘要；需要變更掛載時導向對應 Workspace 設定。

## 畫面狀態與唯讀行為

畫面分別處理 loading、empty、error 與 denied。只有讀取操作時保留可讀內容與一般變更控制項，但停用變更並顯示 i18n 原因；缺少讀取操作時不啟動受保護 query、Provider 或即時連線。

## 限制、失敗與安全

stale 容量不可當作即時值；刪除前必須顯示仍在使用的 Workspace。

## 原始碼依據

- `frontend/src/features/knowledge-base/routes/KnowledgeBaseDetailRoute.tsx`
- `workspace-manager/app/modules/knowledge_base/`
- `workspace-manager/app/modules/platform_resource_analytics/`

## 相關架構與 API

- [platform-resource-observability](/architecture/overview/platform-resource-observability)
- [workspace-settings](/features/workspace/workspace-settings)
- [manager-api](/api/manager-api)
