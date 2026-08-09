#!/bin/sh

set -eu

platform="${AILERON_CONFORMANCE_PLATFORM:?AILERON_CONFORMANCE_PLATFORM is required}"
expected_context="${EXPECTED_KUBE_CONTEXT:?EXPECTED_KUBE_CONTEXT is required}"
artifact_root="${ARTIFACT_DIR:?ARTIFACT_DIR is required}"
storage_class="${RWX_STORAGE_CLASS:?RWX_STORAGE_CLASS is required}"
rwo_storage_class="${RWO_STORAGE_CLASS:?RWO_STORAGE_CLASS is required}"
runtime_home_storage_class="${RUNTIME_HOME_STORAGE_CLASS:-${rwo_storage_class}}"
runtime_home_access_mode="${RUNTIME_HOME_STORAGE_ACCESS_MODE:-ReadWriteOnce}"
shared_storage_size="${E2E_SHARED_STORAGE_SIZE:-1Gi}"
rwo_storage_size="${E2E_RWO_STORAGE_SIZE:-1Gi}"
runtime_home_storage_size="${E2E_RUNTIME_HOME_STORAGE_SIZE:-2Gi}"
operator_image="${OPERATOR_IMAGE:?OPERATOR_IMAGE is required}"
manager_image="${MANAGER_IMAGE:?MANAGER_IMAGE is required}"
workload_probe_image="${WORKLOAD_PROBE_IMAGE:?WORKLOAD_PROBE_IMAGE is required}"
runtime_image="${RUNTIME_IMAGE:?RUNTIME_IMAGE is required}"
browser_image="${BROWSER_IMAGE:?BROWSER_IMAGE is required}"
canvas_image="${CANVAS_IMAGE:?CANVAS_IMAGE is required}"
product_driver_image="${PRODUCT_DRIVER_IMAGE:?PRODUCT_DRIVER_IMAGE is required}"
redis_image="${REDIS_IMAGE:?REDIS_IMAGE is required}"
postgres_image="${POSTGRES_IMAGE:?POSTGRES_IMAGE is required}"
image_pull_secret_source_namespace="${IMAGE_PULL_SECRET_SOURCE_NAMESPACE:-}"
image_pull_secret_source_name="${IMAGE_PULL_SECRET_SOURCE_NAME:-}"
image_pull_secret_name="${IMAGE_PULL_SECRET_NAME:-${image_pull_secret_source_name}}"
product_hook="${PRODUCT_CONFORMANCE_HOOK:-}"
root_squash_mode="${ROOT_SQUASH_MODE:?ROOT_SQUASH_MODE is required}"
run_id="${E2E_RUN_ID:-${platform}-$(date -u +%Y%m%d%H%M%S)-$$}"
target_namespace="${E2E_NAMESPACE:-aileron-kubernetes-e2e-${run_id}}"
artifact_dir="${artifact_root}/${run_id}"
runner_result="failed"

log() {
  printf '[kubernetes-platform-conformance] %s\n' "$*"
}

fail() {
  log "FAILED: $*" >&2
  exit 1
}

require_permission() {
  verb="$1"
  resource="$2"
  kubectl auth can-i "${verb}" "${resource}" | grep -qx yes || \
    fail "current identity cannot ${verb} ${resource}"
}

require_namespaced_permission() {
  verb="$1"
  resource="$2"
  permission_namespace="$3"
  kubectl auth can-i "${verb}" "${resource}" \
    --namespace "${permission_namespace}" | grep -qx yes || \
    fail "current identity cannot ${verb} ${resource} in ${permission_namespace}"
}

require_immutable_image() {
  image="$1"
  repository="${image%@sha256:*}"
  digest="${image##*@sha256:}"
  [ -n "${repository}" ] || fail "conformance image repository is empty: ${image}"
  [ "${image}" = "${repository}@sha256:${digest}" ] || \
    fail "conformance image must use an immutable sha256 digest: ${image}"
  case "${repository}" in
    *@*|*[!A-Za-z0-9._:/-]*) \
      fail "conformance image repository is invalid: ${image}" ;;
  esac
  [ "${#digest}" -eq 64 ] || \
    fail "conformance image digest must contain 64 hexadecimal characters: ${image}"
  case "${digest}" in
    *[!0-9a-f]*) fail "conformance image digest is invalid: ${image}" ;;
  esac
}

schedulable_ready_node_count() {
  kubectl get nodes --no-headers | awk '$2 == "Ready" {print $1}' | \
    while IFS= read -r candidate; do
      [ -n "${candidate}" ] || continue
      unschedulable="$(kubectl get node "${candidate}" -o jsonpath='{.spec.unschedulable}')"
      [ "${unschedulable}" != "true" ] || continue
      if kubectl get node "${candidate}" \
        -o jsonpath='{range .spec.taints[*]}{.effect}{"\n"}{end}' | \
        grep -Eq '^(NoSchedule|NoExecute)$'; then
        continue
      fi
      printf '%s\n' "${candidate}"
    done | awk 'NF {count++} END {print count + 0}'
}

write_failed_capabilities() {
  cat > "${artifact_dir}/capabilities.json" <<EOF
{
  "result": "failed",
  "managerApiLifecycle": false,
  "durableJobs": false,
  "rapidConsecutiveMutations": false,
  "reconcileFailureRetry": false,
  "startStopRestart": false,
  "errorRecovery": false,
  "stoppedWorkspace": false,
  "actionGate": false,
  "signedDrain": false,
  "forcedTerminationProof": false,
  "oldConnectionRejection": false,
  "browserPairing": false,
  "releaseConformanceVerified": false
}
EOF
}

finish() {
  exit_code=$?
  trap - EXIT HUP INT TERM
  mkdir -p "${artifact_dir}"
  if [ ! -s "${artifact_dir}/capabilities.json" ]; then
    write_failed_capabilities
  fi
  printf '%s\n' "${runner_result}" > "${artifact_dir}/platform-runner-result.txt"
  exit "${exit_code}"
}

case "${platform}" in
  eks|gke|aks|ocp|rke2|native-kubernetes) ;;
  *) fail "unsupported platform: ${platform}" ;;
esac
case "${run_id}" in
  ''|*[!a-z0-9-]*) fail "E2E_RUN_ID must contain only lowercase letters, digits, and hyphens" ;;
esac
trap finish EXIT HUP INT TERM
mkdir -p "${artifact_dir}"
write_failed_capabilities

[ -x "${product_hook}" ] || fail "PRODUCT_CONFORMANCE_HOOK is not executable: ${product_hook}"
[ -n "${KUBECONFIG:-}" ] || fail "KUBECONFIG is required"
[ -r "${KUBECONFIG}" ] || fail "KUBECONFIG is not readable: ${KUBECONFIG}"
command -v kubectl >/dev/null 2>&1 || fail "kubectl is required"
command -v jq >/dev/null 2>&1 || fail "jq is required"

if [ -n "${image_pull_secret_source_namespace}" ] || \
  [ -n "${image_pull_secret_source_name}" ] || \
  [ -n "${image_pull_secret_name}" ]; then
  [ -n "${image_pull_secret_source_namespace}" ] || \
    fail "IMAGE_PULL_SECRET_SOURCE_NAMESPACE is required when a pull secret is configured"
  [ -n "${image_pull_secret_source_name}" ] || \
    fail "IMAGE_PULL_SECRET_SOURCE_NAME is required when a pull secret is configured"
  [ -n "${image_pull_secret_name}" ] || \
    fail "IMAGE_PULL_SECRET_NAME is required when a pull secret is configured"
  case "${image_pull_secret_name}" in
    *[!a-z0-9.-]*|.*|*.) fail "IMAGE_PULL_SECRET_NAME must be a DNS subdomain" ;;
  esac
fi

for image in \
  "${operator_image}" \
  "${manager_image}" \
  "${workload_probe_image}" \
  "${runtime_image}" \
  "${browser_image}" \
  "${canvas_image}" \
  "${product_driver_image}" \
  "${redis_image}" \
  "${postgres_image}"; do
  require_immutable_image "${image}"
done

case "${root_squash_mode}" in
  pod) ;;
  evidence)
    root_squash_evidence="${ROOT_SQUASH_EVIDENCE_FILE:?ROOT_SQUASH_EVIDENCE_FILE is required}"
    [ -s "${root_squash_evidence}" ] || fail "root-squash evidence is empty"
    grep -Eq '"rootSquash"[[:space:]]*:[[:space:]]*true([[:space:]]*[,}]|[[:space:]]*$)' \
      "${root_squash_evidence}" || \
      fail "root-squash evidence does not certify rootSquash=true"
    ;;
  *) fail "ROOT_SQUASH_MODE must be pod or evidence" ;;
esac

current_context="$(kubectl config current-context)"
[ "${current_context}" = "${expected_context}" ] || \
  fail "current context '${current_context}' does not match EXPECTED_KUBE_CONTEXT"

kubectl get --raw=/readyz >/dev/null 2>&1 || fail "Kubernetes API is not Ready"
kubectl get storageclass "${storage_class}" >/dev/null 2>&1 || \
  fail "RWX storage class does not exist: ${storage_class}"
kubectl get storageclass "${rwo_storage_class}" >/dev/null 2>&1 || \
  fail "RWO storage class does not exist: ${rwo_storage_class}"
kubectl get storageclass "${runtime_home_storage_class}" >/dev/null 2>&1 || \
  fail "Runtime HOME storage class does not exist: ${runtime_home_storage_class}"
case "${runtime_home_access_mode}" in
  ReadWriteOnce|ReadWriteMany) ;;
  *) fail "RUNTIME_HOME_STORAGE_ACCESS_MODE must be ReadWriteOnce or ReadWriteMany" ;;
esac
for disposable_storage_class in \
  "${storage_class}" \
  "${rwo_storage_class}" \
  "${runtime_home_storage_class}"; do
  reclaim_policy="$(kubectl get storageclass "${disposable_storage_class}" \
    -o jsonpath='{.reclaimPolicy}')"
  [ "${reclaim_policy}" = "Delete" ] || \
    fail "conformance StorageClass must use reclaimPolicy=Delete: ${disposable_storage_class}"
done
ready_nodes="$(schedulable_ready_node_count)"
[ "${ready_nodes}" -ge 2 ] || fail "at least two Ready nodes are required"

require_permission create namespaces
require_permission get customresourcedefinitions.apiextensions.k8s.io
if ! kubectl get crd workspaces.platform.aileron.io >/dev/null 2>&1; then
  require_permission create customresourcedefinitions.apiextensions.k8s.io
  require_permission delete customresourcedefinitions.apiextensions.k8s.io
fi
require_permission create persistentvolumeclaims
if [ -n "${image_pull_secret_name}" ]; then
  require_namespaced_permission get secrets "${image_pull_secret_source_namespace}"
  require_namespaced_permission create secrets "${target_namespace}"
  require_namespaced_permission create serviceaccounts "${target_namespace}"
  require_namespaced_permission patch serviceaccounts "${target_namespace}"
  kubectl get secret "${image_pull_secret_source_name}" \
    --namespace "${image_pull_secret_source_namespace}" -o json | \
    jq -e '
      .type == "kubernetes.io/dockerconfigjson"
      and (.data[".dockerconfigjson"] | type == "string" and length > 0)
    ' >/dev/null || fail "image pull secret is not a non-empty dockerconfigjson Secret"
fi

storage_gid="${PLATFORM_STORAGE_GID:-}"
expected_scc=""
if [ "${platform}" = "ocp" ]; then
  expected_scc="restricted-v2"
  storage_gid="AUTO"
  [ "${root_squash_mode}" = "evidence" ] || \
    fail "OCP requires backend root-squash evidence because restricted-v2 rejects a UID 0 probe"
else
  [ -n "${storage_gid}" ] || fail "PLATFORM_STORAGE_GID is required for ${platform}"
fi

{
  printf 'platform=%s\n' "${platform}"
  printf 'context=%s\n' "${current_context}"
  printf 'rwx_storage_class=%s\n' "${storage_class}"
  printf 'rwo_storage_class=%s\n' "${rwo_storage_class}"
  printf 'runtime_home_storage_class=%s\n' "${runtime_home_storage_class}"
  printf 'runtime_home_access_mode=%s\n' "${runtime_home_access_mode}"
  printf 'shared_storage_size=%s\n' "${shared_storage_size}"
  printf 'rwo_storage_size=%s\n' "${rwo_storage_size}"
  printf 'runtime_home_storage_size=%s\n' "${runtime_home_storage_size}"
  printf 'image_reference_policy=immutable-digest-only\n'
  printf 'operator_image=%s\n' "${operator_image}"
  printf 'manager_image=%s\n' "${manager_image}"
  printf 'workload_probe_image=%s\n' "${workload_probe_image}"
  printf 'runtime_image=%s\n' "${runtime_image}"
  printf 'browser_image=%s\n' "${browser_image}"
  printf 'canvas_image=%s\n' "${canvas_image}"
  printf 'product_driver_image=%s\n' "${product_driver_image}"
  printf 'redis_image=%s\n' "${redis_image}"
  printf 'postgres_image=%s\n' "${postgres_image}"
  if [ -n "${image_pull_secret_name}" ]; then
    printf 'image_pull_secret_source=%s/%s\n' \
      "${image_pull_secret_source_namespace}" "${image_pull_secret_source_name}"
    printf 'image_pull_secret_target_name=%s\n' "${image_pull_secret_name}"
  else
    printf 'image_pull_secret_source=none\n'
    printf 'image_pull_secret_target_name=none\n'
  fi
} > "${artifact_dir}/platform-inputs.txt"
kubectl cluster-info > "${artifact_dir}/cluster-info.txt" 2>&1
kubectl get nodes -o yaml > "${artifact_dir}/nodes-preflight.yaml"
kubectl get storageclass "${storage_class}" -o yaml \
  > "${artifact_dir}/rwx-storage-class-preflight.yaml"
kubectl get storageclass "${rwo_storage_class}" -o yaml \
  > "${artifact_dir}/rwo-storage-class-preflight.yaml"
kubectl get storageclass "${runtime_home_storage_class}" -o yaml \
  > "${artifact_dir}/runtime-home-storage-class-preflight.yaml"
kubectl get csidriver -o yaml > "${artifact_dir}/csi-drivers-preflight.yaml" 2>&1 || true

export E2E_MODE=platform
export E2E_STORAGE_MODE=dynamic
export E2E_RUN_ID="${run_id}"
export EXPECTED_SCC="${expected_scc}"
export IMAGE_PULL_POLICY="${IMAGE_PULL_POLICY:-Always}"
export IMAGE_PULL_SECRET_NAME="${image_pull_secret_name}"
export IMAGE_PULL_SECRET_SOURCE_NAME="${image_pull_secret_source_name}"
export IMAGE_PULL_SECRET_SOURCE_NAMESPACE="${image_pull_secret_source_namespace}"
export PLATFORM_STORAGE_GID="${storage_gid}"
export REQUIRE_PRODUCT_LIFECYCLE=true
export ROOT_SQUASH_MODE="${root_squash_mode}"
export RWX_STORAGE_CLASS="${storage_class}"
export RWO_STORAGE_CLASS="${rwo_storage_class}"
export RUNTIME_HOME_STORAGE_CLASS="${runtime_home_storage_class}"
export RUNTIME_HOME_STORAGE_ACCESS_MODE="${runtime_home_access_mode}"
export E2E_SHARED_STORAGE_SIZE="${shared_storage_size}"
export E2E_RWO_STORAGE_SIZE="${rwo_storage_size}"
export E2E_RUNTIME_HOME_STORAGE_SIZE="${runtime_home_storage_size}"
export PRODUCT_CONFORMANCE_HOOK="${product_hook}"
if [ "${root_squash_mode}" = "evidence" ]; then
  export ROOT_SQUASH_EVIDENCE_FILE="${ROOT_SQUASH_EVIDENCE_FILE}"
fi

"${REPO_ROOT:-/repo}/scripts/test/kubernetes/run-kubernetes-conformance-e2e.sh"

grep -Eq '"result"[[:space:]]*:[[:space:]]*"passed"' \
  "${artifact_dir}/capabilities.json" || fail "storage and generation suite did not pass"
jq -e '
  .releaseConformanceVerified == true
  and .rwoStatePersistence == true
' \
  "${artifact_dir}/capabilities.json" >/dev/null || \
  fail "core capability report is not eligible for release certification"
"${REPO_ROOT:-/repo}/scripts/test/kubernetes/product-conformance/validate-product-report.sh" \
  "${artifact_dir}/product-capabilities.json" || \
  fail "full product evidence contract did not certify the run"

runner_result="passed"
log "${platform} conformance suite passed; artifacts: ${artifact_dir}"
