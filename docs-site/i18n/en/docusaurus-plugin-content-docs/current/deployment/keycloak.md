---
sidebar_position: 4
title: Keycloak Configuration
---

# Keycloak Configuration

Aileron uses [Keycloak](https://www.keycloak.org/) for OAuth2/OIDC authentication with:

- Single Sign-On (SSO)
- OAuth2 Authorization Code Flow with PKCE
- JWT token verification (RS256)
- User role and permission management

## Realm Overview

The platform uses a realm named `aileron`, imported from `keycloak-realm/aileron-realm.json` on first startup.

### Default Client

| Client ID | Type | Description |
|-----------|------|-------------|
| `aileron-frontend` | Public Client | Used by the frontend SPA; no client secret required |

Public client settings:
- **Redirect URIs**: `http://localhost:8082/*`, `http://localhost:8082/callback`
- **Web Origins**: `http://localhost:8082` (CORS allowed origins)
- **Authentication flow**: Authorization Code Flow with PKCE

### Default User

| Username | Password | Roles |
|----------|----------|-------|
| `admin` | `admin123` | `default-roles-aileron` |

### Admin Console

| Environment | URL | Credentials |
|-------------|-----|-------------|
| Docker | `http://localhost:8080/admin` | `admin` / `admin` |
| Kubernetes | `https://keycloak.<baseDomain>/admin` | As configured in Helm values |

## Docker Mode Configuration

In Docker mode, Keycloak runs in `start-dev` mode and auto-imports the realm:

```yaml
# Key settings in docker-compose.yml
keycloak:
  command: start-dev --import-realm
  volumes:
    - ./keycloak-realm:/opt/keycloak/data/import
```

### Inter-Service Authentication Flow

```
Browser → Frontend → Keycloak (OAuth2 login)
                    ↓
                Obtain JWT token
                    ↓
Frontend → Manager API (Bearer token)
              ↓
       Verify JWT signature (JWKS)
```

Both Manager and Runtime validate JWT tokens via Keycloak's JWKS endpoint:

```
http://aileron-keycloak-dev:8080/realms/aileron/protocol/openid-connect/certs
```

### Network Aliases

In Docker mode, Keycloak has two network aliases (`localhost` and `keycloak`). This is because the JWT token's issuer URL contains `localhost`, and containers need to resolve the same hostname when validating tokens.

## Kubernetes Mode Configuration

### Helm Values

```yaml
keycloak:
  enabled: true
  replicaCount: 1
  image:
    repository: quay.io/keycloak/keycloak
    tag: 25.0.0
  service:
    type: ClusterIP
    port: 8080
  auth:
    adminUser: admin
    adminPassword: admin  # Must be changed in production
  env:
    KC_HOSTNAME_STRICT: "false"
    KC_HOSTNAME_STRICT_HTTPS: "false"
    KC_HTTP_ENABLED: "true"
    KC_PROXY_HEADERS: xforwarded
    KC_HEALTH_ENABLED: "true"
    KC_METRICS_ENABLED: "true"
```

### Public URL Configuration

In Kubernetes mode, Keycloak's public URL is derived from `publicRouting`:

```yaml
publicRouting:
  scheme: https
  baseDomain: example.com
  keycloakHost: "keycloak.{baseDomain}"
```

The Helm template generates `PUBLIC_KEYCLOAK_URL` and injects it into the platform-config ConfigMap; Manager and Frontend use this to configure OIDC endpoints.

### Realm Import

In Kubernetes mode, the realm JSON is mounted via ConfigMap:

```
helm/aileron/files/realm.json
  → keycloak-realm-configmap
  → mounted into Keycloak pod
```

## Customizing the Realm

### Adding a Client

To add an OAuth2 client for another service (e.g., mobile app, CLI tool):

1. Open Keycloak Admin Console
2. Select `aileron` realm
3. **Clients** → **Create client**
4. Configure:
   - **Client type**: OpenID Connect
   - **Client ID**: your custom name
   - **Client authentication**: Off for SPAs, On for backends
5. Configure **Valid redirect URIs** and **Web origins**

### Adding Redirect URIs

When deploying to a new domain, update the client's Redirect URIs:

**Docker mode**: Edit via Keycloak Admin Console, or edit `keycloak-realm/aileron-realm.json` and re-import.

**Kubernetes mode**: Edit `helm/aileron/files/realm.json` and redeploy:

```bash
helm upgrade aileron helm/aileron \
  --namespace aileron
```

### Adding Users

1. Open Keycloak Admin Console
2. Select `aileron` realm
3. **Users** → **Add user**
4. Configure username and email
5. Set password in the **Credentials** tab

## Production Recommendations

### Security

- **Change all default passwords**: admin, bootstrap, database
- **Enable HTTPS**: set `KC_HTTPS_ENABLED=true` or terminate TLS at the Ingress
- **Enable strict hostname**: set `KC_HOSTNAME_STRICT=true`
- **Disable HTTP**: set `KC_HTTP_ENABLED=false` (once TLS is in place)

### High Availability

- Use external PostgreSQL (not Helm-managed)
- Configure multiple Keycloak replicas (requires distributed cache like Infinispan)
- Configure session affinity / sticky sessions

### Backup

- Periodically export realm settings:
  ```bash
  # Export via Admin API
  curl -X POST "https://keycloak.example.com/admin/realms/aileron/partial-export?exportClients=true&exportGroupsAndRoles=true" \
    -H "Authorization: Bearer $ADMIN_TOKEN" \
    -o realm-backup.json
  ```
- Back up the Keycloak database

### Monitoring

Keycloak has built-in metrics endpoints (enabled by `KC_METRICS_ENABLED=true`):

```
GET /metrics
GET /health
GET /health/ready
GET /health/live
```
