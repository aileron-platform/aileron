---
sidebar_position: 6
title: Troubleshooting
---

# Troubleshooting

This page collects common issues and fixes encountered during deployment and runtime.

## Startup Issues

### Frontend Can't Log In After docker compose

**Symptom**: Opening `http://localhost:8082` and clicking login redirects to Keycloak but shows an error or fails to load.

**Possible causes**:
1. Keycloak hasn't finished initializing
2. Realm import failed
3. Redirect URI mismatch

**Debugging**:

```bash
# 1. Check Keycloak status
docker compose ps keycloak

# 2. Verify Keycloak is up
docker compose logs keycloak | grep -i "started"

# 3. Check realm was imported
curl http://localhost:8080/realms/aileron/.well-known/openid-configuration

# 4. If realm is missing, restart Keycloak
docker compose restart keycloak
```

:::tip
Keycloak needs about 60 seconds to initialize on first startup. Wait for `docker compose ps` to show `healthy` before trying to log in.
:::

### workspace-manager Fails to Start: Database Connection Error

**Symptom**: `docker compose logs workspace-manager` shows `connection refused` or `password authentication failed`.

**Debugging**:

```bash
# 1. Check postgres status
docker compose ps postgres
docker compose logs postgres

# 2. Test connection manually
docker compose exec postgres psql -U postgres -d aileron -c "SELECT 1;"

# 3. Verify database is initialized
docker compose exec postgres psql -U postgres -d aileron -c "\dt"
```

**Fixes**:
- If database isn't initialized, check the scripts under `init-sql/`
- If the password is wrong, confirm `DATABASE_URL` matches `POSTGRES_PASSWORD`
- Full cleanup and restart: `python scripts/dev/docker/ops.py cleanup && python scripts/dev/docker/ops.py up --build`

### Kubernetes Pod Stuck in `Pending`

**Possible causes**:
1. PVC cannot bind (StorageClass missing)
2. Insufficient resources (CPU / Memory)
3. Image pull failure
4. Node selector / taint mismatch

**Debugging**:

```bash
# 1. Inspect pod events
kubectl describe pod <pod-name> -n aileron

# 2. Check PVC status
kubectl get pvc -n aileron

# 3. Check StorageClass
kubectl get storageclass

# 4. Check node resources
kubectl top nodes
```

### Keycloak OIDC Redirect Fails

**Symptom**: After login, redirect back to the frontend shows an `Invalid redirect uri` error.

**Cause**: The Keycloak client's Valid Redirect URIs don't include the current domain.

**Fix**:

1. Open Keycloak Admin Console
2. `aileron` realm → Clients → `aileron-frontend`
3. Add Valid Redirect URIs:
   - Docker: `http://localhost:8082/*`
   - Kubernetes: `https://example.com/*`
4. Update Web Origins for CORS
5. Save

If editing the Helm chart realm.json, redeploy:

```bash
helm upgrade aileron helm/aileron \
  --namespace aileron
```

## Workspace Issues

### Workspace Creation Hangs

**Docker mode debugging**:

```bash
# 1. Check workspace-manager log
docker compose logs -f workspace-manager

# 2. List all workspace containers
docker ps --filter "name=workspace-"

# 3. Verify Docker socket mount
docker compose exec workspace-manager ls -la /var/run/docker.sock
```

**Kubernetes mode debugging**:

```bash
# 1. Check Workspace CR status
kubectl get workspaces -A
kubectl describe workspace <name> -n <namespace>

# 2. Check Operator logs
kubectl logs -n aileron deployment/aileron-workspace-operator

# 3. Check target namespace pods
kubectl get pods -n workspace-system
kubectl describe pod workspace-runtime-<id> -n workspace-system
```

### Canvas Stuck Loading

**Symptom**: Canvas Runtime or Runtime screen shows a perpetual loading spinner.

**Possible causes**:
1. WebSocket connection failure (timeout too short)
2. Cross-origin issue (CORS)
3. Ingress does not handle wildcard subdomains correctly
4. Database connection pool exhausted (after long runs)

**Debugging**:

```bash
# Check browser DevTools Network tab
# Look for failed WebSocket or XHR requests

# Docker mode: check runtime log
docker compose logs -f workspace-runtime

# Kubernetes mode: check corresponding workspace pod
kubectl logs workspace-runtime-<id> -n workspace-system
```

**Ingress WebSocket settings**:

```yaml
ingress:
  annotations:
    nginx.ingress.kubernetes.io/proxy-read-timeout: "3600"
    nginx.ingress.kubernetes.io/proxy-send-timeout: "3600"
    nginx.ingress.kubernetes.io/proxy-http-version: "1.1"
```

### Workspace Browser (WebRTC) Can't Connect

**Symptom**: Clicking the browser tab shows a black screen or fails to connect.

**Possible causes**:
1. CoTURN not enabled or IP misconfigured
2. UDP port 52000 blocked by firewall
3. NAT 1:1 mapping misconfigured

**Debugging**:

```bash
# Docker mode
docker compose logs workspace-browser

# Verify UDP port is reachable
nc -u -z localhost 52000

# Kubernetes mode
kubectl get svc -l app=coturn -A
kubectl logs -n aileron deployment/aileron-coturn
```

**Kubernetes CoTURN host**:

```yaml
coturn:
  # Docker Desktop K8s uses node IP
  host: "192.168.65.3"
  # Production: use actual public IP
  # host: "203.0.113.10"
```

### Claude Code Doesn't Respond

**Symptom**: Chat Panel shows no reply after sending a message, or shows an authentication error.

**Debugging**:

```bash
# Verify Anthropic API token is set
docker compose exec workspace-runtime env | grep ANTHROPIC

# Check Claude-related errors in runtime log
docker compose logs workspace-runtime | grep -i claude
```

**Common errors**:

| Message | Cause | Fix |
|---------|-------|-----|
| `Unauthorized` / `401` | Invalid or expired token | Update `ANTHROPIC_AUTH_TOKEN` |
| `Model not found` | Wrong model name | Use a supported Claude model ID |
| `Rate limit exceeded` | API quota exceeded | Wait or upgrade API quota |

## Database Issues

### PostgreSQL Directory Permission Error

**Symptom**: `./data/postgres` permission issues prevent the container from starting.

**Fix**:

```bash
# macOS / Linux
sudo chown -R 999:999 ./data/postgres

# Or full cleanup and restart
python scripts/dev/docker/ops.py cleanup
python scripts/dev/docker/ops.py up --build
```

### Connection Pool Exhausted After Long Runs

**Symptom**: After running for a long time, Manager/Runtime shows `QueuePool limit` or httpx `ENOENT` errors.

**Cause**: Zombie connections in the database connection pool are not reclaimed.

**Fix**:
- Restart the affected services: `docker compose restart workspace-manager workspace-runtime`
- Check connection pool settings (`pool_recycle`)
- This is a known issue that is being improved.

## Network Issues

### Services Can't Communicate (Docker mode)

**Symptom**: `workspace-manager` can't reach `workspace-runtime`, or vice versa.

**Debugging**:

```bash
# 1. Verify both containers are on the same network
docker network inspect aileron-network-dev

# 2. Ping from manager to runtime
docker compose exec workspace-manager ping -c 3 workspace-runtime

# 3. Check DNS resolution
docker compose exec workspace-manager nslookup workspace-runtime
```

### CORS Errors

**Symptom**: Browser console shows `Access-Control-Allow-Origin` errors.

**Possible causes**:
- Keycloak Web Origins not set
- Manager API CORS allowlist does not include the frontend domain
- In Kubernetes mode, `PUBLIC_ALLOWED_ORIGINS` misconfigured

**Fix**:

```bash
# Kubernetes: inspect platform-config
kubectl get configmap -n aileron \
  aileron-platform-config -o yaml

# Confirm PUBLIC_ALLOWED_ORIGINS includes the frontend domain
```

### Kubernetes Ingress 502 Bad Gateway

**Possible causes**:
1. Target Service is not ready
2. Service selector mismatch
3. Incorrect Ingress path

**Debugging**:

```bash
# Verify Service endpoints exist
kubectl get endpoints -n aileron

# Confirm pods are Ready
kubectl get pods -n aileron

# Check ingress-controller logs
kubectl logs -n ingress-nginx deployment/ingress-nginx-controller
```

## Performance Issues

### Container OOMKilled

**Symptom**: `kubectl get pods` or `docker compose ps` shows the container repeatedly restarting with `OOMKilled` in events.

**Fix**:

Docker mode — edit `docker-compose.yml`:

```yaml
workspace-browser:
  deploy:
    resources:
      limits:
        memory: 4G  # Increase
```

Kubernetes mode — adjust values.yaml:

```yaml
workspaceManager:
  resources:
    limits:
      memory: 1Gi  # Increase
```

### PostgreSQL Queries Getting Slower

**Debugging**:

```bash
# Connect to DB
docker compose exec postgres psql -U postgres -d aileron

# Check slow queries
SELECT query, calls, total_exec_time, mean_exec_time
FROM pg_stat_statements
ORDER BY mean_exec_time DESC
LIMIT 10;

# Check VACUUM status
SELECT relname, last_vacuum, last_autovacuum
FROM pg_stat_user_tables;
```

## Useful Debugging Commands

### Docker Mode

```bash
# Enter container shell
docker compose exec workspace-manager bash
docker compose exec workspace-runtime bash

# Tail logs for all services
docker compose logs -f

# Rebuild and start a specific service
docker compose up -d --build workspace-manager

# Inspect network
docker network inspect aileron-network-dev

# List all related containers (including dynamic workspaces)
docker ps -a --filter "name=aileron" --filter "name=workspace-"

# Prune unused volumes
docker volume prune
```

### Kubernetes Mode

```bash
# Enter pod shell
kubectl exec -it -n aileron deployment/aileron-workspace-manager -- bash

# View all resources
kubectl get all -n aileron

# Watch pod events
kubectl get events -n aileron --sort-by='.lastTimestamp'

# Tail logs for multiple pods
kubectl logs -f -l app.kubernetes.io/name=workspace-manager -n aileron

# Port-forward for local access
kubectl port-forward -n aileron svc/aileron-workspace-manager 3001:3001

# Check CRDs
kubectl get workspaces -A
kubectl describe workspace <name> -n workspace-system

# Restart a deployment
kubectl rollout restart deployment/aileron-workspace-manager -n aileron

# View all ConfigMaps
kubectl get configmap -n aileron
kubectl describe configmap aileron-platform-config -n aileron
```

## Getting Help

If none of the above resolves your issue:

1. Gather relevant logs (`docker compose logs` or `kubectl logs`)
2. Include docker compose version or Helm values
3. Describe reproduction steps
4. File an issue on [GitHub Issues](https://github.com/) or the relevant community channel
