#!/bin/sh

set -eu

suffix="$(date +%s)-$$"
network="aileron-local-oidc-contract-${suffix}"
secret_volume="aileron-local-oidc-secrets-${suffix}"
ldap_data_volume="aileron-local-oidc-ldap-data-${suffix}"
ldap_config_volume="aileron-local-oidc-ldap-config-${suffix}"
keycloak_data_volume="aileron-local-oidc-keycloak-data-${suffix}"
ldap_container="aileron-local-oidc-openldap-${suffix}"
keycloak_container="aileron-local-oidc-keycloak-${suffix}"

cleanup() {
  docker rm -f "${ldap_container}" "${keycloak_container}" >/dev/null 2>&1 || true
  docker network rm "${network}" >/dev/null 2>&1 || true
  docker volume rm \
    "${secret_volume}" \
    "${ldap_data_volume}" \
    "${ldap_config_volume}" \
    "${keycloak_data_volume}" >/dev/null 2>&1 || true
}
trap cleanup EXIT INT TERM

fail() {
  printf '%s\n' "$1" >&2
  exit 1
}

wait_for_command() {
  container="$1"
  shift
  attempt=0
  while test "${attempt}" -lt 180; do
    if docker exec "${container}" "$@" >/dev/null 2>&1; then
      return 0
    fi
    if test "$(docker inspect "${container}" --format '{{.State.Running}}' 2>/dev/null || true)" != true; then
      docker logs "${container}" >&2 || true
      fail "container exited before becoming ready: ${container}"
    fi
    attempt=$((attempt + 1))
    sleep 1
  done
  docker logs "${container}" >&2 || true
  fail "container did not become ready: ${container}"
}

docker network create "${network}" >/dev/null
docker volume create "${secret_volume}" >/dev/null
docker volume create "${ldap_data_volume}" >/dev/null
docker volume create "${ldap_config_volume}" >/dev/null
docker volume create "${keycloak_data_volume}" >/dev/null

docker run --rm --mount "type=volume,src=${secret_volume},dst=/run/secrets" alpine:3.20 sh -ec '
  umask 0077
  head -c 32 /dev/urandom | base64 | tr -d "\n" > /run/secrets/ldap-admin-password
  head -c 32 /dev/urandom | base64 | tr -d "\n" > /run/secrets/ldap-config-password
  chmod 0400 /run/secrets/ldap-admin-password /run/secrets/ldap-config-password
'

docker run -d \
  --name "${ldap_container}" \
  --network "${network}" \
  --mount "type=volume,src=${secret_volume},dst=/run/secrets,readonly" \
  --mount "type=volume,src=${ldap_data_volume},dst=/var/lib/ldap" \
  --mount "type=volume,src=${ldap_config_volume},dst=/etc/ldap/slapd.d" \
  -e LDAP_ORGANISATION=Aileron \
  -e LDAP_DOMAIN=aileron.local \
  -e LDAP_TLS=false \
  -e LDAP_READONLY_USER=false \
  -e LDAP_ADMIN_PASSWORD_FILE=/run/secrets/ldap-admin-password \
  -e LDAP_CONFIG_PASSWORD_FILE=/run/secrets/ldap-config-password \
  osixia/openldap:1.5.0 >/dev/null

wait_for_command "${ldap_container}" ldapwhoami \
  -x -H ldap://127.0.0.1:389 \
  -D cn=admin,dc=aileron,dc=local \
  -y /run/secrets/ldap-admin-password

docker exec "${ldap_container}" sh -ec '
  for process in /proc/[0-9]*; do
    test -r "${process}/environ" || continue
    for secret_file in /run/secrets/ldap-admin-password /run/secrets/ldap-config-password; do
      if grep -aF -f "${secret_file}" "${process}/environ" >/dev/null 2>&1; then
        exit 1
      fi
      if test -r "${process}/cmdline" && grep -aF -f "${secret_file}" "${process}/cmdline" >/dev/null 2>&1; then
        exit 1
      fi
    done
  done
' || fail 'OpenLDAP materialized a mounted Secret in a long-lived process'

docker run --rm --mount "type=volume,src=${keycloak_data_volume},dst=/opt/keycloak/data" alpine:3.20 sh -ec '
  mkdir -p /opt/keycloak/data/import
  printf "%s\n" "{\"realm\":\"aileron-contract\",\"enabled\":true}" > /opt/keycloak/data/import/aileron-contract.json
  chmod 0600 /opt/keycloak/data/import/aileron-contract.json
  chown -R 1000:0 /opt/keycloak/data
'

docker run -d \
  --name "${keycloak_container}" \
  --network "${network}" \
  --mount "type=volume,src=${keycloak_data_volume},dst=/opt/keycloak/data" \
  -e KC_DB=dev-file \
  -e KC_HTTP_ENABLED=true \
  -e KC_HOSTNAME_STRICT=false \
  quay.io/keycloak/keycloak:25.0.0 \
  start-dev --import-realm >/dev/null

wait_for_command "${keycloak_container}" bash -c ':> /dev/tcp/127.0.0.1/8080'

docker run --rm --network "${network}" alpine:3.20 sh -ec '
  wget -qO- http://'"${keycloak_container}"':8080/realms/aileron-contract/.well-known/openid-configuration >/dev/null
'

if docker inspect "${keycloak_container}" --format '{{range .Config.Env}}{{println .}}{{end}}' |
  grep -Eq '^KC_BOOTSTRAP_ADMIN_(USERNAME|PASSWORD)='; then
  fail 'Keycloak retains a bootstrap administrator environment interface'
fi

printf '%s\n' 'Local OIDC image Secret-file contract passed'
