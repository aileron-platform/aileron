---
title: External Data Services
---

# External Data Services

Aileron can use services outside the installation boundary for the platform database, Identity database, general Redis, job-queue Redis, and job-result Redis. Each of the Core and Identity charts uses only its own `postgres.enabled` value to select PostgreSQL: `true` uses the bundled service and `false` uses an external data service. `redis.enabled` selects the Redis source. Do not add another mode flag.

## Operator prerequisites

The data-service operator prepares:

- Separate, Aileron-dedicated platform and Identity databases.
- A non-superuser platform login that owns the platform database, has `CREATEROLE`, `pg_signal_backend`, and database `CREATE`, and can use the trusted `uuid-ossp` and `pgcrypto` extensions.
- An Identity login that can create, alter, and delete Keycloak objects in the Identity database's `public` schema.
- Three standalone-compatible Redis URLs, each selecting an explicit numeric logical database. Cluster and Sentinel are not supported in the first release.
- Redis ACLs that allow each consumer to connect, PING, read, write, delete, and expire keys in its keyspace. Job queues and results must not use an arbitrary-eviction policy.
- Credentials only in Kubernetes Secrets. Values contain Secret name/key references and non-secret topology. Private CAs use separate Secrets.
- The external-service operator owns backup and restore drills for databases, Redis keyspaces, and Identity data, plus alerts for capacity, latency, connections, replication, and availability. Aileron health endpoints do not replace data-service monitoring.

Installation preflight performs real role/schema creation, active-session termination, generation rotation, extension checks, and PING/write/read/delete operations on all three Redis connections. It removes only probe objects carrying its ownership marker.

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

When Cilium policy is enabled, an external platform database must define `platformDatabase.ciliumEgress`. Use `namespacePods` with exact Pod labels for an in-cluster service, `cidrs` for stable network ranges, or `fqdns` for a managed service with a stable hostname. This is a non-secret network destination: it must not contain credentials or replace an exact target with `world`. The Operator receives only this destination, never the platform DSN.

The libpq query allowlist forwarded to Runtime contains only `sslmode`, `sslrootcert`, `connect_timeout`, `target_session_attrs`, `ssl_min_protocol_version`, and `ssl_max_protocol_version`. Runtime adapts TLS and timeout parameters to asyncpg connection settings instead of passing libpq-only parameters to the driver. The fixed container CA path is `/etc/aileron/data-service-ca/platform-database/ca.crt`. The three `rediss://` CAs use separate `redis-general`, `redis-job-queue`, and `redis-job-result` directories.

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

`jdbcUrl` cannot contain a username, password, client certificate, or custom CA path. Keycloak, preflight, backup, and restore share the same topology, credential Secret, and fixed CA path. `externalDatabaseEgress.mode` accepts an in-cluster `selector`, a static `ipBlock`, or explicit `disabled` when standard NetworkPolicy cannot express a stable FQDN target.

## Rotation and uninstall

Updating a Secret or CA does not replace established connection pools. Change the matching `revision` with connection material: the platform database and three Redis revisions recreate Manager Pods; the Identity database revision recreates Keycloak Pods; a Runtime database CA revision flows through the Workspace CR and recycles Runtime. Generation-login rotation terminates active sessions owned by the previous generation.

Helm uninstall does not delete an external service, database, Identity data, Workspace schema, Runtime login, Redis keyspace, or backup artifact. Removing the Aileron data boundary requires a separately approved, explicitly confirmed, auditable destructive-cleanup operation.

For Docker Compose, `docker-compose.yml` is the external-data-service base. Add `docker-compose.bundled-data-services.yml` for bundled development services and `docker-compose.data-service-tls.yml` for private CAs. The local `local-oidc` profile uses `dev-file`; it is not an external-data-service path.

```bash
# External data services
docker compose -f docker-compose.yml up --remove-orphans --no-build -d

# External data services with private CAs
docker compose -f docker-compose.yml -f docker-compose.data-service-tls.yml \
  up --remove-orphans --no-build -d

# Bundled local data services
docker compose -f docker-compose.yml -f docker-compose.bundled-data-services.yml \
  up --remove-orphans --no-build -d
```
