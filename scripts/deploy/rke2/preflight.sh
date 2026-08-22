#!/bin/sh

set -eu
umask 077

# shellcheck disable=SC1007
repository_root="$(CDPATH= cd -- "$(dirname -- "$0")/../../.." && pwd)"
cd "${repository_root}"

expected_commit=""
registry=""
project=""
values_file=""
harbor_dockerconfig=""
apps_tls_cert=""
platform_artifacts=""
kubeconfig="${KUBECONFIG:-/root/.kube/config}"
namespace="${NAMESPACE:-workspace-system}"
expected_context=""

usage() {
  echo "Usage: $0 --commit SHA --registry HOST --project NAME --values FILE --harbor-dockerconfig FILE --apps-tls-cert FILE --platform-artifacts DIR --context NAME [--kubeconfig FILE] [--namespace NAME]" >&2
  exit 2
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --commit) expected_commit="${2:-}"; shift 2 ;;
    --registry) registry="${2:-}"; shift 2 ;;
    --project) project="${2:-}"; shift 2 ;;
    --values) values_file="${2:-}"; shift 2 ;;
    --harbor-dockerconfig) harbor_dockerconfig="${2:-}"; shift 2 ;;
    --apps-tls-cert) apps_tls_cert="${2:-}"; shift 2 ;;
    --platform-artifacts) platform_artifacts="${2:-}"; shift 2 ;;
    --kubeconfig) kubeconfig="${2:-}"; shift 2 ;;
    --context) expected_context="${2:-}"; shift 2 ;;
    --namespace) namespace="${2:-}"; shift 2 ;;
    *) usage ;;
  esac
done

[ -n "${expected_commit}" ] || usage
[ -n "${registry}" ] || usage
[ -n "${project}" ] || usage
[ -n "${values_file}" ] || usage
[ -n "${harbor_dockerconfig}" ] || usage
[ -n "${apps_tls_cert}" ] || usage
[ -n "${platform_artifacts}" ] || usage
[ -n "${expected_context}" ] || usage
[ -f "${values_file}" ] || {
  echo "Deployment values file does not exist" >&2
  exit 1
}

fail() {
  echo "RKE2 deployment preflight failed: $*" >&2
  exit 1
}

kubectl_target() {
  kubectl --context "${expected_context}" "$@"
}

helm_target() {
  helm --kube-context "${expected_context}" "$@"
}

validate_private_path_ancestors() {
  artifact_path="$1"
  description="$2"
  current_path="$(dirname -- "${artifact_path}")"
  while [ "${current_path}" != "/" ]; do
    [ ! -L "${current_path}" ] ||
      fail "${description} path must not contain a symbolic link"
    [ -d "${current_path}" ] ||
      fail "${description} parent directory does not exist"
    current_path="$(dirname -- "${current_path}")"
  done
}

validate_private_artifact() {
  artifact_path="$1"
  description="$2"
  case "${artifact_path}" in
    /*) ;;
    *) fail "${description} path must be absolute" ;;
  esac
  validate_private_path_ancestors "${artifact_path}" "${description}"
  [ ! -L "${artifact_path}" ] ||
    fail "${description} must not be a symbolic link"
  [ -f "${artifact_path}" ] ||
    fail "${description} must be a regular file"
  [ "$(stat -c '%a' "${artifact_path}")" = "600" ] ||
    fail "${description} permissions must be 0600"
  [ -s "${artifact_path}" ] || fail "${description} must not be empty"
}

for command_name in dirname docker getent git helm jq kubectl openssl python3 realpath stat; do
  command -v "${command_name}" >/dev/null 2>&1 ||
    fail "required command is unavailable: ${command_name}"
done

if ! helm_version="$(helm version --template '{{.Version}}' 2>/dev/null)"; then
  fail "unable to determine the Helm client version"
fi
python3 "${repository_root}/scripts/deploy/rke2/helm_contract.py" \
  validate-version "${helm_version}" >/dev/null ||
  fail "Helm client must be a stable release >=3.13.0 and <4.0.0"
if ! helm_upgrade_help="$(helm_target upgrade --help 2>/dev/null)"; then
  fail "unable to inspect Helm upgrade capabilities"
fi
printf '%s\n' "${helm_upgrade_help}" | grep -Fq -- '--atomic' ||
  fail "Helm upgrade does not support --atomic"
printf '%s\n' "${helm_upgrade_help}" | grep -Fq -- '--history-max' ||
  fail "Helm upgrade does not support --history-max"
printf '%s\n' "${helm_upgrade_help}" | grep -Fq -- '--dry-run' ||
  fail "Helm upgrade does not support --dry-run"
printf '%s\n' "${helm_upgrade_help}" | grep -Fq 'server' ||
  fail "Helm upgrade does not support server-side dry-run"
if ! helm_rollback_help="$(helm_target rollback --help 2>/dev/null)"; then
  fail "unable to inspect Helm rollback capabilities"
fi
printf '%s\n' "${helm_rollback_help}" | grep -Fq -- '--cleanup-on-fail' ||
  fail "Helm rollback does not support --cleanup-on-fail"

printf '%s' "${expected_commit}" | grep -Eq '^[0-9a-f]{40}$' ||
  fail "--commit must be a full lowercase Git SHA"
printf '%s' "${registry}" |
  grep -Eq '^[a-z0-9][a-z0-9.-]*(:[0-9]{1,5})?$' ||
  fail "--registry must be a hostname with an optional port"
printf '%s' "${project}" |
  grep -Eq '^[a-z0-9]+([._-][a-z0-9]+)*$' ||
  fail "--project is not a valid lowercase Harbor project name"

[ "$(uname -m)" = "x86_64" ] || fail "build/deployment host must be amd64"
[ -z "$(git status --porcelain)" ] || fail "Git checkout must be clean"
actual_commit="$(git rev-parse --verify HEAD)"
[ "${actual_commit}" = "${expected_commit}" ] ||
  fail "Git HEAD does not match --commit"
docker buildx version >/dev/null 2>&1 || fail "Docker buildx is unavailable"
available_kib="$(df -Pk "${repository_root}" | awk 'NR == 2 { print $4 }')"
[ "${available_kib}" -ge "${MIN_FREE_DISK_KIB:-20971520}" ] ||
  fail "deployment host has less than the required free disk space"

values_file="$(realpath "${values_file}")"
[ "$(stat -c '%a' "${values_file}")" = "600" ] ||
  fail "deployment values permissions must be 0600"
harbor_dockerconfig="$(realpath "${harbor_dockerconfig}")"
[ "$(stat -c '%a' "${harbor_dockerconfig}")" = "600" ] ||
  fail "Harbor dockerconfig permissions must be 0600"
apps_tls_cert="$(realpath "${apps_tls_cert}")"
[ "$(stat -c '%a' "${apps_tls_cert}")" = "600" ] ||
  fail "Apps TLS certificate permissions must be 0600"
case "${platform_artifacts}" in
  /*) ;;
  *) fail "Platform artifact directory path must be absolute" ;;
esac
validate_private_path_ancestors "${platform_artifacts}" \
  "Platform artifact directory"
[ ! -L "${platform_artifacts}" ] ||
  fail "Platform artifact directory must not be a symbolic link"
[ -d "${platform_artifacts}" ] ||
  fail "Platform artifact directory must be a directory"
[ "$(stat -c '%a' "${platform_artifacts}")" = "700" ] ||
  fail "Platform artifact directory permissions must be 0700"
case "${values_file}" in
  "${repository_root}"/*)
    relative_values="${values_file#"${repository_root}/"}"
    if git ls-files --error-unmatch -- "${relative_values}" >/dev/null 2>&1; then
      fail "deployment values containing secrets must not be tracked by Git"
    fi
    fail "deployment values containing secrets must be outside the Git checkout"
    ;;
esac

[ -f "${kubeconfig}" ] || fail "kubeconfig does not exist"
[ "$(stat -c '%a' "${kubeconfig}")" = "600" ] ||
  fail "kubeconfig permissions must be 0600"
export KUBECONFIG="${kubeconfig}"
current_context="$(kubectl_target config current-context)"
[ -n "${current_context}" ] || fail "kubeconfig has no current context"
[ "${current_context}" = "${expected_context}" ] ||
  fail "kubeconfig current context does not match --context"
kubectl_target cluster-info >/dev/null 2>&1 || fail "target cluster is unavailable"

ready_amd64_workers="$(
  kubectl_target get nodes -o json |
    jq -r '[
      .items[]
      | select(.metadata.labels."kubernetes.io/arch" == "amd64")
      | select((.spec.unschedulable // false) == false)
      | select(
          [.status.conditions[]
           | select(.type == "Ready" and .status == "True")]
          | length == 1
        )
    ] | length'
)"
[ "${ready_amd64_workers}" -ge "${MIN_AMD64_WORKERS:-3}" ] ||
  fail "not enough schedulable Ready amd64 nodes"

kubectl_target get crd ciliumnetworkpolicies.cilium.io >/dev/null 2>&1 ||
  fail "CiliumNetworkPolicy CRD is unavailable"
kubectl_target get ingressclass "${INGRESS_CLASS:-nginx}" >/dev/null 2>&1 ||
  fail "required IngressClass is unavailable"
kubectl_target get namespace "${namespace}" >/dev/null 2>&1 ||
  fail "release namespace must exist before deployment"

work_dir="$(mktemp -d)"
trap 'rm -rf "${work_dir}"' EXIT
trap 'exit 130' HUP INT TERM
chmod 0700 "${work_dir}"
docker_config_directory="${work_dir}/docker"
install -d -m 0700 "${docker_config_directory}"
install -m 0600 "${harbor_dockerconfig}" "${docker_config_directory}/config.json"
rendered="${work_dir}/rendered.yaml"
: > "${rendered}"
chmod 0600 "${rendered}"
core_release_inventory="${work_dir}/core-release-inventory.json"
if ! helm_target list \
  --all \
  --namespace "${namespace}" \
  --filter '^aileron$' \
  --max 2 \
  --output json > "${core_release_inventory}"; then
  fail "unable to inspect the existing Core Helm release"
fi
chmod 0600 "${core_release_inventory}"
if ! core_deployment_mode="$(
  python3 "${repository_root}/scripts/deploy/rke2/helm_contract.py" \
    release-mode "${core_release_inventory}" \
    --namespace "${namespace}" \
    --release aileron
)"; then
  fail "existing Core Helm release inventory is invalid"
fi

helm lint helm/aileron \
  --namespace "${namespace}" \
  --values helm/values-rke2-207-homelab.yaml \
  --values "${values_file}" >/dev/null
helm template aileron helm/aileron \
  --namespace "${namespace}" \
  --include-crds \
  --values helm/values-rke2-207-homelab.yaml \
  --values "${values_file}" > "${rendered}"

image_pull_secrets_file="${work_dir}/image-pull-secrets"
if ! python3 "${repository_root}/scripts/deploy/rke2/preflight_manifest.py" \
  image-pull-secrets \
  "${rendered}" \
  --default-namespace "${namespace}" > "${image_pull_secrets_file}"; then
  fail "rendered image pull Secret inventory is invalid"
fi
[ -s "${image_pull_secrets_file}" ] ||
  fail "rendered workloads do not declare an image pull Secret"

tab="$(printf '\t')"
image_pull_secret_count=0
while IFS="${tab}" read -r workload_namespace image_pull_secret extra_column; do
  if [ -z "${workload_namespace}" ] ||
    [ -z "${image_pull_secret}" ] ||
    [ -n "${extra_column}" ]; then
    fail "rendered image pull Secret inventory row is malformed"
  fi
  image_pull_secret_count=$((image_pull_secret_count + 1))

  [ "${image_pull_secret}" = "harbor-rke-creds" ] ||
    fail "rendered workload uses an unexpected image pull Secret"
  planned_image_pull_secret="${work_dir}/image-pull-secret-${image_pull_secret_count}.json"
  jq -n \
    --arg namespace "${workload_namespace}" \
    --arg name "${image_pull_secret}" \
    --rawfile dockerconfig "${harbor_dockerconfig}" \
    '{
      apiVersion: "v1",
      kind: "Secret",
      metadata: {namespace: $namespace, name: $name},
      type: "kubernetes.io/dockerconfigjson",
      data: {".dockerconfigjson": ($dockerconfig | @base64)}
    }' > "${planned_image_pull_secret}"
  chmod 0600 "${planned_image_pull_secret}"
  if ! registry_auth="$(
    python3 "${repository_root}/scripts/deploy/rke2/preflight_manifest.py" \
      validate-image-pull-secret \
      "${planned_image_pull_secret}" \
      --namespace "${workload_namespace}" \
      --name "${image_pull_secret}" \
      --registry "${registry}" 2>/dev/null
  )"; then
    fail "rendered image pull Secret has an invalid Kubernetes or Docker config contract: ${workload_namespace}/${image_pull_secret}"
  fi
  case "${registry_auth}" in
    true) ;;
    false)
      fail "rendered image pull Secret lacks approved registry credentials: ${workload_namespace}/${image_pull_secret}"
      ;;
    *)
      fail "image pull Secret validator returned an invalid result"
      ;;
  esac
done < "${image_pull_secrets_file}"

[ "${image_pull_secret_count}" -gt 0 ] ||
  fail "rendered workloads do not declare an image pull Secret"

if grep -Fq 'apps.soez.tw' "${rendered}"; then
  fail "rendered manifests contain the retired apps.soez.tw domain"
fi

turn_namespace="aileron-turn-system"
turn_namespace_manifest="${work_dir}/turn-namespace.json"
if ! kubectl_target get namespace "${turn_namespace}" -o json > "${turn_namespace_manifest}"; then
  fail "unable to inspect the installation-owned TURN namespace"
fi
chmod 0600 "${turn_namespace_manifest}"
python3 "${repository_root}/scripts/deploy/rke2/preflight_manifest.py" \
  validate-privileged-namespace "${turn_namespace_manifest}" \
  --namespace "${turn_namespace}" \
  --owner-marker "aileron-installer" >/dev/null ||
  fail "TURN namespace ownership or privileged PSA contract is invalid"

backend_attestor_namespace="aileron-backend-attestor-system"
backend_attestor_namespace_manifest="${work_dir}/backend-attestor-namespace.json"
if ! kubectl_target get namespace "${backend_attestor_namespace}" -o json \
  > "${backend_attestor_namespace_manifest}"; then
  fail "unable to inspect the retained backend-attestor namespace"
fi
chmod 0600 "${backend_attestor_namespace_manifest}"
python3 "${repository_root}/scripts/deploy/rke2/preflight_manifest.py" \
  validate-privileged-namespace "${backend_attestor_namespace_manifest}" \
  --namespace "${backend_attestor_namespace}" \
  --owner-marker "aileron-installer" >/dev/null ||
  fail "backend-attestor namespace ownership or privileged PSA contract is invalid"
python3 "${repository_root}/scripts/deploy/rke2/preflight_manifest.py" \
  validate-network-security "${rendered}" \
  --additional-manifest "${turn_namespace_manifest}" \
  --additional-manifest "${backend_attestor_namespace_manifest}" >/dev/null ||
  fail "rendered manifests contain an unauthorized hostNetwork workload"
python3 "${repository_root}/scripts/deploy/rke2/preflight_manifest.py" \
  validate-firewall-attestor "${rendered}" >/dev/null ||
  fail "rendered firewall attestor contract is invalid"

nodes_file="${work_dir}/nodes.json"
pods_file="${work_dir}/pods.json"
kubectl_target get nodes -o json > "${nodes_file}" ||
  fail "unable to inspect node allocatable resources"
kubectl_target get pods --all-namespaces -o json > "${pods_file}" ||
  fail "unable to inspect current Pod resource requests"
if ! execution_plane_capacity="$(
  python3 "${repository_root}/scripts/deploy/rke2/preflight_manifest.py" \
    validate-execution-plane-capacity \
    "${rendered}" \
    "${nodes_file}" \
    "${pods_file}" \
    --default-namespace "${namespace}" \
    --deployment-mode "${core_deployment_mode}" 2>&1
)"; then
  fail "${execution_plane_capacity}"
fi

base_domain="${BASE_DOMAIN:-apps.rke.soez.tw}"
frontend_host="aileron.${base_domain}"
grep -Fq "${frontend_host}" "${rendered}" ||
  fail "rendered frontend host does not match the required base domain"

images_file="${work_dir}/workload-images.tsv"
identity_mode="${IDENTITY_MODE:-}"
identity_rendered_manifest="${IDENTITY_RENDERED_MANIFEST:-}"
case "${identity_mode}" in
  bundledKeycloak)
    [ -n "${identity_rendered_manifest}" ] ||
      fail "IDENTITY_RENDERED_MANIFEST is required in bundledKeycloak mode"
    [ -f "${identity_rendered_manifest}" ] ||
      fail "IDENTITY_RENDERED_MANIFEST does not exist"
    python3 "${repository_root}/scripts/deploy/rke2/preflight_manifest.py" \
      named-images "${rendered}" \
      --identity-mode "${identity_mode}" \
      --additional-manifest "${identity_rendered_manifest}" > "${images_file}"
    ;;
  externalOidc)
    [ -z "${identity_rendered_manifest}" ] ||
      fail "IDENTITY_RENDERED_MANIFEST must be absent in externalOidc mode"
    python3 "${repository_root}/scripts/deploy/rke2/preflight_manifest.py" \
      named-images "${rendered}" \
      --identity-mode "${identity_mode}" > "${images_file}"
    ;;
  *)
    fail "IDENTITY_MODE must be bundledKeycloak or externalOidc"
    ;;
esac
image_count="$(wc -l < "${images_file}" | tr -d '[:space:]')"

while IFS="${tab}" read -r component image extra_column; do
  [ -n "${component}" ] && [ -n "${image}" ] && [ -z "${extra_column}" ] ||
    fail "rendered named workload image inventory row is malformed"
  case "${image}" in
    "${registry}/${project}/"*) ;;
    *) fail "image is not an approved immutable Harbor reference: ${image}" ;;
  esac
  printf '%s\n' "${image}" | grep -Eq '@sha256:[0-9a-f]{64}$' ||
    fail "image is not an approved immutable Harbor reference: ${image}"

  docker --config "${docker_config_directory}" pull \
    --platform linux/amd64 "${image}" >/dev/null
  inspection="$(
    docker --config "${docker_config_directory}" image inspect "${image}" \
      --format '{{.Os}}|{{.Architecture}}|{{.Config.User}}|{{index .Config.Labels "org.opencontainers.image.revision"}}'
  )"
  image_os="$(printf '%s' "${inspection}" | cut -d '|' -f 1)"
  image_arch="$(printf '%s' "${inspection}" | cut -d '|' -f 2)"
  image_user="$(printf '%s' "${inspection}" | cut -d '|' -f 3)"
  image_revision="$(printf '%s' "${inspection}" | cut -d '|' -f 4)"
  [ "${image_os}" = "linux" ] || fail "image OS is not linux: ${image}"
  [ "${image_arch}" = "amd64" ] || fail "image architecture is not amd64: ${image}"
  printf '%s' "${image_user}" | grep -Eq '^[0-9]+(:[0-9]+)?$' ||
    fail "image user is not numeric: ${image}"
  [ "${image_user%%:*}" -ne 0 ] || fail "image user is root: ${image}"
  [ "${image_revision}" = "${expected_commit}" ] ||
    fail "image revision label does not match Git commit: ${image}"
done < "${images_file}"

tls_secret_inventory="${work_dir}/frontend-tls-secret"
if ! python3 "${repository_root}/scripts/deploy/rke2/preflight_manifest.py" \
  ingress-tls-secret \
  "${rendered}" \
  --default-namespace "${namespace}" \
  --host "${frontend_host}" > "${tls_secret_inventory}"; then
  fail "rendered frontend Ingress TLS Secret inventory is invalid"
fi
[ "$(wc -l < "${tls_secret_inventory}" | tr -d ' ')" -eq 1 ] ||
  fail "rendered frontend Ingress TLS Secret inventory is malformed"
IFS="${tab}" read -r tls_secret_namespace tls_secret extra_column \
  < "${tls_secret_inventory}"
if [ -z "${tls_secret_namespace}" ] ||
  [ -z "${tls_secret}" ] ||
  [ -n "${extra_column}" ]; then
  fail "rendered frontend Ingress TLS Secret inventory row is malformed"
fi
[ "${tls_secret_namespace}" = "${namespace}" ] ||
  fail "rendered frontend Ingress TLS Secret namespace is invalid"
[ "${tls_secret}" = "aileron-apps-tls" ] ||
  fail "rendered frontend Ingress TLS Secret name is invalid"
tls_crt="${work_dir}/tls.crt"
install -m 0600 "${apps_tls_cert}" "${tls_crt}"
[ -s "${tls_crt}" ] || fail "TLS Secret is missing tls.crt"
openssl x509 -in "${tls_crt}" -noout -checkend "${TLS_MIN_VALID_SECONDS:-86400}" >/dev/null ||
  fail "TLS certificate is expired or expires too soon"
openssl x509 -in "${tls_crt}" -noout -ext subjectAltName |
  grep -Fq "DNS:*.${base_domain}" ||
  fail "TLS certificate SAN does not cover the wildcard base domain"

getent ahostsv4 "${frontend_host}" >/dev/null 2>&1 ||
  fail "frontend DNS does not resolve"
getent ahostsv4 "workspace-browser-preflight.${base_domain}" >/dev/null 2>&1 ||
  fail "wildcard Workspace DNS does not resolve"

turn_provider="$(
  python3 "${repository_root}/scripts/deploy/rke2/preflight_manifest.py" \
    turn-provider "${rendered}"
)"
if [ "${turn_provider}" = "builtin" ]; then
  turn_host="$(
    python3 "${repository_root}/scripts/deploy/rke2/preflight_manifest.py" \
      turn-server-host "${rendered}"
  )"
  turn_addresses="$(
    getent ahostsv4 "${turn_host}" |
      awk '{print $1}' |
      sort -u
  )"
  [ -n "${turn_addresses}" ] ||
    fail "built-in TURN DNS does not resolve"
  node_addresses="$(
    kubectl_target get nodes -o json |
      jq -r '.items[].status.addresses[] | select(.type == "InternalIP") | .address' |
      sort -u
  )"
  for address in ${turn_addresses}; do
    printf '%s\n' "${node_addresses}" | grep -Fxq "${address}" ||
      fail "built-in TURN DNS must resolve only to RKE node addresses"
  done
elif [ "${turn_provider}" = "external" ]; then
  validate_private_artifact \
    "${platform_artifacts}/turn/backend-ice-servers-json" \
    "Planned backend TURN ICE servers artifact"
  validate_private_artifact \
    "${platform_artifacts}/turn/frontend-ice-servers-json" \
    "Planned frontend TURN ICE servers artifact"
  [ -n "${TURN_PREFLIGHT_SCRIPT:-}" ] ||
    fail "TURN_PREFLIGHT_SCRIPT is required when external TURN is enabled"
  [ -x "${TURN_PREFLIGHT_SCRIPT}" ] ||
    fail "TURN_PREFLIGHT_SCRIPT is not executable"
  "${TURN_PREFLIGHT_SCRIPT}"
fi

kubectl_target apply \
  --server-side \
  --force-conflicts \
  --field-manager=aileron-deployer \
  --dry-run=server \
  -f helm/aileron/crds/platform.aileron.io_workspaces.yaml >/dev/null
helm_target upgrade --install aileron helm/aileron \
  --namespace "${namespace}" \
  --values helm/values-rke2-207-homelab.yaml \
  --values "${values_file}" \
  --skip-crds \
  --dry-run=server >/dev/null
"${repository_root}/scripts/deploy/rke2/preflight-storage.sh" \
  --context "${expected_context}" >/dev/null

evidence_root="${EVIDENCE_ROOT:-/var/lib/aileron/deployment-evidence}"
timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
evidence_dir="${evidence_root}/${expected_commit}-${timestamp}"
install -d -m 0700 "${evidence_dir}"
{
  printf 'commit=%s\n' "${expected_commit}"
  printf 'context=%s\n' "${current_context}"
  printf 'namespace=%s\n' "${namespace}"
  printf 'ready_amd64_workers=%s\n' "${ready_amd64_workers}"
  printf 'image_count=%s\n' "${image_count}"
  printf 'base_domain=%s\n' "${base_domain}"
  printf 'helm_version=%s\n' "${helm_version}"
  printf 'core_deployment_mode=%s\n' "${core_deployment_mode}"
  printf 'execution_plane_capacity=%s\n' "${execution_plane_capacity}"
  printf 'storage=passed\n'
  printf 'server_dry_run=passed\n'
} > "${evidence_dir}/preflight-summary.txt"
chmod 0600 "${evidence_dir}/preflight-summary.txt"
install -m 0600 "${images_file}" "${evidence_dir}/workload-images.tsv"

printf 'preflight=passed\n'
printf 'evidence=%s\n' "${evidence_dir}"
