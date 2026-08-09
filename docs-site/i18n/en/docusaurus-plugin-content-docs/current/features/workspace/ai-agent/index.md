---
title: AI Agent
---

# AI Agent

## Purpose and Entry Point

AI Agent combines AI Chat and Terminal. They share Workspace context but have independent operations, sessions, and failure states.

## Roles and Allowed Operations

AI Chat requires `workspace.agent_chat.use`; Terminal requires `workspace.terminal.use`. Both currently require at least manager.

## Core Concepts

Chat thread/turn and Terminal session have different lifecycles. Agent provider settings are also separate from Chat eligibility.

## Primary Workflow

After selecting a Workspace, enter Chat or Terminal according to allowed operations. No session is created while Runtime is unavailable.

## View States and Read-only Behavior

The view handles loading, empty, error, and denied states separately. With read-only operations, readable content and normal mutation controls remain visible while mutations are disabled with an i18n reason. Without read access, protected queries, providers, and realtime connections do not start.

## Constraints, Failures, and Safety

Realtime connections are reconnectable. Missing operations or generation changes stop protected connections immediately.

## Source Basis

- `frontend/src/features/ai-chat/`
- `frontend/src/features/workspace/features/container-management/`
- `workspace-runtime/app/modules/thread/`
- `workspace-runtime/app/modules/internal/router.py`

## Related Architecture and APIs

- [ai-chat](/architecture/overview/ai-chat)
- [workspace-runtime](/architecture/backend/workspace-runtime/)
- [runtime-api](/api/runtime-api)
