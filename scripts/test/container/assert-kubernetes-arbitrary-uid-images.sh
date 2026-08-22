#!/bin/sh

set -eu

operator_image="${OPERATOR_IMAGE:?OPERATOR_IMAGE is required}"
manager_image="${MANAGER_IMAGE:?MANAGER_IMAGE is required}"
runtime_image="${RUNTIME_IMAGE:?RUNTIME_IMAGE is required}"
frontend_image="${FRONTEND_IMAGE:?FRONTEND_IMAGE is required}"
browser_image="${BROWSER_IMAGE:-aileron/workspace-chrome:kubernetes-arbitrary-uid-test}"
canvas_image="${CANVAS_IMAGE:-aileron/workspace-canvas:kubernetes-arbitrary-uid-test}"
manager_state_volume="${MANAGER_STATE_VOLUME:?MANAGER_STATE_VOLUME is required}"
runtime_workspace_volume="${RUNTIME_WORKSPACE_VOLUME:?RUNTIME_WORKSPACE_VOLUME is required}"
runtime_home_volume="${RUNTIME_HOME_VOLUME:?RUNTIME_HOME_VOLUME is required}"
storage_volume="${STORAGE_VOLUME:?STORAGE_VOLUME is required}"
storage_gid="${STORAGE_GID:-2000}"
uid_a="1000860000"
uid_b="1000860001"
probe_project_label="aileron-arbitrary-uid-probe-child"

fail() {
  echo "Arbitrary UID image assertion failed: $*" >&2
  exit 1
}

require_image() {
  image="$1"
  docker image inspect "${image}" >/dev/null 2>&1 ||
    fail "Required prebuilt image is missing: ${image}"
}

run_visual_image_contracts() {
  command -v bash >/dev/null 2>&1 || apk add --no-cache bash >/dev/null
  PLATFORM_STORAGE_GID="${storage_gid}" \
    bash /repo/workspace-chrome/tests/kubernetes-image-contract.sh "${browser_image}"
  PLATFORM_STORAGE_GID="${storage_gid}" \
    bash /repo/workspace-canvas/tests/kubernetes-image-contract.sh "${canvas_image}"
}

assert_numeric_non_root_user() {
  image="$1"
  configured_user="$(docker image inspect --format '{{.Config.User}}' "${image}")"

  case "${configured_user}" in
    [1-9][0-9]*:[1-9][0-9]*) ;;
    *) fail "${image} must declare a numeric non-root USER, found '${configured_user}'" ;;
  esac

  effective_uid="$(
    docker run --rm \
      --label "com.docker.compose.project=${probe_project_label}" \
      --label com.docker.compose.service=image-probe \
      --read-only \
      --tmpfs /tmp:rw,noexec,nosuid,size=64m \
      --entrypoint /bin/sh \
      "${image}" \
      -ec 'id -u'
  )"
  [ "${effective_uid}" -ne 0 ] || fail "${image} default process runs as root"
}

assert_frontend_uid() {
  uid="$1"
  docker run --rm \
    --label "com.docker.compose.project=${probe_project_label}" \
    --label com.docker.compose.service=frontend-probe \
    --read-only \
    --tmpfs /tmp:rw,noexec,nosuid,size=32m \
    --user "${uid}:${uid}" \
    --add-host host.docker.internal:host-gateway \
    --env EXPECTED_UID="${uid}" \
    --entrypoint /bin/sh \
    "${frontend_image}" \
    -ec '
      test "$(id -u)" = "${EXPECTED_UID}"
      /docker-entrypoint.sh nginx -g "daemon off;" &
      nginx_pid=$!
      attempts=0
      until wget -qO /tmp/index.html http://127.0.0.1:8082/; do
        kill -0 "${nginx_pid}" 2>/dev/null || exit 1
        attempts=$((attempts + 1))
        [ "${attempts}" -lt 100 ] || exit 1
        sleep 0.1
      done
      grep -qi "<html" /tmp/index.html
      kill "${nginx_pid}"
      wait "${nginx_pid}" || true
      /docker-entrypoint.sh true
      test -f /tmp/aileron-html/index.html
    '
}

prepare_backend_volume() {
  volume="$1"
  docker run --rm \
    --volume "${volume}:/volume" \
    alpine:3.20 \
    /bin/sh -ec "
      find /volume -mindepth 1 -maxdepth 1 -exec rm -rf -- {} +
      chgrp '${storage_gid}' /volume
      chmod 2770 /volume
      touch /volume/.aileron-volume-ready
      chgrp '${storage_gid}' /volume/.aileron-volume-ready
      chmod 0660 /volume/.aileron-volume-ready
    "
}

prepare_runtime_home_volume() {
  prepare_backend_volume "${runtime_home_volume}"
  docker run --rm \
    --volume "${runtime_home_volume}:/volume" \
    alpine:3.20 \
    /bin/sh -ec "
      mkdir -p /volume/.codex
      chgrp -R '${storage_gid}' /volume/.codex
      chmod 2770 /volume/.codex
    "
}

assert_manager_uid() {
  uid="$1"
  docker run --rm \
    --label "com.docker.compose.project=${probe_project_label}" \
    --label com.docker.compose.service=manager-probe \
    --read-only \
    --tmpfs /tmp:rw,noexec,nosuid,size=64m \
    --user "${uid}:${uid}" \
    --group-add "${storage_gid}" \
    --env EXPECTED_UID="${uid}" \
    --env EXPECTED_STORAGE_GID="${storage_gid}" \
    --env HOME=/state/home \
    --env CODEX_HOME=/state/codex \
    --env UV_CACHE_DIR=/tmp/uv-cache \
    --volume "${manager_state_volume}:/state" \
    --volume "${storage_volume}:/host/knowledge-bases" \
    --entrypoint /bin/sh \
    "${manager_image}" \
    -ec '
      test "$(id -u)" = "${EXPECTED_UID}"
      id -G | tr " " "\n" | grep -qx "${EXPECTED_STORAGE_GID}"
      umask 0007
      mkdir -p "${HOME}" "${CODEX_HOME}" /state/local-history /state/uploads /state/marketplace /tmp/uv-cache
      touch /state/local-history/arbitrary-uid /state/uploads/arbitrary-uid /state/marketplace/arbitrary-uid
      touch /host/knowledge-bases/manager-write-probe
      test -x /workspace-manager/.venv/bin/python
      test -x /workspace-manager/.venv/bin/uvicorn
      test -x /workspace-manager/.venv/bin/celery
      test -x /workspace-manager/app/celery
      test -r /workspace-manager/app/celery/app.py
      for required in bash curl git grep python supervisord codex; do
        command -v "${required}" >/dev/null 2>&1 || {
          echo "Manager runtime command is missing: ${required}" >&2
          exit 1
        }
      done
      for forbidden in docker dockerd containerd containerd-shim systemctl redis-cli npm npx uv pip pip3 easy_install gcc g++ make; do
        if command -v "${forbidden}" >/dev/null 2>&1; then
          echo "Manager Kubernetes image contains forbidden command: ${forbidden}" >&2
          exit 1
        fi
      done
      for forbidden_package in docker.io containerd systemd redis-tools npm nodejs build-essential gcc g++; do
        if dpkg-query -W -f="\${Status}" "${forbidden_package}" 2>/dev/null | grep -q "install ok installed"; then
          echo "Manager Kubernetes image contains forbidden package: ${forbidden_package}" >&2
          exit 1
        fi
      done
      codex --version
      supervisord --version
      git --version
      python -c "import importlib.util; assert importlib.util.find_spec(\"setuptools\") is None"
      python -c "import importlib.util; assert importlib.util.find_spec(\"app.celery.app\") is not None"
      if ls /workspace-manager/.env* >/dev/null 2>&1; then
        echo "Manager Kubernetes image contains a baked environment file" >&2
        exit 1
      fi
      if touch /workspace-manager/.root-write-probe 2>/dev/null; then
        echo "Manager root filesystem is writable" >&2
        exit 1
      fi
    '
}

assert_operator_binary_architecture() {
  image_arch="$(docker image inspect --format '{{.Architecture}}' "${operator_image}")"
  case "${image_arch}" in
    amd64) expected_elf_machine="62" ;;
    arm64) expected_elf_machine="183" ;;
    *) fail "Unsupported Operator image architecture: ${image_arch}" ;;
  esac

  operator_container_id="$(
    docker create \
      --label "com.docker.compose.project=${probe_project_label}" \
      --label com.docker.compose.service=operator-architecture-probe \
      --entrypoint /bin/true \
      "${operator_image}"
  )"
  operator_binary="/tmp/workspace-operator-${operator_container_id}"
  if ! docker cp "${operator_container_id}:/app/workspace-operator" "${operator_binary}"; then
    docker rm -f "${operator_container_id}" >/dev/null 2>&1 || true
    fail "Unable to extract Operator binary for architecture verification"
  fi
  docker rm -f "${operator_container_id}" >/dev/null

  elf_machine="$(
    dd if="${operator_binary}" bs=1 skip=18 count=2 2>/dev/null \
      | od -An -tu2 \
      | tr -d '[:space:]'
  )"
  rm -f "${operator_binary}"
  [ "${elf_machine}" = "${expected_elf_machine}" ] ||
    fail "Operator binary ELF architecture ${elf_machine} does not match image ${image_arch}"

  docker run --rm \
    --label "com.docker.compose.project=${probe_project_label}" \
    --label com.docker.compose.service=operator-architecture-probe \
    --read-only \
    --tmpfs /tmp:rw,noexec,nosuid,size=16m \
    --entrypoint /app/workspace-operator \
    "${operator_image}" \
    --help >/dev/null 2>&1 || fail "Operator binary cannot start on ${image_arch}"
}

assert_operator_uid() {
  uid="$1"
  docker run --rm \
    --label "com.docker.compose.project=${probe_project_label}" \
    --label com.docker.compose.service=operator-probe \
    --read-only \
    --tmpfs /tmp:rw,noexec,nosuid,size=16m \
    --user "${uid}:${uid}" \
    --env EXPECTED_UID="${uid}" \
    --entrypoint /bin/sh \
    "${operator_image}" \
    -ec '
      test "$(id -u)" = "${EXPECTED_UID}"
      test -x /app/workspace-operator
      if touch /app/.root-write-probe 2>/dev/null; then
        echo "Operator root filesystem is writable" >&2
        exit 1
      fi
    '
}

assert_runtime_uid() {
  uid="$1"
  docker run --rm \
    --label "com.docker.compose.project=${probe_project_label}" \
    --label com.docker.compose.service=runtime-probe \
    --read-only \
    --tmpfs /tmp:rw,noexec,nosuid,size=64m \
    --tmpfs /home/developer/.codex/tmp:rw,exec,nosuid,size=16m,mode=1777 \
    --user "${uid}:${uid}" \
    --group-add "${storage_gid}" \
    --env EXPECTED_UID="${uid}" \
    --env FIRST_UID="${uid_a}" \
    --env EXPECTED_STORAGE_GID="${storage_gid}" \
    --env HOME=/home/developer \
    --volume "${runtime_workspace_volume}:/workspace" \
    --volume "${runtime_home_volume}:/home/developer" \
    --volume "${storage_volume}:/knowledge:ro" \
    --entrypoint /bin/sh \
    "${runtime_image}" \
    -ec '
      test "$(id -u)" = "${EXPECTED_UID}"
      id -G | tr " " "\n" | grep -qx "${EXPECTED_STORAGE_GID}"
      export CODEX_HOME="${HOME}/.codex"
      export XDG_CONFIG_HOME="${HOME}/.config"
      export XDG_DATA_HOME="${HOME}/.local/share"
      export XDG_STATE_HOME="${HOME}/.local/state"
      umask 0007
      mkdir -p "${HOME}" "${CODEX_HOME}" "${XDG_CONFIG_HOME}" "${XDG_DATA_HOME}" "${XDG_STATE_HOME}" /tmp/supervisor
      touch "${HOME}/arbitrary-uid-${EXPECTED_UID}" "${CODEX_HOME}/arbitrary-uid-${EXPECTED_UID}"
      if [ "${EXPECTED_UID}" != "${FIRST_UID}" ]; then
        test -f "${HOME}/arbitrary-uid-${FIRST_UID}"
        test -f "${CODEX_HOME}/arbitrary-uid-${FIRST_UID}"
      fi
      test -r /knowledge/shared
      grep -qx "uid-b" /knowledge/shared
      if touch /knowledge/runtime-write-probe 2>/dev/null; then
        echo "Runtime Knowledge Base mount is writable" >&2
        exit 1
      fi
      test -x /workspace-runtime/.venv/bin/python
      test -x /opt/terminal-service/bin/terminal-service
      test -x /opt/aileron/npm/bin/codex
      test -x /opt/aileron/npm/bin/playwright-cli
      codex_help="$(codex --help 2>&1)"
      if printf "%s\n" "${codex_help}" | grep -Fq "could not create PATH aliases"; then
        echo "Codex PATH alias setup failed" >&2
        exit 1
      fi
      test "$(stat -c %u "${CODEX_HOME}/tmp/arg0")" = "${EXPECTED_UID}"
      test "$(stat -c %a "${CODEX_HOME}/tmp/arg0")" = "700"
      test -x /opt/aileron/bin/opencode
      test -x /usr/local/bin/uv
      for required in claude codex npm opencode playwright-cli pnpm uv; do
        command -v "${required}" >/dev/null 2>&1 || {
          echo "Runtime command is missing: ${required}" >&2
          exit 1
        }
      done
      ! command -v sshd >/dev/null 2>&1
      ! command -v dockerd >/dev/null 2>&1
      if ls /workspace-runtime/.env* >/dev/null 2>&1; then
        echo "Runtime image contains a baked environment file" >&2
        exit 1
      fi
      if touch /workspace-runtime/.root-write-probe 2>/dev/null; then
        echo "Runtime root filesystem is writable" >&2
        exit 1
      fi
    '
}

assert_startup_contracts() {
  manager_startup=/repo/workspace-manager/scripts/start_services.sh
  manager_supervisor=/repo/workspace-manager/supervisord.kubernetes.conf
  runtime_startup=/repo/workspace-runtime/start_services.kubernetes.sh
  runtime_docker_startup=/repo/workspace-runtime/start_services.sh
  runtime_supervisor=/repo/workspace-runtime/supervisord.kubernetes.conf
  root_dockerignore=/repo/.dockerignore
  frontend_dockerignore=/repo/frontend/.dockerignore

  beat_count="$(grep -c '^\[program:celery-beat\]$' "${manager_supervisor}")"
  [ "${beat_count}" -eq 1 ] || fail "Manager Kubernetes profile must run exactly one Celery beat"

  for forbidden in 'user=root' 'user=developer' '/home/aileron'; do
    if grep -Fq "${forbidden}" "${manager_supervisor}" "${runtime_supervisor}" "${runtime_startup}"; then
      fail "Kubernetes process configuration contains forbidden value: ${forbidden}"
    fi
  done

  grep -Fxq '**/.env' "${root_dockerignore}" ||
    fail "Root Docker context does not exclude .env files"
  grep -Fxq '**/.env.*' "${root_dockerignore}" ||
    fail "Root Docker context does not exclude environment override files"
  grep -Fxq '.env*' "${frontend_dockerignore}" ||
    fail "Frontend Docker context does not exclude environment files"
  if grep -Fq 'COPY workspace-manager/.env' /repo/workspace-manager/Dockerfile ||
    grep -Fq 'COPY workspace-runtime/.env' /repo/workspace-runtime/Dockerfile; then
    fail "Service Dockerfile copies environment files into an image"
  fi

  for forbidden in 'uv sync' 'chown' 'useradd' 'usermod' 'sshd' 'dockerd'; do
    if grep -Fq "${forbidden}" "${runtime_startup}"; then
      fail "Runtime Kubernetes startup mutates the image or starts a rootful daemon: ${forbidden}"
    fi
  done
  if grep -Fq '/workspace/.home' "${runtime_startup}" "${runtime_supervisor}"; then
    fail "Runtime Kubernetes profile must keep user state outside the shared workspace volume"
  fi

  initializer_line="$(grep -n 'initialize_workspace_runtime.py' "${runtime_startup}" | cut -d: -f1)"
  supervisor_line="$(grep -n 'exec /usr/bin/supervisord' "${runtime_startup}" | cut -d: -f1)"
  if [ -z "${initializer_line}" ] ||
    [ -z "${supervisor_line}" ] ||
    [ "${initializer_line}" -ge "${supervisor_line}" ]; then
    fail "Runtime Kubernetes initializer must complete before supervisor"
  fi
  grep -Fq 'initialize_workspace_runtime.py' "${runtime_docker_startup}" ||
    fail "Docker and Kubernetes must use the same Runtime initializer"
  if grep -Rq 'bootstrap_git_repo.sh' \
    /repo/workspace-runtime/scripts \
    /repo/workspace-runtime/start_services.sh \
    /repo/workspace-runtime/start_services.kubernetes.sh; then
    fail "Removed Runtime git bootstrap must not remain referenced"
  fi

  kubernetes_branch="$(sed -n '/AILERON_EXECUTION_PROFILE.*kubernetes/,/^fi$/p' "${manager_startup}")"
  for forbidden in 'uv sync' 'chown' 'useradd' 'usermod'; do
    if printf '%s\n' "${kubernetes_branch}" | grep -Fq "${forbidden}"; then
      fail "Manager Kubernetes startup mutates the image: ${forbidden}"
    fi
  done
}

assert_publication_contract() {
  chart_values=/repo/helm/aileron/values.yaml

  manager_values="$(sed -n '/^workspaceManager:/,/^[^[:space:]]/p' "${chart_values}")"
  operator_values="$(sed -n '/^workspaceOperator:/,/^[^[:space:]]/p' "${chart_values}")"
  kubernetes_values="$(sed -n '/^kubernetes:/,/^[^[:space:]]/p' "${chart_values}")"
  manager_image_values="$(printf '%s\n' "${manager_values}" | sed -n '/^  image:/,/^  serviceAccount:/p')"
  runtime_image_values="$(printf '%s\n' "${operator_values}" | sed -n '/^  runtimeImage:/,/^  image:/p')"
  operator_image_values="$(printf '%s\n' "${operator_values}" | sed -n '/^  image:/,/^  serviceAccount:/p')"
  browser_image_values="$(printf '%s\n' "${kubernetes_values}" | sed -n '/^  browserImage:/,/^  canvasImage:/p')"
  canvas_image_values="$(printf '%s\n' "${kubernetes_values}" | sed -n '/^  canvasImage:/,/^  workspaceDefaults:/p')"

  printf '%s\n' "${manager_image_values}" | grep -Fq 'repository: ailerondocker/workspace-manager' ||
    fail "Helm Manager repository does not reference the published image"
  printf '%s\n' "${manager_image_values}" | grep -Fq 'tag: latest-kubernetes-amd64' ||
    fail "Helm Manager tag does not reference a published Kubernetes image"
  printf '%s\n' "${runtime_image_values}" | grep -Fq 'repository: ailerondocker/workspace-runtime' ||
    fail "Helm Runtime repository does not reference the published image"
  printf '%s\n' "${runtime_image_values}" | grep -Fq 'tag: latest-kubernetes-amd64' ||
    fail "Helm Runtime tag does not reference a published Kubernetes image"
  printf '%s\n' "${operator_image_values}" | grep -Fq 'repository: ailerondocker/workspace-operator' ||
    fail "Helm Operator repository does not reference the published image"
  printf '%s\n' "${operator_image_values}" | grep -Fq 'tag: latest' ||
    fail "Helm Operator tag does not reference the published multi-arch manifest"
  printf '%s\n' "${browser_image_values}" | grep -Fq 'repository: ailerondocker/workspace-chrome' ||
    fail "Helm Browser repository does not reference the published image"
  printf '%s\n' "${browser_image_values}" | grep -Fq 'tag: latest-kubernetes-amd64' ||
    fail "Helm Browser tag does not reference a published Kubernetes image"
  printf '%s\n' "${canvas_image_values}" | grep -Fq 'repository: ailerondocker/workspace-canvas' ||
    fail "Helm Canvas repository does not reference the published image"
  printf '%s\n' "${canvas_image_values}" | grep -Fq 'tag: latest-kubernetes-amd64' ||
    fail "Helm Canvas tag does not reference a published Kubernetes image"
}

assert_storage_identity_transition() {
  docker run --rm \
    --user "${uid_a}:${uid_a}" \
    --group-add "${storage_gid}" \
    --volume "${storage_volume}:/storage" \
    alpine:3.20 \
    /bin/sh -ec 'umask 0007; printf "%s\n" uid-a > /storage/shared'

  docker run --rm \
    --user "${uid_b}:${uid_b}" \
    --group-add "${storage_gid}" \
    --volume "${storage_volume}:/storage" \
    alpine:3.20 \
    /bin/sh -ec 'printf "%s\n" uid-b > /storage/shared'

  if docker run --rm \
    --user "${uid_b}:${uid_b}" \
    --group-add 2001 \
    --volume "${storage_volume}:/storage" \
    alpine:3.20 \
    /bin/sh -ec 'touch /storage/wrong-gid-write-probe' >/dev/null 2>&1; then
    fail "Storage verification must fail with the wrong supplemental GID"
  fi
}

assert_numeric_non_root_user "${operator_image}"
assert_numeric_non_root_user "${manager_image}"
assert_numeric_non_root_user "${runtime_image}"
assert_numeric_non_root_user "${frontend_image}"
require_image "${browser_image}"
require_image "${canvas_image}"
assert_numeric_non_root_user "${browser_image}"
assert_numeric_non_root_user "${canvas_image}"
assert_operator_binary_architecture
assert_startup_contracts
assert_publication_contract

prepare_backend_volume "${manager_state_volume}"
prepare_backend_volume "${runtime_workspace_volume}"
prepare_runtime_home_volume
prepare_backend_volume "${storage_volume}"
assert_storage_identity_transition

assert_operator_uid "${uid_a}"
assert_operator_uid "${uid_b}"
assert_manager_uid "${uid_a}"
assert_manager_uid "${uid_b}"
assert_runtime_uid "${uid_a}"
assert_runtime_uid "${uid_b}"
assert_frontend_uid "${uid_a}"
assert_frontend_uid "${uid_b}"
run_visual_image_contracts

echo "Kubernetes Frontend, Operator, Manager, Runtime, Browser, and Canvas arbitrary UID preflight assertions passed"
