#!/bin/sh
set -eu
umask 077

usage() {
  cat <<'EOF'
Usage:
  docker run --rm \
    -v /var/run/docker.sock:/var/run/docker.sock \
    -v /tmp/aileron-compose-e2e:/tmp/aileron-compose-e2e \
    -v "$PWD:/repo:ro" -w /repo \
    -e COMPOSE_E2E_HOST_REPO_ROOT="$PWD" \
    -e COMPOSE_E2E_SOURCE_REVISION="$(git rev-parse HEAD)" \
    docker:27-cli@sha256:f56779b4e86550493153cc8642c9c8e40b5d934e43cb5b4ea463aea5245c5c01 \
    sh scripts/test/compose-e2e/run.sh [--preflight-only]
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

ensure_digest_image() {
  image="$1"
  case "$image" in
    *@sha256:*) ;;
    *) fail "refusing to pull a mutable image reference: $image" ;;
  esac
  if ! docker image inspect "$image" >/dev/null 2>&1; then
    log "Pulling missing linux/amd64 digest image $image"
    docker pull --platform linux/amd64 "$image" >/dev/null \
      || fail "digest image pull failed: $image"
  fi
  architecture=$(docker image inspect --format '{{.Architecture}}' "$image")
  [ "$architecture" = "amd64" ] \
    || fail "digest image architecture is invalid: $image"
}

random_hex() {
  od -An -N32 -tx1 /dev/urandom | tr -d ' \n'
}

require_root_owned_directory() {
  directory_path="$1"
  description="$2"
  if [ -L "$directory_path" ] || [ ! -d "$directory_path" ]; then
    fail "$description must be a non-linked directory"
  fi
  directory_owner=$(stat -c '%u' "$directory_path" 2>/dev/null) \
    || fail "$description owner cannot be verified"
  [ "$directory_owner" = "0" ] || fail "$description must be root-owned"
}

canonical_directory() {
  readlink -f "$1" 2>/dev/null \
    || fail "$2 canonical path cannot be verified"
}

require_private_direct_child_directory() {
  child_path="$1"
  expected_parent="$2"
  description="$3"
  require_root_owned_directory "$child_path" "$description"
  child_canonical=$(canonical_directory "$child_path" "$description")
  child_parent=$(dirname "$child_canonical")
  [ "$child_parent" = "$expected_parent" ] \
    || fail "$description must be a direct state-parent child"
  chmod 0700 "$child_path"
  child_mode=$(stat -c '%a' "$child_path" 2>/dev/null) \
    || fail "$description mode cannot be verified"
  [ "$child_mode" = "700" ] || fail "$description mode must be 0700"
}

prepare_private_regular_file() {
  private_file="$1"
  description="$2"
  if [ -L "$private_file" ] || [ ! -f "$private_file" ]; then
    echo "$description must be a non-linked regular file" >&2
    return 1
  fi
  private_owner=$(stat -c '%u' "$private_file" 2>/dev/null) || {
    echo "$description owner cannot be verified" >&2
    return 1
  }
  if [ "$private_owner" != "0" ]; then
    echo "$description must be root-owned" >&2
    return 1
  fi
  chmod 0600 "$private_file" || return 1
  private_mode=$(stat -c '%a' "$private_file" 2>/dev/null) || return 1
  if [ "$private_mode" != "600" ]; then
    echo "$description mode must be 0600" >&2
    return 1
  fi
}

valid_workspace_id() {
  printf '%s\n' "$1" | grep -Eq \
    '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
}

valid_container_id_list() {
  container_list="$1"
  while IFS= read -r listed_container_id; do
    [ -n "$listed_container_id" ] || continue
    printf '%s\n' "$listed_container_id" \
      | grep -Eq '^[0-9a-f]{12,64}$' || return 1
  done <<EOF
$container_list
EOF
}

query_all_container_ids() {
  all_container_ids=$(docker ps -aq) || {
    echo "Docker container inventory query failed" >&2
    return 1
  }
  valid_container_id_list "$all_container_ids" || {
    echo "Docker container inventory returned an invalid ID" >&2
    return 1
  }
}

query_project_container_ids() {
  inventory_project="$1"
  project_container_ids=$(docker ps -aq \
    --filter "label=com.docker.compose.project=$inventory_project") || {
    echo "Compose container inventory query failed: $inventory_project" >&2
    return 1
  }
  valid_container_id_list "$project_container_ids" || {
    echo "Compose container inventory returned an invalid ID: $inventory_project" >&2
    return 1
  }
}

query_project_volume_names() {
  inventory_project="$1"
  project_volume_names=$(docker volume ls -q \
    --filter "label=com.docker.compose.project=$inventory_project") || {
    echo "Compose volume inventory query failed: $inventory_project" >&2
    return 1
  }
  while IFS= read -r listed_volume; do
    [ -n "$listed_volume" ] || continue
    printf '%s\n' "$listed_volume" | grep -Eq '^[A-Za-z0-9][A-Za-z0-9_.-]*$' || {
      echo "Compose volume inventory returned an invalid name" >&2
      return 1
    }
  done <<EOF
$project_volume_names
EOF
}

query_project_network_names() {
  inventory_project="$1"
  expected_network="$2"
  project_network_names=$(docker network ls --format '{{.Name}}' \
    --filter "label=com.docker.compose.project=$inventory_project") || {
    echo "Compose network inventory query failed: $inventory_project" >&2
    return 1
  }
  while IFS= read -r listed_network; do
    [ -n "$listed_network" ] || continue
    if [ "$listed_network" != "$expected_network" ]; then
      echo "Compose network inventory returned an unexpected name" >&2
      return 1
    fi
  done <<EOF
$project_network_names
EOF
}

query_workspace_container_ids() {
  workspace_identity="$1"
  workspace_container_ids=$(docker ps -aq \
    --filter "label=aileron.workspace_id=$workspace_identity") || {
    echo "Workspace container inventory query failed" >&2
    return 1
  }
  valid_container_id_list "$workspace_container_ids" || {
    echo "Workspace container inventory returned an invalid ID" >&2
    return 1
  }
}

collect_dynamic_workspace_diagnostics() {
  diagnostic_root="$1"
  diagnostic_workspace_file="$diagnostic_root/results/workspace-id"
  if [ ! -e "$diagnostic_workspace_file" ] \
    && [ ! -L "$diagnostic_workspace_file" ]; then
    return 0
  fi
  prepare_private_regular_file \
    "$diagnostic_workspace_file" "Workspace diagnostic identity" || return 1
  diagnostic_workspace_id=$(tr -d '\r\n' < "$diagnostic_workspace_file")
  if ! valid_workspace_id "$diagnostic_workspace_id"; then
    echo "Refusing dynamic diagnostics for invalid Workspace ID" >&2
    return 1
  fi
  query_workspace_container_ids "$diagnostic_workspace_id" || return 1
  for diagnostic_container_id in $workspace_container_ids; do
    diagnostic_workload=$(docker inspect --format \
      '{{ index .Config.Labels "aileron.workload" }}' \
      "$diagnostic_container_id" 2>/dev/null) || {
      echo "Workspace workload identity is unavailable: $diagnostic_container_id" >&2
      continue
    }
    case "$diagnostic_workload" in
      runtime|browser|canvas|browser-connectivity-probe) ;;
      *)
        echo "Skipping diagnostics for unexpected Workspace workload" >&2
        continue
        ;;
    esac
    diagnostic_image=$(docker inspect --format '{{.Config.Image}}' \
      "$diagnostic_container_id" 2>/dev/null) || {
      echo "Workspace image identity is unavailable: $diagnostic_container_id" >&2
      continue
    }
    printf '%s\n' "$diagnostic_image" \
      | grep -Eq '^[A-Za-z0-9][A-Za-z0-9._/@:-]{0,255}$' || {
      echo "Workspace image identity is invalid: $diagnostic_container_id" >&2
      continue
    }
    diagnostic_state=$(docker inspect --format '{{.State.Status}}' \
      "$diagnostic_container_id" 2>/dev/null) || {
      echo "Workspace state is unavailable: $diagnostic_container_id" >&2
      continue
    }
    case "$diagnostic_state" in
      created|running|paused|restarting|removing|exited|dead) ;;
      *)
        echo "Workspace state is invalid: $diagnostic_container_id" >&2
        continue
        ;;
    esac
    diagnostic_exit_code=$(docker inspect --format '{{.State.ExitCode}}' \
      "$diagnostic_container_id" 2>/dev/null) || {
      echo "Workspace exit code is unavailable: $diagnostic_container_id" >&2
      continue
    }
    printf '%s\n' "$diagnostic_exit_code" | grep -Eq '^[0-9]+$' || {
      echo "Workspace exit code is invalid: $diagnostic_container_id" >&2
      continue
    }
    printf '%s\n' "--- Workspace $diagnostic_workload logs" \
      "container=$diagnostic_container_id image=$diagnostic_image" \
      "state=$diagnostic_state exitCode=$diagnostic_exit_code tail=200 ---"
    docker logs --tail 200 "$diagnostic_container_id" 2>&1 || {
      echo "Workspace logs are unavailable: $diagnostic_container_id" >&2
    }
  done
}

cleanup_dynamic_workspace() {
  recovery_root="$1"
  recovery_workspace_file="$recovery_root/results/workspace-id"
  if [ ! -e "$recovery_workspace_file" ] && [ ! -L "$recovery_workspace_file" ]; then
    return 0
  fi
  prepare_private_regular_file \
    "$recovery_workspace_file" "Workspace recovery identity" || return 1
  recovery_workspace_id=$(tr -d '\r\n' < "$recovery_workspace_file")
  if ! valid_workspace_id "$recovery_workspace_id"; then
    echo "Refusing dynamic cleanup for invalid Workspace ID" >&2
    return 1
  fi
  query_workspace_container_ids "$recovery_workspace_id" || return 1
  dynamic_cleanup_status=0
  for dynamic_id in $workspace_container_ids; do
    case "$dynamic_id" in
      *[!0-9a-f]*|'')
        echo "Workspace container inventory contains an invalid ID" >&2
        return 1
        ;;
    esac
    log "Removing only dynamic container $dynamic_id for Workspace $recovery_workspace_id"
    docker rm -f "$dynamic_id" >/dev/null || dynamic_cleanup_status=1
  done
  query_workspace_container_ids "$recovery_workspace_id" || return 1
  if [ -n "$workspace_container_ids" ]; then
    echo "Workspace containers remain after cleanup: $recovery_workspace_id" >&2
    return 1
  fi
  [ "$dynamic_cleanup_status" -eq 0 ] || {
    echo "Workspace container removal reported a failure" >&2
    return 1
  }
}

valid_project_name() {
  printf '%s\n' "$1" \
    | grep -Eq '^aileron-compose-e2e-[0-9]{14}-[0-9]+-[0-9a-f]{8}$'
}

valid_source_image() {
  candidate_image="$1"
  owner_project="$2"
  valid_project_name "$owner_project" || return 1
  owner_suffix=${owner_project##*-}
  printf '%s\n' "$candidate_image" | grep -Eq \
    "^ailerondocker/(workspace-runtime-base-lite|workspace-runtime|workspace-chrome|workspace-canvas|workspace-manager|workspace-ui|workspace-operator|platform-coturn|platform-keycloak):acceptance-[0-9a-f]{40}-$owner_suffix$"
}

query_image_ids() {
  image_reference="$1"
  image_ids=$(docker image ls -q --no-trunc "$image_reference") || {
    echo "Docker image inventory query failed: $image_reference" >&2
    return 1
  }
  while IFS= read -r listed_image_id; do
    [ -n "$listed_image_id" ] || continue
    printf '%s\n' "$listed_image_id" | grep -Eq '^sha256:[0-9a-f]{64}$' || {
      echo "Docker image inventory returned an invalid ID" >&2
      return 1
    }
  done <<EOF
$image_ids
EOF
}

valid_builder_name() {
  candidate_builder="$1"
  owner_project="$2"
  valid_project_name "$owner_project" \
    && [ "$candidate_builder" = "$owner_project-builder" ]
}

query_builder_names() {
  builder_names=$(docker buildx ls --format '{{.Name}}') || {
    echo "Docker Buildx builder inventory query failed" >&2
    return 1
  }
  while IFS= read -r listed_builder; do
    [ -n "$listed_builder" ] || continue
    printf '%s\n' "$listed_builder" | grep -Eq '^[A-Za-z0-9][A-Za-z0-9_.-]*$' || {
      echo "Docker Buildx builder inventory returned an invalid name" >&2
      return 1
    }
  done <<EOF
$builder_names
EOF
}

builder_exists_in_inventory() {
  expected_builder="$1"
  while IFS= read -r listed_builder; do
    [ "$listed_builder" != "$expected_builder" ] || return 0
  done <<EOF
$builder_names
EOF
  return 1
}

remove_owned_builder() {
  builder_owner_project="$1"
  builder_metadata_file="$2"
  [ -e "$builder_metadata_file" ] || [ -L "$builder_metadata_file" ] || return 0
  prepare_private_regular_file \
    "$builder_metadata_file" "Compose E2E Buildx builder identity" || return 1
  owned_builder=$(tr -d '\r\n' < "$builder_metadata_file")
  if ! valid_builder_name "$owned_builder" "$builder_owner_project"; then
    echo "Refusing invalid Compose E2E Buildx builder identity" >&2
    return 1
  fi
  query_builder_names || return 1
  builder_exists_in_inventory "$owned_builder" || return 0
  docker buildx rm "$owned_builder" >/dev/null || return 1
  query_builder_names || return 1
  if builder_exists_in_inventory "$owned_builder"; then
    echo "Compose E2E Buildx builder remains after cleanup: $owned_builder" >&2
    return 1
  fi
}

image_is_container_referenced() {
  referenced_image="$1"
  initial_container_file="$2"
  prepare_private_regular_file \
    "$initial_container_file" "initial container inventory" || return 2
  query_all_container_ids || return 2
  for container_id in $all_container_ids; do
    configured_image=$(docker inspect --format '{{.Config.Image}}' \
      "$container_id" 2>/dev/null) || return 2
    [ "$configured_image" != "$referenced_image" ] || return 0
  done
  return 1
}

remove_owned_source_images() {
  image_owner_project="$1"
  owned_image_file="$2"
  initial_container_file="$3"
  image_cleanup_status=0
  [ -e "$owned_image_file" ] || [ -L "$owned_image_file" ] || return 0
  prepare_private_regular_file \
    "$owned_image_file" "owned source image inventory" || return 1

  while IFS= read -r image; do
    [ -n "$image" ] || continue
    if ! valid_source_image "$image" "$image_owner_project"; then
      echo "Refusing invalid Compose E2E owned image reference: $image" >&2
      image_cleanup_status=1
      continue
    fi
    if ! query_image_ids "$image"; then
      image_cleanup_status=1
      continue
    fi
    [ -n "$image_ids" ] || continue
    image_owner=$(docker image inspect --format \
      '{{index .Config.Labels "io.aileron.compose-e2e.run"}}' \
      "$image" 2>/dev/null) || {
      image_cleanup_status=1
      continue
    }
    if [ "$image_owner" != "$image_owner_project" ]; then
      log "Preserving source image not owned by this run: $image"
      continue
    fi
    if image_is_container_referenced "$image" "$initial_container_file"; then
      log "Preserving source image referenced by a protected container: $image"
      image_cleanup_status=1
      continue
    else
      reference_status=$?
      if [ "$reference_status" -ne 1 ]; then
        image_cleanup_status=1
        continue
      fi
    fi
    if ! docker image rm "$image" >/dev/null; then
      image_cleanup_status=1
      continue
    fi
    if ! query_image_ids "$image" || [ -n "$image_ids" ]; then
      image_cleanup_status=1
    fi
  done < "$owned_image_file"
  return "$image_cleanup_status"
}

recover_stale_run() {
  stale_root="$1"
  stale_project_file="$stale_root/.compose-project"
  stale_env_file="$stale_root/compose.env"
  stale_compose_file="$stale_root/compose.yml"
  stale_owned_image_file="$stale_root/.owned-source-images"
  stale_initial_container_file="$stale_root/.initial-containers"
  stale_builder_file="$stale_root/.buildx-builder"

  require_private_direct_child_directory \
    "$stale_root" "$canonical_state_parent" "stale Compose E2E state root"
  if ! prepare_private_regular_file \
    "$stale_project_file" "stale Compose project identity" \
    || ! prepare_private_regular_file \
      "$stale_owned_image_file" "stale owned source image inventory" \
    || ! prepare_private_regular_file \
      "$stale_initial_container_file" "stale initial container inventory" \
    || ! prepare_private_regular_file \
      "$stale_builder_file" "stale Buildx builder identity"; then
    echo "Refusing incomplete or linked Compose E2E recovery state: $stale_root" >&2
    return 1
  fi
  stale_compose_available=false
  if [ -e "$stale_env_file" ] || [ -L "$stale_env_file" ] \
    || [ -e "$stale_compose_file" ] || [ -L "$stale_compose_file" ]; then
    if ! prepare_private_regular_file "$stale_env_file" "stale Compose environment" \
      || ! prepare_private_regular_file "$stale_compose_file" "stale Compose document"; then
      echo "Refusing incomplete or linked Compose E2E recovery state: $stale_root" >&2
      return 1
    fi
    stale_compose_available=true
  fi

  stale_project=$(tr -d '\r\n' < "$stale_project_file")
  if ! valid_project_name "$stale_project"; then
    echo "Refusing invalid stale Compose project identity: $stale_root" >&2
    return 1
  fi
  chmod 0700 "$stale_root"

  log "Recovering stale isolated Compose project $stale_project"
  cleanup_dynamic_workspace "$stale_root" || return 1
  if [ "$stale_compose_available" = true ]; then
    if ! docker compose --env-file "$stale_env_file" -p "$stale_project" \
      -f "$stale_compose_file" \
      --profile local-oidc --profile compose-e2e \
      down --volumes --remove-orphans >/dev/null 2>&1; then
      log "Stale Compose down was inconclusive; verifying authoritative inventory"
    fi
  fi

  query_project_container_ids "$stale_project" || return 1
  stale_container_ids="$project_container_ids"
  query_project_volume_names "$stale_project" || return 1
  stale_volume_names="$project_volume_names"
  query_project_network_names "$stale_project" "$stale_project-network" || return 1
  stale_network_names="$project_network_names"
  if [ -n "$stale_container_ids" ] || [ -n "$stale_volume_names" ] \
    || [ -n "$stale_network_names" ]; then
    echo "Stale Compose project still owns resources: $stale_project" >&2
    return 1
  fi

  if ! remove_owned_source_images "$stale_project" "$stale_owned_image_file" \
    "$stale_initial_container_file"; then
    echo "Stale Compose E2E image cleanup did not converge: $stale_project" >&2
    return 1
  fi
  if ! remove_owned_builder "$stale_project" "$stale_builder_file"; then
    echo "Stale Compose E2E builder cleanup did not converge: $stale_project" >&2
    return 1
  fi

  case "$stale_root" in
    "$state_parent"/run-*) rm -rf "$stale_root" ;;
    *) echo "Refusing to remove unexpected stale state path: $stale_root" >&2; return 1 ;;
  esac
}

test -f /.dockerenv || fail "run.sh must execute inside a container"
command -v docker >/dev/null 2>&1 || fail "docker CLI is unavailable"
docker info >/dev/null 2>&1 || fail "Docker daemon is unavailable"
docker compose version >/dev/null 2>&1 || fail "Docker Compose plugin is unavailable"
docker buildx version >/dev/null 2>&1 || fail "Docker Buildx plugin is unavailable"

source_revision="${COMPOSE_E2E_SOURCE_REVISION:-}"
printf '%s\n' "$source_revision" | grep -Eq '^[0-9a-f]{40}$' \
  || fail "exact source revision is required"

repo_root=$(pwd)
case "$repo_root" in
  /*) ;;
  *) fail "repository path must be absolute" ;;
esac
test -f "$repo_root/docker-compose.yml" || fail "run from the repository root"
test -f "$repo_root/contracts/platform-configuration/contract.json" \
  || fail "platform configuration contract is unavailable"

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
if [ -e "$state_parent" ] || [ -L "$state_parent" ]; then
  require_root_owned_directory "$state_parent" "state parent"
else
  mkdir -p "$state_parent"
  require_root_owned_directory "$state_parent" "state parent"
fi
chmod 0700 "$state_parent"
canonical_state_parent=$(canonical_directory "$state_parent" "state parent")
[ "$canonical_state_parent" = "$state_parent" ] \
  || fail "state parent must use its canonical path"
state_parent_owner=$(stat -c '%u' "$state_parent" 2>/dev/null) \
  || fail "state parent owner cannot be reverified"
state_parent_mode=$(stat -c '%a' "$state_parent" 2>/dev/null) \
  || fail "state parent mode cannot be reverified"
if [ "$state_parent_owner" != "0" ] || [ "$state_parent_mode" != "700" ]; then
  fail "state parent ownership or mode changed"
fi

for stale_root in "$state_parent"/run-*; do
  [ -d "$stale_root" ] || continue
  recover_stale_run "$stale_root" \
    || fail "stale Compose E2E recovery did not converge: $stale_root"
done

run_id="$(date +%Y%m%d%H%M%S)-$$-$(random_hex | cut -c1-8)"
project="aileron-compose-e2e-$run_id"
network="$project-network"
run_suffix=${project##*-}
source_tag="acceptance-$source_revision-$run_suffix"
source_images="
ailerondocker/workspace-runtime-base-lite:$source_tag
ailerondocker/workspace-runtime:$source_tag
ailerondocker/workspace-chrome:$source_tag
ailerondocker/workspace-canvas:$source_tag
ailerondocker/workspace-manager:$source_tag
ailerondocker/workspace-ui:$source_tag
ailerondocker/workspace-operator:$source_tag
ailerondocker/platform-coturn:$source_tag
ailerondocker/platform-keycloak:$source_tag
"
state_root=$(mktemp -d "$state_parent/run-$run_id-XXXXXX")
require_private_direct_child_directory \
  "$state_root" "$canonical_state_parent" "Compose E2E state root"
mirror_root="$state_root/root"
result_root="$state_root/results"
env_file="$state_root/compose.env"
compose_file="$state_root/compose.yml"
resolved_file="$state_root/resolved.yml"
initial_running_file="$state_root/initial-running"
initial_container_ids_file="$state_root/.initial-containers"
owned_source_images_file="$state_root/.owned-source-images"
builder_file="$state_root/.buildx-builder"
builder="$project-builder"
buildkit_image='moby/buildkit:buildx-stable-1@sha256:2f5adac4ecd194d9f8c10b7b5d7bceb5186853db1b26e5abd3a657af0b7e26ec'
renderer_image="ailerondocker/workspace-manager:$source_tag"

cleanup() {
  original_status=$?
  trap - EXIT INT TERM
  cleanup_status=0
  recovery_failed=false
  manager_diagnostics=""
  dynamic_workspace_diagnostics=""
  set +e
  if ! query_project_container_ids "$project"; then
    project_container_ids=""
    cleanup_status=1
    recovery_failed=true
  fi

  if [ "$original_status" -ne 0 ]; then
    if [ -f "$env_file" ] && [ -n "$project_container_ids" ]; then
      log "Collecting isolated project diagnostics"
      docker compose --env-file "$env_file" -p "$project" \
        -f "$compose_file" \
        --profile local-oidc ps >&2
      docker compose --env-file "$env_file" -p "$project" \
        -f "$compose_file" \
        --profile local-oidc logs --no-color --tail 200 >&2
      manager_diagnostics=$(
        docker compose --env-file "$env_file" -p "$project" \
          -f "$compose_file" \
          --profile local-oidc logs --no-color --tail 200 workspace-manager 2>&1
      )
    fi
    if ! dynamic_workspace_diagnostics=$( \
      collect_dynamic_workspace_diagnostics "$state_root" 2>&1
    ); then
      log "Dynamic Workspace diagnostics were incomplete"
    fi
  fi

  if ! cleanup_dynamic_workspace "$state_root"; then
    cleanup_status=1
    recovery_failed=true
  fi

  if [ -f "$env_file" ] && [ -f "$compose_file" ]; then
    log "Removing isolated Compose project $project"
    if ! docker compose --env-file "$env_file" -p "$project" \
      -f "$compose_file" \
      --profile local-oidc --profile compose-e2e \
      down --volumes --remove-orphans >/dev/null 2>&1; then
      log "Compose down was inconclusive; verifying authoritative inventory"
    fi
  fi

  resources_remaining=false
  if query_project_container_ids "$project"; then
    remaining_container_ids="$project_container_ids"
  else
    remaining_container_ids=""
    cleanup_status=1
    recovery_failed=true
    resources_remaining=true
  fi
  if query_project_volume_names "$project"; then
    remaining_volume_names="$project_volume_names"
  else
    remaining_volume_names=""
    cleanup_status=1
    recovery_failed=true
    resources_remaining=true
  fi
  if query_project_network_names "$project" "$network"; then
    remaining_network_names="$project_network_names"
  else
    remaining_network_names=""
    cleanup_status=1
    recovery_failed=true
    resources_remaining=true
  fi
  if [ -n "$remaining_container_ids" ]; then
    echo "Isolated Compose containers remain after cleanup: $project" >&2
    cleanup_status=1
    resources_remaining=true
  fi
  if [ -n "$remaining_volume_names" ]; then
    echo "Isolated Compose volumes remain after cleanup: $project" >&2
    cleanup_status=1
    resources_remaining=true
  fi
  if [ -n "$remaining_network_names" ]; then
    echo "Isolated Compose network remains after cleanup: $network" >&2
    cleanup_status=1
    resources_remaining=true
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

  image_cleanup_failed=false
  if [ "$resources_remaining" = false ] \
    && ! remove_owned_source_images "$project" "$owned_source_images_file" \
      "$initial_container_ids_file"; then
    echo "Exact-source image cleanup did not converge: $project" >&2
    cleanup_status=1
    image_cleanup_failed=true
  fi

  builder_cleanup_failed=false
  if ! remove_owned_builder "$project" "$builder_file"; then
    echo "Exact Buildx builder cleanup did not converge: $project" >&2
    cleanup_status=1
    builder_cleanup_failed=true
  fi

  if [ "$resources_remaining" = false ] \
    && [ "$image_cleanup_failed" = false ] \
    && [ "$builder_cleanup_failed" = false ] \
    && [ "$recovery_failed" = false ]; then
    case "$state_root" in
      "$state_parent"/*) rm -rf "$state_root" ;;
      *) echo "Refusing to remove unexpected state path: $state_root" >&2; cleanup_status=1 ;;
    esac
  else
    log "Preserving private recovery state for residual project $project: $state_root"
  fi

  if [ -n "$manager_diagnostics" ]; then
    log "Final bounded Workspace Manager diagnostics"
    printf '%s\n' "$manager_diagnostics" >&2
  fi
  if [ -n "$dynamic_workspace_diagnostics" ]; then
    log "Final bounded dynamic Workspace diagnostics"
    printf '%s\n' "$dynamic_workspace_diagnostics" >&2
  fi

  if [ "$original_status" -ne 0 ]; then
    exit "$original_status"
  fi
  exit "$cleanup_status"
}
trap cleanup EXIT HUP INT TERM

mkdir -p "$mirror_root/data" "$result_root"
printf '%s\n' "$project" > "$state_root/.compose-project"
printf '%s\n' "$builder" > "$builder_file"
printf '%s\n' "$source_images" | sed '/^$/d' > "$owned_source_images_file"
: > "$initial_container_ids_file"
chmod 0600 \
  "$state_root/.compose-project" "$builder_file" \
  "$owned_source_images_file" "$initial_container_ids_file"

query_all_container_ids || fail "initial Docker container inventory is unavailable"
printf '%s\n' "$all_container_ids" > "$initial_container_ids_file"
for image in $source_images; do
  query_image_ids "$image" || fail "source image collision inventory failed: $image"
  [ -z "$image_ids" ] || fail "run-unique exact-source image already exists: $image"
done

query_builder_names || fail "Buildx builder collision inventory failed"
if builder_exists_in_inventory "$builder"; then
  fail "run-owned Buildx builder already exists: $builder"
fi
docker buildx create \
  --name "$builder" \
  --driver docker-container \
  --driver-opt "image=$buildkit_image" >/dev/null \
  || fail "run-owned Buildx builder creation failed"
query_builder_names || fail "created Buildx builder inventory failed"
builder_exists_in_inventory "$builder" \
  || fail "run-owned Buildx builder is unavailable after creation"

for source_path in \
  workspace-manager workspace-runtime workspace-terminal workspace-canvas \
  workspace-chrome frontend packages contracts helm scripts local-oidc \
  init-sql docker-compose.yml docker-compose.bundled-data-services.yml docker-bake.hcl; do
  test -e "$repo_root/$source_path" || fail "required source path is missing: $source_path"
  ln -s "$host_repo_root/$source_path" "$mirror_root/$source_path"
done

for data_path in \
  postgres redis workspace-data workspace-scripts runtime-home browser-credentials \
  knowledge-bases runtime-assertions init-scripts \
  platform-secrets turn-config turn-secrets; do
  mkdir -p "$mirror_root/data/$data_path"
done
chmod 0700 "$mirror_root/data/platform-secrets" "$mirror_root/data/turn-config" "$mirror_root/data/turn-secrets"
chmod 0770 "$mirror_root/data/knowledge-bases"

log "Building exact-source application images for $source_revision"
IMAGE_NAMESPACE=ailerondocker \
LOCAL_TAG="$source_tag" \
PYTHON_IMAGE='python:3.14.6-slim@sha256:b921fe7e7522f828d45197a47656ec465a9b15689b27fa8e1fba2864fca5b967' \
NODE_SLIM_IMAGE='node:24.18.0-slim@sha256:d45d78e7929b46875bbd4e29bea672d5bc48186c6c3588306521c815e78352d6' \
NODE_ALPINE_IMAGE='node:24.18.0-alpine@sha256:4ba75f835bb8802193e4c114572113d4b26f95f6f094f4b5229d2a77773e0afc' \
RUNTIME_GO_IMAGE='golang:1.23@sha256:e87b2a5f6df2dff71ea330d55d54f4979eb380ae58a7e3aabc9d53121243e689' \
OPERATOR_GO_IMAGE='golang:1.22-alpine@sha256:6d405dfc5fdf3a45df1529cf060b920041f52ce523487e0f36f02765af294a51' \
OPERATOR_RUNTIME_IMAGE='alpine:3.20@sha256:c64c687cbea9300178b30c95835354e34c4e4febc4badfe27102879de0483b5e' \
docker buildx bake --builder "$builder" --file docker-bake.hcl --load \
  --set '*.platform=linux/amd64' \
  --set "*.labels.org.opencontainers.image.revision=$source_revision" \
  --set "*.labels.io.aileron.compose-e2e.run=$project" \
  --set "workspace-runtime-production.tags=ailerondocker/workspace-runtime:$source_tag" \
  --set "workspace-manager-production.tags=ailerondocker/workspace-manager:$source_tag" \
  runtime-base-lite workspace-runtime-production workspace-browser workspace-canvas \
  workspace-manager-production workspace-ui workspace-operator platform-coturn platform-keycloak

for image in $source_images; do
  query_image_ids "$image" || fail "exact-source image inventory failed: $image"
  [ -n "$image_ids" ] || fail "exact-source image is unavailable: $image"
  identity=$(docker image inspect \
    --format '{{.Architecture}} {{index .Config.Labels "org.opencontainers.image.revision"}} {{index .Config.Labels "io.aileron.compose-e2e.run"}}' \
    "$image") || fail "exact-source image identity query failed: $image"
  [ "$identity" = "amd64 $source_revision $project" ] \
    || fail "exact-source image identity is invalid: $image"
done

postgres_bootstrap_password=$(random_hex)
postgres_platform_password=$(random_hex)
postgres_platform_username=platform_login
oidc_client_secret=$(random_hex)
keycloak_admin_password="E2e-$(random_hex)-Aa9!"
platform_admin_password="E2e-$(random_hex)-Aa9!"
turn_secret=$(random_hex)
gateway_token=$(random_hex)
agent_token=$(random_hex)

printf '%s\n' "$postgres_bootstrap_password" > "$mirror_root/data/platform-secrets/postgres-bootstrap-superuser-password"
printf '%s\n' "$postgres_platform_username" > "$mirror_root/data/platform-secrets/postgres-platform-username"
printf '%s\n' "$postgres_platform_password" > "$mirror_root/data/platform-secrets/postgres-platform-password"
printf 'postgresql://%s:%s@postgres:5432/aileron\n' "$postgres_platform_username" "$postgres_platform_password" > "$mirror_root/data/platform-secrets/platform-database-url"
printf '%s\n' 'redis://redis:6379/0' > "$mirror_root/data/platform-secrets/redis-general-url"
printf '%s\n' 'redis://redis:6379/1' > "$mirror_root/data/platform-secrets/redis-job-queue-url"
printf '%s\n' 'redis://redis:6379/2' > "$mirror_root/data/platform-secrets/redis-job-result-url"
printf '%s\n' "$oidc_client_secret" > "$mirror_root/data/platform-secrets/oidc-client-secret"
keycloak_admin_password_file="$mirror_root/data/platform-secrets/keycloak-bootstrap-admin-password"
printf '%s' "$keycloak_admin_password" > "$keycloak_admin_password_file"
printf '%s' "$platform_admin_password" > "$mirror_root/data/platform-secrets/local-oidc-platform-admin-password"
chmod 0600 \
  "$mirror_root/data/platform-secrets/postgres-bootstrap-superuser-password" \
  "$mirror_root/data/platform-secrets/postgres-platform-username" \
  "$mirror_root/data/platform-secrets/postgres-platform-password" \
  "$mirror_root/data/platform-secrets/platform-database-url" \
  "$mirror_root/data/platform-secrets/redis-general-url" \
  "$mirror_root/data/platform-secrets/redis-job-queue-url" \
  "$mirror_root/data/platform-secrets/redis-job-result-url" \
  "$mirror_root/data/platform-secrets/oidc-client-secret" \
  "$mirror_root/data/platform-secrets/local-oidc-platform-admin-password"
chown 1000:1000 "$keycloak_admin_password_file"
chmod 0400 "$keycloak_admin_password_file"

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
KEYCLOAK_BOOTSTRAP_ADMIN_USERNAME=keycloak-admin
HOST_PROJECT_ROOT=$mirror_root
HOST_PLATFORM_SECRETS_DIR=$mirror_root/data/platform-secrets
HOST_TURN_CONFIG_DIR=$mirror_root/data/turn-config
HOST_TURN_SECRETS_DIR=$mirror_root/data/turn-secrets
TURN_CREDENTIAL_REVISION=$project
TURN_CONNECTIVITY_GATEWAY_EXTERNAL_PORT=0
TURN_RELAY_MIN_PORT=49160
TURN_RELAY_MAX_PORT=49180
VITE_BROWSER_EXTENSION_ID=
WORKSPACE_MANAGER_IMAGE=ailerondocker/workspace-manager:$source_tag
WORKSPACE_OPERATOR_IMAGE=ailerondocker/workspace-operator:$source_tag
WORKSPACE_RUNTIME_IMAGE=ailerondocker/workspace-runtime:$source_tag
WORKSPACE_BROWSER_IMAGE=ailerondocker/workspace-chrome:$source_tag
WORKSPACE_CANVAS_IMAGE=ailerondocker/workspace-canvas:$source_tag
WORKSPACE_UI_IMAGE=ailerondocker/workspace-ui:$source_tag
COTURN_IMAGE=ailerondocker/platform-coturn:$source_tag
PLATFORM_KEYCLOAK_IMAGE=ailerondocker/platform-keycloak:$source_tag
COMPOSE_E2E_NETWORK=$network
COMPOSE_E2E_SOURCE_ROOT=$host_repo_root
COMPOSE_E2E_STATE_ROOT=$state_root
EOF
chmod 0600 "$env_file"

compose() {
  docker compose --env-file "$env_file" -p "$project" \
    -f "$compose_file" "$@"
}

query_project_container_ids "$project" \
  || fail "generated Compose container inventory is unavailable"
[ -z "$project_container_ids" ] || fail "generated Compose project already exists"
query_project_network_names "$project" "$network" \
  || fail "generated Compose network inventory is unavailable"
[ -z "$project_network_names" ] || fail "generated Compose network already exists"

docker image inspect "$renderer_image" >/dev/null 2>&1 \
  || fail "exact-source renderer image is unavailable: $renderer_image"
helper_image='python:3.12-alpine@sha256:aa679aa4eed6eb56c1dc6ad3f1b98b7d2d788fd961596779d188fdedad97fb38'
ensure_digest_image "$helper_image"

printf '%s\n' "$project" > "$state_root/.runner-visible"
docker run --rm --pull never \
  -v "$state_root:/compose-e2e-state:ro" \
  "$helper_image" \
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
  --overlay /compose-e2e-source/docker-compose.bundled-data-services.yml \
  --output "$compose_file" \
  --network-name "$network" \
  --source-root "$host_repo_root" \
  --state-root "$state_root"

test -f "$compose_file" || fail "isolated Compose document was not rendered"
chmod 0600 "$compose_file"

compose --profile local-oidc --profile compose-e2e config > "$resolved_file"
grep -q "name: $network" "$resolved_file" || fail "resolved network is not unique"
if grep -q 'container_name:' "$resolved_file"; then
  fail "resolved services still contain fixed container_name values"
fi
if grep -Eq 'published: "?(389|3478|5433|6382|8082|18083)"?$' "$resolved_file"; then
  fail "resolved services still publish a fixed root-stack port"
fi

images=$(compose --profile local-oidc --profile compose-e2e config --images | sort -u)
dynamic_images="ailerondocker/workspace-runtime:$source_tag ailerondocker/workspace-chrome:$source_tag ailerondocker/workspace-canvas:$source_tag"
for image in $images $dynamic_images; do
  case "$image" in
    *@sha256:*) ensure_digest_image "$image" ;;
    *)
      exact_source_image=false
      for built_image in $source_images; do
        if [ "$image" = "$built_image" ]; then
          exact_source_image=true
          break
        fi
      done
      [ "$exact_source_image" = true ] \
        || fail "Compose image is neither digest-pinned nor exact-source: $image"
      docker image inspect "$image" >/dev/null 2>&1 \
        || fail "exact-source image is unavailable: $image"
      ;;
  esac
done

echo "COMPOSE_E2E_PREFLIGHT_OK project=$project network=$network"
if [ "$preflight_only" = true ]; then
  exit 0
fi

docker ps -q > "$initial_running_file"
chmod 0600 "$initial_running_file"
log "Starting isolated clean-volume Compose project $project"
compose --profile local-oidc up -d --wait --wait-timeout 420 --no-build --pull never

keycloak_container=$(compose --profile local-oidc ps -q keycloak)
[ -n "$keycloak_container" ] || fail "isolated Keycloak container is missing"
keycloak_started_before=$(docker inspect --format '{{.State.StartedAt}}' "$keycloak_container")
keycloak_volume_before=$(docker inspect --format '{{range .Mounts}}{{if eq .Destination "/opt/keycloak/data"}}{{.Name}}{{end}}{{end}}' "$keycloak_container")
[ -n "$keycloak_volume_before" ] || fail "isolated Keycloak data volume is missing"
log "Restarting clean-volume Keycloak before Admin Console and OIDC login gates"
docker restart --time 30 "$keycloak_container" >/dev/null \
  || fail "isolated Keycloak restart failed"
keycloak_ready=false
keycloak_wait=0
while [ "$keycloak_wait" -lt 180 ]; do
  keycloak_health=$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}missing{{end}}' "$keycloak_container" 2>/dev/null || true)
  if [ "$keycloak_health" = "healthy" ]; then
    keycloak_ready=true
    break
  fi
  sleep 1
  keycloak_wait=$((keycloak_wait + 1))
done
[ "$keycloak_ready" = true ] || fail "restarted Keycloak did not become healthy"
keycloak_started_after=$(docker inspect --format '{{.State.StartedAt}}' "$keycloak_container")
keycloak_volume_after=$(docker inspect --format '{{range .Mounts}}{{if eq .Destination "/opt/keycloak/data"}}{{.Name}}{{end}}{{end}}' "$keycloak_container")
[ "$keycloak_started_before" != "$keycloak_started_after" ] \
  || fail "Keycloak restart did not replace the running process"
[ "$keycloak_volume_before" = "$keycloak_volume_after" ] \
  || fail "Keycloak restart changed the isolated data volume"

log "Running black-box assertions inside the isolated project network"
compose --profile local-oidc --profile compose-e2e run --rm --no-deps e2e-runner

log "Compose E2E completed without touching the live root stack"
