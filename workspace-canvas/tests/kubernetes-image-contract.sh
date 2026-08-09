#!/usr/bin/env bash
set -euo pipefail

image="${1:?usage: $0 IMAGE}"
storage_gid="${PLATFORM_STORAGE_GID:-2000}"
container=""

cleanup() {
  if [[ -n "${container}" ]]; then
    docker rm -f "${container}" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

fail() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 1
}

config_user="$(docker image inspect --format '{{.Config.User}}' "${image}")"
[[ "${config_user}" =~ ^[1-9][0-9]*:[1-9][0-9]*$ ]] ||
  fail "Kubernetes Canvas image must declare a numeric non-root user: ${config_user:-<empty>}"

for runtime_uid in 10001 1000860000; do
  container="canvas-kubernetes-contract-${runtime_uid}-$$"
  docker run -d \
    --name "${container}" \
    --user "${runtime_uid}:${runtime_uid}" \
    --group-add "${storage_gid}" \
    --read-only \
    --cap-drop ALL \
    --security-opt no-new-privileges \
    --tmpfs /tmp:rw,exec,nosuid,nodev,mode=1777 \
    --tmpfs "/workspace:rw,exec,nosuid,nodev,uid=${runtime_uid},gid=${storage_gid},mode=2770" \
    "${image}" >/dev/null

  ready=false
  for _ in {1..90}; do
    if docker exec "${container}" node -e \
      'fetch("http://127.0.0.1:3013/ready").then((response) => process.exit(response.ok ? 0 : 1)).catch(() => process.exit(1))' \
      >/dev/null 2>&1; then
      ready=true
      break
    fi
    sleep 1
  done
  if [[ "${ready}" != true ]]; then
    docker logs "${container}" >&2 || true
    fail "Canvas did not become ready as UID ${runtime_uid}"
  fi

  [[ "$(docker exec "${container}" id -u)" == "${runtime_uid}" ]] ||
    fail "Canvas did not retain arbitrary UID ${runtime_uid}"
  docker exec "${container}" node -e \
    'fetch("http://127.0.0.1:3003/").then((response) => process.exit(response.ok ? 0 : 1)).catch(() => process.exit(1))'
  docker exec "${container}" sh -ec '! touch /rootfs-write-probe'
  docker exec "${container}" sh -ec 'touch /tmp/runtime-write-probe /workspace/workspace-write-probe'

  logs="$(docker logs "${container}" 2>&1)"
  if grep -Eiq 'permission denied|read-only file system|operation not permitted' <<<"${logs}"; then
    printf '%s\n' "${logs}" >&2
    fail "Canvas logged a filesystem permission failure as UID ${runtime_uid}"
  fi

  docker rm -f "${container}" >/dev/null
  container=""
done
