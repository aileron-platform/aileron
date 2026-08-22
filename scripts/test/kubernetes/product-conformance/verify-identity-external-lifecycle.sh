#!/bin/sh

set -eu

repo_root="${REPO_ROOT:-/repo}"
namespace="${E2E_NAMESPACE:?E2E_NAMESPACE is required}"
run_id="${E2E_RUN_ID:?E2E_RUN_ID is required}"
data_namespace="${PRODUCT_DATA_SERVICE_NAMESPACE:-${namespace}-data}"
identity_namespace="${namespace}-identity"
storage_mode="${E2E_STORAGE_MODE:?E2E_STORAGE_MODE is required}"
storage_class="${RWO_STORAGE_CLASS:?RWO_STORAGE_CLASS is required}"
nfs_server="${NFS_SERVER:-}"
image_map="${PRODUCT_WORKLOAD_IMAGES_FILE:?PRODUCT_WORKLOAD_IMAGES_FILE is required}"
keycloak_source="${KEYCLOAK_IMAGE:?KEYCLOAK_IMAGE is required}"
postgres_source="${POSTGRES_IMAGE:?POSTGRES_IMAGE is required}"
output="${IDENTITY_LIFECYCLE_OUTPUT:?IDENTITY_LIFECYCLE_OUTPUT is required}"
release="identity"
work_dir="$(mktemp -d)"
identity_database_host="external-postgres.${data_namespace}.svc.cluster.local"
identity_database="keycloak"
identity_username="identity_login"
identity_password="identity_password"
marker="identity-external-retention-${run_id}"

trap 'rm -rf "${work_dir}"' EXIT HUP INT TERM

kube() {
  if command -v kubectl >/dev/null 2>&1; then
    kubectl "$@"
    return
  fi
  k3s kubectl "$@"
}

fail() {
  printf '[identity-external-lifecycle] FAILED: %s\n' "$*" >&2
  exit 1
}

resolve_image() {
  source_image="$1"
  resolved="$(awk -v source="${source_image}" '$1 == source {print $2}' "${image_map}")"
  printf '%s\n' "${resolved}" | \
    grep -Eq '^[a-z0-9]([a-z0-9._:/-]*[a-z0-9])?@sha256:[0-9a-f]{64}$' || \
    fail "immutable image mapping is missing for ${source_image}"
  printf '%s' "${resolved}"
}

split_image() {
  immutable_image="$1"
  image_repository="${immutable_image%@sha256:*}"
  image_digest="sha256:${immutable_image##*@sha256:}"
}

identity_sql() {
  kube exec -n "${data_namespace}" deployment/external-postgres -- \
    env PGPASSWORD="${identity_password}" PGSSLMODE=verify-full \
    PGSSLROOTCERT=/etc/postgres-tls/ca.crt \
    psql -h "${identity_database_host}" -U "${identity_username}" \
    -d "${identity_database}" -v ON_ERROR_STOP=1 "$@"
}

wait_job() {
  job_name="$1"
  if ! kube wait --for=condition=complete "job/${job_name}" \
    -n "${identity_namespace}" --timeout=300s >/dev/null; then
    kube logs "job/${job_name}" -n "${identity_namespace}" \
      --all-containers=true >&2 || true
    fail "Job ${job_name} did not complete"
  fi
}

keycloak_image="$(resolve_image "${keycloak_source}")"
postgres_image="$(resolve_image "${postgres_source}")"
split_image "${keycloak_image}"
keycloak_repository="${image_repository}"
keycloak_digest="${image_digest}"
split_image "${postgres_image}"
postgres_repository="${image_repository}"
postgres_digest="${image_digest}"

postgres_uid="$(
  kube get deployment external-postgres -n "${data_namespace}" \
    -o jsonpath='{.metadata.uid}'
)"

kube exec -n "${data_namespace}" deployment/external-postgres -- \
  env PGPASSWORD=bootstrap_password \
  psql -h 127.0.0.1 -U bootstrap_superuser -d aileron \
  -v ON_ERROR_STOP=1 -c \
  "CREATE ROLE ${identity_username} WITH LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE INHERIT NOREPLICATION NOBYPASSRLS PASSWORD '${identity_password}'" \
  >/dev/null
kube exec -n "${data_namespace}" deployment/external-postgres -- \
  env PGPASSWORD=bootstrap_password \
  createdb -h 127.0.0.1 -U bootstrap_superuser \
  --owner="${identity_username}" "${identity_database}"

cat > "${work_dir}/namespace.yaml" <<EOF
apiVersion: v1
kind: Namespace
metadata:
  name: ${identity_namespace}
  labels:
    aileron.io/product-conformance-run: ${run_id}
EOF
kube apply -f "${work_dir}/namespace.yaml" >/dev/null

if [ "${storage_mode}" = "static-nfs" ]; then
  [ -n "${nfs_server}" ] || fail "NFS_SERVER is required for static-nfs"
  cat > "${work_dir}/backup-pv.yaml" <<EOF
apiVersion: v1
kind: PersistentVolume
metadata:
  name: identity-backup-${run_id}
  labels:
    aileron.io/product-conformance-run: ${run_id}
spec:
  capacity: {storage: 1Gi}
  accessModes: [ReadWriteOnce]
  persistentVolumeReclaimPolicy: Retain
  storageClassName: ${storage_class}
  mountOptions:
    - vers=4.2
    - hard
    - timeo=600
    - retrans=2
  claimRef:
    namespace: ${identity_namespace}
    name: aileron-identity-backup
  nfs:
    server: ${nfs_server}
    path: /manager-state/product/${run_id}/identity-backup
EOF
  kube apply -f "${work_dir}/backup-pv.yaml" >/dev/null
fi

kube get secret external-postgres-tls -n "${data_namespace}" \
  -o jsonpath='{.data.ca\.crt}' | base64 -d > "${work_dir}/ca.crt"
kube create secret generic identity-database-ca -n "${identity_namespace}" \
  --from-file=ca.crt="${work_dir}/ca.crt" --dry-run=client -o yaml \
  > "${work_dir}/identity-database-ca.yaml"
kube apply -f "${work_dir}/identity-database-ca.yaml" >/dev/null

kube create secret generic identity-postgres -n "${identity_namespace}" \
  --from-literal=username="${identity_username}" \
  --from-literal=password="${identity_password}" --dry-run=client -o yaml \
  > "${work_dir}/identity-postgres.yaml"
kube apply -f "${work_dir}/identity-postgres.yaml" >/dev/null
kube create secret generic keycloak-bootstrap-admin -n "${identity_namespace}" \
  --from-literal=username=bootstrap-admin \
  --from-literal=password=bootstrap-password --dry-run=client -o yaml \
  > "${work_dir}/keycloak-bootstrap-admin.yaml"
kube apply -f "${work_dir}/keycloak-bootstrap-admin.yaml" >/dev/null

cat > "${work_dir}/realm.json" <<'EOF'
{
  "realm": "aileron",
  "enabled": true,
  "sslRequired": "none",
  "clients": [
    {
      "clientId": "aileron-manager",
      "secret": "identity-client-secret",
      "enabled": true,
      "publicClient": false,
      "standardFlowEnabled": true,
      "redirectUris": ["https://aileron.example.test/api/v1/oauth2/callback"]
    }
  ],
  "users": [
    {
      "id": "22222222-2222-4222-8222-222222222222",
      "username": "platform-admin",
      "email": "platform-admin@example.test",
      "enabled": true,
      "emailVerified": true
    }
  ]
}
EOF
kube create secret generic keycloak-realm-import -n "${identity_namespace}" \
  --from-file=realm.json="${work_dir}/realm.json" --dry-run=client -o yaml \
  > "${work_dir}/keycloak-realm-import.yaml"
kube apply -f "${work_dir}/keycloak-realm-import.yaml" >/dev/null

cat > "${work_dir}/platform-import.json" <<'EOF'
{"ifResourceExists":"FAIL","users":[]}
EOF
kube create secret generic keycloak-platform-admin -n "${identity_namespace}" \
  --from-literal=subject=22222222-2222-4222-8222-222222222222 \
  --from-literal=username=platform-admin \
  --from-literal=email=platform-admin@example.test \
  --from-literal=password=platform-password \
  --from-file=import.json="${work_dir}/platform-import.json" \
  --dry-run=client -o yaml > "${work_dir}/keycloak-platform-admin.yaml"
kube apply -f "${work_dir}/keycloak-platform-admin.yaml" >/dev/null
kube create secret generic keycloak-break-glass -n "${identity_namespace}" \
  --from-literal=username=break-glass \
  --from-literal=email=break-glass@example.test \
  --from-literal=password=break-glass-password \
  --dry-run=client -o yaml > "${work_dir}/keycloak-break-glass.yaml"
kube apply -f "${work_dir}/keycloak-break-glass.yaml" >/dev/null

cat > "${work_dir}/values.yaml" <<EOF
images:
  keycloak:
    repository: ${keycloak_repository}
    digest: ${keycloak_digest}
    pullPolicy: Never
  postgres:
    repository: ${postgres_repository}
    digest: ${postgres_digest}
    pullPolicy: Never
postgres:
  enabled: false
  database: ${identity_database}
  jdbcUrl: jdbc:postgresql://${identity_database_host}:5432/${identity_database}?sslmode=verify-full
  revision: identity-external-v1
  caSecretName: identity-database-ca
  caSecretKey: ca.crt
networkPolicy:
  externalDatabaseEgress:
    mode: selector
    namespaceLabels:
      kubernetes.io/metadata.name: ${data_namespace}
    podLabels:
      app.kubernetes.io/name: external-postgres
backup:
  enabled: true
  claimName: aileron-identity-backup
  storage:
    size: 1Gi
    storageClassName: ${storage_class}
    accessMode: ReadWriteOnce
    mountRootSupplementalGroup: ${PLATFORM_STORAGE_GID:-2000}
restore:
  enabled: false
EOF

helm upgrade --install "${release}" "${repo_root}/helm/aileron-identity" \
  -n "${identity_namespace}" -f "${work_dir}/values.yaml" \
  --wait --timeout 10m >/dev/null
kube rollout status deployment/aileron-identity-keycloak \
  -n "${identity_namespace}" --timeout=300s >/dev/null
keycloak_pod="$(kube get pod -n "${identity_namespace}" \
  -l app.kubernetes.io/name=aileron-identity-keycloak \
  -o jsonpath='{.items[0].metadata.name}')"
kube exec -n "${identity_namespace}" "${keycloak_pod}" -- \
  env KC_CLI_PASSWORD=bootstrap-password \
  /opt/keycloak/bin/kcadm.sh config credentials \
  --config /tmp/identity-e2e-kcadm.config \
  --server http://127.0.0.1:8080 --realm master --user bootstrap-admin \
  >/dev/null
kube exec -n "${identity_namespace}" "${keycloak_pod}" -- \
  /opt/keycloak/bin/kcadm.sh get realms/aileron \
  --config /tmp/identity-e2e-kcadm.config >/dev/null

identity_sql -Atc \
  "CREATE TABLE public.aileron_identity_retention(marker text PRIMARY KEY); INSERT INTO public.aileron_identity_retention VALUES ('${marker}');" \
  >/dev/null
helm upgrade "${release}" "${repo_root}/helm/aileron-identity" \
  -n "${identity_namespace}" -f "${work_dir}/values.yaml" \
  --set-string postgres.revision=identity-external-v2 \
  --wait --timeout 10m >/dev/null

identity_sql -Atc "DROP TABLE public.aileron_identity_retention" >/dev/null
kube scale deployment/aileron-identity-keycloak -n "${identity_namespace}" \
  --replicas=0 >/dev/null
kube rollout status deployment/aileron-identity-keycloak \
  -n "${identity_namespace}" --timeout=300s >/dev/null

expected_confirmation="${identity_namespace}/${release}/restore/${run_id}"
confirmation="${IDENTITY_DESTRUCTIVE_CONFIRMATION:-}"
[ "${confirmation}" = "${expected_confirmation}" ] || \
  fail "destructive restore confirmation does not match the disposable release"
helm template "${release}" "${repo_root}/helm/aileron-identity" \
  -n "${identity_namespace}" -f "${work_dir}/values.yaml" \
  --set backup.enabled=false --set restore.enabled=true \
  --show-only templates/restore-job.yaml > "${work_dir}/restore-job.yaml"
kube delete job aileron-identity-restore -n "${identity_namespace}" \
  --ignore-not-found --wait=true >/dev/null
kube apply -n "${identity_namespace}" -f "${work_dir}/restore-job.yaml" >/dev/null
wait_job aileron-identity-restore
[ "$(identity_sql -Atc \
  "SELECT count(*) FROM public.aileron_identity_retention WHERE marker='${marker}'")" = "1" ] || \
  fail "Identity restore did not recover the database marker"
kube delete job aileron-identity-restore -n "${identity_namespace}" \
  --ignore-not-found --wait=true >/dev/null

kube scale deployment/aileron-identity-keycloak -n "${identity_namespace}" \
  --replicas=1 >/dev/null
kube rollout status deployment/aileron-identity-keycloak \
  -n "${identity_namespace}" --timeout=300s >/dev/null
keycloak_pod="$(kube get pod -n "${identity_namespace}" \
  -l app.kubernetes.io/name=aileron-identity-keycloak \
  -o jsonpath='{.items[0].metadata.name}')"
kube exec -n "${identity_namespace}" "${keycloak_pod}" -- \
  env KC_CLI_PASSWORD=bootstrap-password \
  /opt/keycloak/bin/kcadm.sh config credentials \
  --config /tmp/identity-e2e-kcadm.config \
  --server http://127.0.0.1:8080 --realm master --user bootstrap-admin \
  >/dev/null

egress_namespace="$(kube get networkpolicy aileron-identity-keycloak \
  -n "${identity_namespace}" \
  -o jsonpath='{.spec.egress[0].to[0].namespaceSelector.matchLabels.kubernetes\.io/metadata\.name}')"
egress_pod="$(kube get networkpolicy aileron-identity-keycloak \
  -n "${identity_namespace}" \
  -o jsonpath='{.spec.egress[0].to[0].podSelector.matchLabels.app\.kubernetes\.io/name}')"
[ "${egress_namespace}" = "${data_namespace}" ] && \
  [ "${egress_pod}" = "external-postgres" ] || \
  fail "Identity external database NetworkPolicy target is incorrect"

helm uninstall "${release}" -n "${identity_namespace}" \
  --wait --timeout 10m >/dev/null
[ "$(identity_sql -Atc \
  "SELECT count(*) FROM public.aileron_identity_retention WHERE marker='${marker}'")" = "1" ] || \
  fail "Identity database was not retained after Helm uninstall"
[ "$(kube get deployment external-postgres -n "${data_namespace}" \
  -o jsonpath='{.metadata.uid}')" = "${postgres_uid}" ] || \
  fail "external PostgreSQL workload changed during Identity lifecycle"

printf 'login\tbackup\tdestructive_restore\trestart\tuninstall_retention\texternal_workload_unchanged\tnetwork_policy_selector\ntrue\ttrue\ttrue\ttrue\ttrue\ttrue\ttrue\n' \
  > "${output}"

kube delete namespace "${identity_namespace}" --wait=true >/dev/null
if [ "${storage_mode}" = "static-nfs" ]; then
  kube delete pv "identity-backup-${run_id}" --ignore-not-found >/dev/null
fi
printf '[identity-external-lifecycle] external Identity lifecycle passed\n'
