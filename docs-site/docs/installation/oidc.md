---
title: 外部 OIDC 安裝
---

# 外部 OIDC 安裝

Aileron 必須連接一個符合 OpenID Connect 的外部 identity provider。核心 Helm Chart 不部署
Keycloak、LDAP、realm、provider database 或任何 IdP 管理元件。開發或 CI 若需要自帶 IdP，
應使用獨立 installation，不能作為 Aileron subchart。

## Provider 設定

建立 confidential client，啟用 Authorization Code flow，並註冊：

- Redirect URI：`{Platform Public Origin}/api/v1/oauth2/callback`
- Post logout URI：`{Platform Public Origin}/login`
- Scope：至少 `openid`，通常加上 `profile email`

Provider 的 issuer、由 issuer 固定衍生的 Discovery 與 JWKS 必須由 Manager Pod 存取；authorization endpoint 必須
可由使用者瀏覽器存取。Aileron 不呼叫 provider-specific administration API。

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
