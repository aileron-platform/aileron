---
title: Workspace Automation View
---

# Workspace Automation View

## Purpose and Entry Point

Enter from Workspace navigation to view jobs and executions scoped to the current Workspace. Canonical job and execution documentation belongs to Automation Center.

## Roles and Allowed Operations

Entry requires `workspace.automation.execute`; the platform Automation Center remains gated to platform members.

## Core Concepts

Workspace view is a filter and context, not a second automation domain.

## Primary Workflow

Filter jobs and executions by Workspace ID and open the same create, edit, and execution-detail workflows.

## View States and Read-only Behavior

The view handles loading, empty, error, and denied states separately. With read-only operations, readable content and normal mutation controls remain visible while mutations are disabled with an i18n reason. Without read access, protected queries, providers, and realtime connections do not start.

## Constraints, Failures, and Safety

Changing Workspace clears stale selection and query identity to avoid showing another Workspace’s execution.

## Source Basis

- `frontend/src/features/workspace-automation/AutomationModule.tsx::AutomationModule`
- `frontend/src/features/workspace-automation/providers/AutomationProvider.tsx`
- `workspace-manager/app/modules/automation/`

## Related Architecture and APIs

- [ai-chat](/architecture/overview/ai-chat)
- [automation](/features/automation/)
- [manager-api](/api/manager-api)
