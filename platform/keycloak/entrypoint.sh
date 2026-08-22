#!/bin/bash

set -euo pipefail

runtime_directory=/opt/keycloak/conf
config_file="${runtime_directory}/keycloak.conf"

read_required() {
  local path=$1
  test -s "${path}" || {
    printf 'Required Keycloak input is missing: %s\n' "${path}" >&2
    exit 1
  }
  local value
  value=$(<"${path}")
  test "${value}" = "${value//$'\n'/}" || {
    printf 'Required Keycloak input must be a single line: %s\n' "${path}" >&2
    exit 1
  }
  printf '%s' "${value}"
}

umask 077
if test "${1:-}" = bootstrap-principals; then
  shift
  realm=${1:?realm is required}
  server=${2:?server is required}
  admin_username=$(read_required /run/secrets/keycloak-bootstrap-admin/username)
  admin_password=$(read_required /run/secrets/keycloak-bootstrap-admin/password)
  platform_subject=$(read_required /run/secrets/keycloak-platform-admin/subject)
  platform_username=$(read_required /run/secrets/keycloak-platform-admin/username)
  platform_email=$(read_required /run/secrets/keycloak-platform-admin/email)
  platform_password=$(read_required /run/secrets/keycloak-platform-admin/password)
  break_glass_username=$(read_required /run/secrets/keycloak-break-glass/username)
  break_glass_email=$(read_required /run/secrets/keycloak-break-glass/email)
  break_glass_password=$(read_required /run/secrets/keycloak-break-glass/password)
  attempts=0
  while true; do
    export KC_CLI_PASSWORD="${admin_password}"
    if /opt/keycloak/bin/kcadm.sh config credentials --config /tmp/kcadm.config \
      --server "${server}" --realm master --user "${admin_username}" >/dev/null 2>&1; then
      unset KC_CLI_PASSWORD
      break
    fi
    unset KC_CLI_PASSWORD
    attempts=$((attempts + 1))
    test "${attempts}" -lt 60 || {
      printf 'Keycloak did not become ready for principal provisioning\n' >&2
      exit 1
    }
    sleep 2
  done
  if /opt/keycloak/bin/kcadm.sh get "users/${platform_subject}" --config /tmp/kcadm.config \
    -r "${realm}" >/dev/null 2>&1; then
    platform_user_id=${platform_subject}
  else
    username_user_id=$(/opt/keycloak/bin/kcadm.sh get users --config /tmp/kcadm.config \
      -r "${realm}" -q exact=true -q "username=${platform_username}" --fields id --format csv --noquotes | tail -n 1)
    test -z "${username_user_id}" || {
      printf 'Keycloak platform administrator username belongs to a different subject\n' >&2
      exit 1
    }
    /opt/keycloak/bin/kcadm.sh create partialImport --config /tmp/kcadm.config -r "${realm}" \
      -f /run/secrets/keycloak-platform-admin/import.json >/dev/null
    /opt/keycloak/bin/kcadm.sh get "users/${platform_subject}" --config /tmp/kcadm.config \
      -r "${realm}" >/dev/null 2>&1 || {
      printf 'Keycloak partial import did not create the configured platform administrator subject\n' >&2
      exit 1
    }
    platform_user_id=${platform_subject}
  fi
  test -n "${platform_user_id}" && test "${platform_user_id}" = "${platform_subject}" || {
    printf 'Keycloak platform administrator does not match the configured bootstrap subject\n' >&2
    exit 1
  }
  username_user_id=$(/opt/keycloak/bin/kcadm.sh get users --config /tmp/kcadm.config \
    -r "${realm}" -q exact=true -q "username=${platform_username}" --fields id --format csv --noquotes | tail -n 1)
  test -z "${username_user_id}" || test "${username_user_id}" = "${platform_subject}" || {
    printf 'Keycloak platform administrator username belongs to a different subject\n' >&2
    exit 1
  }
  /opt/keycloak/bin/kcadm.sh update "users/${platform_user_id}" --config /tmp/kcadm.config -r "${realm}" \
    -s "username=${platform_username}" -s "email=${platform_email}" \
    -s firstName=Platform -s 'lastName=Administrator' -s enabled=true -s emailVerified=true >/dev/null
  export KC_CLI_PASSWORD="${platform_password}"
  if /opt/keycloak/bin/kcadm.sh set-password --config /tmp/kcadm.config -r "${realm}" \
    --userid "${platform_user_id}" >/dev/null; then
    unset KC_CLI_PASSWORD
  else
    set_password_status=$?
    unset KC_CLI_PASSWORD
    exit "${set_password_status}"
  fi

  break_glass_user_id=$(/opt/keycloak/bin/kcadm.sh get users --config /tmp/kcadm.config \
    -r "${realm}" -q exact=true -q "username=${break_glass_username}" --fields id --format csv --noquotes | tail -n 1)
  if test -z "${break_glass_user_id}"; then
    break_glass_user_id=$(/opt/keycloak/bin/kcadm.sh create users --config /tmp/kcadm.config -r "${realm}" \
      -s "username=${break_glass_username}" -s "email=${break_glass_email}" \
      -s firstName=Local -s 'lastName=Emergency Administrator' -s enabled=true \
      -s emailVerified=true -i)
  fi
  test -n "${break_glass_user_id}" || {
    printf 'Keycloak did not return a break-glass user ID\n' >&2
    exit 1
  }
  /opt/keycloak/bin/kcadm.sh update "users/${break_glass_user_id}" --config /tmp/kcadm.config -r "${realm}" \
    -s "username=${break_glass_username}" -s "email=${break_glass_email}" \
    -s firstName=Local -s 'lastName=Emergency Administrator' -s enabled=true -s emailVerified=true >/dev/null
  export KC_CLI_PASSWORD="${break_glass_password}"
  if /opt/keycloak/bin/kcadm.sh set-password --config /tmp/kcadm.config -r "${realm}" \
    --userid "${break_glass_user_id}" >/dev/null; then
    unset KC_CLI_PASSWORD
  else
    set_password_status=$?
    unset KC_CLI_PASSWORD
    exit "${set_password_status}"
  fi
  rm -f -- /tmp/kcadm.config
  unset admin_password platform_password break_glass_password
  printf 'Keycloak platform administrator and native break-glass principals are ready\n'
  exit 0
fi

mkdir -p "${runtime_directory}"
if test -f /run/secrets/identity-postgres/username; then
  db_username=$(read_required /run/secrets/identity-postgres/username)
  db_password=$(read_required /run/secrets/identity-postgres/password)
  db_url=$(read_required /opt/aileron/public-config/db-url)
  database_config=$(printf 'db=postgres\ndb-url=%s\ndb-username=%s\ndb-password=%s\n' "${db_url}" "${db_username}" "${db_password}")
  admin_username=$(read_required /run/secrets/keycloak-bootstrap-admin/username)
  admin_password=$(read_required /run/secrets/keycloak-bootstrap-admin/password)
  hostname=$(read_required /opt/aileron/public-config/hostname)
  hostname_admin=$(read_required /opt/aileron/public-config/hostname-admin)
else
  database_config='db=dev-file'
  admin_username=${KEYCLOAK_BOOTSTRAP_ADMIN_USERNAME:?KEYCLOAK_BOOTSTRAP_ADMIN_USERNAME is required}
  admin_password=$(read_required /run/secrets/keycloak-bootstrap-admin-password)
  hostname=${KEYCLOAK_PUBLIC_HOSTNAME:?KEYCLOAK_PUBLIC_HOSTNAME is required}
  hostname_admin=${KEYCLOAK_ADMIN_HOSTNAME:-${hostname}}
fi

{
  printf '%s\n' "${database_config}"
  printf 'hostname=%s\n' "${hostname}"
  printf 'hostname-admin=%s\n' "${hostname_admin}"
  printf 'http-enabled=true\n'
  printf 'proxy-headers=xforwarded\n'
} >"${config_file}"
chmod 0600 "${config_file}"
export AILERON_BOOTSTRAP_ADMIN_PASSWORD=${admin_password}
if ! /opt/keycloak/bin/kc.sh bootstrap-admin user \
  --username "${admin_username}" \
  --password:env AILERON_BOOTSTRAP_ADMIN_PASSWORD \
  --no-prompt; then
  printf 'Dedicated Keycloak bootstrap administrator already exists or could not be recreated\n' >&2
fi
unset AILERON_BOOTSTRAP_ADMIN_PASSWORD db_username db_password db_url database_config admin_username admin_password hostname hostname_admin

exec /opt/keycloak/bin/kc.sh "$@"
