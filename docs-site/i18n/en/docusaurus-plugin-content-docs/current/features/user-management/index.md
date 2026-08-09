---
title: User Management
---

# User Management

## Purpose and entry point

Platform admins use `/user-management` to manage local user snapshots, groups, platform roles, and
account state. The resource-authorization model remains canonical in [Permissions and Roles](/features/platform/permissions-and-roles).

## Identity and local accounts

The OIDC provider owns sign-in and credentials. Manager uses `(oidc_issuer, oidc_subject)` as the
canonical external identity, creates a member snapshot on first successful sign-in, and syncs
optional username, email, and display-name claims. Keycloak and LDAP can only back an external
provider; they are not UI or API management dependencies.

## Roles and operations

Every user-management Operation ID is platform-admin-only. Manager owns local `admin`/`member`
platform roles; Workspace/Knowledge Base `reader`, `manager`, `owner`, and group shares belong to
resource authorization.

## UI and failure behavior

The UI handles loading, empty, error, and denied states separately. Read-only access preserves
readable content and disabled mutation controls; without a read operation it does not start protected
queries, Providers, or WebSockets. Sync or database failures retain diagnosable state and never
appear as completed partial success.

## Source index

- `frontend/src/features/user-management/UserManagementModule.tsx`
- `workspace-manager/app/modules/identity/admin.py::UserAdminService`
- `workspace-manager/app/modules/identity/snapshot_sync.py`

## Related documentation and APIs

- [Identity Synchronization and OIDC](/architecture/backend/workspace-manager/identity-and-access)
- [Identity and Access Control](/architecture/overview/identity-and-access)
- [Manager API](/api/manager-api)
