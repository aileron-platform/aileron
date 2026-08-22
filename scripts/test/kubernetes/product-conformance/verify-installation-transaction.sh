#!/bin/sh

set -eu

repo_root="${REPO_ROOT:-/repo}"
namespace="${E2E_NAMESPACE:?E2E_NAMESPACE is required}"
run_id="${E2E_RUN_ID:?E2E_RUN_ID is required}"
release="${PRODUCT_HELM_RELEASE:-product}"
mode="${PRODUCT_DATA_SERVICE_MODE:-bundled}"
data_namespace="${PRODUCT_DATA_SERVICE_NAMESPACE:-${namespace}-data}"
output="${PRODUCT_TRANSACTION_OUTPUT:?PRODUCT_TRANSACTION_OUTPUT is required}"
fullname="${release}-aileron"
marker_schema="aileron_e2e_installation_transaction"
marker_key="aileron:e2e:installation-transaction:${run_id}"
platform_password="platform_password"
redis_password="external_redis_password"
work_dir="$(mktemp -d)"

trap 'rm -rf "${work_dir}"' EXIT HUP INT TERM

kube() {
  if command -v kubectl >/dev/null 2>&1; then
    kubectl "$@"
    return
  fi
  k3s kubectl "$@"
}

fail() {
  printf '[product-installation-transaction] FAILED: %s\n' "$*" >&2
  exit 1
}

release_revision() {
  helm history "${release}" -n "${namespace}" -o json | jq -er '.[-1].revision'
}

wait_manager() {
  kube rollout status "deployment/${fullname}-workspace-manager" \
    -n "${namespace}" --timeout=300s >/dev/null
}

release_objects() {
  kube get all,configmap,secret,serviceaccount,role,rolebinding,pvc \
    -n "${namespace}" -l "app.kubernetes.io/instance=${release}" \
    -o name 2>/dev/null || true
}

wait_for_release_objects_absent() {
  attempts=0
  remaining_release_objects="$(release_objects)"
  while [ -n "${remaining_release_objects}" ]; do
    attempts=$((attempts + 1))
    [ "${attempts}" -lt 120 ] || \
      fail "chart-managed release objects remain after uninstall: ${remaining_release_objects}"
    sleep 1
    remaining_release_objects="$(release_objects)"
  done
}

wait_deployment_rollout() {
  deployment="$1"
  generation="$(
    kube get deployment "${deployment}" -n "${data_namespace}" \
      -o jsonpath='{.metadata.generation}'
  )"
  attempts=0
  while [ "$(
    kube get deployment "${deployment}" -n "${data_namespace}" \
      -o jsonpath='{.status.observedGeneration}'
  )" != "${generation}" ]; do
    attempts=$((attempts + 1))
    [ "${attempts}" -lt 150 ] || \
      fail "${deployment} did not observe generation ${generation}"
    sleep 2
  done
  kube rollout status "deployment/${deployment}" -n "${data_namespace}" \
    --timeout=300s >/dev/null
}

platform_sql() {
  kube exec -n "${data_namespace}" deployment/external-postgres -- \
    env PGPASSWORD="${platform_password}" \
    psql -h 127.0.0.1 -U platform_login -d aileron -v ON_ERROR_STOP=1 "$@"
}

external_redis() {
  kube exec -n "${data_namespace}" deployment/external-redis -- \
    redis-cli --tls --cacert /etc/redis-tls/ca.crt \
    --sni "external-redis.${data_namespace}.svc.cluster.local" -h 127.0.0.1 \
    --user default -a "${redis_password}" --no-auth-warning -n 0 "$@"
}

run_transaction_driver() {
  command="$1"
  job_name="product-${command}"
  image_pull_policy="${IMAGE_PULL_POLICY:-Never}"
  image_pull_secrets=""
  if [ -n "${IMAGE_PULL_SECRET_NAME:-}" ]; then
    image_pull_secrets="      imagePullSecrets:
        - name: ${IMAGE_PULL_SECRET_NAME}"
  fi
  nfs_environment=""
  if [ "${E2E_STORAGE_MODE:?E2E_STORAGE_MODE is required}" = "static-nfs" ]; then
    nfs_environment="            - name: NFS_SERVER
              value: ${NFS_SERVER:?NFS_SERVER is required for static-nfs storage}"
  fi
  cat > "${work_dir}/${job_name}.yaml" <<EOF
apiVersion: batch/v1
kind: Job
metadata:
  name: ${job_name}
  namespace: ${namespace}
spec:
  backoffLimit: 0
  template:
    spec:
${image_pull_secrets}
      restartPolicy: Never
      serviceAccountName: product-conformance
      containers:
        - name: driver
          image: ${PRODUCT_DRIVER_IMAGE:?PRODUCT_DRIVER_IMAGE is required}
          imagePullPolicy: ${image_pull_policy}
          args: ["${command}"]
          env:
            - name: E2E_NAMESPACE
              value: ${namespace}
            - name: E2E_RUN_ID
              value: ${run_id}
            - name: PRODUCT_MANAGER_URL
              value: http://${fullname}-workspace-manager:3001
            - name: PRODUCT_PLATFORM_PUBLIC_ORIGIN
              value: https://aileron.example.test
            - name: PRODUCT_OIDC_ADAPTER_URL
              value: https://${fullname}-oidc-fixture:8443
            - name: PRODUCT_OIDC_ISSUER_URL
              value: https://${fullname}-oidc-fixture:8443
            - name: PRODUCT_OIDC_CLIENT_ID
              value: aileron-manager
            - name: SSL_CERT_FILE
              value: /etc/aileron/oidc-ca/ca.crt
            - name: PRODUCT_POSTGRES_DSN
              valueFrom:
                secretKeyRef:
                  name: aileron-platform-secrets
                  key: database-url
            - name: PRODUCT_REPORT_PATH
              value: /tmp/product-report.json
            - name: PRODUCT_HELM_RELEASE
              value: ${release}
            - name: PRODUCT_DRIVER_IMAGE
              value: ${PRODUCT_DRIVER_IMAGE}
            - name: RUNTIME_IMAGE
              value: ${RUNTIME_IMAGE:?RUNTIME_IMAGE is required}
            - name: BROWSER_IMAGE
              value: ${BROWSER_IMAGE:?BROWSER_IMAGE is required}
            - name: CANVAS_IMAGE
              value: ${CANVAS_IMAGE:?CANVAS_IMAGE is required}
            - name: IMAGE_PULL_POLICY
              value: ${image_pull_policy}
            - name: RWX_STORAGE_CLASS
              value: ${RWX_STORAGE_CLASS:?RWX_STORAGE_CLASS is required}
            - name: E2E_STORAGE_MODE
              value: ${E2E_STORAGE_MODE}
${nfs_environment}
            - name: PLATFORM_STORAGE_GID
              value: "${PLATFORM_STORAGE_GID:-2000}"
          volumeMounts:
            - name: oidc-ca
              mountPath: /etc/aileron/oidc-ca
              readOnly: true
            - name: platform-database-ca
              mountPath: /etc/aileron/data-service-ca/platform-database
              readOnly: true
      volumes:
        - name: oidc-ca
          secret:
            secretName: external-oidc-tls
        - name: platform-database-ca
          secret:
            secretName: product-platform-database-ca
EOF
  kube delete job "${job_name}" -n "${namespace}" \
    --ignore-not-found --wait=true >/dev/null
  kube apply -f "${work_dir}/${job_name}.yaml" >/dev/null
  attempts=0
  while [ "$(kube get job "${job_name}" -n "${namespace}" \
    -o jsonpath='{.status.succeeded}' 2>/dev/null || true)" != "1" ]; do
    if [ "$(kube get job "${job_name}" -n "${namespace}" \
      -o jsonpath='{.status.failed}' 2>/dev/null || true)" = "1" ]; then
      kube logs "job/${job_name}" -n "${namespace}" >&2 || true
      fail "${command} Job failed"
    fi
    attempts=$((attempts + 1))
    [ "${attempts}" -lt 600 ] || {
      kube logs "job/${job_name}" -n "${namespace}" >&2 || true
      fail "${command} Job did not finish before the deadline"
    }
    sleep 1
  done
  kube logs "job/${job_name}" -n "${namespace}"
  kube delete job "${job_name}" -n "${namespace}" --wait=true >/dev/null
}

case "${mode}" in
  bundled|external) ;;
  *) fail "PRODUCT_DATA_SERVICE_MODE must be bundled or external" ;;
esac

initial_revision="$(release_revision)"
case "${initial_revision}" in
  ''|*[!0-9]*) fail "initial Helm revision is invalid" ;;
esac

postgres_uid=""
redis_uid=""
if [ "${mode}" = "external" ]; then
  postgres_uid="$(kube get deployment external-postgres -n "${data_namespace}" -o jsonpath='{.metadata.uid}')"
  redis_uid="$(kube get deployment external-redis -n "${data_namespace}" -o jsonpath='{.metadata.uid}')"
  [ -n "${postgres_uid}" ] && [ -n "${redis_uid}" ] || \
    fail "external data-service fixture identities are missing"
  platform_sql -Atc \
    "CREATE SCHEMA IF NOT EXISTS ${marker_schema}; CREATE TABLE IF NOT EXISTS ${marker_schema}.retention(marker text PRIMARY KEY); INSERT INTO ${marker_schema}.retention(marker) VALUES ('${run_id}') ON CONFLICT (marker) DO NOTHING;" \
    >/dev/null
  [ "$(external_redis SET "${marker_key}" retained)" = "OK" ] || \
    fail "external Redis retention marker could not be created"
  run_transaction_driver "prepare-transaction-workspace"
fi

preflight_failure_verified="not-applicable"
workload_unchanged_verified="not-applicable"
retry_verified="not-applicable"
probe_cleanup_verified="not-applicable"
if [ "${mode}" = "external" ]; then
  manager_pod_uid="$(
    kube get pod -n "${namespace}" \
      -l app.kubernetes.io/component=workspace-manager \
      -o jsonpath='{.items[0].metadata.uid}'
  )"
  original_result_url="$(
    kube get secret product-redis-job-result -n "${namespace}" \
      -o jsonpath='{.data.url}' | base64 -d
  )"
  invalid_result_url="$(
    printf '%s' "${original_result_url}" | \
      sed 's/external_redis_password/invalid_preflight_password/'
  )"
  [ "${invalid_result_url}" != "${original_result_url}" ] || \
    fail "external Redis fixture URL did not contain the expected credential"
  invalid_result_url_data="$(printf '%s' "${invalid_result_url}" | base64 | tr -d '\n')"
  original_result_url_data="$(printf '%s' "${original_result_url}" | base64 | tr -d '\n')"
  kube patch secret product-redis-job-result -n "${namespace}" --type merge \
    -p "{\"data\":{\"url\":\"${invalid_result_url_data}\"}}" >/dev/null
  if helm upgrade "${release}" "${repo_root}/helm/aileron" \
    -n "${namespace}" --reuse-values \
    --wait --timeout 3m >/dev/null 2>&1; then
    kube patch secret product-redis-job-result -n "${namespace}" --type merge \
      -p "{\"data\":{\"url\":\"${original_result_url_data}\"}}" >/dev/null
    fail "Helm upgrade unexpectedly passed with an invalid external Redis credential"
  fi
  preflight_failure_verified="true"
  kube patch secret product-redis-job-result -n "${namespace}" --type merge \
    -p "{\"data\":{\"url\":\"${original_result_url_data}\"}}" >/dev/null
  current_manager_pod_uid="$(
    kube get pod -n "${namespace}" \
      -l app.kubernetes.io/component=workspace-manager \
      -o jsonpath='{.items[0].metadata.uid}'
  )"
  [ "${current_manager_pod_uid}" = "${manager_pod_uid}" ] || \
    fail "Manager Pod changed during a failed data-service preflight"
  [ "$(kube get deployment "${fullname}-workspace-manager" -n "${namespace}" \
    -o jsonpath='{.status.availableReplicas}')" = "1" ] || \
    fail "Manager stopped being available after a failed data-service preflight"
  workload_unchanged_verified="true"
  probe_role_count="$(platform_sql -Atc \
    "SELECT count(*) FROM pg_roles WHERE rolname LIKE 'aileron_pf_%'")"
  probe_schema_count="$(platform_sql -Atc \
    "SELECT count(*) FROM pg_namespace WHERE nspname LIKE 'aileron_pf_%'")"
  [ "${probe_role_count}" = "0" ] && [ "${probe_schema_count}" = "0" ] || \
    fail "failed preflight left PostgreSQL probe roles or schemas"
  probe_cleanup_verified="true"
fi

helm upgrade "${release}" "${repo_root}/helm/aileron" \
  -n "${namespace}" --reuse-values \
  --wait --timeout 10m >/dev/null
upgrade_revision="$(release_revision)"
[ "${upgrade_revision}" -gt "${initial_revision}" ] || \
  fail "Helm retry did not create a newer release revision"
wait_manager
if [ "${mode}" = "external" ]; then
  retry_verified="true"
fi

credential_ca_rotation_verified="not-applicable"
manager_recreated_verified="not-applicable"
runtime_recycled_verified="not-applicable"
if [ "${mode}" = "external" ]; then
  manager_uid_before_rotation="$(
    kube get pod -n "${namespace}" \
      -l app.kubernetes.io/component=workspace-manager \
      -o jsonpath='{.items[0].metadata.uid}'
  )"
  runtime_deployment="$(
    kube get deployment -n "${namespace}" \
      -l aileron.io/component=workspace-runtime \
      -o jsonpath='{.items[0].metadata.name}'
  )"
  [ -n "${runtime_deployment}" ] || \
    fail "a Runtime Deployment is required for CA rotation evidence"
  workspace_cr="workspace-${runtime_deployment#workspace-runtime-}"
  runtime_uid_before_rotation="$(
    kube get pods -n "${namespace}" -o json | jq -er \
      --arg prefix "${runtime_deployment}-" \
      '[.items[] | select(.metadata.name | startswith($prefix))] |
       sort_by(.metadata.creationTimestamp) | last | .metadata.uid'
  )"

  tls_dir="${work_dir}/rotated-tls"
  mkdir -p "${tls_dir}"
  openssl req -config /dev/null -x509 -newkey rsa:2048 -nodes \
    -days 1 -sha256 -subj "/CN=aileron-e2e-rotated-ca" \
    -addext "basicConstraints=critical,CA:TRUE" \
    -addext "keyUsage=critical,keyCertSign,cRLSign" \
    -keyout "${tls_dir}/ca.key" -out "${tls_dir}/ca.crt" >/dev/null 2>&1
  for service in postgres redis; do
    if [ "${service}" = "postgres" ]; then
      service_name=external-postgres
    else
      service_name=external-redis
    fi
    service_host="${service_name}.${data_namespace}.svc.cluster.local"
    openssl req -config /dev/null -newkey rsa:2048 -nodes \
      -subj "/CN=${service_name}" \
      -keyout "${tls_dir}/${service}.key" \
      -out "${tls_dir}/${service}.csr" >/dev/null 2>&1
    printf '%s\n' \
      "subjectAltName=DNS:${service_host}" \
      "basicConstraints=critical,CA:FALSE" \
      "keyUsage=critical,digitalSignature,keyEncipherment" \
      "extendedKeyUsage=serverAuth" > "${tls_dir}/${service}.ext"
    openssl x509 -req -days 1 -sha256 \
      -in "${tls_dir}/${service}.csr" \
      -CA "${tls_dir}/ca.crt" -CAkey "${tls_dir}/ca.key" \
      -CAcreateserial -extfile "${tls_dir}/${service}.ext" \
      -out "${tls_dir}/${service}.crt" >/dev/null 2>&1
  done

  kube create secret generic external-postgres-tls -n "${data_namespace}" \
    --from-file=ca.crt="${tls_dir}/ca.crt" \
    --from-file=tls.crt="${tls_dir}/postgres.crt" \
    --from-file=tls.key="${tls_dir}/postgres.key" \
    --dry-run=client -o yaml > "${work_dir}/external-postgres-tls.yaml"
  kube apply -f "${work_dir}/external-postgres-tls.yaml" >/dev/null
  kube create secret generic external-redis-tls -n "${data_namespace}" \
    --from-file=ca.crt="${tls_dir}/ca.crt" \
    --from-file=tls.crt="${tls_dir}/redis.crt" \
    --from-file=tls.key="${tls_dir}/redis.key" \
    --dry-run=client -o yaml > "${work_dir}/external-redis-tls.yaml"
  kube apply -f "${work_dir}/external-redis-tls.yaml" >/dev/null

  platform_password_rotated="platform_password_rotated"
  redis_password_rotated="external_redis_password_rotated"
  kube exec -n "${data_namespace}" deployment/external-postgres -- \
    env PGPASSWORD=bootstrap_password \
    psql -h 127.0.0.1 -U bootstrap_superuser -d aileron \
    -v ON_ERROR_STOP=1 -c \
    "ALTER ROLE platform_login PASSWORD '${platform_password_rotated}'" >/dev/null
  kube patch deployment external-redis -n "${data_namespace}" --type=json \
    -p "[{\"op\":\"replace\",\"path\":\"/spec/template/spec/containers/0/args/13\",\"value\":\"${redis_password_rotated}\"},{\"op\":\"replace\",\"path\":\"/spec/template/spec/containers/0/readinessProbe/exec/command/9\",\"value\":\"${redis_password_rotated}\"}]" \
    >/dev/null
  kube rollout restart deployment/external-postgres -n "${data_namespace}" >/dev/null
  wait_deployment_rollout external-postgres
  wait_deployment_rollout external-redis

  platform_password="${platform_password_rotated}"
  redis_password="${redis_password_rotated}"
  database_url="$(kube get secret aileron-platform-secrets -n "${namespace}" \
    -o jsonpath='{.data.database-url}' | base64 -d | \
    sed 's/:platform_password@/:platform_password_rotated@/')"
  database_url_data="$(printf '%s' "${database_url}" | base64 | tr -d '\n')"
  kube patch secret aileron-platform-secrets -n "${namespace}" --type merge \
    -p "{\"data\":{\"database-url\":\"${database_url_data}\"}}" >/dev/null
  for redis_secret in product-redis-general product-redis-job-queue product-redis-job-result; do
    redis_url="$(kube get secret "${redis_secret}" -n "${namespace}" \
      -o jsonpath='{.data.url}' | base64 -d | \
      sed 's/external_redis_password/external_redis_password_rotated/')"
    redis_url_data="$(printf '%s' "${redis_url}" | base64 | tr -d '\n')"
    kube patch secret "${redis_secret}" -n "${namespace}" --type merge \
      -p "{\"data\":{\"url\":\"${redis_url_data}\"}}" >/dev/null
  done
  ca_data="$(base64 < "${tls_dir}/ca.crt" | tr -d '\n')"
  for ca_secret in product-platform-database-ca product-redis-general-ca product-redis-job-queue-ca product-redis-job-result-ca; do
    kube patch secret "${ca_secret}" -n "${namespace}" --type merge \
      -p "{\"data\":{\"ca.crt\":\"${ca_data}\"}}" >/dev/null
  done

  helm upgrade "${release}" "${repo_root}/helm/aileron" \
    -n "${namespace}" --reuse-values \
    --set-string platformDatabase.revision=product-platform-database-v2 \
    --set-string redis.connections.general.revision=product-redis-general-v2 \
    --set-string redis.connections.jobQueue.revision=product-redis-job-queue-v2 \
    --set-string redis.connections.jobResult.revision=product-redis-job-result-v2 \
    --wait --timeout 10m >/dev/null
  wait_manager
  manager_uid_after_rotation="$(
    kube get pod -n "${namespace}" \
      -l app.kubernetes.io/component=workspace-manager \
      -o jsonpath='{.items[0].metadata.uid}'
  )"
  [ "${manager_uid_after_rotation}" != "${manager_uid_before_rotation}" ] || \
    fail "Manager Pod was not recreated after data-service rotation"
  manager_recreated_verified="true"
  [ "$(platform_sql -Atc 'SELECT 1')" = "1" ] || \
    fail "Manager PostgreSQL credential and CA rotation did not reconnect"
  [ "$(external_redis PING)" = "PONG" ] || \
    fail "Redis credential and CA rotation did not reconnect"
  credential_ca_rotation_verified="true"

  kube patch workspace "${workspace_cr}" -n "${namespace}" --type merge \
    -p "{\"spec\":{\"runtime\":{\"databaseTrust\":{\"secretName\":\"product-platform-database-ca\",\"secretKey\":\"ca.crt\",\"revision\":\"product-platform-database-v2\"}}}}" \
    >/dev/null
  runtime_uid_after_rotation=""
  attempts=0
  while [ -z "${runtime_uid_after_rotation}" ]; do
    runtime_uid_after_rotation="$(
      kube get pods -n "${namespace}" -o json | jq -r \
        --arg prefix "${runtime_deployment}-" \
        --arg previous "${runtime_uid_before_rotation}" \
        '[.items[] |
          select(.metadata.name | startswith($prefix)) |
          select(.metadata.uid != $previous) |
          select(any(.status.conditions[]?; .type == "Ready" and .status == "True"))] |
         sort_by(.metadata.creationTimestamp) | last | .metadata.uid // empty'
    )"
    if [ -z "${runtime_uid_after_rotation}" ]; then
      attempts=$((attempts + 1))
      [ "${attempts}" -lt 150 ] || \
        fail "Runtime Pod was not recycled after database CA revision changed"
      sleep 2
    fi
  done
  runtime_recycled_verified="true"
  run_transaction_driver "cleanup-transaction-workspace"
fi

helm rollback "${release}" "${initial_revision}" -n "${namespace}" \
  --wait --timeout 10m >/dev/null
rollback_revision="$(release_revision)"
[ "${rollback_revision}" -gt "${upgrade_revision}" ] || \
  fail "Helm rollback did not create a newer release revision"
wait_manager

helm uninstall "${release}" -n "${namespace}" --wait --timeout 10m >/dev/null
if helm status "${release}" -n "${namespace}" >/dev/null 2>&1; then
  fail "Helm release still exists after uninstall"
fi
wait_for_release_objects_absent

retention_verified="not-applicable"
cleanup_verified="not-applicable"
if [ "${mode}" = "external" ]; then
  [ "$(kube get deployment external-postgres -n "${data_namespace}" -o jsonpath='{.metadata.uid}')" = "${postgres_uid}" ] || \
    fail "external PostgreSQL workload changed during Helm transaction"
  [ "$(kube get deployment external-redis -n "${data_namespace}" -o jsonpath='{.metadata.uid}')" = "${redis_uid}" ] || \
    fail "external Redis workload changed during Helm transaction"
  [ "$(platform_sql -Atc "SELECT count(*) FROM ${marker_schema}.retention WHERE marker = '${run_id}'")" = "1" ] || \
    fail "external PostgreSQL marker was not retained after uninstall"
  [ "$(external_redis GET "${marker_key}")" = "retained" ] || \
    fail "external Redis marker was not retained after uninstall"
  retention_verified="true"

  platform_sql -Atc "DROP SCHEMA ${marker_schema} CASCADE" >/dev/null
  [ "$(external_redis DEL "${marker_key}")" = "1" ] || \
    fail "external Redis marker cleanup failed"
  [ "$(platform_sql -Atc "SELECT to_regnamespace('${marker_schema}') IS NULL")" = "t" ] || \
    fail "external PostgreSQL marker cleanup left residue"
  [ "$(external_redis EXISTS "${marker_key}")" = "0" ] || \
    fail "external Redis marker cleanup left residue"
  cleanup_verified="true"
fi

printf 'mode\tinitial_revision\tupgrade_revision\trollback_revision\tuninstalled\texternal_retention\tmarker_cleanup\tpreflight_failed\tworkload_unchanged\tretry_passed\tprobe_cleanup\tcredential_ca_rotation\tmanager_recreated\truntime_recycled\n%s\t%s\t%s\t%s\ttrue\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
  "${mode}" "${initial_revision}" "${upgrade_revision}" "${rollback_revision}" \
  "${retention_verified}" "${cleanup_verified}" \
  "${preflight_failure_verified}" "${workload_unchanged_verified}" \
  "${retry_verified}" "${probe_cleanup_verified}" \
  "${credential_ca_rotation_verified}" "${manager_recreated_verified}" \
  "${runtime_recycled_verified}" > "${output}"

printf '[product-installation-transaction] install, upgrade, rollback, and uninstall passed in %s mode\n' "${mode}"
