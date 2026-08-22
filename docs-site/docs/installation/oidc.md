---
title: OIDC 與 Identity Plane 安裝
---

# OIDC 與 Identity Plane 安裝

Aileron Core 只依賴標準 OpenID Connect。安裝時必須且只能選擇一種 Identity adapter：

- `bundledKeycloak`：產品提供的預設 Keycloak Identity Plane。
- `externalOidc`：部署者提供的 OIDC provider。

兩種模式都只向 Workspace Manager 交付 issuer、client ID、client Secret reference 與 CA
reference。Frontend、Runtime、Terminal 與 Operator 不取得 provider token、Keycloak 管理介面或
LDAP 設定。

## Bundled Keycloak

Kubernetes 使用獨立的 `helm/aileron-identity` chart。Identity Plane 有自己的 Helm release、
namespace、PostgreSQL、PVC、Secret、Ingress 與備份生命週期；它不是 `helm/aileron` subchart，
也不與平台 PostgreSQL 共用資料。Installer 先建立並驗證 namespace 與既存 Secrets，再安裝
Identity Plane；Discovery 與 JWKS Ready 後才安裝 Aileron release。

Identity Plane 的 PostgreSQL 來源由 Identity chart 自己的 `postgres.enabled` 決定，與
`bundledKeycloak`／`externalOidc` adapter 選擇無關。使用外部身分資料庫時，Keycloak、preflight、
backup 與 restore 都依[外部資料服務](./external-data-services.md)使用同一連線與 TLS 契約。

Identity chart 不建立 Namespace 或 Secret，也不接受明文 credential。所有工作負載只掛載既存
Secret files；Keycloak 與 PostgreSQL images 必須使用 immutable digest。`identity-installation/
generate_secrets.py` 可在外部 mode `0700` 目錄建立或驗證所需 artifacts，檔案固定為 mode
`0600`，且不會輸出 Secret value。

Keycloak Admin Console administrator、Keycloak native break-glass principal 與 Aileron
bootstrap admin principal 是三個不同責任。Admin Console 管理 realm 與 native users；native
break-glass principal 仍使用標準 OIDC 登入；Aileron 平台角色只依 `(issuer, subject)` 決定。
Self-registration 預設關閉。

### 內建帳號與密碼

Bundled Keycloak 會建立三個用途不同的帳號。帳號名稱含有 `admin` 不代表它擁有 Aileron
平台管理員角色；請依下表使用，不要共用或互相替代：

| 帳號 | 預設使用者名稱 | 密碼 | 用途與 Aileron 角色 |
| --- | --- | --- | --- |
| Aileron 平台管理員 | `admin` | 一般 Kubernetes 安裝產生強隨機密碼；只有 HomeLab／測試部署明確使用 `admin123` | 透過正常 OIDC 登入 Aileron，並以 `platform_role=admin` 管理使用者、平台資源與 Marketplace |
| Keycloak bootstrap administrator | `keycloak-admin` | 安裝時產生強隨機密碼，沒有固定預設值 | 只登入 Keycloak Admin Console 管理 realm 與 native users；不是 Aileron 平台管理員 |
| Break-glass | `local-emergency-admin` | 安裝時產生強隨機密碼，沒有固定預設值 | 緊急 OIDC 登入；預設是 Aileron `member`，除非平台管理員另外升級角色 |

:::danger HomeLab 密碼不得用於共享環境
`admin123` 只為隔離的 HomeLab／本機測試提供簡單登入。任何多人共用、可被其他網段存取或對外
暴露的環境，都必須在開放服務前改用獨立強密碼。一般 Kubernetes／bundled 安裝不得沿用此值。
:::

安裝器不會把隨機密碼寫入 Git、文件、log 或驗收報告。HomeLab 的 installation-owned 私密
artifact 位於下列 mode `0700` private tree，credential files 為 mode `0600`：

```text
<private-root>/install-secrets/homelab/identity-artifacts/keycloak-platform-admin/{subject,username,email,password,import.json}
<private-root>/install-secrets/homelab/identity-artifacts/keycloak-bootstrap-admin/{username,password}
<private-root>/install-secrets/homelab/identity-artifacts/keycloak-break-glass/{username,email,password}
```

預設 `<private-root>` 是 `/root/aileron-private`。Kubernetes 中對應資料位於
`aileron-identity-system` Namespace 的 `keycloak-platform-admin`、
`keycloak-bootstrap-admin` 與 `keycloak-break-glass` Secrets；只能由授權的叢集管理者讀取，且
不得把 `kubectl get secret ... -o yaml` 的輸出貼入 ticket、聊天或 shell history。一般安裝請以
實際 private root 與安裝器產生的 artifact inventory 為準。

Docker 的 `local-oidc` profile 同樣只部署 Keycloak，不部署 OpenLDAP 或測試目錄。若未來需要
LDAP，由 Keycloak User Federation 串接；Aileron 的 OIDC、JIT 與授權契約不改變。目前版本不
提供 LDAP workload、seed、Secret 或 federation 設定。

## External OIDC provider

建立 confidential client，啟用 Authorization Code flow，並註冊：

- Redirect URI：`{Platform Public Origin}/api/v1/oauth2/callback`
- Post logout URI：`{Platform Public Origin}/login`
- Scope：至少 `openid`，通常加上 `profile email`

Provider 的 issuer、由 issuer 固定衍生的 Discovery 與 JWKS 必須由 Manager Pod 存取；authorization endpoint 必須
可由使用者瀏覽器存取。Aileron 不呼叫 provider-specific administration API。

選用 `externalOidc` 時，Installer 不 render 或安裝 Identity Plane。External provider 必須通過與
Bundled Keycloak 相同的標準 OIDC conformance；不得把 external provider 當作失敗時的 fallback。
HomeLab acceptance bundle 的 `offlineOidcConformance` 僅驗證 provider-neutral adapter 與產品資料
契約，report 會明確標示 `mode: offline`；它不會部署、連線或宣稱已驗證任何外部 provider。正式採用
`externalOidc` 前，部署者仍須以目標 provider 執行真實 Authorization Code + PKCE、JIT 與登入失敗
情境驗證。

## Helm values

```yaml
platformPublicOrigin: https://aileron.example.com

oidc:
  issuerUrl: https://login.example.com/realms/aileron
  clientId: aileron-manager
  clientSecretName: aileron-oidc-client
  clientSecretKey: client-secret
```

`clientSecretName` 必須指向既存 Secret；Chart 不生成 client secret。若 provider 使用私人 CA，
另設定 `caSecretName` 與 `caSecretKey`。OIDC 設定與 secret 只注入 Manager，不會注入 Runtime、
Terminal 或 Operator。Scopes、signature algorithm、token lifetime、JWKS cache 與 Discovery timeout
由 Manager 唯一 typed settings model 的服務預設管理，不是 Helm 安裝輸入。

Discovery 固定為 `{issuerUrl}/.well-known/openid-configuration`。callback、post-logout redirect、
CORS 與 CSRF Origin 全部由 `platformPublicOrigin` 衍生，不提供個別 override。

OIDC 只用於登入、callback 與選用 provider logout。成功 callback 建立 Manager Session 後，
Session 有效期間的請求認證與授權完全由平台本機處理，不呼叫 provider；只有 Session 缺少、
過期、撤銷或 principal binding 不一致所產生的 `401 MANAGER_SESSION_REQUIRED` 才會讓
Frontend 重新進入 OIDC authorization flow。`403 PLATFORM_AUTHORIZATION_DENIED` 表示本機
使用者或平台 operation 不允許，不會觸發重新登入。

Session activity touch 與過期資料 cleanup 使用 Manager 固定內部政策，不是 Docker Compose
環境變數或 Helm value。Docker 與 Kubernetes 都不接受 touch 或 cleanup 的安裝輸入。

## Readiness 與故障

Manager 啟動時驗證 Discovery issuer、允許演算法與至少一把 JWKS signing key。設定錯誤會
阻止啟動；provider 無法連線時新的登入流程 fail closed，但既有有效 Manager Session 不會
因此失效。Frontend 不直接呼叫 provider token endpoint，也不保存 provider token。

## Signing Secret

Execution Grant 使用獨立的 Manager-to-Execution Ed25519 authority。`runtimeAssertions` 的
private-key Secret 只供 Manager 使用，public-JWKS Secret供 Runtime 與 Terminal 使用；Chart
不生成 key material。輪替時先發布新 public key，確認 consumers 已載入，再切換 active
private key，最後於 token TTL 與 rollout propagation window 後移除舊 key。

## 相關文件

- [身分與存取控制](/architecture/overview/identity-and-access)
- [Helm Values 參考](/reference/helm-values)
- [環境變數參考](/installation/environment-variables)
