---
title: Automation Center
---

# Automation Center

## Purpose and Entry Point

Automation Center is the canonical product surface for jobs, triggers, and execution records, entered at `/automation`.

## Roles and Allowed Operations

Platform members may enter. Executing against a Workspace still requires `workspace.automation.execute`.

## Core Concepts

A Job defines when and where to run. An Execution is one durable attempt. A Thread stores agent conversation data.

## Primary Workflow

Create or edit a job, configure cron/webhook, trigger an execution, track state, and inspect the AI Chat timeline.

## View States and Read-only Behavior

The view handles loading, empty, error, and denied states separately. With read-only operations, readable content and normal mutation controls remain visible while mutations are disabled with an i18n reason. Without read access, protected queries, providers, and realtime connections do not start.

## Constraints, Failures, and Safety

Cancel, retry, and runner recovery use durable state. Losing Workspace authorization pauses jobs and cancels nonterminal executions.

## Source Basis

- `frontend/src/features/workspace-automation/AutomationModule.tsx::AutomationModule`
- `frontend/src/features/workspace-automation/providers/AutomationProvider.tsx`
- `workspace-manager/app/modules/automation/`

## Related Architecture and APIs

- [ai-chat](/architecture/overview/ai-chat)
- [automation-runner-recovery](/installation/automation-runner-recovery)
- [manager-api](/api/manager-api)
