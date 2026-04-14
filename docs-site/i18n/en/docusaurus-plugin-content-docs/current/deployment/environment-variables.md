---
sidebar_position: 3
title: Environment Variables Reference
---

# Environment Variables Reference

This page lists all service environment variables. Docker mode sets them in `docker-compose.yml`; Kubernetes mode injects them via Helm values or ConfigMaps.

## Workspace Manager

### Core

| Variable | Default | Description |
|----------|---------|-------------|
| `PORT` | `3001` | API listen port |
| `HOST` | `0.0.0.0` | Listen host |
| `NODE_ENV` | `development` | Runtime environment |
| `DEBUG` | `true` | Debug mode |
| `DEPLOYMENT_ENV` | `docker` / `kubernetes` | Deployment mode; determines workspace provisioner |

### Database

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql://postgres:postgres@postgres:5432/aileron` | PostgreSQL connection string |

### Redis / Celery

| Variable | Default | Description |
|----------|---------|-------------|
| `REDIS_URL` | `redis://redis:6379` | Redis URL |
| `CELERY_BROKER_URL` | `redis://redis:6379/0` | Celery broker (uses DB 0) |
| `CELERY_RESULT_BACKEND` | `redis://redis:6379/1` | Celery result backend (uses DB 1) |
| `CELERY_TASK_SERIALIZER` | `json` | Task serializer |
| `CELERY_RESULT_SERIALIZER` | `json` | Result serializer |
| `CELERY_ACCEPT_CONTENT` | `json` | Accepted content types |

### Authentication (JWT)

| Variable | Default | Description |
|----------|---------|-------------|
| `SECRET_KEY` | _(dev default)_ | JWT signing secret. **Must be changed in production.** |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `180` | Access token expiry (minutes) |
| `REFRESH_TOKEN_EXPIRE_DAYS` | `7` | Refresh token expiry (days) |

### Keycloak (OAuth2/OIDC)

| Variable | Default | Description |
|----------|---------|-------------|
| `KEYCLOAK_SERVER_URL` | `http://aileron-keycloak-dev:8080` | Keycloak internal URL |
| `KEYCLOAK_REALM` | `aileron` | Keycloak realm name |
| `KEYCLOAK_CLIENT_ID` | `aileron-frontend` | OAuth2 client ID |
| `KEYCLOAK_CLIENT_SECRET` | _(empty)_ | OAuth2 client secret (not needed for public clients) |
| `KEYCLOAK_JWKS_CACHE_TTL` | `3600` | JWKS cache TTL (seconds) |

### Docker Mode Only

| Variable | Default | Description |
|----------|---------|-------------|
| `DOCKER_HOST` | `unix:///var/run/docker.sock` | Docker daemon socket |
| `DOCKER_NETWORK` | `aileron-network-dev` | Docker network name |
| `WORKSPACE_RUNTIME_URL` | `http://workspace-runtime:3002` | Runtime internal URL |
| `HOST_PROJECT_ROOT` | `.` | Project root on host |
| `HOST_WORKSPACE_RUNTIME_DIR` | `./workspace-runtime` | Runtime directory on host |
| `HOST_WORKSPACE_MANAGER_DIR` | `./workspace-manager` | Manager directory on host |
| `HOST_WORKSPACES_DIR` | `./data/workspace-data` | Workspace data directory |

### Claude API

| Variable | Default | Description |
|----------|---------|-------------|
| `ANTHROPIC_BASE_URL` | _(empty)_ | Claude API base URL (for custom proxy) |
| `ANTHROPIC_AUTH_TOKEN` | _(empty)_ | Claude API token |

---

## Workspace Runtime

### Core

| Variable | Default | Description |
|----------|---------|-------------|
| `PORT` | `3002` | API listen port |
| `NODE_ENV` | `development` | Runtime environment |
| `ENV` | `development` | Application environment |
| `WORKSPACE_ID` | `default-workspace` | Workspace ID |
| `WORKSPACE_MANAGER_URL` | `http://workspace-manager:3001` | Manager internal URL |
| `DEPLOYMENT_ENV` | `docker` / `kubernetes` | Deployment mode |

### Database

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql://postgres:postgres@postgres:5432/aileron` | PostgreSQL connection string |

### Redis & Request Tracing

| Variable | Default | Description |
|----------|---------|-------------|
| `REDIS_URL` | `redis://redis:6379` | Redis URL |
| `REDIS_HOST` | `redis` | Redis host |
| `REDIS_PORT` | `6379` | Redis port |
| `REDIS_DB` | `0` | Redis DB index |
| `ENABLE_REDIS` | `true` | Enable Redis |
| `REDIS_MAX_CONNECTIONS` | `20` | Max connection pool size |
| `REDIS_SOCKET_TIMEOUT` | `30` | Socket timeout (seconds) |
| `REDIS_RETRY_ATTEMPTS` | `3` | Retry attempts |
| `REQUEST_TTL_SECONDS` | `3600` | Request TTL |
| `CLEANUP_INTERVAL_SECONDS` | `300` | Cleanup interval |

### Internal Authentication

| Variable | Default | Description |
|----------|---------|-------------|
| `INTERNAL_API_TOKEN` | `dev-internal-token` | Service-to-service auth token |

### SSH

| Variable | Default | Description |
|----------|---------|-------------|
| `SSH_PORT` | `22` | SSH listen port |
| `SSH_HOST_KEY_PATH` | `/etc/ssh/ssh_host_rsa_key` | SSH host key path |

### Git

| Variable | Default | Description |
|----------|---------|-------------|
| `GIT_USER_NAME` | `Developer` | Git user name |
| `GIT_USER_EMAIL` | `developer@workspace.local` | Git user email |

### Terminal Service

| Variable | Default | Description |
|----------|---------|-------------|
| `TERMINAL_PORT` | `3004` | Terminal WebSocket port |
| `LOG_LEVEL` | `debug` | Log level |
| `MAX_TABS_PER_WORKSPACE` | `10` | Max terminal tabs per workspace |
| `SESSION_TIMEOUT` | `300` | Session timeout (seconds) |
| `PTY_BUFFER_SIZE` | `1024` | PTY buffer size |

### VS Code Server

| Variable | Default | Description |
|----------|---------|-------------|
| `VSCODE_SERVER_PORT` | `8080` | VS Code Server port |

### Claude API

| Variable | Default | Description |
|----------|---------|-------------|
| `ANTHROPIC_BASE_URL` | _(empty)_ | Claude API base URL |
| `ANTHROPIC_AUTH_TOKEN` | _(empty)_ | Claude API token |

### Keycloak (OAuth2/OIDC)

| Variable | Default | Description |
|----------|---------|-------------|
| `KEYCLOAK_SERVER_URL` | `http://aileron-keycloak-dev:8080` | Keycloak internal URL |
| `KEYCLOAK_REALM` | `aileron` | Realm name |
| `KEYCLOAK_CLIENT_ID` | `aileron-web` | OAuth2 client ID |
| `KEYCLOAK_JWKS_URL` | _(auto-composed)_ | JWKS endpoint URL |
| `KEYCLOAK_JWKS_CACHE_TTL` | `3600` | JWKS cache TTL (seconds) |

### Browser Container Discovery

| Variable | Default | Description |
|----------|---------|-------------|
| `BROWSER_CONTAINER_NAME` | `workspace-browser-default-workspace` | Browser container name |
| `BROWSER_CDP_URL` | `http://workspace-browser-default-workspace:9223` | Chrome DevTools Protocol URL |
| `BROWSER_WEBRTC_INTERNAL_URL` | `http://workspace-browser-default-workspace:6080` | WebRTC internal URL |

### Next.js Container Discovery

| Variable | Default | Description |
|----------|---------|-------------|
| `NEXTJS_CONTAINER_NAME` | `workspace-nextjs-default-workspace` | Next.js container name |
| `NEXTJS_INTERNAL_URL` | `http://workspace-nextjs-default-workspace:3003` | Next.js internal URL |
| `NEXTJS_API_URL` | `http://workspace-nextjs-default-workspace:3013` | Next.js management API URL |

---

## Frontend

| Variable | Default | Description |
|----------|---------|-------------|
| `NODE_ENV` | `development` / `production` | Runtime environment |
| `DOCKER_ENV` | `true` / `false` | Whether running inside Docker |
| `VITE_API_BASE_URL` | `http://localhost:3001` | Manager API URL (browser-side) |
| `VITE_FRONTEND_PUBLIC_URL` | _(empty)_ | Frontend public URL |
| `VITE_KEYCLOAK_SERVER_URL` | `http://localhost:8080` | Keycloak URL (browser-side) |
| `VITE_KEYCLOAK_REALM` | `aileron` | Keycloak realm |
| `VITE_KEYCLOAK_CLIENT_ID` | `aileron-frontend` | Keycloak client ID |
| `VITE_WORKSPACE_K8S_ALLOWED_NAMESPACES` | `workspace-system,default` | Allowed K8s namespaces |
| `VITE_WORKSPACE_K8S_DEFAULT_NAMESPACE` | `workspace-system` | Default K8s namespace |

:::warning VITE_ Prefix
All `VITE_` variables are bundled into the frontend JavaScript. Never put secrets in these variables.
:::

---

## Keycloak

| Variable | Default | Description |
|----------|---------|-------------|
| `KC_HOSTNAME` | `localhost` | Keycloak hostname |
| `KC_HOSTNAME_URL` | `http://localhost:8080` | Public full URL |
| `KC_HOSTNAME_ADMIN_URL` | `http://localhost:8080` | Admin console URL |
| `KC_HOSTNAME_STRICT` | `false` | Strict hostname check |
| `KC_HOSTNAME_STRICT_HTTPS` | `false` | Strict HTTPS check |
| `KC_HTTP_ENABLED` | `true` | Enable HTTP |
| `KC_HTTPS_ENABLED` | `false` | Enable HTTPS |
| `KC_PROXY_HEADERS` | `xforwarded` | Trusted proxy header type |
| `KC_DB` | `postgres` | Database type |
| `KC_DB_URL` | `jdbc:postgresql://postgres:5432/keycloak` | Database URL |
| `KC_DB_USERNAME` | `postgres` | Database user |
| `KC_DB_PASSWORD` | `postgres` | Database password |
| `KC_BOOTSTRAP_ADMIN_USERNAME` | `admin` | Initial admin user |
| `KC_BOOTSTRAP_ADMIN_PASSWORD` | `admin` | Initial admin password |
| `KC_HEALTH_ENABLED` | `true` | Enable health endpoints |
| `KC_METRICS_ENABLED` | `true` | Enable metrics endpoint |

---

## Workspace Browser (neko)

| Variable | Default | Description |
|----------|---------|-------------|
| `WORKSPACE_ID` | `default-workspace` | Workspace ID |
| `NEKO_SERVER_BIND` | `:6080` | neko listen address |
| `NEKO_DESKTOP_SCREEN` | `1440x900@30` | Desktop resolution and FPS |
| `NEKO_MEMBER_MULTIUSER_USER_PASSWORD` | `neko` | Regular user password |
| `NEKO_MEMBER_MULTIUSER_ADMIN_PASSWORD` | `admin` | Admin password |
| `NEKO_WEBRTC_ICELITE` | `1` | Enable ICE Lite mode |
| `NEKO_WEBRTC_UDPMUX` | `52000` | WebRTC UDP mux port |
| `NEKO_WEBRTC_NAT1TO1` | `127.0.0.1` | NAT 1:1 mapping IP |
| `NEKO_SESSION_IMPLICIT_HOSTING` | `true` | Auto-assign host permissions |

---

## Workspace Next.js

| Variable | Default | Description |
|----------|---------|-------------|
| `WORKSPACE_ID` | `default-workspace` | Workspace ID |
| `PORT` | `3003` | Next.js dev server port |
| `API_PORT` | `3013` | Management API port |
| `WORKSPACE_DIR` | `/workspace` | Workspace directory |
| `NODE_ENV` | `development` | Runtime environment |

---

## Workspace Operator (Kubernetes only)

| Variable | Default | Description |
|----------|---------|-------------|
| `LOG_LEVEL` | `info` | Log level |
| `WORKSPACE_CRD_GROUP` | `platform.aileron.io` | CRD API group |
| `WORKSPACE_CRD_VERSION` | `v1alpha1` | CRD API version |
| `WATCH_NAMESPACE` | _(empty)_ | Watch namespace; empty means watch all |

---

## Kubernetes ConfigMap Injection

In Kubernetes mode, the platform-config ConfigMap auto-injects these variables:

| ConfigMap Key | Description |
|---------------|-------------|
| `PUBLIC_SCHEME` | Public routing scheme |
| `PUBLIC_BASE_DOMAIN` | Base domain |
| `PUBLIC_FRONTEND_URL` | Full Frontend URL |
| `PUBLIC_WORKSPACE_MANAGER_URL` | Full Manager URL |
| `PUBLIC_KEYCLOAK_URL` | Full Keycloak URL |
| `PUBLIC_RUNTIME_HOST_PATTERN` | Runtime host pattern |
| `PUBLIC_BROWSER_HOST_PATTERN` | Browser host pattern |
| `PUBLIC_NEXTJS_HOST_PATTERN` | Next.js host pattern |
| `RUNTIME_PROVISIONER` | Provisioner type |
| `RUNTIME_K8S_NAMESPACE` | Default K8s namespace |
| `RUNTIME_K8S_ALLOWED_NAMESPACES` | Allowed namespaces |
| `RUNTIME_K8S_SERVICE_TYPE` | Service type |
| `RUNTIME_K8S_IMAGE` | Runtime image |
| `RUNTIME_K8S_BROWSER_IMAGE` | Browser image |
| `RUNTIME_K8S_NEXTJS_IMAGE` | Next.js image |
| `CILIUM_ENABLED` | Whether Cilium is enabled |
| `FIREWALL_DEFAULTS_CONFIGMAP_NAME` | Firewall defaults ConfigMap name |
