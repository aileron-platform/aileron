#!/bin/sh

set -eu

chart_dir=${1:-/repo/helm/aileron-identity}
repository_root=$(CDPATH= cd -- "${chart_dir}/../.." && pwd)
homelab_values="${repository_root}/helm/values-rke2-207-homelab-identity.yaml"
external_database_values="${chart_dir}/tests/values/external-database.yaml"
namespace=aileron-identity-system
rendered=$(mktemp)
public_ingress=$(mktemp)
trap 'rm -f "${rendered}" "${public_ingress}"' EXIT INT TERM

fail() {
  printf '%s\n' "$1" >&2
  exit 1
}

has_prefix_path() {
  expected_path=$1
  manifest=$2
  awk -v expected_path="${expected_path}" '
    $0 == "          - path: " expected_path {
      matched_path = 1
      next
    }
    matched_path && $0 == "            pathType: Prefix" {
      found = 1
    }
    {
      matched_path = 0
    }
    END {
      exit found ? 0 : 1
    }
  ' "${manifest}"
}

assert_restricted_pods() {
  expected_pods=$1
  expected_keycloak_contexts=$2
  expected_postgres_pods=$3
  expected_postgres_contexts=$((expected_postgres_pods * 2))
  test "$(grep -c 'runAsNonRoot: true' "${rendered}")" -eq "$((expected_pods * 2))" ||
    fail 'an Identity Pod or container does not require a non-root user'
  test "$(grep -c 'seccompProfile:' "${rendered}")" -eq "${expected_pods}" ||
    fail 'an Identity Pod does not use RuntimeDefault seccomp'
  test "$(grep -c 'allowPrivilegeEscalation: false' "${rendered}")" -eq "${expected_pods}" ||
    fail 'an Identity container permits privilege escalation'
  test "$(grep -c 'drop: \["ALL"\]' "${rendered}")" -eq "${expected_pods}" ||
    fail 'an Identity container retains Linux capabilities'
  test "$(grep -c 'runAsUser: 1000' "${rendered}")" -eq "${expected_keycloak_contexts}" ||
    fail 'a Keycloak workload does not use the image UID'
  test "$(grep -c 'runAsGroup: 1000' "${rendered}")" -eq "${expected_keycloak_contexts}" ||
    fail 'a Keycloak workload does not use the image GID'
  test "$(grep -c 'runAsUser: 70' "${rendered}")" -eq "${expected_postgres_contexts}" ||
    fail 'a PostgreSQL workload does not use the image UID'
  test "$(grep -c 'runAsGroup: 70' "${rendered}")" -eq "${expected_postgres_contexts}" ||
    fail 'a PostgreSQL workload does not use the image GID'
  test "$(grep -c 'fsGroup: 70' "${rendered}")" -eq "${expected_postgres_pods}" ||
    fail 'a PostgreSQL Pod does not use the image GID for mounted storage'
  test "$(grep -c 'fsGroupChangePolicy: OnRootMismatch' "${rendered}")" -eq "${expected_postgres_pods}" ||
    fail 'a PostgreSQL Pod does not minimize mounted storage ownership changes'
  if grep -Eq '(fsGroup|runAsGroup|runAsUser): 999' "${rendered}"; then
    fail 'an Identity workload retains the removed PostgreSQL 999:999 identity'
  fi
}

helm lint "${chart_dir}" --namespace "${namespace}" >/dev/null
helm lint "${chart_dir}" --namespace "${namespace}" --values "${external_database_values}" >/dev/null
helm template aileron-identity "${chart_dir}" --namespace "${namespace}" >"${rendered}"

for kind in ConfigMap Deployment Ingress Job NetworkPolicy PersistentVolumeClaim Service; do
  grep -Eq "^kind: ${kind}$" "${rendered}" || fail "Identity Plane does not render ${kind}"
done
if grep -Eq '^kind: (Namespace|Secret)$' "${rendered}"; then
  fail 'Identity chart owns namespace creation or Secret generation'
fi
if grep -Eq 'secretKeyRef:|envFrom:|apk add|apt-get|curl .*https?://' "${rendered}"; then
  fail 'Identity workload uses Secret environment delivery or runtime package download'
fi
if grep -E '^ +image:' "${rendered}" | grep -Evq '@sha256:[a-f0-9]{64}"?$'; then
  fail 'Identity workload renders a mutable image tag'
fi
grep -Eq 'image: .*@sha256:[a-f0-9]{64}"?$' "${rendered}" || fail 'Identity workload does not render immutable image digests'
if grep -Fq 'helm.sh/resource-policy: keep' "${rendered}"; then
  fail 'Identity PVC or realm state is implicitly retained after uninstall'
fi
grep -Fq 'keycloak-bootstrap-admin' "${rendered}" || fail 'Keycloak administrator Secret reference is missing'
grep -Fq 'keycloak-platform-admin' "${rendered}" || fail 'Keycloak platform administrator Secret reference is missing'
grep -Fq 'keycloak-break-glass' "${rendered}" || fail 'Keycloak break-glass Secret reference is missing'
for break_glass_path in username email password; do
  grep -Fq "path: ${break_glass_path}" "${rendered}" ||
    fail "Keycloak break-glass Secret does not project ${break_glass_path}"
done
test "$(grep -c 'path: subject' "${rendered}")" -eq 1 ||
  fail 'only the platform administrator Secret may project a subject'
grep -Fq 'keycloak-realm-import' "${rendered}" || fail 'generated realm import Secret reference is missing'
grep -Fq 'path: import.json' "${rendered}" ||
  fail 'platform administrator Secret does not project its deterministic partial import'
grep -Fq 'identity-postgres' "${rendered}" || fail 'Identity PostgreSQL is not independently owned'
grep -Fq 'value: /var/lib/postgresql/data/pgdata' "${rendered}" ||
  fail 'Identity PostgreSQL does not initialize data in a process-owned PVC subdirectory'
if grep -Fq 'supplementalGroups:' "${rendered}"; then
  fail 'Identity PostgreSQL injects a mount-root group without an explicit storage contract'
fi
grep -Fq 'name: aileron-identity-backup' "${rendered}" || fail 'Identity chart does not own the backup PVC'
test "$(grep -c 'automountServiceAccountToken: false' "${rendered}")" -eq 3 ||
  fail 'an Identity Pod receives a Kubernetes API token'
test "$(grep -c 'readOnlyRootFilesystem: true' "${rendered}")" -eq 3 ||
  fail 'an Identity container has a writable root filesystem'
assert_restricted_pods 3 4 1
if grep -Eiq 'ldap|userstorageprovider|workspace-manager|manager.*api' "${rendered}"; then
  fail 'Identity Plane leaks LDAP or Aileron core ownership'
fi

helm template aileron-identity "${chart_dir}" --namespace "${namespace}" \
  --set backup.enabled=true >"${rendered}"
grep -Fq 'aileron-identity-backup' "${rendered}" || fail 'explicit backup hook is missing'
grep -Fq 'platform.aileron.dev/identity-data-operation: backup' "${rendered}" ||
  fail 'backup purpose identity is missing'
grep -Fq 'mv -f -- /backup/identity.dump.next /backup/identity.dump' "${rendered}" ||
  fail 'backup dump is not published atomically'
test "$(grep -c 'automountServiceAccountToken: false' "${rendered}")" -eq 4 ||
  fail 'the Identity backup Pod receives a Kubernetes API token'
test "$(grep -c 'readOnlyRootFilesystem: true' "${rendered}")" -eq 4 ||
  fail 'the Identity backup container has a writable root filesystem'
assert_restricted_pods 4 4 2

helm template aileron-identity "${chart_dir}" --namespace "${namespace}" \
  --set restore.enabled=true >"${rendered}"
grep -Fq 'aileron-identity-restore' "${rendered}" || fail 'explicit restore hook is missing'
grep -Fq 'platform.aileron.dev/identity-data-operation: restore' "${rendered}" ||
  fail 'restore purpose identity is missing'
test "$(grep -c 'automountServiceAccountToken: false' "${rendered}")" -eq 4 ||
  fail 'the Identity restore Pod receives a Kubernetes API token'
test "$(grep -c 'readOnlyRootFilesystem: true' "${rendered}")" -eq 4 ||
  fail 'the Identity restore container has a writable root filesystem'
assert_restricted_pods 4 4 2

if helm template aileron-identity "${chart_dir}" --namespace "${namespace}" \
  --set backup.enabled=true --set restore.enabled=true >/dev/null 2>&1; then
  fail 'backup and restore were accepted simultaneously'
fi
if helm template aileron-identity "${chart_dir}" --namespace "${namespace}" \
  --set issuerUrl=https://wrong.example.test/realms/aileron >/dev/null 2>&1; then
  fail 'issuer and public Identity hostname drift was accepted'
fi
if helm template aileron-identity "${chart_dir}" --namespace "${namespace}" \
  --set postgres.storage.mountRootSupplementalGroup=0 >/dev/null 2>&1; then
  fail 'a root supplemental group was accepted for the PostgreSQL mount root'
fi
if helm template aileron-identity "${chart_dir}" --namespace "${namespace}" \
  --set secrets.breakGlass.subjectKey=subject >/dev/null 2>&1; then
  fail 'the removed Kubernetes break-glass subject field was accepted'
fi
if helm template aileron-identity "${chart_dir}" --namespace "${namespace}" \
  --set secrets.platformAdministrator.subjectKey= >/dev/null 2>&1; then
  fail 'a platform administrator Secret without a subject key was accepted'
fi
if helm template aileron-identity "${chart_dir}" --namespace "${namespace}" \
  --set secrets.platformAdministrator.importKey= >/dev/null 2>&1; then
  fail 'a platform administrator Secret without an import key was accepted'
fi
if helm template aileron-identity "${chart_dir}" --namespace "${namespace}" \
  --set secrets.platformAdministrator.unexpectedKey=unexpected >/dev/null 2>&1; then
  fail 'an unknown platform administrator Secret key was accepted'
fi

external_database_args="--set postgres.enabled=false --set postgres.jdbcUrl=jdbc:postgresql://identity-db.example.test:5432/keycloak?sslmode=verify-full --set postgres.revision=identity-database-v1 --set postgres.caSecretName=identity-database-ca --set postgres.caSecretKey=ca.crt"
# shellcheck disable=SC2086
helm template aileron-identity "${chart_dir}" --namespace "${namespace}" \
  ${external_database_args} \
  --set networkPolicy.externalDatabaseEgress.mode=disabled >"${rendered}"
if test "$(yq eval-all 'select(.metadata.name == "aileron-identity-postgres") | .kind' "${rendered}" | wc -l)" -ne 0; then
  fail 'external Identity mode still renders chart-owned PostgreSQL resources'
fi
grep -Fq 'aileron.io/identity-database-revision: "identity-database-v1"' "${rendered}" ||
  fail 'external Identity database revision does not roll Keycloak'
grep -Fq 'jdbc:postgresql://identity-db.example.test:5432/keycloak?sslmode=verify-full&sslrootcert=/etc/aileron/data-service-ca/identity-database/ca.crt' "${rendered}" ||
  fail 'Keycloak does not use the external JDBC topology and fixed CA path'
grep -Fq 'mountPath: /etc/aileron/data-service-ca/identity-database' "${rendered}" ||
  fail 'external Identity database CA is not mounted at the fixed path'
test "$(yq eval-all 'select(.metadata.name == "aileron-identity-data-service-preflight" and .metadata.annotations."helm.sh/hook" == "pre-install,pre-upgrade,pre-rollback") | [.kind, .metadata.annotations."helm.sh/hook-weight"] | @tsv' "${rendered}")" = "$(printf 'ConfigMap\t-30\tJob\t-20')" ||
  fail 'external Identity preflight ConfigMap and Job do not preserve hook ordering'
test "$(yq eval-all 'select(.kind == "Job" and .metadata.name == "aileron-identity-data-service-preflight") | [.spec.template.spec.securityContext.runAsUser, .spec.template.spec.securityContext.runAsGroup, .spec.template.spec.securityContext.fsGroup, .spec.template.spec.securityContext.fsGroupChangePolicy] | @tsv' "${rendered}")" = "$(printf '70\t70\t70\tOnRootMismatch')" ||
  fail 'external Identity preflight cannot read group-projected database credentials as the PostgreSQL image identity'
test "$(yq eval-all 'select(.metadata.name == "aileron-identity-data-service-preflight") | .metadata.annotations."helm.sh/hook"' "${rendered}" | grep -Fxc 'pre-install,pre-upgrade,pre-rollback')" -eq 2 ||
  fail 'external Identity preflight does not gate install, upgrade, and rollback'
test "$(yq eval-all 'select(.metadata.name == "aileron-identity-data-service-preflight" and .metadata.labels."app.kubernetes.io/component" == "data-service-hook-cleanup") | [.metadata.annotations."helm.sh/hook", .metadata.annotations."helm.sh/hook-delete-policy"] | @tsv' "${rendered}")" = "$(printf 'post-delete\tbefore-hook-creation,hook-succeeded')" ||
  fail 'external Identity preflight ConfigMap is not removed after uninstall'
test "$(yq eval-all 'select(.kind == "NetworkPolicy" and .metadata.name == "aileron-identity-keycloak") | .spec.policyTypes | join(",")' "${rendered}")" = 'Ingress' ||
  fail 'disabled external database egress still isolates Keycloak egress'
if yq eval-all 'select(.kind == "NetworkPolicy" and .metadata.name == "aileron-identity-keycloak") | has("spec.egress")' "${rendered}" | grep -Fqx true; then
  fail 'disabled external database egress still renders egress rules'
fi

# shellcheck disable=SC2086
helm template aileron-identity "${chart_dir}" --namespace "${namespace}" \
  ${external_database_args} \
  --set backup.enabled=true \
  --set networkPolicy.externalDatabaseEgress.mode=selector \
  --set networkPolicy.externalDatabaseEgress.namespaceLabels.database=external \
  --set networkPolicy.externalDatabaseEgress.podLabels.app=postgres >"${rendered}"
grep -Fq 'value: "postgresql://identity-db.example.test:5432/keycloak?sslmode=verify-full&sslrootcert=/etc/aileron/data-service-ca/identity-database/ca.crt"' "${rendered}" ||
  fail 'Identity backup does not use the external libpq topology and fixed CA path'
grep -Fq "printf '*:*:*:%s:%s\\n'" "${rendered}" ||
  fail 'Identity backup does not use a topology-independent pgpass entry'
grep -Fq 'database: external' "${rendered}" ||
  fail 'selector-mode external database namespace selector is missing'
grep -Fq 'app: postgres' "${rendered}" ||
  fail 'selector-mode external database Pod selector is missing'

# shellcheck disable=SC2086
helm template aileron-identity "${chart_dir}" --namespace "${namespace}" \
  ${external_database_args} \
  --set restore.enabled=true \
  --set networkPolicy.externalDatabaseEgress.mode=ipBlock \
  --set networkPolicy.externalDatabaseEgress.cidr=10.24.0.0/16 >"${rendered}"
grep -Fq 'cidr: "10.24.0.0/16"' "${rendered}" ||
  fail 'ipBlock-mode external database CIDR is missing'
grep -Fq 'pg_restore --username="$username" --clean --if-exists --no-owner --dbname="$DATABASE_URL"' "${rendered}" ||
  fail 'Identity restore does not use the external libpq topology'

for invalid_external_args in \
  '--set postgres.enabled=false --set postgres.jdbcUrl=jdbc:postgresql://identity-db.example.test/keycloak --set networkPolicy.externalDatabaseEgress.mode=disabled' \
  '--set postgres.enabled=false --set postgres.jdbcUrl=jdbc:postgresql://identity-db.example.test/keycloak?sslmode=verify-full&sslrootcert=/tmp/ca.crt --set postgres.revision=v1 --set networkPolicy.externalDatabaseEgress.mode=disabled' \
  '--set postgres.enabled=false --set postgres.jdbcUrl=jdbc:postgresql://identity-db.example.test/keycloak --set postgres.revision=v1 --set postgres.caSecretName=ca --set postgres.caSecretKey=ca.crt --set networkPolicy.externalDatabaseEgress.mode=disabled'; do
  # shellcheck disable=SC2086
  if helm template aileron-identity "${chart_dir}" --namespace "${namespace}" ${invalid_external_args} >/dev/null 2>&1; then
    fail 'an incomplete or ambiguous external Identity database contract was accepted'
  fi
done

helm template aileron-identity "${chart_dir}" --namespace "${namespace}" \
  --values "${homelab_values}" \
  --set images.keycloak.digest=sha256:cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc \
  --set images.postgres.digest=sha256:dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd \
  >"${rendered}"
for expected in \
  'harbor-rke-creds' \
  'harbor.rke.soez.tw/library/platform-keycloak@sha256:cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc' \
  'harbor.rke.soez.tw/library/platform-postgres@sha256:dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd' \
  'keycloak.apps.rke.soez.tw' \
  'keycloak-admin.apps.rke.soez.tw' \
  'keycloak-apps-tls' \
  'aileron-local-rwo-retain' \
  'aileron-nfs-rwx-retain' \
  'ReadWriteMany' \
  'nginx.ingress.kubernetes.io/whitelist-source-range: "192.168.50.0/24"' \
  'https://keycloak.apps.rke.soez.tw/realms/aileron' \
  'https://aileron.apps.rke.soez.tw/api/v1/oauth2/callback' \
  'aileron-frontend' \
  'kubernetes.io/metadata.name: kube-system'; do
  grep -Fq "${expected}" "${rendered}" || fail "HomeLab Identity profile does not render ${expected}"
done
grep -A1 '^        supplementalGroups:$' "${rendered}" | grep -Fq '          - 100' ||
  fail 'HomeLab Identity PostgreSQL does not receive the local-path mount-root group'
test "$(grep -c '^kind: Ingress$' "${rendered}")" -eq 2 ||
  fail 'HomeLab Identity profile does not enable both public and admin ingress'
awk '
  /^---$/ {
    if (capture) {
      exit
    }
    kind = ""
  }
  /^kind:/ {
    kind = $2
  }
  kind == "Ingress" && $0 == "  name: aileron-identity" {
    capture = 1
  }
  capture {
    print
  }
' "${rendered}" >"${public_ingress}"
has_prefix_path '/realms/master/protocol/openid-connect' "${public_ingress}" ||
  fail 'public Identity ingress does not expose the Keycloak master realm OIDC protocol endpoints'
has_prefix_path '/realms/master/login-actions' "${public_ingress}" ||
  fail 'public Identity ingress does not expose the Keycloak master realm login actions'
if has_prefix_path '/realms/master' "${public_ingress}" ||
  has_prefix_path '/realms/master/' "${public_ingress}"; then
  fail 'public Identity ingress exposes the whole Keycloak master realm'
fi
core_client_id=$(awk '/^oidc:$/ { in_oidc=1; next } in_oidc && /^  clientId:/ { print $2; exit }' \
  "${repository_root}/helm/values-rke2-207-homelab.yaml")
identity_client_id=$(awk '/^clientId:/ { print $2; exit }' "${homelab_values}")
test "${identity_client_id}" = "${core_client_id}" || fail 'HomeLab core and Identity client IDs drifted'

printf '%s\n' 'Identity Plane Helm contract passed'
