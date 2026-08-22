---
title: Agent Settings
---

# Agent Settings

## Purpose and Entry Point

Enter Agent Settings from Workspace navigation. The shared entry covers Agents, Skills, Commands, MCP, Settings, and Subagents, then exposes provider differences.

## Roles and Allowed Operations

General settings use Workspace detail/content operations. Pages that may return secrets or raw scoped values use sensitive-settings read/manage.

## Core Concepts

Project, local, and user scope are independent from provider. Runtime provider adapters resolve file paths.

## Primary Workflow

Select a provider and settings type, then scope; read and save with revision. User-scope content lives in the Workspace's own persistent Runtime HOME, shared by every user and session of that Workspace — it is not an isolated personal space per human user.

## View States and Read-only Behavior

The view handles loading, empty, error, and denied states separately. With read-only operations, readable content and normal mutation controls remain visible while mutations are disabled with an i18n reason. Without read access, protected queries, providers, and realtime connections do not start.

## Constraints, Failures, and Safety

Secrets are not loaded before masking. Default content never overwrites same-name custom content, external paths, or symlink conflicts.

## Source Basis

- `frontend/src/features/workspace/features/agent-settings/`
- `workspace-runtime/app/modules/cli_settings/`
- `workspace-runtime/app/modules/claude_code/`

## Related Architecture and APIs

- [workspace-runtime](/architecture/backend/workspace-runtime/)
- [runtime-api](/api/runtime-api)
