---
title: 瀏覽器
---

# 瀏覽器

## 目的與入口

由 Workspace 瀏覽器入口啟動或連接 browser automation session。

## 角色與允許操作

要求 `workspace.browser_automation.use`；缺少操作時不佈建或連線。

## 核心概念

Browser 畫面、Neko WebSocket/WebRTC session、存取 credential generation 與 extension pairing
是不同生命週期。切離 Browser 功能時會完整關閉目前 Neko client；再次進入時必須重新呼叫
`POST /api/v1/workspaces/{workspace_id}/browser/access`；client、timer 與 credential 都只屬於該次
可見期間。

Docker Compose 與 Kubernetes 都以 `browserConnectivity` 表示 TURN 路徑狀態。Docker Compose
的安裝層由 Coturn、connectivity-evidence-gateway 與 host frontend vantage 組成；每個執行中
Browser generation 另有同 network namespace 的 connectivity probe。Kubernetes 則由 Operator
管理相同語意的 probe、Gateway 與 CR status projection：

| 狀態 | Admission | 意義 |
| --- | --- | --- |
| `pending` | `denied` | Browser 或 probe 尚未完成觀測 |
| `ready` | `allowed` | backend 與所有 required frontend vantage 都有相符且未過期的 relay 證據 |
| `degraded` | `allowed` | backend 成功；frontend 最新嘗試失敗，但同 producer 與雙 revision 的最後成功仍在 TTL 內 |
| `not_ready` | `denied` | 必要 evidence 缺少、過期、revision 不符或資料路徑失敗 |
| `unavailable` | `denied` | profile、probe 或 evidence service 無法提供權威觀測 |

## 主要流程

Manager 只消費 `browserConnectivity.admission`；`ready`，或仍有有效 evidence 且 projection 為
`allowed` 的 `degraded`，可核發新的 Browser access。Manager 不重新解讀 state 或檢查 expiry；
projection writer 必須在 TTL 到期時改投影為 `not_ready`／`denied`。`pending`／`not_ready` 的
`denied` projection（包括 admission 當下已到期）回傳 `409 BROWSER_CONNECTIVITY_NOT_READY`；
只有 `unavailable` 回傳 `503 BROWSER_CONNECTIVITY_UNAVAILABLE`。Browser 畫面直接顯示
projection 的 state，不自行重算 evidence freshness。畫面取得 access 後建立一個 Neko generation；若 WebSocket、
ICE、WebRTC 或 data channel 失敗，會先關閉整個 generation，再重新取得 access 後建立下一個。
`turnRest` profile 的每次 access 都包含新的短效 `iceServers`，該 generation 的
`RTCPeerConnection` 必須覆寫 Neko startup ICE list；credential 不跨 generation 重用。
Browser session 只有在 Neko WebSocket 已連線、WebRTC 已連線、收到狀態為 `live` 的 video
track，且 data channel 已開啟時才算 ready。任一連線關閉、cleanup 或 video track `ended` 都會
立即清除對應 readiness；頁面或 Workspace URL 可開啟本身不代表 Browser 可用。

Docker Manager 在 Browser／probe lifecycle commit 後立即排入 reconcile，並以 5 秒週期批次
重新讀取 backend probe 與每個 required frontend vantage 的 evidence。HTTP 讀取在資料庫鎖外
執行，寫回時以 Workspace lock、Browser instance 與 container fence 防止舊 generation 覆蓋
新狀態；aggregate `expiresAt` 取所有必要 evidence 的最早值。Evidence Authority 以自己的
`acceptedAt` 計算 `expiresAt`，producer 的 `measuredAt` 只供診斷。每個 producer 與雙 revision
保留最新嘗試及最後成功；不得使用舊 projection 或跨 revision 成功證據形成 `degraded`。
這些欄位會以 typed projection 寫入 Workspace，不儲存 raw evidence
或 Gateway token。

自動恢復一次只允許一個 request，最多五次且總預算兩分鐘；delay 採有 jitter 的 exponential
backoff，單次上限 30 秒。離線時暫停，收到 `online` 後再繼續。用盡預算後才顯示可由使用者
觸發的重試，不會在背景產生無限重連。

## 畫面狀態與唯讀行為

畫面分別處理準備連線、連線中、已連線、恢復中、重試耗盡與 denied。所有訊息使用
`workspace.browser.*` i18n key。只有讀取操作時保留可讀內容與一般變更控制項，但停用變更並
顯示 i18n 原因；缺少讀取操作時不啟動受保護 query、Provider 或即時連線。

## 限制、失敗與安全

`browserConnectivity` 是新 session admission gate，不會主動切斷已建立且仍健康的 WebRTC
session。pairing token 必須短效且 workspace-scoped；Browser access、TURN credential、agent
token 與 Gateway nonce 不得寫入 URL、log、CR status 或文件範例。

## 原始碼依據

- `frontend/src/features/workspace/features/browser/`
- `frontend/src/features/workspace/features/browser/hooks/useBrowserAccessRecovery.ts`
- `workspace-manager/app/modules/workspace/browser_credential_access.py`
- `workspace-manager/app/modules/workspace/browser_connectivity_contract.py`
- `workspace-manager/app/modules/workspace/browser_connectivity_evaluator.py`
- `workspace-manager/app/modules/workspace/browser_connectivity_reconcile.py`
- `workspace-runtime/app/modules/client_browser_relay/`
- `workspace-operator/internal/controller/browser_connectivity.go`
- `workspace-operator/internal/controller/connectivity_evidence_gateway.go`

## 相關架構與 API

- [execution-plane](/architecture/overview/execution-plane)
- [manager-api](/api/manager-api)
- [runtime-api](/api/runtime-api)
