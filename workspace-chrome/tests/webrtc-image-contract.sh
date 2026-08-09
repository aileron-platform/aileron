#!/usr/bin/env bash
set -euo pipefail

image="${1:?usage: $0 IMAGE}"
container="neko-image-contract-$RANDOM-$$"
secret_directory="$(mktemp -d)"

cleanup() {
  docker rm -f "$container" >/dev/null 2>&1 || true
  rm -f \
    "${secret_directory}/user-password" \
    "${secret_directory}/admin-password"
  rmdir "${secret_directory}" >/dev/null 2>&1 || true
}
trap cleanup EXIT

printf '%s' '0123456789012345678901234567890123456789012' \
  >"${secret_directory}/user-password"
printf '%s' 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQ' \
  >"${secret_directory}/admin-password"
chmod 0600 \
  "${secret_directory}/user-password" \
  "${secret_directory}/admin-password"

docker run --rm --entrypoint /bin/sh "$image" -c '
  set -eu
  test "$(grep -Ec "^capture:" /etc/neko/neko.yaml)" -eq 1
  test "$(grep -Ec "^[[:space:]]+show_pointer: false$" /etc/neko/neko.yaml)" -eq 2
  grep -Fq "ids: [main]" /etc/neko/neko.yaml
  grep -Fq "implicit_hosting: true" /etc/neko/neko.yaml
  grep -Eq "^[[:space:]]+icelite: false$" /etc/neko/neko.yaml
  grep -Eq "^[[:space:]]+udpmux: 0$" /etc/neko/neko.yaml
  grep -Eq "^[[:space:]]+nat1to1: \[\]$" /etc/neko/neko.yaml
  grep -Eq "^[[:space:]]+ip_retrieval_url: \"\"$" /etc/neko/neko.yaml
  ! grep -Fq "127.0.0.1" /etc/neko/neko.yaml
  grep -Fxq "command=/usr/bin/neko serve" /etc/neko/supervisord.conf
  ! grep -Fq -- "--server.static" /etc/neko/supervisord.conf
  test "$NEKO_LEGACY" = true
  test "$NEKO_PLUGINS_ENABLED" = false
  test "$NEKO_CHAT_ENABLED" = false
  test "$NEKO_FILETRANSFER_ENABLED" = false
  test "$NEKO_CAPTURE_BROADCAST_AUTOSTART" = false
  test "$NEKO_CAPTURE_SCREENCAST_ENABLED" = false
  test "$NEKO_CAPTURE_WEBCAM_ENABLED" = false
  test "$NEKO_CAPTURE_MICROPHONE_ENABLED" = false
  test "$NEKO_SESSION_INACTIVE_CURSORS" = false
'

docker run -d \
  --name "$container" \
  --shm-size=2g \
  --env 'NEKO_MEMBER_PROVIDER=multiuser' \
  --env 'NEKO_MEMBER_MULTIUSER_USER_PASSWORD_FILE=/run/secrets/browser-credentials/user-password' \
  --env 'NEKO_MEMBER_MULTIUSER_ADMIN_PASSWORD_FILE=/run/secrets/browser-credentials/admin-password' \
  --mount "type=bind,src=${secret_directory}/user-password,dst=/run/secrets/browser-credentials/user-password,readonly" \
  --mount "type=bind,src=${secret_directory}/admin-password,dst=/run/secrets/browser-credentials/admin-password,readonly" \
  "$image" >/dev/null
ready=false
for _ in {1..120}; do
  logs="$(docker logs "$container" 2>&1)"
  if grep -Fq 'neko ready' <<<"$logs"; then
    ready=true
    break
  fi
  sleep 1
done
if [[ "${ready}" != true ]]; then
  docker logs "$container" >&2 || true
  printf '%s\n' 'Neko image contract failed: Browser did not become ready' >&2
  exit 1
fi

docker exec "$container" supervisorctl status neko | grep -Fq RUNNING
logs="$(docker logs "$container" 2>&1)"
test "$(grep -Fc 'show-pointer=false' <<<"$logs")" -eq 2
! grep -Fq 'show-pointer=true' <<<"$logs"
grep -Eq 'video_id=.*main' <<<"$logs"
grep -Eq 'video_id=.*legacy' <<<"$logs"

printf '%s\n' 'Neko image contract passed'
