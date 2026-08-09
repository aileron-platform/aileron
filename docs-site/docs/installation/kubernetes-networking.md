---
title: Kubernetes 網路與 TURN
description: Service DNS、Ingress、TLS、Cilium 與 Browser WebRTC 網路契約
---

# Kubernetes 網路與 TURN

## 內部與公開路由

服務對服務流量使用 Kubernetes Service DNS；所有 Aileron 瀏覽器流量只使用
`platformPublicOrigin` 的單一 host。外部 OIDC Provider 保有自己的 canonical issuer host，
且只有 Manager Pod 存取 Discovery、JWKS 與 token endpoint。

Frontend Ingress 接收 `/`、`/api/v1/...` 與 `/workspaces/{uuid}/runtime|browser|canvas/...`。
Frontend gateway 只把 canonical Workspace UUID 與固定 target 映射至 namespace-qualified
Service DNS，不接受 request-supplied upstream。HTTP streaming、WebSocket Upgrade、subprotocol、
Authorization、Cookie 與 `X-Forwarded-*` 都由 gateway 保留。

## 公開網址範例

以下以 `example.com` 示範產品入口：

```text
https://aileron.apps.example.com/
```

對應設定：

```yaml
platformPublicOrigin: https://aileron.apps.example.com

ingress:
  enabled: true
  className: nginx
  useDefaultClass: false
  tlsMode: kubernetesSecret
  tlsSecretName: aileron-platform-tls
  annotations:
    nginx.ingress.kubernetes.io/proxy-read-timeout: "3600"
    nginx.ingress.kubernetes.io/proxy-send-timeout: "3600"
    nginx.ingress.kubernetes.io/proxy-http-version: "1.1"
```

憑證只需涵蓋 `aileron.apps.example.com`。上述 annotations 是 NGINX 範例，不是產品硬編碼；
其他環境可透過 `spec.ingressClassName`、provider annotation 或明確選用的 cluster default
IngressClass 選擇控制器。

## Cilium

`cilium.enabled=true` 時，Operator 依 Workspace firewall desired state建立 policy。
DNS、Manager/OIDC provider 控制流量與 TURN 屬於 infrastructure egress，不是 UI 管理的網域清單。

## 明確 TURN Reachability Profile

平台不從雲端名稱、Ingress controller 或 homelab 標籤推測 TURN。`turn.profile` 是唯一的
machine-readable contract，必須明確列出 backend/frontend URL、policy backend、control 與
relay destination、relay UDP range、credential issuer 及 evidence freshness：

```yaml
turn:
  enabled: true
  iceServersSecretName: external-turn-ice
  backendIceServersKey: backend-ice-servers-json
  frontendIceServersKey: frontend-ice-servers-json
  credentialRevision: 7
  profile:
    policyBackend: cilium
    backend:
      urls: ["turn:turn.apps.example.com:3478"]
      controlDestination:
        kind: ciliumEntities
        values: [host, remote-node]
      relayDestination:
        kind: ciliumEntities
        values: [host, remote-node]
      relayPortRange: {min: 49160, max: 49259}
    frontend:
      urls: ["turn:turn.apps.example.com:3478"]
    credentialIssuer:
      kind: turnRest
      secretRef: external-turn-ice
      ttlSeconds: 300
    evidence:
      intervalSeconds: 30
      ttlSeconds: 90
      requiredFrontendVantages: [internet]
```

正式外部 vantage 使用 `turnRest`，對應 Secret 必須包含 `turn-rest-shared-secret`；Gateway
依 Coturn TURN REST 規則產生到期 timestamp username 與 HMAC credential。`staticSecret` 只適用
於明確標記的開發或單站測試 profile，不能作為 production-required vantage credential。

`turnRest` 也涵蓋實際 Browser 資料路徑。Browser Pod sidecar 每次 backend probe 都以 shared
secret 產生新的短效 credential；Manager 的 Browser access response 會回傳新的 frontend
`iceServers`，前端以該值建立本次 `RTCPeerConnection`，不使用 Neko 啟動時的固定 TURN
credential。內建 Coturn 使用 `staticSecret`；外部 TURN 才使用 `turnRest`。

`policyBackend` 支援 `cilium`、`kubernetes` 與明確的 `unenforced`。Destination 必須使用與
backend 相容的 `ciliumEntities`、`cidrs`、`namespacePods`、`fqdns` 或 `unenforced`；relay
destination 不接受 FQDN，因為實際 relay 位址必須落在明確 CIDR、Pod identity 或 Cilium
entity。control port 與 relay UDP range 會產生不同 egress rule，不能合併成寬鬆的 world rule。

## 內建 Coturn

`coturn.enabled=true` 時，Chart 會建立獨立 namespace、`hostNetwork` Coturn DaemonSet、
公開 TURN Service、Browser ICE Secret，以及與 Browser credential 分離的 probe identity。

```yaml
coturn:
  enabled: true
  namespace: aileron-turn-system
  frontendHost: "turn.{baseDomain}"
  listenerPort: 3478
  realm: aileron
```

`turn.{baseDomain}` 只可解析至執行 Coturn 的節點。每個節點與上游設備必須放行 profile 的
listener TCP/UDP 與 relay UDP range。部署前必須建立 `coturn.auth.existingSecretName` 指向的
credential Secret；輪替 Browser 或 probe credential 時必須同步提高 `turn.credentialRevision`。

## 外部 TURN

外部服務同樣由 TURN Reachability Profile 描述實際 endpoint 與 policy destination。部署者須在
Runtime namespace 建立 `turn.existingSecretName` 指向的 Secret，內容包含 profile 所引用的
backend/frontend ICE JSON key 與 TURN REST shared-secret key。另須在 release namespace 建立
`connectivityEvidenceGateway.auth.existingSecretName` 指向的 Secret。Secret 必須提供
`internal-token`、`agent-tokens-json`、`probe-ice-servers-json`，以及每個由 Chart 啟動的 host Agent
所需的 `agent-<vantage>-token`。外部管理的 Agent token 應由 Secret manager 安全分發至 Agent
主機，不需要在 Kubernetes Secret 中重複保存。本 Chart 的 release namespace 與 Runtime
namespace 必須相同；所有實際值由外部 Secret 管理，不放在版控。

以下 manifest 顯示必要 key 與 JSON 形狀；所有 `<...>` 都必須由 Secret manager 注入：

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: external-turn-ice
  namespace: workspace-system
type: Opaque
stringData:
  backend-ice-servers-json: >-
    [{"urls":["turn:turn.example.com:3478?transport=udp"]}]
  frontend-ice-servers-json: >-
    [{"urls":["turns:turn.example.com:5349?transport=tcp"]}]
  turn-rest-shared-secret: "<TURN REST shared secret>"
---
apiVersion: v1
kind: Secret
metadata:
  name: aileron-aileron-connectivity-evidence
  namespace: workspace-system
type: Opaque
stringData:
  internal-token: "<operator-to-gateway token>"
  agent-tokens-json: '{"internet":"<internet-agent token>"}'
  probe-ice-servers-json: >-
    [{"urls":["turns:turn.example.com:5349?transport=tcp"]}]
  agent-internet-token: "<internet-agent token>"
```

`agent-tokens-json` 是以 vantage ID 為 key 的 JSON object；每個
`requiredFrontendVantages` 都必須有且只能有一個相符 token。`agent-internet-token` 是 Chart
host Agent 對應 `vantageId: internet` 時掛載的唯讀檔案內容。三個 ICE JSON key 都是
`RTCIceServer[]`；`turnRest` profile 只保存 URL，username 與 credential 在核發時產生。

backend endpoint 必須從 Browser Pod 完成 authenticated allocation 與 relay round trip；frontend
endpoint 必須從每個 required external vantage 使用公開 DNS、TLS 與 transport 完成相同測試。
只測 DNS、TCP connect、STUN binding、Service readiness 或偶爾看到 direct ICE 都不算通過。

## Connectivity Evidence Gateway 與外部 Agent

Chart 只建立 namespace 內的 ClusterIP Gateway Service，不建立 Gateway Ingress，也沒有
`connectivityEvidenceGateway.publicHost` Helm value。若需要外部 Agent，部署者必須在 Chart
之外提供公開 HTTPS reverse proxy 或 Ingress，將指定 host 導向該 Service；外部 Agent 不需要
inbound port，但需要對這個 Gateway endpoint 的 outbound HTTPS，以及對 TURN listener 與實際
relay address/range 的 outbound TCP/UDP。Agent 以
installation ID、vantage ID 與 bearer enrollment token 取得短效 challenge 及 TURN REST probe ICE
credential，完成 relay 後回傳 nonce、profile revision、credential revision、observed time、TTL
與 relay address。Gateway 會拒絕過期、重放、identity 不符或 revision 不符的提交；evidence
不保存 credential、token 或 nonce。

```yaml
connectivityEvidenceGateway:
  enabled: true
  installationId: "{releaseNamespace}.{releaseName}"
  hostAgent:
    enabled: false
    vantageId: host
    tls:
      caSecretName: ""
      caSecretKey: ca.crt
```

Agent 使用與 Workspace Operator 相同的 image，並以 `--mode=connectivity-external-agent` 啟動。
token 必須由 Secret manager 寫入只允許 Agent 身分讀取的檔案；命令列與環境變數只傳檔案路徑，
不傳 token 值：

```bash
docker run --read-only --cap-drop=ALL --restart=unless-stopped \
  --mount type=bind,src=/run/secrets/aileron-connectivity-agent-token,dst=/var/run/secrets/aileron-connectivity-agent-token,readonly \
  -e CONNECTIVITY_EVIDENCE_GATEWAY_URL=https://connectivity.apps.example.com \
  -e AILERON_INSTALLATION_ID=workspace-system.aileron \
  -e CONNECTIVITY_AGENT_VANTAGE_ID=internet \
  -e CONNECTIVITY_AGENT_INTERVAL_SECONDS=30 \
  -e CONNECTIVITY_AGENT_TOKEN_FILE=/var/run/secrets/aileron-connectivity-agent-token \
  ailerondocker/workspace-operator@sha256:<digest> \
  --mode=connectivity-external-agent
```

Gateway 使用公開 CA 時，Agent 直接使用 image 的系統 trust store。企業私有 CA 環境必須將
CA bundle 以唯讀 Secret 或主機檔案交付給 Agent；Chart 管理的 `hostAgent` 透過
`tls.caSecretName` 與 `tls.caSecretKey` 掛載並設定 `CONNECTIVITY_AGENT_CA_FILE`。外部
Docker Agent 則自行掛載 CA 檔並設定同一環境變數。Agent 會把自訂 CA 加入系統 trust
store，仍要求 TLS 1.2 以上且不提供跳過憑證驗證的選項。

Gateway protocol 使用 `POST /v1/challenges` 與 `POST /v1/evidence`；Operator 以內部 token 讀取
`GET /v1/evidence/{profileRevision}/{vantage}`。Agent log 必須顯示週期成功，Workspace CR 中每個
required vantage 的 evidence 也必須在 `expiresAt` 前持續更新。

正式部署應將 Agent 放在實際使用者網路、DMZ、企業出口或平台管理的外部地區。本機開發或
明確分類的單站 homelab 可啟用 `hostAgent`，但 Kubernetes node 的 host network 證據不能宣稱
代表一般網際網路或所有使用者最後一哩。每個 production-required vantage 都必須有自己的
token；缺少證據時 Gateway 不延長已到期 evidence 的 TTL。

## Browser connectivity readiness 與授權

每個 Browser Pod 另有不掛 ServiceAccount token 的 probe sidecar，直接從 Browser network
namespace 測 backend TURN。Operator 拉取 sidecar 與 Gateway evidence，驗證 profile revision、
credential revision、observed time 與 expiry 後，才更新 Workspace CR 的
`status.browserConnectivity`。狀態由 Operator 單一權威產生，Manager 只投影並在
`POST /api/v1/workspaces/{workspace_id}/browser/access` 做新 session admission。

狀態不是 Pod liveness，也不會切斷既有健康 session。一般 restart、stop/start 不輪替 Browser
credential；權限撤銷或明確 rotate 只重建 Browser，不應變更 Runtime/Canvas Pod UID。所有
credential、agent token 與 challenge secret 都不得寫入 CR、ConfigMap 或 log。

Backend probe 使用的 TURN REST username 是 `${expiry}:backend:${workspaceId}`，其中 identity 僅供
TURN 稽核歸屬。證據的 Workspace 邊界由每個 Browser 的專屬 Service endpoint、profile revision、
credential revision、observed time 與 expiry 共同約束；Operator 不以 username 解析結果決定
Workspace 歸屬。

## 原始碼依據

- `helm/aileron/values.schema.json`
- `helm/aileron/templates/connectivity-evidence-gateway.yaml`
- `workspace-operator/internal/controller/turn_profile.go`
- `workspace-operator/internal/controller/turn_probe.go`
- `workspace-operator/internal/controller/connectivity_evidence_gateway.go`
- `workspace-operator/internal/controller/browser_connectivity.go`
