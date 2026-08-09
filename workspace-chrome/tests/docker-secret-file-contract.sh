#!/usr/bin/env bash

set -euo pipefail

image="${1:?usage: $0 IMAGE}"
container="aileron-browser-docker-secret-contract-$RANDOM-$$"
missing_container="${container}-missing"
plaintext_container="${container}-plaintext"
secret_directory="$(mktemp -d)"
user_password='0123456789012345678901234567890123456789012'
admin_password='abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQ'

cleanup() {
  docker rm -f \
    "${container}" \
    "${missing_container}" \
    "${plaintext_container}" >/dev/null 2>&1 || true
  rm -f \
    "${secret_directory}/user-password" \
    "${secret_directory}/admin-password"
  rmdir "${secret_directory}" >/dev/null 2>&1 || true
}
trap cleanup EXIT

fail() {
  printf '%s\n' "Docker Browser secret-file contract failed: $*" >&2
  exit 1
}

wait_for_exit() {
  local target="$1"
  local state
  for _ in {1..60}; do
    state="$(docker inspect --format '{{.State.Status}}' "${target}")"
    if [[ "${state}" == "exited" || "${state}" == "dead" ]]; then
      return 0
    fi
    sleep 1
  done
  fail "${target} did not fail closed within 60 seconds"
}

printf '%s' "${user_password}" >"${secret_directory}/user-password"
printf '%s' "${admin_password}" >"${secret_directory}/admin-password"
chmod 0600 \
  "${secret_directory}/user-password" \
  "${secret_directory}/admin-password"

docker run -d --name "${missing_container}" "${image}" >/dev/null
docker run -d \
    --name "${plaintext_container}" \
    --env "NEKO_MEMBER_PROVIDER=multiuser" \
    --env "NEKO_MEMBER_MULTIUSER_USER_PASSWORD=${user_password}" \
    --env "NEKO_MEMBER_MULTIUSER_ADMIN_PASSWORD=${admin_password}" \
    "${image}" >/dev/null
wait_for_exit "${missing_container}"
wait_for_exit "${plaintext_container}"

missing_status="$(docker inspect --format '{{.State.ExitCode}}' "${missing_container}")"
missing_state="$(docker inspect --format '{{.State.Status}}' "${missing_container}")"
missing_output="$(docker logs "${missing_container}" 2>&1)"
plaintext_status="$(docker inspect --format '{{.State.ExitCode}}' "${plaintext_container}")"
plaintext_state="$(docker inspect --format '{{.State.Status}}' "${plaintext_container}")"
plaintext_output="$(docker logs "${plaintext_container}" 2>&1)"

if [[ "${missing_state}" != "exited" ]] \
  || [[ "${missing_status}" -ne 78 ]] \
  || ! grep -Fxq 'BROWSER_CREDENTIAL_INVALID' <<<"${missing_output}"; then
  fail "missing Secret files must fail closed with exit 78"
fi
if [[ "${plaintext_state}" != "exited" ]] \
  || [[ "${plaintext_status}" -ne 78 ]] \
  || ! grep -Fxq 'BROWSER_CREDENTIAL_INVALID' <<<"${plaintext_output}"; then
  fail "plaintext credential environment must fail closed with exit 78"
fi

docker run -d \
  --name "${container}" \
  --shm-size=2g \
  --env 'NEKO_MEMBER_PROVIDER=multiuser' \
  --env 'NEKO_MEMBER_MULTIUSER_USER_PASSWORD_FILE=/run/secrets/browser-credentials/user-password' \
  --env 'NEKO_MEMBER_MULTIUSER_ADMIN_PASSWORD_FILE=/run/secrets/browser-credentials/admin-password' \
  --env 'NEKO_WEBRTC_ICELITE=true' \
  --env 'NEKO_WEBRTC_UDPMUX=52000' \
  --env 'NEKO_WEBRTC_NAT1TO1=127.0.0.1' \
  --mount "type=bind,src=${secret_directory}/user-password,dst=/run/secrets/browser-credentials/user-password,readonly" \
  --mount "type=bind,src=${secret_directory}/admin-password,dst=/run/secrets/browser-credentials/admin-password,readonly" \
  "${image}" >/dev/null

ready=false
for _ in {1..60}; do
  state="$(docker inspect --format '{{.State.Status}}' "${container}")"
  if [[ "${state}" == "exited" || "${state}" == "dead" ]]; then
    docker logs "${container}" >&2 || true
    fail "Browser exited before becoming ready"
  fi
  if docker exec "${container}" wget -q -O /dev/null http://127.0.0.1:6080/health; then
    ready=true
    break
  fi
  sleep 1
done
[[ "${ready}" == true ]] || fail "Browser did not become ready"

container_environment="$(docker inspect --format '{{range .Config.Env}}{{println .}}{{end}}' "${container}")"
if grep -Fq "${user_password}" <<<"${container_environment}" \
  || grep -Fq "${admin_password}" <<<"${container_environment}" \
  || grep -Eq '^NEKO_MEMBER_MULTIUSER_(USER|ADMIN)_PASSWORD=' <<<"${container_environment}"; then
  fail "Docker container environment contains plaintext Browser credentials"
fi

docker exec "${container}" /bin/sh -ec '
  user_password="$(cat /run/secrets/browser-credentials/user-password)"
  admin_password="$(cat /run/secrets/browser-credentials/admin-password)"
  test "$(stat -c %a /tmp/aileron-browser/neko.generated.yaml)" = "600"
  test "$(grep -Ec "^member:" /tmp/aileron-browser/neko.generated.yaml)" -eq 1
  grep -Fq "user_password: \"${user_password}\"" /tmp/aileron-browser/neko.generated.yaml
  grep -Fq "admin_password: \"${admin_password}\"" /tmp/aileron-browser/neko.generated.yaml
  for environment_file in /proc/[0-9]*/environ; do
    environment="$(cat "${environment_file}" 2>/dev/null | tr "\000" "\n" || true)"
    ! printf "%s\n" "${environment}" | grep -Fq "${user_password}"
    ! printf "%s\n" "${environment}" | grep -Fq "${admin_password}"
    ! printf "%s\n" "${environment}" | grep -Eq "^NEKO_MEMBER_MULTIUSER_(USER|ADMIN)_PASSWORD="
  done
  pid_one_environment="$(tr "\000" "\n" </proc/1/environ)"
  ! printf "%s\n" "${pid_one_environment}" | grep -Eq "^NEKO_WEBRTC_(ICELITE|UDPMUX|NAT1TO1)="
'

printf '%s\n' 'Docker Browser secret-file contract passed'
