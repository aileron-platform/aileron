---
title: Workspace Settings
---

# Workspace Settings

## Purpose and Entry Point

Enter Workspace Settings to manage basic metadata, access, knowledge-base mounts, and reset. This page owns the canonical knowledge-base mount/unmount workflow.

## Roles and Allowed Operations

Basic reads require detail read. Metadata, access, attachment, and lifecycle each use their specific manage/execute Operation IDs.

## Core Concepts

Settings subpages gate independently by sensitivity. Knowledge Base Center only displays usage and does not own mount mutations.

## Primary Workflow

Select a subpage and confirm the operation before loading. Mounting a knowledge base updates Workspace attachment desired state and waits for convergence.

## View States and Read-only Behavior

The view handles loading, empty, error, and denied states separately. With read-only operations, readable content and normal mutation controls remain visible while mutations are disabled with an i18n reason. Without read access, protected queries, providers, and realtime connections do not start.

## Constraints, Failures, and Safety

Reset and unmount may affect Runtime. Show impact before execution and preserve durable failure state.

## Source Basis

- `frontend/src/features/workspace/features/workspace-settings/WorkspaceSettingsPage.tsx::WorkspaceSettingsPage`
- `workspace-manager/app/modules/workspace/`
- `workspace-manager/app/modules/knowledge_base/`

## Related Architecture and APIs

- [execution-plane](/architecture/overview/execution-plane)
- [manager-api](/api/manager-api)
