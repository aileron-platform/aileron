---
title: Knowledge Base
---

# Knowledge Base

## Purpose and Entry Point

Knowledge Base Center manages files and versioned content reusable across Workspaces, entered at `/knowledge-base`.

## Roles and Allowed Operations

Platform members list and create. Resource readers view detail, managers manage content/settings/sharing, and owners permanently delete.

## Core Concepts

The knowledge-base resource, Git repository, sharing source, and Workspace usage are separate. Mount mutations belong to Workspace Settings.

## Primary Workflow

Create a knowledge base, manage files and versions, configure sharing, then mount it from Workspace Settings.

## View States and Read-only Behavior

The view handles loading, empty, error, and denied states separately. With read-only operations, readable content and normal mutation controls remain visible while mutations are disabled with an i18n reason. Without read access, protected queries, providers, and realtime connections do not start.

## Constraints, Failures, and Safety

Deletion checks owner and Workspace usage. Public access grants reader only, never mutation.

## Source Basis

- `frontend/src/features/knowledge-base/KnowledgeBaseModule.tsx::KnowledgeBaseModule`
- `frontend/src/features/knowledge-base/routes/KnowledgeBaseDetailRoute.tsx::KnowledgeBaseDetailRoute`
- `workspace-manager/app/modules/knowledge_base/`

## Related Architecture and APIs

- [identity-and-access](/architecture/overview/identity-and-access)
- [manager-api](/api/manager-api)
