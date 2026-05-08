---
sidebar_position: 2
title: Workspace Manager
---

# Workspace Manager

## Overview

Workspace Manager is the core service of Aileron, responsible for managing the full lifecycle of development workspaces — including creation, configuration, start, stop, and deletion.

## Core Features

### Workspace Management
- **CRUD**: create, read, update, delete workspaces
- **Container management**: Docker / Kubernetes container lifecycle control
- **Marketplace support**: manage agent packages and provider settings
- **Network configuration**: firewall rules and port mapping management

### Team Collaboration
- **Multi-user support**: workspace member management
- **Permission control**: role-based access control (RBAC)
- **Team management**: team creation and member invitations

### Automation Tasks
- **Cron scheduling**: scheduled tasks using Cron expressions
- **AI integration**: automation tasks that can drive agent workflows, with Claude Code currently the most complete
- **Execution monitoring**: track task status and results

## Technical Architecture

| Component | Technology |
|-----------|------------|
| Web framework | FastAPI |
| ORM | SQLAlchemy |
| Database | PostgreSQL |
| Cache / queue | Redis |
| Background tasks | Celery |
| Container management | Docker / Kubernetes |
| Authentication | Keycloak JWT |

## Directory Structure

```
workspace-manager/
├── app/
│   ├── celery/            # Celery background task configuration
│   ├── config/            # Configuration modules
│   ├── core/              # Core functionality
│   ├── db/                # Database connection and migrations
│   ├── jinja_templates/   # Jinja2 templates
│   ├── middleware/        # Middleware
│   ├── models/            # SQLAlchemy models
│   ├── modules/           # Feature modules
│   ├── routers/           # API routes
│   ├── services/          # Business logic layer
│   ├── tasks.py           # Celery task definitions
│   ├── translations/      # i18n resources
│   └── utils/             # Utility functions
├── scripts/               # Deployment scripts
├── tests/                 # Tests
├── pyproject.toml
└── Dockerfile
```

## Environment Variables

### Basic Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | — | PostgreSQL connection URL |
| `REDIS_URL` | — | Redis connection URL |
| `SECRET_KEY` | — | JWT signing secret |
| `DOCKER_HOST` | `unix:///var/run/docker.sock` | Docker host |
| `DEBUG` | `false` | Debug mode |

### Keycloak Authentication (Optional)

| Variable | Default | Description |
|----------|---------|-------------|
| `ENABLE_AUTH` | `false` | Enable Keycloak OAuth2/OIDC |
| `KEYCLOAK_SERVER_URL` | — | Keycloak server URL (with realm) |
| `KEYCLOAK_REALM` | `aileron` | Keycloak realm name |
| `KEYCLOAK_CLIENT_ID` | — | OAuth2 client ID |
| `KEYCLOAK_CLIENT_SECRET` | — | OAuth2 client secret |
| `JWT_ALGORITHM` | `RS256` | JWT verification algorithm |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | `30` | Access token expiry (minutes) |

### Enabling Keycloak Authentication

1. Set `ENABLE_AUTH=true`
2. Configure Keycloak-related environment variables
3. Restart the service

:::note
Once authentication is enabled, all API endpoints require a valid JWT token.
:::

## Local Development

```bash
docker compose up -d workspace-manager
```

For local development, `workspace-manager` should be started through Docker Compose and should normally run alongside the rest of the stack. Compose mounts `./workspace-manager` into `/workspace-manager` inside the container, so code changes are usually picked up through the existing reload behavior.

If the dependent services are not already running, start the full stack instead:

```bash
docker compose up -d
```

## Testing

```bash
# Run all tests
pytest

# Run tests with coverage
pytest --cov=app --cov-report=html

# Containerized tests (recommended)
make test-workspaces

# Lint and static checks
make lint-workspaces
```

:::tip Containerized Tests
Prefer containerized tests to avoid validation failures caused by missing PostgreSQL headers or Python dependencies on the host.
:::

## Monitoring

| Service | URL | Description |
|---------|-----|-------------|
| Health endpoint | `http://localhost:3001/health` | Confirm service, DB, and Redis status |
| Swagger UI | `http://localhost:3001/docs` | Interactive API docs |
| ReDoc | `http://localhost:3001/redoc` | Static API docs |
| Flower | `http://localhost:5555` | Celery task monitoring |
