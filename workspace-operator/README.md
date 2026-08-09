# workspace-operator

`workspace-operator`是`platform.aileron.io/v1alpha1` `Workspace`自訂資源的
Kubernetes controller。Manager負責持久化生命週期命令、授權、revision與job；
Operator只觀察Workspace CR，將desired state收斂成同一namespace內的Kubernetes資源，
不另行決定使用者權限。

## 現行範圍

- 以`POD_NAMESPACE`限制controller-runtime cache，使用namespaced
  `Role`／`RoleBinding`管理同一個`workspaceRuntimeNamespace`內的資源。
- `contracts/controller-dependencies/registry.json`是Controller Kubernetes API依賴的唯一
  權威來源。每個依賴都宣告resource、scope、typed object、存取模式、verbs、啟用條件與
  event mapper或direct lookup probe；Go wiring與Helm RBAC均由這份registry產生或衍生。
- 啟動時會先形成完整enabled dependency set，逐一驗證GVK discovery、resource scope、
  direct lookup與informer wiring。Manager cache同步全部成功後才啟動Workspace controller；
  任一依賴失敗時不提供partial controller mode，`readyz`維持失敗。
- 管理Workspace finalizer、每個Workspace的RWX PVC，以及Runtime、Browser、Canvas
  三個Deployment與Service；Terminal與agent共置於Runtime workload，
  因此是三個受管workload、四個邏輯元件。
- Operator不建立每個Workspace的公開Ingress或hostname。Runtime、Browser、Canvas與
  WebSocket的公開位置由Manager投影為Platform Public Origin下的same-origin path。
- 在啟用Cilium時收斂Workspace、Runtime peer與Browser的
  `CiliumNetworkPolicy`。每個top-level Rule都包含delivery marker；每個節點上的
  firewall attestor只從本機Cilium agent Unix socket讀取`policy.realized`，
  並以Pod UID、CiliumEndpoint UID／endpoint ID、policy UID／generation、
  revision、delivery ID、agent incarnation與時效性產生精確證據。Operator必須取得
  所有selected endpoint × matching policy證據才回寫`status.firewall.phase=Applied`；
  停用Cilium時則清除對應policy。
- 以`spec.runtime.instanceId`、`spec.runtime.mountRevision`與
  `spec.runtime.accessRevision`標記不可變component generation。三個Deployment均使用
  `Recreate`；desired revision改變時，先把舊workload縮為零並確認舊Pod消失，再建立
  新generation。
- 只在Runtime Deployment掛載Knowledge Base。每個attachment使用canonical UUID
  作為共享KB PVC的`subPath`，以alias掛到`/knowledge/{alias}`，且
  `readOnly: true`固定為唯讀；Browser與Canvas不掛載KB。
- 將Manager指定的public JWKS Secret掛入Runtime，用於驗證instance-bound的
  Runtime access、drain與Browser pairing assertion。Operator不持有Manager私鑰。
- 回寫`status.observedGeneration`、`status.components.runtime`的mount／access
  observed revision，以及`status.components.runtime`、
  `status.components.browser`、`status.components.canvas`的control-plane phase、Ready與
  Pod UID；status不包含internal或public URL。
- 刪除Workspace時清理受管Deployment、Service、PVC與Cilium policy，
  完成後才移除finalizer。

Operator不執行attachment授權、durable job dispatch、drain assertion簽發或Manager
資料庫交易；這些責任都在Workspace Manager。完整契約請參考
`docs-site/docs/features/workspace-lifecycle.md`、
`docs-site/docs/features/knowledge-base/permissions.md`與
`docs-site/docs/installation/kubernetes.md`。

firewall attestor 的Cilium agent socket是高信任能力。Helm只將單一
`/var/run/cilium/cilium.sock`以唯讀`hostPath.type=Socket`掛入、程式只送出
endpoint API `GET`，並使用獨立namespaced ServiceAccount／Role、唯讀root
filesystem、`RuntimeDefault` seccomp與drop all capabilities。因socket本身的權限，
attestor container明確以UID 0執行；唯讀mount只限制filesystem寫入，不能限制socket
API verb，因此不得把這個socket掛入任何Workspace workload。

## Namespace 與部署前提

Helm release namespace、Manager、Operator、Workspace CR、共享Workspace／KB PVC與
`kubernetes.workspaceRuntimeNamespace`必須一致；目前預設為`workspace-system`，
RKE2 profile使用`aileron`。release namespace不一致時chart會fail closed。

Operator的namespaced權限只存在於上述runtime namespace的`Role`。只有設定
`kubernetes.workspaceData.storageClassName`或
`kubernetes.runtimeHome.storageClassName`時，Chart才建立僅含StorageClass `get`的
`ClusterRole`／`ClusterRoleBinding`；停用Cilium時，其API依賴與權限也會同時排除。
Mutation verbs由canonical contract對generated RBAC的container tests證明，不以實際
create、update或delete probe驗證。

安裝前必須預建Manager Ed25519 private-key Secret，以及包含相符public key與
`activeKid`的JWKS Secret。Manager會在金鑰缺少或不相符時fail closed。

目前已對EKS、GKE、AKS、OCP、RKE2與原生Kubernetes六份Helm profile完成
render／security assertions，並通過arbitrary-UID container preflight；這代表chart
與部署契約相容，不等同已在六種真實平台完成conformance certification。各平台仍需
以實際RWX storage、ingress、網路與安全策略執行release conformance。

## Container 測試

所有測試都從repository root以container執行：

```bash
docker compose -f workspace-operator/docker-compose.test.yml \
  run --build --rm workspace-operator-test
```

清理測試資源：

```bash
docker compose -f workspace-operator/docker-compose.test.yml \
  down -v --remove-orphans
```
