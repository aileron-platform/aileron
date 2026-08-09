---
title: Author and Publish
---

# Author and Publish

## Purpose and Entry Point

Platform admins author content in the package editor, manage files and version control, and publish catalog versions.

## Roles and Allowed Operations

Content mutation and publishing are admin-only platform operations.

## Core Concepts

Draft, revision, working tree, and published package are separate. Saving a document does not publish the package.

## Primary Workflow

Create or open a draft, edit files, resolve revision conflicts, commit, and publish.

## View States and Read-only Behavior

The view handles loading, empty, error, and denied states separately. With read-only operations, readable content and normal mutation controls remain visible while mutations are disabled with an i18n reason. Without read access, protected queries, providers, and realtime connections do not start.

## Constraints, Failures, and Safety

Validate manifest, paths, and provider before publish. Conflicts never overwrite silently.

## Source Basis

- `frontend/src/features/marketplace/features/marketplace-editor/MarketplaceEditorPage.tsx`
- `workspace-manager/app/modules/marketplace/`
- `packages/aileron-marketplace-core/`

## Related Architecture and APIs

- [version-control](/architecture/overview/version-control)
- [manager-api](/api/manager-api)
