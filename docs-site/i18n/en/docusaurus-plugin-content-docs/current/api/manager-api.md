---
sidebar_position: 1
title: Manager API
---

# Workspace Manager API

## Interactive Documentation

- **Swagger UI**: http://localhost:3001/docs
- **ReDoc**: http://localhost:3001/redoc

## Base URL

```
http://localhost:3001
```

## Authentication

Authentication is disabled by default (`ENABLE_AUTH=false`).

When Keycloak authentication is enabled, all API calls must include a Bearer token in the header:

```
Authorization: Bearer <jwt_token>
```

## Main Endpoints

### Health Check

```
GET /health
```

Response:
```json
{ "status": "ok", "database": "ok", "redis": "ok" }
```

### Workspace Management

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v1/workspaces` | List all workspaces |
| `POST` | `/api/v1/workspaces` | Create a workspace |
| `GET` | `/api/v1/workspaces/{id}` | Get workspace details |
| `PUT` | `/api/v1/workspaces/{id}` | Update a workspace |
| `DELETE` | `/api/v1/workspaces/{id}` | Delete a workspace |
| `POST` | `/api/v1/workspaces/{id}/start` | Start a workspace |
| `POST` | `/api/v1/workspaces/{id}/stop` | Stop a workspace |
| `POST` | `/api/v1/workspaces/{id}/restart` | Restart a workspace |

### Workspace Settings

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v1/workspaces/{id}/setup/*` | Get settings |
| `PUT` | `/api/v1/workspaces/{id}/setup/*` | Update settings |

### Template Management

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v1/templates` | List templates |
| `POST` | `/api/v1/templates` | Create a template |
| `GET` | `/api/v1/templates/{id}` | Get a template |
| `PUT` | `/api/v1/templates/{id}` | Update a template |
| `DELETE` | `/api/v1/templates/{id}` | Delete a template |

### Automation Tasks

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v1/automation` | List automation tasks |
| `POST` | `/api/v1/automation` | Create a task |
| `GET` | `/api/v1/automation/{id}` | Get a task |
| `PUT` | `/api/v1/automation/{id}` | Update a task |
| `DELETE` | `/api/v1/automation/{id}` | Delete a task |
| `POST` | `/api/v1/automation/{id}/trigger` | Manually trigger |

### User Management

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v1/users` | List users |
| `POST` | `/api/v1/users` | Create a user |
| `GET` | `/api/v1/users/{id}` | Get a user |
| `PUT` | `/api/v1/users/{id}` | Update a user |

### Team Management

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v1/teams` | List teams |
| `POST` | `/api/v1/teams` | Create a team |
| `POST` | `/api/v1/teams/{id}/members` | Add a member |

### Other

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v1/settings` | Platform settings |
| `GET` | `/api/v1/container-images` | Container image list |
| `GET` | `/api/v1/oauth/*` | OAuth flows |

## Error Format

```json
{
  "detail": "Error message",
  "code": "ERROR_CODE"
}
```

Common HTTP status codes:

| Status | Description |
|--------|-------------|
| `200` | Success |
| `201` | Created |
| `400` | Bad request |
| `401` | Unauthenticated |
| `403` | Forbidden |
| `404` | Not found |
| `500` | Server error |
