#!/bin/sh

set -eu

repo_root=${1:-/repo}
compose_file="${repo_root}/docker-compose.yml"
rendered=$(docker compose --env-file "${repo_root}/.env.example" --profile local-oidc -f "${compose_file}" config)
services=$(docker compose --env-file "${repo_root}/.env.example" --profile local-oidc -f "${compose_file}" config --services)

fail() {
  printf '%s\n' "$1" >&2
  exit 1
}

printf '%s\n' "${services}" | grep -Fxq keycloak || fail 'local-oidc profile does not render Keycloak'
printf '%s\n' "${services}" | grep -Fxq local-oidc-config || fail 'local-oidc profile does not render its realm adapter'
if printf '%s\n' "${services}" | grep -Eiq 'ldap|directory'; then
  fail 'local-oidc profile still renders a directory workload'
fi
if printf '%s\n' "${rendered}" | grep -Eiq 'openldap|ldap[_-](admin|config|alice|bob)|10-seed-users'; then
  fail 'local-oidc profile still exposes an LDAP contract'
fi
if [ -L "${repo_root}/directory" ] || {
  [ -d "${repo_root}/directory" ] &&
    find "${repo_root}/directory" -mindepth 1 -print -quit | grep -q .
}; then
  fail 'repository still contains an unused LDAP directory asset'
fi

printf '%s\n' "${rendered}" | grep -Fq 'keycloak-bootstrap-admin-password' ||
  fail 'Keycloak bootstrap administrator password is not an installation Secret'
printf '%s\n' "${rendered}" | grep -Fq 'KC_DB: dev-file' ||
  fail 'local Keycloak does not select its isolated dev-file database'
printf '%s\n' "${rendered}" | grep -Fq 'local-oidc-platform-admin-password' ||
  fail 'platform administrator password is not an installation Secret'
printf '%s\n' "${rendered}" | grep -Fq 'BOOTSTRAP_ADMIN_SUBJECT' ||
  fail 'local OIDC realm does not use the canonical platform administrator subject'
if printf '%s\n' "${rendered}" | grep -Fq 'LOCAL_OIDC_BREAK_GLASS'; then
  fail 'local OIDC retains a duplicate break-glass identity contract'
fi

printf '%s\n' 'Local OIDC Compose contract passed'
