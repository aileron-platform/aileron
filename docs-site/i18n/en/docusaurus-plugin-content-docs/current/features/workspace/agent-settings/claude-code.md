---
title: Claude Code Settings
---

# Claude Code Settings

## Purpose and Entry Point

Select Claude Code in Agent Settings to manage Agents, Skills, Commands, MCP, and Settings.

## Roles and Allowed Operations

Uses the Workspace and sensitive-settings operations defined by Agent Settings.

## Core Concepts

Claude Code-specific settings cooperate with shared CLI settings adapters; Runtime resolvers determine scope and file locations.

## Primary Workflow

Select resource type and scope, load, edit, and save with revision.

## View States and Read-only Behavior

The view handles loading, empty, error, and denied states separately. With read-only operations, readable content and normal mutation controls remain visible while mutations are disabled with an i18n reason. Without read access, protected queries, providers, and realtime connections do not start.

## Constraints, Failures, and Safety

Never assume the host HOME. User scope uses the managed HOME resolved by Runtime for the current user.

## Source Basis

- `workspace-runtime/app/modules/claude_code/`
- `workspace-runtime/app/modules/cli_settings/`
- `frontend/src/features/workspace/features/agent-settings/`

## Related Architecture and APIs

- [agent-runtime-terminology](/architecture/backend/workspace-runtime/agent-runtime-terminology)
- [runtime-api](/api/runtime-api)
