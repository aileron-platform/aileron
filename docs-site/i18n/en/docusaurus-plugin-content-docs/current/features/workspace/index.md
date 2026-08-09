---
title: Workspace
---

# Workspace

## Purpose and Entry Point

Workspace is the primary AI development surface, entered through `/workspace`, the creation wizard, and `/workspace/:workspaceId/*`.

## Roles and Allowed Operations

Platform members can create and list workspaces. Resource readers view detail, managers perform most interactions and management, and owners can permanently delete.

## Core Concepts

A workspace combines control-plane availability with an execution-plane generation. Feature navigation is filtered by that Workspace’s `allowedOperations`.

## Primary Workflow

The root loads visible workspaces and selects the existing or first item. It enters AI Chat when allowed, otherwise File Management.

## View States and Read-only Behavior

The view handles loading, empty, error, and denied states separately. With read-only operations, readable content and normal mutation controls remain visible while mutations are disabled with an i18n reason. Without read access, protected queries, providers, and realtime connections do not start.

## Constraints, Failures, and Safety

Runtime features do not mount when availability is not ready, the generation is stale, or authorization data is incomplete.

## Source Basis

- `frontend/src/features/workspace/WorkspaceModule.tsx::WorkspaceRootResolver`
- `frontend/src/features/workspace/layout/workspaceNavigationModel.ts`
- `frontend/src/features/workspace/model/workspacePermissions.ts::resolveWorkspacePermissions`
- `contracts/workspace-availability.json`

## Related Architecture and APIs

- [frontend](/architecture/frontend/)
- [execution-plane](/architecture/overview/execution-plane)
- [manager-api](/api/manager-api)
- [runtime-api](/api/runtime-api)
