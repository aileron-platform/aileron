---
title: Version Control
---

# Version Control

## Purpose and Entry Point

Enter through Workspace Changes and History to handle repository setup, diffs, commits, branches, and synchronization.

## Roles and Allowed Operations

Reading requires `workspace.detail.read`; Git and working-tree mutations require `workspace.content.manage`.

## Core Concepts

The repository target interface, operation lock, revision, and product adapter define one Git operation boundary.

## Primary Workflow

Confirm or create the repository, then select changes or history. Mutations run under the target lock and return a new revision.

## View States and Read-only Behavior

The view handles loading, empty, error, and denied states separately. With read-only operations, readable content and normal mutation controls remain visible while mutations are disabled with an i18n reason. Without read access, protected queries, providers, and realtime connections do not start.

## Constraints, Failures, and Safety

Clone, fetch, push, and conflict errors remain diagnosable. Concurrent writes never run on an unlocked target.

## Source Basis

- `frontend/src/shared/version-control/`
- `frontend/src/features/workspace/integrations/version-control/`
- `workspace-runtime/app/modules/version_control/`
- `packages/aileron-git-core/`

## Related Architecture and APIs

- [version-control](/architecture/overview/version-control)
- [runtime-api](/api/runtime-api)
