---
title: Groups
---

# Groups

## Purpose and entry point

Platform admins create local groups and manage members through the user-management groups and group
members routes.

## Core model

Provider-side groups, when a provider supplies them, and Aileron local groups are separate layers.
Resource `group_share` references an Aileron local group and never copies provider membership; an
LDAP group does not automatically become a resource share.

## Main flow

Create or select a local group, add/remove members, and refresh user and resource authorization
after the mutation. Every operation requires a platform-admin Operation ID.

## Failure and security

A group mutation can immediately change an effective resource role, so the Frontend must re-query
backend authorization. Restricted reads preserve readable content and disabled mutation controls;
errors use i18n keys.

## Source index

- `frontend/src/features/user-management/`
- `workspace-manager/app/modules/identity/groups.py`
- `workspace-manager/app/modules/identity/group_router.py`

## Related documentation and APIs

- [Identity and Access Control](/architecture/overview/identity-and-access)
- [Manager API](/api/manager-api)
