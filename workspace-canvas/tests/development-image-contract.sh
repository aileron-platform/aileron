#!/usr/bin/env bash
set -euo pipefail

image="${1:?usage: $0 IMAGE}"
container="canvas-development-contract-$$"

cleanup() {
  docker rm -f "${container}" >/dev/null 2>&1 || true
}
trap cleanup EXIT

fail() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 1
}

configured_user="$(docker image inspect --format '{{.Config.User}}' "${image}")"
[[ "${configured_user}" == "1000:1000" ]] ||
  fail "Development Canvas image must declare user 1000:1000, found ${configured_user:-<empty>}"

docker run --detach --name "${container}" "${image}" >/dev/null

tmpfs_config="$(docker inspect --format '{{json .HostConfig.Tmpfs}}' "${container}")"
[[ "${tmpfs_config}" == "null" || "${tmpfs_config}" == "{}" ]] ||
  fail "Development contract must run without tmpfs mounts, found ${tmpfs_config}"

ready=false
for _ in {1..120}; do
  state="$(docker inspect --format '{{.State.Status}}' "${container}")"
  if [[ "${state}" != "running" ]]; then
    docker logs "${container}" >&2 || true
    fail "Canvas exited before readiness"
  fi
  if [[ "$(docker inspect --format '{{.State.Health.Status}}' "${container}")" == "healthy" ]] &&
    docker exec "${container}" node -e \
      'fetch("http://127.0.0.1:3013/ready").then((response) => process.exit(response.ok ? 0 : 1)).catch(() => process.exit(1))' \
      >/dev/null 2>&1; then
    ready=true
    break
  fi
  sleep 1
done

if [[ "${ready}" != true ]]; then
  docker logs "${container}" >&2 || true
  fail "Canvas did not become healthy and ready"
fi

[[ "$(docker exec "${container}" id -u)" == "1000" ]] ||
  fail "Canvas did not retain the image default non-root UID"
docker exec "${container}" sh -ec \
  'touch /tmp/aileron-canvas/development-contract-write-probe'
docker exec "${container}" node -e \
  'fetch("http://127.0.0.1:3003/").then((response) => process.exit(response.ok ? 0 : 1)).catch(() => process.exit(1))'

logs="$(docker logs "${container}" 2>&1)"
if grep -Eiq 'permission denied|read-only file system|operation not permitted' <<<"${logs}"; then
  printf '%s\n' "${logs}" >&2
  fail "Canvas logged a filesystem permission failure"
fi
