---
sidebar_position: 5
title: 生產環境部署
---

# 生產環境部署指南

本指南涵蓋將 Aileron 部署至生產環境時需要考量的安全性、可靠性與效能面向。

:::warning
此平台目前處於 alpha 階段（v0.1.0-alpha），以下為建議方向。實際部署請根據組織的安全與合規要求調整。
:::

## 部署前檢查清單

### 必要項目

- [ ] 所有預設密碼已修改（PostgreSQL、Redis、Keycloak、JWT Secret）
- [ ] TLS 憑證已配置（Ingress 或反向代理）
- [ ] DNS 記錄已設定（至少包含固定服務 host，workspace host 需由 wildcard 或自動化記錄覆蓋）
- [ ] Keycloak Redirect URI 已更新為正式網域
- [ ] `VITE_` 開頭的環境變數不含機密資訊
- [ ] Docker Socket 掛載已移除（使用 Kubernetes 模式）
- [ ] 資料庫連線使用加密（`sslmode=require`）

### 建議項目

- [ ] 容器映像使用固定版本 tag（非 `latest` 或 `dev`）
- [ ] Resource limits/requests 已設定
- [ ] 持久化儲存已配置（PVC + 適當的 StorageClass）
- [ ] 若 Team Wiki Knowledge Base 會啟用 Git LFS，`workspace-manager` image 已安裝 `git-lfs`
- [ ] 監控與告警已就緒
- [ ] 備份策略已建立
- [ ] Log 收集已配置

## 安全加固

### 密碼與 Secret 管理

**絕對不要使用預設密碼。** 以下是需要修改的項目：

```yaml
# values.yaml - 生產環境範例
postgres:
  auth:
    password: "<strong-random-password>"

keycloak:
  auth:
    adminUser: admin
    adminPassword: "<strong-random-password>"

workspaceManager:
  env:
    SECRET_KEY: "<random-256-bit-key>"
    ACCESS_TOKEN_EXPIRE_MINUTES: "60"     # 縮短 token 有效期
    REFRESH_TOKEN_EXPIRE_DAYS: "1"
```

建議使用 Kubernetes Secret 管理敏感資訊，而非直接寫在 values.yaml：

```bash
# 建立 Secret
kubectl create secret generic aileron-secrets \
  --from-literal=DATABASE_PASSWORD='<password>' \
  --from-literal=SECRET_KEY='<key>' \
  --from-literal=KEYCLOAK_ADMIN_PASSWORD='<password>' \
  -n aileron
```

:::tip 外部 Secret 管理
可搭配 [External Secrets Operator](https://external-secrets.io/) 或 [Sealed Secrets](https://sealed-secrets.netlify.app/) 從 AWS Secrets Manager、HashiCorp Vault 等來源同步。
:::

### TLS / HTTPS

所有對外服務必須使用 HTTPS：

```yaml
publicRouting:
  scheme: https

ingress:
  annotations:
    cert-manager.io/cluster-issuer: "letsencrypt-prod"
    nginx.ingress.kubernetes.io/ssl-redirect: "true"
  tls:
    - secretName: aileron-tls
      hosts:
        - example.com
        - "*.example.com"
```

Keycloak 也需要配合更新：

```yaml
keycloak:
  env:
    KC_HOSTNAME_STRICT: "true"
    KC_HOSTNAME_STRICT_HTTPS: "true"
    KC_PROXY_HEADERS: xforwarded
```

### 容器映像安全

- 使用私有 registry，設定 `global.imagePullSecrets`
- 映像 tag 使用 commit SHA 或語意化版本，避免 `latest`
- 定期掃描映像漏洞（Trivy、Snyk 等）

```yaml
global:
  imagePullSecrets:
    - name: registry-credentials

frontend:
  image:
    repository: your-registry.com/workspace-ui
    tag: v0.1.0
    pullPolicy: IfNotPresent
```

### 網路安全

- 啟用 Cilium 進行 workspace 間的網路隔離
- 限制 Keycloak Admin Console 的存取來源
- 工作區的 domain allowlist 應盡量精確

```yaml
cilium:
  enabled: true

firewall:
  defaults:
    workspace:
      allowedDomains:
        - github.com
        - api.github.com
        - registry.npmjs.org
        - pypi.org
        - api.anthropic.com
    browser:
      allowedDomains:
        - github.com
```

## 資源規劃

### 目前叢集實際設定（2026-04-13，`aileron` namespace）

以下是目前叢集上實際查到的 `resources.requests` / `resources.limits`：

| Workload | Container | Requests | Limits |
|----------|-----------|----------|--------|
| `aileron-aileron-workspace-manager` | `workspace-manager` | CPU `500m` / Memory `1Gi` | CPU `2` / Memory `2Gi` |
| `aileron-aileron-frontend` | `frontend` | 未設定 | 未設定 |
| `aileron-aileron-keycloak` | `keycloak` | 未設定 | 未設定 |
| `aileron-aileron-workspace-operator` | `workspace-operator` | 未設定 | 未設定 |
| `aileron-aileron-coturn` | `coturn` | 未設定 | 未設定 |
| `aileron-aileron-postgres` | `postgres` | 未設定 | 未設定 |
| `aileron-aileron-redis` | `redis` | 未設定 | 未設定 |
| `workspace-runtime-default-workspace` | `runtime` | 未設定 | 未設定 |
| `workspace-browser-default-workspace` | `browser` | 未設定 | 未設定 |
| `workspace-nextjs-default-workspace` | `nextjs` | 未設定 | 未設定 |

:::note
也就是說，目前 live cluster 只有 `workspace-manager` 已明確設定 requests / limits，其餘平台服務與預設 workspace deployment 都還沒有把 container resources 寫進 Pod spec。
:::

### 平台服務建議配置

| 服務 | CPU Request | CPU Limit | Memory Request | Memory Limit |
|------|-------------|-----------|----------------|--------------|
| Frontend | 100m | 500m | 128Mi | 256Mi |
| Workspace Manager | 250m | 1000m | 256Mi | 512Mi |
| Workspace Operator | 100m | 500m | 128Mi | 256Mi |
| Keycloak | 500m | 1000m | 512Mi | 1Gi |
| PostgreSQL | 250m | 1000m | 256Mi | 1Gi |
| Redis | 100m | 500m | 128Mi | 256Mi |
| CoTURN | 100m | 500m | 64Mi | 128Mi |

### Workspace Pod 建議配置

| 元件 | CPU Request | CPU Limit | Memory Request | Memory Limit |
|------|-------------|-----------|----------------|--------------|
| Runtime | 500m | 2000m | 512Mi | 2Gi |
| Browser (neko) | 1000m | 2000m | 1Gi | 2Gi |
| Next.js | 250m | 1000m | 256Mi | 512Mi |

### Chart 目前支援的資源設定入口

Helm chart 已支援下列 values：

```yaml
frontend:
  resources: {}

workspaceManager:
  resources:
    requests:
      cpu: 500m
      memory: 1Gi
    limits:
      cpu: 2000m
      memory: 2Gi

workspaceOperator:
  resources: {}

postgres:
  resources: {}

redis:
  resources: {}

keycloak:
  resources: {}

coturn:
  resources: {}

kubernetes:
  workspaceDefaults:
    runtime:
      resources:
        requests:
          cpu: 500m
          memory: 2Gi
        limits:
          cpu: 2000m
          memory: 4Gi
    browser:
      resources:
        requests:
          cpu: 500m
          memory: 1Gi
        limits:
          cpu: 2000m
          memory: 2Gi
    nextjs:
      resources:
        requests:
          cpu: 500m
          memory: 1Gi
        limits:
          cpu: 2000m
          memory: 2Gi
```

:::caution Chart 預設值與 live cluster 的差異
雖然 `kubernetes.workspaceDefaults.*.resources` 已在 chart 中有預設值，而且目前 `aileron-aileron-platform-config` ConfigMap 也能查到對應 JSON，但現有 `workspace-runtime-default-workspace`、`workspace-browser-default-workspace`、`workspace-nextjs-default-workspace` 這三個 Deployment 目前仍是 `resources: {}`。這表示現有 workspace 是否真的套用到預設資源，仍需要直接以實際 Deployment / Pod spec 為準來驗證。
:::

```yaml
# 在 values.yaml 設定 resource limits
workspaceManager:
  resources:
    requests:
      cpu: 250m
      memory: 256Mi
    limits:
      cpu: 1000m
      memory: 512Mi
```

### 如何查目前 K8s 實際資源設定

查看平台服務與 StatefulSet：

```bash
kubectl get deploy,statefulset -n aileron \
  -o jsonpath='{range .items[*]}{.kind}{"\t"}{.metadata.name}{"\t"}{range .spec.template.spec.containers[*]}{.name}{": requests="}{.resources.requests.cpu}{"/"}{.resources.requests.memory}{", limits="}{.resources.limits.cpu}{"/"}{.resources.limits.memory}{"; "}{end}{"\n"}{end}'
```

查看單一 workspace 的 deployment：

```bash
kubectl get deploy workspace-runtime-default-workspace \
  workspace-browser-default-workspace \
  workspace-nextjs-default-workspace \
  -n aileron -o yaml
```

查看 workspace 預設資源是否已寫入 platform config：

```bash
kubectl get configmap aileron-aileron-platform-config -n aileron \
  -o jsonpath='{.data.RUNTIME_K8S_RUNTIME_RESOURCES}{"\n"}{.data.RUNTIME_K8S_BROWSER_RESOURCES}{"\n"}{.data.RUNTIME_K8S_NEXTJS_RESOURCES}{"\n"}'
```

### 儲存規劃

| 用途 | 建議大小 | Access Mode | 說明 |
|------|----------|-------------|------|
| PostgreSQL | 20-50Gi | ReadWriteOnce | 視工作區數量與歷史資料 |
| Redis | 5-10Gi | ReadWriteOnce | 任務佇列與快取 |
| Workspace 資料 | 10-50Gi/workspace | ReadWriteOnce | 程式碼、Claude 資料 |

## 外部服務整合

生產環境建議將以下服務改為外部託管，不使用 Helm 內建版本：

### 外部 PostgreSQL

```yaml
postgres:
  enabled: false  # 停用內建 PostgreSQL

workspaceManager:
  env:
    DATABASE_URL: "postgresql://user:pass@rds-instance.region.rds.amazonaws.com:5432/aileron?sslmode=require"
```

### 外部 Redis

```yaml
redis:
  enabled: false  # 停用內建 Redis

workspaceManager:
  env:
    REDIS_URL: "rediss://user:pass@redis-cluster.region.cache.amazonaws.com:6379"
    CELERY_BROKER_URL: "rediss://user:pass@redis-cluster.region.cache.amazonaws.com:6379/0"
    CELERY_RESULT_BACKEND: "rediss://user:pass@redis-cluster.region.cache.amazonaws.com:6379/1"
```

### 外部 Keycloak

若已有企業級 Keycloak 或其他 OIDC provider：

```yaml
keycloak:
  enabled: false  # 停用內建 Keycloak

workspaceManager:
  env:
    KEYCLOAK_SERVER_URL: "https://sso.company.com"
    KEYCLOAK_REALM: "aileron"
    KEYCLOAK_CLIENT_ID: "your-client-id"
```

## 備份策略

### 資料庫備份

```bash
# PostgreSQL 備份
kubectl exec -n aileron statefulset/aileron-postgres -- \
  pg_dump -U postgres aileron > backup-$(date +%Y%m%d).sql

# 定期備份（搭配 CronJob）
```

### Keycloak Realm 備份

```bash
# 匯出 Realm 設定
ADMIN_TOKEN=$(curl -s -X POST "https://keycloak.example.com/realms/master/protocol/openid-connect/token" \
  -d "client_id=admin-cli" \
  -d "username=admin" \
  -d "password=$ADMIN_PASSWORD" \
  -d "grant_type=password" | jq -r '.access_token')

curl -X POST "https://keycloak.example.com/admin/realms/aileron/partial-export?exportClients=true&exportGroupsAndRoles=true" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -o realm-backup-$(date +%Y%m%d).json
```

### Workspace 資料備份

- PVC 使用 VolumeSnapshot（若 CSI driver 支援）
- 或使用 Velero 進行叢集級備份

## 監控

### 健康檢查端點

| 服務 | 端點 |
|------|------|
| Workspace Manager | `GET /health` |
| Workspace Runtime | `GET /health` |
| Keycloak | `GET /health/ready` |
| PostgreSQL | `pg_isready` |
| Redis | `redis-cli ping` |

### Metrics

- **Keycloak**: `GET /metrics`（Prometheus 格式，需 `KC_METRICS_ENABLED=true`）
- **Celery Flower**: `http://<manager>:5555/api/tasks`（Celery 任務監控）
- **Workspace Manager**: `/docs` 端點可用於 API 可用性監控

### 建議告警規則

| 條件 | 嚴重度 | 說明 |
|------|--------|------|
| Pod CrashLoopBackOff | Critical | 服務啟動失敗 |
| Keycloak 不健康 | Critical | 認證服務中斷，影響所有登入 |
| PostgreSQL 不健康 | Critical | 資料庫中斷 |
| Redis 不健康 | High | 任務佇列中斷 |
| PVC 使用率 > 80% | Warning | 儲存空間即將用盡 |
| Celery task 失敗率上升 | Warning | 自動化任務異常 |

## 升級流程

### Helm Chart 升級

```bash
# 1. 檢視變更
helm diff upgrade aileron helm/aileron \
  --namespace aileron \
  -f production-values.yaml

# 2. 備份
kubectl exec -n aileron statefulset/aileron-postgres -- \
  pg_dump -U postgres aileron > pre-upgrade-backup.sql

# 3. 執行升級
helm upgrade aileron helm/aileron \
  --namespace aileron \
  -f production-values.yaml

# 4. 驗證
kubectl get pods -n aileron
kubectl logs -n aileron deployment/aileron-workspace-manager --tail=50
```

### 資料庫 Migration

```bash
# 執行 migration（若有提供）
./scripts/db/run-migrations.sh
```

:::caution
升級前務必備份資料庫。CRD 更新需特別注意，因為 `helm upgrade` 不會自動更新 CRD。若 CRD schema 有變更：

```bash
kubectl apply -f helm/aileron/crds/
```
:::
