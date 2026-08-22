---
title: RKE2 HomeLab 安裝
description: 以唯一的三階段安裝器部署及升級 RKE2 HomeLab
---

# RKE2 HomeLab 安裝

本頁只描述已驗證的 RKE2 HomeLab 正式契約。唯一頂層入口是
`scripts/deploy/rke2/install.py`；不得以手動建立 Namespace／Secret 或直接執行 Helm
取代安裝器。其他 Kubernetes provider 尚未具備相同的完整安裝與復原驗證，因此本頁不提供
推測性的通用安裝路徑。

部署前另請確認：

- [儲存設計](./kubernetes-storage.md)
- [映像建置與私有 Registry](./kubernetes-images.md)
- [網路、Ingress、TLS 與 TURN](./kubernetes-networking.md)
- [Workspace 防火牆](./kubernetes-firewall.md)
- [Helm values 參考](/reference/helm-values.md)

## 前置條件

- 使用乾淨 checkout 與完整 40 字元 Git SHA；部署與映像皆為 `linux/amd64`。
- 使用 tracked `scripts/deploy/rke2/requirements.txt` 的 hashes 建立部署 Python runtime。
  CI 會在 pinned Python 3.9／linux/amd64 stage 實際安裝同一份 production lock，執行
  `pip check`，並匯入 `jsonschema` 與 `yaml`。
- 使用 stable Helm `>=3.13.0,<4.0.0`。Preflight 會實際驗證 server-side dry-run、
  atomic upgrade、history limit 與 rollback cleanup capability。
- 固定 private root 為 `/root/aileron-private`、mode `0700`；private root、其下每一層
  installation-owned 目錄，以及所有 mode `0600` kubeconfig、inventory、TLS、CA、dockerconfig
  與其他私密輸入，都必須由安裝器的 effective UID 擁有。路徑不得含 symbolic link 或 hard link。
- Kubeconfig 的 `current-context` 必須等於命令指定 context，只能包含 inline CA 與 inline
  token，或 inline client certificate/key。`certificate-authority`、`client-certificate`、
  `client-key`、`tokenFile`、`exec`、`auth-provider` 等外部或動態引用一律拒絕。
- 所有 Aileron 映像都已推送為目標 commit 的不可變 digest，且已產生受信任的 published image
  inventory。
- 叢集的 StorageClass、Cilium、Ingress、DNS、Apps TLS、OIDC TLS、TURN 與 Registry trust
  已依 HomeLab profile 完成。Registry CA、Apps ingress CA 與 OIDC CA 是三個獨立輸入，不得
  fallback。

完整參數與 private input 路徑以 repository 中的 `scripts/deploy/rke2/INSTALL.md` 為準。

## Identity 模式

- `bundledKeycloak`：安裝器管理 bundled Keycloak，以及 `workspace-system`、
  `aileron-turn-system`、`aileron-backend-attestor-system`、`aileron-identity-system`。
- `externalOidc`：安裝器管理 `workspace-system`、`aileron-turn-system` 與
  retained `aileron-backend-attestor-system`；`aileron-identity-system` 必須不存在，外部 issuer
  必須提供標準 OIDC Discovery／JWKS。

Bundled 模式會建立用途分離的 Aileron 平台管理員、Keycloak Console 管理員與 break-glass
帳號。HomeLab 的平台管理員預設為 `admin`／`admin123`，只適用於隔離測試環境；一般 Kubernetes
安裝會產生強隨機密碼。完整角色、密碼政策與私密 artifact 位置請見
[OIDC 與 Identity Plane 安裝](./oidc.md#內建帳號與密碼)。

未來 LDAP 支援位於 Identity provider federation 邊界：LDAP 管理帳號生命週期，Keycloak 或
外部 IdP 透過 OIDC 提供應用登入，本專案只管理應用授權並保留本機緊急管理員。Installer 不會
直接綁定 LDAP protocol 或預先匯入整個 directory，因此現行 Docker／HomeLab 不啟用 LDAP
不會封死後續支援路徑。

## Retained backend attestor prerequisite

完整重建會保留 `aileron-acceptance-system` 與 `aileron-backend-attestor-system`；兩者都不是
reset target。Backend attestor Namespace 由 `aileron-installer` 擁有，PSA 固定為
`enforce=privileged`、`audit=restricted`、`warn=restricted`，且只使用固定
`harbor-rke-creds` image pull Secret。Harbor dockerconfig 必須只含命令指定的 exact registry
entry，不得把 credential 寫入 log 或 evidence。

第一次 signed pre-reset snapshot 前，先在 repository 外建立 mode `0600` canonical JSON
execution profile。Profile 固定使用 schema `aileron-backend-execution-profile/v1`，將 NFS target
限制在 pinned IPv4 與 approved mount roots，並將 local-path target 限制在 live node hostname、
node UID 與 approved mount roots；至少要提供一種 target。可由 tracked
`scripts/deploy/rke2/backend-execution-profile.example.json` 建立輸入，但所有 placeholder 與
`_comment` 都必須移除，並依 schema canonicalize 後再使用。

Dedicated preparer 預設只驗證並執行 Kubernetes server-side dry-run：

```bash
python3 scripts/deploy/rke2/prepare_backend_attestor.py \
  --kubeconfig /root/aileron-private/kubeconfig \
  --harbor-dockerconfig /root/aileron-private/harbor/dockerconfig.json \
  --execution-profile /root/aileron-private/inputs/backend-execution-profile.json \
  --context rke \
  --registry harbor.rke.soez.tw
```

Exit `78` 表示 prerequisite 尚未 Ready；此時才以完全相同參數加上 `--apply`，再重新執行上方
validate。Apply 會以 UID／resourceVersion precondition 建立或精確收斂 Namespace 與 pull Secret，
並將 profile exact bytes write-once 發布到
`/root/aileron-private/backend-attestor/execution-profile.json`。Namespace 是 durable prerequisite；
若後續 Secret 步驟失敗也不會自動刪除。既存固定 profile 內容不同、Namespace／Secret owner、UID、
PSA、type、data key 或 Registry credential 漂移時都會 fail closed。

## 唯一三階段流程

三次命令必須使用完全相同的 commit、context、Identity 選擇與完整 private inputs，包括上述
repo 外 `--execution-profile`：

```bash
python3 scripts/deploy/rke2/install.py validate <完整安裝參數>
python3 scripts/deploy/rke2/install.py prepare-cluster <完整安裝參數> --confirm-create-namespaces
python3 scripts/deploy/rke2/install.py apply <完整安裝參數>
```

### `validate`

`validate` 不持久變更 Kubernetes，也不在 stable private tree 留下 phase artifact。若目標
Namespace 不存在，安裝器會對包含 installer owner 與完整 PSA labels 的固定 manifest 執行
server-side dry-run，再以 exit `78` 要求執行 `prepare-cluster`。缺少真實 namespace scope 時，
不得把 Namespace-scoped Secret 或 Helm validation 誤報為成功。

### `prepare-cluster`

此 phase 唯一允許的持久 mutation 是 Namespace。所有 ownership、UID、resourceVersion check
與 server-side dry-run 都必須在第一個 mutation 前完成；既存 Namespace 只能由安裝器收斂其
完整 PSA profile。Exact profile 會移除所有未宣告的 `pod-security.kubernetes.io/*` label，但保留
非 PSA label。所有 server-side dry-run 完成後、第一個 mutation 前會重新讀取完整 target inventory；
原先 absent target 或 external OIDC 禁止的 Identity Namespace 新出現時，維持零 mutation 並停止。
Mutation 後必須重新查詢並確認：

- Namespace UID 未替換。
- Owner 與 exact PSA labels 相符。
- `status.phase` 精確等於 `Active`。
- `metadata.deletionTimestamp` 不存在。

任何 allowlisted target 或 external OIDC 模式下殘留的 Identity Namespace 正在 Terminating
時，都必須 fail closed。此 phase 不得建立 Secret、Helm release 或 application data。

### `apply`

`apply` 先完成相同 validation。Identity／Core Secret dry-run、Helm server-side dry-run 與完整
core preflight 全部通過後，才可進入 Secret transaction。第一個 Secret mutation 前會再次驗證
所有 Namespace 的 UID、owner、PSA、`Active` phase 與 deletion timestamp；任何 replacement、
drift 或 termination 都在零 Secret／release mutation 下停止。

Namespace 是 transaction 之外的 durable prerequisite。後續部署或復原失敗不會自動刪除已安全
建立的 Namespace。

## 全域鎖與 private input snapshot

安裝器直接對自身 effective UID 擁有、mode `0700` 的 private root directory file descriptor 取得 non-blocking flock，並
驗證 path 與 descriptor 的 device／inode；不建立 `installation.lock` 或其他穩定 lock artifact。
因此首次 `validate`／`prepare-cluster` 即使遇到 contention，也不會污染 stable private tree。

每個外部檔案與其 private parent directories 都必須由相同 effective UID 擁有。檔案以同一個
`O_NOFOLLOW` descriptor 執行 `fstat → read → fstat`，接著以
`O_EXCL` 建立 mode `0600` snapshot，並 fsync 檔案與目錄。Snapshot 後不再讀取原始路徑；原始
檔案被替換也不會改變本 phase 使用的內容。`validate` 與 `prepare-cluster` 使用會自動清除的
private phase directory；`apply` 使用 commit-scoped write-once snapshots，重試時內容不一致即
停止。

Kubeconfig 先保存 raw snapshot，再以該 raw snapshot 與原始 context 執行
`kubectl config view --raw --flatten --minify`，輸出第二份 mode `0600` snapshot。Flatten 前後的
API server 與 CA 必須相同；cluster UID 與所有後續 Kubernetes／Helm 命令都固定使用 flattened
snapshot，不會再次讀取原 kubeconfig。

## Secret 與 release transaction

安裝器依 Identity mode 與 canonical Secret registry 展開 exact allowlist。Mutation 前會記錄每個
Secret 的 `existing`／`absent` pre-state；既存 Secret 的完整 JSON 只保存在 mode `0600` private
snapshot，inventory 不包含 Secret value。失敗時只復原 allowlist 內的項目，且所有 replace／delete
都以 UID 與 resourceVersion precondition fail closed。

Core preflight 會驗證映像、TLS、Namespace、網路安全、Helm capability、DaemonSet 與
Deployment／StatefulSet／Job capacity，以及新 Workspace 的 Runtime／Browser／Canvas capacity。
通過後才安裝或升級 Identity，再驗 OIDC readiness，最後重新執行 live Core preflight 並部署 Core。
Core rollback、Secret restore 或 Identity recovery 任一步不可信時，不得宣告部署成功。

## 驗收

Pod Ready、PVC Bound 與 Helm `deployed` 只屬最小健康訊號，不是完整部署證據。完整驗收唯一
信任 `scripts/deploy/rke2/deployment-acceptance-contract.json` 與 code-owned digest，且必須從正常
OIDC API／UI 流程建立新的 `oidcWorkspace`。

驗收依因果 DAG 證明 signed 11-image release 集合、clean reset、Identity／OIDC、Runtime、Terminal、
Browser、Canvas、WebSocket、TURN、Workspace lifecycle、component restart 與 soak；live workload
實際使用的映像必須另以 Pod `imageID` 證據核對，`imageRelease` 本身不宣稱 live rollout attestation。所有 private
input、raw report、bundle 與 sidecar 都必須留在 code-owned mode `0700` 目錄內，檔案為 mode
`0600`；Secret、token、密碼與私鑰不得寫入 Git、report 或 log。

目前 v8 因果順序固定為：signed image inventory → `cleanReset --reset-phase pre-reset` snapshot／epoch →
non-mutating `suites` 與 `offlineOidcConformance`（可平行）→ reset → signed post-reset `cleanReset` report →
top-level `install.py` 三階段 → `imageRelease` → bundled 模式的 `identity` → `oidcWorkspace` → 其餘
Workspace reports。Reset executor 在讀取 signed backend inputs 或執行任何 mutation 前，會以同一
commit／run／context／trust 驗證兩份 root report的 canonical JSON、HMAC、source與 observation，並把 digest／
`finishedAt` 綁入 execution state；resume漂移會停止。每個 active 非 root producer 都直接從 v8 `causalEdges`
計算目前 authentication mode 的 immediate predecessors，並在自己的 side effect 前以同一個 canonical／HMAC／
identity／source／observation／freshness validator 全部驗證；Workspace predecessor 另須完全符合目前的
Workspace ID／subject。既有 `cleanReset` 重跑與 final bundle 也重用同一 validator。

每個 producer 先以完整 commit 與 deployment run ID 導出唯一
`/root/aileron-private/evidence/<完整 SHA>/<deployment run ID>/`，在任何 trust／cluster query 前將
CLI 提供的 kubeconfig write-once 保存為 `kubeconfig.raw`，再以明確
`kubectl --kubeconfig <raw snapshot> --context <context> config view --raw --flatten --minify --output=json`
建立 `kubeconfig`。Raw／flattened selected identity digest 必須相同；中斷重跑只接受兩份 exact
bytes。來源替換、identity drift 或既有 snapshot 不一致都會在 trust query 前停止。之後的 reset
inventory collector、backend attestor、Job、restart、browser lifecycle、kubectl 與 Helm 全部只使用
該 flattened path，且每個命令明確指定 kubeconfig 與 context。

Bundle 與 final validator 不接受 `--kubeconfig`，只從相同 commit／run directory 讀取上述 canonical
raw／flattened pair；bundle 發布後的第二次 validation 也使用完全相同的 flattened path：

```bash
python3 scripts/deploy/rke2/acceptance_bundle.py \
  --expected-commit "$FULL_GIT_SHA" \
  --deployment-run-id "$DEPLOYMENT_RUN_ID" \
  --context rke
python3 scripts/deploy/rke2/acceptance_evidence.py \
  --expected-commit "$FULL_GIT_SHA" \
  --deployment-run-id "$DEPLOYMENT_RUN_ID" \
  --context rke
```

### Tracked OIDC Browser 驗收

唯一 active Workspace 驗收流程由 `scripts/deploy/rke2/acceptance_producer.py` 固定執行 tracked
`frontend/e2e/homelab-acceptance.mjs`。Producer 必須證明 checkout clean、HEAD 等於完整驗收 commit，
且 probe bytes 等於該 commit 的 Git object，再以完整 SHA 建置並依 image ID 執行 Playwright image。
`oidcWorkspace` 會走真實 OIDC Authorization Code／PKCE 登入並建立 Workspace；Frontend 完成 callback
後只使用 opaque Manager session，所有 authenticated mutation 都帶同一 session 取得的 memory-only
CSRF token 與正確 `Origin`。

`terminal`、`http`、`websocket` 與 `browser` 會以該 Workspace 與 OIDC session 驗證正式 Gateway、
execution grant、protocol round-trip 與 Browser UI。Workspace-scoped `turn` attestor 驗證真實 TURN relay；
上述報告全部成功後，`workspaceLifecycle` 才以同一 session／CSRF 依序執行 component restart、stop、
Stopped observation、start 與 Running／Ready observation。這組 tracked OIDC Browser probes 與 TURN
attestor 是 active lifecycle 驗收的唯一入口，其 causal order 由
`scripts/deploy/rke2/deployment-acceptance-contract.json` 固定。

### Bundled Keycloak browser input

目前不含 LDAP 的 bundled Keycloak HomeLab 使用 `--use-break-glass-login`，由固定的 installation-owned
Keycloak bootstrap administrator 與 break-glass credential sources 產生 Browser 驗收 input：

```bash
python3 scripts/deploy/rke2/prepare_browser_input.py \
  --expected-commit "$FULL_GIT_SHA" \
  --deployment-run-id "$DEPLOYMENT_RUN_ID" \
  --use-break-glass-login
```

輸出固定為
`/root/aileron-private/acceptance-inputs/<full SHA>/<deployment run ID>/browser-input.json`，是 mode
`0600` write-once canonical JSON；CLI 不提供任意 output path。Keycloak 啟用 LDAP federation 時，使用
完整的一對 private login credential files，且不搭配 `--use-break-glass-login`：

```bash
python3 scripts/deploy/rke2/prepare_browser_input.py \
  --expected-commit "$FULL_GIT_SHA" \
  --deployment-run-id "$DEPLOYMENT_RUN_ID" \
  --login-username-file "$LOGIN_USERNAME_FILE" \
  --login-password-file "$LOGIN_PASSWORD_FILE"
```

兩個 login files 都必須位於 owner-only private tree，且通過 regular-file、owner、mode、symlink 與
hardlink 檢查。LDAP 管理帳號生命週期，Keycloak 負責 federation 與 OIDC authentication；Aileron 仍以
相同 OIDC／JIT provisioning／應用授權 seam 接收使用者，並保留本機 break-glass administrator。

Epoch、reset snapshot、report 與 bundle 都必須是 strict UTF-8、所有層級不得有 duplicate JSON key，
且 raw bytes 必須精確等於 sorted compact canonical JSON 加單一換行。重新排欄位、調整空白、移除
結尾換行或以 duplicate key 製造語意相同文件，一律不得通過簽章與 write-once evidence gate；tracked
acceptance contract 仍由 code-owned digest 綁定格式，但 parser 同樣拒絕 duplicate key。

Clean reset snapshot 會將 exact PV name／UID／backend locator digest 綁定上述 execution profile、
retained Namespace／pull Secret UID 與 signed image inventory。Reset executor 只有在三個 resettable
Namespace、Workspace、PVC 與 target PV 已由權威 live inventory 證明不存在後，才可逐 target 執行
backend cleanup；每個 target 都先寫入可續跑 journal，再將 canonical aggregate write-once 發布到
`/root/aileron-private/reset/<commit>/<run-id>/backend-cleanup-results.json`。Journal 已完成時，aggregate
缺少、非 canonical 或 digest 不符都會停止，不會從 journal 重建檔案。

Post-reset producer 只接受相同 commit、run ID 與人工核准的 snapshot SHA-256。它先驗證 signed
cleanup aggregate，再以 read-only mount 的獨立 attestor Jobs 重驗每個 backend path 不存在；producer
沒有 cleanup surface，也不信任 aggregate 自報的 `allAbsent`。任何 target identity、execution resource、
image、Job provenance 或 live Kubernetes absence 漂移都會 fail closed。

## 升級與復原

升級同樣重新執行 `validate → prepare-cluster → apply`，並提供新的 full SHA 與 signed image
inventory；不得直接執行 Helm upgrade。復原由 installer 的 Secret／Core／Identity transaction
契約處理，不得以手動 Helm rollback 取代。資料庫、CRD 或 PVC 契約需要復原時，必須搭配相符的
資料 snapshot、CRD 與 image digest，並重新完成整套驗收。
