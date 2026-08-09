---
title: Usage and Capacity
---

# Usage and Capacity

## Purpose and Entry Point

Inspect Workspace usage and current capacity from knowledge-base detail. Mount and unmount remain in Workspace Settings.

## Roles and Allowed Operations

Detail readers view normal usage. Governance and capacity actions use platform-resource or knowledge-base management operations.

## Core Concepts

Workspace usage, effective quota, capacity observation, and platform risk are different data.

## Primary Workflow

Load consuming Workspaces and capacity summary. Navigate to the corresponding Workspace Settings to change a mount.

## View States and Read-only Behavior

The view handles loading, empty, error, and denied states separately. With read-only operations, readable content and normal mutation controls remain visible while mutations are disabled with an i18n reason. Without read access, protected queries, providers, and realtime connections do not start.

## Constraints, Failures, and Safety

Stale capacity is not current. Deletion shows Workspaces still using the knowledge base.

## Source Basis

- `frontend/src/features/knowledge-base/routes/KnowledgeBaseDetailRoute.tsx`
- `workspace-manager/app/modules/knowledge_base/`
- `workspace-manager/app/modules/platform_resource_analytics/`

## Related Architecture and APIs

- [platform-resource-observability](/architecture/overview/platform-resource-observability)
- [workspace-settings](/features/workspace/workspace-settings)
- [manager-api](/api/manager-api)
