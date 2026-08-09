---
title: Users
---

# Users

## Purpose and entry point

The Users, role-issues, and disabled views search local account snapshots and provide platform-admin
governance for role and account state. Aileron does not provide provider passwords, temporary
passwords, or a provider administration API.

## Core fields

`oidcIssuer` + `oidcSubject` is the canonical external identity. Local user ID, username, email,
platform role, and account state are separate fields. Provider profile-claim changes do not change
the identity.

## Main flow

Manager JIT-syncs a snapshot at sign-in. A platform admin can query users, replace a local platform
role, or handle a disabled/role-issue state; each mutation refreshes the list and
`/api/v1/oauth2/session` `allowedOperations`.

## Limits and security

Do not delete or demote the last usable platform admin. Tokens, provider credentials, and secrets
never enter logs; all user-facing errors use i18n keys.

## Source index

- `frontend/src/features/user-management/`
- `workspace-manager/app/modules/identity/admin_router.py`
- `workspace-manager/app/modules/identity/admin.py::UserAdminService`
- `workspace-manager/app/modules/identity/snapshot_sync.py`

## Related documentation and APIs

- [Identity Synchronization and OIDC](/architecture/backend/workspace-manager/identity-and-access)
- [Manager API](/api/manager-api)
