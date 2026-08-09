#!/bin/sh

set -eu

browser_user_password="${NEKO_MEMBER_MULTIUSER_USER_PASSWORD:-}"
browser_admin_password="${NEKO_MEMBER_MULTIUSER_ADMIN_PASSWORD:-}"
if [ -z "${browser_user_password}" ] \
  || [ -z "${browser_admin_password}" ] \
  || [ "${browser_user_password}" = "${browser_admin_password}" ] \
  || [ "${browser_user_password}" = "neko" ] \
  || [ "${browser_user_password}" = "admin" ] \
  || [ "${browser_admin_password}" = "neko" ] \
  || [ "${browser_admin_password}" = "admin" ]; then
  printf '%s\n' 'BROWSER_CREDENTIAL_INVALID' >&2
  exit 78
fi
if [ "${NEKO_MEMBER_PROVIDER:-}" != "multiuser" ]; then
  printf '%s\n' 'BROWSER_CREDENTIAL_INVALID' >&2
  exit 78
fi

state_dir=/tmp/aileron-browser
profile_dir="${state_dir}/chromium"
profile_seed_dir=/opt/aileron/chromium-profile-seed
supervisor_dir="${state_dir}/supervisor"

umask 0077
mkdir -p \
  "${state_dir}/home" \
  "${state_dir}/runtime" \
  "${state_dir}/tmp" \
  "${profile_dir}/Default" \
  "${supervisor_dir}"

rm -f \
  "${supervisor_dir}/supervisord.pid" \
  "${supervisor_dir}/supervisor.sock" \
  "${state_dir}/pulseaudio.socket"

seed_profile_file() {
  source_path="$1"
  destination_path="$2"

  if [ ! -e "${destination_path}" ]; then
    cp "${source_path}" "${destination_path}"
    chmod 0600 "${destination_path}"
  fi
}

seed_profile_file \
  "${profile_seed_dir}/Default/Preferences" \
  "${profile_dir}/Default/Preferences"
seed_profile_file \
  "${profile_seed_dir}/Default/Google Profile Picture.png" \
  "${profile_dir}/Default/Google Profile Picture.png"

exec "$@"
