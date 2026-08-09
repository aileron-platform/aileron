---
title: Executions
---

# Executions

## Purpose and Entry Point

Inspect global or per-job executions in Automation Center, open details, cancel, or view the agent timeline.

## Roles and Allowed Operations

Execution visibility and control use the target Workspace automation operation.

## Core Concepts

Queued, claimed, running, completed, failed, and cancelled are durable execution states. UI connection state is not execution outcome.

## Primary Workflow

Open an execution from the list and update state through polling/events. Details render the thread using shared AI Chat item mapping.

## View States and Read-only Behavior

The view handles loading, empty, error, and denied states separately. With read-only operations, readable content and normal mutation controls remain visible while mutations are disabled with an i18n reason. Without read access, protected queries, providers, and realtime connections do not start.

## Constraints, Failures, and Safety

Claim/recovery contracts handle runner interruption. Closing the page never marks a running execution failed.

## Source Basis

- `frontend/src/features/workspace-automation/components/execution/ExecutionDetailDialog.tsx`
- `workspace-manager/app/modules/automation/router.py`
- `workspace-manager/app/modules/automation/repository.py`
- `workspace-manager/app/modules/automation/execution.py`

## Related Architecture and APIs

- [ai-chat](/architecture/overview/ai-chat)
- [automation-runner-recovery](/installation/automation-runner-recovery)
- [manager-api](/api/manager-api)
