---
sidebar_position: 3
title: 環境變數參考
---

# 環境變數參考

本頁列出所有服務的環境變數。Docker 模式直接在 `docker-compose.yml` 設定，Kubernetes 模式透過 Helm values 或 ConfigMap 注入。

## Workspace Manager

### 核心設定

| 變數 | 預設值 | 說明 |
|------|--------|------|
| `PORT` | `3001` | API 監聽 port |
| `HOST` | `0.0.0.0` | 監聽 host |
| `NODE_ENV` | `development` | 執行環境 |
| `DEBUG` | `true` | 除錯模式 |
| `DEPLOYMENT_ENV` | `docker` / `kubernetes` | 部署模式，決定 workspace provisioner |

### 資料庫

| 變數 | 預設值 | 說明 |
|------|--------|------|
| `DATABASE_URL` | `postgresql://postgres:postgres@postgres:5432/aileron` | PostgreSQL 連線字串 |

### Redis / Celery

| 變數 | 預設值 | 說明 |
|------|--------|------|
| `REDIS_URL` | `redis://redis:6379` | Redis 連線 URL |
| `CELERY_BROKER_URL` | `redis://redis:6379/0` | Celery broker（使用 DB 0） |
| `CELERY_RESULT_BACKEND` | `redis://redis:6379/1` | Celery 結果後端（使用 DB 1） |
| `CELERY_TASK_SERIALIZER` | `json` | 任務序列化格式 |
| `CELERY_RESULT_SERIALIZER` | `json` | 結果序列化格式 |
| `CELERY_ACCEPT_CONTENT` | `json` | 接受的內容格式 |

### 認證 (JWT)

| 變數 | 預設值 | 說明 |
|------|--------|------|
| `SECRET_KEY` | _(開發預設值)_ | JWT signing secret，**生產環境必須修改** |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `180` | Access token 有效期（分鐘） |
| `REFRESH_TOKEN_EXPIRE_DAYS` | `7` | Refresh token 有效期（天） |

### Keycloak (OAuth2/OIDC)

| 變數 | 預設值 | 說明 |
|------|--------|------|
| `KEYCLOAK_SERVER_URL` | `http://aileron-keycloak-dev:8080` | Keycloak 內部 URL |
| `KEYCLOAK_REALM` | `aileron` | Keycloak Realm 名稱 |
| `KEYCLOAK_CLIENT_ID` | `aileron-frontend` | OAuth2 Client ID |
| `KEYCLOAK_CLIENT_SECRET` | _(空)_ | OAuth2 Client Secret（public client 不需要） |
| `KEYCLOAK_JWKS_CACHE_TTL` | `3600` | JWKS 快取時間（秒） |

### Docker 模式專用

| 變數 | 預設值 | 說明 |
|------|--------|------|
| `DOCKER_HOST` | `unix:///var/run/docker.sock` | Docker daemon socket |
| `DOCKER_NETWORK` | `aileron-network-dev` | Docker 網路名稱 |
| `WORKSPACE_RUNTIME_URL` | `http://workspace-runtime:3002` | Runtime 內部 URL |
| `HOST_PROJECT_ROOT` | `.` | 主機上的專案根目錄 |
| `HOST_WORKSPACE_RUNTIME_DIR` | `./workspace-runtime` | 主機上 runtime 目錄 |
| `HOST_WORKSPACE_MANAGER_DIR` | `./workspace-manager` | 主機上 manager 目錄 |
| `HOST_WORKSPACES_DIR` | `./data/workspace-data` | 工作區資料目錄 |

### Claude API

| 變數 | 預設值 | 說明 |
|------|--------|------|
| `ANTHROPIC_BASE_URL` | _(空)_ | Claude API Base URL（自訂 proxy 時使用） |
| `ANTHROPIC_AUTH_TOKEN` | _(空)_ | Claude API 認證 Token |

---

## Workspace Runtime

### 核心設定

| 變數 | 預設值 | 說明 |
|------|--------|------|
| `PORT` | `3002` | API 監聽 port |
| `NODE_ENV` | `development` | 執行環境 |
| `ENV` | `development` | 應用環境 |
| `WORKSPACE_ID` | `default-workspace` | 工作區 ID |
| `WORKSPACE_MANAGER_URL` | `http://workspace-manager:3001` | Manager 內部 URL |
| `DEPLOYMENT_ENV` | `docker` / `kubernetes` | 部署模式 |

### 資料庫

| 變數 | 預設值 | 說明 |
|------|--------|------|
| `DATABASE_URL` | `postgresql://postgres:postgres@postgres:5432/aileron` | PostgreSQL 連線字串 |

### Redis 與請求追蹤

| 變數 | 預設值 | 說明 |
|------|--------|------|
| `REDIS_URL` | `redis://redis:6379` | Redis 連線 URL |
| `REDIS_HOST` | `redis` | Redis host |
| `REDIS_PORT` | `6379` | Redis port |
| `REDIS_DB` | `0` | Redis DB index |
| `ENABLE_REDIS` | `true` | 啟用 Redis |
| `REDIS_MAX_CONNECTIONS` | `20` | 連線池最大連線數 |
| `REDIS_SOCKET_TIMEOUT` | `30` | Socket 超時（秒） |
| `REDIS_RETRY_ATTEMPTS` | `3` | 重試次數 |
| `REQUEST_TTL_SECONDS` | `3600` | 請求 TTL |
| `CLEANUP_INTERVAL_SECONDS` | `300` | 清理間隔 |

### 內部認證

| 變數 | 預設值 | 說明 |
|------|--------|------|
| `INTERNAL_API_TOKEN` | `dev-internal-token` | 服務間認證 token |

### SSH 設定

| 變數 | 預設值 | 說明 |
|------|--------|------|
| `SSH_PORT` | `22` | SSH 監聽 port |
| `SSH_HOST_KEY_PATH` | `/etc/ssh/ssh_host_rsa_key` | SSH host key 路徑 |

### Git 設定

| 變數 | 預設值 | 說明 |
|------|--------|------|
| `GIT_USER_NAME` | `Developer` | Git 使用者名稱 |
| `GIT_USER_EMAIL` | `developer@workspace.local` | Git 使用者 email |

### Terminal Service

| 變數 | 預設值 | 說明 |
|------|--------|------|
| `TERMINAL_PORT` | `3004` | Terminal WebSocket port |
| `LOG_LEVEL` | `debug` | 日誌等級 |
| `MAX_TABS_PER_WORKSPACE` | `10` | 每個 workspace 最大 terminal 分頁數 |
| `SESSION_TIMEOUT` | `300` | Session 超時（秒） |
| `PTY_BUFFER_SIZE` | `1024` | PTY 緩衝區大小 |

### VS Code Server

| 變數 | 預設值 | 說明 |
|------|--------|------|
| `VSCODE_SERVER_PORT` | `8080` | VS Code Server 監聽 port |

### Claude API

| 變數 | 預設值 | 說明 |
|------|--------|------|
| `ANTHROPIC_BASE_URL` | _(空)_ | Claude API Base URL |
| `ANTHROPIC_AUTH_TOKEN` | _(空)_ | Claude API 認證 Token |

### Keycloak (OAuth2/OIDC)

| 變數 | 預設值 | 說明 |
|------|--------|------|
| `KEYCLOAK_SERVER_URL` | `http://aileron-keycloak-dev:8080` | Keycloak 內部 URL |
| `KEYCLOAK_REALM` | `aileron` | Realm 名稱 |
| `KEYCLOAK_CLIENT_ID` | `aileron-web` | OAuth2 Client ID |
| `KEYCLOAK_JWKS_URL` | _(自動組合)_ | JWKS 端點 URL |
| `KEYCLOAK_JWKS_CACHE_TTL` | `3600` | JWKS 快取時間（秒） |

### Browser Container Discovery

| 變數 | 預設值 | 說明 |
|------|--------|------|
| `BROWSER_CONTAINER_NAME` | `workspace-browser-default-workspace` | Browser 容器名稱 |
| `BROWSER_CDP_URL` | `http://workspace-browser-default-workspace:9223` | Chrome DevTools Protocol URL |
| `BROWSER_WEBRTC_INTERNAL_URL` | `http://workspace-browser-default-workspace:6080` | WebRTC 內部 URL |

### Next.js Container Discovery

| 變數 | 預設值 | 說明 |
|------|--------|------|
| `NEXTJS_CONTAINER_NAME` | `workspace-nextjs-default-workspace` | Next.js 容器名稱 |
| `NEXTJS_INTERNAL_URL` | `http://workspace-nextjs-default-workspace:3003` | Next.js 內部 URL |
| `NEXTJS_API_URL` | `http://workspace-nextjs-default-workspace:3013` | Next.js 管理 API URL |

---

## Frontend

| 變數 | 預設值 | 說明 |
|------|--------|------|
| `NODE_ENV` | `development` / `production` | 執行環境 |
| `DOCKER_ENV` | `true` / `false` | 是否在 Docker 內執行 |
| `VITE_API_BASE_URL` | `http://localhost:3001` | Manager API URL（瀏覽器端） |
| `VITE_FRONTEND_PUBLIC_URL` | _(空)_ | Frontend public URL |
| `VITE_KEYCLOAK_SERVER_URL` | `http://localhost:8080` | Keycloak URL（瀏覽器端） |
| `VITE_KEYCLOAK_REALM` | `aileron` | Keycloak Realm |
| `VITE_KEYCLOAK_CLIENT_ID` | `aileron-frontend` | Keycloak Client ID |
| `VITE_WORKSPACE_K8S_ALLOWED_NAMESPACES` | `workspace-system,default` | 允許的 K8s namespace |
| `VITE_WORKSPACE_K8S_DEFAULT_NAMESPACE` | `workspace-system` | 預設 K8s namespace |

:::warning VITE_ 前綴
所有 `VITE_` 開頭的變數會被打包進前端 JavaScript。不要在此放入機密資訊。
:::

---

## Keycloak

| 變數 | 預設值 | 說明 |
|------|--------|------|
| `KC_HOSTNAME` | `localhost` | Keycloak hostname |
| `KC_HOSTNAME_URL` | `http://localhost:8080` | 對外完整 URL |
| `KC_HOSTNAME_ADMIN_URL` | `http://localhost:8080` | 管理後台 URL |
| `KC_HOSTNAME_STRICT` | `false` | 嚴格 hostname 檢查 |
| `KC_HOSTNAME_STRICT_HTTPS` | `false` | 嚴格 HTTPS 檢查 |
| `KC_HTTP_ENABLED` | `true` | 啟用 HTTP |
| `KC_HTTPS_ENABLED` | `false` | 啟用 HTTPS |
| `KC_PROXY_HEADERS` | `xforwarded` | 信任的 proxy header 類型 |
| `KC_DB` | `postgres` | 資料庫類型 |
| `KC_DB_URL` | `jdbc:postgresql://postgres:5432/keycloak` | 資料庫 URL |
| `KC_DB_USERNAME` | `postgres` | 資料庫使用者 |
| `KC_DB_PASSWORD` | `postgres` | 資料庫密碼 |
| `KC_BOOTSTRAP_ADMIN_USERNAME` | `admin` | 初始管理員帳號 |
| `KC_BOOTSTRAP_ADMIN_PASSWORD` | `admin` | 初始管理員密碼 |
| `KC_HEALTH_ENABLED` | `true` | 啟用健康檢查端點 |
| `KC_METRICS_ENABLED` | `true` | 啟用 metrics 端點 |

---

## Workspace Browser (neko)

| 變數 | 預設值 | 說明 |
|------|--------|------|
| `WORKSPACE_ID` | `default-workspace` | 工作區 ID |
| `NEKO_SERVER_BIND` | `:6080` | neko 監聽位址 |
| `NEKO_DESKTOP_SCREEN` | `1440x900@30` | 桌面解析度與幀率 |
| `NEKO_MEMBER_MULTIUSER_USER_PASSWORD` | `neko` | 一般使用者密碼 |
| `NEKO_MEMBER_MULTIUSER_ADMIN_PASSWORD` | `admin` | 管理員密碼 |
| `NEKO_WEBRTC_ICELITE` | `1` | 啟用 ICE Lite 模式 |
| `NEKO_WEBRTC_UDPMUX` | `52000` | WebRTC UDP mux port |
| `NEKO_WEBRTC_NAT1TO1` | `127.0.0.1` | NAT 1:1 映射 IP |
| `NEKO_SESSION_IMPLICIT_HOSTING` | `true` | 自動分配 host 權限 |

---

## Workspace Next.js

| 變數 | 預設值 | 說明 |
|------|--------|------|
| `WORKSPACE_ID` | `default-workspace` | 工作區 ID |
| `PORT` | `3003` | Next.js dev server port |
| `API_PORT` | `3013` | 管理 API port |
| `WORKSPACE_DIR` | `/workspace` | 工作區目錄 |
| `NODE_ENV` | `development` | 執行環境 |

---

## Workspace Operator (Kubernetes 專用)

| 變數 | 預設值 | 說明 |
|------|--------|------|
| `LOG_LEVEL` | `info` | 日誌等級 |
| `WORKSPACE_CRD_GROUP` | `platform.aileron.io` | CRD API group |
| `WORKSPACE_CRD_VERSION` | `v1alpha1` | CRD API version |
| `WATCH_NAMESPACE` | _(空)_ | 限定 watch 的 namespace，空值表示 watch 所有 |

---

## Kubernetes ConfigMap 注入

在 Kubernetes 模式下，以下環境變數由 platform-config ConfigMap 自動注入：

| ConfigMap Key | 說明 |
|---------------|------|
| `PUBLIC_SCHEME` | public routing scheme |
| `PUBLIC_BASE_DOMAIN` | base domain |
| `PUBLIC_FRONTEND_URL` | Frontend 完整 URL |
| `PUBLIC_WORKSPACE_MANAGER_URL` | Manager 完整 URL |
| `PUBLIC_KEYCLOAK_URL` | Keycloak 完整 URL |
| `PUBLIC_RUNTIME_HOST_PATTERN` | Runtime host pattern |
| `PUBLIC_BROWSER_HOST_PATTERN` | Browser host pattern |
| `PUBLIC_NEXTJS_HOST_PATTERN` | Next.js host pattern |
| `RUNTIME_PROVISIONER` | provisioner 類型 |
| `RUNTIME_K8S_NAMESPACE` | 預設 K8s namespace |
| `RUNTIME_K8S_ALLOWED_NAMESPACES` | 允許的 namespace |
| `RUNTIME_K8S_SERVICE_TYPE` | Service type |
| `RUNTIME_K8S_IMAGE` | Runtime 映像 |
| `RUNTIME_K8S_BROWSER_IMAGE` | Browser 映像 |
| `RUNTIME_K8S_NEXTJS_IMAGE` | Next.js 映像 |
| `CILIUM_ENABLED` | 是否啟用 Cilium |
| `FIREWALL_DEFAULTS_CONFIGMAP_NAME` | Firewall defaults ConfigMap 名稱 |
