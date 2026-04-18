# Docker Image 發布流程

本專案提供 GitHub Actions workflow `[docker-publish.yml](./workflows/docker-publish.yml)`，用來自動建置並推送 Docker Hub image。

## 發布規則

- `develop` branch push：發布 `dev` tag
- `main` branch push：發布 `latest` tag
- `workflow_dispatch`：可手動選擇發布 `dev`、`latest` 或 `both`

## 平台與 tag 命名

所有 image 都會先發布單平台 tag，再組成 multi-arch manifest。

一般服務 image：

- `:<channel>-amd64`
- `:<channel>-arm64`
- `:<channel>`

例如：

- `ailerondocker/workspace-manager:dev-amd64`
- `ailerondocker/workspace-manager:dev-arm64`
- `ailerondocker/workspace-manager:dev`

`workspace-runtime` 另外包含 flavor：

- `:<channel>-codex-amd64`
- `:<channel>-codex-arm64`
- `:<channel>-codex`
- `:<channel>-lite-amd64`
- `:<channel>-lite-arm64`
- `:<channel>-lite`

例如：

- `ailerondocker/workspace-runtime:latest-codex`
- `ailerondocker/workspace-runtime:latest-lite`

## 涵蓋 image

Base image：

- `ailerondocker/codex-universal`
- `ailerondocker/workspace-runtime-base-lite`

一般服務：

- `ailerondocker/workspace-ui`
- `ailerondocker/workspace-manager`
- `ailerondocker/workspace-chrome`
- `ailerondocker/workspace-nextjs`
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
  - `codex` -> `codex-universal`
  - `lite` -> `workspace-runtime-base-lite`
- workflow 目前只負責發布 image，不會自動修改 `docker-compose.yml`、Helm values 或程式內的預設 image tag。
- `codex-universal` 來源為 `workspace-runtime/codex-universal` submodule，workflow checkout 時會一併抓取 submodule。
