---
title: File Management
---

# File Management

## Purpose and Entry Point

Enter File Management from Workspace navigation to browse, create, edit, rename, move, upload, and delete workspace files.

## Roles and Allowed Operations

Reading requires `workspace.detail.read`; mutations require `workspace.content.manage`.

## Core Concepts

Canonical paths, revisions, and selection identity prevent stale writes. The file workbench combines shared file core with a product adapter.

## Primary Workflow

Select a directory or file, load content, and save with the expected revision. Conflicts require reload or an explicit user decision, never silent overwrite.

## View States and Read-only Behavior

The view handles loading, empty, error, and denied states separately. With read-only operations, readable content and normal mutation controls remain visible while mutations are disabled with an i18n reason. Without read access, protected queries, providers, and realtime connections do not start.

## Constraints, Failures, and Safety

All paths remain within the managed root; traversal, symlink escape, and invalid names are rejected.

## Source Basis

- `frontend/src/features/workspace/features/file-management/`
- `frontend/src/shared/components/file-workbench/`
- `workspace-runtime/app/modules/file_system/`
- `packages/aileron-file-core/`

## Related Architecture and APIs

- [frontend](/architecture/frontend/)
- [runtime-api](/api/runtime-api)
