---
sidebar_position: 4
title: Keycloak 認證配置
---

# Keycloak 認證配置

Aileron 使用 [Keycloak](https://www.keycloak.org/) 提供 OAuth2/OIDC 認證服務，支援：

- 單一登入（SSO）
- OAuth2 Authorization Code Flow with PKCE
- JWT Token 驗證（RS256）
- 使用者角色與權限管理

## Realm 概覽

平台使用名為 `aileron` 的 Realm，首次啟動時自動從 `keycloak-realm/aileron-realm.json` 匯入。

### 預設 Client

| Client ID | 類型 | 說明 |
|-----------|------|------|
| `aileron-frontend` | Public Client | 前端 SPA 使用，無需 client secret |

Public Client 設定：
- **Redirect URIs**: `http://localhost:8082/*`、`http://localhost:8082/callback`
- **Web Origins**: `http://localhost:8082`（CORS 允許來源）
- **認證流程**: Authorization Code Flow with PKCE

### 預設使用者

| 帳號 | 密碼 | 角色 |
|------|------|------|
| `admin` | `admin123` | `default-roles-aileron` |

### 管理後台

| 環境 | URL | 帳號/密碼 |
|------|-----|-----------|
| Docker | `http://localhost:8080/admin` | `admin` / `admin` |
| Kubernetes | `https://keycloak.<baseDomain>/admin` | 依 Helm values 設定 |

## Docker 模式配置

Docker 模式下，Keycloak 以 `start-dev` 模式執行並自動匯入 Realm：

```yaml
# docker-compose.yml 中的關鍵設定
keycloak:
  command: start-dev --import-realm
  volumes:
    - ./keycloak-realm:/opt/keycloak/data/import
```

### 服務間認證流程

```
瀏覽器 → Frontend → Keycloak (OAuth2 登入)
                   ↓
               取得 JWT Token
                   ↓
Frontend → Manager API (Bearer token)
              ↓
         驗證 JWT 簽章 (JWKS)
```

Manager 和 Runtime 都會透過 Keycloak 的 JWKS 端點驗證 JWT：

```
http://aileron-keycloak-dev:8080/realms/aileron/protocol/openid-connect/certs
```

### Network Alias

Docker 模式下，Keycloak 設定了 `localhost` 和 `keycloak` 兩個 network alias。這是因為 JWT token 的 issuer URL 包含 `localhost`，容器內驗證 token 時需要能用相同的 hostname 訪問 Keycloak。

## Kubernetes 模式配置

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
    adminPassword: admin  # 生產環境必須修改
  env:
    KC_HOSTNAME_STRICT: "false"
    KC_HOSTNAME_STRICT_HTTPS: "false"
    KC_HTTP_ENABLED: "true"
    KC_PROXY_HEADERS: xforwarded
    KC_HEALTH_ENABLED: "true"
    KC_METRICS_ENABLED: "true"
```

### Public URL 配置

在 Kubernetes 模式下，Keycloak 的 public URL 由 `publicRouting` 決定：

```yaml
publicRouting:
  scheme: https
  baseDomain: example.com
  keycloakHost: "keycloak.{baseDomain}"
```

Helm template 會自動生成 `PUBLIC_KEYCLOAK_URL` 並注入到 platform-config ConfigMap，Manager 和 Frontend 據此設定 OIDC 端點。

### Realm 匯入

Kubernetes 模式下，Realm JSON 透過 ConfigMap 掛載：

```
helm/aileron/files/realm.json
  → keycloak-realm-configmap
  → 掛載到 Keycloak Pod
```

## 自訂 Realm 設定

### 新增 Client

若需要為其他服務（如 mobile app、CLI 工具）新增 OAuth2 Client：

1. 進入 Keycloak Admin Console
2. 選擇 `aileron` Realm
3. **Clients** → **Create client**
4. 設定：
   - **Client type**: OpenID Connect
   - **Client ID**: 自訂名稱
   - **Client authentication**: 根據需求（SPA 用 Off，後端用 On）
5. 設定 **Valid redirect URIs** 與 **Web origins**

### 新增 Redirect URI

部署到新的網域時，需要更新 Client 的 Redirect URI：

**Docker 模式**：直接在 Keycloak Admin Console 修改，或編輯 `keycloak-realm/aileron-realm.json` 後重新匯入。

**Kubernetes 模式**：修改 `helm/aileron/files/realm.json`，重新部署：

```bash
helm upgrade aileron helm/aileron \
  --namespace aileron
```

### 新增使用者

1. 進入 Keycloak Admin Console
2. 選擇 `aileron` Realm
3. **Users** → **Add user**
4. 設定 username、email
5. **Credentials** 分頁設定密碼

## 生產環境建議

### 安全性

- **修改所有預設密碼**：admin 帳號、bootstrap 密碼、資料庫密碼
- **啟用 HTTPS**：設定 `KC_HTTPS_ENABLED=true`，或透過 Ingress 終止 TLS
- **啟用 strict hostname**：設定 `KC_HOSTNAME_STRICT=true`
- **關閉 HTTP**：設定 `KC_HTTP_ENABLED=false`（若已有 TLS）

### 高可用性

- 使用外部 PostgreSQL（非 Helm 內建）
- 配置多副本 Keycloak（需要 distributed cache，如 Infinispan）
- 設定 session affinity 或 sticky session

### 備份

- 定期匯出 Realm 設定：
  ```bash
  # 透過 Admin API 匯出
  curl -X POST "https://keycloak.example.com/admin/realms/aileron/partial-export?exportClients=true&exportGroupsAndRoles=true" \
    -H "Authorization: Bearer $ADMIN_TOKEN" \
    -o realm-backup.json
  ```
- 備份 Keycloak 資料庫

### 監控

Keycloak 內建 metrics 端點（需 `KC_METRICS_ENABLED=true`）：

```
GET /metrics
GET /health
GET /health/ready
GET /health/live
```
