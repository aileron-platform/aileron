---
title: 部署診斷
description: Kubernetes、Docker 與平台服務的通用診斷流程
---

# 部署診斷

診斷時先保存實際狀態，再變更設定。輸出若含 Secret、token、cookie、內部位址或使用者資料，
必須先遮蔽才能分享。

## Helm 安裝或升級失敗

```bash
helm status aileron -n workspace-system
helm history aileron -n workspace-system
helm get values aileron -n workspace-system -o yaml
kubectl get events -n workspace-system \
  --sort-by='.lastTimestamp'
kubectl get jobs,pods -n workspace-system
```

重新執行 lint、render 與 server-side dry-run，確認錯誤發生在 values 驗證、API admission、
hook Job 或 workload readiness。

## Pod 無法啟動

```bash
kubectl get pods -n workspace-system -o wide
kubectl describe pod -n workspace-system <pod-name>
kubectl logs -n workspace-system <pod-name> --all-containers
kubectl logs -n workspace-system <pod-name> --all-containers --previous
```

依事件判斷：

- `ErrImagePull`／`ImagePullBackOff`：檢查 digest、imagePullSecret、Registry CA 與節點網路。
- `CreateContainerConfigError`：檢查 Secret key、ConfigMap key 與 security context。
- `CrashLoopBackOff`：比較 current/previous log、termination reason 與 exit code。
- `Pending`：檢查資源、taint、affinity、PVC 與 StorageClass binding mode。

## PVC Pending 或權限失敗

```bash
kubectl get storageclass
kubectl get pvc,pv -n workspace-system
kubectl describe pvc -n workspace-system <pvc-name>
kubectl get events -n workspace-system \
  --field-selector involvedObject.kind=PersistentVolumeClaim
```

不要在應用程式 image 內對 volume root 執行 `chown`，不要加入 privileged initContainer，
也不要關閉 NFS `root_squash`。請回到 [Kubernetes 儲存設計](./kubernetes-storage.md)檢查
StorageClass、GID、setgid 與 export policy。

## Workspace 元件狀態不一致

```bash
kubectl get workspace -n workspace-system <workspace-name> -o yaml
kubectl get deployment,pod,service,ingress \
  -n workspace-system \
  -l aileron.io/workspace-id=<workspace-id>
```

Runtime、Browser、Canvas 是獨立元件。請分別查看 `status.components` 的 phase、desired/
observed revision、Pod UID 與 reason。首次 bootstrap 完成前，Browser/Canvas 尚未建立是
預期行為；bootstrap 完成後，單一元件錯誤不應重建其他健康元件。

Runtime bootstrap 失敗時：

```bash
kubectl logs -n workspace-system \
  --selector='aileron.io/workspace-id=<workspace-id>,aileron.io/component=workspace-runtime' \
  --all-containers \
  --tail=200
kubectl get pod -n workspace-system \
  -l aileron.io/workspace-id=<workspace-id> \
  -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.status.containerStatuses[*].state.terminated.reason}{"\t"}{.status.containerStatuses[*].state.terminated.message}{"\n"}{end}'
```

依穩定 error code 檢查 Git、agent defaults、custom setup 或 Runtime HOME 內的 bootstrap
state，不要用重建另兩個元件掩蓋失敗。

## Firewall 未套用

先從 Manager firewall API 取得 desired revision，再比較 Workspace CR 與 Cilium policy：

```bash
kubectl get workspace -n workspace-system <workspace-name> -o yaml
kubectl get ciliumnetworkpolicy -n workspace-system \
  -l aileron.io/workspace-id=<workspace-id> \
  -o yaml
kubectl logs -n workspace-system \
  --selector='app.kubernetes.io/instance=aileron,app.kubernetes.io/component=workspace-operator' \
  --all-containers \
  --tail=200
```

`applying` 表示 observed revision 尚未追上 desired revision；`error` 時依 error code 處理。
Firewall 更新不應改變 Runtime、Browser 或 Canvas Pod UID。

## Ingress、TLS 或 WebSocket 失敗

```bash
kubectl get ingress -n workspace-system
kubectl describe ingress -n workspace-system <ingress-name>
kubectl get secret -n workspace-system aileron-platform-tls \
  -o jsonpath='{.type}{"\n"}'
curl -vkI https://aileron.apps.example.com/
```

確認 Platform Public Origin 的 DNS、憑證 SAN、IngressClass 與 WebSocket timeout 設定一致，
並確認 `/api/v1` 與 `/workspaces/{uuid}/runtime|browser|canvas` 都由同一 Ingress 進入 Frontend gateway。
不要把公開 URL 用於叢集內服務互連。

## Browser WebRTC 或 TURN 失敗

先設定本次安裝名稱；以下範例不假設固定 release 或 namespace：

```bash
export RELEASE_NAMESPACE=<release-namespace>
export RELEASE_NAME=<release-name>
export AILERON_FULLNAME=<chart-fullname>
export WORKSPACE_ID=<workspace-id>
export WORKSPACE_RESOURCE=workspace-${WORKSPACE_ID}
```

`AILERON_FULLNAME` 是 Helm chart fullname；預設為 `${RELEASE_NAME}-aileron`，若設定
`fullnameOverride` 或 `nameOverride` 則使用實際渲染名稱。

依序檢查四層；上一層未通過時不要用下一層的重試掩蓋問題。

### 1. Control plane 與 admission

```bash
kubectl get workspace -n "${RELEASE_NAMESPACE}" "${WORKSPACE_RESOURCE}" \
  -o jsonpath='{.status.browserConnectivity}{"\n"}'
kubectl logs -n "${RELEASE_NAMESPACE}" \
  deployment/${RELEASE_NAME}-aileron-workspace-operator \
  --tail=200
kubectl logs -n "${RELEASE_NAMESPACE}" \
  deployment/${RELEASE_NAME}-aileron-workspace-manager \
  --tail=200
```

以已登入的相同 actor 呼叫 `/api/v1/workspaces/${WORKSPACE_ID}/availability` 與
`POST /api/v1/workspaces/${WORKSPACE_ID}/browser/access`。`pending`、`not_ready` 對應
`409 BROWSER_CONNECTIVITY_NOT_READY`；具有有效 TTL 的 `degraded` 仍可核發 access；
`unavailable` 或 admission 當下 evidence 已到期對應 `503 BROWSER_CONNECTIVITY_UNAVAILABLE`。

### 2. Browser Pod backend probe

```bash
kubectl get secret -n "${RELEASE_NAMESPACE}" <turn-secret-name> \
  -o jsonpath='{.metadata.resourceVersion}{"\n"}'
kubectl logs -n "${RELEASE_NAMESPACE}" \
  --selector="aileron.io/workspace-id=${WORKSPACE_ID},aileron.io/component=workspace-browser" \
  -c connectivity-probe \
  --tail=200
kubectl get deployment -n "${RELEASE_NAMESPACE}" \
  -l "aileron.io/workspace-id=${WORKSPACE_ID},aileron.io/component=workspace-browser" \
  -o jsonpath='{range .items[0].spec.template.spec.containers[?(@.name=="connectivity-probe")].env[?(@.name=="TURN_PROBE_IDENTITY")]}{.value}{"\n"}{end}'
kubectl get ciliumnetworkpolicy -n "${RELEASE_NAMESPACE}" \
  -l "aileron.io/workspace-id=${WORKSPACE_ID}" \
  -o yaml
```

比對 `profileRevision`、`credentialRevision`、`observedAt`、`expiresAt` 與 `backendState`。
`TURN_PROBE_IDENTITY` 必須是 `backend:${WORKSPACE_ID}`；核發後的 TURN REST username 是
`${expiry}:backend:${WORKSPACE_ID}`，僅供 TURN 稽核歸屬。
`BACKEND_TURN_PATH_NOT_READY` 表示 sidecar 無法從 Browser network namespace 完成 authenticated
allocation 與 relay round trip；`BACKEND_EVIDENCE_UNAVAILABLE` 表示 sidecar evidence endpoint
不可讀。接著檢查 TURN DNS、TLS、listener、relay UDP range 與 control/relay egress rule。

### 3. Frontend external vantage

```bash
kubectl logs -n "${RELEASE_NAMESPACE}" \
  deployment/${AILERON_FULLNAME}-connectivity-evidence-gateway \
  --tail=200
kubectl get workspace -n "${RELEASE_NAMESPACE}" "${WORKSPACE_RESOURCE}" \
  -o jsonpath='{.status.browserConnectivity.frontendState}{"\n"}{.status.browserConnectivity.expiresAt}{"\n"}'
```

在 Agent 所在主機檢查 `connectivity-external-agent` log，確認 installation ID、vantage ID、Gateway
HTTPS、TURN listener 與 relay range。`FRONTEND_TURN_PATH_NOT_READY` 表示至少一個 required
vantage 沒有相符且未到期的 evidence。若 `coturn.enabled=true`，才另外檢查
`coturn.namespace` 的 Coturn DaemonSet；外部 TURN 不會建立該資源。

若 aggregate 狀態不足以定位問題，應從具備 internal token 的授權 control-plane 執行環境，針對
每個 `requiredFrontendVantages` 個別讀取
`GET /v1/evidence/{profileRevision}/{vantage}`。成功回應必須逐一核對 `vantageId`、
`profileRevision`、`credentialRevision`、`observedAt`、`expiresAt`、relay address 與成功狀態。
internal token 不得輸出到 shell history、log 或疑難排解文件。

### 4. Neko session 與前端 recovery

```bash
kubectl logs -n "${RELEASE_NAMESPACE}" \
  --selector="aileron.io/workspace-id=${WORKSPACE_ID},aileron.io/component=workspace-browser" \
  -c browser \
  --tail=200
```

Browser DevTools 依序確認 `/browser/access` 成功且回傳本次短效 `iceServers`、Neko WebSocket
upgrade、relay ICE candidate/selected pair、WebRTC `connected` 與 data channel `open`。只有前三層
都通過後，才把 timeout 視為單一 Neko generation 問題。`net::ERR_NETWORK_CHANGED` 會觸發
bounded recovery，但不能用前端重連掩蓋過期 evidence 或無法到達的 TURN path。輪替 TURN
Secret 時同步提高 `turn.credentialRevision`。

## PostgreSQL 或 Redis 效能

```bash
kubectl get pvc,pod -n workspace-system -o wide
kubectl describe pvc -n workspace-system <pvc-name>
kubectl top pod -n workspace-system
```

確認 PostgreSQL、Redis 與 Manager state 使用各自的 local RWO Retain StorageClass，Pod
落在 volume 所屬節點。local volume 的節點故障復原依賴平台備份與還原，不具共享儲存的
跨節點可攜性。

## Docker 模式

```bash
docker compose ps
docker compose logs --tail=200 workspace-manager
docker logs --tail=200 workspace-runtime-<workspace-id>
```

Docker Compose 的 Browser TURN readiness 依下列順序檢查：

```bash
docker compose ps turn-readiness-preflight coturn \
  connectivity-evidence-gateway connectivity-external-agent workspace-manager
docker compose logs --tail=200 turn-readiness-preflight
docker compose logs --tail=200 coturn connectivity-evidence-gateway connectivity-external-agent
docker compose logs --tail=200 workspace-manager
docker logs --tail=200 workspace-browser-connectivity-probe-<workspace-id>
```

`turn-readiness-preflight` 必須是 `exited (0)`；若不是，先確認
`${HOST_TURN_CONFIG_DIR}/turn-reachability-profile.json`、`${HOST_TURN_SECRETS_DIR}` 的完整
secret bundle、`WORKSPACE_OPERATOR_IMAGE`、`COTURN_IMAGE` 與 profile relay port range。不要把
secret 或 token 貼入 log；只分享檔案名稱、權限與遮蔽後的錯誤碼。

接著確認 host agent 能以 host network 連到本機 Gateway 的 `${TURN_CONNECTIVITY_GATEWAY_EXTERNAL_PORT:-18083}`，
Gateway 能讀取 Coturn 使用的同一份 TURN REST secret，且 Browser probe 使用相同的
`TURN_CREDENTIAL_REVISION`。若只有 Browser access 失敗，取得 Workspace 的
`browser_connectivity_state`、`browser_connectivity_reason`、`browser_connectivity_backend_*` 與
`browser_connectivity_frontend_*` typed 欄位；不要以重建 Browser 取代 evidence 診斷。

Docker admission 對應如下：

| 狀態 | Browser access 行為 |
| --- | --- |
| `ready` | 核發 Browser access 與短效 TURN credential |
| `degraded` 且 `expiresAt` 尚未到期 | 仍核發 access；依 frontend failure 追查 host agent／Gateway／TURN path |
| `pending`／`not_ready` | `409 BROWSER_CONNECTIVITY_NOT_READY` |
| `unavailable` 或 `expiresAt` 已到期 | `503 BROWSER_CONNECTIVITY_UNAVAILABLE` |

Runtime 測試應使用 `workspace-runtime/docker-compose.test.yml` 的 test service。Docker 模式的
volume 與 Kubernetes PVC 職責不同，但 bootstrap 順序、TURN readiness preflight 與一次性
defaults 契約相同。
