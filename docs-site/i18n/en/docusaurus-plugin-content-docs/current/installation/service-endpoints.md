---
title: Service Endpoints and Accounts
---

# Service Endpoints and Accounts

Browsers use one Platform Public Origin. Docker defaults to `http://localhost:8082`; Kubernetes uses `platformPublicOrigin`.

## Public paths

| Function | Path |
| --- | --- |
| Frontend SPA | `/` |
| Manager API | `/api/v1/...` |
| OIDC login, callback, and logout | `/api/v1/oauth2/...` |
| Workspace Runtime | `/workspaces/{workspaceId}/runtime/...` |
| Workspace Browser | `/workspaces/{workspaceId}/browser/...` |
| Workspace Canvas | `/workspaces/{workspaceId}/canvas/...` |

Frontend's gateway accepts only a canonical Workspace UUID and the fixed `runtime`, `browser`, or `canvas` target. Browsers receive no Service DNS, container port, Workspace host, or request-supplied upstream.

## Local Docker endpoints

| Service | URL | Description |
| --- | --- | --- |
| Aileron | `http://localhost:8082` | Sole browser entry point |
| Connectivity Gateway | `http://localhost:18083` | Evidence endpoint for the host frontend vantage, not a public Manager API |
| Coturn | `turn:localhost:3478` | TURN control listener; the profile owns the relay range |

## Sign-in

The selected Identity adapter owns sign-in credentials. Docker and Kubernetes configure the canonical issuer and Manager confidential client. Bundled Keycloak native users are managed through the Keycloak Admin Console. Aileron bootstrap administration creates only a local role snapshot and never creates a Provider password.

## Workspace health

Runtime health uses a same-origin path:

```text
GET /workspaces/{workspaceId}/runtime/health
```

Browser and Canvas use fixed Workspace paths on the same Origin and never depend on a dynamic hostname or port.
