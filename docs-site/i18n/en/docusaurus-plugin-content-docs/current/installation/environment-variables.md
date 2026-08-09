---
title: Environment Variable Reference
---

# Environment Variable Reference

Aileron separates installation inputs from container outputs. The repository-root `.env` is the only Docker installation surface, and Helm values are the only Kubernetes installation surface. Service directories have no independent `.env` contract, and Adapter-derived values are not installation inputs.

## Shared installation settings

| Logical setting | Docker | Kubernetes | Description |
| --- | --- | --- | --- |
| Platform Public Origin | `PLATFORM_PUBLIC_ORIGIN` | `platformPublicOrigin` | Exact `http(s)://host[:port]` with no path, query, fragment, credentials, or trailing slash |
| Canonical OIDC issuer | `OIDC_ISSUER_URL` | `oidc.issuerUrl` | External provider issuer; distinct from Platform Public Origin |
| OIDC client ID | `OIDC_CLIENT_ID` | `oidc.clientId` | Manager confidential client ID |
| OIDC client secret | `${HOST_PLATFORM_SECRETS_DIR}/oidc-client-secret` | `oidc.clientSecretName` + `oidc.clientSecretKey` | Secret reference consumed only by Manager |

Manager is the sole OIDC client. Discovery is always `{OIDC_ISSUER_URL}/.well-known/openid-configuration`. Platform Public Origin deterministically derives:

- callback: `{origin}/api/v1/oauth2/callback`
- post-logout redirect: `{origin}/login`
- credentialed-request, CSRF, and CORS Origin: `{origin}`

These derived values cannot be overridden independently. Frontend, Runtime, Terminal, and Operator receive no external issuer, OIDC client secret, or provider token.

During a valid Manager Session, the platform handles authentication locally. Session activity touch
and absolute-expiry cleanup use fixed internal policies; Docker Compose and Helm expose no touch or
cleanup installation variables.

## Docker Compose installation inputs

The root `.env.example` lists the complete Compose input surface. Its main groups are:

| Group | Variables |
| --- | --- |
| Installation identity | `TZ`, `AILERON_INSTALLATION_ID`, `BOOTSTRAP_ADMIN_SUBJECT`, `BOOTSTRAP_ADMIN_USERNAME`, `BOOTSTRAP_ADMIN_EMAIL` |
| Host sources | `HOST_PROJECT_ROOT`, `HOST_PLATFORM_SECRETS_DIR`, `HOST_TURN_CONFIG_DIR`, `HOST_TURN_SECRETS_DIR` |
| Browser and TURN | `TURN_CREDENTIAL_REVISION`, `TURN_CONNECTIVITY_GATEWAY_EXTERNAL_PORT`, `TURN_RELAY_MIN_PORT`, `TURN_RELAY_MAX_PORT` |
| Frontend capability | `VITE_BROWSER_EXTENSION_ID` |
| Image selection | `WORKSPACE_MANAGER_IMAGE`, `WORKSPACE_OPERATOR_IMAGE`, `WORKSPACE_RUNTIME_IMAGE`, `WORKSPACE_UI_IMAGE`, `COTURN_IMAGE` |

The Compose Adapter produces fixed container paths, Service DNS, callback, logout, Origin, and service defaults. Those values do not belong in the root `.env`.

## Kubernetes Helm installation inputs

Helm uses `platformPublicOrigin`, `oidc.*`, `platformSecrets.*`, `runtimeAssertions.*`, and existing Secret name/key settings owned by each feature. The Chart does not accept arbitrary service environment overrides. The public Ingress serves one Platform Public Origin host; Frontend's same-origin path gateway routes Runtime, Browser, and Canvas traffic.

## Workspace Runtime platform environment

Manager Provisioner and Workspace Operator inject the same `AILERON_*` key set. These are Adapter outputs, not deployer or Workspace-user settings:

| Variable | Description |
| --- | --- |
| `AILERON_WORKSPACE_ID` | Workspace ID |
| `AILERON_WORKSPACE_PATH` | Workspace filesystem root |
| `AILERON_RUNTIME_INSTANCE_ID` | Execution-plane generation ID |
| `AILERON_RUNTIME_ACCESS_REVISION` | Runtime access revision |
| `AILERON_KB_MOUNT_REVISION` | Knowledge Base mount revision |
| `AILERON_WORKTREE_SUBDIR` | Managed Git worktree subdirectory |
| `AILERON_MANAGER_INTERNAL_URL` | Internal Manager Service URL |
| `AILERON_PLATFORM_PUBLIC_ORIGIN` | Sole exact platform Origin |
| `AILERON_RUNTIME_STATE_DATABASE_URL_FILE` | Workspace-scoped database URL Secret file |
| `AILERON_RUNTIME_CONTROL_TOKEN_FILE` | Generation-scoped control-token Secret file |
| `AILERON_RUNTIME_ASSERTION_PUBLIC_KEY_SET_FILE` | Manager assertion public JWKS file |
| `AILERON_RUNTIME_ASSERTION_ISSUER` | Manager assertion issuer |
| `AILERON_BROWSER_SERVICE_NAME` | Internal Browser service name |
| `AILERON_BROWSER_WEBRTC_INTERNAL_URL` | Internal Browser WebRTC URL |
| `AILERON_BROWSER_CDP_URL` | Internal Browser CDP URL |
| `AILERON_CANVAS_SERVICE_NAME` | Internal Canvas service name |
| `AILERON_CANVAS_INTERNAL_URL` | Internal Canvas renderer URL |
| `AILERON_CANVAS_API_URL` | Internal Canvas management API URL |

Workspace-user environments may not use the `AILERON_*` prefix.

## Secret delivery

- Docker: the root `.env` stores only host Secret directory or file paths. Compose mounts them read-only, and services consume only `*_FILE` or fixed mounted paths.
- The local OpenLDAP adapter uses the third-party image's native `LDAP_ADMIN_PASSWORD_FILE` and `LDAP_CONFIG_PASSWORD_FILE` interface only during first-start initialization. The long-running `slapd` argv and environment must not contain Secret values afterward.
- Kubernetes: values store only existing Secret names and keys. Application Pods receive Secrets only through read-only Secret volumes and consume them through `*_FILE` or contract-defined fixed mounted paths.
- Application Secrets must not be materialized into the process environment through `SecretKeyRef` or `envFrom.secretRef`. `SecretKeyRef` is not an accepted Secret delivery interface.
- Secret values never belong in ordinary environment variables, ConfigMaps, Frontend build environments, documentation examples, or version control.

## Frontend

Frontend uses same-origin relative paths for API, OAuth, Runtime, Browser, Canvas, and WebSocket traffic. It accepts no public URL, API base URL, Workspace host, or dynamic port setting. The only retained build capability flag with a proven consumer is `VITE_BROWSER_EXTENSION_ID`.
