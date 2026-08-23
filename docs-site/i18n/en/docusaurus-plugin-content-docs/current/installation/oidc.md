---
title: OIDC and Identity Plane Installation
---

# OIDC and Identity Plane Installation

Aileron Core depends only on standard OpenID Connect. An installation must select exactly one
Identity adapter:

- `bundledKeycloak`: the product-provided default Keycloak Identity Plane.
- `externalOidc`: an OIDC provider supplied by the installer.

Both modes project only an issuer, client ID, client Secret reference, and CA reference to Workspace
Manager. Frontend, Runtime, Terminal, and Operator never receive provider tokens, Keycloak
administration interfaces, or LDAP configuration.

## Bundled Keycloak

Kubernetes uses the independent `helm/aileron-identity` chart. The Identity Plane has its own Helm
release, namespace, PostgreSQL database, PVCs, Secrets, Ingress, and backup lifecycle. It is not a
`helm/aileron` subchart and does not share the platform PostgreSQL database. The installer creates
and validates the namespace and existing Secrets first, installs the Identity Plane, and installs
the Aileron release only after Discovery and JWKS are ready.

The Identity chart's own `postgres.enabled` value selects its PostgreSQL source independently from
the `bundledKeycloak`/`externalOidc` adapter choice. With an external Identity database, Keycloak,
preflight, backup, and restore use the same connection and TLS contract described in
[External Data Services](./external-data-services.md).

The Identity chart creates neither Namespaces nor Secrets and accepts no plaintext credentials.
Every workload mounts existing Secret files, and Keycloak and PostgreSQL images use immutable
digests. `identity-installation/generate_secrets.py` creates or validates the required artifacts in
an external mode-`0700` directory. Artifact files are mode `0600`, and Secret values are never
printed.

The Keycloak Admin Console administrator, Keycloak native break-glass principal, and Aileron
bootstrap admin principal have separate responsibilities. The Admin Console manages the realm and
native users. The native break-glass principal still signs in through standard OIDC. Aileron grants
platform roles only from `(issuer, subject)`. Self-registration is disabled by default.

### Bundled Accounts and Passwords

Bundled Keycloak creates three accounts with separate responsibilities. An account name containing
`admin` does not grant the Aileron platform-admin role. Use each account only for the purpose below:

| Account | Default username | Password | Purpose and Aileron role |
| --- | --- | --- | --- |
| Aileron platform administrator | `admin` | General Kubernetes installations generate a strong random password; only an isolated test deployment explicitly uses `admin123` | Signs in to Aileron through normal OIDC with `platform_role=admin` to manage users, platform resources, and Marketplace content |
| Keycloak bootstrap administrator | `keycloak-admin` | Strong random password generated during installation; no fixed default | Signs in only to the Keycloak Admin Console to manage the realm and native users; it is not an Aileron platform administrator |
| Break-glass | `local-emergency-admin` | Strong random password generated during installation; no fixed default | Emergency OIDC sign-in; it defaults to Aileron `member` unless a platform administrator explicitly promotes it |

:::danger Never reuse the test password in a shared environment
`admin123` exists only for convenient sign-in to an isolated local test deployment. Replace
it with a unique strong password before allowing access from other users, networks, or the Internet.
General Kubernetes and bundled installations must not reuse this value.
:::

The installer never writes random passwords to Git, documentation, logs, or acceptance reports. The
installation-owned artifacts are kept in the following mode-`0700` private tree, with
mode-`0600` credential files:

```text
<private-root>/install-secrets/rke2/identity-artifacts/keycloak-platform-admin/{subject,username,email,password,import.json}
<private-root>/install-secrets/rke2/identity-artifacts/keycloak-bootstrap-admin/{username,password}
<private-root>/install-secrets/rke2/identity-artifacts/keycloak-break-glass/{username,email,password}
```

The default `<private-root>` is `/root/aileron-private`. In Kubernetes, the corresponding data is in
the `keycloak-platform-admin`, `keycloak-bootstrap-admin`, and `keycloak-break-glass` Secrets in the
`aileron-identity-system` Namespace. Only an authorized cluster administrator may read them. Never
paste `kubectl get secret ... -o yaml` output into tickets, chat, or shell history. For a general
installation, use its actual private root and installer-generated artifact inventory.

Docker's `local-oidc` profile also runs Keycloak only; it does not deploy OpenLDAP or a test
directory. A future LDAP integration belongs inside Keycloak User Federation and does not change
Aileron's OIDC, JIT, or authorization contracts. This release provides no LDAP workload, seed,
Secret, or federation setting.

## External OIDC provider

Create a confidential client, enable Authorization Code flow, and register:

- Redirect URI: `{Platform Public Origin}/api/v1/oauth2/callback`
- Post-logout URI: `{Platform Public Origin}/login`
- Scope: at least `openid`, normally with `profile email`

Manager Pods must reach the issuer, issuer-derived Discovery, and JWKS. User browsers must reach the authorization
endpoint. Aileron does not call a provider-specific administration API.

In `externalOidc` mode, the installer does not render or install the Identity Plane. The external
provider must pass the same standard OIDC conformance as Bundled Keycloak and is not a fallback for
a failed bundled provider.
The acceptance bundle's `offlineOidcConformance` report validates only the provider-neutral
adapter and product data contract and is explicitly marked with `mode: offline`. It does not deploy,
connect to, or claim certification of an external provider. Before production use of `externalOidc`,
the installer must separately exercise Authorization Code with PKCE, JIT, and failed-login scenarios
against the selected provider.

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
