---
title: Files and Version Control
---

# Files and Version Control

## Purpose and Entry Point

Enter from knowledge-base Files, Changes, and History to manage canonical content and Git history.

## Roles and Allowed Operations

Reading requires detail read; content and Git mutations require `knowledge_base.content.manage`.

## Core Concepts

Knowledge Base and Workspace share file/version-control interfaces but use different target adapters to resolve repositories.

## Primary Workflow

Select a file, edit and save with revision. Version-control operations run under the knowledge-base target lock.

## View States and Read-only Behavior

The view handles loading, empty, error, and denied states separately. With read-only operations, readable content and normal mutation controls remain visible while mutations are disabled with an i18n reason. Without read access, protected queries, providers, and realtime connections do not start.

## Constraints, Failures, and Safety

Workspace mounts cannot bypass the knowledge-base content operation to mutate canonical content.

## Source Basis

- `frontend/src/features/knowledge-base/components/`
- `frontend/src/shared/components/file-workbench/`
- `workspace-manager/app/modules/knowledge_base/`
- `packages/aileron-git-core/`

## Related Architecture and APIs

- [version-control](/architecture/overview/version-control)
- [manager-api](/api/manager-api)
