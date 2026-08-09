---
title: 工作區設定
---

# 工作區設定

## 目的與入口

由 Workspace 設定進入，管理基本資料、存取、知識庫掛載與重設。知識庫 mount/unmount 的 canonical 流程在此頁。

## 角色與允許操作

基本讀取要求 detail read；metadata、access、attachment 與 lifecycle 各用對應 manage/execute Operation ID。

## 核心概念

設定子頁依資料敏感度分別 gate；知識庫中心只顯示使用關係，不擁有掛載 mutation。

## 主要流程

選擇子頁、確認 operation 後才載入；掛載知識庫時更新 Workspace attachment desired state 並等待收斂。

## 畫面狀態與唯讀行為

畫面分別處理 loading、empty、error 與 denied。只有讀取操作時保留可讀內容與一般變更控制項，但停用變更並顯示 i18n 原因；缺少讀取操作時不啟動受保護 query、Provider 或即時連線。

## 限制、失敗與安全

重設與解除掛載可能影響 Runtime；執行前顯示影響範圍並保留 durable 失敗狀態。

## 原始碼依據

- `frontend/src/features/workspace/features/workspace-settings/WorkspaceSettingsPage.tsx::WorkspaceSettingsPage`
- `workspace-manager/app/modules/workspace/`
- `workspace-manager/app/modules/knowledge_base/`

## 相關架構與 API

- [execution-plane](/architecture/overview/execution-plane)
- [manager-api](/api/manager-api)
