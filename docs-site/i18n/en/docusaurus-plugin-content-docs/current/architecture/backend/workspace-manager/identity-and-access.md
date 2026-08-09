---
title: Manager OIDC BFF and Session
---

# Manager OIDC BFF and Session

## OIDC Core

`workspace-manager/app/modules/auth` is the only external OIDC trust boundary. OIDC Core owns
Authorization Code + PKCE, state, nonce, Discovery, JWKS, ID/Access Token validation, optional
UserInfo, and end-session. Provider access, ID, and refresh tokens are not persisted after creating
the External Principal and local user snapshot.

Invalid static configuration prevents Manager startup. Manager must retrieve canonical Discovery
metadata and at least one usable signing key before it becomes ready. During a provider outage, new
login attempts fail closed, but existing valid Manager Sessions and local authorization remain
valid. OIDC flows accept only unexpired in-memory cache entries, and an unknown `kid` triggers at
most one refresh.

## External Principal and local authorization

The External Principal identity key is `(canonical issuer, sub)`. The first successful login creates
a local member. Different issuers or matching email addresses are never linked automatically. After
a successful callback creates a Manager Session, valid Sessions do not call the IdP, UserInfo,
introspection, or Provider Token refresh. Each Manager request computes `allowedOperations` from the
local Session and User snapshot. Local disablement, an invalid role, or Session revocation takes
effect on the next request.

`ManagerRequestAuthentication` is the single authentication Module for protected HTTP requests. One
indexed projected JOIN reads the required Session and User fields, validates Session evidence, Local
User Authorization Policy, and Origin/CSRF, conditionally updates activity through a fixed internal
touch window, and creates an immutable request context and Authorization Actor after releasing the
authentication database connection. Session Bootstrap, Logout, and operation policy reuse that
context without parsing the Cookie or querying Session/User again.

## Session and CSRF

- `GET /api/v1/oauth2/login` creates state, nonce, and a PKCE verifier, then redirects to the provider.
- `GET /api/v1/oauth2/callback` exchanges the code, validates the provider response, and creates a session.
- `GET /api/v1/oauth2/session` returns the local user, `allowedOperations`, absolute expiry, and the Session-bound CSRF token.
- `POST /api/v1/oauth2/logout` requires session, Origin, and CSRF, then deletes the local session first.

The cookie contains only an opaque handle. The database stores its SHA-256 hash, `user_id`, issuer,
subject, authentication context, and timestamps. Frontend keeps the CSRF token only in memory; the
database stores the current Session-bound token for mutation validation. GET, HEAD, and OPTIONS never mutate state.

Missing, expired, revoked, or principal-mismatched Session evidence returns
`401 MANAGER_SESSION_REQUIRED`; only that response lets Frontend start OIDC reauthentication once.
Valid Session evidence with a denied Local User Authorization Policy or platform operation returns
`403 PLATFORM_AUTHORIZATION_DENIED`, preserves the Session, and does not reauthenticate. Origin and
CSRF denials use their own 403 error codes.

Session activity touch and absolute-expiry cleanup use fixed internal windows, schedules, and bounded
batches. The request hot path does not synchronously delete expired Sessions. Neither lifecycle
policy exposes an environment variable, Compose setting, or Helm value.

## Execution Grant issuance seam

`POST /api/v1/workspaces/{workspaceId}/execution-grants` accepts a Runtime instance, one audience,
and explicit actions. Manager calls `WorkspaceRuntimeAccessService.authorize` for every action, then
`RuntimeAssertionService.sign_execution_grant` signs the current instance and access revision. There
is no `all`, implicit expansion, or cross-audience Grant.

`contracts/workspace-execution-access/` owns the claims, seven actions, audience constraints, and
test vectors. Manager, Runtime, and Terminal cannot define another public contract.

## Container verification

```bash
docker compose -f workspace-manager/docker-compose.test.yml run --rm workspace-manager-test \
  uv run pytest tests/unit/modules/auth \
  tests/unit/modules/workspace/runtime/test_execution_grant.py \
  tests/unit/modules/workspace/runtime/test_execution_grant_contract.py
```

## Related documentation

- [Identity and Access Control](/architecture/overview/identity-and-access)
- [External OIDC Installation](/installation/oidc)
- [Manager API](/api/manager-api)
