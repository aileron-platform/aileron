---
sidebar_position: 2
title: Service URLs & Credentials
---

# Service URLs & Credentials

Once startup is complete, the following services are available:

## Service URLs (Docker mode)

| Service | URL | Description |
|---------|-----|-------------|
| **Frontend** | http://localhost:8082 | Main UI |
| **Manager API** | http://localhost:3001 | Workspace Manager REST API |
| **Manager Swagger** | http://localhost:3001/docs | Manager interactive API docs |
| **Manager ReDoc** | http://localhost:3001/redoc | Manager ReDoc API docs |
| **Runtime API** | http://localhost:3002 | Workspace Runtime REST API |
| **Runtime Swagger** | http://localhost:3002/docs | Runtime interactive API docs |
| **Runtime ReDoc** | http://localhost:3002/redoc | Runtime ReDoc API docs |
| **Keycloak Admin** | http://localhost:8080/admin | Authentication management console |
| **Draw.io** | http://localhost:8083 | Diagram tool |
| **Flower** | http://localhost:5555 | Celery task monitoring |

## Default Credentials

### Frontend Login

```
username: admin
password: admin123
```

### Keycloak Admin Console

```
URL:      http://localhost:8080/admin
username: admin
password: admin
```

:::warning Production Environments
The credentials above are development defaults. You **must** change all passwords and secrets before any production deployment.
:::

## Health Check Endpoints

| Service | Endpoint |
|---------|----------|
| Workspace Manager | `GET http://localhost:3001/health` |
| Workspace Runtime | `GET http://localhost:3002/health` |

## Integration Tests

```bash
# Run runtime integration tests
./scripts/test/run-all-tests.sh runtime

# Run manager integration tests
./scripts/test/run-all-tests.sh manager
```
