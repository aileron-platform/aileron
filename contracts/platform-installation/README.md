# Core Platform Secret 安裝契約

`secret-registry.json` 是 HomeLab core platform Secret artifact 與 Kubernetes
Secret 投影的唯一版型。Generator 與 Kubernetes apply seam 都讀取此檔，不各自維護
Secret 名稱、namespace 或 key 對應。

## 產生與重用 artifact

正式發布的 Workspace Manager image 內含 generator：

```bash
docker run --rm \
  --volume /absolute/private/output:/output \
  workspace-manager-image@sha256:IMAGE_DIGEST \
  /workspace-manager/.venv/bin/python \
  /workspace-manager/scripts/generate_platform_installation_secrets.py \
  /output \
  --values /installation-contract/core-values.json \
  --turn-url turn:turn.apps.example.tw:3478
```

輸出目錄必須是 `0700`，所有檔案必須是 `0600`。完整且有效的既有集合會原樣重用；
缺檔、多檔、內容不一致或權限過寬都會 fail closed。指令只回報成功狀態或 artifact
識別，不輸出 Secret 值。

## 投影到 Kubernetes

OIDC client secret、OIDC CA、Apps TLS certificate/key/CA 與 Harbor
dockerconfig 是安裝環境提供的外部 `0600` 檔案，不由 generator 建立。Artifact directory、generated
files 與所有 external inputs 都必須位於固定 installation private root `/root/aileron-private` 內；每層
directory 必須由執行者擁有且為 `0700`，檔案必須由執行者擁有、`0600`、link count 為一。Helper 以
stable FD 驗證 path／descriptor inode 與讀取前後 metadata；private root 外路徑、hardlink、symlink 或
讀取中的 replacement 一律 fail closed。使用
`--external-input ARTIFACT_ID=/absolute/path` 各提供一次完整集合：

```bash
python3 scripts/deploy/rke2/apply_platform_secrets.py \
  --artifact-directory /absolute/private/output \
  --values /root/aileron-private/install/FULL_GIT_SHA/release-values/core-values.json \
  --kubeconfig /root/aileron-private/install/FULL_GIT_SHA/snapshots/kubeconfig \
  --context rke \
  --external-input oidc-client-secret=/absolute/private/oidc-client-secret \
  --external-input oidc-ca=/absolute/private/oidc-ca.crt \
  --external-input apps-tls-cert=/absolute/private/tls.crt \
  --external-input apps-tls-key=/absolute/private/tls.key \
  --external-input apps-tls-ca=/absolute/private/ca.crt \
  --external-input harbor-dockerconfig=/absolute/private/dockerconfig.json
```

`--values` 內的 `postgres.enabled` 與 `redis.enabled` 是唯一模式來源。當
`postgres.enabled=false` 時，generator 不建立內建 PostgreSQL username/password/database URL，apply
額外要求 `database-url` 與 `platform-database-ca`。當 `redis.enabled=false` 時，apply 額外要求
`redis-general-url`、`redis-job-queue-url`、`redis-job-result-url` 及三份對應 CA。模式為 `true` 時，這些外部
artifact 一律禁止。外部 URL 與 credential 只存在 installation private root 與 Kubernetes Secret，不寫入
release values。

預設只執行 Kubernetes server dry-run；加入 `--apply` 才會在全部 Secret dry-run
成功後套用。執行前會驗證 current context、namespace owner label，以及所有既存
Secret 的 owner label。namespace 必須先由 installer 建立並標記
`platform.aileron.dev/namespace-owner=aileron-installer`。

`--kubeconfig` 為必填，且只能指向安裝私密根目錄內、owner 控制、`0600`、
minified 且 self-contained 的 flattened snapshot。Helper 會先以 stable FD 將輸入複製到私密根目錄內
本次唯一的 raw snapshot，再由該副本產生 minified flattened snapshot；後續每一個 `kubectl` 呼叫都只會
同時顯式帶入本次 flattened 路徑與 `--context`，原始路徑在驗證後遭替換也不能切換 cluster identity。
程序不讀取 ambient `KUBECONFIG`，也不使用
`/root/.kube/config` 或其他預設 kubeconfig。

Mutation policy 固定為 tracked `contracts/platform-installation/secret-registry.json` 的 exact digest 與
schema；CLI／API 都沒有 registry path override。Artifact ID、generated relative path、Secret target、type
與 data mapping 必須唯一且完整，duplicate target、額外欄位、未知 namespace 或 `..` path traversal 都會
在任何 Kubernetes query 前拒絕。Retained backend-attestor pull Secret 不在此 registry，也不屬於一般
application Secret transaction／rollback。
