---
title: AI Chat
---

# AI Chat

## 目的與入口

由 Workspace 的 AI Agent／AI Chat 進入，建立 thread、送出訊息、觀看 tool use/result/thinking 與回覆，並可處理結構化提問。

## 角色與允許操作

使用與送出要求 `workspace.agent_chat.use`；缺少操作時不掛載 Chat Provider 或 WebSocket。

## 核心概念

Thread、turn、message item 與 agent session 分離；Claude Code、Codex 與 OpenCode 事件在 Runtime mapper 邊界正規化。

## 主要流程

選擇或建立 thread、送出 user message、串流 assistant 與 tool events、持久化後由 invalidation 更新 timeline。

## 畫面狀態與唯讀行為

畫面分別處理 loading、empty、error 與 denied。只有讀取操作時保留可讀內容與一般變更控制項，但停用變更並顯示 i18n 原因；缺少讀取操作時不啟動受保護 query、Provider 或即時連線。

## 限制、失敗與安全

重連不得重複 message item；tool call/result 配對與 timeline 順序需維持。結構化問題適合有限且互斥的選項，不取代自由文字對話。

## 原始碼依據

- `frontend/src/features/ai-chat/`
- `workspace-runtime/app/modules/thread/lifecycle.py::ThreadService`
- `workspace-runtime/app/modules/thread/message_repository.py`
- `workspace-runtime/app/modules/thread/*_event_mapper.py`

## 相關架構與 API

- [ai-chat](/architecture/overview/ai-chat)
- [runtime-api](/api/runtime-api)
