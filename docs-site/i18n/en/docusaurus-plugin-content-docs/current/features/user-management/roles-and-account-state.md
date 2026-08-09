---
title: Platform Roles and Account State
---

# Platform Roles and Account State

## Purpose and entry point

Platform admins use user management to change local `admin`/`member` platform roles and handle
role-issue, enabled, and disabled account states.

## Core model

Platform roles expand only platform operations; a disabled account is rejected by local
authorization policy on the next request. Neither change directly modifies Workspace or Knowledge
Base resource shares. A provider role claim may be login input, but the local role is the
authoritative authorization state.

## Main flow

After replacing a local platform role or account state, the next Manager request applies the local
`UserAuthorizationPolicy` directly, and `/api/v1/oauth2/session` returns `allowedOperations` from
the current role. The last usable platform admin cannot be disabled, deleted, or demoted.

## Failure and security

Unknown or multiple managed platform roles become a role issue and fail closed. All management
operations require a platform admin; secrets, tokens, and provider responses never enter logs, and
display text uses i18n keys.

## Source index

- `workspace-manager/app/modules/identity/platform_role.py::PlatformRole`
- `workspace-manager/app/modules/identity/authorization.py::PlatformAuthorizationService`
- `workspace-manager/app/modules/identity/admin_router.py`

## Related documentation and APIs

- [Identity and Access Control](/architecture/overview/identity-and-access)
- [Platform Permissions and Roles](/features/platform/permissions-and-roles)
- [Manager API](/api/manager-api)
