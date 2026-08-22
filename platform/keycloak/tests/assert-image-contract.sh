#!/bin/sh

set -eu

repo_root=${1:-/repo}
dockerfile="${repo_root}/platform/keycloak/Dockerfile"
bake_file="${repo_root}/docker-bake.hcl"

fail() {
  printf '%s\n' "$1" >&2
  exit 1
}

grep -Eq '^FROM quay\.io/keycloak/keycloak:[^ ]+@sha256:[a-f0-9]{64}' "${dockerfile}" ||
  fail 'platform-keycloak base image is not pinned by digest'
grep -Fq 'USER 1000:1000' "${dockerfile}" || fail 'platform-keycloak does not run as its fixed non-root user'
if grep -Eiq 'apk add|apt-get|dnf install|microdnf install|curl .*https?://' "${repo_root}/platform/keycloak/entrypoint.sh"; then
  fail 'platform-keycloak downloads runtime dependencies'
fi
if grep -Eq -- '--password[ =].*(admin_password|password)|--new-password' "${repo_root}/platform/keycloak/entrypoint.sh"; then
  fail 'platform-keycloak passes a Secret sentinel through process argv'
fi
if grep -Fq "printf '%s\\n' \"\${admin_password}\" |" "${repo_root}/platform/keycloak/entrypoint.sh"; then
  fail 'platform-keycloak administrator credential still relies on an interactive stdin prompt'
fi
grep -Fq 'export KC_CLI_PASSWORD="${admin_password}"' "${repo_root}/platform/keycloak/entrypoint.sh" ||
  fail 'platform-keycloak administrator credential does not use the supported CLI environment'
if grep -Eq "printf '%s\\n' \"\$\{(platform_password|break_glass_password)\}\" \|" "${repo_root}/platform/keycloak/entrypoint.sh"; then
  fail 'platform-keycloak break-glass credential still relies on an interactive stdin prompt'
fi
grep -Fq 'export KC_CLI_PASSWORD="${platform_password}"' "${repo_root}/platform/keycloak/entrypoint.sh" ||
  fail 'platform-keycloak platform administrator credential does not use the supported CLI environment'
grep -Fq 'export KC_CLI_PASSWORD="${break_glass_password}"' "${repo_root}/platform/keycloak/entrypoint.sh" ||
  fail 'platform-keycloak break-glass credential does not use the supported CLI environment'
test "$(grep -Ec '^[[:space:]]+unset KC_CLI_PASSWORD$' "${repo_root}/platform/keycloak/entrypoint.sh")" -eq 6 ||
  fail 'platform-keycloak does not clear CLI passwords after success and failure'
if grep -Eq 'keycloak-break-glass/subject|-s "id=\$\{break_glass_subject\}"' "${repo_root}/platform/keycloak/entrypoint.sh"; then
  fail 'platform-keycloak accepts a caller-supplied break-glass subject'
fi
grep -Fq 'get "users/${platform_subject}"' "${repo_root}/platform/keycloak/entrypoint.sh" ||
  fail 'platform-keycloak does not resolve the canonical platform administrator by subject first'
grep -Fq 'username belongs to a different subject' "${repo_root}/platform/keycloak/entrypoint.sh" ||
  fail 'platform-keycloak does not reject a platform administrator username collision'
grep -Fq 'create partialImport' "${repo_root}/platform/keycloak/entrypoint.sh" ||
  fail 'platform-keycloak does not use deterministic partial import for an existing realm'
grep -Fq -- '-f /run/secrets/keycloak-platform-admin/import.json' "${repo_root}/platform/keycloak/entrypoint.sh" ||
  fail 'platform-keycloak does not consume the installation-owned deterministic realm import'
if grep -Fq -- '-s "id=${platform_subject}"' "${repo_root}/platform/keycloak/entrypoint.sh"; then
  fail 'platform-keycloak still assumes create-users preserves a caller-supplied subject'
fi
grep -Fq -- '--userid "${platform_user_id}"' "${repo_root}/platform/keycloak/entrypoint.sh" ||
  fail 'platform-keycloak does not reset the canonical user ID password'

rendered=$(docker buildx bake --file "${bake_file}" --print platform-keycloak platform-keycloak-kubernetes)
printf '%s\n' "${rendered}" | grep -Fq 'platform/keycloak' || fail 'bake targets do not own the Keycloak build context'
printf '%s\n' "${rendered}" | grep -Fq 'platform-keycloak:dev' || fail 'local Keycloak image target is missing'
printf '%s\n' "${rendered}" | grep -Fq 'platform-keycloak:latest-kubernetes' || fail 'release Keycloak image target is missing'

printf '%s\n' 'platform-keycloak image contract passed'
