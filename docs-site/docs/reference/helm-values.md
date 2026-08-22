---
title: Helm Values 參考
description: Aileron Kubernetes production values 分組索引
---

# Helm Values 參考

本頁列出 production 部署的主要設定。完整預設值以 `helm/aileron/values.yaml` 為準；正式
profile 對必填欄位採 fail-closed，不會從 global 設定推測持久化用途。

## Global 與安全

| Key | 用途 |
| --- | --- |
| `global.imagePullSecrets` | 選填；各 workload namespace 內既有的同名 Registry Secrets；built-in Coturn 使用獨立 namespace |
| `security.requireStrongSecrets` | 啟用 production hardening：HTTPS、Ingress、不可變 image digest 與明確 StorageClass |
| `platformSecrets.existingSecretName` | Manager 與 PostgreSQL 共用的既有平台 Secret 名稱 |
| `platformSecrets.databaseUrlKey` | Manager 完整 PostgreSQL DSN 的 Secret key |
| `platformSecrets.runtimeDatabaseCredentialKey` | Manager-only Runtime instance credential HMAC key 的 Secret key |
| `platformSecrets.postgresUsernameKey`／`platformSecrets.postgresPasswordKey` | 內建 PostgreSQL identity 的 Secret keys |
| `runtimeAssertions.*` | 既有 assertion signer/JWKS Secret references |
| `browserCredentials.*` | Runtime namespace 內既有 Browser keyring Secret、key 與 rotation revision |

## 身分驗證

| Key | 用途 |
| --- | --- |
| `platformPublicOrigin` | 唯一精確平台公開 Origin；callback、logout、CORS 與所有瀏覽器公開路徑皆由此衍生 |
| `oidc.issuerUrl` | 外部 provider 的 canonical HTTPS issuer；必填 |
| `oidc.clientId` | Manager confidential OIDC client ID |
| `oidc.clientSecretName`／`oidc.clientSecretKey` | Manager-only 既存 client Secret reference |
| `oidc.caSecretName`／`oidc.caSecretKey` | optional Manager-only provider CA Secret reference |
| `bootstrap.admin.*` | 以 issuer + subject 建立本地平台管理員快照；credential 仍由 OIDC provider 擁有 |

Chart 不部署或管理 IdP，也不把 OIDC 設定注入 Runtime、Terminal 或 Operator。Frontend
只透過 Manager BFF session 登入。安裝方式見[外部 OIDC 安裝](../installation/oidc.md)。

## Storage

| Key | 用途 |
| --- | --- |
| `kubernetes.workspaceData.storageClassName` | 三元件共享 working tree RWX/Delete class |
| `kubernetes.runtimeHome.storageClassName` | Runtime HOME 專用 Delete class |
| `kubernetes.runtimeHome.accessMode` | 單一 `ReadWriteOnce`（預設）或 `ReadWriteMany` |
| `kubernetes.knowledgeBases.storageClassName` | canonical KB RWX/Retain class |
| `kubernetes.managerState.storageClassName` | Manager state RWO/Retain class |
| `postgres.persistence.storageClassName` | PostgreSQL RWO/Retain class |
| `redis.persistence.storageClassName` | Redis RWO/Retain class |
| `kubernetes.platformStorageGid` | 採固定 POSIX GID profile 時的共用 storage GID |
| `kubernetes.storageVerification.workspaceStorageClassName` | Workspace RWX 專用、可拋棄的 Delete class |
| `kubernetes.storageVerification.managerStateStorageClassName` | Manager state RWO 專用、可拋棄的 Delete class |
| `kubernetes.storageVerification.workspaceSize` | Workspace RWX probe 容量；正值 Kubernetes quantity，預設 `1Gi` |
| `kubernetes.storageVerification.managerStateSize` | Manager state RWO probe 容量；正值 Kubernetes quantity，預設 `1Gi` |

兩種 probe 容量可依雲端 storage tier 的最低容量分別設定，不會改變正式 PVC 容量。
verification class 必須與 production class 不同且使用 `reclaimPolicy: Delete`。
`helm/aileron/tests/values/platform-*.yaml` 僅為 Helm render contract fixtures；它們不會建立
provider StorageClass，也不是 EKS、GKE、AKS、OCP、RKE2 或原生 Kubernetes 的認證證據。

## Images

| Key | 用途 |
| --- | --- |
| `frontend.image.*` | Frontend image |
| `workspaceManager.image.*` | Manager Kubernetes image |
| `workspaceOperator.image.*` | Operator image |
| `workspaceOperator.runtimeImage.*` | Runtime Kubernetes image |
| `kubernetes.browserImage.*` | Browser Kubernetes image |
| `kubernetes.canvasImage.*` | Canvas Kubernetes image |
| `postgres.image.*` | PostgreSQL platform image |
| `redis.image.*` | Redis platform image |

每個 image object 都提供 `repository`、`digest` 與 `tag`。正式環境填入
`digest: sha256:...` 並保持 `tag: ""`，Chart 只會 render
`repository@sha256:...`；preflight 另驗證 manifest 是目標架構。

## Routing

| Key | 用途 |
| --- | --- |
| `platformPublicOrigin` | Frontend、Manager API、OAuth、Runtime、Browser、Canvas 與 WebSocket 共用的 Origin |
| `ingress.enabled` | 固定平台 Ingress |
| `ingress.className` | 選填的 `spec.ingressClassName` |
| `ingress.useDefaultClass` | 明確接受叢集 default IngressClass |
| `ingress.tlsMode` | `disabled`、`kubernetesSecret` 或 `controllerManaged` |
| `ingress.tlsSecretName` | Runtime namespace 內既有 TLS Secret |
| `ingress.annotations` | 單一平台 Ingress 的 provider annotations |
| `cilium.enabled` | Workspace network policy |

`ingress.enabled` 預設關閉，避免 generic values 在雲端意外建立公開 Load Balancer。正式 profile 必須明確選擇 Ingress controller 與 TLS 模式。Frontend gateway 透過 `/workspaces/{uuid}/runtime|browser|canvas` 固定路徑連到叢集內部 Service；不建立 Workspace 公開 host。

## Firewall

| Key | 用途 |
| --- | --- |
| `firewall.seed.workspace` | 新 Workspace 的 Runtime/Canvas 初始設定 |
| `firewall.seed.browser` | 新 Workspace 的 Browser 初始設定 |
| `*.egressMode` | `blocked`、`allowlist` 或 `unrestricted` |
| `*.allowedDomains` | `allowlist` 模式建立時寫入 DB 的 exact hostname；其他模式必須為空 |

seed 只初始化新 Workspace，既有 Workspace 不會在 Helm upgrade 後被覆寫。

## TURN

| Key | 用途 |
| --- | --- |
| `turn.enabled` | 啟用 TURN |
| `turn.existingSecretName` | Runtime namespace 內既有的 Browser ICE 與 TURN REST shared-secret Secret |
| `turn.backendIceServersKey` | backend ICE JSON key |
| `turn.frontendIceServersKey` | frontend ICE JSON key |
| `turn.credentialRevision` | Secret rotation revision |
| `turn.profile.policyBackend` | `cilium`、`kubernetes` 或 `unenforced` |
| `turn.profile.backend` | Browser Pod 使用的 URL、control/relay destination 與 relay port range |
| `turn.profile.frontend.urls` | required external vantage 使用的公開 TURN URL |
| `turn.profile.credentialIssuer` | 固定使用 `turnRest`；定義 Secret ref 與短效 credential TTL |
| `turn.profile.evidence` | probe interval、evidence TTL 與 required frontend vantages |
| `coturn.enabled` | 部署內建 Coturn；關閉時由外部 TURN 滿足同一 profile |
| `coturn.frontendHost` | 內建模式的公開 TURN DNS template |
| `coturn.image` | 內建 Coturn image reference |
| `coturn.namespace` | 內建 Coturn namespace；使用 private image 時須有與 `global.imagePullSecrets` 同名的 Secret |
| `connectivityEvidenceGateway.*` | Gateway installation identity、公開 host、probe identity 與 agent enrollment 設定 |
| `connectivityEvidenceGateway.hostAgent.*` | 本機開發或明確分類單站環境的 host-network vantage；私有 CA 由 `tls.caSecretName`／`tls.caSecretKey` 掛載；預設關閉 |

內建 Coturn credential、外部 TURN 的 Browser／probe ICE JSON、Gateway internal token 與每個
vantage token 都必須由 namespace-scoped existing Secret 提供。`turnRest` ICE JSON 只含 URL；
Manager access 與 Browser sidecar 在使用時核發短效 credential。Registry Secret 是另一個
namespace-scoped 契約。

## Canvas 正式發佈

Canvas publishing 不是 Aileron Helm 的全域 values。它是 Workspace 的可選 Skill；
GitLab API、Argo CD API、OCI registry 與固定 image digest 由 Workspace 的
`AILERON_PUBLISH_*` 環境變數提供。請參考 [Canvas 發佈管理員設定](/installation/canvas-publishing-admin)。

## Workspace bootstrap 與生命週期

Workspace CR 以 bootstrap revision/status 與 Runtime、Browser、Canvas 各自的
desired/observed revision 表達狀態。Runtime bootstrap 順序固定為 Git、agent defaults、
custom setup、supervisor；Browser/Canvas 只在首次 bootstrap 成功後解除 gate。

agent defaults 由 Runtime image 的 `/opt/aileron/agent-defaults` 一次性植入 Codex、Claude
與 OpenCode 各自的 Client User Scope（`${CODEX_HOME:-$HOME/.codex}/skills`、
`${CLAUDE_CONFIG_DIR:-$HOME/.claude}/skills`、`$HOME/.config/opencode/skills`），三個
Target Client 各自持有獨立副本，不使用 symbolic link；marker 位於
`${HOME}/.local/state/aileron/bootstrap`。Pod restart 或 image upgrade 不覆寫使用者修改，
也不補回使用者刪除內容。
custom setup 由 Runtime non-root UID 執行，有 timeout、輸出上限與穩定錯誤狀態。

## Workspace storage 與 observability

`kubernetes.workspaceData.size` 與 `kubernetes.runtimeHome.size` 決定新 Workspace 兩個 PVC 的初始 desired capacity；既有 PVC 不因調小 values 而縮容。Workspace CRD 的 `spec.storage` 使用 integer bytes，Operator 在唯一 adapter 轉成 Kubernetes quantity。平台 `TZ` 影響統計 daily bucket，Runtime 以固定週期回報實際使用量。
