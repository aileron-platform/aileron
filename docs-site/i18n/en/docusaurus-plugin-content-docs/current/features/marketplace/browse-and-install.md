---
title: Browse and Install
---

# Browse and Install

## Purpose and Entry Point

Enter from the Marketplace catalog or package detail to search, filter, export, and install packages.

## Roles and Allowed Operations

Members and admins can browse, export, and install, subject to final platform Operation ID checks.

## Core Concepts

Provider plus package ID forms route identity. Installation creates a user copy and does not mutate the catalog source.

## Primary Workflow

Open details, choose an install target, create the user copy, and refresh the list using canonical identity.

## View States and Read-only Behavior

The view handles loading, empty, error, and denied states separately. With read-only operations, readable content and normal mutation controls remain visible while mutations are disabled with an i18n reason. Without read access, protected queries, providers, and realtime connections do not start.

## Constraints, Failures, and Safety

clone_failed, conflicts, and unsupported providers are explicit. One canonical resource never becomes duplicate installed entries.

## Source Basis

- `frontend/src/features/marketplace/`
- `workspace-manager/app/modules/marketplace/user_copy.py`
- `packages/aileron-marketplace-core/`

## Related Architecture and APIs

- [version-control](/architecture/overview/version-control)
- [manager-api](/api/manager-api)
