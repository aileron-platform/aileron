#!/bin/sh

set -eu

script_dir="$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)"
runtime_home_storage_class="${RUNTIME_HOME_STORAGE_CLASS:-${RWO_STORAGE_CLASS:?RWO_STORAGE_CLASS is required}}"
runtime_home_storage_access_mode="${RUNTIME_HOME_STORAGE_ACCESS_MODE:-ReadWriteOnce}"
shared_storage_size="${E2E_SHARED_STORAGE_SIZE:-1Gi}"
rwo_storage_size="${E2E_RWO_STORAGE_SIZE:-1Gi}"
runtime_home_storage_size="${E2E_RUNTIME_HOME_STORAGE_SIZE:-2Gi}"
data_service_mode="${PRODUCT_DATA_SERVICE_MODE:-bundled}"

RUNTIME_HOME_STORAGE_CLASS="${runtime_home_storage_class}" \
RUNTIME_HOME_STORAGE_ACCESS_MODE="${runtime_home_storage_access_mode}" \
E2E_SHARED_STORAGE_SIZE="${shared_storage_size}" \
E2E_RWO_STORAGE_SIZE="${rwo_storage_size}" \
E2E_RUNTIME_HOME_STORAGE_SIZE="${runtime_home_storage_size}" \
PRODUCT_DATA_SERVICE_MODE="${data_service_mode}" \
  "${script_dir}/install-product-stack.sh"
"${script_dir}/run-product-conformance.sh"
if command -v kubectl >/dev/null 2>&1; then
  kubectl delete job product-conformance -n "${E2E_NAMESPACE}" \
    --ignore-not-found --wait=true >/dev/null
else
  k3s kubectl delete job product-conformance -n "${E2E_NAMESPACE}" \
    --ignore-not-found --wait=true >/dev/null
fi
PRODUCT_TRANSACTION_OUTPUT="${PRODUCT_CAPABILITIES_OUTPUT%.json}-installation-transaction.tsv" \
  "${script_dir}/verify-installation-transaction.sh"
if [ "${data_service_mode}" = "external" ]; then
  identity_output="${PRODUCT_CAPABILITIES_OUTPUT%.json}-identity-external-lifecycle.tsv"
  IDENTITY_LIFECYCLE_OUTPUT="${identity_output}" \
  IDENTITY_DESTRUCTIVE_CONFIRMATION="${E2E_NAMESPACE}-identity/identity/restore/${E2E_RUN_ID}" \
    "${script_dir}/verify-identity-external-lifecycle.sh"
fi
