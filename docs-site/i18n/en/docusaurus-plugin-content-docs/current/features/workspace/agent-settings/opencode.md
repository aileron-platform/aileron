---
title: OpenCode Settings
---

# OpenCode Settings

## Purpose and Entry Point

Select OpenCode in Agent Settings to manage its supported CLI settings resources.

## Roles and Allowed Operations

Uses the Workspace and sensitive-settings operations defined by Agent Settings.

## Core Concepts

Runtime adapters define OpenCode filenames, scopes, and supported resources; Claude Code paths are not reused.

## Primary Workflow

Select resource and scope, load, validate, and save.

## View States and Read-only Behavior

The view handles loading, empty, error, and denied states separately. With read-only operations, readable content and normal mutation controls remain visible while mutations are disabled with an i18n reason. Without read access, protected queries, providers, and realtime connections do not start.

## Constraints, Failures, and Safety

Unsupported provider resources are hidden and do not start queries.

## Source Basis

- `workspace-runtime/app/modules/cli_settings/`
- `frontend/src/features/workspace/features/agent-settings/`

## Related Architecture and APIs

- [agent-runtime-terminology](/architecture/backend/workspace-runtime/agent-runtime-terminology)
- [runtime-api](/api/runtime-api)
