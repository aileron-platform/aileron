---
sidebar_position: 6
title: 故障排除
---

# 故障排除

本頁收集部署和執行時常見的問題與解決方式。

## 啟動問題

### Docker Compose 啟動後前端無法登入

**症狀**：開啟 `http://localhost:8082` 後，點擊登入跳轉到 Keycloak，但顯示錯誤或無法載入。

**可能原因**：
1. Keycloak 尚未完成初始化
2. Realm 匯入失敗
3. Redirect URI 不符

**排查步驟**：

```bash
# 1. 確認 Keycloak 狀態
docker compose ps keycloak

# 2. 確認 Keycloak 已就緒
docker compose logs keycloak | grep -i "started"

# 3. 檢查 Realm 是否成功匯入
curl http://localhost:8080/realms/aileron/.well-known/openid-configuration

# 4. 若 Realm 缺失，重新啟動 Keycloak
docker compose restart keycloak
```

:::tip
Keycloak 首次啟動需要約 60 秒初始化。等 `docker compose ps` 顯示 `healthy` 再嘗試登入。
:::

### workspace-manager 啟動失敗：資料庫連線錯誤

**症狀**：`docker compose logs workspace-manager` 顯示 `connection refused` 或 `password authentication failed`。

**排查步驟**：

```bash
# 1. 確認 postgres 狀態
docker compose ps postgres
docker compose logs postgres

# 2. 手動測試連線
docker compose exec postgres psql -U postgres -d aileron -c "SELECT 1;"

# 3. 確認資料庫已初始化
docker compose exec postgres psql -U postgres -d aileron -c "\dt"
```

**解決方式**：
- 若資料庫未初始化，檢查 `init-sql/` 目錄下的腳本
- 若密碼錯誤，確認 `DATABASE_URL` 環境變數與 `POSTGRES_PASSWORD` 一致
- 完整清除後重啟：`python scripts/dev/docker/ops.py cleanup && python scripts/dev/docker/ops.py up --build`

### Kubernetes Pod 卡在 `Pending` 狀態

**可能原因**：
1. PVC 無法綁定（StorageClass 不存在）
2. 資源不足（CPU / Memory）
3. Image pull 失敗
4. Node selector / taint 不符

**排查步驟**：

```bash
# 1. 檢視 Pod 事件
kubectl describe pod <pod-name> -n aileron

# 2. 檢查 PVC 狀態
kubectl get pvc -n aileron

# 3. 檢查 StorageClass
kubectl get storageclass

# 4. 檢查節點資源
kubectl top nodes
```

### Keycloak OIDC redirect 失敗

**症狀**：登入後跳轉回前端時出現 `Invalid redirect uri` 錯誤。

**原因**：Keycloak Client 的 Valid Redirect URIs 未包含目前使用的網域。

**解決方式**：

1. 進入 Keycloak Admin Console
2. `aileron` Realm → Clients → `aileron-frontend`
3. 新增 Valid Redirect URIs：
   - Docker: `http://localhost:8082/*`
   - Kubernetes: `https://example.com/*`
4. 更新 Web Origins 對應的 CORS 允許來源
5. Save

若修改 Helm chart 的 realm.json，記得重新部署：

```bash
helm upgrade aileron helm/aileron \
  --namespace aileron
```

### Workspace 子網域無法連線（Kubernetes 本機開發）

**症狀**：Workspace 建立成功，但 AI Conversation 顯示 **Disconnected**。DevTools Network 中對 `workspace-runtime-<uuid>.aileron.localhost` 的請求 Status Code 為空白（連線失敗），或 preview / version-control 全部無法載入。

**原因**：macOS 不會自動將 `*.aileron.localhost` 三層子網域解析到 `127.0.0.1`。瀏覽器 DNS 查詢失敗 → 無法連到 nginx ingress → WebSocket / REST API 全部斷線。

**解決方式**：安裝 dnsmasq 做本地 wildcard DNS，詳見 [Kubernetes 模式 → 本機開發 DNS 設定](./kubernetes.md#本機開發-dns-設定-macos)。

**快速驗證是否為 DNS 問題**：

```bash
# 如果回空白或 NXDOMAIN，就是 DNS 沒設好
dscacheutil -q host -a name workspace-runtime-test.aileron.localhost

# 設好 dnsmasq 後應回 127.0.0.1
```

## Workspace 問題

### Workspace 建立卡住不動

**Docker 模式排查**：

```bash
# 1. 檢查 workspace-manager log
docker compose logs -f workspace-manager

# 2. 列出所有 workspace 容器
docker ps --filter "name=workspace-"

# 3. 檢查 Docker socket 掛載
docker compose exec workspace-manager ls -la /var/run/docker.sock
```

**Kubernetes 模式排查**：

```bash
# 1. 檢查 Workspace CR 狀態
kubectl get workspaces -A
kubectl describe workspace <name> -n <namespace>

# 2. 檢查 Operator log
kubectl logs -n aileron deployment/aileron-workspace-operator

# 3. 檢查目標 namespace 的 Pod
kubectl get pods -n workspace-system
kubectl describe pod workspace-runtime-<id> -n workspace-system
```

### Preview 畫面卡在載入中

**症狀**：Workspace 的 Next.js Preview 或 Runtime 畫面一直轉圈。

**可能原因**：
1. WebSocket 連線失敗（timeout 設太短）
2. 跨域問題（CORS）
3. Ingress 未正確處理 wildcard 子網域
4. 資料庫連線池耗盡（長時間運行）

**排查步驟**：

```bash
# 檢查瀏覽器 DevTools Network tab
# 尋找失敗的 WebSocket 或 XHR 請求

# Docker 模式：檢查 runtime log
docker compose logs -f workspace-runtime

# Kubernetes 模式：檢查對應 workspace pod
kubectl logs workspace-runtime-<id> -n workspace-system
```

**Ingress WebSocket 設定**：

```yaml
ingress:
  annotations:
    nginx.ingress.kubernetes.io/proxy-read-timeout: "3600"
    nginx.ingress.kubernetes.io/proxy-send-timeout: "3600"
    nginx.ingress.kubernetes.io/proxy-http-version: "1.1"
```

### Workspace Browser (WebRTC) 無法連線

**症狀**：點擊瀏覽器分頁後黑畫面或連線失敗。

**可能原因**：
1. CoTURN 未啟用或 IP 錯誤
2. UDP port 52000 被防火牆阻擋
3. NAT 1:1 映射設定錯誤

**排查步驟**：

```bash
# Docker 模式
docker compose logs workspace-browser

# 確認 UDP port 可用
nc -u -z localhost 52000

# Kubernetes 模式
kubectl get svc -l app=coturn -A
kubectl logs -n aileron deployment/aileron-coturn
```

**Kubernetes CoTURN host 設定**：

```yaml
coturn:
  # Docker Desktop k8s 使用 node IP
  host: "192.168.65.3"
  # 正式環境改為實際 public IP
  # host: "203.0.113.10"
```

### Claude Code 無法執行

**症狀**：Chat Panel 發送訊息後無回應，或顯示認證錯誤。

**排查步驟**：

```bash
# 確認 Anthropic API token 已設定
docker compose exec workspace-runtime env | grep ANTHROPIC

# 檢查 runtime log 中的 Claude 相關錯誤
docker compose logs workspace-runtime | grep -i claude
```

**常見錯誤**：

| 錯誤訊息 | 原因 | 解決 |
|----------|------|------|
| `Unauthorized` / `401` | Token 無效或過期 | 更新 `ANTHROPIC_AUTH_TOKEN` |
| `Model not found` | 模型名稱錯誤 | 確認使用支援的 Claude 模型 ID |
| `Rate limit exceeded` | 超過 API 限流 | 等待或升級 API 配額 |

## 資料庫問題

### PostgreSQL 資料夾權限錯誤

**症狀**：`./data/postgres` 權限問題導致容器無法啟動。

**解決方式**：

```bash
# macOS / Linux
sudo chown -R 999:999 ./data/postgres

# 或完整清除後重啟
python scripts/dev/docker/ops.py cleanup
python scripts/dev/docker/ops.py up --build
```

### Agent Sessions 表不存在（Kubernetes）

**症狀**：AI Conversation 返回 **500 Internal Server Error**，runtime log 出現：

```
relation "agent_sessions" does not exist
```

**原因**：Kubernetes PostgreSQL 啟動後未執行 `init-sql/001_init_schema.sql`，導致 `agent_sessions`、`agent_tasks`、`agent_messages` 等表缺失。

**解決方式**：

若使用 v0.1.0 之後的 Helm chart，bootstrap job 會在 `helm install` / `helm upgrade` 時自動執行 init schema。直接升級即可：

```bash
helm upgrade aileron helm/aileron --namespace aileron
```

若需手動修復現有環境：

```bash
# 找到 postgres pod
kubectl get pods -n aileron -l app.kubernetes.io/component=postgres

# 從本機灌入 init schema
kubectl exec -i -n aileron aileron-aileron-postgres-0 -- \
  psql -U postgres -d aileron -f - < init-sql/001_init_schema.sql

# 驗證
kubectl exec -n aileron aileron-aileron-postgres-0 -- \
  psql -U postgres -d aileron -c "\dt agent_*"
```

所有 DDL 使用 `CREATE TABLE IF NOT EXISTS`，重複執行不會影響既有資料。

### 資料庫長時間執行後連線耗盡

**症狀**：長時間運行後 Manager/Runtime 出現 `QueuePool limit` 或 httpx `ENOENT` 錯誤。

**原因**：資料庫連線池中的殭屍連線未被回收。

**解決方式**：
- 重啟相關服務：`docker compose restart workspace-manager workspace-runtime`
- 檢查連線池設定（`pool_recycle`）
- 這是已知問題，持續優化中

## 網路問題

### 服務間無法通訊（Docker 模式）

**症狀**：`workspace-manager` 無法呼叫 `workspace-runtime` 或反之。

**排查**：

```bash
# 1. 確認兩個容器在同一網路
docker network inspect aileron-network-dev

# 2. 從 manager 容器 ping runtime
docker compose exec workspace-manager ping -c 3 workspace-runtime

# 3. 檢查 DNS 解析
docker compose exec workspace-manager nslookup workspace-runtime
```

### CORS 錯誤

**症狀**：瀏覽器 console 顯示 `Access-Control-Allow-Origin` 錯誤。

**可能原因**：
- Keycloak Web Origins 未設定
- Manager API 的 CORS 白名單不含前端網域
- Kubernetes 模式下 `PUBLIC_ALLOWED_ORIGINS` 設定錯誤

**解決方式**：

```bash
# Kubernetes 檢查 platform-config
kubectl get configmap -n aileron \
  aileron-platform-config -o yaml

# 確認 PUBLIC_ALLOWED_ORIGINS 包含前端網域
```

### Kubernetes Ingress 502 Bad Gateway

**可能原因**：
1. 目標 Service 未就緒
2. Service selector 不符
3. Ingress path 設定錯誤

**排查**：

```bash
# 確認 Service Endpoints 存在
kubectl get endpoints -n aileron

# 確認 Pod 處於 Ready 狀態
kubectl get pods -n aileron

# 檢查 ingress-controller log
kubectl logs -n ingress-nginx deployment/ingress-nginx-controller
```

## 效能問題

### 容器記憶體不足被 OOMKilled

**症狀**：`kubectl get pods` 或 `docker compose ps` 顯示容器反覆重啟，事件訊息含 `OOMKilled`。

**解決方式**：

Docker 模式編輯 `docker-compose.yml`：

```yaml
workspace-browser:
  deploy:
    resources:
      limits:
        memory: 4G  # 調高
```

Kubernetes 模式調整 values.yaml：

```yaml
workspaceManager:
  resources:
    limits:
      memory: 1Gi  # 調高
```

### PostgreSQL 查詢變慢

**排查**：

```bash
# 連線到 DB
docker compose exec postgres psql -U postgres -d aileron

# 查看慢查詢
SELECT query, calls, total_exec_time, mean_exec_time
FROM pg_stat_statements
ORDER BY mean_exec_time DESC
LIMIT 10;

# 檢查 VACUUM 狀態
SELECT relname, last_vacuum, last_autovacuum
FROM pg_stat_user_tables;
```

## 有用的除錯指令

### Docker 模式

```bash
# 進入容器 shell
docker compose exec workspace-manager bash
docker compose exec workspace-runtime bash

# 即時追蹤所有服務 log
docker compose logs -f

# 重新建置並啟動特定服務
docker compose up -d --build workspace-manager

# 檢查網路
docker network inspect aileron-network-dev

# 列出所有相關容器（含動態 workspace）
docker ps -a --filter "name=aileron" --filter "name=workspace-"

# 清除無用的 volumes
docker volume prune
```

### Kubernetes 模式

```bash
# 進入 Pod shell
kubectl exec -it -n aileron deployment/aileron-workspace-manager -- bash

# 檢視所有資源
kubectl get all -n aileron

# 觀察 Pod 事件
kubectl get events -n aileron --sort-by='.lastTimestamp'

# 即時追蹤 log（多個 Pod）
kubectl logs -f -l app.kubernetes.io/name=workspace-manager -n aileron

# Port-forward 本地存取
kubectl port-forward -n aileron svc/aileron-workspace-manager 3001:3001

# 檢查 CRD
kubectl get workspaces -A
kubectl describe workspace <name> -n workspace-system

# 重啟 Deployment
kubectl rollout restart deployment/aileron-workspace-manager -n aileron

# 檢視所有 ConfigMap
kubectl get configmap -n aileron
kubectl describe configmap aileron-platform-config -n aileron
```

## 取得協助

若以上方法無法解決問題：

1. 收集相關 log（`docker compose logs` 或 `kubectl logs`）
2. 附上 docker compose 版本或 Helm values
3. 描述重現步驟
4. 提供到 [GitHub Issues](https://github.com/) 或相關社群
