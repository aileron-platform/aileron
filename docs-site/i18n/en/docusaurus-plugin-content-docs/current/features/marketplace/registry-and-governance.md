---
title: Registry and Governance
---

# Registry and Governance

## Purpose and Entry Point

Platform admins use Marketplace Settings to manage Registry, SSH keys, version control, and activity records.

## Roles and Allowed Operations

Registry and governance are admin-only. Registry queries do not start before the operation gate passes.

## Core Concepts

Registry source, synchronization state, package identity, and audit record are distinct.

## Primary Workflow

Add or update a registry, validate connectivity, synchronize the catalog, and inspect activity records.

## View States and Read-only Behavior

The view handles loading, empty, error, and denied states separately. With read-only operations, readable content and normal mutation controls remain visible while mutations are disabled with an i18n reason. Without read access, protected queries, providers, and realtime connections do not start.

## Constraints, Failures, and Safety

SSH private keys and credentials are not echoed. Synchronization failures preserve source and error without deleting the last-known-good catalog.

## Source Basis

- `frontend/src/features/marketplace/features/marketplace-settings/MarketplaceSettingsPage.tsx`
- `workspace-manager/app/modules/marketplace/workflows/registry_operations.py`
- `workspace-manager/app/modules/marketplace/activity_repository.py`

## Related Architecture and APIs

- [workspace-manager](/architecture/backend/workspace-manager/)
- [manager-api](/api/manager-api)
