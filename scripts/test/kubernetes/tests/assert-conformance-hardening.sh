#!/bin/sh

set -eu

script_dir="$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)"
repo_root="${REPO_ROOT:-$(CDPATH='' cd -- "${script_dir}/../../../.." && pwd)}"
temporary_root="$(mktemp -d)"

cleanup() {
  rm -rf "${temporary_root}"
}

fail() {
  printf 'Conformance hardening assertion failed: %s\n' "$*" >&2
  exit 1
}

assert_contains() {
  assert_file="$1"
  assert_expected="$2"
  if ! grep -Fq -- "${assert_expected}" "${assert_file}"; then
    sed -n '1,120p' "${assert_file}" >&2 || true
    fail "${assert_file} does not contain ${assert_expected}"
  fi
}

trap cleanup EXIT HUP INT TERM

test_platform_wrapper() {
  root="${temporary_root}/platform-wrapper"
  bin_dir="${root}/bin"
  fake_repo="${root}/repo"
  mkdir -p \
    "${bin_dir}" \
    "${fake_repo}/scripts/test/kubernetes/product-conformance"

  cat > "${bin_dir}/kubectl" <<'EOF'
#!/bin/sh
set -eu
case "$1" in
  config)
    printf 'formal-context\n'
    ;;
  auth)
    printf 'yes\n'
    ;;
  cluster-info)
    printf 'cluster is ready\n'
    ;;
  get)
    case "$2" in
      nodes)
        case "$*" in
          *--no-headers*)
            printf 'node-a Ready\nnode-b Ready\n'
            ;;
          *) printf 'apiVersion: v1\nkind: NodeList\n' ;;
        esac
        ;;
      node) ;;
      secret)
        printf '%s\n' '{"type":"kubernetes.io/dockerconfigjson","data":{".dockerconfigjson":"c2Vuc2l0aXZlLWNvbmZpZw=="}}'
        ;;
      storageclass)
        case "$*" in
          *jsonpath*) printf 'Delete' ;;
          *) printf 'apiVersion: storage.k8s.io/v1\nkind: StorageClass\n' ;;
        esac
        ;;
      *) printf 'apiVersion: v1\nkind: List\n' ;;
    esac
    ;;
  *) ;;
esac
EOF
  chmod 0755 "${bin_dir}/kubectl"

  cat > "${fake_repo}/scripts/test/kubernetes/run-kubernetes-conformance-e2e.sh" <<'EOF'
#!/bin/sh
set -eu
output_dir="${ARTIFACT_DIR}/${E2E_RUN_ID}"
mkdir -p "${output_dir}"
printf '{"result":"passed","releaseConformanceVerified":%s,"rwoStatePersistence":true}\n' \
  "${FAKE_RELEASE_VERIFIED:-true}" > "${output_dir}/capabilities.json"
printf '%s\n' '{"result":"passed"}' > "${output_dir}/product-capabilities.json"
EOF
  chmod 0755 "${fake_repo}/scripts/test/kubernetes/run-kubernetes-conformance-e2e.sh"
  cat > "${fake_repo}/scripts/test/kubernetes/product-conformance/validate-product-report.sh" <<'EOF'
#!/bin/sh
exit 0
EOF
  chmod 0755 "${fake_repo}/scripts/test/kubernetes/product-conformance/validate-product-report.sh"
  hook="${root}/product-hook.sh"
  printf '#!/bin/sh\nexit 0\n' > "${hook}"
  chmod 0755 "${hook}"
  kubeconfig="${root}/kubeconfig"
  printf 'apiVersion: v1\n' > "${kubeconfig}"
  root_squash_evidence="${root}/root-squash.json"
  printf '%s\n' '{"rootSquash":true}' > "${root_squash_evidence}"
  digest="$(printf '%064d' 0)"

  run_wrapper() {
    artifact_root="$1"
    run_id="$2"
    redis_reference="$3"
    release_verified="${4:-true}"
    mkdir -p "${artifact_root}"
    env \
      PATH="${bin_dir}:${PATH}" \
      REPO_ROOT="${fake_repo}" \
      AILERON_CONFORMANCE_PLATFORM=rke2 \
      EXPECTED_KUBE_CONTEXT=formal-context \
      ARTIFACT_DIR="${artifact_root}" \
      E2E_RUN_ID="${run_id}" \
      FAKE_RELEASE_VERIFIED="${release_verified}" \
      RWX_STORAGE_CLASS=nfs-rwx \
      RWO_STORAGE_CLASS=local-rwo \
      OPERATOR_IMAGE="registry.example/operator@sha256:${digest}" \
      MANAGER_IMAGE="registry.example/manager@sha256:${digest}" \
      WORKLOAD_PROBE_IMAGE="registry.example/probe@sha256:${digest}" \
      RUNTIME_IMAGE="registry.example/runtime@sha256:${digest}" \
      BROWSER_IMAGE="registry.example/browser@sha256:${digest}" \
      CANVAS_IMAGE="registry.example/canvas@sha256:${digest}" \
      PRODUCT_DRIVER_IMAGE="registry.example/driver@sha256:${digest}" \
      REDIS_IMAGE="${redis_reference}" \
      POSTGRES_IMAGE="registry.example/postgres@sha256:${digest}" \
      PRODUCT_CONFORMANCE_HOOK="${hook}" \
      ROOT_SQUASH_MODE=evidence \
      ROOT_SQUASH_EVIDENCE_FILE="${root_squash_evidence}" \
      PLATFORM_STORAGE_GID=100 \
      KUBECONFIG="${kubeconfig}" \
      IMAGE_PULL_SECRET_SOURCE_NAMESPACE=registry-system \
      IMAGE_PULL_SECRET_SOURCE_NAME=harbor-source \
      IMAGE_PULL_SECRET_NAME=harbor-pull \
      "${repo_root}/scripts/test/kubernetes/run-kubernetes-platform-conformance.sh"
  }

  success_artifacts="${root}/success-artifacts"
  run_wrapper \
    "${success_artifacts}" \
    formal-success \
    "registry.example/redis@sha256:${digest}"
  inputs="${success_artifacts}/formal-success/platform-inputs.txt"
  for expected in \
    'image_reference_policy=immutable-digest-only' \
    'rwx_storage_class=nfs-rwx' \
    'rwo_storage_class=local-rwo' \
    'runtime_home_storage_class=local-rwo' \
    'runtime_home_access_mode=ReadWriteOnce' \
    "redis_image=registry.example/redis@sha256:${digest}" \
    "postgres_image=registry.example/postgres@sha256:${digest}" \
    'image_pull_secret_source=registry-system/harbor-source' \
    'image_pull_secret_target_name=harbor-pull'; do
    assert_contains "${inputs}" "${expected}"
  done
  if grep -Fq 'c2Vuc2l0aXZlLWNvbmZpZw==' "${inputs}"; then
    fail "platform inputs exposed dockerconfig secret content"
  fi

  mutable_stderr="${root}/mutable.stderr"
  if run_wrapper \
    "${root}/mutable-artifacts" \
    formal-mutable \
    'registry.example/redis:latest' \
    > "${root}/mutable.stdout" 2> "${mutable_stderr}"; then
    fail "formal wrapper certified a mutable platform image"
  fi
  assert_contains "${mutable_stderr}" 'must use an immutable sha256 digest'

  uncertified_stderr="${root}/uncertified.stderr"
  if run_wrapper \
    "${root}/uncertified-artifacts" \
    formal-uncertified \
    "registry.example/redis@sha256:${digest}" \
    false \
    > "${root}/uncertified.stdout" 2> "${uncertified_stderr}"; then
    fail "formal wrapper accepted a non-certifying core report"
  fi
  assert_contains "${uncertified_stderr}" \
    'core capability report is not eligible for release certification'
}

test_crd_contract() {
  root="${temporary_root}/crd-contract"
  bin_dir="${root}/bin"
  mkdir -p "${bin_dir}"
  expected="${root}/expected.json"
  observed="${root}/observed.json"
  mismatched="${root}/mismatched.json"
  manifest="${root}/workspace-crd.yaml"
  log_file="${root}/kubectl.log"
  printf '{}\n' > "${manifest}"
  cat > "${expected}" <<'EOF'
{"spec":{"group":"platform.aileron.io","scope":"Namespaced","names":{"plural":"workspaces","singular":"workspace","kind":"Workspace","shortNames":["ws"]},"versions":[{"name":"v1alpha1","served":true,"storage":true,"schema":{"openAPIV3Schema":{"type":"object","properties":{"spec":{"type":"object"}}}},"subresources":{"status":{}},"additionalPrinterColumns":[]}]}}
EOF
  cp "${expected}" "${observed}"
  jq '.spec.versions[0].name = "v1beta1"' "${expected}" > "${mismatched}"

  cat > "${bin_dir}/kubectl" <<'EOF'
#!/bin/sh
set -eu
printf '%s\n' "$*" >> "${KUBECTL_LOG}"
case "$1" in
  get)
    case "$*" in
      *'-o json'*) cat "${OBSERVED_CRD}" ;;
      *) [ "${CRD_PRESENT}" = true ] ;;
    esac
    ;;
  create)
    cat "${EXPECTED_CRD}"
    ;;
  apply)
    [ "${CRD_PRESENT}" = false ] || exit 91
    ;;
  wait) ;;
  delete) ;;
  patch) exit 92 ;;
  *) exit 93 ;;
esac
EOF
  chmod 0755 "${bin_dir}/kubectl"

  existing_artifacts="${root}/existing-artifacts"
  : > "${log_file}"
  env \
    PATH="${bin_dir}:${PATH}" \
    KUBECTL_LOG="${log_file}" \
    CRD_PRESENT=true \
    EXPECTED_CRD="${expected}" \
    OBSERVED_CRD="${observed}" \
    WORKSPACE_CRD_MANIFEST="${manifest}" \
    WORKSPACE_CRD_ARTIFACT_DIR="${existing_artifacts}" \
    "${repo_root}/scripts/test/kubernetes/crd-contract.sh" ensure
  assert_contains "${existing_artifacts}/workspace-crd-disposition.txt" preexisting
  if grep -Eq '^(apply|patch|delete) ' "${log_file}"; then
    fail "pre-existing CRD verification used a mutating kubectl command"
  fi
  env \
    PATH="${bin_dir}:${PATH}" \
    KUBECTL_LOG="${log_file}" \
    CRD_PRESENT=true \
    EXPECTED_CRD="${expected}" \
    OBSERVED_CRD="${observed}" \
    WORKSPACE_CRD_MANIFEST="${manifest}" \
    WORKSPACE_CRD_ARTIFACT_DIR="${existing_artifacts}" \
    "${repo_root}/scripts/test/kubernetes/crd-contract.sh" cleanup
  if grep -Eq '^delete ' "${log_file}"; then
    fail "cleanup deleted a pre-existing CRD"
  fi

  mismatch_stderr="${root}/mismatch.stderr"
  if env \
    PATH="${bin_dir}:${PATH}" \
    KUBECTL_LOG="${log_file}" \
    CRD_PRESENT=true \
    EXPECTED_CRD="${expected}" \
    OBSERVED_CRD="${mismatched}" \
    WORKSPACE_CRD_MANIFEST="${manifest}" \
    WORKSPACE_CRD_ARTIFACT_DIR="${root}/mismatch-artifacts" \
    "${repo_root}/scripts/test/kubernetes/crd-contract.sh" ensure \
    > "${root}/mismatch.stdout" 2> "${mismatch_stderr}"; then
    fail "CRD contract accepted a mismatched served version"
  fi
  assert_contains "${mismatch_stderr}" 'does not match the exact required schema and versions'

  fresh_artifacts="${root}/fresh-artifacts"
  : > "${log_file}"
  env \
    PATH="${bin_dir}:${PATH}" \
    KUBECTL_LOG="${log_file}" \
    CRD_PRESENT=false \
    EXPECTED_CRD="${expected}" \
    OBSERVED_CRD="${observed}" \
    WORKSPACE_CRD_MANIFEST="${manifest}" \
    WORKSPACE_CRD_ARTIFACT_DIR="${fresh_artifacts}" \
    "${repo_root}/scripts/test/kubernetes/crd-contract.sh" ensure
  assert_contains "${fresh_artifacts}/workspace-crd-disposition.txt" created
  grep -Eq '^apply ' "${log_file}" || fail "fresh CRD flow did not apply the manifest"
  env \
    PATH="${bin_dir}:${PATH}" \
    KUBECTL_LOG="${log_file}" \
    CRD_PRESENT=false \
    EXPECTED_CRD="${expected}" \
    OBSERVED_CRD="${observed}" \
    WORKSPACE_CRD_MANIFEST="${manifest}" \
    WORKSPACE_CRD_ARTIFACT_DIR="${fresh_artifacts}" \
    "${repo_root}/scripts/test/kubernetes/crd-contract.sh" cleanup
  grep -Eq '^delete crd workspaces.platform.aileron.io ' "${log_file}" || \
    fail "fresh CRD cleanup did not delete the owned CRD"

  grep -Fq 'crd-contract.sh" ensure' \
    "${repo_root}/scripts/test/kubernetes/run-kubernetes-conformance-e2e.sh" || \
    fail "Kubernetes conformance E2E does not use the CRD contract helper"
}

test_image_pull_secret_copy() {
  root="${temporary_root}/image-pull-secret"
  bin_dir="${root}/bin"
  mkdir -p "${bin_dir}"
  source_secret="${root}/source-secret.json"
  copied_secret="${root}/copied-secret.json"
  kubectl_log="${root}/kubectl.log"
  sensitive_value='c2Vuc2l0aXZlLWhhcmJvci1jb25maWc='
  printf '%s\n' \
    "{\"type\":\"kubernetes.io/dockerconfigjson\",\"data\":{\".dockerconfigjson\":\"${sensitive_value}\"}}" \
    > "${source_secret}"
  cat > "${bin_dir}/kubectl" <<'EOF'
#!/bin/sh
set -eu
printf '%s\n' "$*" >> "${KUBECTL_LOG}"
case "$1" in
  get) cat "${SOURCE_SECRET}" ;;
  create) cat > "${COPIED_SECRET}" ;;
  patch) ;;
  *) exit 94 ;;
esac
EOF
  chmod 0755 "${bin_dir}/kubectl"

  artifact_dir="${root}/artifacts"
  env \
    PATH="${bin_dir}:${PATH}" \
    KUBECTL_LOG="${kubectl_log}" \
    SOURCE_SECRET="${source_secret}" \
    COPIED_SECRET="${copied_secret}" \
    IMAGE_PULL_SECRET_SOURCE_NAMESPACE=registry-system \
    IMAGE_PULL_SECRET_SOURCE_NAME=harbor-source \
    IMAGE_PULL_SECRET_TARGET_NAMESPACE=workspace-test \
    IMAGE_PULL_SECRET_NAME=harbor-pull \
    IMAGE_PULL_SECRET_ARTIFACT_DIR="${artifact_dir}" \
    "${repo_root}/scripts/test/kubernetes/image-pull-secret.sh"

  jq -e \
    --arg sensitive "${sensitive_value}" '
      .metadata == {namespace: "workspace-test", name: "harbor-pull"}
      and .type == "kubernetes.io/dockerconfigjson"
      and .data[".dockerconfigjson"] == $sensitive
    ' "${copied_secret}" >/dev/null || fail "copied image pull Secret is invalid"
  metadata="${artifact_dir}/image-pull-secret-metadata.txt"
  assert_contains "${metadata}" 'source_namespace=registry-system'
  assert_contains "${metadata}" 'target_name=harbor-pull'
  if grep -Fq "${sensitive_value}" "${metadata}"; then
    fail "image pull Secret evidence exposed dockerconfig content"
  fi
  assert_contains "${kubectl_log}" \
    'patch serviceaccount default -n workspace-test --type=merge'
}

test_failed_product_job() {
  root="${temporary_root}/failed-product-job"
  bin_dir="${root}/bin"
  mkdir -p "${bin_dir}"
  capture="${root}/driver-job.yaml"
  cat > "${bin_dir}/kubectl" <<'EOF'
#!/bin/sh
set -eu
case "$1" in
  delete) ;;
  apply)
    previous=""
    for argument in "$@"; do
      if [ "${previous}" = "-f" ]; then cp "${argument}" "${DRIVER_JOB_CAPTURE}"; fi
      previous="${argument}"
    done
    ;;
  get)
    case "$*" in
      *status.succeeded*) ;;
      *status.failed*) printf '1' ;;
    esac
    ;;
  logs)
    printf '%s\n' \
      'driver failed after writing stale output' \
      'PRODUCT_CONFORMANCE_RESULT={"schemaVersion":1,"result":"passed"}'
    ;;
  *) exit 95 ;;
esac
EOF
  chmod 0755 "${bin_dir}/kubectl"
  stderr="${root}/stderr"
  if env \
    PATH="${bin_dir}:${PATH}" \
    DRIVER_JOB_CAPTURE="${capture}" \
    E2E_NAMESPACE=test-namespace \
    E2E_RUN_ID=test-run \
    E2E_STORAGE_MODE=dynamic \
    PRODUCT_DRIVER_IMAGE=registry.example/driver:test \
    PRODUCT_CAPABILITIES_OUTPUT="${root}/result.json" \
    RUNTIME_IMAGE=registry.example/runtime:test \
    BROWSER_IMAGE=registry.example/browser:test \
    CANVAS_IMAGE=registry.example/canvas:test \
    RWX_STORAGE_CLASS=nfs-rwx \
    IMAGE_PULL_SECRET_NAME=harbor-pull \
    "${repo_root}/scripts/test/kubernetes/product-conformance/run-product-conformance.sh" \
    > "${root}/stdout" 2> "${stderr}"; then
    fail "failed product Job was accepted because its logs contained a passed result"
  fi
  assert_contains "${stderr}" 'driver failed after writing stale output'
  assert_contains "${stderr}" 'product conformance Job failed'
  [ ! -e "${root}/result.json" ] || fail "failed Job wrote certified output"
  assert_contains "${capture}" 'imagePullSecrets:'
  assert_contains "${capture}" 'name: harbor-pull'
}

test_unknown_e2e_mode_rejected() {
  root="${temporary_root}/unknown-e2e-mode"
  mkdir -p "${root}"
  stderr="${root}/stderr"
  if env \
    E2E_MODE=unknown \
    E2E_RUN_ID=unknown-mode \
    OPERATOR_IMAGE=operator:test \
    MANAGER_IMAGE=manager:test \
    WORKLOAD_PROBE_IMAGE=probe:test \
    "${repo_root}/scripts/test/kubernetes/run-kubernetes-conformance-e2e.sh" \
    > "${root}/stdout" 2> "${stderr}"; then
    fail "unknown E2E mode was accepted"
  fi
  assert_contains "${stderr}" 'E2E_MODE must be local, diagnostic, or platform'
}

test_wait_for_first_consumer_order() {
  runner="${repo_root}/scripts/test/kubernetes/run-kubernetes-conformance-e2e.sh"
  consumer_line="$(
    grep -nF 'kube apply -f "${render_dir}/manager-writer.yaml"' "${runner}" \
      | head -n 1 \
      | cut -d: -f1
  )"
  rwo_wait_line="$(
    grep -nF '"pvc/manager-state-pvc"' "${runner}" \
      | head -n 1 \
      | cut -d: -f1
  )"
  [ -n "${consumer_line}" ] || fail "Manager state consumer creation is missing"
  [ -n "${rwo_wait_line}" ] || fail "Manager state PVC wait is missing"
  [ "${rwo_wait_line}" -gt "${consumer_line}" ] || \
    fail "Manager state PVC is awaited before its WaitForFirstConsumer Pod exists"
}

test_cleanup_finalizes_workspaces_before_namespace_delete() {
  runner="${repo_root}/scripts/test/kubernetes/run-kubernetes-conformance-e2e.sh"
  collect_line="$(
    grep -nF '  collect_artifacts' "${runner}" | tail -n 1 | cut -d: -f1
  )"
  cleanup_call_line="$(
    grep -nF '      cleanup_test_namespace' "${runner}" | head -n 1 | cut -d: -f1
  )"
  workspace_delete_line="$(
    grep -nF 'kube delete workspaces.platform.aileron.io --all -n "${namespace}"' \
      "${runner}" | head -n 1 | cut -d: -f1
  )"
  workspace_wait_line="$(
    grep -nF 'cleanup_wait_until "Workspace finalization" 60 cleanup_workspaces_absent' \
      "${runner}" | head -n 1 | cut -d: -f1
  )"
  finalizer_patch_line="$(
    grep -nF 'kube patch "${workspace_resource}" -n "${namespace}" --type=merge' \
      "${runner}" | head -n 1 | cut -d: -f1
  )"
  namespace_delete_line="$(
    grep -nF 'kube delete namespace "${namespace}" --wait=false' \
      "${runner}" | head -n 1 | cut -d: -f1
  )"
  namespace_wait_line="$(
    grep -nF 'cleanup_wait_until "test namespace deletion" 120 cleanup_namespace_absent' \
      "${runner}" | head -n 1 | cut -d: -f1
  )"
  for line in \
    "${collect_line}" \
    "${cleanup_call_line}" \
    "${workspace_delete_line}" \
    "${workspace_wait_line}" \
    "${finalizer_patch_line}" \
    "${namespace_delete_line}" \
    "${namespace_wait_line}"; do
    [ -n "${line}" ] || fail "test namespace cleanup contract is incomplete"
  done
  [ "${cleanup_call_line}" -gt "${collect_line}" ] || \
    fail "test namespace cleanup runs before artifacts are collected"
  [ "${workspace_delete_line}" -lt "${workspace_wait_line}" ] && \
    [ "${workspace_wait_line}" -lt "${finalizer_patch_line}" ] && \
    [ "${finalizer_patch_line}" -lt "${namespace_delete_line}" ] && \
    [ "${namespace_delete_line}" -lt "${namespace_wait_line}" ] || \
    fail "test namespace cleanup does not preserve finalization ordering"
  assert_contains "${runner}" \
    "jsonpath='{.metadata.labels.aileron\\.io/test-run-id}'"
  assert_contains "${runner}" \
    'cleanup_wait_until "forced Workspace finalization" 15 cleanup_workspaces_absent'
}

test_cleanup_wait_observes_timeout_boundary() {
  runner="${repo_root}/scripts/test/kubernetes/run-kubernetes-conformance-e2e.sh"
  function_file="${temporary_root}/cleanup-wait-function.sh"
  sleep_marker="${temporary_root}/cleanup-wait-slept"
  sed -n '/^cleanup_wait_until() {$/,/^}$/p' \
    "${runner}" > "${function_file}"

  if ! sh -c '
    . "$1"
    log() { :; }
    sleep_marker_path="$2"
    sleep() { : > "${sleep_marker_path}"; }
    checks=0
    ready_on_boundary() {
      checks=$((checks + 1))
      [ "${checks}" -ge 2 ]
    }
    cleanup_wait_until "boundary condition" 1 ready_on_boundary
    [ "${checks}" -eq 2 ]
    [ -e "$2" ]
    rm -f "$2"
    never_ready() { return 1; }
    cleanup_wait_until "test condition" 0 never_ready || true
    [ ! -e "$2" ]
  ' sh "${function_file}" "${sleep_marker}"; then
    fail "cleanup wait does not observe the timeout boundary correctly"
  fi
}

test_cleanup_absence_requires_successful_api_response() {
  runner="${repo_root}/scripts/test/kubernetes/run-kubernetes-conformance-e2e.sh"
  function_file="${temporary_root}/cleanup-absence-functions.sh"
  sed -n '/^cleanup_namespace_absent() {$/,/^}$/p' \
    "${runner}" > "${function_file}"
  assert_contains "${function_file}" "--ignore-not-found"

  if ! sh -c '
    . "$1"
    namespace="test-namespace"
    response="missing"
    kube() {
      case "${response}" in
        missing) return 0 ;;
        present) printf "%s\n" "namespace/test-namespace"; return 0 ;;
        error) return 1 ;;
      esac
    }
    cleanup_namespace_absent
    response="present"
    if cleanup_namespace_absent; then
      exit 1
    fi
    response="error"
    if cleanup_namespace_absent; then
      exit 1
    fi
  ' sh "${function_file}"; then
    fail "cleanup absence check treats API errors or existing namespaces as deleted"
  fi
}

test_product_runtime_home_storage_forwarding() {
  runner="${repo_root}/scripts/test/kubernetes/run-kubernetes-conformance-e2e.sh"
  hook="${repo_root}/scripts/test/kubernetes/product-conformance/product-conformance-hook.sh"
  installer="${repo_root}/scripts/test/kubernetes/product-conformance/install-product-stack.sh"
  runner_hook_block="${temporary_root}/product-hook-call.txt"

  sed -n \
    '/^assert_product_hook() {$/,/^snapshot_before_delete() {$/p' \
    "${runner}" > "${runner_hook_block}"

  for expected in \
    'RUNTIME_HOME_STORAGE_CLASS="${runtime_home_storage_class}"' \
    'E2E_SHARED_STORAGE_SIZE="${shared_storage_size}"' \
    'E2E_RWO_STORAGE_SIZE="${rwo_storage_size}"' \
    'E2E_RUNTIME_HOME_STORAGE_SIZE="${runtime_home_storage_size}"'; do
    assert_contains "${runner_hook_block}" "${expected}"
    assert_contains "${hook}" "${expected}"
  done
  assert_contains \
    "${runner_hook_block}" \
    'RUNTIME_HOME_STORAGE_ACCESS_MODE="${runtime_home_access_mode}"'
  assert_contains \
    "${hook}" \
    'RUNTIME_HOME_STORAGE_ACCESS_MODE="${runtime_home_storage_access_mode}"'
  for expected in \
    '--set-string kubernetes.runtimeHome.storageClassName="${runtime_home_storage_class}"' \
    '--set-string kubernetes.runtimeHome.accessMode="${runtime_home_storage_access_mode}"' \
    '"RUNTIME_HOME_STORAGE_CLASS_NAME=${runtime_home_storage_class}"' \
    '"RUNTIME_HOME_STORAGE_ACCESS_MODE=${runtime_home_storage_access_mode}"'; do
    assert_contains "${installer}" "${expected}"
  done
  if grep -Fq \
    'kubernetes.runtimeHome.accessMode=ReadWriteOnce' \
    "${installer}"; then
    fail "product installer hardcodes the Runtime HOME access mode"
  fi
  if grep -Fq \
    '"RUNTIME_HOME_STORAGE_ACCESS_MODE=ReadWriteOnce"' \
    "${installer}"; then
    fail "product installer hardcodes the Operator Runtime HOME access mode"
  fi
}

test_platform_wrapper
test_crd_contract
test_image_pull_secret_copy
test_failed_product_job
test_unknown_e2e_mode_rejected
test_wait_for_first_consumer_order
test_cleanup_finalizes_workspaces_before_namespace_delete
test_cleanup_wait_observes_timeout_boundary
test_cleanup_absence_requires_successful_api_response
test_product_runtime_home_storage_forwarding

printf 'Conformance hardening assertions passed\n'
