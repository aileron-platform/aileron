#!/bin/sh

set -eu

fail() {
  printf '%s\n' 'BROWSER_CREDENTIAL_INVALID' >&2
  exit 78
}

read_secret() {
  secret_file="$1"
  [ -f "${secret_file}" ] || fail
  [ ! -L "${secret_file}" ] || fail
  [ -r "${secret_file}" ] || fail
  secret_size="$(wc -c <"${secret_file}" | tr -d ' ')"
  [ "${secret_size}" = "43" ] || fail
  secret_value="$(cat "${secret_file}")"
  case "${secret_value}" in
    *[!A-Za-z0-9_-]*) fail ;;
  esac
  printf '%s' "${secret_value}"
}

if [ "${NEKO_MEMBER_MULTIUSER_USER_PASSWORD+x}" = "x" ] \
  || [ "${NEKO_MEMBER_MULTIUSER_ADMIN_PASSWORD+x}" = "x" ] \
  || [ "${NEKO_MEMBER_PROVIDER:-}" != "multiuser" ]; then
  fail
fi

user_password_file="${NEKO_MEMBER_MULTIUSER_USER_PASSWORD_FILE:-}"
admin_password_file="${NEKO_MEMBER_MULTIUSER_ADMIN_PASSWORD_FILE:-}"
[ -n "${user_password_file}" ] || fail
[ -n "${admin_password_file}" ] || fail

browser_user_password="$(read_secret "${user_password_file}")"
browser_admin_password="$(read_secret "${admin_password_file}")"
[ "${browser_user_password}" != "${browser_admin_password}" ] || fail

state_directory=/tmp/aileron-browser
generated_config="${state_directory}/neko.generated.yaml"
generated_supervisor="${state_directory}/supervisord.generated.conf"

umask 0077
mkdir -p "${state_directory}"
chmod 0711 "${state_directory}"
awk '
  /^member:[[:space:]]*$/ { skipping_member = 1; next }
  skipping_member && /^[^[:space:]#][^:]*:/ { skipping_member = 0 }
  !skipping_member { print }
' /etc/neko/neko.yaml >"${generated_config}"
cat >>"${generated_config}" <<EOF

member:
  provider: multiuser
  multiuser:
    user_password: "${browser_user_password}"
    admin_password: "${browser_admin_password}"
EOF
chown neko:neko "${generated_config}"
chmod 0600 "${generated_config}"

sed \
  "s|command=/usr/bin/neko serve|command=/usr/bin/neko serve --config ${generated_config}|" \
  /etc/neko/supervisord.conf >"${generated_supervisor}"
grep -Fxq \
  "command=/usr/bin/neko serve --config ${generated_config}" \
  "${generated_supervisor}" || fail
chmod 0600 "${generated_supervisor}"

unset \
  browser_user_password \
  browser_admin_password \
  user_password_file \
  admin_password_file \
  secret_file \
  secret_value \
  secret_size

exec /usr/bin/env \
  -u NEKO_MEMBER_MULTIUSER_USER_PASSWORD \
  -u NEKO_MEMBER_MULTIUSER_ADMIN_PASSWORD \
  -u NEKO_MEMBER_MULTIUSER_USER_PASSWORD_FILE \
  -u NEKO_MEMBER_MULTIUSER_ADMIN_PASSWORD_FILE \
  -u NEKO_WEBRTC_ICELITE \
  -u NEKO_WEBRTC_UDPMUX \
  -u NEKO_WEBRTC_NAT1TO1 \
  "$@"
