---
sidebar_position: 2
title: 服務位址與帳號
---

# 服務位址與帳號

啟動完成後，所有服務如下：

## 服務位址（Docker 模式）

| 服務 | URL | 說明 |
|------|-----|------|
| **Frontend** | http://localhost:8082 | 主操作介面 |
| **Manager API** | http://localhost:3001 | Workspace Manager REST API |
| **Manager Swagger** | http://localhost:3001/docs | Manager 互動式 API 文件 |
| **Manager ReDoc** | http://localhost:3001/redoc | Manager ReDoc API 文件 |
| **Runtime API** | http://localhost:3002 | Workspace Runtime REST API |
| **Runtime Swagger** | http://localhost:3002/docs | Runtime 互動式 API 文件 |
| **Runtime ReDoc** | http://localhost:3002/redoc | Runtime ReDoc API 文件 |
| **Keycloak Admin** | http://localhost:8080/admin | 認證管理後台 |
| **Draw.io** | http://localhost:8083 | 圖表工具 |
| **Flower** | http://localhost:5555 | Celery 任務監控 |

## 預設帳號

### 前端登入

```
username: admin
password: admin123
```

### Keycloak 管理後台

```
URL:      http://localhost:8080/admin
username: admin
password: admin
```

:::warning 生產環境
以上為開發用預設帳號，生產部署時**必須**修改所有密碼與 secret。
:::

## 健康檢查端點

| 服務 | 端點 |
|------|------|
| Workspace Manager | `GET http://localhost:3001/health` |
| Workspace Runtime | `GET http://localhost:3002/health` |

## 整合測試

```bash
# 執行 runtime 整合測試
python3 scripts/dev/docker/ops.py test runtime

# 執行 manager 整合測試
python3 scripts/dev/docker/ops.py test manager
```
