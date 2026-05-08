# Aileron Workspace Manager

Workspace Manager is the core backend service in Aileron. It manages the full workspace lifecycle, including creation, configuration, startup, restart, and deletion.

## Capabilities

### Workspace Management

- workspace CRUD
- Docker and Kubernetes lifecycle control
- template-based workspace creation
- firewall and port mapping management

### Collaboration

- multi-user workspaces
- role-based access control
- team and member management

### Automation

- cron-based scheduling
- Claude Code assisted automation
- execution tracking

## Stack

- FastAPI
- SQLAlchemy
- PostgreSQL
- Redis
- Celery
- Docker and Kubernetes

## Layout

```text
workspace-manager/
├── app/
├── scripts/
├── tests/
├── pyproject.toml
├── Dockerfile
└── README.md
```

## Local Development

```bash
# recommended
uv pip install -e ".[dev]"

# alternative
pip install -e ".[dev]"

cp .env.example .env
python -m app.main
```

Or run with Uvicorn:

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 3001
```

## Docker

```bash
docker build -t aileron/workspace-manager .
docker compose up -d
docker compose logs -f workspace-manager
```

## Main API Areas

- `GET /health`
- `/api/v1/users/*`
- `/api/v1/teams/*`
- `/api/v1/workspaces/*`
- `/api/v1/workspaces/{workspace_id}/setup/*`
- `/api/v1/marketplace/*`
- `/api/v1/automation/*`
- `/api/v1/container-images/*`
- `/api/v1/settings`
- `/api/v1/oauth/*`

Interactive docs:

- Swagger UI: `http://localhost:3001/docs`
- ReDoc: `http://localhost:3001/redoc`

## Key Environment Variables

| Variable | Description |
|---|---|
| `DATABASE_URL` | PostgreSQL connection URL |
| `REDIS_URL` | Redis connection URL |
| `SECRET_KEY` | JWT signing key |
| `DOCKER_HOST` | Docker host |
| `DEBUG` | debug mode |

### Optional Keycloak Settings

| Variable | Description |
|---|---|
| `ENABLE_AUTH` | enable Keycloak OAuth2/OIDC |
| `KEYCLOAK_SERVER_URL` | Keycloak server URL |
| `KEYCLOAK_REALM` | realm name |
| `KEYCLOAK_CLIENT_ID` | OAuth client ID |
| `KEYCLOAK_CLIENT_SECRET` | OAuth client secret |
| `JWT_ALGORITHM` | JWT verification algorithm |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | access token lifetime |

See `.env.example` for the full configuration surface.

### Knowledge Base Maintenance

Knowledge Base storage uses the manager-side directory configured by `MANAGER_KNOWLEDGE_BASES_DIR`.

Celery Beat runs two daily maintenance jobs:

- `knowledge_bases.reconcile_kb_quota` at `02:00` (`TZ`-aware): scans every non-tombstoned KB directory and refreshes `knowledge_bases.current_size_bytes`
- `knowledge_bases.cleanup_tombstoned_kb` at `03:00` (`TZ`-aware): removes KB directories past `KB_TOMBSTONE_RETENTION_HOURS` and deletes their DB records

Relevant settings:

| Variable | Description |
|---|---|
| `MANAGER_KNOWLEDGE_BASES_DIR` | workspace-manager sees KB files under this path |
| `DEFAULT_USER_KB_QUOTA_BYTES` | total KB quota per owner |
| `DEFAULT_KB_QUOTA_BYTES` | default quota per KB |
| `KB_SINGLE_FILE_SIZE_LIMIT` | max file size per KB file |
| `KB_ALLOWED_EXTENSIONS` | allowed KB file extension whitelist |
| `KB_TOMBSTONE_RETENTION_HOURS` | retention window before tombstoned KB cleanup |

## Tests

```bash
# all tests
pytest

# with coverage
pytest --cov=app --cov-report=html

# a specific file
pytest tests/test_workspaces.py -v
```

### Containerized Verification

Prefer containerized tests when possible:

```bash
make test-workspaces
make lint-workspaces
make verify-workspaces
```

## Monitoring

- Flower: `http://localhost:5555`
- health check: `http://localhost:3001/health`

## Security

- JWT authentication
- RBAC
- CORS controls
- Pydantic validation
