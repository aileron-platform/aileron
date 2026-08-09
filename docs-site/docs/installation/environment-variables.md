---
title: 環境變數參考
---

# 環境變數參考

Aileron 把安裝輸入與容器輸出分開管理。Docker 的唯一安裝輸入表面是 repository root `.env`；Kubernetes 的唯一安裝輸入表面是 Helm values。服務目錄沒有獨立 `.env` 契約，且 Adapter 衍生值不是安裝輸入。

## 共同安裝設定

| 邏輯設定 | Docker | Kubernetes | 說明 |
| --- | --- | --- | --- |
| Platform Public Origin | `PLATFORM_PUBLIC_ORIGIN` | `platformPublicOrigin` | 精確 `http(s)://host[:port]`，不可包含 path、query、fragment、credentials 或結尾 `/` |
| Canonical OIDC issuer | `OIDC_ISSUER_URL` | `oidc.issuerUrl` | 外部 Provider issuer，與 Platform Public Origin 是不同設定 |
| OIDC client ID | `OIDC_CLIENT_ID` | `oidc.clientId` | Manager confidential client ID |
| OIDC client secret | `${HOST_PLATFORM_SECRETS_DIR}/oidc-client-secret` | `oidc.clientSecretName` + `oidc.clientSecretKey` | 只供 Manager 使用的 Secret reference |

Manager 是唯一 OIDC client。Discovery 固定為 `{OIDC_ISSUER_URL}/.well-known/openid-configuration`，並由 Platform Public Origin 衍生：

- callback：`{origin}/api/v1/oauth2/callback`
- post-logout redirect：`{origin}/login`
- credentialed request、CSRF 與 CORS Origin：`{origin}`

這些衍生值不能個別覆寫。Frontend、Runtime、Terminal 與 Operator 不接收 external issuer、OIDC client secret 或 provider token。

Manager Session 有效期間完全由平台本機處理。Session activity touch 與 absolute expiry
cleanup 使用固定內部政策；Docker Compose 與 Helm 都不提供 touch 或 cleanup 的安裝變數。

## Docker Compose 安裝輸入

root `.env.example` 列出目前可設定的完整 Compose input。主要群組如下：

| 群組 | 變數 |
| --- | --- |
| 安裝識別 | `TZ`、`AILERON_INSTALLATION_ID`、`BOOTSTRAP_ADMIN_SUBJECT`、`BOOTSTRAP_ADMIN_USERNAME`、`BOOTSTRAP_ADMIN_EMAIL` |
| Host source | `HOST_PROJECT_ROOT`、`HOST_PLATFORM_SECRETS_DIR`、`HOST_TURN_CONFIG_DIR`、`HOST_TURN_SECRETS_DIR` |
| Browser／TURN | `TURN_CREDENTIAL_REVISION`、`TURN_CONNECTIVITY_GATEWAY_EXTERNAL_PORT`、`TURN_RELAY_MIN_PORT`、`TURN_RELAY_MAX_PORT` |
| Frontend capability | `VITE_BROWSER_EXTENSION_ID` |
| Image selection | `WORKSPACE_MANAGER_IMAGE`、`WORKSPACE_OPERATOR_IMAGE`、`WORKSPACE_RUNTIME_IMAGE`、`WORKSPACE_UI_IMAGE`、`COTURN_IMAGE` |

Compose Adapter 會產生固定 container path、Service DNS、callback、logout、Origin 與服務預設；這些值不放入 root `.env`。

## Kubernetes Helm 安裝輸入

Helm 使用 `platformPublicOrigin`、`oidc.*`、`platformSecrets.*`、`runtimeAssertions.*` 與各功能的 existing Secret name/key。Chart 不接受任意 service environment override。公開 Ingress 只服務 Platform Public Origin 的單一 host；Runtime、Browser 與 Canvas 由 Frontend same-origin path gateway 轉送。

## Workspace Runtime 平台環境

Manager Provisioner 與 Workspace Operator 注入相同的 `AILERON_*` key set。這些是 Adapter output，不是安裝者或 Workspace 使用者設定：

| 變數 | 說明 |
| --- | --- |
| `AILERON_WORKSPACE_ID` | Workspace ID |
| `AILERON_WORKSPACE_PATH` | Workspace filesystem root |
| `AILERON_RUNTIME_INSTANCE_ID` | execution-plane generation ID |
| `AILERON_RUNTIME_ACCESS_REVISION` | Runtime access revision |
| `AILERON_KB_MOUNT_REVISION` | Knowledge Base mount revision |
| `AILERON_WORKTREE_SUBDIR` | 受管理的 Git worktree 子目錄 |
| `AILERON_MANAGER_INTERNAL_URL` | Manager 內部 Service URL |
| `AILERON_PLATFORM_PUBLIC_ORIGIN` | 唯一精確平台 Origin |
| `AILERON_RUNTIME_STATE_DATABASE_URL_FILE` | Workspace-scoped database URL Secret file |
| `AILERON_RUNTIME_CONTROL_TOKEN_FILE` | generation-scoped control token Secret file |
| `AILERON_RUNTIME_ASSERTION_PUBLIC_KEY_SET_FILE` | Manager assertion public JWKS file |
| `AILERON_RUNTIME_ASSERTION_ISSUER` | Manager assertion issuer |
| `AILERON_BROWSER_SERVICE_NAME` | Browser 內部 service name |
| `AILERON_BROWSER_WEBRTC_INTERNAL_URL` | Browser 內部 WebRTC URL |
| `AILERON_BROWSER_CDP_URL` | Browser 內部 CDP URL |
| `AILERON_CANVAS_SERVICE_NAME` | Canvas 內部 service name |
| `AILERON_CANVAS_INTERNAL_URL` | Canvas renderer 內部 URL |
| `AILERON_CANVAS_API_URL` | Canvas 管理 API 內部 URL |

Workspace 使用者環境不得使用 `AILERON_*` 前綴。

## Secret 交付

- Docker：root `.env` 只保存 host Secret 目錄或檔案路徑；Compose 以唯讀 mount 交付，服務只讀 `*_FILE` 或固定 mounted path。
- 本機 OpenLDAP adapter 使用第三方 image 原生的 `LDAP_ADMIN_PASSWORD_FILE` 與 `LDAP_CONFIG_PASSWORD_FILE`；只允許首次初始化階段讀取，完成後長期 `slapd` 的 argv 與 environment 不得含 Secret value。
- Kubernetes：values 只保存 existing Secret name/key；Application Pod 只能透過唯讀 Secret volume 取得 Secret，並以 `*_FILE` 或契約定義的固定 mounted path 讀取。
- Application Secret 不得透過 `SecretKeyRef` 或 `envFrom.secretRef` 實體化為 process environment。`SecretKeyRef` 也不屬於合法的 Secret 交付介面。
- Secret value 不可放進一般環境變數、ConfigMap、Frontend build environment、文件範例或版本控制。

## Frontend

Frontend 的 API、OAuth、Runtime、Browser、Canvas 與 WebSocket 全部使用 same-origin 相對路徑，不接受 public URL、API base URL、Workspace host 或動態 port 設定。唯一保留的 build capability flag 是經 consumer 證明必要的 `VITE_BROWSER_EXTENSION_ID`。
