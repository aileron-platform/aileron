---
title: Resource Statistics and Capacity
---

# Resource Statistics and Capacity

## Purpose and Entry Point

Platform admins enter Platform Resources to inspect Workspace and knowledge-base management, analytics, trends, capacity risks, and expansion requests.

## Roles and Allowed Operations

Read and governance use platform-resource Operation IDs and are admin-only. Hiding buttons never replaces Manager authorization.

## Core Concepts

An observation is a point-in-time fact; risk is Manager evaluation using thresholds and freshness; an expansion request completes only when observed capacity reaches the target.

### Machine Contract Identifiers

- Ranges: `7d`, `30d`, `90d`
- Storage kinds: `workspace_data`, `runtime_home`, `knowledge_base`
- Workspace health groups: `running`, `transitioning`, `stopped`, `error`
- Capacity risks: `normal`, `warning`, `critical`, `unknown`, `stale`
- Endpoints: `/platform-resources/workspaces/statistics/summary`, `/platform-resources/workspaces/statistics/resource-trend`, `/platform-resources/workspaces/statistics/capacity-trend`
- Endpoints: `/platform-resources/knowledge-bases/statistics/summary`, `/platform-resources/knowledge-bases/statistics/resource-trend`, `/platform-resources/knowledge-bases/statistics/capacity-trend`
- Endpoints: `/platform-resources/knowledge-bases/{knowledgeBaseId}/quota`, `/platform-resources/workspaces/{workspaceId}/capacity-expansions`, `/workspaces/{workspaceId}/capacity`, `/internal/workspaces/{workspaceId}/resource-telemetry/batches`

## Primary Workflow

Switch between management/analytics and Workspace/knowledge-base scope, select a period, then load summaries and trends. Governance creates a durable request and waits for convergence.

## View States and Read-only Behavior

The view handles loading, empty, error, and denied states separately. With read-only operations, readable content and normal mutation controls remain visible while mutations are disabled with an i18n reason. Without read access, protected queries, providers, and realtime connections do not start.

## Constraints, Failures, and Safety

Data source, period, timezone, freshness, and unknown/stale states remain visible. One failed section does not erase other successful data.

## Source Basis

- `frontend/src/features/platform-resources/PlatformResourcesModule.tsx::PlatformResourcesModule`
- `frontend/src/features/platform-resources/data-session/usePlatformResourcesDataSession.ts`
- `workspace-manager/app/modules/platform_resource_analytics/`
- `workspace-manager/app/modules/platform_resource_capacity/`

## Related Architecture and APIs

- [platform-resource-observability](/architecture/overview/platform-resource-observability)
- [manager-api](/api/manager-api)
