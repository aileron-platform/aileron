---
title: Container Management
---

# Container Management

## Purpose and Entry Point

Enter Container Management to inspect Runtime, Terminal, and firewall-related state.

## Roles and Allowed Operations

Runtime/sensitive settings use sensitive-settings operations. Firewall reads and mutations use `workspace.firewall.read/manage`.

## Core Concepts

Desired firewall, observed firewall, Runtime generation, and Terminal session are separate states.

## Primary Workflow

Read current state, submit settings, and wait for observed state. Terminal sessions use a separate creation flow.

## View States and Read-only Behavior

The view handles loading, empty, error, and denied states separately. With read-only operations, readable content and normal mutation controls remain visible while mutations are disabled with an i18n reason. Without read access, protected queries, providers, and realtime connections do not start.

## Constraints, Failures, and Safety

Disable operations while Runtime is unavailable. Sensitive environment variables never return to users without the read operation.

## Source Basis

- `frontend/src/features/workspace/features/container-management/`
- `workspace-manager/app/modules/workspace/firewall.py`
- `workspace-runtime/app/modules/internal/`
- `workspace-runtime/app/modules/internal/router.py`

## Related Architecture and APIs

- [execution-plane](/architecture/overview/execution-plane)
- [manager-api](/api/manager-api)
- [runtime-api](/api/runtime-api)
