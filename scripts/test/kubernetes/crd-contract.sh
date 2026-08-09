#!/bin/sh

set -eu

action="${1:?action is required}"
crd_name="workspaces.platform.aileron.io"
manifest="${WORKSPACE_CRD_MANIFEST:?WORKSPACE_CRD_MANIFEST is required}"
artifact_dir="${WORKSPACE_CRD_ARTIFACT_DIR:?WORKSPACE_CRD_ARTIFACT_DIR is required}"
disposition_file="${artifact_dir}/workspace-crd-disposition.txt"
expected_contract="${artifact_dir}/workspace-crd-expected-contract.json"
observed_contract="${artifact_dir}/workspace-crd-observed-contract.json"

log() {
  printf '[workspace-crd-contract] %s\n' "$*" >&2
}

fail() {
  log "FAILED: $*"
  exit 1
}

kube() {
  if command -v kubectl >/dev/null 2>&1; then
    kubectl "$@"
    return
  fi
  if command -v k3s >/dev/null 2>&1; then
    k3s kubectl "$@"
    return
  fi
  fail "kubectl or k3s is required"
}

write_contract() {
  source_file="$1"
  destination="$2"
  jq -S '
    {
      group: .spec.group,
      scope: .spec.scope,
      names: {
        plural: .spec.names.plural,
        singular: .spec.names.singular,
        kind: .spec.names.kind,
        shortNames: (.spec.names.shortNames // [])
      },
      versions: [
        .spec.versions[] |
        {
          name,
          served,
          storage,
          schema,
          subresources: (.subresources // {}),
          additionalPrinterColumns: (.additionalPrinterColumns // [])
        }
      ]
    }
  ' "${source_file}" > "${destination}"
}

verify_contract() {
  expected_resource="${artifact_dir}/workspace-crd-expected-resource.json"
  observed_resource="${artifact_dir}/workspace-crd-observed-resource.json"

  kube create --dry-run=client -f "${manifest}" -o json > "${expected_resource}"
  kube get crd "${crd_name}" -o json > "${observed_resource}"
  write_contract "${expected_resource}" "${expected_contract}"
  write_contract "${observed_resource}" "${observed_contract}"
  rm -f "${expected_resource}" "${observed_resource}"

  if ! cmp -s "${expected_contract}" "${observed_contract}"; then
    diff -u "${expected_contract}" "${observed_contract}" >&2 || true
    fail "existing Workspace CRD does not match the exact required schema and versions"
  fi
}

ensure_crd() {
  command -v jq >/dev/null 2>&1 || fail "jq is required"
  [ -r "${manifest}" ] || fail "Workspace CRD manifest is not readable: ${manifest}"
  mkdir -p "${artifact_dir}"

  if kube get crd "${crd_name}" >/dev/null 2>&1; then
    printf 'preexisting\n' > "${disposition_file}"
    log "verifying the pre-existing Workspace CRD without mutating it"
  else
    log "installing the Workspace CRD on a fresh cluster"
    kube apply -f "${manifest}" >/dev/null
    printf 'created\n' > "${disposition_file}"
  fi

  kube wait --for=condition=Established \
    "crd/${crd_name}" --timeout=120s >/dev/null
  verify_contract
  log "Workspace CRD schema and versions match the required contract"
}

cleanup_crd() {
  [ -r "${disposition_file}" ] || return 0
  disposition="$(cat "${disposition_file}")"
  case "${disposition}" in
    preexisting)
      log "leaving the pre-existing Workspace CRD unchanged"
      ;;
    created)
      kube delete crd "${crd_name}" \
        --ignore-not-found --wait=false >/dev/null 2>&1
      ;;
    *)
      fail "invalid Workspace CRD disposition: ${disposition}"
      ;;
  esac
}

case "${action}" in
  ensure) ensure_crd ;;
  cleanup) cleanup_crd ;;
  *) fail "action must be ensure or cleanup" ;;
esac
