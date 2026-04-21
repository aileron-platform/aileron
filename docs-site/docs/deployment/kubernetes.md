---
sidebar_position: 2
title: Kubernetes 模式
---

# Kubernetes 部署

## 適用情境

- 正式環境或多人協作部署
- 需要使用 Helm 管理平台固定服務
- 需要導入 `workspace-operator` 做 workspace 動態排程
- 需要 per-workspace 網路隔離（Cilium）
- 需要 Ingress/TLS 對外公開

## 架構概覽

```
┌─────────────────────────────────────────────────────────────┐
│                     Ingress Controller                       │
│  example.com → frontend                                      │
│  workspace-manager.example.com → manager                     │
│  keycloak.example.com → keycloak                             │
│  workspace-runtime-{id}.example.com → runtime pod            │
│  workspace-browser-{id}.example.com → browser pod            │
└────────┬──────────┬──────────┬──────────────────────────────┘
         │          │          │
   ┌─────▼────┐ ┌───▼────┐ ┌──▼───────┐   ┌──────────────┐
   │ Frontend  │ │Manager │ │Keycloak  │   │  Workspace   │
   │ Deploy    │ │Deploy  │ │Deploy    │   │  Operator    │
   └──────────┘ └───┬────┘ └──────────┘   │  Deploy      │
                    │                      └──────┬───────┘
              ┌─────▼──────┐                      │ reconcile
              │ Celery +   │               ┌──────▼───────┐
              │ Flower     │               │ Workspace CR │
              └────────────┘               │ (CRD)        │
                                           └──────┬───────┘
              ┌────────────┐                      │ creates
              │ PostgreSQL │               ┌──────▼───────┐
              │ StatefulSet│               │ Runtime Pod  │
              └────────────┘               │ Browser Pod  │
              ┌────────────┐               │ Next.js Pod  │
              │   Redis    │               │ Service      │
              │ StatefulSet│               │ Ingress      │
              └────────────┘               │ CiliumPolicy │
              ┌────────────┐               └──────────────┘
              │  CoTURN    │
              │ Deployment │
              └────────────┘
```

## Helm 管理範圍

Helm chart 管理平台固定服務：

| 資源類型 | 包含項目 |
|----------|---------|
| **Deployment** | frontend、workspace-manager、workspace-operator、keycloak、coturn |
| **StatefulSet** | postgres、redis |
| **Service** | 所有服務的 ClusterIP Service、CoTURN NodePort |
| **Ingress** | frontend、workspace-manager、keycloak 的統一入口 |
| **ConfigMap** | platform-config、workspace-routing、firewall-defaults、keycloak-realm、frontend-nginx |
| **Secret** | 資料庫密碼、Keycloak 密碼 |
| **RBAC** | workspace-operator ClusterRole、workspace-manager Role、ServiceAccount |
| **CRD** | `workspaces.platform.aileron.io` |
| **Job** | postgres-bootstrap（初始化資料庫） |

:::note
每個 workspace 的動態資源（Pod、Service、Ingress、CiliumNetworkPolicy）不由 Helm 直接管理，而是由 workspace-operator 根據 Workspace CR 進行 reconcile。
:::

## 需求

- Kubernetes cluster（建議 1.26+）
- `kubectl`
- `helm`（建議 3.12+）
- Ingress Controller（預設 nginx）
- 可管理的 DNS（workspace host 必須可解析；可用 wildcard DNS，或自動建立每個 host 記錄）
- TLS 憑證（若要對外公開，可搭配 cert-manager）
- `Cilium`（若要完整啟用 per-workspace firewall）
- 共享儲存（ReadWriteMany PVC 或等效方案）

## Helm Chart 位置

```
helm/aileron/
├── Chart.yaml
├── values.yaml
├── crds/
│   └── platform.aileron.io_workspaces.yaml
├── templates/
│   ├── _helpers.tpl
│   ├── frontend-deployment.yaml
│   ├── workspace-manager-deployment.yaml
│   ├── workspace-operator-deployment.yaml
│   ├── keycloak-deployment.yaml
│   ├── coturn-deployment.yaml
│   ├── postgres-statefulset.yaml
│   ├── redis-statefulset.yaml
│   ├── ingress.yaml
│   ├── platform-configmap.yaml
│   ├── workspace-routing-configmap.yaml
│   ├── firewall-defaults-configmap.yaml
│   ├── workspace-manager-rbac.yaml
│   ├── workspace-operator-rbac.yaml
│   └── ... (其他 service / secret / job)
└── files/
    └── realm.json
```

## 安裝

### 驗證 chart

```bash
# 語法檢查
helm lint helm/aileron

# 模板渲染預覽
helm template test-release helm/aileron
```

### 安裝

```bash
helm install aileron helm/aileron \
  --namespace aileron \
  --create-namespace
```

### 使用自訂 values 檔案安裝

```bash
# 複製預設 values 並修改
cp helm/aileron/values.yaml my-values.yaml
# 編輯 my-values.yaml ...

helm install aileron helm/aileron \
  --namespace aileron \
  --create-namespace \
  -f my-values.yaml
```

### 升級

```bash
helm upgrade aileron helm/aileron \
  --namespace aileron
```

### 移除

```bash
helm uninstall aileron --namespace aileron
```

:::caution CRD 不會自動刪除
`helm uninstall` 不會移除 CRD。若需完全清除：

```bash
kubectl delete crd workspaces.platform.aileron.io
```
:::

## Public Routing 設定

Kubernetes 模式使用 host-based routing（子網域模式），不使用 path-based ingress。

目前的實作是：

- Helm 建立 1 個平台層 Ingress，處理 Frontend、Workspace Manager、Keycloak
- `workspace-operator` 在每次建立 workspace 時，另外為 `workspace-runtime`、`workspace-browser`、`workspace-nextjs` 各建立 1 個獨立 Ingress

也就是說，workspace 流量不是由單一 wildcard Ingress rule 轉送，而是由 Operator 依 `workspaceId` 展開 host pattern，建立明確的 Ingress host 規則。

### Helm Values

| Value | 預設值 | 說明 |
|-------|--------|------|
| `publicRouting.scheme` | `http` | `http` 或 `https` |
| `publicRouting.baseDomain` | `aileron.local` | 主要網域 |
| `publicRouting.frontendHost` | `{baseDomain}` | Frontend host |
| `publicRouting.workspaceManagerHost` | `workspace-manager.{baseDomain}` | Manager host |
| `publicRouting.keycloakHost` | `keycloak.{baseDomain}` | Keycloak host |
| `publicRouting.runtimeHostPattern` | `workspace-runtime-{workspaceId}.{baseDomain}` | Runtime host pattern |
| `publicRouting.browserHostPattern` | `workspace-browser-{workspaceId}.{baseDomain}` | Browser host pattern |
| `publicRouting.nextjsHostPattern` | `workspace-nextjs-{workspaceId}.{baseDomain}` | Next.js host pattern |

`{baseDomain}` 和 `{workspaceId}` 是 Helm template 在部署時替換的佔位符。

### 範例設定

以 `example.com` 為示意域名：

```bash
helm upgrade --install aileron helm/aileron \
  --namespace aileron \
  --create-namespace \
  --set publicRouting.scheme=https \
  --set publicRouting.baseDomain=example.com \
  --set publicRouting.frontendHost='{baseDomain}' \
  --set publicRouting.workspaceManagerHost='workspace-manager.{baseDomain}' \
  --set publicRouting.keycloakHost='keycloak.{baseDomain}' \
  --set publicRouting.runtimeHostPattern='workspace-runtime-{workspaceId}.{baseDomain}' \
  --set publicRouting.browserHostPattern='workspace-browser-{workspaceId}.{baseDomain}' \
  --set publicRouting.nextjsHostPattern='workspace-nextjs-{workspaceId}.{baseDomain}'
```

對外 host 對應關係：

| 服務 | Host |
|------|------|
| Frontend | `https://example.com` |
| Workspace Manager | `https://workspace-manager.example.com` |
| Keycloak | `https://keycloak.example.com` |
| Workspace Runtime | `https://workspace-runtime-<workspaceId>.example.com` |
| Workspace Browser | `https://workspace-browser-<workspaceId>.example.com` |
| Workspace Next.js | `https://workspace-nextjs-<workspaceId>.example.com` |

每建立一個新的 workspace，就會依照同一組 pattern 產生另一組不同的網址。例如 `default-workspace` 會得到：

- `workspace-runtime-default-workspace.example.com`
- `workspace-browser-default-workspace.example.com`
- `workspace-nextjs-default-workspace.example.com`

## DNS 與 TLS 需求

### DNS 記錄

需要準備的 DNS 記錄：

| 記錄類型 | 名稱 | 指向 | 用途 |
|----------|------|------|------|
| A / CNAME | `example.com` | Ingress IP | Frontend |
| A / CNAME | `workspace-manager.example.com` | Ingress IP | Manager API |
| A / CNAME | `keycloak.example.com` | Ingress IP | 認證服務 |
| A / CNAME | `*.example.com` 或自動建立 `workspace-*-<workspaceId>.example.com` | Ingress IP | 所有 workspace 子網域 |

:::tip
Kubernetes 目前會為每個 workspace component 建立明確的 Ingress host，例如 `workspace-runtime-default-workspace.example.com`。DNS 層可用單一 wildcard 記錄簡化管理，也可以搭配 ExternalDNS 等工具自動建立每個 A/CNAME 記錄。
:::

### TLS 設定

使用 cert-manager 自動管理憑證：

```yaml
# values.yaml
ingress:
  enabled: true
  className: "nginx"
  annotations:
    cert-manager.io/cluster-issuer: "letsencrypt-prod"
  tls:
    - secretName: aileron-tls
      hosts:
        - example.com
        - "*.example.com"
```

:::caution Workspace TLS 行為
`values.yaml` 的 `ingress.tls` 只會套用到 Helm 建立的那個平台 Ingress。`workspace-operator` 目前建立的 workspace Ingress 只包含 host/path 規則與 nginx annotation，沒有額外寫入 `spec.tls`。若要讓 workspace 子網域走 HTTPS，通常需要由 ingress controller 提供 wildcard / default certificate，或另外擴充 operator 的 Ingress TLS 邏輯。
:::

或手動建立 TLS Secret：

```bash
kubectl create secret tls aileron-tls \
  --cert=fullchain.pem \
  --key=privkey.pem \
  -n aileron
```

### 本機開發 DNS 設定 (macOS)

在本機使用 Kubernetes（Docker Desktop / Rancher Desktop / minikube）開發時，預設 `baseDomain` 為 `aileron.localhost`。每個 workspace 會動態產生子網域，例如：

```
workspace-runtime-<uuid>.aileron.localhost
workspace-browser-<uuid>.aileron.localhost
workspace-nextjs-<uuid>.aileron.localhost
```

macOS 不會自動將 `*.aileron.localhost` 解析到 `127.0.0.1`，而 `/etc/hosts` 也不支援 wildcard。因此需要使用 dnsmasq 做本地 wildcard DNS 解析。

:::caution 不設定會怎樣？
瀏覽器無法解析 workspace 子網域 → HTTP request 發不出去 → AI Conversation 顯示 **Disconnected**、version-control / preview 等功能全部失效。DevTools Network 會看到 **Status Code 空白**。
:::

**安裝與設定步驟**：

```bash
# 1. 安裝 dnsmasq
brew install dnsmasq

# 2. 加入 wildcard 規則
echo 'address=/aileron.localhost/127.0.0.1' >> $(brew --prefix)/etc/dnsmasq.conf

# 3. 建立 macOS resolver 設定
sudo mkdir -p /etc/resolver
echo 'nameserver 127.0.0.1' | sudo tee /etc/resolver/aileron.localhost

# 4. 啟動 dnsmasq (以 root 綁定 port 53)
sudo brew services start dnsmasq
```

**驗證**：

```bash
# 確認 macOS resolver 已掛載
scutil --dns | grep -A2 aileron.localhost

# 測試解析（應回 127.0.0.1）
dscacheutil -q host -a name test.aileron.localhost

# 直接查詢 dnsmasq
dig @127.0.0.1 test.aileron.localhost +short
```

:::tip 替代方案：nip.io
若不想安裝 dnsmasq，可改用公開 wildcard DNS 服務。在 `values.yaml` 設定 `publicRouting.baseDomain: 127.0.0.1.nip.io`，所有 `*.127.0.0.1.nip.io` 都會自動解析到 `127.0.0.1`。但需要 `helm upgrade` 並重建現有 workspace。
:::

## Internal vs External URL

:::important
`internalUrl` 與 `externalUrl` 分工明確，部署時不要混用。
:::

| 類型 | 用途 | 使用場景 |
|------|------|----------|
| `internalUrl` | Cluster 內部 Service DNS | pod-to-pod、service-to-service 呼叫 |
| `externalUrl` | 公開 Ingress URL | 瀏覽器、OIDC redirect、WebSocket、preview |

Internal URL 範例：

```
http://workspace-manager.<namespace>.svc.cluster.local:3001
http://workspace-runtime-<workspaceId>.<namespace>.svc.cluster.local:3002
http://workspace-browser-<workspaceId>.<namespace>.svc.cluster.local:6080
http://workspace-nextjs-<workspaceId>.<namespace>.svc.cluster.local:3003
```

workspace-routing ConfigMap 記錄了完整的 routing 合約，包含 service name template 與 port 對應：

| 設定 | 值 |
|------|-----|
| `RUNTIME_SERVICE_NAME_TEMPLATE` | `workspace-runtime-{workspaceId}` |
| `BROWSER_SERVICE_NAME_TEMPLATE` | `workspace-browser-{workspaceId}` |
| `NEXTJS_SERVICE_NAME_TEMPLATE` | `workspace-nextjs-{workspaceId}` |
| `RUNTIME_SERVICE_PORT` | `3002` |
| `BROWSER_SERVICE_PORT` | `6080` |
| `NEXTJS_SERVICE_PORT` | `3003` |

## Workspace CRD

Workspace Operator 使用自訂 CRD `workspaces.platform.aileron.io` 管理工作區：

```yaml
apiVersion: platform.aileron.io/v1alpha1
kind: Workspace
metadata:
  name: ws-example
  namespace: workspace-system
spec:
  workspaceId: "my-workspace"
  ownerId: "user-123"
  provisioner: kubernetes
  runtime:
    imageKey: default
    image: ailerondocker/workspace-runtime:k8s-local
    resources: {}
  browser:
    enabled: true
    image: ailerondocker/workspace-browser:k8s-local
  nextjs:
    enabled: true
    image: ailerondocker/workspace-nextjs:k8s-local
  workspacePath: /workspace
  targetNamespace: workspace-system
  git:
    url: "https://github.com/example/repo.git"
    branch: main
  envVars:
    - key: NODE_ENV
      value: production
  firewall:
    workspace:
      networkAccessEnabled: true
      domainAccessMode: specific
      allowedDomains:
        - github.com
        - api.anthropic.com
    browser:
      networkAccessEnabled: true
      domainAccessMode: specific
      allowedDomains:
        - google.com
```

### CRD Status

Operator 會將 workspace 狀態更新到 `.status`：

| 欄位 | 說明 |
|------|------|
| `status.phase` | workspace 整體狀態 |
| `status.targetNamespace` | 實際部署的 namespace |
| `status.components.runtime.phase` | Runtime pod 狀態 |
| `status.components.runtime.internalUrl` | Runtime 內部 URL |
| `status.components.runtime.externalUrl` | Runtime 外部 URL |
| `status.components.browser.*` | Browser pod 狀態與 URL |
| `status.components.nextjs.*` | Next.js pod 狀態與 URL |
| `status.firewall.*.effectiveAllowedDomains` | 實際生效的 domain 允許清單 |

### 操作觸發

透過 `spec.operations` 可觸發元件重啟：

```yaml
spec:
  operations:
    restartWorkspaceAt: "2026-04-09T10:00:00Z"   # 重啟整個 workspace
    restartRuntimeAt: "2026-04-09T10:00:00Z"      # 僅重啟 runtime
    restartBrowserAt: "2026-04-09T10:00:00Z"      # 僅重啟 browser
    restartNextjsAt: "2026-04-09T10:00:00Z"       # 僅重啟 nextjs
```

## Kubernetes 設定

| Helm Value | 環境變數 | 預設值 | 說明 |
|------------|----------|--------|------|
| `kubernetes.provisioner` | `RUNTIME_PROVISIONER` | `kubernetes` | 預設 provisioner |
| `kubernetes.defaultNamespace` | `RUNTIME_K8S_NAMESPACE` | `workspace-system` | 預設 namespace |
| `kubernetes.allowedNamespaces` | `RUNTIME_K8S_ALLOWED_NAMESPACES` | `[workspace-system, default]` | 允許的 namespace 列表 |
| `kubernetes.serviceType` | `RUNTIME_K8S_SERVICE_TYPE` | `ClusterIP` | Service type |
| `kubernetes.nodePort` | `RUNTIME_K8S_NODE_PORT` | _(空)_ | NodePort 設定 |
| `kubernetes.nodeAddress` | `RUNTIME_K8S_NODE_ADDRESS` | `127.0.0.1` | Node 位址 |
| `kubernetes.pvcName` | `RUNTIME_K8S_PVC_NAME` | `workspace-runtime-pvc` | PVC 名稱 |
| `kubernetes.runtimeImage` | `RUNTIME_K8S_IMAGE` | `ailerondocker/workspace-runtime:k8s-local` | Runtime 映像 |
| `kubernetes.browserImage` | `RUNTIME_K8S_BROWSER_IMAGE` | `ailerondocker/workspace-browser:k8s-local` | Browser 映像 |
| `kubernetes.nextjsImage` | `RUNTIME_K8S_NEXTJS_IMAGE` | `ailerondocker/workspace-nextjs:k8s-local` | Next.js 映像 |
| `kubernetes.watchNamespace` | `WATCH_NAMESPACE` | _(空，所有 namespace)_ | Operator watch namespace |

### 覆寫 namespace 與 allowlist 範例

```bash
helm upgrade --install aileron helm/aileron \
  --namespace aileron \
  --create-namespace \
  --set kubernetes.defaultNamespace=workspace-system \
  --set kubernetes.allowedNamespaces[0]=workspace-system \
  --set kubernetes.allowedNamespaces[1]=team-a \
  --set kubernetes.allowedNamespaces[2]=team-b
```

## RBAC 與 Service Account

### Workspace Operator

Operator 需要 **ClusterRole** 層級的權限來跨 namespace 管理 workspace 資源：

| API Group | Resources | Verbs |
|-----------|-----------|-------|
| `""` (core) | pods, services, PVC, events, configmaps, secrets | 全部 |
| `apps` | deployments, statefulsets | 全部 |
| `networking.k8s.io` | ingresses | 全部 |
| `cilium.io` | ciliumnetworkpolicies | 全部（僅 cilium 啟用時） |
| `platform.aileron.io` | workspaces, workspaces/status, workspaces/finalizers | 全部 |

### Workspace Manager

Manager 僅需 **Role** 層級權限（限定在 workspace namespace 內）：

| API Group | Resources | Verbs |
|-----------|-----------|-------|
| `platform.aileron.io` | workspaces | 全部 |

## Storage 與 Persistence

### 平台服務持久化

| 服務 | 預設大小 | Access Mode | 用途 |
|------|----------|-------------|------|
| PostgreSQL | 10Gi | ReadWriteOnce | 資料庫 |
| Redis | 5Gi | ReadWriteOnce | 快取與任務佇列 |

```yaml
# values.yaml 範例
postgres:
  persistence:
    enabled: true
    size: 20Gi
    storageClass: "fast-ssd"

redis:
  persistence:
    enabled: true
    size: 5Gi
```

### Workspace 儲存

Workspace 使用 PVC 掛載工作目錄，Operator 會根據 `kubernetes.pvcName` 配置自動建立掛載：

```yaml
kubernetes:
  pvcName: workspace-runtime-pvc
```

:::tip 共享儲存
若多個 workspace 需要共享基礎映像或工具，可使用 ReadWriteMany 的 StorageClass（如 NFS、CephFS、EFS）。
:::

### Knowledge Base 儲存

Knowledge Base 會使用獨立的共享 PVC，由 Helm chart 管理：

```yaml
kubernetes:
  knowledgeBases:
    pvcName: knowledge-bases-pvc
    size: 20Gi
    accessModes:
      - ReadWriteMany
    storageClassName: hostpath
```

掛載流程如下：

- Helm 建立 `knowledge-bases-pvc`
- `workspace-manager` 將它掛到 `/host/knowledge-bases`
- `workspace-operator` 再把每個 attach 的 KB 以 `subPath=<kbId>` 掛進 runtime Pod 的 `/knowledge/<alias>`

本機 dev 建議：

- 預設 `hostpath` 是單節點 fallback，適合 Docker Desktop 或本機 Kubernetes smoke test
- 它不是多節點共享 RWX 的替代品

正式環境建議：

- 將 `kubernetes.knowledgeBases.storageClassName` 切到真正的共享 RWX 類型，例如 `nfs`
- `helm/values-rke.yaml` 已內建這個覆寫
- 在驗證 KB attach / mount 之前，先確認 `knowledge-bases-pvc` 已經 `Bound`

建議檢查：

```bash
kubectl get pvc -n aileron knowledge-bases-pvc
kubectl describe pvc -n aileron knowledge-bases-pvc
kubectl describe deployment -n aileron aileron-workspace-manager
```

## CoTURN (WebRTC TURN Server)

workspace-browser 使用 [neko](https://github.com/m1k1o/neko) 透過 WebRTC 串流桌面畫面。在 Kubernetes 環境中，neko pod 與使用者瀏覽器之間存在多層 NAT，必須透過 TURN server 做 relay 才能建立 WebRTC 連線。

### 為什麼需要 TURN

WebRTC 建立連線時，雙方透過 ICE 協議交換候選位址（candidate）：

```
瀏覽器（Mac） ←── WebSocket 信令 ──→ neko pod（K8s）
     │                                      │
     └──── 嘗試直連（host candidate）────────┘
           pod IP（10.x.x.x）對外不可達 → 失敗
     │                                      │
     └──── TURN relay ─── coturn ──────────┘
           雙方各在 coturn 上拿到 relay 位址 → 成功
```

若沒有 TURN，ICE 只有 host candidate（pod 內部 IP），瀏覽器完全連不到，browser 元件會卡在 **Connecting...**。

### 架構說明

```
[瀏覽器]                    [K8s Node]
    │  turn:nodeIP:nodePort      │
    │──────────────────────────→│ NodePort 30479
    │                            │  ↓ (kube-proxy)
    │                         [coturn pod]
    │                         hostNetwork: true
    │                         port 3478 直接綁 nodeIP
    │                         relay: nodeIP:49152-65535
    │←─── relay at nodeIP:49xxx ─┘
    │
[neko pod]
    │  turn:nodeIP:nodePort
    │──────────────────────────→ [coturn] (同 K8s 內部可達)
    │←─── relay at nodeIP:49yyy ─┘
    │
兩端 relay 都在 nodeIP，coturn 在中間轉發 → WebRTC 連線建立
```

### 為什麼需要 `hostNetwork: true`

TURN relay 使用的 ephemeral UDP 埠（預設 49152–65535）**無法透過 NodePort 一一對應**（NodePort 只能對應單一 port）。啟用 `hostNetwork: true` 後：

- coturn pod 直接使用 node 的網路 namespace
- relay 埠直接綁定在 node IP，對外可達
- 信令 port（3478）同樣直接在 node IP 上，不需要 NodePort 路由也能存取

這是 NodePort-only K8s 環境中部署 TURN server 的標準做法。

### `host` 與 `frontendHost` 的區別

neko v3 將 ICE server 設定分為 **backend**（neko pod → TURN）與 **frontend**（瀏覽器 → TURN）兩組，這讓本機與正式環境可以使用不同的位址：

| 設定 | 適用方 | 說明 |
|------|--------|------|
| `coturn.host` | neko pod（backend） | Pod 連到 TURN 用的 IP，使用 node IP |
| `coturn.frontendHost` | 使用者瀏覽器（frontend） | 瀏覽器連到 TURN 用的 IP；若未設定，預設同 `host` |

:::info 正式環境
正式 K8s 環境的瀏覽器直接連 node IP（`host`），**不需要設定 `frontendHost`**（留空即自動 fallback 到 `host`）。
:::

:::info 本機開發（Docker Desktop）
Docker Desktop 對 Mac 上的瀏覽器只透過 `localhost` proxy NodePort，不直接暴露 VM IP（`192.168.65.3`）。因此：
- `host` = `192.168.65.3`（pod 可達的 node IP）
- `frontendHost` = `127.0.0.1`（Mac 瀏覽器透過 Docker Desktop localhost proxy 可達）
:::

### Helm Values

| Helm Value | 預設值 | 說明 |
|------------|--------|------|
| `coturn.enabled` | `true` | 是否啟用 TURN server |
| `coturn.port` | `3478` | coturn 監聽 port（container 內） |
| `coturn.nodePort` | `30478` | K8s NodePort |
| `coturn.host` | `192.168.65.3` | node 的外部可達 IP（backend 用） |
| `coturn.frontendHost` | `""`（同 `host`） | 瀏覽器連 TURN 用的 IP（frontend 用） |
| `coturn.username` | `aileron` | TURN 認證帳號 |
| `coturn.credential` | `aileron-turn-secret` | TURN 認證密碼（正式環境請換強密碼） |
| `coturn.realm` | `aileron.localhost` | TURN realm |

### 各環境設定範例

**正式環境（NodePort，node 有 public IP）：**

```yaml
coturn:
  host: "203.0.113.10"      # node 的公網 IP
  nodePort: 30479
  username: "aileron"
  credential: "your-strong-secret-here"
  # frontendHost 不需設定，自動同 host
```

防火牆需開放：
- `nodePort`（預設 30479）：UDP + TCP，供 TURN 信令使用
- `49152–65535`：UDP，供 TURN relay media 使用

**本機開發（Docker Desktop）：**

```yaml
coturn:
  host: "192.168.65.3"      # Docker Desktop node IP（pod 可達）
  frontendHost: "127.0.0.1" # Mac 瀏覽器透過 localhost proxy 可達
  nodePort: 30479
```

**多 node 正式環境注意事項：**

`hostNetwork: true` 在每個 node 上只能跑一個 coturn（port 3478 衝突）。若 cluster 有多個 node，需用 `nodeSelector` 固定 coturn 到指定 node，並確保 `coturn.host` 設為該 node 的 IP：

```bash
# 將 coturn 固定到特定 node（先為 node 加 label）
kubectl label node <turn-node> role=turn

# values.yaml 加入
# coturn.nodeSelector.role: turn
```

### 驗證 TURN 連線

連線正常時，browser pod log 會出現：

```
ICE connection state changed: connected
peer connection state changed: connected
set webrtc connected: connected=true
```

若 browser 卡在 **Connecting...**，依序檢查：

1. **coturn pod 是否正常啟動：**

   ```bash
   kubectl logs -n aileron deployment/aileron-coturn | grep "Relay address"
   # 應看到 node IP（如 203.0.113.10）而非 pod 內部 IP（10.x.x.x）
   ```

2. **relay 位址是否正確（node IP，非 pod IP）：**

   ```
   INFO: Relay address to use: 203.0.113.10  ← 正確
   INFO: Relay address to use: 10.1.0.x      ← 錯誤（缺 --external-ip 或 hostNetwork）
   ```

3. **防火牆是否放行 UDP 49152–65535。**

4. **本機開發：** `frontendHost` 是否設為 `127.0.0.1`，而非 Docker Desktop VM IP。

## Ingress 設定

預設使用 nginx ingress controller，並配置 WebSocket 所需的長超時：

```yaml
ingress:
  enabled: true
  className: "nginx"
  annotations:
    nginx.ingress.kubernetes.io/proxy-read-timeout: "3600"
    nginx.ingress.kubernetes.io/proxy-send-timeout: "3600"
    nginx.ingress.kubernetes.io/proxy-http-version: "1.1"
```

Helm chart 會自動為以下服務產生 Ingress rule：
- Frontend（`frontendHost`）
- Workspace Manager（`workspaceManagerHost`）
- Keycloak（`keycloakHost`）

:::note
Workspace 動態 Ingress（runtime、browser、nextjs）由 Operator 在 reconcile 時建立，而且每個 workspace 都會有自己獨立的 host 與 Ingress，不在此 Helm 管理 Ingress 範圍內。
:::

## Firewall Defaults

Kubernetes 模式下，平台安裝一份 firewall defaults ConfigMap，區分 workspace 和 browser 兩組：

### 預設允許 Domain

**Workspace Runtime：**
- `github.com`、`api.github.com`、`objects.githubusercontent.com`、`raw.githubusercontent.com`
- `registry.npmjs.org`、`npmjs.com`
- `pypi.org`、`files.pythonhosted.org`
- `api.anthropic.com`

**Workspace Browser：**
- `github.com`
- `google.com`、`gstatic.com`、`googleapis.com`

### 覆寫 firewall 預設 domain

```bash
helm upgrade --install aileron helm/aileron \
  --namespace aileron \
  --set firewall.defaults.workspace.allowedDomains[0]=github.com \
  --set firewall.defaults.workspace.allowedDomains[1]=registry.npmjs.org \
  --set firewall.defaults.browser.allowedDomains[0]=google.com \
  --set firewall.defaults.browser.allowedDomains[1]=gstatic.com
```

Operator 與 Manager 透過 `FIREWALL_DEFAULTS_CONFIGMAP_NAME` 環境變數取得這份 ConfigMap。啟用 Cilium 後，Operator 會為每個 workspace 建立 `CiliumNetworkPolicy`。

```yaml
# 啟用 Cilium
cilium:
  enabled: true
```

## Helm Values 完整參考

### Global

| Value | 預設值 | 說明 |
|-------|--------|------|
| `global.imagePullSecrets` | `[]` | Image pull secrets |
| `global.storageClass` | `""` | 預設 StorageClass |

### 服務開關

| Value | 預設值 | 說明 |
|-------|--------|------|
| `frontend.enabled` | `true` | 啟用 Frontend |
| `workspaceManager.enabled` | `true` | 啟用 Manager |
| `workspaceOperator.enabled` | `true` | 啟用 Operator |
| `postgres.enabled` | `true` | 啟用 PostgreSQL |
| `redis.enabled` | `true` | 啟用 Redis |
| `keycloak.enabled` | `true` | 啟用 Keycloak |
| `coturn.enabled` | `true` | 啟用 CoTURN |

### 服務映像

| Value | 預設值 |
|-------|--------|
| `frontend.image.repository` | `ailerondocker/workspace-ui` |
| `frontend.image.tag` | `k8s-local` |
| `workspaceManager.image.repository` | `ailerondocker/workspace-manager` |
| `workspaceManager.image.tag` | `k8s-local` |
| `workspaceOperator.image.repository` | `ailerondocker/workspace-operator` |
| `workspaceOperator.image.tag` | `k8s-local` |

### 認證

| Value | 預設值 | 說明 |
|-------|--------|------|
| `postgres.auth.username` | `postgres` | DB 使用者 |
| `postgres.auth.password` | `postgres` | DB 密碼 |
| `postgres.auth.appDatabase` | `aileron` | 應用程式 DB |
| `postgres.auth.keycloakDatabase` | `keycloak` | Keycloak DB |
| `keycloak.auth.adminUser` | `admin` | Keycloak 管理員 |
| `keycloak.auth.adminPassword` | `admin` | Keycloak 密碼 |
| `workspaceManager.env.SECRET_KEY` | _(開發預設值)_ | JWT signing key |

### Kubernetes Storage

| Value | 預設值 | 說明 |
|-------|--------|------|
| `kubernetes.pvcName` | `workspace-runtime-pvc` | Workspace working directory PVC |
| `kubernetes.knowledgeBases.pvcName` | `knowledge-bases-pvc` | Knowledge Base 專用共享 PVC 名稱 |
| `kubernetes.knowledgeBases.size` | `20Gi` | Knowledge Base PVC 容量 |
| `kubernetes.knowledgeBases.accessModes` | `[ReadWriteMany]` | Knowledge Base PVC access modes |
| `kubernetes.knowledgeBases.storageClassName` | `hostpath` | 本機 dev 預設 fallback；正式環境請切到共享 RWX 類型，例如 `nfs` |

## 驗證部署

安裝完成後，執行以下檢查：

```bash
# 檢查所有 Pod 狀態
kubectl get pods -n aileron

# 檢查 Service
kubectl get svc -n aileron

# 檢查 Ingress
kubectl get ingress -n aileron

# 檢查 CRD 是否安裝
kubectl get crd workspaces.platform.aileron.io

# 查看 Workspace CR（若已建立）
kubectl get workspaces -A

# 檢查 ConfigMap
kubectl get configmap -n aileron

# 查看特定服務 log
kubectl logs -n aileron deployment/aileron-workspace-manager
kubectl logs -n aileron deployment/aileron-workspace-operator
```

## 當前限制

- workspace 動態 host 是否由單一 Ingress、Gateway API 或自訂 controller 承接，取決於實際叢集的 ingress 能力
- 完整啟用 public domain routing 需先完成 DNS 與 TLS 準備，否則 Keycloak/OIDC、preview 與 WebSocket 無法正常對外工作
- 完整啟用 per-workspace domain allowlist 需安裝並配置 `Cilium`
- CoTURN `host` 必須設為 node 的實際可路由 IP；正式環境不需設 `frontendHost`（預設同 `host`），本機 Docker Desktop 開發需額外設 `frontendHost: "127.0.0.1"`
