# Identity Plane Secret 安裝契約

`generate_secrets.py` 只在 installation-owned、mode `0700` 的 `--private-root` 內建立私密
artifact；private root、output 與既有 artifact 的任一路徑元件都不得是 symbolic link。
所有檔案固定為 mode `0600` regular file，並以 no-follow 方式讀取；重複執行不會輪替既有值。Realm import 只預置
無 credential、固定 subject 的特殊平台管理員，不包含其他一般使用者。既有 realm 由 provisioning Job 讀取
`keycloak-platform-admin/import.json`，透過 idempotent partial import 補入同一 principal；此專用 payload
只含 `ifResourceExists` 與該使用者。密碼只經 CLI 環境變數設定，不寫入任何 import JSON。Provisioning Helm hook Job 會先依 core `bootstrap.admin.subject` 建立或收斂
`keycloak-platform-admin` 的可登入平台管理員，再建立 native break-glass principal。平台管理員
必須以 canonical subject 查詢，若預期 username 已屬於其他 subject 會 fail closed。Native
break-glass principal 使用
`keycloak-break-glass` Secret 中的 username、email 與 password 建立；user ID 只採用
Keycloak Admin API 建立或查詢後回傳的 canonical ID，不接受 installation artifact 指定 subject。

```sh
python3 identity-installation/generate_secrets.py \
  --private-root /private \
  --output-dir /private/aileron-identity \
  --realm aileron \
  --platform-origin https://aileron.apps.rke.soez.tw \
  --client-id aileron-frontend
```

`apply_secrets.sh` 要求目標 namespace 已標記
`platform.aileron.dev/namespace-owner=aileron-installer`，且外部 Harbor pull Secret 與 TLS
檔案皆位於指定 private root 且為 mode `0600`。套用前會拒絕任一 symlink ancestor，並以
`O_NOFOLLOW` 讀取後複製到受保護暫存目錄，後續 JSON、OpenSSL 與 kubectl 只消費安全副本。它只建立 Identity Plane 真正消費的七個 Secret，先做
server-side dry-run，再以相同 field manager apply；`--dry-run` 可只執行驗證。

```sh
sh identity-installation/apply_secrets.sh \
  --private-root /private \
  --artifact-dir /private/aileron-identity \
  --context rke2-207-homelab \
  --namespace aileron-identity-system \
  --image-pull-secret-file /private/harbor/dockerconfig.json \
  --tls-cert-file /private/tls/keycloak.crt \
  --tls-key-file /private/tls/keycloak.key \
  --dry-run
```

OIDC client Secret 與 OIDC CA 由 installation layer 使用同一 artifact／輸入，直接投影至
core platform namespace；Identity namespace 不保存沒有 consumer 的重複 Secret。

HomeLab Identity release 會建立 `aileron-identity-backup` PVC，使用
`aileron-nfs-rwx-retain` 與 `ReadWriteMany`。管理入口固定由
`keycloak-admin.apps.rke.soez.tw` 提供，Ingress 只允許 `192.168.50.0/24`；這不是公開管理
入口。

備份／還原 smoke 會在 Identity PostgreSQL 建立 sentinel、執行真實 `pg_dump` Job、刪除
sentinel、停止 Keycloak、執行真實 `pg_restore` Job並驗證 sentinel，最後清除 sentinel、重做
乾淨備份並恢復 Keycloak replicas。這是破壞性的完整資料庫還原，只能對明確 context 與
Identity release 執行，且確認值必須完全相符：

```sh
commit=0123456789abcdef0123456789abcdef01234567
chart_digest="sha256:$(git ls-tree -r "${commit}" -- helm/aileron-identity | openssl dgst -sha256 -r | awk '{print $1}')"
keycloak_image="harbor.example.test/library/platform-keycloak@sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
keycloak_runtime_image="harbor.example.test/library/platform-keycloak@sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
postgres_image="harbor.example.test/library/platform-postgres@sha256:cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc"
postgres_runtime_image="harbor.example.test/library/platform-postgres@sha256:dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd"

python3 identity-installation/backup_restore_smoke.py \
  --kubeconfig /root/aileron-private/kubeconfig \
  --context rke2-207-homelab \
  --namespace aileron-identity-system \
  --release aileron-identity \
  --commit 0123456789abcdef0123456789abcdef01234567 \
  --release-revision 7 \
  --chart-version 0.1.0 \
  --chart-digest "${chart_digest}" \
  --keycloak-image "${keycloak_image}" \
  --keycloak-runtime-image "${keycloak_runtime_image}" \
  --postgres-image "${postgres_image}" \
  --postgres-runtime-image "${postgres_runtime_image}" \
  --confirm-destructive-restore \
  "rke2-207-homelab/aileron-identity-system/aileron-identity@revision=7,chart=0.1.0,commit=${commit},chartDigest=${chart_digest},keycloakImage=${keycloak_image},keycloakRuntimeImage=${keycloak_runtime_image},postgresImage=${postgres_image},postgresRuntimeImage=${postgres_runtime_image}"
```

所有 Helm／Kubernetes API 操作都固定使用必填、絕對路徑的 `--kubeconfig` 與 `--context`，不讀取
ambient `KUBECONFIG` 或預設 context。Acceptance producer 呼叫此 smoke 時只傳入該 commit／run 的
canonical flattened snapshot。任何 mutation 前，
smoke 只會使用該 checkout 的 canonical `helm/aileron-identity`，不接受外部 chart path。它會
比對 full commit 的 Git tree hash、tracked blob inventory、chart digest、已安裝 Helm release
metadata，以及用 installed values 從 canonical chart 重建的 manifest；symlink、untracked file、
同版本但內容修改或 installed manifest drift 都會在 mutation 前失敗。之後才驗證 Helm image
values 與 signed inventory v2 提供的 OCI index／唯一 linux/amd64 runtime digest pair，並逐層驗證
Keycloak 與 PostgreSQL 的 live Deployment、active ReplicaSet、唯一 running Pod、Job owner 及實際
Pod `imageID`。Registry revision 與 index→runtime 關係由 release signer 在簽署 inventory 前重查；
smoke 本身不接受 registry 自報結果，也不需要 Docker Buildx。PostgreSQL 密碼只會寫入 Pod 內
mode `0600` 的暫時 `PGPASSFILE`，不會進入 process argv 或 environment。

Job cleanup 會在每次嘗試前重讀 live Job，取得同一 transaction 的 UID 與 `resourceVersion`，再透過
Kubernetes REST `DeleteOptions` 執行 foreground delete；不使用 kubectl 不存在的 client-side
precondition flag。API 接受 DELETE 後不會重送，而會每兩秒精確重讀 Job、controller UID Pod 與
Job name Pod，最多等待 120 秒；同 UID 與 transaction 的 terminating Job 可繼續等待，foreign
或 replacement Job 則立即失敗。Flattened kubeconfig 的父目錄同時作為最小權限 private root
與暫時 client credential 目錄，因此必須是 canonical、owner-controlled mode `0700` 目錄。
成功時 stdout 只輸出一行 canonical JSON，schema 為
`aileron-identity-backup-restore-smoke/v1`，包含依序且唯一的兩個 `backupJobUids`、
`restoreJobUid`、`restoreMarker=identity-smoke-marker` 與 `jobClosureVerified=true`。

Provider-neutral external OIDC gate 使用 Kubernetes product conformance 的非 Keycloak fixture，
實際完成 Authorization Code + PKCE、Manager callback、opaque session 與 JIT reconciliation；
結果以 `externalOidcAuthorizationCodeJit` capability 獨立記錄，Discovery／JWKS render 不算通過。
