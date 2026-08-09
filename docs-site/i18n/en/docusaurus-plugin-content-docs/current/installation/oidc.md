---
title: External OIDC Installation
---

# External OIDC Installation

Aileron requires an external OpenID Connect identity provider. The core Helm Chart does not deploy
Keycloak, LDAP, a realm, a provider database, or any IdP administration component. Development and
CI may install a separate IdP, but it cannot be an Aileron subchart.

## Provider configuration

Create a confidential client, enable Authorization Code flow, and register:

- Redirect URI: `{Platform Public Origin}/api/v1/oauth2/callback`
- Post-logout URI: `{Platform Public Origin}/login`
- Scope: at least `openid`, normally with `profile email`

Manager Pods must reach the issuer, issuer-derived Discovery, and JWKS. User browsers must reach the authorization
endpoint. Aileron does not call a provider-specific administration API.

## Helm values

```yaml
platformPublicOrigin: https://aileron.example.com

oidc:
  issuerUrl: https://login.example.com/realms/aileron
  clientId: aileron-manager
  clientSecretName: aileron-oidc-client
  clientSecretKey: client-secret
```

`clientSecretName` must reference an existing Secret; the Chart never generates a client secret.
For a private provider CA, also configure `caSecretName` and `caSecretKey`. OIDC configuration and
secret are injected only into Manager, never Runtime, Terminal, or Operator. Scopes, signature
algorithms, token lifetime, JWKS cache, and Discovery timeout are managed by the Manager's single
typed settings model defaults and are not Helm installation inputs.

Discovery is always `{issuerUrl}/.well-known/openid-configuration`. Callback, post-logout redirect,
CORS, and CSRF Origin are all derived from `platformPublicOrigin` and cannot be overridden separately.

OIDC is used only for login, callback, and optional provider logout. After a successful callback
creates a Manager Session, valid Sessions are authenticated and authorized entirely by the local
platform without provider calls. Only `401 MANAGER_SESSION_REQUIRED`, produced for a missing,
expired, revoked, or principal-mismatched Session, makes Frontend re-enter the OIDC authorization
flow. `403 PLATFORM_AUTHORIZATION_DENIED` means the local user or platform operation is denied and
does not trigger reauthentication.

Manager uses fixed internal policies for Session activity touch and expired-data cleanup. They are
not Docker Compose environment variables or Helm values, and neither Docker nor Kubernetes accepts
touch or cleanup installation inputs.

## Readiness and failure

At startup, Manager validates the Discovery issuer, allowed algorithms, and at least one JWKS
signing key. Invalid configuration prevents startup. During provider outage, new login attempts fail
closed, but existing valid Manager Sessions do not become invalid. Frontend never calls the provider
token endpoint directly and never stores provider tokens.

## Signing Secret

Execution Grants use a separate Manager-to-Execution Ed25519 authority. The `runtimeAssertions`
private-key Secret is mounted only by Manager, while Runtime and Terminal receive the public-JWKS
Secret. The Chart never generates key material. Rotation publishes the new public key first,
confirms consumers have loaded it, switches the active private key, then removes the retired key
after the token TTL and rollout propagation window.

## Related documentation

- [Identity and Access Control](/architecture/overview/identity-and-access)
- [Helm Values Reference](/reference/helm-values)
- [Environment Variable Reference](/installation/environment-variables)
