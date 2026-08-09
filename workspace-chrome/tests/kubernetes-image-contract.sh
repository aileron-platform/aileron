#!/usr/bin/env bash

set -euo pipefail

image="${1:?usage: $0 IMAGE}"
uids=(1000860000 1000860001)
containers=()

cleanup() {
  if ((${#containers[@]} > 0)); then
    docker rm -f "${containers[@]}" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

fail() {
  echo "Kubernetes browser image contract failed: $*" >&2
  exit 1
}

assert_rejected_credentials() {
  expected_code=78
  set +e
  output="$(
    docker run --rm \
      --env "NEKO_MEMBER_PROVIDER=${1:-}" \
      --env "NEKO_MEMBER_MULTIUSER_USER_PASSWORD=${2:-}" \
      --env "NEKO_MEMBER_MULTIUSER_ADMIN_PASSWORD=${3:-}" \
      "${image}" 2>&1
  )"
  status=$?
  set -e
  if [[ "${status}" -ne "${expected_code}" ]] \
    || ! grep -Fxq "BROWSER_CREDENTIAL_INVALID" <<<"${output}"; then
    fail "invalid Browser credentials must fail closed with exit 78"
  fi
}

assert_rejected_credentials "" "" ""
assert_rejected_credentials "multiuser" "same-password" "same-password"
assert_rejected_credentials "multiuser" "neko" "derived-admin-password"
assert_rejected_credentials "multiuser" "derived-user-password" "admin"

configured_user="$(docker image inspect --format '{{.Config.User}}' "${image}")"
if ! grep -Eq '^[1-9][0-9]*:[1-9][0-9]*$' <<<"${configured_user}"; then
  fail "image must declare a numeric non-root USER, found '${configured_user}'"
fi

docker run --rm --entrypoint /bin/sh "${image}" -ec '
  command -v curl >/dev/null
  test -r /opt/aileron/chromium-profile-seed/Default/Preferences
  test -r "/opt/aileron/chromium-profile-seed/Default/Google Profile Picture.png"
  test -x /usr/local/bin/aileron-browser-kubernetes-entrypoint
  test -r /etc/neko/neko.kubernetes.yaml
  test -r /etc/neko/supervisord.kubernetes.conf
  test -r /etc/neko/xorg.kubernetes.conf
  test -r /etc/pulse/default.kubernetes.pa
  test -r /etc/neko/supervisord.kubernetes/chromium.conf
  test -r /etc/neko/supervisord.kubernetes/cdp-relay.conf
  ! grep -RE "^[[:space:]]*user=|chown=" \
    /etc/neko/supervisord.kubernetes.conf \
    /etc/neko/supervisord.kubernetes/*.conf
  ! grep -E "(^|[[:space:]])(chown|su|sudo|gosu)([[:space:]]|$)" \
    /usr/local/bin/aileron-browser-kubernetes-entrypoint
  ! grep -RE "/var/(log|run)" \
    /etc/neko/supervisord.kubernetes.conf \
    /etc/neko/supervisord.kubernetes/*.conf
  grep -Fq "/tmp/aileron-browser/supervisor/supervisord.pid" \
    /etc/neko/supervisord.kubernetes.conf
  grep -Fxq "command=/usr/bin/neko serve --config /etc/neko/neko.kubernetes.yaml" \
    /etc/neko/supervisord.kubernetes.conf
  grep -Eq "^[[:space:]]+icelite: false$" /etc/neko/neko.kubernetes.yaml
  grep -Eq "^[[:space:]]+udpmux: 0$" /etc/neko/neko.kubernetes.yaml
  grep -Eq "^[[:space:]]+nat1to1: \[\]$" /etc/neko/neko.kubernetes.yaml
  grep -Eq "^[[:space:]]+ip_retrieval_url: \"\"$" /etc/neko/neko.kubernetes.yaml
  ! grep -Fq "127.0.0.1" /etc/neko/neko.kubernetes.yaml
  grep -Fq -- "--user-data-dir=%(ENV_AILERON_BROWSER_PROFILE_DIR)s" \
    /etc/neko/supervisord.kubernetes/chromium.conf
  grep -Fq "/tmp/aileron-browser/xf86-input-neko.sock" \
    /etc/neko/xorg.kubernetes.conf
  grep -Fq "socket=/tmp/aileron-browser/pulseaudio.socket" \
    /etc/pulse/default.kubernetes.pa
  test "${NEKO_DESKTOP_INPUT_SOCKET}" = "/tmp/aileron-browser/xf86-input-neko.sock"
'

assert_restricted_runtime() {
  uid="$1"
  container="aileron-browser-kubernetes-contract-${uid}-$$"
  containers+=("${container}")

  docker run -d \
    --name "${container}" \
    --read-only \
    --user "${uid}:${uid}" \
    --cap-drop ALL \
    --security-opt no-new-privileges \
    --env 'NEKO_MEMBER_PROVIDER=multiuser' \
    --env 'NEKO_MEMBER_MULTIUSER_USER_PASSWORD=contract-user-password' \
    --env 'NEKO_MEMBER_MULTIUSER_ADMIN_PASSWORD=contract-admin-password' \
    --env 'NEKO_WEBRTC_ICESERVERS_BACKEND=[{"urls":["turn:turn.internal.test:3478"],"username":"contract-user","credential":"contract-password"}]' \
    --env 'NEKO_WEBRTC_ICESERVERS_FRONTEND=[{"urls":["turn:turn.external.test:30478"],"username":"contract-user","credential":"contract-password"}]' \
    --tmpfs /tmp:rw,noexec,nosuid,nodev,size=1g \
    --tmpfs /dev/shm:rw,noexec,nosuid,nodev,size=1g \
    "${image}" >/dev/null

  ready=false
  for _ in {1..120}; do
    state="$(docker inspect --format '{{.State.Status}}' "${container}")"
    if [[ "${state}" == "exited" || "${state}" == "dead" ]]; then
      docker logs "${container}" >&2 || true
      fail "container for UID ${uid} exited before becoming ready"
    fi

    if docker exec --user "${uid}:${uid}" "${container}" \
      wget -q -O /dev/null http://127.0.0.1:6080/health \
      && docker exec --user "${uid}:${uid}" "${container}" \
        wget -q -O /tmp/aileron-browser/cdp-version.json \
        http://127.0.0.1:9223/json/version \
      && docker exec --user "${uid}:${uid}" "${container}" \
        /bin/sh -ec '
          supervisorctl -c /etc/neko/supervisord.kubernetes.conf status |
            awk '\''$2 != "RUNNING" { exit 1 }'\''
        '; then
      ready=true
      break
    fi
    sleep 1
  done

  if [[ "${ready}" != true ]]; then
    docker logs "${container}" >&2 || true
    fail "container for UID ${uid} did not expose Neko and CDP within 120 seconds"
  fi

  docker exec --user "${uid}:${uid}" \
    --env EXPECTED_UID="${uid}" \
    --env CONTRACT_TRACE="${CONTRACT_TRACE:-0}" \
    "${container}" \
    /bin/sh -ec '
      test "${CONTRACT_TRACE}" != "1" || set -x
      test "$(id -u)" = "${EXPECTED_UID}"
      if awk -F: -v expected="${EXPECTED_UID}" '\''$3 == expected { found=1 } END { exit found ? 0 : 1 }'\'' /etc/passwd; then
        echo "Arbitrary UID unexpectedly has a passwd entry" >&2
        exit 1
      fi
      test "$(awk '\''$1 == "NoNewPrivs:" { print $2 }'\'' /proc/1/status)" = "1"
      test "$(awk '\''$1 == "CapEff:" { print $2 }'\'' /proc/1/status)" = "0000000000000000"
      for status_file in /proc/[0-9]*/status; do
        process_uid="$(
          awk '\''$1 == "Uid:" { print $2 }'\'' "${status_file}" 2>/dev/null ||
            true
        )"
        test -z "${process_uid}" && continue
        test "${process_uid}" = "${EXPECTED_UID}"
      done
      test -S /tmp/.X11-unix/X99
      test -S /tmp/aileron-browser/xf86-input-neko.sock
      test -S /tmp/aileron-browser/pulseaudio.socket
      test ! -e /tmp/pulseaudio.socket
      test -z "$(find /tmp -mindepth 1 -maxdepth 1 \
        ! -name aileron-browser \
        ! -name .X11-unix \
        ! -name .X99-lock \
        -print -quit)"
      test -w /tmp/aileron-browser/chromium/Default/Preferences
      test -s /tmp/aileron-browser/cdp-version.json
      grep -Fq webSocketDebuggerUrl /tmp/aileron-browser/cdp-version.json
      touch /tmp/aileron-browser/write-probe
      touch /dev/shm/write-probe
      if touch /etc/aileron-browser-rootfs-write-probe 2>/dev/null; then
        echo "Root filesystem is writable" >&2
        exit 1
      fi
      if touch /opt/aileron/chromium-profile-seed/rootfs-write-probe 2>/dev/null; then
        echo "Immutable profile seed is writable" >&2
        exit 1
      fi
      supervisorctl -c /etc/neko/supervisord.kubernetes.conf status \
        | awk '\''$2 != "RUNNING" { exit 1 }'\''
    '

  logs="$(docker logs "${container}" 2>&1)"
  plain_logs="$(sed $'s/\033\\[[0-9;]*m//g' <<<"${logs}")"
  grep -Fq "neko ready" <<<"${logs}" \
    || fail "Neko did not report ready for UID ${uid}"
  grep -Fq 'config=/etc/neko/neko.kubernetes.yaml' <<<"${plain_logs}" \
    || fail "Neko did not load the generated Kubernetes config"
  grep -Eq 'webrtc starting.*epr=59000-59100.*icelite=false.*nat1to1= .*udpmux=0' <<<"${plain_logs}" \
    || fail "Neko did not parse the Kubernetes WebRTC profile"
  grep -Eq 'iceservers-backend=.*turn:turn\.internal\.test:3478.*contract-user' <<<"${plain_logs}" \
    || fail "Neko did not parse the backend TURN server"
  grep -Eq 'iceservers-frontend=.*turn:turn\.external\.test:30478.*contract-user' <<<"${plain_logs}" \
    || fail "Neko did not parse the frontend TURN server"
  if grep -Eq 'nat1to1=127\.0\.0\.1|udpmux=52000' <<<"${plain_logs}"; then
    fail "Neko inherited the Docker-only WebRTC profile"
  fi
  if grep -Fq "Can't drop privilege as nonroot user" <<<"${logs}"; then
    fail "supervisor attempted to change user for UID ${uid}"
  fi

  docker rm -f "${container}" >/dev/null
}

for uid in "${uids[@]}"; do
  assert_restricted_runtime "${uid}"
done

echo "Kubernetes browser image contract passed for arbitrary UIDs: ${uids[*]}"
