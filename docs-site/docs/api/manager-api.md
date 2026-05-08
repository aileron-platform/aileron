---
sidebar_position: 1
title: Manager API
---

# Workspace Manager API

## 互動式文件

- **Swagger UI**：http://localhost:3001/docs
- **ReDoc**：http://localhost:3001/redoc

## Base URL

```
http://localhost:3001
```

## 認證

預設無需認證（`ENABLE_AUTH=false`）。

啟用 Keycloak 認證後，所有 API 需要在 Header 帶入 Bearer Token：

```
Authorization: Bearer <jwt_token>
```

## 主要端點

### 健康檢查

```
GET /health
```

回應：
```json
{ "status": "ok", "database": "ok", "redis": "ok" }
```

### 工作區管理

| Method | 路徑 | 說明 |
|--------|------|------|
| `GET` | `/api/v1/workspaces` | 列出所有 workspace |
| `POST` | `/api/v1/workspaces` | 建立 workspace |
| `GET` | `/api/v1/workspaces/{id}` | 取得 workspace 詳情 |
| `PUT` | `/api/v1/workspaces/{id}` | 更新 workspace |
| `DELETE` | `/api/v1/workspaces/{id}` | 刪除 workspace |
| `POST` | `/api/v1/workspaces/{id}/start` | 啟動 workspace |
| `POST` | `/api/v1/workspaces/{id}/stop` | 停止 workspace |
| `POST` | `/api/v1/workspaces/{id}/restart` | 重啟 workspace |

### 工作區設定

| Method | 路徑 | 說明 |
|--------|------|------|
| `GET` | `/api/v1/workspaces/{id}/setup/*` | 取得設定 |
| `PUT` | `/api/v1/workspaces/{id}/setup/*` | 更新設定 |

### 自動化任務

| Method | 路徑 | 說明 |
|--------|------|------|
| `GET` | `/api/v1/automation` | 列出自動化任務 |
| `POST` | `/api/v1/automation` | 建立任務 |
| `GET` | `/api/v1/automation/{id}` | 取得任務 |
| `PUT` | `/api/v1/automation/{id}` | 更新任務 |
| `DELETE` | `/api/v1/automation/{id}` | 刪除任務 |
| `POST` | `/api/v1/automation/{id}/trigger` | 手動觸發 |

### 使用者管理

| Method | 路徑 | 說明 |
|--------|------|------|
| `GET` | `/api/v1/users` | 列出使用者 |
| `POST` | `/api/v1/users` | 建立使用者 |
| `GET` | `/api/v1/users/{id}` | 取得使用者 |
| `PUT` | `/api/v1/users/{id}` | 更新使用者 |

### 團隊管理

| Method | 路徑 | 說明 |
|--------|------|------|
| `GET` | `/api/v1/teams` | 列出團隊 |
| `POST` | `/api/v1/teams` | 建立團隊 |
| `POST` | `/api/v1/teams/{id}/members` | 新增成員 |

### 其他

| Method | 路徑 | 說明 |
|--------|------|------|
| `GET` | `/api/v1/settings` | 平台設定 |
| `GET` | `/api/v1/container-images` | 容器映像列表 |
| `GET` | `/api/v1/oauth/*` | OAuth 流程 |

## 錯誤格式

```json
{
  "detail": "錯誤訊息",
  "code": "ERROR_CODE"
}
```

常見 HTTP 狀態碼：

| 狀態碼 | 說明 |
|--------|------|
| `200` | 成功 |
| `201` | 建立成功 |
| `400` | 請求格式錯誤 |
| `401` | 未認證 |
| `403` | 無權限 |
| `404` | 資源不存在 |
| `500` | 伺服器錯誤 |
