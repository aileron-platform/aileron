# RKE2 HomeLab 部署介面

RKE2 HomeLab 對操作者只公開一個生命週期介面：`stage`、`apply`、`status`。Release preparation、
clean reset、Identity/Core 安裝與完整 acceptance 都是這個介面後方的 code-owned implementation；
操作者不自行排列底層命令，也不直接選擇 private state、evidence 或 transaction path。

## 執行環境

Deployment host 使用 Python 3.9 與 hashed lock：

```bash
python3 -m venv /root/aileron-private/python
/root/aileron-private/python/bin/python -m pip install --disable-pip-version-check --require-hashes --requirement scripts/deploy/rke2/requirements.txt
```

同一個 clean checkout 必須包含 Git、Docker Engine、Docker Compose／Buildx、`kubectl`、Helm 與可連線的
RKE2 kubeconfig。建置與測試 runner 固定為 `linux/amd64`；來源 `HEAD` 必須等於本次 full SHA，tracked 與
untracked 狀態都必須為空。

## Deployment profile

Profile 必須符合 `contracts/homelab-deployment/homelab-profile.schema.json`。可從
`contracts/homelab-deployment/homelab-profile.example.json` 建立 installation-owned、mode `0600` 的實際
profile。它包含：

- `installationIntent: newInstallation`。
- 精確 kubeconfig context、Registry host/project、Platform HTTPS origin 與 TURN URL。
- `bundledKeycloak` 或 `externalOidc`，兩者互斥。
- acceptance `breakGlass` 或 private credential files；external OIDC 必須使用 files。
- kubeconfig、backend execution profile、Harbor docker config、Registry CA、Apps TLS/CA、OIDC CA，以及
  mode-specific Identity TLS 或 external client Secret。
- 可選的 Core／Identity data-service values overlay。兩份 overlay 都只能覆寫資料服務欄位，且
  PostgreSQL 模式只由各 chart 的 `postgres.enabled` 決定；Core Redis 模式只由 `redis.enabled` 決定。
- Core 外部 PostgreSQL 的 database URL／CA、三類外部 Redis URL／CA，以及 bundled Keycloak 使用外部
  PostgreSQL 時的 username／password／CA，均以獨立 `0600` private input 提供。values 僅保存 Secret
  reference、CA reference 與 revision，不保存 credential。

Registry CA、Apps CA 與 OIDC CA 是不同角色。相同公開 CA 可以在 deterministic bundle 中去重，但 profile
不可用一個欄位取代另一個角色。未來 LDAP 只透過 Keycloak User Federation 接入；profile、Aileron OIDC
interface、JIT 與授權模型都不加入 LDAP 設定。

追蹤的範例 overlay 為 `helm/values-rke2-207-homelab-external-data-services.yaml` 與
`helm/values-rke2-207-homelab-identity-external-data-services.yaml`。Profile 的
`coreDataServiceValues`／`identityDataServiceValues` 指向安裝者私密根目錄內經審核的副本；對應 external
input 必須完整成組，且實際要求或禁止由 snapshot 後的 rendered values 判定。未提供 overlay 時使用 release
contract 的 bundled data-service values。

## 唯一操作流程

```bash
python3 scripts/deploy/rke2/homelab.py stage --profile /root/aileron-private/homelab-profile.json --commit "$FULL_GIT_SHA"
python3 scripts/deploy/rke2/homelab.py apply --run-id "$RUN_ID" --approve-digest "$REQUIRED_DIGEST"
python3 scripts/deploy/rke2/homelab.py status --run-id "$RUN_ID"
```

`stage` 只驗證並固定 source、profile、全部 private inputs、typed plan 與 journal；它不執行 Kubernetes mutation。
輸出的 `approvalDigest` 是第一次 `apply` 的精確核准值。

`apply` 在 installation-wide execution lock 下依序執行：

1. `newInstallation`：建立或完整讀回 installation identity v3 與 immutable acceptance trust。
2. `releasePreparation`：建置／重用精確 11 個 immutable `linux/amd64` images，產生
   `component／revision／platform／tagged image／OCI index immutable image／runtime immutable image` 六欄
   inventory。Signer 只接受 profile 固定的 exact Registry／project 與 installation-owned、mode `0600` Docker
   config；簽署前會重新讀取全部 remote Buildx documents，驗證 name、revision、OCI index 與唯一
   `linux/amd64` runtime pair。
3. `reset`：固定 pre-reset snapshot 與 causal-root reports，回傳新的 `requiredApprovalDigest`；只有再次核准該
   snapshot digest 才會刪除 snapshot 內的 exact resources/data。
4. `install`：validation、必要 Namespace preparation、再次 validation、Identity/Core/TURN apply 與 recovery。
5. `acceptance`：image、OIDC、Workspace、Terminal、HTTP、Browser、WebSocket、TURN、lifecycle、restart、
   以monotonic clock量測的1800秒read-only soak，以及mode-specific terminal report與final signed bundle。Soak固定
   每60秒取樣、最大gap 75秒且至少31 samples；每個sample的canonical query raw source都綁定attempt／sequence／
   query identity，並由validator重算active controller、Pod／container、Workspace、Service與Browser drift。Workspace root與
   固定controller不得有owner；target controller／RS／Pod／Service只接受唯一六欄canonical owner，Browser兩份query必須
   exact綁定同一Pod。Inactive／unknown owner不得留下產品Pod。

任何 step 中斷後都只從 durable journal 與已驗證的 canonical evidence 向前續跑。對可能已完成 mutation、
但缺少可信 report 的 ambiguous 狀態會 fail closed，不會自動重做 Workspace create、restart 或停用登入。
Identity、Backend 與 Oracle 的短期 Job 以 transaction token、create response UID、UID／resourceVersion delete
precondition 與 bounded reconcile 收斂 create／delete 的不確定結果；foreign 或 replacement object 不會被刪除，
完成前必須證明 Job 及 controller-UID／job-name Pod inventory 都不存在。Identity smoke、Backend、Oracle 與 soak
只消費同一份 signed index/runtime pair，不自行查 Registry 或接受第三個 digest。
Identity smoke 完成兩次 backup 與一次 restore，且三個短期 Job 全部閉包後，才輸出單行 canonical transaction
report；producer 將它寫入 commit／run-bound restore marker，in-cluster oracle 驗證該 durable marker，不再查詢依
契約已刪除的暫時 Job。Job delete 由 Kubernetes REST `DeleteOptions.preconditions` 執行，不使用 kubectl
client-side 模擬參數；API接受後不重送，改以2秒間隔、最多120秒驗證Job與兩種Pod inventory均已閉包。

`status` 只讀 journal，不執行 probe 或 mutation。每次續跑都使用目前輸出的
`requiredApprovalDigest`；不得重用已消費的 plan digest，也不得猜測 reset snapshot digest。

## 完成定義

只有 journal `phase=succeeded`，且 acceptance bundle 經 final validator 通過，才代表本次 deployment 完成。
Helm `deployed`、Pod Ready、OIDC discovery 200 或單一 Workspace 可啟動都只是中間訊號。Live HomeLab 的
實際刪除、安裝與monotonic 1800秒soak必須另有本次run的exact-SHA evidence，不能由本機container tests替代。
