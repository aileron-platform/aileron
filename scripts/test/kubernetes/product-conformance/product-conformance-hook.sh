#!/bin/sh

set -eu

script_dir="$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)"
runtime_home_storage_class="${RUNTIME_HOME_STORAGE_CLASS:-${RWO_STORAGE_CLASS:?RWO_STORAGE_CLASS is required}}"
runtime_home_storage_access_mode="${RUNTIME_HOME_STORAGE_ACCESS_MODE:-ReadWriteOnce}"
shared_storage_size="${E2E_SHARED_STORAGE_SIZE:-1Gi}"
rwo_storage_size="${E2E_RWO_STORAGE_SIZE:-1Gi}"
runtime_home_storage_size="${E2E_RUNTIME_HOME_STORAGE_SIZE:-2Gi}"

RUNTIME_HOME_STORAGE_CLASS="${runtime_home_storage_class}" \
RUNTIME_HOME_STORAGE_ACCESS_MODE="${runtime_home_storage_access_mode}" \
E2E_SHARED_STORAGE_SIZE="${shared_storage_size}" \
E2E_RWO_STORAGE_SIZE="${rwo_storage_size}" \
E2E_RUNTIME_HOME_STORAGE_SIZE="${runtime_home_storage_size}" \
  "${script_dir}/install-product-stack.sh"
"${script_dir}/run-product-conformance.sh"
