# Docker Image 發布流程

本專案提供 GitHub Actions workflow `[docker-publish.yml](./workflows/docker-publish.yml)`，用來自動建置並推送 Docker Hub image。

## 發布規則

- `develop` branch push：發布 `dev-*` 單平台 tag
- `main` branch push：發布 `latest-*` 單平台 tag
- `workflow_dispatch`：可手動選擇發布 `dev`、`latest` 或 `both`

## 平台與 tag 命名

所有 image 只會發布單平台 tag，不再建立無平台的 multi-arch manifest tag。

一般服務 image：

- `:<channel>-amd64`
- `:<channel>-arm64`

例如：

- `ailerondocker/workspace-manager:dev-amd64`
- `ailerondocker/workspace-manager:dev-arm64`

`workspace-runtime` 另外包含 flavor：

- `:<channel>-codex-amd64`
- `:<channel>-codex-arm64`
- `:<channel>-lite-amd64`
- `:<channel>-lite-arm64`

例如：

- `ailerondocker/workspace-runtime:latest-codex-amd64`
- `ailerondocker/workspace-runtime:latest-lite-arm64`

## 涵蓋 image

Base image：

- `ailerondocker/workspace-runtime-base-lite`

一般服務：

- `ailerondocker/workspace-ui`
- `ailerondocker/workspace-manager`
- `ailerondocker/workspace-chrome`
- `ailerondocker/workspace-canvas`
- `ailerondocker/workspace-operator`

Runtime：

- `ailerondocker/workspace-runtime`（`codex` / `lite`）

## GitHub Secrets

需要在 repository secrets 設定：

- `DOCKERHUB_USERNAME`
- `DOCKERHUB_TOKEN`

建議使用 Docker Hub access token，不要直接使用帳號密碼。

## 手動發布方式

進入 GitHub Actions 後執行 `Publish Docker Images`，可選：

- `release_channel`
  - `auto`：依 branch 自動判斷
  - `dev`
  - `latest`
  - `both`
- `scope`
  - `all`
  - `base`
  - `services`
  - `runtime`

## 注意事項

- `workspace-runtime` 會依 flavor 引用不同 base image：
  - `codex` -> 直接從 Docker Hub 拉取 `ailerondocker/codex-universal:latest-<arch>`
  - `lite` -> `workspace-runtime-base-lite:<channel>-<arch>`
- `workspace-ui` 的 `dev-*` tag 是本地開發用途，使用 `frontend/Dockerfile.dev` 啟動 Vite dev server；`latest-*` tag 則使用 `frontend/Dockerfile` 建置 nginx 靜態站台。
- workflow 目前只負責發布 image，不會自動修改 `docker-compose.yml`、Helm values 或程式內的預設 image tag。
- `codex-universal` 由 `aileron-platform/codex-universal` repository 的獨立 workflow 負責建置與發布。
