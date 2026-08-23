#!/bin/sh

set -eu
umask 077

repository_root="$(CDPATH='' cd -- "$(dirname -- "$0")/../../.." && pwd)"
cd "${repository_root}"

expected_commit=""
registry=""
project=""
values_file=""
kubeconfig=""
namespace=""
context=""
identity_mode=""
identity_rendered_manifest=""
harbor_dockerconfig=""
apps_tls_cert=""
oidc_issuer=""
oidc_ca=""
platform_artifacts=""
result_sidecar=""
timeout="${DEPLOY_TIMEOUT:-20m}"

usage() {
  echo "Usage: $0 --commit SHA --registry HOST --project NAME --values FILE --kubeconfig FILE --context NAME --namespace NAME --identity-mode MODE [--identity-manifest FILE] --harbor-dockerconfig FILE --apps-tls-cert FILE --oidc-issuer URL --oidc-ca FILE --platform-artifacts DIR --result-sidecar FILE [--timeout 20m]" >&2
  exit 2
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --commit) expected_commit="${2:-}"; shift 2 ;;
    --registry) registry="${2:-}"; shift 2 ;;
    --project) project="${2:-}"; shift 2 ;;
    --values) values_file="${2:-}"; shift 2 ;;
    --kubeconfig) kubeconfig="${2:-}"; shift 2 ;;
    --context) context="${2:-}"; shift 2 ;;
    --namespace) namespace="${2:-}"; shift 2 ;;
    --identity-mode) identity_mode="${2:-}"; shift 2 ;;
    --identity-manifest) identity_rendered_manifest="${2:-}"; shift 2 ;;
    --harbor-dockerconfig) harbor_dockerconfig="${2:-}"; shift 2 ;;
    --apps-tls-cert) apps_tls_cert="${2:-}"; shift 2 ;;
    --oidc-issuer) oidc_issuer="${2:-}"; shift 2 ;;
    --oidc-ca) oidc_ca="${2:-}"; shift 2 ;;
    --platform-artifacts) platform_artifacts="${2:-}"; shift 2 ;;
    --result-sidecar) result_sidecar="${2:-}"; shift 2 ;;
    --timeout) timeout="${2:-}"; shift 2 ;;
    *) usage ;;
  esac
done

for required_value in \
  "${expected_commit}" \
  "${registry}" \
  "${project}" \
  "${values_file}" \
  "${kubeconfig}" \
  "${context}" \
  "${namespace}" \
  "${identity_mode}" \
  "${harbor_dockerconfig}" \
  "${apps_tls_cert}" \
  "${oidc_issuer}" \
  "${oidc_ca}" \
  "${platform_artifacts}" \
  "${result_sidecar}"; do
  [ -n "${required_value}" ] || usage
done
[ -n "${context}" ] || usage
printf '%s' "${expected_commit}" | grep -Eq '^[0-9a-f]{40}$' || usage
printf '%s' "${timeout}" | grep -Eq '^[1-9][0-9]*(s|m|h)$' || usage

fail() {
  echo "RKE2 deployment failed: $*" >&2
  exit 1
}

kubectl_target() {
  kubectl --context "${context}" "$@"
}

helm_target() {
  helm --kube-context "${context}" "$@"
}

[ "${namespace}" = "workspace-system" ] ||
  fail "--namespace must be workspace-system"
case "${identity_mode}" in
  bundledKeycloak)
    [ -n "${identity_rendered_manifest}" ] ||
      fail "--identity-manifest is required in bundledKeycloak mode"
    [ "${oidc_issuer}" = "https://keycloak.apps.rke.soez.tw/realms/aileron" ] ||
      fail "bundledKeycloak issuer does not match the installation contract"
    ;;
  externalOidc)
    [ -z "${identity_rendered_manifest}" ] ||
      fail "--identity-manifest must be absent in externalOidc mode"
    ;;
  *) fail "--identity-mode must be bundledKeycloak or externalOidc" ;;
esac

for command_name in awk base64 getent git helm jq kubectl openssl python3; do
  command -v "${command_name}" >/dev/null 2>&1 ||
    fail "required command is unavailable: ${command_name}"
done

[ -z "$(git status --porcelain)" ] ||
  fail "deployment requires a clean Git checkout"
actual_commit="$(git rev-parse --verify HEAD)"
[ "${actual_commit}" = "${expected_commit}" ] ||
  fail "Git HEAD does not match --commit"

private_root="$({
  python3 "${repository_root}/scripts/deploy/rke2/private_input.py" private-root
} 2>/dev/null)" || fail "installation private root is invalid"
transactions_root="${private_root}/transactions"
if [ -e "${transactions_root}" ] || [ -L "${transactions_root}" ]; then
  python3 "${repository_root}/scripts/deploy/rke2/private_input.py" \
    validate-directory \
    --path "${transactions_root}" \
    --description "deployment transactions directory" >/dev/null ||
    fail "deployment transactions directory is invalid"
else
  mkdir -m 0700 "${transactions_root}" ||
    fail "deployment transactions directory cannot be created"
fi
transaction_directory="$(mktemp -d "${transactions_root}/deploy.XXXXXX")" ||
  fail "deployment transaction directory cannot be created"
chmod 0700 "${transaction_directory}"

python3 "${repository_root}/scripts/deploy/rke2/installation_transaction.py" \
  validate-core-result \
  --path "${result_sidecar}" \
  --commit "${expected_commit}" >/dev/null 2>&1 ||
  fail "Core deployment result sidecar is invalid"

rollback_required=false
result_recorded=false
previous_revision=""
helm_mutation_started=false

rollback_release() {
  if [ "${helm_mutation_started}" != true ]; then
    return 0
  fi
  if [ -n "${previous_revision}" ]; then
    helm_target rollback aileron "${previous_revision}" \
      --namespace "${namespace}" \
      --wait \
      --cleanup-on-fail \
      --timeout "${timeout}"
    return
  fi

  rollback_release_inventory="${transaction_directory}/core-rollback-release.json"
  helm_target list \
    --all \
    --namespace "${namespace}" \
    --filter '^aileron$' \
    --output json >"${rollback_release_inventory}" || return 1
  rollback_release_count="$(
    jq -er 'if type == "array" then length else error("shape") end' \
      "${rollback_release_inventory}"
  )" || return 1
  case "${rollback_release_count}" in
    0) return 0 ;;
    1)
      jq -e '.[0].name == "aileron"' "${rollback_release_inventory}" \
        >/dev/null || return 1
      ;;
    *) return 1 ;;
  esac
  helm_target uninstall aileron \
    --namespace "${namespace}" \
    --wait \
    --timeout "${timeout}"
}

rollback_core() {
  core_release_recovered=false
  core_crd_recovered=false
  if rollback_release; then
    core_release_recovered=true
  else
    echo "RKE2 Core Helm recovery failed after the primary failure" >&2
  fi
  if python3 \
    "${repository_root}/scripts/deploy/rke2/installation_transaction.py" \
    restore-crd-transaction \
    --transaction-directory "${transaction_directory}" \
    --context "${context}" >/dev/null 2>&1; then
    core_crd_recovered=true
  else
    echo "RKE2 Workspace CRD recovery failed after the primary failure" >&2
  fi
  [ "${core_release_recovered}" = true ] &&
    [ "${core_crd_recovered}" = true ]
}

record_core_result() {
  result_status="$1"
  result_rollback_attempted="$2"
  result_rollback_succeeded="$3"
  python3 "${repository_root}/scripts/deploy/rke2/installation_transaction.py" \
    write-core-result \
    --path "${result_sidecar}" \
    --commit "${expected_commit}" \
    --primary-exit-code "${result_status}" \
    --core-rollback-attempted "${result_rollback_attempted}" \
    --core-rollback-succeeded "${result_rollback_succeeded}" >/dev/null 2>&1
}

cleanup() {
  status="$?"
  trap - EXIT HUP INT TERM
  set +e
  rollback_attempted=false
  rollback_succeeded=false
  if [ "${status}" -ne 0 ] && [ "${rollback_required}" = true ]; then
    rollback_attempted=true
    if rollback_core; then
      rollback_succeeded=true
    else
      echo "RKE2 deployment rollback failed after the primary failure" >&2
    fi
  fi
  result_write_failed=false
  if [ "${result_recorded}" != true ]; then
    record_core_result \
      "${status}" \
      "${rollback_attempted}" \
      "${rollback_succeeded}" || result_write_failed=true
  fi
  if { [ "${rollback_attempted}" = true ] &&
    [ "${rollback_succeeded}" != true ]; } ||
    [ "${result_write_failed}" = true ]; then
    echo "RKE2 deployment transaction was retained for recovery evidence" >&2
  else
    rm -rf -- "${transaction_directory}"
  fi
  if [ "${result_write_failed}" = true ] && [ "${status}" -eq 0 ]; then
    echo "RKE2 deployment result could not be recorded" >&2
    status=70
  fi
  exit "${status}"
}

interrupted() {
  exit 130
}

trap cleanup EXIT
trap interrupted HUP INT TERM

snapshot_input() {
  source_path="$1"
  destination_name="$2"
  description="$3"
  shift 3
  python3 "${repository_root}/scripts/deploy/rke2/private_input.py" \
    snapshot-file \
    --source "${source_path}" \
    --destination "${transaction_directory}/${destination_name}" \
    --description "${description}" \
    "$@" >/dev/null || fail "${description} is invalid"
}

snapshot_input \
  "${kubeconfig}" \
  kubeconfig \
  kubeconfig
snapshot_input \
  "${values_file}" \
  core-values.json \
  "core release values" \
  --commit "${expected_commit}" \
  --snapshot-name core-values.json
snapshot_input \
  "${harbor_dockerconfig}" \
  dockerconfig.json \
  "Harbor dockerconfig"
snapshot_input \
  "${apps_tls_cert}" \
  apps-tls.crt \
  "Apps TLS certificate"
snapshot_input \
  "${oidc_ca}" \
  oidc-ca.crt \
  "OIDC CA"
if [ "${identity_mode}" = "bundledKeycloak" ]; then
  snapshot_input \
    "${identity_rendered_manifest}" \
    identity-rendered.yaml \
    "Identity rendered manifest" \
    --commit "${expected_commit}" \
    --snapshot-name identity-rendered.yaml
  identity_rendered_manifest="${transaction_directory}/identity-rendered.yaml"
fi
python3 "${repository_root}/scripts/deploy/rke2/private_input.py" \
  validate-directory \
  --path "${platform_artifacts}" \
  --description "platform installation artifacts" \
  --expected-relative-path "install-secrets/rke2/platform-artifacts" >/dev/null ||
  fail "platform installation artifacts are invalid"

kubeconfig="${transaction_directory}/kubeconfig"
values_file="${transaction_directory}/core-values.json"
harbor_dockerconfig="${transaction_directory}/dockerconfig.json"
apps_tls_cert="${transaction_directory}/apps-tls.crt"
oidc_ca="${transaction_directory}/oidc-ca.crt"
export KUBECONFIG="${kubeconfig}"

identity_release_inventory="${transaction_directory}/identity-release.json"
helm_target list \
  --all \
  --namespace aileron-identity-system \
  --filter '^aileron-identity$' \
  --output json >"${identity_release_inventory}" ||
  fail "Identity Helm release inventory is unavailable"
if [ "${identity_mode}" = "bundledKeycloak" ]; then
  jq -e '
    type == "array" and
    length == 1 and
    .[0].name == "aileron-identity" and
    .[0].status == "deployed"
  ' "${identity_release_inventory}" >/dev/null ||
    fail "bundled Identity Helm release is not deployed"
  live_identity_manifest="${transaction_directory}/identity-live.yaml"
  helm_target get manifest aileron-identity \
    --namespace aileron-identity-system >"${live_identity_manifest}" ||
    fail "live Identity manifest is unavailable"
  chmod 0600 "${live_identity_manifest}"
  python3 "${repository_root}/scripts/deploy/rke2/preflight_manifest.py" \
    assert-equivalent-manifests \
    "${identity_rendered_manifest}" \
    "${live_identity_manifest}" \
    --document-class release >/dev/null ||
    fail "live Identity manifest does not match the planned snapshot"
  live_identity_hooks="${transaction_directory}/identity-live-hooks.yaml"
  helm_target get hooks aileron-identity \
    --namespace aileron-identity-system >"${live_identity_hooks}" ||
    fail "live Identity hooks are unavailable"
  chmod 0600 "${live_identity_hooks}"
  python3 "${repository_root}/scripts/deploy/rke2/preflight_manifest.py" \
    assert-equivalent-manifests \
    "${identity_rendered_manifest}" \
    "${live_identity_hooks}" \
    --document-class hooks >/dev/null ||
    fail "live Identity hooks do not match the planned snapshot"
else
  jq -e 'type == "array" and length == 0' \
    "${identity_release_inventory}" >/dev/null ||
    fail "externalOidc mode must not retain a bundled Identity release"
fi

python3 "${repository_root}/scripts/deploy/rke2/wait_for_oidc.py" \
  --issuer-url "${oidc_issuer}" \
  --ca-file "${oidc_ca}" \
  --timeout-seconds 600 >/dev/null ||
  fail "OIDC discovery readiness failed"

IDENTITY_MODE="${identity_mode}" \
IDENTITY_RENDERED_MANIFEST="${identity_rendered_manifest}" \
  "${repository_root}/scripts/deploy/rke2/preflight.sh" \
  --commit "${expected_commit}" \
  --registry "${registry}" \
  --project "${project}" \
  --values "${values_file}" \
  --harbor-dockerconfig "${harbor_dockerconfig}" \
  --apps-tls-cert "${apps_tls_cert}" \
  --platform-artifacts "${platform_artifacts}" \
  --kubeconfig "${kubeconfig}" \
  --context "${context}" \
  --namespace "${namespace}" >/dev/null ||
  fail "full deployment preflight failed"

python3 "${repository_root}/scripts/deploy/rke2/ensure_installation_namespaces.py" \
  --kubeconfig "${kubeconfig}" \
  --context "${context}" \
  --identity-mode "${identity_mode}" >/dev/null ||
  fail "installation namespace reconciliation failed"

core_release_inventory="${transaction_directory}/core-release.json"
helm_target list \
  --all \
  --namespace "${namespace}" \
  --filter '^aileron$' \
  --output json >"${core_release_inventory}" ||
  fail "existing Helm release inventory is unavailable"
core_release_count="$(jq -er 'if type == "array" then length else error("shape") end' "${core_release_inventory}")" ||
  fail "existing Helm release inventory is invalid"
case "${core_release_count}" in
  0) ;;
  1)
    jq -e '.[0].name == "aileron"' "${core_release_inventory}" >/dev/null ||
      fail "existing Helm release inventory is invalid"
    core_release_history="${transaction_directory}/core-history.json"
    helm_target history aileron \
      --namespace "${namespace}" \
      --output json >"${core_release_history}" ||
      fail "existing Helm release history is unavailable"
    previous_revision="$(
      jq -er '[.[] | select(.status == "deployed") | (.revision | tonumber)] | max' \
        "${core_release_history}"
    )" || fail "existing Helm release has no rollback-safe deployed revision"
    ;;
  *) fail "existing Helm release inventory contains duplicate releases" ;;
esac

python3 "${repository_root}/scripts/deploy/rke2/installation_transaction.py" \
  prepare-crd-transaction \
  --transaction-directory "${transaction_directory}" \
  --context "${context}" >/dev/null 2>&1 ||
  fail "Workspace CRD pre-state snapshot failed"

rollback_required=true
kubectl_target apply \
  --server-side \
  --force-conflicts \
  --field-manager=aileron-deployer \
  -f helm/aileron/crds/platform.aileron.io_workspaces.yaml >/dev/null ||
  fail "Workspace CRD apply failed"

helm_mutation_started=true
helm_target upgrade --install aileron helm/aileron \
  --namespace "${namespace}" \
  --values helm/values-rke2-207-homelab.yaml \
  --values "${values_file}" \
  --skip-crds \
  --atomic \
  --wait \
  --timeout "${timeout}" \
  --history-max 10 ||
  fail "Core Helm release failed"

base_domain="${BASE_DOMAIN:-apps.rke.soez.tw}"
frontend_host="aileron.${base_domain}"
tls_work_dir="${transaction_directory}/tls"
mkdir -m 0700 "${tls_work_dir}"
helm_target get manifest aileron \
  --namespace "${namespace}" >"${tls_work_dir}/manifest.yaml" ||
  fail "deployed Core manifest is unavailable"
python3 "${repository_root}/scripts/deploy/rke2/preflight_manifest.py" \
  ingress-tls-secret \
  "${tls_work_dir}/manifest.yaml" \
  --default-namespace "${namespace}" \
  --host "${frontend_host}" >"${tls_work_dir}/secret-inventory" ||
  fail "frontend TLS inventory is invalid"
tab="$(printf '\t')"
IFS="${tab}" read -r tls_secret_namespace tls_secret extra_column \
  <"${tls_work_dir}/secret-inventory"
if [ -z "${tls_secret_namespace}" ] ||
  [ -z "${tls_secret}" ] ||
  [ -n "${extra_column}" ]; then
  fail "frontend TLS inventory is invalid"
fi
kubectl_target get secret "${tls_secret}" \
  --namespace "${tls_secret_namespace}" \
  -o jsonpath='{.data.tls\.crt}' |
  base64 -d >"${tls_work_dir}/expected.crt"
expected_fingerprint="$(
  openssl x509 -in "${tls_work_dir}/expected.crt" -noout -fingerprint -sha256
)" || fail "frontend TLS Secret is invalid"

frontend_addresses="$(
  getent ahostsv4 "${frontend_host}" |
    awk '{print $1}' |
    sort -u
)"
[ -n "${frontend_addresses}" ] || fail "frontend DNS is unavailable"

for frontend_address in ${frontend_addresses}; do
  openssl s_client \
    -connect "${frontend_address}:443" \
    -servername "${frontend_host}" \
    -verify_return_error \
    -showcerts \
    </dev/null >"${tls_work_dir}/client.log" 2>&1 ||
    fail "deployed frontend TLS verification failed"
  awk '
    /-----BEGIN CERTIFICATE-----/ { capture = 1 }
    capture { print }
    /-----END CERTIFICATE-----/ { exit }
  ' "${tls_work_dir}/client.log" >"${tls_work_dir}/served.crt"
  served_fingerprint="$(
    openssl x509 -in "${tls_work_dir}/served.crt" -noout -fingerprint -sha256
  )" || fail "deployed frontend certificate is invalid"
  [ "${served_fingerprint}" = "${expected_fingerprint}" ] ||
    fail "deployed frontend TLS certificate does not match its Secret"
done

record_core_result 0 false false ||
  fail "Core deployment result could not be recorded"
result_recorded=true
rollback_required=false
printf 'core-stage=passed\n'
printf 'commit=%s\n' "${expected_commit}"
