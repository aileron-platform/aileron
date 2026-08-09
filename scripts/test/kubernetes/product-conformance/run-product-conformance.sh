#!/bin/sh

set -eu

namespace="${E2E_NAMESPACE:?E2E_NAMESPACE is required}"
run_id="${E2E_RUN_ID:?E2E_RUN_ID is required}"
release="${PRODUCT_HELM_RELEASE:-product}"
driver_image="${PRODUCT_DRIVER_IMAGE:?PRODUCT_DRIVER_IMAGE is required}"
output="${PRODUCT_CAPABILITIES_OUTPUT:?PRODUCT_CAPABILITIES_OUTPUT is required}"
image_pull_policy="${IMAGE_PULL_POLICY:-Never}"
image_pull_secret_name="${IMAGE_PULL_SECRET_NAME:-}"
storage_mode="${E2E_STORAGE_MODE:?E2E_STORAGE_MODE is required}"
service_account="product-conformance"
fullname="${release}-aileron"
job_name="product-conformance"
work_dir="$(mktemp -d)"

trap 'rm -rf "${work_dir}"' EXIT HUP INT TERM
rm -f "${output}"

kube() {
  if command -v kubectl >/dev/null 2>&1; then
    kubectl "$@"
    return
  fi
  k3s kubectl "$@"
}

case "${storage_mode}" in
  static-nfs)
    nfs_server="${NFS_SERVER:?NFS_SERVER is required for static-nfs storage}"
    nfs_env="            - name: NFS_SERVER
              value: ${nfs_server}"
    ;;
  dynamic)
    nfs_env=""
    ;;
  *)
    printf 'E2E_STORAGE_MODE must be static-nfs or dynamic\n' >&2
    exit 1
    ;;
esac

if [ -n "${image_pull_secret_name}" ]; then
  case "${image_pull_secret_name}" in
    *[!a-z0-9.-]*|.*|*.)
      printf 'IMAGE_PULL_SECRET_NAME must be a DNS subdomain\n' >&2
      exit 1
      ;;
  esac
fi

job_image_pull_secrets_block=""
image_pull_secret_env=""
if [ -n "${image_pull_secret_name}" ]; then
  job_image_pull_secrets_block="      imagePullSecrets:
        - name: ${image_pull_secret_name}"
  image_pull_secret_env="            - name: IMAGE_PULL_SECRET_NAME
              value: ${image_pull_secret_name}"
fi

cat > "${work_dir}/driver-job.yaml" <<EOF
apiVersion: batch/v1
kind: Job
metadata:
  name: ${job_name}
  namespace: ${namespace}
spec:
  backoffLimit: 0
  template:
    spec:
${job_image_pull_secrets_block}
      restartPolicy: Never
      serviceAccountName: ${service_account}
      containers:
        - name: driver
          image: ${driver_image}
          imagePullPolicy: ${image_pull_policy}
          args: ["run"]
          env:
            - name: E2E_NAMESPACE
              value: ${namespace}
            - name: E2E_RUN_ID
              value: ${run_id}
            - name: PRODUCT_MANAGER_URL
              value: http://${fullname}-workspace-manager:3001
            - name: PRODUCT_OIDC_ADAPTER_URL
              value: https://${fullname}-oidc-fixture:8443
            - name: PRODUCT_OIDC_ISSUER_URL
              value: https://${fullname}-oidc-fixture:8443
            - name: PRODUCT_OIDC_CLIENT_ID
              value: aileron-manager
            - name: SSL_CERT_FILE
              value: /etc/aileron/oidc-ca/ca.crt
            - name: PRODUCT_POSTGRES_DSN
              value: postgresql://postgres:postgres@${fullname}-postgres:5432/aileron
            - name: PRODUCT_REPORT_PATH
              value: /evidence/product-report.json
            - name: PRODUCT_HELM_RELEASE
              value: ${release}
            - name: PRODUCT_DRIVER_IMAGE
              value: ${driver_image}
            - name: RUNTIME_IMAGE
              value: ${RUNTIME_IMAGE:?RUNTIME_IMAGE is required}
            - name: BROWSER_IMAGE
              value: ${BROWSER_IMAGE:?BROWSER_IMAGE is required}
            - name: CANVAS_IMAGE
              value: ${CANVAS_IMAGE:?CANVAS_IMAGE is required}
            - name: IMAGE_PULL_POLICY
              value: ${image_pull_policy}
${image_pull_secret_env}
            - name: RWX_STORAGE_CLASS
              value: ${RWX_STORAGE_CLASS:?RWX_STORAGE_CLASS is required}
            - name: E2E_STORAGE_MODE
              value: ${storage_mode}
${nfs_env}
            - name: PLATFORM_STORAGE_GID
              value: "${PLATFORM_STORAGE_GID:-2000}"
          volumeMounts:
            - name: evidence
              mountPath: /evidence
            - name: oidc-ca
              mountPath: /etc/aileron/oidc-ca
              readOnly: true
      volumes:
        - name: evidence
          emptyDir: {}
        - name: oidc-ca
          secret:
            secretName: external-oidc-tls
EOF

kube delete job "${job_name}" -n "${namespace}" --ignore-not-found --wait=true >/dev/null
kube apply -f "${work_dir}/driver-job.yaml" >/dev/null

timeout_seconds="${PRODUCT_CONFORMANCE_TIMEOUT_SECONDS:-1800}"
case "${timeout_seconds}" in
  ''|*[!0-9]*)
    printf 'PRODUCT_CONFORMANCE_TIMEOUT_SECONDS must be a positive integer\n' >&2
    exit 1
    ;;
esac
[ "${timeout_seconds}" -gt 0 ] || {
  printf 'PRODUCT_CONFORMANCE_TIMEOUT_SECONDS must be a positive integer\n' >&2
  exit 1
}
attempts="${timeout_seconds}"
succeeded=""
failed=""
while [ "${attempts}" -gt 0 ]; do
  succeeded="$(kube get job "${job_name}" -n "${namespace}" -o jsonpath='{.status.succeeded}' 2>/dev/null || true)"
  failed="$(kube get job "${job_name}" -n "${namespace}" -o jsonpath='{.status.failed}' 2>/dev/null || true)"
  [ "${succeeded}" = "1" ] && break
  [ "${failed}" = "1" ] && break
  attempts=$((attempts - 1))
  sleep 1
done
if [ "${succeeded}" != "1" ]; then
  kube logs job/${job_name} -n "${namespace}" >&2 || true
  if [ "${failed}" = "1" ]; then
    printf 'product conformance Job failed\n' >&2
  else
    printf 'product conformance Job did not succeed before the deadline\n' >&2
  fi
  exit 1
fi

kube logs job/${job_name} -n "${namespace}" | tee "${work_dir}/driver.log"
result_line="$(grep '^PRODUCT_CONFORMANCE_RESULT=' "${work_dir}/driver.log" | tail -n 1 || true)"
[ -n "${result_line}" ] || {
  printf 'product driver did not emit a conformance report\n' >&2
  exit 1
}
printf '%s\n' "${result_line#PRODUCT_CONFORMANCE_RESULT=}" | jq . > "${output}"

"$(dirname "$0")/validate-product-report.sh" "${output}"
