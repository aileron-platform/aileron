#!/bin/sh

set -eu

repo_root=${1:-/repo}
compose_file="${repo_root}/docker-compose.yml"

fail() {
  printf '%s\n' "$1" >&2
  exit 1
}

test ! -e "${repo_root}/local-oidc/openldap-entrypoint.sh" ||
  fail 'obsolete OpenLDAP Secret bootstrap wrapper still exists'
test ! -e "${repo_root}/local-oidc/keycloak-entrypoint.sh" ||
  fail 'obsolete Keycloak Secret bootstrap wrapper still exists'

grep -Fq 'LDAP_ADMIN_PASSWORD_FILE: /run/secrets/ldap-admin-password' "${compose_file}" ||
  fail 'OpenLDAP does not use its native LDAP_ADMIN_PASSWORD_FILE adapter'
grep -Fq 'LDAP_CONFIG_PASSWORD_FILE: /run/secrets/ldap-config-password' "${compose_file}" ||
  fail 'OpenLDAP does not use its native LDAP_CONFIG_PASSWORD_FILE adapter'
grep -Fq -- '- start-dev' "${compose_file}" ||
  fail 'Keycloak does not use its native start-dev command'
grep -Fq -- '- --import-realm' "${compose_file}" ||
  fail 'Keycloak realm import is not enabled'
grep -Fq 'start_period: 6m' "${compose_file}" ||
  fail 'Keycloak healthcheck does not allow clean-volume initialization time'

if grep -Eq '(LDAP_ADMIN_PASSWORD|LDAP_CONFIG_PASSWORD|KC_BOOTSTRAP_ADMIN_PASSWORD)[=:]' "${compose_file}"; then
  fail 'Compose materializes a mounted Secret into a process environment or command'
fi
if grep -Fq 'KC_BOOTSTRAP_ADMIN_USERNAME' "${compose_file}" ||
  grep -Fq 'keycloak-admin-password' "${compose_file}"; then
  fail 'Compose retains the unnecessary Keycloak bootstrap administrator interface'
fi
if grep -Fq 'keycloak-entrypoint.sh' "${compose_file}" ||
  grep -Fq 'openldap-entrypoint.sh' "${compose_file}"; then
  fail 'Compose retains an obsolete local OIDC bootstrap wrapper'
fi

printf '%s\n' 'Local OIDC Secret bootstrap contract passed'
