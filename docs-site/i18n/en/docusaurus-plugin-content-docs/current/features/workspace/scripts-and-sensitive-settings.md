---
title: Scripts and Sensitive Settings
---

# Scripts and Sensitive Settings

## Purpose and Entry Point

Enter through Workspace Settings or Container Management to manage setup scripts, environment variables, and other potentially secret values.

## Roles and Allowed Operations

Reading requires `workspace.sensitive_settings.read`; mutations require `workspace.sensitive_settings.manage`.

## Core Concepts

Displayed values, masked values, write-only secrets, and execution results remain separate.

## Primary Workflow

Load only after the read gate. Save with revision to prevent overwrite; script execution reports a separate result.

## View States and Read-only Behavior

The view handles loading, empty, error, and denied states separately. With read-only operations, readable content and normal mutation controls remain visible while mutations are disabled with an i18n reason. Without read access, protected queries, providers, and realtime connections do not start.

## Constraints, Failures, and Safety

Secrets never enter logs, toasts, or documentation. Without the read operation they are not loaded before masking.

## Source Basis

- `frontend/src/features/workspace/features/workspace-settings/`
- `frontend/src/features/workspace/features/container-management/`
- `workspace-manager/app/modules/workspace/`
- `workspace-runtime/app/modules/internal/`

## Related Architecture and APIs

- [identity-and-access](/architecture/overview/identity-and-access)
- [manager-api](/api/manager-api)
- [runtime-api](/api/runtime-api)
