---
title: Jobs and Triggers
---

# Jobs and Triggers

## Purpose and Entry Point

Create and edit jobs in Automation Center, selecting Workspace, agent instructions, and cron or webhook triggers.

## Roles and Allowed Operations

Creation and execution require `workspace.automation.execute` on the target Workspace.

## Core Concepts

Job, trigger, schedule, webhook secret, and execution queue are distinct states.

## Primary Workflow

Validate the form, create the job, and enable the trigger. Cron schedules in the configured timezone; webhook verifies its secret before enqueueing.

## View States and Read-only Behavior

The view handles loading, empty, error, and denied states separately. With read-only operations, readable content and normal mutation controls remain visible while mutations are disabled with an i18n reason. Without read access, protected queries, providers, and realtime connections do not start.

## Constraints, Failures, and Safety

Prevent duplicate triggers and excess concurrency. Webhook secrets are never shown again in plaintext.

## Source Basis

- `frontend/src/features/workspace-automation/components/`
- `workspace-manager/app/modules/automation/router.py`
- `workspace-manager/app/modules/automation/jobs.py`
- `workspace-manager/app/modules/automation/scheduler.py`

## Related Architecture and APIs

- [workspace-manager](/architecture/backend/workspace-manager/)
- [manager-api](/api/manager-api)
