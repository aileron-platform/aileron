---
title: 生產環境部署
---

# 生產環境部署指南

本指南涵蓋將 Aileron 部署至生產環境時需要考量的安全性、可靠性與效能面向。

:::warning
此平台尚未正式 release，以下為建議方向。實際部署請根據組織的安全與合規要求調整。
:::

## 平台資源統計的原子部署

Manager schema、Runtime telemetry、Workspace CRD／Operator 與 Frontend 必須同批部署。先套用 CRD，再部署 Operator、Manager、Runtime 與 Frontend；Redis 不可用時 Manager 會回 PostgreSQL，但 hourly aggregate、daily capacity snapshot 與 retention prune 的 scheduler 仍須正常執行。

## 部署前檢查清單

### 必要項目

- [ ] 所有 credential 與密鑰已由受控 Secret 提供（PostgreSQL、OIDC client、Runtime assertion signer、Browser credential keyring、Runtime database credential key）
- [ ] TLS 憑證已配置（Ingress 或反向代理）
- [ ] `platformPublicOrigin` 的單一 DNS 記錄已指向 Ingress／load balancer，且 TLS 憑證涵蓋該 host
- [ ] 若使用 split DNS，內外 resolver 已分別驗證 Platform Public Origin 會指向預期端點
- [ ] OIDC provider 的 redirect URI、audience 與 issuer 已更新為正式網域與正式 client
- [ ] `VITE_` 開頭的環境變數不含機密資訊
- [ ] 未掛載 Docker Socket（使用 Kubernetes 模式）
- [ ] 已接受目前 Chart 的限制：內建 PostgreSQL 連線尚未啟用 TLS，且不支援 external database；若組織要求資料庫傳輸加密，正式部署須先補齊該契約

### 建議項目

- [ ] 容器映像使用不可變 digest，且 manifest 架構符合目標節點
- [ ] Resource limits/requests 已設定
- [ ] 持久化儲存已配置（PVC + 適當的 StorageClass）
- [ ] 若 Knowledge Base 會啟用 Git LFS，`workspace-manager` image 已安裝 `git-lfs`
- [ ] 監控與告警已就緒
- [ ] 備份策略已建立
- [ ] Log 收集已配置

## 安全加固

### Credential 與 Secret 管理

OIDC provider 負責登入 credential；Aileron 只保存驗證所需的非秘密設定與 provider client
參數。以下只示範部署 override，不包含 provider 密碼或 provider admin API credential：

```yaml
# 僅用於部署主機的 values-production.yaml，不可提交至版本庫
# 這只是 deployment override，不是完整平台 overlay
security:
  requireStrongSecrets: true

platformSecrets:
  existingSecretName: aileron-platform-secrets
  databaseUrlKey: database-url
  runtimeDatabaseCredentialKey: runtime-database-credential-key
  postgresUsernameKey: postgres-username
  postgresPasswordKey: postgres-password

oidc:
  issuerUrl: https://login.example.com/realms/aileron
  clientId: aileron-manager
  clientSecretName: aileron-oidc-client
  clientSecretKey: client-secret

bootstrap:
  admin:
    enabled: true
    subject: "<provider-subject>"
    username: admin
    email: admin@aileron.com
```

`bootstrap.admin.subject` 只建立 Manager 本地 admin snapshot；provider credential、群組與
登入政策由外部 OIDC provider 管理。

正式部署的 OIDC 與本地 admin snapshot 契約請見[外部 OIDC 安裝](./oidc.md)。
`bootstrap.admin.enabled=true` 時，`install` 與 `upgrade` 都必須等候 snapshot bootstrap Job
成功；Job 不建立 provider 帳號、不處理密碼，也不把 provider credential 寫入 Pod arguments
或環境變數。

Provider token 有效期由 OIDC provider policy 管理；只有 Manager 在 callback 期間驗證
issuer、audience、簽章與 `OIDC_MAX_TOKEN_LIFETIME_SECONDS`。正式環境若
要調整 token 或 SSO session policy，應在 provider 的受管設定中調整並驗證 PKCE 流程，不要
設定不存在的 Aileron JWT lifetime override。

Chart 只掛載上述 existing Secret references，不建立或保存 Secret value。這段檔案只示範
Secret reference 與 bootstrap override，不是可單獨安裝的完整 values；正式部署還必須由平台 overlay 提供
所有 Aileron component 的不可變 image digest、各用途 StorageClass、正式網域、
Registry 認證方式、Ingress、TURN 與網路隔離設定。部署檔應以權限 `0600` 保存在
部署主機，並在安裝後安全刪除。

以下沿用 [Kubernetes 快速安裝](./kubernetes.md) 的雙 values 流程；所有叢集都必須把
`PLATFORM_VALUES` 指向自己產生並完成驗證的 platform overlay：

```bash
chmod 0600 values-production.yaml
export PLATFORM_VALUES=/run/aileron/platform-values.yaml

helm upgrade --install aileron ./helm/aileron \
  --namespace workspace-system \
  --create-namespace \
  --values "${PLATFORM_VALUES}" \
  --values values-production.yaml \
  --atomic \
  --wait \
  --wait-for-jobs \
  --timeout 15m
```

:::tip 外部 Secret 管理
若要從 AWS Secrets Manager、Google Secret Manager、Azure Key Vault 或 HashiCorp Vault 同步機密，應由 External Secrets 或部署流程建立 Chart 引用的 existing Secret。values 只保存 Secret name/key，不保存 Secret value。
:::

### TLS / HTTPS

所有公開 HTTP 與 WebSocket 服務必須使用 HTTPS。TURN 不屬於 HTTP；它依 Reachability Profile
明確使用 `turn:` TCP/UDP 或 `turns:` TLS，並只開放宣告的 listener 與 relay range：

```yaml
platformPublicOrigin: https://aileron.apps.example.com

ingress:
  enabled: true
  className: "<ingress-class>"
  useDefaultClass: false
  tlsMode: kubernetesSecret
  tlsSecretName: aileron-platform-tls
  annotations: {}
```

TLS Secret 必須已存在於共同的 Runtime namespace，且憑證涵蓋 Platform Public Origin 的
單一 host。annotations 應由各平台 deployment profile 提供；不要在產品 values
假設 NGINX、AWS、GCP 或 Azure 的實作。
若憑證由雲端 Ingress controller 管理，改用 `tlsMode: controllerManaged` 並保持
`tlsSecretName: ""`；其餘憑證引用放在 provider annotations 或 IngressClass policy。

使用外部 OIDC provider 時，請確認 provider 的正式 issuer 與 client：

```yaml
oidc:
  issuerUrl: https://login.example.com/realms/aileron
  clientId: aileron-frontend
```

### 容器映像安全

- 使用私有 Registry；外部 Registry 設定 `global.imagePullSecrets`，雲端原生 Registry
  則可使用 kubelet／node managed identity
- 正式部署只使用 immutable digest，不使用任何 tag
- 定期掃描映像漏洞（Trivy、Snyk 等）

使用 built-in TURN 時，Coturn 位於獨立的 `coturn.namespace`。同一個
`global.imagePullSecrets` 名稱必須同時存在於 Runtime 與 Coturn namespace；完整流程請見
[Kubernetes 快速安裝 — 準備 namespace 與 Secrets](./kubernetes.md#1-準備-namespace-與-secrets)。

```yaml
global:
  imagePullSecrets:
    - name: registry-credentials

frontend:
  image:
    repository: your-registry.com/workspace-ui
    digest: sha256:<64-hex-digest>
    tag: ""
    pullPolicy: IfNotPresent
```

若 EKS／GKE／AKS 已完成 ECR／Artifact Registry／ACR 的 node pull 權限，請改用
`global.imagePullSecrets: []`。Pod workload identity 與 kubelet image pull identity
不是同一契約，必須分別驗證。

### 網路安全

- 啟用 Cilium 進行 workspace 間的網路隔離
- 限制外部 OIDC provider administration surface 的存取來源
- 工作區的 domain allowlist 應盡量精確

```yaml
cilium:
  enabled: true

firewall:
  seed:
    workspace:
      egressMode: allowlist
      allowedDomains:
        - github.com
        - api.github.com
        - registry.npmjs.org
        - pypi.org
        - api.anthropic.com
        - chatgpt.com
        - api.openai.com
        - auth.openai.com
    browser:
      egressMode: allowlist
      allowedDomains:
        - github.com
```

`firewall.seed` 只在建立新 Workspace 時寫入資料庫。之後使用者可在 UI 刪除 seed domain；
Helm upgrade 與服務重啟都不會回填。完整契約請見
[Kubernetes Workspace 防火牆](./kubernetes-firewall.md)。

### 正式環境 TURN

每個 Kubernetes、OpenShift 與企業私有部署都要提供明確 TURN Reachability Profile。內建
Coturn 的 DNS 只解析至 Coturn 節點，節點防火牆放行 listener 與 relay UDP range；外部 TURN
則由 profile 描述 Browser Pod 與公開 endpoint 的不同 destination。

正式支援條件包含 Browser Pod sidecar 的 backend relay evidence，以及每個 required external
vantage 經 Connectivity Evidence Gateway 提交的 frontend relay evidence。所有 evidence 都必須
符合目前 profile/credential revision 且未超過 TTL；external vantage credential issuer 必須是
`turnRest`。Service 健康、port open、STUN binding 或
偶爾 direct ICE 成功都不構成 TURN conformance。設定與驗收流程請見
[Kubernetes 網路與 TURN](./kubernetes-networking.md)。

## 資源規劃

### 目前資源契約

Helm chart 會部署固定的 control plane，Workspace Operator 則根據每個 `Workspace` CR 動態建立 Runtime、Browser 與 Canvas Deployment。平台不會自動建立 Workspace；使用者須透過 UI 或 API 明確建立所需的 Workspace。

### 平台服務建議配置

| 服務 | CPU Request | CPU Limit | Memory Request | Memory Limit |
|------|-------------|-----------|----------------|--------------|
| Frontend | 100m | 500m | 128Mi | 256Mi |
| Workspace Manager | 250m | 1000m | 256Mi | 512Mi |
| Workspace Operator | 100m | 500m | 128Mi | 256Mi |
| Bundled OIDC adapter（選配） | 500m | 1000m | 512Mi | 1Gi |
| PostgreSQL | 250m | 1000m | 256Mi | 1Gi |
| Redis | 100m | 500m | 128Mi | 256Mi |

### Workspace Pod 建議配置

| 元件 | CPU Request | CPU Limit | Memory Request | Memory Limit |
|------|-------------|-----------|----------------|--------------|
| Runtime | 500m | 2000m | 1Gi | 3Gi |
| Browser (neko) | 500m | 2000m | 1Gi | 2Gi |
| Canvas | 100m | 1000m | 1Gi | 2Gi |

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

kubernetes:
  workspaceDefaults:
    runtime:
      resources:
        requests:
          cpu: 500m
          memory: 1Gi
        limits:
          cpu: 2000m
          memory: 3Gi
    browser:
      resources:
        requests:
          cpu: 500m
          memory: 1Gi
        limits:
          cpu: 2000m
          memory: 2Gi
    canvas:
      resources:
        requests:
          cpu: 100m
          memory: 1Gi
        limits:
          cpu: 1000m
          memory: 2Gi
```

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
kubectl get deploy,statefulset -n workspace-system \
  -o jsonpath='{range .items[*]}{.kind}{"\t"}{.metadata.name}{"\t"}{range .spec.template.spec.containers[*]}{.name}{": requests="}{.resources.requests.cpu}{"/"}{.resources.requests.memory}{", limits="}{.resources.limits.cpu}{"/"}{.resources.limits.memory}{"; "}{end}{"\n"}{end}'
```

查看單一 Workspace 的動態 Deployment：

```bash
kubectl get deploy -n workspace-system \
  -l 'aileron.io/workspace-id=<workspace-id>' \
  -o yaml
```

查看 workspace 預設資源是否已寫入 platform config：

```bash
kubectl get configmap aileron-aileron-platform-config -n workspace-system \
  -o jsonpath='{.data.RUNTIME_K8S_RUNTIME_RESOURCES}{"\n"}{.data.RUNTIME_K8S_BROWSER_RESOURCES}{"\n"}{.data.RUNTIME_K8S_CANVAS_RESOURCES}{"\n"}'
```

### 儲存規劃

| 用途 | 建議大小 | Access Mode | 說明 |
|------|----------|-------------|------|
| PostgreSQL | 20-50Gi | ReadWriteOnce | 視工作區數量與歷史資料 |
| Redis | 5-10Gi | ReadWriteOnce | 任務佇列與快取 |
| Workspace working tree | 10-50Gi/workspace | ReadWriteMany | Repository 與工作檔；需支援跨節點重建 |
| Runtime HOME | 2-10Gi/workspace | 預設 ReadWriteOnce；選用 ReadWriteMany | CLI 登入、agent 設定、XDG 與 bootstrap 狀態 |
| Knowledge Base | 20-100Gi | ReadWriteMany | Manager 寫入、多個 Runtime 以 `subPath` 唯讀掛載 |
| Manager state | 20-50Gi | ReadWriteOnce | Marketplace registry 與其他 Manager 持久狀態 |

## 外部服務邊界

當前 chart 直接管理 PostgreSQL 與 Redis，但不部署或管理 OIDC provider。Manager 的 OIDC
issuer、audience 與 timeout 只由正式 `oidc.*` values 設定。

外部 OIDC、企業 SSO 與 LDAP-backed provider 目前均由 `oidc.issuerUrl` 支援；provider 的
credential、LDAP 設定與備份由 provider 運維流程負責，不以未受管的 env override 取代正式
OIDC values。

## 備份策略

### 資料庫備份

```bash
# PostgreSQL 備份
kubectl exec -n workspace-system statefulset/aileron-aileron-postgres -- \
  pg_dump -U postgres aileron > backup-$(date +%Y%m%d).sql

# 定期備份（搭配 CronJob）
```

### OIDC provider 備份

依 provider 的正式備份與 restore contract 保存 issuer 設定、client registration、signing
key rotation metadata 與 LDAP federation（若有）。Aileron 不提供 provider-specific admin
API，也不保存 provider database 或 realm backup。

### Workspace 資料備份

- PVC 使用 VolumeSnapshot（若 CSI driver 支援）
- 或使用 Velero 進行叢集級備份

## 監控

### 健康檢查端點

| 服務 | 端點 |
|------|------|
| Workspace Manager | `GET /health` |
| Workspace Runtime | `GET /health` |
| OIDC provider | 外部 provider 依其 readiness contract |
| PostgreSQL | `pg_isready` |
| Redis | `redis-cli ping` |

### Metrics

- **Celery Flower**：只在部署內部網路提供 Celery 任務監控
- **Workspace Manager**: 使用 `GET /health` 監控 HTTP service 可回應

Manager 的 OIDC readiness 驗證 Discovery／JWKS 可達性。外部 provider 的 health 與
metrics 依 provider contract。

### 建議告警規則

| 條件 | 嚴重度 | 說明 |
|------|--------|------|
| Pod CrashLoopBackOff | Critical | 服務啟動失敗 |
| OIDC provider 不健康 | Critical | 認證服務中斷，影響所有登入 |
| PostgreSQL 不健康 | Critical | 資料庫中斷 |
| Redis 不健康 | High | 任務佇列中斷 |
| PVC 使用率 > 80% | Warning | 儲存空間即將用盡 |
| Celery task 失敗率上升 | Warning | Workspace Runtime durable job 或知識庫維護異常 |

## 升級流程

### 權限契約一致部署

平台角色與資源角色契約把 Manager、Runtime、Frontend、Helm schema、資料庫與 OIDC issuer
設定視為一個不可拆分的部署單位，禁止讓各服務運行彼此不相容的契約。

1. 對資料庫與 OIDC provider 設定建立同一時間點的完整快照。
2. 停止外部流量並進入維護狀態。
3. 以全新資料庫與目前 OIDC issuer 套用 schema、`admin/member` 平台角色及 `reader/manager/owner` 資源角色契約。
4. 同批部署 Manager、Runtime、Frontend 與 Helm schema。
5. 等 DB、OIDC provider、Manager、Runtime readiness 通過，再建立 smoke 帳號、ownership 與 shares。
6. 完成平台角色與資源角色的 HTTP／UI 正負向 smoke 後才恢復流量。

任一 readiness 或 smoke 失敗時，維持流量關閉並還原同一組 DB＋OIDC provider 設定快照；禁止只處理單一服務。

### Helm Chart 升級

```bash
# 1. 檢視變更
helm diff upgrade aileron helm/aileron \
  --namespace workspace-system \
  -f "${PLATFORM_VALUES}" \
  -f values-production.yaml

# 2. 備份
kubectl exec -n workspace-system statefulset/aileron-aileron-postgres -- \
  pg_dump -U postgres aileron > pre-upgrade-backup.sql

# 3. 執行升級
kubectl apply -f helm/aileron/crds/
helm upgrade aileron helm/aileron \
  --namespace workspace-system \
  -f "${PLATFORM_VALUES}" \
  -f values-production.yaml \
  --atomic --wait --wait-for-jobs

# 4. 驗證
kubectl get pods -n workspace-system
kubectl logs -n workspace-system \
  --selector='app.kubernetes.io/instance=aileron,app.kubernetes.io/component=workspace-manager' \
  --all-containers \
  --tail=50
```

只要 `bootstrap.admin.enabled=true`，`helm upgrade` 就會執行本地 admin snapshot bootstrap，
將 `bootstrap.admin.subject` 對應到 OIDC issuer + subject；不會建立、重設或覆寫 provider
密碼。provider credential rotation 應依 provider 自身流程完成，再以 `--wait-for-jobs` 驗證
OIDC 登入與 `/api/v1/oauth2/session`。

:::caution
升級前務必備份資料庫。`helm upgrade` 不會自動更新 CRD，因此必須先套用 `helm/aileron/crds/`。資料庫必須符合目前 schema；不相容時先確認快照可回復，再以全新資料庫安裝。
:::
