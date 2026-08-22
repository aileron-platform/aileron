---
title: 服務位址與帳號
---

# 服務位址與帳號

瀏覽器只使用一個 Platform Public Origin。Docker 預設為 `http://localhost:8082`；Kubernetes 由 `platformPublicOrigin` 決定。

## 公開路徑

| 功能 | 路徑 |
| --- | --- |
| Frontend SPA | `/` |
| Manager API | `/api/v1/...` |
| OIDC login／callback／logout | `/api/v1/oauth2/...` |
| Workspace Runtime | `/workspaces/{workspaceId}/runtime/...` |
| Workspace Browser | `/workspaces/{workspaceId}/browser/...` |
| Workspace Canvas | `/workspaces/{workspaceId}/canvas/...` |

Frontend gateway 只接受 canonical Workspace UUID 與固定 `runtime`、`browser`、`canvas` target。瀏覽器不取得 Service DNS、容器 port、Workspace host 或 request-supplied upstream。

## Docker 本機位址

| 服務 | URL | 說明 |
| --- | --- | --- |
| Aileron | `http://localhost:8082` | 唯一瀏覽器入口 |
| Connectivity Gateway | `http://localhost:18083` | host frontend vantage 的 evidence 入口，不是公開 Manager API |
| Coturn | `turn:localhost:3478` | TURN control listener；relay range 由 profile 決定 |

## 登入

登入 credential 由目前選用的 Identity adapter 管理。Docker 與 Kubernetes 都設定 canonical issuer 與 Manager confidential client；Bundled Keycloak 的 native user 由 Keycloak Admin Console 管理，Aileron bootstrap admin 只建立本地角色快照，不建立 Provider 密碼。

## Workspace 健康檢查

Runtime health 使用 same-origin 路徑：

```text
GET /workspaces/{workspaceId}/runtime/health
```

Browser 與 Canvas 也使用同一 Origin 下的固定 Workspace path，不依賴動態 hostname 或 port。
