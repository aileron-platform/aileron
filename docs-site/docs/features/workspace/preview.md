---
title: 預覽畫面
---

# 預覽畫面

## 目的與入口

由 Workspace 的「預覽畫面」進入，用於查看 Web 應用輸出；Canvas 類型的互動表面稱為「網頁畫布」。

## 角色與允許操作

入口要求 `workspace.detail.read`；發佈與互動仍受 Runtime availability、route 與 Canvas contract 限制。

## 核心概念

預覽畫面是產品功能名稱；Web Canvas 是表面；Canvas 是 manifest、bridge 與程式契約識別。

## 主要流程

偵測 manifest、選擇 route、啟動預覽；需要發佈時使用固定 user resource 的 publishing flow。

## 畫面狀態與唯讀行為

畫面分別處理 loading、empty、error 與 denied。只有讀取操作時保留可讀內容與一般變更控制項，但停用變更並顯示 i18n 原因；缺少讀取操作時不啟動受保護 query、Provider 或即時連線。

## 限制、失敗與安全

contentDir 必須限制在 managed root；無 manifest、build 失敗或 route 無效時顯示可診斷狀態。

## 原始碼依據

- `frontend/src/features/workspace/features/canvas/`
- `workspace-runtime/app/modules/canvas/`
- `workspace-runtime/app/modules/canvas/publishing.py`

## 相關架構與 API

- [protocol](/architecture/overview/canvas/protocol)
- [publishing](/architecture/overview/canvas/publishing)
- [runtime-api](/api/runtime-api)
