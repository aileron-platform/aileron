#!/bin/sh
set -eu

usage() {
  cat <<'EOF'
用法：
  docker run --rm \
    -v /var/run/docker.sock:/var/run/docker.sock \
    -v /tmp/aileron-compose-e2e:/tmp/aileron-compose-e2e \
    -v "$PWD:/repo:ro" -w /repo \
    -e COMPOSE_E2E_HOST_REPO_ROOT="$PWD" \
    docker:27-cli sh scripts/test/compose-e2e/run.sh [--preflight-only]
EOF
}

preflight_only=false
case "${1-}" in
  "") ;;
  --preflight-only) preflight_only=true ;;
  --help|-h) usage; exit 0 ;;
  *) usage >&2; exit 2 ;;
esac

fail() {
  echo "COMPOSE_E2E_PRECHECK_FAILED: $*" >&2
  exit 1
}

log() {
  echo "[compose-e2e] $*"
}

random_hex() {
  od -An -N32 -tx1 /dev/urandom | tr -d ' \n'
}

test -f /.dockerenv || fail "run.sh must execute inside a container"
command -v docker >/dev/null 2>&1 || fail "docker CLI is unavailable"
docker info >/dev/null 2>&1 || fail "Docker daemon is unavailable"
docker compose version >/dev/null 2>&1 || fail "Docker Compose plugin is unavailable"

repo_root=$(pwd)
case "$repo_root" in
  /*) ;;
  *) fail "repository path must be absolute" ;;
esac
test -f "$repo_root/docker-compose.yml" || fail "run from the repository root"
test -f "$repo_root/PLATFORM-CONFIGURATION-DESIGN.md" || fail "platform design is unavailable"

host_repo_root="${COMPOSE_E2E_HOST_REPO_ROOT:-$repo_root}"
case "$host_repo_root" in
  /*) ;;
  *) fail "host repository path must be absolute" ;;
esac

state_parent="${COMPOSE_E2E_STATE_PARENT:-/tmp/aileron-compose-e2e}"
case "$state_parent" in
  /*) ;;
  *) fail "state parent must be an absolute path" ;;
esac
case "$state_parent" in
  "$repo_root"|"$repo_root"/*) fail "state parent must be outside the repository" ;;
esac
mkdir -p "$state_parent"

for stale_root in "$state_parent"/run-*; do
  [ -d "$stale_root" ] || continue
  stale_project_file="$stale_root/.compose-project"
  [ -f "$stale_project_file" ] || continue
  stale_project=$(tr -d '\r\n' < "$stale_project_file")
  case "$stale_project" in
    aileron-compose-e2e-*) ;;
    *) continue ;;
  esac
  if [ -z "$(docker ps -aq --filter "label=com.docker.compose.project=$stale_project")" ]; then
    case "$stale_root" in
      "$state_parent"/run-*) rm -rf "$stale_root" ;;
    esac
  fi
done

run_id="$(date +%Y%m%d%H%M%S)-$$-$(random_hex | cut -c1-8)"
project="aileron-compose-e2e-$run_id"
network="$project-network"
state_root=$(mktemp -d "$state_parent/run-$run_id-XXXXXX")
mirror_root="$state_root/root"
result_root="$state_root/results"
env_file="$state_root/compose.env"
compose_file="$state_root/compose.yml"
resolved_file="$state_root/resolved.yml"
workspace_id_file="$result_root/workspace-id"
initial_running_file="$state_root/initial-running"
renderer_image="ailerondocker/workspace-manager:dev"

mkdir -p "$mirror_root/data" "$result_root"
printf '%s\n' "$project" > "$state_root/.compose-project"

cleanup() {
  original_status=$?
  trap - EXIT INT TERM
  cleanup_status=0
  set +e
  project_container_ids=$(docker ps -aq \
    --filter "label=com.docker.compose.project=$project")

  if [ "$original_status" -ne 0 ] && [ -f "$env_file" ] \
    && [ -n "$project_container_ids" ]; then
    log "Collecting isolated project diagnostics"
    docker compose --env-file "$env_file" -p "$project" \
      -f "$compose_file" \
      --profile local-oidc ps >&2
    docker compose --env-file "$env_file" -p "$project" \
      -f "$compose_file" \
      --profile local-oidc logs --no-color --tail 200 >&2
  fi

  if [ -s "$workspace_id_file" ]; then
    workspace_id=$(tr -d '\r\n' < "$workspace_id_file")
    case "$workspace_id" in
      [0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f]-[0-9a-f][0-9a-f][0-9a-f][0-9a-f]-[0-9a-f][0-9a-f][0-9a-f][0-9a-f]-[0-9a-f][0-9a-f][0-9a-f][0-9a-f]-[0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f])
        dynamic_ids=$(docker ps -aq --filter "label=aileron.workspace_id=$workspace_id")
        if [ -n "$dynamic_ids" ]; then
          log "Removing only dynamic containers labeled for Workspace $workspace_id"
          docker rm -f $dynamic_ids >/dev/null || cleanup_status=1
        fi
        ;;
      *)
        echo "Refusing dynamic cleanup for invalid Workspace ID" >&2
        cleanup_status=1
        ;;
    esac
  fi

  if [ -f "$env_file" ] && [ -n "$project_container_ids" ]; then
    log "Removing isolated Compose project $project"
    docker compose --env-file "$env_file" -p "$project" \
      -f "$compose_file" \
      --profile local-oidc --profile compose-e2e \
      down --volumes --remove-orphans >/dev/null 2>&1 || cleanup_status=1
  fi

  if [ -f "$initial_running_file" ]; then
    while IFS= read -r container_id; do
      [ -n "$container_id" ] || continue
      if ! docker inspect -f '{{.State.Running}}' "$container_id" 2>/dev/null | grep -q '^true$'; then
        echo "Pre-existing live container was not preserved: $container_id" >&2
        cleanup_status=1
      fi
    done < "$initial_running_file"
  fi

  case "$state_root" in
    "$state_parent"/*) rm -rf "$state_root" ;;
    *) echo "Refusing to remove unexpected state path: $state_root" >&2; cleanup_status=1 ;;
  esac

  if [ "$original_status" -ne 0 ]; then
    exit "$original_status"
  fi
  exit "$cleanup_status"
}
trap cleanup EXIT HUP INT TERM

for source_path in \
  workspace-manager workspace-runtime workspace-terminal workspace-canvas \
  workspace-chrome frontend packages contracts helm scripts local-oidc init-sql \
  docker-compose.yml docker-bake.hcl; do
  test -e "$repo_root/$source_path" || fail "required source path is missing: $source_path"
  ln -s "$host_repo_root/$source_path" "$mirror_root/$source_path"
done

for data_path in \
  postgres redis workspace-data workspace-scripts runtime-home browser-credentials \
  knowledge-bases runtime-assertions init-scripts openldap openldap-config \
  platform-secrets turn-config turn-secrets; do
  mkdir -p "$mirror_root/data/$data_path"
done
chmod 0700 "$mirror_root/data/platform-secrets" "$mirror_root/data/turn-config" "$mirror_root/data/turn-secrets"
chmod 0770 "$mirror_root/data/knowledge-bases"

postgres_password=$(random_hex)
oidc_client_secret=$(random_hex)
local_admin_password="E2e-$(random_hex)-Aa9!"
ldap_admin_password=$(random_hex)
ldap_config_password=$(random_hex)
ldap_alice_password=$(random_hex)
ldap_bob_password=$(random_hex)
turn_secret=$(random_hex)
gateway_token=$(random_hex)
agent_token=$(random_hex)

printf '%s\n' "$postgres_password" > "$mirror_root/data/platform-secrets/postgres-password"
printf 'postgres:5432:aileron:postgres:%s\n' "$postgres_password" > "$mirror_root/data/platform-secrets/postgres-passfile"
printf '%s\n' "$oidc_client_secret" > "$mirror_root/data/platform-secrets/oidc-client-secret"
printf '%s\n' "$local_admin_password" > "$mirror_root/data/platform-secrets/local-admin-password"
printf '%s' "$ldap_admin_password" > "$mirror_root/data/platform-secrets/ldap-admin-password"
printf '%s' "$ldap_config_password" > "$mirror_root/data/platform-secrets/ldap-config-password"
printf '%s\n' "$ldap_alice_password" > "$mirror_root/data/platform-secrets/ldap-alice-password"
printf '%s\n' "$ldap_bob_password" > "$mirror_root/data/platform-secrets/ldap-bob-password"
chmod 0600 "$mirror_root/data/platform-secrets"/*

sed 's#turn:127.0.0.1:3478#turn:coturn:3478#g' \
  "$repo_root/contracts/browser-connectivity/turn-reachability-profile.json" \
  > "$mirror_root/data/turn-config/turn-reachability-profile.json"
printf '%s\n' "$turn_secret" > "$mirror_root/data/turn-secrets/turn-rest-shared-secret"
printf '%s\n' '[{"urls":["turn:coturn:3478"]}]' > "$mirror_root/data/turn-secrets/turn-backend-ice-servers.json"
printf '%s\n' '[{"urls":["turn:coturn:3478"]}]' > "$mirror_root/data/turn-secrets/turn-frontend-ice-servers.json"
printf '%s\n' "$turn_secret" > "$mirror_root/data/turn-secrets/coturn-auth-secret"
printf '%s\n' "$gateway_token" > "$mirror_root/data/turn-secrets/gateway-internal-token"
printf '%s\n' "$agent_token" > "$mirror_root/data/turn-secrets/host-agent-token"
printf '{"host":"%s"}\n' "$agent_token" > "$mirror_root/data/turn-secrets/connectivity-agent-tokens.json"
chmod 0600 "$mirror_root/data/turn-config/turn-reachability-profile.json" "$mirror_root/data/turn-secrets"/*

cat > "$env_file" <<EOF
PLATFORM_PUBLIC_ORIGIN=http://127.0.0.1:8082
OIDC_ISSUER_URL=http://workspace-manager:8080/realms/aileron
OIDC_CLIENT_ID=aileron-manager
ENV=development
TZ=Asia/Taipei
AILERON_INSTALLATION_ID=$project
BOOTSTRAP_ADMIN_SUBJECT=00000000-0000-4000-8000-000000000001
BOOTSTRAP_ADMIN_USERNAME=admin
BOOTSTRAP_ADMIN_EMAIL=admin@compose-e2e.invalid
HOST_PROJECT_ROOT=$mirror_root
HOST_PLATFORM_SECRETS_DIR=$mirror_root/data/platform-secrets
HOST_TURN_CONFIG_DIR=$mirror_root/data/turn-config
HOST_TURN_SECRETS_DIR=$mirror_root/data/turn-secrets
TURN_CREDENTIAL_REVISION=$project
TURN_CONNECTIVITY_GATEWAY_EXTERNAL_PORT=0
TURN_RELAY_MIN_PORT=49160
TURN_RELAY_MAX_PORT=49180
VITE_BROWSER_EXTENSION_ID=
WORKSPACE_MANAGER_IMAGE=ailerondocker/workspace-manager:dev
WORKSPACE_OPERATOR_IMAGE=ailerondocker/workspace-operator:dev
WORKSPACE_RUNTIME_IMAGE=ailerondocker/workspace-runtime:dev-lite
WORKSPACE_UI_IMAGE=ailerondocker/workspace-ui:dev
COTURN_IMAGE=ailerondocker/platform-coturn:dev
COMPOSE_E2E_NETWORK=$network
COMPOSE_E2E_SOURCE_ROOT=$host_repo_root
COMPOSE_E2E_STATE_ROOT=$state_root
EOF
chmod 0600 "$env_file"

compose() {
  docker compose --env-file "$env_file" -p "$project" \
    -f "$compose_file" "$@"
}

test -z "$(docker ps -aq --filter "label=com.docker.compose.project=$project")" \
  || fail "generated Compose project already exists"
docker network inspect "$network" >/dev/null 2>&1 \
  && fail "generated Compose network already exists"

for image in "$renderer_image" python:3.12-alpine; do
  docker image inspect "$image" >/dev/null 2>&1 \
    || fail "required existing image is unavailable: $image"
done

printf '%s\n' "$project" > "$state_root/.runner-visible"
docker run --rm --pull never \
  -v "$state_root:/compose-e2e-state:ro" \
  python:3.12-alpine \
  test -f /compose-e2e-state/.runner-visible \
  || fail "state path is not shared with the Docker daemon; mount it at the same absolute path"

docker run --rm --pull never \
  --entrypoint /workspace-manager/.venv/bin/python \
  -v "$host_repo_root:/compose-e2e-source:ro" \
  -v "$state_root:$state_root" \
  -w /compose-e2e-source \
  "$renderer_image" \
  scripts/test/compose-e2e/render_compose.py \
  --source /compose-e2e-source/docker-compose.yml \
  --output "$compose_file" \
  --network-name "$network" \
  --source-root "$host_repo_root" \
  --state-root "$state_root"

test -f "$compose_file" || fail "isolated Compose document was not rendered"

compose --profile local-oidc --profile compose-e2e config > "$resolved_file"
grep -q "name: $network" "$resolved_file" || fail "resolved network is not unique"
if grep -q 'container_name:' "$resolved_file"; then
  fail "resolved services still contain fixed container_name values"
fi
if grep -Eq 'published: "?(389|3478|5433|6382|8082|18083)"?$' "$resolved_file"; then
  fail "resolved services still publish a fixed root-stack port"
fi

images=$(compose --profile local-oidc --profile compose-e2e config --images | sort -u)
dynamic_images="ailerondocker/workspace-runtime:dev-lite ailerondocker/workspace-chrome:dev ailerondocker/workspace-canvas:dev"
for image in $images $dynamic_images; do
  docker image inspect "$image" >/dev/null 2>&1 \
    || fail "required existing image is unavailable: $image"
done

echo "COMPOSE_E2E_PREFLIGHT_OK project=$project network=$network"
if [ "$preflight_only" = true ]; then
  exit 0
fi

docker ps -q > "$initial_running_file"
log "Starting isolated clean-volume Compose project $project"
compose --profile local-oidc up -d --wait --wait-timeout 420 --no-build --pull never

log "Running black-box assertions inside the isolated project network"
compose --profile local-oidc --profile compose-e2e run --rm --no-deps e2e-runner

log "Compose E2E completed without touching the live root stack"
