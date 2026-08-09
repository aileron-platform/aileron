---
title: Codex Settings
---

# Codex Settings

## Purpose and Entry Point

Select Codex in Agent Settings to manage supported Skills, MCP, Settings, and other CLI resources.

## Roles and Allowed Operations

Uses the Workspace and sensitive-settings operations defined by Agent Settings.

## Core Concepts

Codex has provider-specific runtime names and settings locations. Frontend uses provider IDs, not display text, for decisions.

## Primary Workflow

Select resource and scope, load, validate, and save with revision.

## View States and Read-only Behavior

The view handles loading, empty, error, and denied states separately. With read-only operations, readable content and normal mutation controls remain visible while mutations are disabled with an i18n reason. Without read access, protected queries, providers, and realtime connections do not start.

## Constraints, Failures, and Safety

External paths, non-directories, and symlink conflicts fail closed and are never overwritten.

## Source Basis

- `workspace-runtime/app/modules/cli_settings/`
- `frontend/src/features/workspace/features/agent-settings/`

## Related Architecture and APIs

- [agent-runtime-terminology](/architecture/backend/workspace-runtime/agent-runtime-terminology)
- [runtime-api](/api/runtime-api)
