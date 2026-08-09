# Aileron Workspace Manager

Workspace Manager 是 Aileron 的控制平面服務，負責 Workspace 生命週期、權限、協作、Automation 與 Docker／Kubernetes execution plane 編排。

## 主要能力

- Workspace 建立、設定、啟動、重啟與刪除
- Docker 與 Kubernetes execution plane 編排
- RBAC、使用者群組與 Knowledge Base 分享
- Automation 排程與執行追蹤
- OIDC Authorization Code flow、BFF session 與 CSRF 保護

## 本機開發

正式本機部署只使用 repository root 的 Compose Adapter：

```bash
docker buildx bake --load local
docker compose up --remove-orphans --no-build -d
docker compose logs -f workspace-manager
```

Manager 的獨立 `.env` 不屬於正式設定表面。Compose 安裝輸入只放在 root `.env`；Kubernetes 安裝輸入只放在 Helm values。

## 公開 Origin 與 OIDC 契約

每套安裝只設定一個 `PLATFORM_PUBLIC_ORIGIN`。Manager 由此值確定性衍生：

- OIDC callback：`{origin}/api/v1/oauth2/callback`
- post-logout redirect：`{origin}/login`
- credentialed request、CSRF 與 CORS Origin：`{origin}`

`OIDC_ISSUER_URL` 是外部 Provider 的 canonical issuer，Discovery 固定使用 `{issuer}/.well-known/openid-configuration`。Manager 是唯一 OIDC client；Frontend、Runtime、Terminal 與 Operator 不取得 issuer、client secret 或 provider token。

OIDC client secret 與其他機密只以唯讀檔案提供，例如 `OIDC_CLIENT_SECRET_FILE`。Docker 掛載 root `.env` 所指向的 host Secret 目錄；Kubernetes 使用 existing Secret name/key 與唯讀 Secret volume。不得以一般環境變數傳遞明文 Secret。

## Runtime 平台環境

Manager Provisioner 對 Runtime 注入的所有平台欄位都使用 `AILERON_*`，包括 Workspace identity/path、Runtime instance/revision、Manager internal URL、Platform Public Origin、Browser、Canvas、assertion 與 Secret file reference。Workspace 使用者環境不得使用 `AILERON_*` 前綴。

## API

- `GET /health`
- `/api/v1/oauth2/*`
- `/api/v1/users/*`
- `/api/v1/workspaces/*`
- `/api/v1/marketplace/*`
- `/api/v1/automation/*`
- `/api/v1/settings`

瀏覽器一律透過 Platform Public Origin 的 `/api/v1/...` 使用 API。容器內部服務才使用部署 Adapter 產生的 Service DNS。

## Container 測試

```bash
make test-workspaces
make lint-workspaces
make verify-workspaces
```
