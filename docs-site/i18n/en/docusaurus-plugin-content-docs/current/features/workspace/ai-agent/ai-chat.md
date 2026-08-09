---
title: AI Chat
---

# AI Chat

## Purpose and Entry Point

Enter AI Agent / AI Chat to create threads, send messages, inspect tool use/result/thinking and responses, and answer structured questions.

## Roles and Allowed Operations

Use and submission require `workspace.agent_chat.use`. Without it, the Chat Provider and WebSocket do not mount.

## Core Concepts

Thread, turn, message item, and agent session are distinct. Claude Code, Codex, and OpenCode events normalize at Runtime mapper boundaries.

## Primary Workflow

Select or create a thread, send a user message, stream assistant and tool events, then update the timeline through invalidation after persistence.

## View States and Read-only Behavior

The view handles loading, empty, error, and denied states separately. With read-only operations, readable content and normal mutation controls remain visible while mutations are disabled with an i18n reason. Without read access, protected queries, providers, and realtime connections do not start.

## Constraints, Failures, and Safety

Reconnect must not duplicate message items. Tool call/result pairing and timeline order remain stable. Structured questions suit bounded exclusive choices and do not replace free-form chat.

## Source Basis

- `frontend/src/features/ai-chat/`
- `workspace-runtime/app/modules/thread/lifecycle.py::ThreadService`
- `workspace-runtime/app/modules/thread/message_repository.py`
- `workspace-runtime/app/modules/thread/*_event_mapper.py`

## Related Architecture and APIs

- [ai-chat](/architecture/overview/ai-chat)
- [runtime-api](/api/runtime-api)
