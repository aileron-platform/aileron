---
title: AI Chat 前後端架構
---

# AI Chat 前後端架構

本頁說明 Aileron AI Chat 從前端送出訊息、Workspace Runtime 執行 Agent、事件持久化、WebSocket 同步，到前端組合與顯示時間軸的完整機制。內容同時作為工程師的架構導覽，以及 AI 在分析或修改程式前應建立的共同心智模型。

## 架構總覽

| 面向 | 現行機制 |
|---|---|
| History 單位 | Timeline Message Item |
| History API | `/timeline?beforeSequence=...` |
| Tool result | DB typed sidecar，由 tool-call item hydrate |
| Realtime | `timeline_updated` 的 created／changed item invalidation |
| Frontend cache | 單一 timeline infinite query，最多 500 items |
| Virtualization | Timeline presentation group；大型 Activity 局部 DOM virtualization |
| UI 語意 | Agent response、Activity、Thinking 與 tool cards 的目前 presentation contract |

AI Chat 入口與每次執行都要求後端 `allowedOperations` 包含 `workspace.agent_chat.use`，因此有效資源角色至少為 Manager，或由 Platform Admin 取得受稽核的 manager override。缺少操作時不顯示 Chat 導覽，也不掛載 Chat Provider、query、WebSocket 或 session。operation 撤銷後，前端立即停止連線並清除 cached Runtime URL；一般 bearer request 仍逐次通過 `runtime-access` revalidation，Manager 也會提升 generation，使失效的 internal signed assertion 與執行中的 Agent session 終止。

## 核心名詞

| 名詞 | 定義 | 是否為分頁單位 |
|---|---|---|
| Thread | 一段可持續多次提問的 AI Chat；Automation 的每次有效 execution 也會建立自己的 Thread。 | 否 |
| Turn | 一次已接受的使用者意圖，從 user message 開始，到對應 Agent execution 進入 terminal status。Retry／resume 可在同一 Turn 產生新的 Turn Execution。 | 否 |
| Turn Execution | 一次 Claude、Codex 或 OpenCode runner invocation。`agent_resume_id` 只用於接續 provider session，不是 Thread、Turn 或 cursor。 | 否 |
| Raw Message | `thread_messages` 中的一筆 append-only event，例如 user、agent text、thinking、tool call、tool result、system、git diff 或 error。 | 否 |
| Timeline Message Item | API、cache 與 history pagination 單位。一般 raw message 對應一個 item；工具互動以 `tool_call` 為 item anchor，results 是 sidecars。 | **唯一分頁單位** |
| Presentation Row | 前端把已載入 items 組成的可視列，例如訊息、Activity、Thinking 或 tool card。它只存在前端，沒有 API、cursor 或獨立 cache。 | 否 |

Turn Execution 與接續對話用的 Agent Resume ID、目前執行用的 Active Turn Execution ID 屬於不同概念；完整的 ID 對照與正規化規則請見 [Agent Runtime 名詞對照](/architecture/backend/workspace-runtime/agent-runtime-terminology)。

一個問題加上 1,000 個 Agent／工具回應仍是 **1 Turn**，但可能有 1,001 個以上 Raw Messages 與相近數量的 Timeline Message Items。因此效能上限不能只看 Turn 數量。

## 整體元件與資料流

```text
AI Chat Workbench / Automation Execution Detail
  │
  │ REST：Thread metadata、history、mutation、完整 tool result
  │ WebSocket：已提交資料的 invalidation hint
  ▼
Workspace Runtime - Thread Router / Thread Service
  │
  ├─ private _ThreadExecution / AgentRunner seam
  │    ├─ Claude SDK adapter → Claude Event Mapper
  │    ├─ Codex SDK adapter  → Codex Event Mapper
  │    └─ OpenCode ACP adapter → OpenCode Event Mapper
  │
  ├─ Canonical AgentEvent
  │    └─ text / thinking / tool_call / tool_result / lifecycle
  │
  ├─ Thread / Turn / Execution / Message Repositories
  │
  ▼
PostgreSQL
  ├─ threads
  ├─ thread_turns
  ├─ thread_turn_executions
  ├─ thread_messages
  └─ thread_tool_result_contents
```

Workspace Manager 不負責一般 AI Chat 的訊息內容。它管理 workspace 與 Automation execution lifecycle；Automation 真正進入 Agent 流程後，由 Workspace Runtime 建立或解析對應 Thread，底部對話仍走相同的 Runtime timeline。

## 寫入流程

1. 前端建立 draft Thread，或對已建立的 Thread 呼叫 `submit`／`messages` mutation。附件先存入 Thread attachment storage，訊息只保存受控的 attachment reference。
2. Runtime 驗證 workspace、Thread ownership／origin 與目前 lifecycle，建立或沿用 Logical Turn，並為這次 runner invocation 建立 Turn Execution。
3. Runtime 啟動選定的 Claude、Codex 或 OpenCode runner。各 provider mapper 先把 SDK／ACP 原生事件正規化為共用 `AgentEvent`。
4. `ThreadService` 透過 private `_ThreadExecution` 與 `AgentRunner` 協調執行；canonical event persistence 將事件寫入 append-only `thread_messages`，同步更新 Thread／Turn／Execution lifecycle。Tool result 必須先以 execution-scoped tool key 找到 tool call，才能保存 parent relation。
5. Tool result 的 timeline preview 保持 bounded；超出 preview 的完整 bytes 存在 `thread_tool_result_contents`。使用者按下 Show all 時，才以 result message id 讀取完整內容。
6. Runtime 只在 event transaction commit 後排程 coalesced WebSocket invalidation；rollback 不會送出 phantom ids 或 metadata。WebSocket 不是 durable event log，前端收到後仍透過 REST 取得 authoritative state。

## Stop（停止目前 Turn）

```http
POST /api/v1/threads/{threadId}/stop
```

- Stop 只停止目前 active Turn，不是取消整個 Thread；已產生的 partial output 保留，該 Turn／Turn Execution 標記為 canceled。
- Runtime 先將 Thread 標為 `stopping` 並廣播 `status_updated`，接著要求 provider runner 停止並**確認 runner 已結束**，最後才在同一原子步驟內把該 Turn 標為 canceled，並在 FIFO queue 有下一則訊息時直接接續啟動為新 Turn；queue 為空則 Thread 結束為 `canceled`。
- 是否接續下一則訊息與正常完成（`complete` event）時的 dequeue 共用同一段 finish-and-handoff 邏輯，兩者行為一致。
- Runner 停止失敗或逾時、且 runner 仍存活時，Thread 維持 `stopping`、queue 原封不動、不啟動下一 Turn，回傳可重試的錯誤；runner 回報停止時丟錯但已確認不存活，仍視為安全並完成 handoff。
- 對同一個 active execution 重複呼叫 Stop 是冪等的，不會重複 dequeue 或建立 Turn。
- Thread 在 `stopping` 期間收到的新訊息，行為與其他 running 狀態相同：加入 queue 尾端，不會被立即執行。

## 持久化與配對保證

`thread_messages` 是唯一 append-only 訊息事實來源。Thread、Turn 與 Turn Execution 保存 lifecycle／grouping metadata，不把 provider 原始 session id 當成第一方主鍵。

- `tool_call_key` 在同一 Turn Execution 內識別一個 call。
- `tool_result.parent_tool_use_id` 指向自己的 `tool_call` message DB id。
- 找不到 parent call 的 result 必須 fail fast，不能建立 orphan result 或默默配到最近的 call。
- Nested tool 只有在 provider 明確提供 parent identity 時才建立關聯；不可依名稱、時間相鄰或陣列位置猜測。
- 只對 provider-backed tool call／result、Question answer 與 upstream 提供 reliable identity 的 events 要求 deterministic `source_event_key`：相同 event replay 為 no-op，相同 key 但 canonical payload 不同視為 conflict。沒有 durable id 的 Codex plan notification 每次保留為 distinct occurrence，不承諾 mapper restart replay 去重。
- 每筆 append 在同一 transaction 鎖定 Thread row，鎖定後重查 reliable source key，再以已有 index 計算 `MAX(message_sequence) + 1`。`threadVersion` 只用於 realtime metadata，不是 history cursor。

### Call-anchored Message Item

系統不把 `tool_result` 當成可見 timeline row：

```text
Raw persistence
  tool_call ────────────────┐
  tool_result (provider) ───┼─► Tool Timeline Item
  tool_result (answer) ─────┘    anchor = tool_call
```

- `tool_call` 是工具互動唯一的 presentation anchor，決定 item 的固定 `sequence` 與 scroll identity。
- `tool_result` 仍是 append-only DB row，但只以 typed sidecar hydrate 回原 tool item。
- `result_kind` 只有 `provider_result` 與 `interaction_answer`，同一 parent 的每種 kind 最多一筆。Question 可合法同時有「等待使用者輸入」的 provider result，以及送出答案後的 interaction answer；畫面仍只有同一張 Question card。
- 一般 item 的 `itemVersion` 等於自己的 message sequence；tool item 的 `itemVersion` 是 call 與相關 results 的最大 sequence。Result 到達只提高版本，不移動 anchor。
- 完整 result 由 message-id detail endpoint 讀取；history page 不攜帶無界限內容。

## 讀取與分頁

### Timeline 契約

```http
GET /api/v1/threads/{threadId}/timeline?limit=100
GET /api/v1/threads/{threadId}/timeline?beforeSequence=1002&limit=100
```

- `beforeSequence` 是唯一 history cursor，使用 exclusive `<`。
- 預設 100、最大 200 個 presentation anchors；response 一律依 `sequence` 升冪排列。
- Anchor allowlist 明確包含 user、agent text、thinking、tool call、system、system init、git diff 與 error；`tool_result` 不在 allowlist。
- Backend 先用 partial anchor index 讀 `limit + 1`，再以固定批次 hydrate 本頁 tool results 與本頁引用的 Turn／Execution metadata；不得 N+1，也不得為補完整 Turn 或 tool tree 擴張頁面。
- Cache 最多 5 頁、預設 500 items。

Realtime 更新已知 items 使用 bounded batch-get：

```http
POST /api/v1/threads/{threadId}/timeline/items/batch-get
```

它最多接收 200 個既知 anchor ids，只回相同的 item projection；沒有 cursor、next page 或獨立 cache，因此不是第二個 history pagination layer。

## Realtime、cache 與 reconnect

| 情境 | 現行行為 |
|---|---|
| 新訊息／tool call | `createdItemIds` 經 bounded batch-get 合併進 latest cache window |
| Tool result 到達 | Parent call 放入 `changedItemIds`，只 patch cache 中已載入的同一 tool item |
| 使用者停在歷史中段 | 顯示未讀更新，不強制跳底；回到底部才清除提示 |
| WebSocket 重連 | 重抓固定 latest page，REST 恢復 authoritative state |
| Invalidation payload overflow | 送 `refreshLatest: true`，不傳無界限 id 清單 |

WebSocket 事件名稱為 `timeline_updated`，包含 bounded `createdItemIds`、`changedItemIds` 與本次引用的 Turn／Execution metadata。事件只是一個 invalidation hint：漏掉事件不影響歷史正確性，前端可由 latest page、bounded batch refresh 與 `beforeSequence` 恢復狀態，不需要 replay log 或 outbox。

## 向上捲時的 Result、Use、Think 順序

Raw DB 依 sequence 倒序讀取時，可能依序遇到：

```text
102 tool_result
101 tool_call / use
100 thinking
```

History query 會排除 `102 tool_result` anchor，因此使用者第一次看到的是一張以 `101 tool_call` 為 anchor、已 hydrate result 的 card：

```text
Tool card [Use header → Result preview]
```

載入下一個更早 page 的 `100 thinking` 後，前端依升冪 sequence 重組為：

```text
Think → 同一張 Tool card [Use header → Result preview]
```

畫面不會出現 standalone Result、不會先顯示 Result 再補 Use，也不會因 Think prepend 而重建 tool card。若後方已有 final text，Think 與 tool card 仍位於 final text 前的 Activity；尚無 final text 時則各自是可 virtualize 的 agent-part rows。向上捲只載入使用者要求的更早 page，不為補齊未載入的 Think 或 nested parent 自動跨頁查詢。

Claude 與 OpenCode 有正式 Thinking／thought event，可驗證完整順序；Codex 目前沒有 persisted reasoning item，因此只顯示 Use＋Result，不得虛構 Think。

## 前端組合與 UI 不變條件

`toTimelinePresentation()` 直接讀取 hydrated tool item，並將連續 thinking、agent text 與 top-level tools 組成一個 Agent response。`ThreadMessageItem` 將最後一段 Agent text 直接顯示，前面的 parts 放入 Activity。資料分頁調整**不得有意改變目前訊息 presentation contract**：

- 連續 Agent parts 視覺上仍是一個 Agent response，不拆成零散聊天泡泡。
- Final text 前的工具與思考仍放在「處理中／已完成」Activity；Activity 預設收合。
- Activity 展開後，各個 Thinking 仍有自己的內層展開／收合與標題 contract。
- Question／Canvas 必須保持可見、可操作，不可被 Activity 預設隱藏。
- Tool card 必須保留 structured `parameters`、專用 renderer、Use header 在 Result preview 之前的順序，以及 Show all 行為。
- Nested parent／child 都已載入時維持 parent card 內呈現；缺一端時不遞迴補抓整棵 tree，也不新增 breadcrumb UI。
- Files Changed 的區塊與 Turn 內顯示語意保持不變。
- Older prepend 要保留第一個可見 row 與 offset；只有使用者位於底部時才跟隨新訊息。

`toTimelinePresentation()` 只根據目前 cache 中已載入且連續的 items 產生 presentation group。Presentation grouping 不進 DB、不進 API，也沒有自己的 cursor。

頂層 `ThreadTimeline` virtualize 已載入的 presentation groups，cache 固定最多 500 items。Collapsed Activity 不 mount children；展開 Activity 超過 50 parts 時使用局部 part virtualizer並保留現有 `50dvh` 內層捲動。這個局部 virtualizer沒有 query、cache 或 cursor，只限制 DOM，**不是第二層分頁**。

## 三 Agent 正規化邊界

| Agent | 正式工具 identity | Thinking | Parent 規則 |
|---|---|---|---|
| Claude SDK | `ToolUseBlock.id`／`ServerToolUseBlock.id` 與 result 的 `tool_use_id` | 有正式 thinking | SDK 明確提供 `parent_tool_use_id` 時才保存 |
| Codex SDK | command、MCP、web search 的 `item.id` | 目前不持久化 reasoning | 現有 types 不猜 parent；無 durable id 的 plan notification 每次都是 distinct occurrence |
| OpenCode ACP | `tool_call_id` | 有 thought event | 現有 ACP update 不猜 parent；process-local seen set 只能是最佳化 |

三條 mapper 都必須輸出相同 canonical tool contract：對有 reliable upstream identity 的 tool events 產生穩定 event key、讓 call/result 共用 tool key、維持 call-before-result、只將 terminal result 標記為 result phase，並且只在 provider 明確提供時保存 parent key。Codex plan notification 仍是沒有 durable identity 的明確例外。正常 callback 中由 mapper 保證 call 在 result 前；跨 callback 找不到 call 時由 adapter fail fast。設計上不使用 placeholder、pending-result inbox 或 reconciliation worker。

## AI Chat 與 Automation 的共用邊界

- 一般 AI Chat Thread 由使用者擁有；Automation Thread 由 Manager automation execution lookup，並使用 workspace member access。
- 每筆真正進入 Agent 流程的 Automation execution 擁有獨立 Runtime Thread，不把多次排程執行合併成 job-level conversation。
- Automation Execution Detail 上方 lifecycle 來自 Workspace Manager；下方 Agent 對話來自 Workspace Runtime。
- AI Chat Workbench 與 Automation Execution Detail 共用 `ThreadTimeline`、timeline endpoint、query/cache、presentation compositor 與 renderer；Automation 另外保留 Manager lifecycle 及 automation-execution-to-thread lookup。

## 必守效能與實作邊界

現行架構的必要 invariant：

1. 1 Turn／1,001 items 的初次 response 最多 100 items；cache 預設最多 500 items。
2. 100 calls 後接 100 results，latest page 仍回 100 個 hydrated tool items，不是空頁或 100 個 orphan results。
3. Result realtime update 不增加 row count、不改 call sequence，也不重傳完整 Turn。
4. Page query 數量固定，不隨本頁 tool 數量增加；collapsed／expanded UI 的 mounted DOM 都只跟 viewport 與 overscan 成長。
5. 系統只有 `beforeSequence` 一個 history cursor；沒有 Turn history、result 子分頁或跨頁 tree fetch。

設計上刻意不引入 message watermark、`asOfSequence` snapshot protocol、mutable projection table、pending inbox、durable event log／outbox、所有文字的 semantic hash、通用 nested-tree virtualizer 或新 breadcrumb UI；只有量測或正式 provider capture 證明需要時才會考慮加入。

## 程式索引

| 範圍 | 主要路徑 |
|---|---|
| Runtime Thread interface | `workspace-runtime/app/modules/thread/router.py`、`lifecycle.py::ThreadService`、`execution.py::_ThreadExecution` |
| Persistence／tool pairing | `workspace-runtime/app/modules/thread/message_repository.py`、`repository.py`、`turn_repository.py` |
| 三 Agent mapper／adapter | `workspace-runtime/app/modules/thread/claude_sdk_event_mapper.py`、`codex_sdk_event_mapper.py`、`opencode_acp_event_mapper.py` 與對應 `*_agent_runner.py` |
| WebSocket invalidation | `workspace-runtime/app/modules/thread/invalidation_emitter.py`、`websocket/router.py` |
| Frontend query／realtime | `frontend/src/features/ai-chat/hooks/`、`frontend/src/features/ai-chat/realtime/` |
| Frontend timeline／composition | `frontend/src/features/ai-chat/components/messages/` |
| Automation viewer | `frontend/src/features/workspace-automation/components/execution/ExecutionDetailDialog.tsx` |

### 設計原則

1. 系統只有單一 Message Item 分頁；沒有 Turn history API 或獨立的 turn 更新事件。
2. Tool result 是 raw persistence event，但在 UI 中不是獨立 row；不要由 raw sequence 推導畫面一定 Result-first。
3. Turn 是 lifecycle boundary，不是效能或 pagination boundary；單一 Turn 可以有大量 items。
4. Frontend grouping 是 loaded-only derived presentation，不是第二個資料模型，也不可為了組完整 Activity 自動抓取未載入 history。
5. 任何三 Agent 變更都必須走 canonical mapper → `AgentRunner` seam → persistence → timeline 的共用路徑；不可只替單一 provider 或 Automation 建立旁路。
6. 資料層調整不能被用來改版現有 UI；Activity、Thinking、Question／Canvas、tool cards 與 Files Changed 都是必要產品語意。
