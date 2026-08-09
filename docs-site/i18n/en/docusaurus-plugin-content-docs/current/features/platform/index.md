---
title: Platform Overview
---

# Platform Overview

## Purpose and Entry Point

Platform Overview centralizes cross-product permissions, roles, resource statistics, and capacity governance. Entry points include Platform Resources and authorization states across products.

## Roles and Allowed Operations

Platform members use normal products. Platform admins additionally use user management, platform resources, and governance operations. Platform `allowedOperations` are authoritative.

## Core Concepts

`PlatformRole`, `OperationId`, and platform resource observations are distinct: roles expand operations, observations provide facts, and governance evaluates those facts.

## Primary Workflow

After login, `/api/v1/oauth2/session` returns platform operations. Global Navigation shows only accessible products, and Platform Resources then loads management or analytics data.

## View States and Read-only Behavior

The view handles loading, empty, error, and denied states separately. With read-only operations, readable content and normal mutation controls remain visible while mutations are disabled with an i18n reason. Without read access, protected queries, providers, and realtime connections do not start.

## Constraints, Failures, and Safety

Platform state is never inferred from JWT or a frontend role table. Stale observations must remain stale or unknown, never normal.

## Source Basis

- `frontend/src/app/AppRouter.tsx::AppRouter`
- `frontend/src/app/components/navigation/GlobalNavigation.tsx`
- `workspace-manager/app/modules/authorization/operation_policy.py`
- `workspace-manager/app/modules/platform_resource_analytics/`

## Related Architecture and APIs

- [identity-and-access](/architecture/overview/identity-and-access)
- [platform-resource-observability](/architecture/overview/platform-resource-observability)
- [manager-api](/api/manager-api)
