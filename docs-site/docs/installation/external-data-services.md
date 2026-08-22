---
title: 外部資料服務
---

# 外部資料服務

Aileron 可讓平台資料庫、身分資料庫、一般 Redis、工作佇列 Redis 與工作結果 Redis 使用安裝範圍外的服務。Core 與 Identity chart 都只以各自的 `postgres.enabled` 選擇 PostgreSQL 來源：`true` 使用內建服務，`false` 使用外部資料服務。Redis 由 `redis.enabled` 選擇來源。不要建立其他 mode flag。

## 營運者準備事項

資料服務營運者必須先準備：

- 互不共用的 Aileron 專用平台 database 與身分 database。
- 平台 login 是平台 database owner，具有 `CREATEROLE`、`pg_signal_backend`、database `CREATE`，並可使用 `uuid-ossp` 與 `pgcrypto` trusted extensions。它必須是非 superuser。
- 身分 login 可在身分 database 的 `public` schema 建立、修改與刪除 Keycloak 物件。
- 三條 standalone-compatible Redis URL；每條都明確選擇 numeric logical database。首版不支援 Cluster 或 Sentinel。
- Redis ACL 至少允許各 consumer 在自己的 keyspace 執行連線、PING、讀寫、刪除與過期操作。工作佇列與結果不得使用會任意淘汰資料的 policy。
- 所有 URL credential 只放在 Kubernetes Secret；values 只放 Secret name/key 與非秘密 topology。私有 CA 也由獨立 Secret 提供。
- 外部服務營運者負責 database、Redis keyspace 與 Identity data 的備份、還原演練、容量、延遲、連線數、複寫狀態與可用性告警；Aileron health endpoint 不能取代資料服務監控。

安裝 preflight 會實際驗證 role/schema 建立、active session termination、generation rotation、extension 能力，以及三條 Redis 的 PING/write/read/delete。probe 只清除自己建立且帶有本次 ownership marker 的物件。

## Core values

```yaml
postgres:
  enabled: false

platformSecrets:
  existingSecretName: aileron-platform-secrets
  databaseUrlKey: database-url
  runtimeDatabaseCredentialKey: runtime-database-credential-key

platformDatabase:
  revision: platform-database-v1
  caSecretName: platform-database-ca
  caSecretKey: ca.crt
  ciliumEgress:
    kind: namespacePods
    namespace: platform-data
    podLabels:
      app.kubernetes.io/name: postgres

redis:
  enabled: false
  connections:
    general:
      revision: redis-general-v1
      urlSecretName: redis-general
      urlSecretKey: url
      caSecretName: redis-general-ca
      caSecretKey: ca.crt
    jobQueue:
      revision: redis-job-queue-v1
      urlSecretName: redis-job-queue
      urlSecretKey: url
      caSecretName: redis-job-queue-ca
      caSecretKey: ca.crt
    jobResult:
      revision: redis-job-result-v1
      urlSecretName: redis-job-result
      urlSecretKey: url
      caSecretName: redis-job-result-ca
      caSecretKey: ca.crt
```

啟用 Cilium policy 時，外部平台資料庫必須提供 `platformDatabase.ciliumEgress`。同叢集服務使用 `namespacePods` 與明確 Pod labels；固定網段使用 `cidrs`；受管服務的穩定 hostname 使用 `fqdns`。這是非秘密網路目的地，不得放入 credential 或以 `world` 取代精確 target。Operator 只接收此目的地，不接收平台 DSN。

平台 DSN 可傳入 Runtime 的 libpq query allowlist 僅包含 `sslmode`、`sslrootcert`、`connect_timeout`、`target_session_attrs`、`ssl_min_protocol_version` 與 `ssl_max_protocol_version`。Runtime 會把 TLS 與 timeout 參數轉成 asyncpg 連線設定，而不會把 libpq 專用參數直接交給 driver。CA 在容器內的固定位置是 `/etc/aileron/data-service-ca/platform-database/ca.crt`。三條 `rediss://` 連線的 CA 分別位於 `redis-general`、`redis-job-queue` 與 `redis-job-result` 目錄。

## Identity values

```yaml
postgres:
  enabled: false
  jdbcUrl: jdbc:postgresql://identity-db.example.test:5432/aileron_identity?sslmode=verify-full
  revision: identity-database-v1
  caSecretName: identity-database-ca
  caSecretKey: ca.crt

networkPolicy:
  externalDatabaseEgress:
    mode: ipBlock
    cidr: 10.24.0.0/16
```

`jdbcUrl` 不得含 username、password、client certificate 或自訂 CA path。Keycloak、preflight、backup 與 restore 共用同一 topology、credential Secret 與固定 CA path。`externalDatabaseEgress.mode` 可用同叢集的 `selector`、靜態 `ipBlock`，或在無法用標準 NetworkPolicy 表達 FQDN 時明確設為 `disabled`。

## Rotation 與解除安裝

Secret 或 CA 更新不會更換既有 connection pool。更新連線 material 時必須同時改變對應 `revision`：平台資料庫與三條 Redis revision 會重建 Manager Pod；身分資料庫 revision 會重建 Keycloak Pod；Runtime database CA revision 會透過 Workspace CR 觸發 Runtime recycle。generation login rotation 會終止舊 generation 的 active sessions。

Helm uninstall 不會刪除外部 service、database、Identity data、Workspace schema、Runtime login、Redis keyspace 或 backup artifact。需要刪除 Aileron 資料邊界時，必須使用另行核准、明確確認且可稽核的 destructive cleanup 操作。

Docker Compose 的 `docker-compose.yml` 是外部資料服務 base。內建開發服務使用 `docker-compose.bundled-data-services.yml` overlay；私有 CA 使用 `docker-compose.data-service-tls.yml` overlay。本機 `local-oidc` profile 使用 `dev-file`，不是外部資料服務路徑。

```bash
# 外部資料服務
docker compose -f docker-compose.yml up --remove-orphans --no-build -d

# 外部資料服務與私有 CA
docker compose -f docker-compose.yml -f docker-compose.data-service-tls.yml \
  up --remove-orphans --no-build -d

# 內建本機資料服務
docker compose -f docker-compose.yml -f docker-compose.bundled-data-services.yml \
  up --remove-orphans --no-build -d
```
