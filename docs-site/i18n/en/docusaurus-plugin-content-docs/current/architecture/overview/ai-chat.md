---
title: AI Chat Frontend and Backend Architecture
---

# AI Chat Frontend and Backend Architecture

This page describes the complete Aileron AI Chat mechanism, from submitting a message in the frontend, running an agent in Workspace Runtime, persisting events, and synchronizing over WebSocket to composing and displaying the frontend timeline. It serves both as an architecture guide for engineers and as the shared mental model an AI should establish before analyzing or modifying the code.

## Architecture Overview

| Aspect | Current mechanism |
|---|---|
| History unit | Timeline Message Item |
| History API | `/timeline?beforeSequence=...` |
| Tool result | DB typed sidecar, hydrated by the tool-call item |
| Realtime | `timeline_updated` created/changed item invalidation |
| Frontend cache | One timeline infinite query, up to 500 items |
| Virtualization | Timeline presentation groups; local DOM virtualization for large Activity groups |
| UI semantics | Current presentation contract for Agent response, Activity, Thinking, and tool cards |

AI Chat entry and every execution require backend `allowedOperations` to contain `workspace.agent_chat.use`, so the effective resource role must be at least Manager or a Platform Admin must receive an audited manager override. Without the operation, Chat navigation is absent and the Chat Provider, query, WebSocket, and session do not mount. When the operation is revoked, the frontend immediately stops connections and clears the cached Runtime URL. Ordinary bearer requests still pass through `runtime-access` revalidation, and Manager increments generation so invalidated internal signed assertions and active Agent sessions terminate.

## Core Terminology

| Term | Definition | Pagination unit? |
|---|---|---|
| Thread | An AI Chat that can continue across multiple user prompts. Every valid Automation execution also creates its own Thread. | No |
| Turn | One accepted user intent, beginning with a user message and ending when the corresponding Agent execution reaches a terminal status. A retry or resume can create a new Turn Execution within the same Turn. | No |
| Turn Execution | One Claude, Codex, or OpenCode runner invocation. `agent_resume_id` is used only to resume a provider session; it is not a Thread, Turn, or cursor. | No |
| Raw Message | One append-only event in `thread_messages`, such as user, agent text, thinking, tool call, tool result, system, git diff, or error. | No |
| Timeline Message Item | The unit of the API, cache, and history pagination. A regular raw message maps to one item. A tool interaction uses `tool_call` as the item anchor and results as sidecars. | **The only pagination unit** |
| Presentation Row | A visible row the frontend derives from loaded items, such as a message, Activity, Thinking, or tool card. It exists only in the frontend and has no API, cursor, or independent cache. | No |

Turn Execution, the Agent Resume ID used to continue a conversation, and the Active Turn Execution ID used for the current run are separate concepts. For the complete identifier mapping and normalization rules, see [Agent Runtime Terminology](/architecture/backend/workspace-runtime/agent-runtime-terminology).

One question followed by 1,000 Agent/tool responses is still **1 Turn**, but it can contain 1,001 or more Raw Messages and a similar number of Timeline Message Items. Performance limits therefore cannot be based only on the number of Turns.

## Components and Data Flow

```text
AI Chat Workbench / Automation Execution Detail
  │
  │ REST: Thread metadata, history, mutations, complete tool result
  │ WebSocket: invalidation hints for committed data
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

Workspace Manager does not own ordinary AI Chat message content. It manages the Workspace and Automation execution lifecycle. Once Automation enters the actual Agent flow, Workspace Runtime creates or resolves the corresponding Thread, and the conversation below it uses the same Runtime timeline.

## Write Flow

1. The frontend creates a draft Thread or calls the `submit`/`messages` mutation on an already-created Thread. Attachments are first stored in Thread attachment storage; the message stores only controlled attachment references.
2. Runtime validates the Workspace, Thread ownership/origin, and current lifecycle, creates or reuses the Logical Turn, and creates a Turn Execution for this runner invocation.
3. Runtime starts the selected Claude, Codex, or OpenCode runner. Each provider mapper first normalizes native SDK/ACP events into a shared `AgentEvent`.
4. `ThreadService` coordinates execution through private `_ThreadExecution` and the `AgentRunner` seam. Canonical event persistence appends events to `thread_messages` and updates the Thread/Turn/Execution lifecycle. A tool result must find its tool call through an execution-scoped tool key before the parent relation can be saved.
5. The timeline preview for a tool result remains bounded. Complete bytes beyond the preview are stored in `thread_tool_result_contents`. The full content is fetched by result message ID only when the user selects Show all.
6. Runtime schedules a coalesced WebSocket invalidation only after the event transaction commits. A rollback never sends phantom IDs or metadata. WebSocket is not a durable event log; after receiving an event, the frontend still retrieves authoritative state through REST.

## Persistence and Pairing Guarantees

`thread_messages` is the single append-only source of truth for messages. Thread, Turn, and Turn Execution store lifecycle/grouping metadata; a provider's raw session ID is not used as a first-party primary key.

- `tool_call_key` identifies one call within a Turn Execution.
- `tool_result.parent_tool_use_id` points to the DB ID of its own `tool_call` message.
- A result whose parent call cannot be found must fail fast. It must not create an orphan result or silently attach to the nearest call.
- A nested tool is related only when the provider supplies an explicit parent identity. Name, time proximity, or array position must not be used to guess.
- A deterministic `source_event_key` is required only for provider-backed tool calls/results, Question answers, and events for which the upstream source provides a reliable identity. Replaying the same event is a no-op; the same key with a different canonical payload is a conflict. A Codex plan notification without a durable ID remains a distinct occurrence each time and does not promise deduplication across mapper restarts.
- Every append locks the Thread row in the same transaction, rechecks reliable source keys after locking, and calculates `MAX(message_sequence) + 1` using the existing index. `threadVersion` is used only for realtime metadata, not as a history cursor.

### Call-Anchored Message Item

The system does not expose `tool_result` as a visible timeline row:

```text
Raw persistence
  tool_call ────────────────┐
  tool_result (provider) ───┼─► Tool Timeline Item
  tool_result (answer) ─────┘    anchor = tool_call
```

- `tool_call` is the sole presentation anchor for a tool interaction and determines the item's fixed `sequence` and scroll identity.
- `tool_result` remains an append-only DB row, but hydrates the original tool item only as a typed sidecar.
- `result_kind` is either `provider_result` or `interaction_answer`; each parent can have at most one of each kind. A Question may legitimately have both a provider result indicating that it is waiting for user input and an interaction answer submitted afterward. The screen still shows a single Question card.
- For a regular item, `itemVersion` equals its own message sequence. For a tool item, `itemVersion` is the maximum sequence across the call and related results. Result arrival only increases the version; it does not move the anchor.
- The complete result is read through the message-ID detail endpoint. A history page never carries unbounded content.

## Reading and Pagination

### Timeline Contract

```http
GET /api/v1/threads/{threadId}/timeline?limit=100
GET /api/v1/threads/{threadId}/timeline?beforeSequence=1002&limit=100
```

- `beforeSequence` is the only history cursor and uses exclusive `<`.
- The default is 100 presentation anchors and the maximum is 200. Responses are always ordered by ascending `sequence`.
- The anchor allowlist explicitly includes user, agent text, thinking, tool call, system, system init, git diff, and error. It excludes `tool_result`.
- The backend reads `limit + 1` through the partial anchor index, then hydrates tool results and referenced Turn/Execution metadata for that page in fixed batches. It must not introduce N+1 queries or expand a page to complete a Turn or tool tree.
- The cache holds at most 5 pages and defaults to 500 items.

Realtime updates to known items use a bounded batch-get:

```http
POST /api/v1/threads/{threadId}/timeline/items/batch-get
```

It accepts at most 200 known anchor IDs and returns the same item projection. It has no cursor, next page, or independent cache, so it is not a second history pagination layer.

## Realtime, Cache, and Reconnect

| Situation | Current behavior |
|---|---|
| New message/tool call | Merge `createdItemIds` into the latest cache window through bounded batch-get |
| Tool result arrives | Put the parent call in `changedItemIds` and patch only that already-loaded tool item |
| User is in the middle of history | Show an unread update without forcing a jump to the bottom; clear it only after returning to the bottom |
| WebSocket reconnect | Refetch a fixed latest page; REST restores authoritative state |
| Invalidation payload overflow | Send `refreshLatest: true` instead of an unbounded ID list |

The WebSocket event is named `timeline_updated` and contains bounded `createdItemIds`, `changedItemIds`, and referenced Turn/Execution metadata. It is only an invalidation hint: missing an event does not compromise history correctness. The frontend can recover through the latest page, bounded batch refresh, and `beforeSequence`, without a replay log or outbox.

## Result, Use, and Think Order When Scrolling Up

When raw DB rows are read in descending sequence order, the query may encounter:

```text
102 tool_result
101 tool_call / use
100 thinking
```

The history query excludes `102 tool_result` as an anchor, so the user first sees a card anchored at `101 tool_call` with its result already hydrated:

```text
Tool card [Use header → Result preview]
```

After the next earlier page loads `100 thinking`, the frontend recomposes the ascending sequence as:

```text
Think → the same Tool card [Use header → Result preview]
```

The screen never shows a standalone Result, never displays Result before later adding Use, and does not recreate the tool card when Think is prepended. If final text follows, Think and the tool card remain in the Activity before that final text. If no final text exists yet, each is a virtualizable agent-part row. Scrolling upward loads only the earlier page the user requested; it does not cross pages automatically to complete an unloaded Think or nested parent.

Claude and OpenCode provide formal Thinking/thought events and can verify the complete order. Codex currently has no persisted reasoning item, so it shows only Use + Result and must not invent Think.

## Frontend Composition and UI Invariants

`toTimelinePresentation()` reads hydrated tool items directly and composes consecutive thinking, agent text, and top-level tools into one Agent response. `ThreadMessageItem` displays the final Agent text directly and puts preceding parts in Activity. Pagination changes **must not intentionally alter the current message presentation contract**:

- Consecutive Agent parts remain visually one Agent response instead of separate chat bubbles.
- Tools and thinking before final text remain in the “Processing/Completed” Activity, which is collapsed by default.
- When Activity is expanded, each Thinking section retains its own inner expand/collapse behavior and title contract.
- Question/Canvas must remain visible and interactive and must not be hidden by Activity's default collapsed state.
- A tool card must preserve structured `parameters`, its dedicated renderer, the Use header before the Result preview, and Show all behavior.
- When both a nested parent and child are loaded, they remain presented within the parent card. When one side is missing, the UI does not recursively fetch the whole tree and does not add breadcrumb UI.
- The Files Changed section and its semantics within a Turn remain unchanged.
- Prepending older content preserves the first visible row and offset. New messages are followed only when the user is at the bottom.

`toTimelinePresentation()` creates presentation groups only from currently loaded, consecutive items in the cache. Presentation grouping is not stored in the DB or API and has no cursor of its own.

The top-level `ThreadTimeline` virtualizes loaded presentation groups, while the cache remains capped at 500 items. A collapsed Activity does not mount its children. When an expanded Activity has more than 50 parts, a local part virtualizer preserves the existing inner `50dvh` scroll area. This local virtualizer has no query, cache, or cursor; it only limits DOM and **is not a second pagination layer**.

## Three-Agent Normalization Boundary

| Agent | Formal tool identity | Thinking | Parent rule |
|---|---|---|---|
| Claude SDK | `ToolUseBlock.id`/`ServerToolUseBlock.id` and the result's `tool_use_id` | Formal thinking is available | Persist only when the SDK explicitly supplies `parent_tool_use_id` |
| Codex SDK | `item.id` for commands, MCP, and web search | Reasoning is not currently persisted | Current types do not guess a parent; every plan notification without a durable ID is a distinct occurrence |
| OpenCode ACP | `tool_call_id` | A thought event is available | Current ACP updates do not guess a parent; a process-local seen set is only an optimization |

All three mappers must output the same canonical tool contract: generate stable event keys for tool events with reliable upstream identity, make calls and results share a tool key, preserve call-before-result, mark only a terminal result as the result phase, and persist a parent key only when the provider explicitly supplies one. Codex plan notifications remain the explicit exception without a durable identity. In a normal callback, the mapper guarantees that the call precedes the result; if a call cannot be found across callbacks, the adapter fails fast. The design does not use placeholders, a pending-result inbox, or a reconciliation worker.

## Shared Boundary Between AI Chat and Automation

- An ordinary AI Chat Thread is user-owned. An Automation Thread is resolved through the Manager automation execution lookup and uses Workspace member access.
- Every Automation execution that enters the Agent flow owns an independent Runtime Thread. Multiple scheduled executions are not merged into a job-level conversation.
- The upper lifecycle section of Automation Execution Detail comes from Workspace Manager; the lower Agent conversation comes from Workspace Runtime.
- AI Chat Workbench and Automation Execution Detail share `ThreadTimeline`, the timeline endpoint, query/cache, presentation compositor, and renderers. Automation additionally retains the Manager lifecycle and automation-execution-to-thread lookup.

## Required Performance and Implementation Boundaries

The current architecture requires these invariants:

1. The initial response for 1 Turn/1,001 items contains no more than 100 items, and the cache defaults to at most 500 items.
2. When 100 calls are followed by 100 results, the latest page still returns 100 hydrated tool items rather than an empty page or 100 orphan results.
3. A realtime Result update does not increase the row count, change the call sequence, or retransmit the complete Turn.
4. The number of page queries remains constant regardless of the number of tools on the page. Mounted DOM for collapsed and expanded UI grows only with the viewport and overscan.
5. The system has only one history cursor, `beforeSequence`; it has no Turn history, result sub-pagination, or cross-page tree fetch.

The design intentionally does not introduce a message watermark, `asOfSequence` snapshot protocol, mutable projection table, pending inbox, durable event log/outbox, semantic hashes for all text, a general nested-tree virtualizer, or new breadcrumb UI. These are considered only if measurements or formal provider captures demonstrate a need.

## Code Index

| Scope | Primary paths |
|---|---|
| Runtime Thread interface | `workspace-runtime/app/modules/thread/router.py`, `lifecycle.py::ThreadService`, and `execution.py::_ThreadExecution` |
| Persistence/tool pairing | `workspace-runtime/app/modules/thread/message_repository.py`, `repository.py`, and `turn_repository.py` |
| Three Agent mappers/adapters | `workspace-runtime/app/modules/thread/claude_sdk_event_mapper.py`, `codex_sdk_event_mapper.py`, `opencode_acp_event_mapper.py`, and the matching `*_agent_runner.py` files |
| WebSocket invalidation | `workspace-runtime/app/modules/thread/invalidation_emitter.py` and `websocket/router.py` |
| Frontend query/realtime | `frontend/src/features/ai-chat/hooks/`, `frontend/src/features/ai-chat/realtime/` |
| Frontend timeline/composition | `frontend/src/features/ai-chat/components/messages/` |
| Automation viewer | `frontend/src/features/workspace-automation/components/execution/ExecutionDetailDialog.tsx` |

### Design Principles

1. The system has only one Message Item pagination layer. There is no Turn history API or independent turn update event.
2. A tool result is a raw persistence event but not an independent UI row. Do not infer that the screen must show Result first from raw sequence order.
3. Turn is a lifecycle boundary, not a performance or pagination boundary. One Turn can contain many items.
4. Frontend grouping is loaded-only derived presentation, not a second data model, and it must not automatically fetch unloaded history to complete an Activity.
5. Every three-Agent change must follow the shared canonical mapper → `AgentRunner` seam → persistence → timeline path. Do not create a side path for only one provider or for Automation.
6. A data-layer change must not be used to redesign the existing UI. Activity, Thinking, Question/Canvas, tool cards, and Files Changed are required product semantics.
