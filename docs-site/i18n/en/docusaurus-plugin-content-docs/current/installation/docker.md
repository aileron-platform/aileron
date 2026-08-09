---
title: Docker Mode
---

# Docker Deployment

## When to Use It

- Local development and debugging
- Quickly evaluating the complete platform
- Environments that do not need Kubernetes, Operator, or Cilium
- Single-host deployments

## Requirements

- [Docker](https://docs.docker.com/get-docker/) (24.0+ recommended)
- [Docker Compose](https://docs.docker.com/compose/install/) (V2, usually included with Docker Desktop)
- [Git LFS](https://git-lfs.com/) (optional; required when a Knowledge Base enables Git LFS and manages large files under `raw/`)
- At least 4 vCPUs
- At least 8 GB of available memory
- 12–16 GB of available memory recommended for more stable browser and agent workflows
- At least 30 GB of free disk space
- 50 GB of free disk space recommended to avoid images, volumes, and workspace data quickly exhausting storage

## Service Architecture

In Docker mode, the root `docker compose` manages only the control plane. Workspace Manager uses the Docker API to create an isolated execution plane for each running Workspace:

```text
Frontend / Manager / external OIDC or development IdP fixture
               |
       Workspace Manager + Docker API
               |
       +-------------------------------------+
       | Workspace A: Runtime/Browser/Canvas |
       | Workspace B: Runtime/Browser/Canvas |
       +-------------------------------------+

PostgreSQL and Redis provide control-plane infrastructure.
```

### Services

| Service | Image | Description |
|------|------|------|
| **postgres** | `postgres:15-alpine` | Primary platform database |
| **redis** | `redis:7-alpine` | Task queue (Celery broker), result backend, and session management |
| **openldap** | `osixia/openldap:1.5.0` | LDAP directory for local account-lifecycle development |
| **openldap-seed** | `osixia/openldap:1.5.0` | One-shot local LDAP seed job; exits after success |
| **turn-readiness-preflight** | `ailerondocker/workspace-manager:dev` | Validates the TURN profile, secret bundle, image, and relay ports before startup |
| **coturn** | `${COTURN_IMAGE}` | TURN control listener and relay UDP range |
| **connectivity-evidence-gateway** | `${WORKSPACE_OPERATOR_IMAGE}` | Accepts host frontend-vantage challenges and evidence |
| **connectivity-external-agent** | `${WORKSPACE_OPERATOR_IMAGE}` | Runs TURN probes from the host-network frontend vantage |
| **runtime-assertion-key-init** | `ailerondocker/workspace-manager:dev` | One-shot Runtime assertion key generation; exits after success |
| **identity-bootstrap** | `ailerondocker/workspace-manager:dev` | One-shot local platform-role and administrator-snapshot bootstrap; never creates a provider password |
| **workspace-manager** | `ailerondocker/workspace-manager:dev` | Core management service: Workspace CRUD, permissions, lifecycle, and dynamic execution-plane provisioning |
| **frontend** | `ailerondocker/workspace-ui:dev` | React + Vite development server |
| **drawio** | `jgraph/drawio` | Embedded diagram editor |

These thirteen names are the complete root Compose service list. Celery worker, Celery Beat, and
Flower are not separate Compose services; Supervisor runs them inside the `workspace-manager`
container. Flower is available only on the deployment-internal network.

Manager creates the following containers dynamically for each Workspace; they are not present in the root `docker-compose.yml`:

| Container | Description |
|------|------|
| **workspace-runtime-&lt;workspace-id&gt;** | Agent Runtime, Terminal, file, and Git APIs |
| **workspace-browser-&lt;workspace-id&gt;** | neko WebRTC browser and CDP |
| **workspace-canvas-&lt;workspace-id&gt;** | Workspace Canvas rendering and management API |

:::info Git LFS and Knowledge Bases
Git version control is optional for each Knowledge Base. The Manager environment needs the `git lfs` command only when a Knowledge Base enables Git LFS. To track large PDFs, images, archives, or other `raw/` source files with LFS, confirm that Git LFS is installed in the `workspace-manager` image.
:::

See [Install and Start](./getting-started) for first startup, service-status checks, stopping, and cleanup. `docker buildx bake --load local` builds all images required by the control plane and execution planes. `docker compose up --no-build` starts only the control plane; Manager still creates Runtime, Browser, and Canvas dynamically.

In Aileron, the complete Docker Compose stack is both a deployment option and the default local development mode. Daily module development assumes that the full service set is running, with development mounts and each service's reload mechanism reflecting source changes.

See [Service Endpoints and Accounts](./service-endpoints) for service URLs, default accounts, and health-check endpoints.

## Version and Dependency Ownership

Each source type owns its versions; neither `ops.py` nor Compose duplicates them:

| Type | Single source | Rule |
|------|----------|------|
| Image toolchains such as Python, Node.js, npm, pnpm, uv, Claude Code, Codex, OpenCode, Playwright CLI, and Maven | Root `docker-bake.hcl` | Dockerfiles accept build arguments with no defaults |
| Frontend and Canvas npm packages | Their respective `package.json` and `package-lock.json` | Reproduce the lockfile with `npm ci` |
| Manager and Runtime Python packages | Their respective `pyproject.toml` and `uv.lock` | Build from a frozen lockfile |
| Go modules | Their respective `go.mod` and `go.sum` | Reproduce the Go module lock state |
| Runtime service images such as PostgreSQL, Redis, an OIDC adapter, and Draw.io | `docker-compose.yml` or Helm values | Managed separately from the application build toolchain |

When updating a toolchain version, change only `docker-bake.hcl` and update checksum fields together. Do not add another numeric version to a Dockerfile, Compose file, Makefile, shell script, or `ops.py`.

Inspect the final Bake resolution without building:

```bash
docker buildx bake --print local
docker buildx bake --print release
```

The RKE2 release script resolves toolchain versions through the same Bake targets before applying Registry, tag, and `linux/amd64` settings. Local, CI, and release flows therefore do not maintain build arguments independently.

## Environment Variables

See [Environment Variable Reference](./environment-variables) for the complete list. The variables below can be set in the shell or an `.env` file and affect overall Docker Compose behavior. Refer to the full environment-variable page for service-specific settings.

| Variable | Default | Description |
|------|--------|------|
| `PLATFORM_PUBLIC_ORIGIN` | `http://localhost:8082` | Sole browser-visible Origin; no path or trailing slash |
| `OIDC_ISSUER_URL` | `http://localhost:8080/realms/aileron` | Canonical external Provider issuer |
| `OIDC_CLIENT_ID` | `aileron-manager` | Manager confidential client ID |
| `TZ` | `Asia/Taipei` | System time zone |
| `HOST_PROJECT_ROOT` | `.` | Absolute path to the project root on the host |
| `HOST_PLATFORM_SECRETS_DIR` | Required | Directory containing PostgreSQL, OIDC client, and platform Secret files |
| `HOST_WORKSPACES_DIR` | `./data/workspace-data` | Workspace data storage path |
| `HOST_WORKSPACE_SCRIPTS_DIR` | `./data/workspace-scripts` | Workspace scripts storage path |
| `HOST_RUNTIME_HOME_DIR` | `./data/runtime-home` | Root for each dynamic Runtime's complete user HOME |
| `WORKSPACE_OPERATOR_IMAGE` | `ailerondocker/workspace-operator:dev` | Existing Operator image used by the Gateway, host agent, and Browser probe |
| `COTURN_IMAGE` | `ailerondocker/platform-coturn:dev` | Coturn image, supplied locally or by the deployer |
| `HOST_TURN_CONFIG_DIR` | `./data/turn-config` | Host directory containing the canonical TURN profile |
| `HOST_TURN_SECRETS_DIR` | `./data/turn-secrets` | Directory containing the TURN REST, backend/frontend ICE, Coturn, Gateway, and host-agent secret bundle |
| `TURN_CREDENTIAL_REVISION` | `docker-compose-v1` | Credential revision for this installation |
| `TURN_RELAY_MIN_PORT` / `TURN_RELAY_MAX_PORT` | `49160` / `49180` | Relay range that must exactly match `backend.relayPortRange` in the profile |
| `TURN_CONNECTIVITY_GATEWAY_EXTERNAL_PORT` | `18083` | Gateway host port used by the host agent |
| `VITE_BROWSER_EXTENSION_ID` | Empty | Browser-extension capability flag with a proven consumer |

:::tip .env file
Create `.env` in the project root and Docker Compose loads it automatically.
:::

### Local OIDC Secrets

When the `local-oidc` profile is enabled, `${HOST_PLATFORM_SECRETS_DIR}` must also
contain `local-admin-password`, `ldap-admin-password`, `ldap-config-password`,
`ldap-alice-password`, and `ldap-bob-password`. OpenLDAP reads the mounted files
through the image-native `*_FILE` adapter; after first-start initialization, the
long-running `slapd` argv and environment contain no Secret value. Keycloak imports
the `aileron` realm with its local emergency administrator and does not create a
master-realm bootstrap administrator, so no separate Keycloak admin Secret is needed.

`ldap-admin-password` and `ldap-config-password` contain the exact password bytes and
must not include surrounding whitespace or a trailing newline. `local-oidc-config`
validates this contract before OpenLDAP starts and fails closed on invalid files.

### TURN readiness bundle

Dynamic Browsers do not publish per-container WebRTC media ports. Neko uses the
same TURN-compatible profile as Kubernetes, and Coturn relays browser traffic to
the Browser container on the Compose network.

Docker Compose runs `turn-readiness-preflight` before Coturn, the Gateway, host agent,
Manager, and identity bootstrap. The deployer must create these files; missing, empty,
or inconsistent files fail closed:

```text
${HOST_TURN_CONFIG_DIR}/turn-reachability-profile.json
${HOST_TURN_SECRETS_DIR}/turn-rest-shared-secret
${HOST_TURN_SECRETS_DIR}/turn-backend-ice-servers.json
${HOST_TURN_SECRETS_DIR}/turn-frontend-ice-servers.json
${HOST_TURN_SECRETS_DIR}/coturn-auth-secret
${HOST_TURN_SECRETS_DIR}/gateway-internal-token
${HOST_TURN_SECRETS_DIR}/host-agent-token
${HOST_TURN_SECRETS_DIR}/connectivity-agent-tokens.json
```

`turn-rest-shared-secret` and `coturn-auth-secret` must match, while
`connectivity-agent-tokens.json` must contain the same `host` value as
`host-agent-token`. The profile is the single installation source of truth and must
declare `credentialIssuer.kind=turnRest`,
`credentialIssuer.secretRef=turn-rest-shared-secret`, and a `host` entry in
`requiredFrontendVantages`. Do not commit the profile or secrets to Git.

Use the repository contract as a local starting point:

```bash
mkdir -p data/turn-config data/turn-secrets
cp contracts/browser-connectivity/turn-reachability-profile.json \
  data/turn-config/turn-reachability-profile.json
export HOST_PROJECT_ROOT="$PWD"
turn_secret="$(openssl rand -hex 32)"
printf '%s\n' "$turn_secret" > data/turn-secrets/turn-rest-shared-secret
printf '%s\n' '[{"urls":["turn:coturn:3478"]}]' > data/turn-secrets/turn-backend-ice-servers.json
printf '%s\n' '[{"urls":["turn:127.0.0.1:3478"]}]' > data/turn-secrets/turn-frontend-ice-servers.json
printf '%s\n' "$turn_secret" > data/turn-secrets/coturn-auth-secret
printf '%s\n' "$(openssl rand -hex 32)" > data/turn-secrets/gateway-internal-token
agent_token="$(openssl rand -hex 32)"
printf '%s\n' "$agent_token" > data/turn-secrets/host-agent-token
printf '{"host":"%s"}\n' "$agent_token" > data/turn-secrets/connectivity-agent-tokens.json
chmod 600 data/turn-secrets/*
chmod 600 data/turn-config/turn-reachability-profile.json
```

Manager starts each Browser connectivity probe with the owner UID/GID of these
bind-mounted files. The profile, TURN REST Secret, and backend ICE server file must
therefore have the same owner; an owner mismatch fails Browser generation closed. The
backend ICE server file uses the Compose-network Coturn address, while the frontend
ICE server file uses an address reachable by the browser. The Compose service continues
to run with only the minimum capabilities.

The `workspace-operator` image must contain the `connectivity-evidence-gateway`,
`connectivity-external-agent`, and `browser-connectivity-probe` binary modes. Compose
does not hide a build or pull an alternate image during startup. The default macOS and
Linux host vantage uses host networking, and the frontend TURN URL must be reachable
from both the local browser and host agent.

## Volume Mounts

### Persistent Data

| Host path | Container path | Description |
|------|----------|------|
| `./data/postgres` | `/var/lib/postgresql/data` | PostgreSQL data |
| `./data/redis` | `/data` | Redis persistent data |
| `./data/workspace-data` | `/host/workspace-data` | Workspace project files managed by Manager; dynamic containers mount the corresponding subdirectory |
| `./data/workspace-scripts` | `/host/workspace-scripts` | Workspace scripts managed by Manager |
| `./data/runtime-home/<workspace-id>` | `/home/developer` in the dynamic Runtime | Complete user HOME, preserving agent logins, settings, XDG state, Maven state, and user-installed tools |

Built-in platform CLIs are not installed in persistent HOME. uv, Node.js, npm, pnpm, and Claude Code are on system paths; Codex and Playwright CLI are under `/opt/aileron/npm`; OpenCode is under `/opt/aileron/bin`. Clearing HOME therefore removes user state but not tools built into the image.

### Development Mounts

These mounts are the core of local development mode. Compose mounts control-plane services; Manager mounts Runtime source and Terminal when it creates a dynamic Runtime.

| Host path | Container path | Purpose |
|------|----------|------|
| `./workspace-manager` | `/workspace-manager` | Manager code hot reload |
| `./workspace-runtime` | `/workspace-runtime` in a dynamic Runtime | Runtime source mounted by Manager |
| `./workspace-terminal` | `/workspace-terminal` in a dynamic Runtime | Terminal source mounted by Manager |
| `./frontend` | `/app` | Frontend code hot reload |
| `/var/run/docker.sock` | `/var/run/docker.sock` | Docker socket for container management |

### Development and Production Images

Aileron Bake targets and tags have explicit meanings:

| Type | Example tag | Code source | Deployment |
|------|----------|------------|----------|
| Local development | `dev`, `dev-lite`, `dev-java` | Host code mounted through volumes | Docker Compose development mode |
| Production | `${RELEASE_TAG}` | Code packaged into the image | Production Docker image |
| Kubernetes | `${RELEASE_TAG}-kubernetes` | Packaged code using a non-root target | Kubernetes, Helm, and RKE2 |

Local tags do not include the CPU architecture. Bake creates an executable image for the build platform. CI or the RKE2 release flow explicitly selects the platform for cross-platform publishing.

:::caution Docker socket mount
`workspace-manager` and every Runtime created by the Docker provisioner mount `/var/run/docker.sock`; the Runtime mount is not selected per tool. This grants the container high-privilege control over the host Docker daemon and is suitable only for a trusted local development environment. Kubernetes Runtimes do not mount the host Docker socket. Use Kubernetes mode in production.
:::

## Network Configuration

All services use the same `aileron-network-dev` bridge network.

Services reach one another by container name through Docker Compose's built-in DNS, for example:

- `postgres:5432`
- `redis:6379`
- `workspace-manager:3001`
- `workspace-runtime-<workspace-id>:3002`

Docker Compose does not install an IdP. Configure `OIDC_ISSUER_URL` for the
installation-owned external provider. Discovery is always `{issuer}/.well-known/openid-configuration`,
and the document's `issuer` must match exactly. `PLATFORM_PUBLIC_ORIGIN` is the sole browser entry
point; callback, logout, and CORS derive from it.

## Resource Requirements

| Service | CPU | Memory | Description |
|------|-----|--------|------|
| workspace-browser | 2-core limit | 2 GB limit / 1 GB reservation | neko WebRTC is the most resource-intensive component |
| workspace-browser | — | 2 GB SHM | Shared memory required by Chrome |
| Other services | Unlimited | Unlimited | Allocated dynamically according to actual use |

:::tip Recommended configuration
For single-host evaluation and basic flow validation, use at least `4 vCPU / 8 GB RAM / 30 GB` of free disk. For more stable browser and automation workflows with an OIDC adapter and multiple concurrent services, use `6–8 vCPU / 12–16 GB RAM / 50 GB` of free disk. If the same host also runs Harbor, another Registry, large containers, or additional development services, start with at least `16 GB RAM` to avoid swap or disk exhaustion.
:::

## Common Commands

Build all local images:

```bash
docker buildx bake --load local
```

Start with existing images, or stop non-destructively while preserving data:

```bash
docker compose up --remove-orphans --no-build -d
make down
```

Run container tests and retain the same images as the final local artifacts:

```bash
make verify-local
```

Follow logs:

```bash
docker compose logs -f
docker compose logs -f workspace-manager
docker logs -f workspace-runtime-<workspace-id>
```

Run the project's only destructive host-side full reset:

```bash
make full-reset
```

`docker compose` manages only control-plane services. Starting, stopping, restarting, or deleting an individual Workspace must go through the Manager UI or API; do not operate its dynamic containers directly. `ops.py up --build` remains available as a convenience wrapper, but internally it only calls Bake followed by Compose and owns no version or architecture decisions. `make down` is a non-destructive stop that preserves volumes, PostgreSQL, and Workspace persistent data.

Startup includes Compose `--remove-orphans`, which removes containers no longer present in the configuration for the same Compose project. Docker Compose only handles orphans with the same project label; dynamically created Workspace containers and other test projects are outside this scope.

## Full Reset

`full-reset` is the only destructive local-environment reset available from the host. Permanent deletion of an individual Workspace must use the Manager UI or API and must not be replaced by host-side container cleanup.

```bash
make full-reset
```

This flow:

1. Deletes all dynamic Workspace containers.
2. Stops all Docker Compose services.
3. Deletes Docker volumes whose names match the `aileron` filter.
4. Deletes Docker networks whose names match the `aileron` filter.
5. Asks whether to delete project Docker images.
6. Clears container-generated files under `data/`, including PostgreSQL, Redis, optional adapter, and Workspace data.
7. Clears listed project and `/tmp` directories.
8. Asks whether to run `docker system prune -f --volumes`.

`full-reset` completes only after confirming that all dynamic Workspace containers and local persistent data under `data/`, including PostgreSQL, Redis, Workspace data, and Runtime homes, have been removed. Any required cleanup failure must produce a non-zero exit status.

The direct resource discovery in the first seven steps is limited to Aileron Workspace containers, volumes and networks whose names match `aileron`, project images, and the listed data directories. Step 8 is a global Docker prune. When confirmed, Docker additionally removes global containers, networks, images, build cache, and volumes that it considers unused, including unused resources from other projects.

:::danger
`full-reset` deletes Aileron database data, including users, Workspace settings, and templates. Confirming the global prune may also delete unused Docker resources from other projects. Back up data and read every interactive prompt before continuing.
:::

Restart after the full reset:

```bash
docker buildx bake --load local
docker compose up --remove-orphans --no-build -d
```

## Health Checks

The control-plane services in the root Compose stack define health checks:

| Service | Check | Interval | Initial delay |
|------|----------|------|----------|
| postgres | `pg_isready` | 10s | — |
| redis | `redis-cli ping` | 10s | — |
| development-only OIDC fixture (when enabled) | TCP port 8080 | 30s | 60s |
| workspace-manager | HTTP `/health` | 30s | — |
| frontend | HTTP `/` | 30s | — |

Manager lifecycle reconciliation owns dynamic execution-plane health and each component revision. Query Runtime health through `/workspaces/{workspaceId}/runtime/health` on the same Origin, not through a separate hostname or localhost port.

## Docker and Kubernetes Responsibilities

| Area | Docker mode | Kubernetes mode |
|------|-------------|-----------------|
| Service management | `docker compose` | Helm + Operator |
| Workspace lifecycle | Docker container | Pod + internal Service; public traffic uses Frontend's gateway |
| Network isolation | Docker bridge network | Cilium Network Policy |
| Storage | Host volume mount | PVC (Persistent Volume Claim) |
| Authentication | Required (external OIDC or the local development IdP fixture) | Required (external OIDC provider with Ingress TLS) |
| Best suited for | Development, testing, demos | Production and multi-user collaboration |

For Kubernetes deployment, see [Kubernetes Mode](./kubernetes).
