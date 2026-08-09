---
title: Kubernetes 快速安裝
description: 以 Helm 從全新環境安裝 Aileron 的最短流程
---

# Kubernetes 快速安裝

本章是全新 Kubernetes 環境的安裝入口。專案不提供可直接部署的 production platform
overlay；部署流程必須產生 `/run/aileron/platform-values.yaml`，提供該叢集已驗證的儲存、
網路、Ingress、TURN 與安全契約。`helm/aileron/tests/values/platform-*.yaml` 只供 render
contract 測試，不是部署 profile。正式部署前，先完成下列專題：

- [儲存設計](./kubernetes-storage.md)
- [映像建置與私有 Registry](./kubernetes-images.md)
- [網路、Ingress、TLS 與 TURN](./kubernetes-networking.md)
- [Workspace 防火牆](./kubernetes-firewall.md)
- [Helm values 參考](/reference/helm-values.md)

## 前置條件

- 已列入專案 conformance matrix 且實際通過驗證的 Kubernetes minor／provider 組合、
  `kubectl`、Helm 3 與可用的 Ingress Controller。不得只因某個 API 已存在，就推論其後
  所有 Kubernetes minor 都受支援。
- 叢集必須提供 GA
  [`discovery.k8s.io/v1` EndpointSlice API](https://kubernetes.io/docs/reference/kubernetes-api/discovery/endpoint-slice-v1/)；
  conformance 無法使用時應直接失敗，不得改用 `Endpoints` API。
- Cilium。正式環境必須以 `cilium.enabled=true` 啟用 Workspace 網路隔離；目前的
  firewall attestor DaemonSet 需要以 UID 0 唯讀掛載 node 上的 Cilium socket。
- Workspace working tree 使用 `Filesystem + ReadWriteMany` 的共享儲存。
- Runtime HOME 預設使用 `ReadWriteOnce`；平台也可明確改用 `ReadWriteMany`。
- Knowledge Base 使用 `Filesystem + ReadWriteMany + Retain` 的共享儲存。
- Manager state、PostgreSQL 與 Redis 各自使用明確的 `ReadWriteOnce + Retain` StorageClass。
- 所有 Aileron 映像均為目標架構的不可變 digest，且節點信任私有 Registry CA。
- `platformPublicOrigin` 的單一公開 DNS 與 TLS Secret 已完成。
- Runtime assertion 金鑰與 Browser credential 等必要 Secret 已建立；Registry 認證則依平台
  使用 kubelet identity 或 image pull Secret。
- 內建 TURN 的 DNS 與節點防火牆已完成；使用外部 TURN 時則已建立 ICE JSON Secret。

正式 profile 不會從 `global.storageClass` 推測資料用途。每個持久化元件都必須指定自己的
StorageClass。

## 1. 準備 namespace 與 Secrets

以下命令都應在叢集管理主機執行：

先在權限 `0700` 的暫存目錄準備：

```bash
install -d -m 0700 /run/aileron/private-material
```

- `private-key.pem`：Ed25519 PKCS#8 private key，檔案權限 `0600`。
- `jwks.json`：只包含對應 public key，且其 `kid` 與
  `runtimeAssertions.activeKid` 完全相同。
- `browser-credential-keyring.json`：由受控 secret workflow 產生，檔案權限 `0600`，
  格式如下；key material 是 32-byte random value 的 unpadded base64url。

`jwks.json` 必須使用以下 OKP／Ed25519 signing-key schema；`x` 是 32-byte raw public
key 的 unpadded base64url，不是 PEM 或 DER 內容：

```json
{
  "keys": [
    {
      "kty": "OKP",
      "crv": "Ed25519",
      "alg": "EdDSA",
      "use": "sig",
      "kid": "workspace-manager-ed25519-v1",
      "x": "<base64url-encoded-32-byte-public-key>"
    }
  ]
}
```

在受控管理主機準備 `openssl` 與 `jq` 後，可用下列命令驗證 schema、`kid` 與
private／public key pair。命令不會輸出 private key，但仍不得開啟 shell tracing：

```bash
set +x
export ACTIVE_KID=workspace-manager-ed25519-v1

head -n 1 /run/aileron/private-material/private-key.pem \
  | grep -qx -- '-----BEGIN PRIVATE KEY-----'
openssl pkey \
  -in /run/aileron/private-material/private-key.pem \
  -check -noout >/dev/null

jq -e --arg kid "${ACTIVE_KID}" '
  ([.keys[] | select(.kid == $kid)] | length) == 1 and
  any(.keys[];
    .kid == $kid and
    .kty == "OKP" and
    .crv == "Ed25519" and
    .alg == "EdDSA" and
    .use == "sig" and
    (.x | test("^[A-Za-z0-9_-]{43}$"))
  )
' /run/aileron/private-material/jwks.json >/dev/null

EXPECTED_X="$(
  jq -er --arg kid "${ACTIVE_KID}" \
    '.keys[] | select(.kid == $kid) | .x' \
    /run/aileron/private-material/jwks.json
)"
ACTUAL_X="$(
  openssl pkey \
    -in /run/aileron/private-material/private-key.pem \
    -pubout -outform DER 2>/dev/null \
  | tail -c 32 \
  | openssl base64 -A \
  | tr '+/' '-_' \
  | tr -d '='
)"
test "${EXPECTED_X}" = "${ACTUAL_X}"
unset EXPECTED_X ACTUAL_X ACTIVE_KID
```

`runtimeAssertions.activeKid` 必須設成同一個 `kid`。正式 PKI／secret workflow 應直接產生
上述兩份 material，這段命令只負責部署前驗證，不負責產生或輪替金鑰。

Browser credential keyring 使用另一組獨立 secret，格式如下：

```json
{
  "algorithm": "hkdf-sha256-v1",
  "activeKeyId": "browser-credential-v1",
  "keys": {
    "browser-credential-v1": "<base64url-encoded-32-byte-secret>"
  }
}
```

專案的 `workspace-manager/scripts/generate_runtime_assertion_keys.py` 目前是 Docker
development 初始化工具，不是 production PKI 契約。正式環境應由組織的 PKI／secret
manager 產生並保管 matching assertion pair 與 Browser keyring。

接著建立 namespace 與 Secret：

```bash
export NAMESPACE=workspace-system
export TURN_NAMESPACE=aileron-turn-system

kubectl create namespace "${NAMESPACE}" \
  --dry-run=client -o yaml | kubectl apply -f -

kubectl create secret docker-registry registry-pull \
  --namespace "${NAMESPACE}" \
  --docker-server="${REGISTRY_HOST}" \
  --docker-username="${REGISTRY_USERNAME}" \
  --docker-password="${REGISTRY_PASSWORD}"

kubectl create secret generic runtime-assertion-signer \
  --namespace "${NAMESPACE}" \
  --from-file=private-key.pem=/run/aileron/private-material/private-key.pem

kubectl create secret generic runtime-assertion-public-jwks \
  --namespace "${NAMESPACE}" \
  --from-file=jwks.json=/run/aileron/private-material/jwks.json

kubectl create secret generic browser-credential-keyring \
  --namespace "${NAMESPACE}" \
  --from-file=keyring.json=/run/aileron/private-material/browser-credential-keyring.json

kubectl create secret tls aileron-platform-tls \
  --namespace "${NAMESPACE}" \
  --cert=./tls.crt \
  --key=./tls.key
```

若使用 built-in TURN、private Coturn image，且採 Secret-based Registry 認證，
`global.imagePullSecrets` 也會被 Coturn DaemonSet 引用，但 Kubernetes Secret 不能跨
namespace。Chart 不會複製 Registry Secret，因此安裝前還必須預建 Coturn namespace、
標記為本 Helm release 管理，並建立同名 Secret：

```bash
kubectl create namespace "${TURN_NAMESPACE}" \
  --dry-run=client -o yaml | kubectl apply -f -
kubectl label namespace "${TURN_NAMESPACE}" \
  app.kubernetes.io/managed-by=Helm --overwrite
kubectl annotate namespace "${TURN_NAMESPACE}" \
  meta.helm.sh/release-name=aileron \
  meta.helm.sh/release-namespace="${NAMESPACE}" \
  --overwrite

kubectl create secret docker-registry registry-pull \
  --namespace "${TURN_NAMESPACE}" \
  --docker-server="${REGISTRY_HOST}" \
  --docker-username="${REGISTRY_USERNAME}" \
  --docker-password="${REGISTRY_PASSWORD}"
```

若關閉 TURN、使用 external provider，或透過 kubelet／node managed identity 取得映像
拉取權限，則不需執行這個流程。雙 namespace Secret 流程只適用於 Secret-based Registry
認證；Chart 尚未自動複製或輪替 Secret。

不要將 Secret 值、kubeconfig、私鑰或含機密的 deployment values 放入 Git。

上述 `registry-pull` 只適用於需要 Kubernetes Secret 的外部私有 Registry。EKS／ECR、
GKE／Artifact Registry 或 AKS／ACR 若已由 kubelet／node managed identity 取得 pull
權限，請省略該 Secret 與 `global.imagePullSecrets`。

Helm release namespace 必須等於 `kubernetes.workspaceRuntimeNamespace`；Chart 會在
render 階段拒絕不一致的設定。外部 Registry 的 `registry-pull` 只需在這個共同 namespace
建立一份，供 Chart workload 與 Workspace 專用 ServiceAccount 使用。Kubernetes Secret
無法跨 namespace 引用，Chart 也不會替管理者複製 Registry credential。

每套 Workspace Operator installation只管理這一個runtime namespace。Controller cache、
Workspace CR與所有namespaced受管資源都限制在相同namespace；平台不提供cluster-wide、
multi-namespace或selector-based watch模式。需要隔離多個runtime namespace時，應各自部署
獨立installation。

Operator的Kubernetes API依賴與Helm RBAC來自同一份Controller Dependency Contract。
Chart只為namespaced dependency建立Role；只有實際設定Workspace或Runtime HOME
StorageClass時，才建立僅允許StorageClass `get`的ClusterRole。啟用Cilium時才加入
CiliumNetworkPolicy與CiliumEndpoint權限。Operator在所有已啟用dependency完成API
discovery、scope與wiring驗證、direct read及cache sync前不會啟動reconcile worker，任一
失敗都會使readiness fail closed，且不會只啟動部分controller。

## 2. 建立 deployment values

以平台 profile 加上不進版控的 values 檔案：

```yaml
global:
  imagePullSecrets:
    - name: registry-pull

platformPublicOrigin: https://aileron.apps.example.com

oidc:
  issuerUrl: https://login.example.com/realms/aileron
  clientId: aileron-manager

ingress:
  enabled: true
  className: "<ingress-class>"
  useDefaultClass: false
  tlsMode: kubernetesSecret
  tlsSecretName: aileron-platform-tls
  annotations: {}

runtimeAssertions:
  issuer: workspace-manager
  activeKid: workspace-manager-ed25519-v1
  privateKeySecretName: runtime-assertion-signer
  publicKeySetSecretName: runtime-assertion-public-jwks

browserCredentials:
  existingSecretName: browser-credential-keyring
  key: keyring.json
  revision: 1

cilium:
  enabled: true
```

映像 digest、StorageClass、強密碼與 TURN 設定請依專題文件補齊。
使用平台原生 Registry identity 時，將 `global.imagePullSecrets` 保持空陣列。
`ingress.annotations` 只套用於單一平台 Ingress。請由部署環境填入 AWS Load Balancer
Controller、GKE Ingress、Application Gateway、NGINX 或其他控制器所需值；產品預設會關閉
公開 Ingress，也不假設任何特定控制器。Runtime、Browser 與 Canvas 只建立內部 Service，
Frontend gateway 以 `/workspaces/{uuid}/runtime|browser|canvas` 固定 path 轉送。

控制器選擇可使用 `ingress.className`、`kubernetes.io/ingress.class` annotation，或在叢集已有刻意設定的 default IngressClass 時
明確設為 `ingress.useDefaultClass: true`。TLS 由 Kubernetes Secret 終止時使用
`tlsMode: kubernetesSecret`；由 AWS ACM、GCP pre-shared certificate 或其他控制器政策管理時
使用 `tlsMode: controllerManaged` 並保持 `tlsSecretName: ""`。

## 3. 部署前檢查

以下以部署流程產生的 platform overlay 示範；每個叢集都必須讓 `PLATFORM_VALUES`
指向自己的 platform overlay：

```bash
export PLATFORM_VALUES=/run/aileron/platform-values.yaml

helm lint helm/aileron \
  -f "${PLATFORM_VALUES}" \
  -f /run/aileron/deployment-values.yaml

helm template aileron helm/aileron \
  --namespace workspace-system \
  -f "${PLATFORM_VALUES}" \
  -f /run/aileron/deployment-values.yaml \
  >/tmp/aileron-rendered.yaml

kubectl apply --dry-run=server -f /tmp/aileron-rendered.yaml
```

`PLATFORM_VALUES` 必須是該叢集的 provider-neutral／provider-specific production profile；
不可把其他環境的 GID、StorageClass 或管理者設定當成 EKS、GKE、AKS 或原生 Kubernetes
的預設。
`helm/aileron/tests/values/platform-*.yaml` 只是 Helm render contract fixtures，不是可部署
profile；render 通過也不能取代目標 provider 與實際 CSI 上的 conformance 認證。
任何環境的通過結果都只代表該次記錄的 Kubernetes minor、CSI、CNI 與 admission 組合；
若要新增或升級原生 Kubernetes、EKS、GKE、AKS、OCP 或 RKE2 版本，必須把該組合納入矩陣
並重新執行完整 conformance。

目前的 production 網路隔離契約只涵蓋允許部署 Cilium、DaemonSet、UID 0 container 與
Cilium socket `hostPath` 的 node-based cluster。GKE Autopilot、EKS Fargate、AKS virtual
nodes 或禁止該 host access 的環境不在此契約內；若未來要支援，必須先提供另一個可驗證的
firewall attestation backend，不能把 Cilium enforcement 靜默略過。

成功條件：

- lint、render 與 server-side dry-run 都回傳成功。
- render 結果沒有浮動 image tag。
- 所有持久化元件都有專屬 StorageClass。
- 內建 TURN 是唯一允許使用 `hostNetwork` 的 workload，且只放行設定的 relay 範圍。
- TURN 認證只透過 Secret 引用，不出現在 Pod arguments 的實際值中。
- 使用 built-in TURN 與 private Registry 時，`workspace-system` 與 `coturn.namespace`
  都能讀取 `global.imagePullSecrets` 指定的同名 Secret。

## 4. 安裝

```bash
helm upgrade --install aileron helm/aileron \
  --namespace workspace-system \
  --create-namespace \
  -f "${PLATFORM_VALUES}" \
  -f /run/aileron/deployment-values.yaml \
  --atomic \
  --timeout 15m
```

## 5. 最小驗收

```bash
kubectl get pods,pvc,ingress -n workspace-system
export RELEASE=aileron
for component in frontend workspace-manager workspace-operator; do
  kubectl wait deployment \
    --namespace workspace-system \
    --selector="app.kubernetes.io/instance=${RELEASE},app.kubernetes.io/component=${component}" \
    --for=condition=Available \
    --timeout=10m
done
kubectl get jobs -n workspace-system
helm status aileron -n workspace-system
```

所有平台 Pod 應為 Ready，PVC 應為 Bound，Helm release 應為 `deployed`。接著建立測試
Workspace，確認首次 bootstrap 完成後 Runtime、Browser 與 Canvas 各自 Ready。

## 升級

先保存目前 revision 與 values，再以新的不可變 digest升級：

```bash
helm history aileron -n workspace-system
helm get values aileron -n workspace-system -o yaml \
  >/run/aileron/previous-values.yaml

helm upgrade aileron helm/aileron \
  --namespace workspace-system \
  -f "${PLATFORM_VALUES}" \
  -f /run/aileron/deployment-values.yaml \
  --atomic \
  --timeout 15m
```

## 回復

只變更 Deployment 與 values，且未變更資料契約時：

```bash
helm rollback aileron <revision> \
  --namespace workspace-system \
  --wait \
  --timeout 15m
```

資料庫 schema、CRD 或 PVC 契約已變更時，單獨執行 `helm rollback` 不足。必須同時還原相符
的 PostgreSQL/NFS snapshot、CRD 與映像 digest。Knowledge Base 與平台狀態應使用 Retain
StorageClass，避免 release 操作直接回收資料。
