---
title: 資源統計與容量
---

# 資源統計與容量

## 目的與入口

平台管理員由「平台資源」進入 Workspace／知識庫管理與分析頁，查看目前分布、期間趨勢、容量風險與擴充要求。

## 角色與允許操作

讀取與治理使用 platform-resource Operation ID，均限定 platform admin；畫面不能以隱藏按鈕取代 Manager 授權。

## 核心概念

Observation 是時間點事實；risk 是 Manager 依門檻與 freshness 的判定；expansion request 只有 observed capacity 達標才 completed。

### 機器契約識別碼

- 期間：`7d`、`30d`、`90d`
- 儲存種類：`workspace_data`、`runtime_home`、`knowledge_base`
- Workspace 狀態群組：`running`、`transitioning`、`stopped`、`error`
- 容量風險：`normal`、`warning`、`critical`、`unknown`、`stale`
- 端點：`/platform-resources/workspaces/statistics/summary`、`/platform-resources/workspaces/statistics/resource-trend`、`/platform-resources/workspaces/statistics/capacity-trend`
- 端點：`/platform-resources/knowledge-bases/statistics/summary`、`/platform-resources/knowledge-bases/statistics/resource-trend`、`/platform-resources/knowledge-bases/statistics/capacity-trend`
- 端點：`/platform-resources/knowledge-bases/{knowledgeBaseId}/quota`、`/platform-resources/workspaces/{workspaceId}/capacity-expansions`、`/workspaces/{workspaceId}/capacity`、`/internal/workspaces/{workspaceId}/resource-telemetry/batches`

## 主要流程

切換管理／分析與 Workspace／知識庫範圍，選擇期間後讀取摘要與趨勢；治理操作建立 durable request 並等待收斂。

## 畫面狀態與唯讀行為

畫面分別處理 loading、empty、error 與 denied。只有讀取操作時保留可讀內容與一般變更控制項，但停用變更並顯示 i18n 原因；缺少讀取操作時不啟動受保護 query、Provider 或即時連線。

## 限制、失敗與安全

資料來源、期間、時區、freshness 與 unknown/stale 必須可見；個別區塊失敗不應抹除其他已成功資料。

## 原始碼依據

- `frontend/src/features/platform-resources/PlatformResourcesModule.tsx::PlatformResourcesModule`
- `frontend/src/features/platform-resources/data-session/usePlatformResourcesDataSession.ts`
- `workspace-manager/app/modules/platform_resource_analytics/`
- `workspace-manager/app/modules/platform_resource_capacity/`

## 相關架構與 API

- [platform-resource-observability](/architecture/overview/platform-resource-observability)
- [manager-api](/api/manager-api)
