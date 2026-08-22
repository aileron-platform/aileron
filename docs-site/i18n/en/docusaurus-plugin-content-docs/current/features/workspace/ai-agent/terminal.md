---
title: Terminal
---

# Terminal

## Purpose and Entry Point

Enter through AI Agent / Terminal or Container Management to create a reconnectable interactive shell session that retains its working directory.

## Roles and Allowed Operations

Terminal use requires `workspace.terminal.use`; sensitive container settings require separate sensitive-settings operations.

## Core Concepts

Terminal session, connection, and tab are distinct. Connections to one session share shell state and the last confirmed working directory.

## Primary Workflow

Create a session, attach WebSocket, and run commands. Update the working directory when the prompt returns; reconnect or restart from the last confirmed value.

## View States and Read-only Behavior

The view handles loading, empty, error, and denied states separately. With read-only operations, readable content and normal mutation controls remain visible while mutations are disabled with an i18n reason. Without read access, protected queries, providers, and realtime connections do not start.

## Constraints, Failures, and Safety

Only an invalid working directory falls back to the Workspace default. Disconnecting does not delete the session.

## Source Basis

- `frontend/src/features/workspace/features/container-management/`
- `workspace-runtime/app/modules/internal/router.py`
- `workspace-terminal/`

## Related Architecture and APIs

- [workspace-runtime](/architecture/backend/workspace-runtime/)
- [runtime-api](/api/runtime-api)
