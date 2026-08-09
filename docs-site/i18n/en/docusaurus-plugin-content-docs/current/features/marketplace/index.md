---
title: Marketplace
---

# Marketplace

## Purpose and Entry Point

Marketplace is the product surface for browsing, installing, editing, and governing packages, entered at `/marketplace/packages`.

## Roles and Allowed Operations

Members and admins browse, export, and install. Publishing, content management, deletion, and Registry management are admin-only.

## Core Concepts

Catalog package, provider, user copy, draft, and registry source are distinct entities.

## Primary Workflow

Select a catalog package and install a user copy. Admins can open the editor, edit, and publish.

## View States and Read-only Behavior

The view handles loading, empty, error, and denied states separately. With read-only operations, readable content and normal mutation controls remain visible while mutations are disabled with an i18n reason. Without read access, protected queries, providers, and realtime connections do not start.

## Constraints, Failures, and Safety

Clone/import failures retain explicit state. Display-only deduplication never replaces canonical identity handling.

## Source Basis

- `frontend/src/features/marketplace/MarketplaceModule.tsx::MarketplaceModule`
- `frontend/src/features/marketplace/model/marketplacePermissions.ts::resolveMarketplacePermissions`
- `workspace-manager/app/modules/marketplace/`
- `packages/aileron-marketplace-core/`

## Related Architecture and APIs

- [frontend](/architecture/frontend/)
- [manager-api](/api/manager-api)
