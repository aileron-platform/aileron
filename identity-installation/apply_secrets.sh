#!/bin/sh

set -eu

artifact_dir=
private_root=
cluster_context=
kubeconfig=
namespace=
expected_namespace_uid=
transaction_directory=
transaction_commit=
dry_run=false
image_pull_secret_file=
tls_cert_file=
tls_key_file=
values_file=
postgres_username_file=
postgres_password_file=
postgres_ca_file=

while test "$#" -gt 0; do
  case "$1" in
    --artifact-dir) artifact_dir=$2; shift 2 ;;
    --private-root) private_root=$2; shift 2 ;;
    --context) cluster_context=$2; shift 2 ;;
    --kubeconfig) kubeconfig=$2; shift 2 ;;
    --namespace) namespace=$2; shift 2 ;;
    --expected-namespace-uid) expected_namespace_uid=$2; shift 2 ;;
    --transaction-directory) transaction_directory=$2; shift 2 ;;
    --transaction-commit) transaction_commit=$2; shift 2 ;;
    --image-pull-secret-file) image_pull_secret_file=$2; shift 2 ;;
    --tls-cert-file) tls_cert_file=$2; shift 2 ;;
    --tls-key-file) tls_key_file=$2; shift 2 ;;
    --values) values_file=$2; shift 2 ;;
    --postgres-username-file) postgres_username_file=$2; shift 2 ;;
    --postgres-password-file) postgres_password_file=$2; shift 2 ;;
    --postgres-ca-file) postgres_ca_file=$2; shift 2 ;;
    --dry-run) dry_run=true; shift ;;
    *) printf 'Unknown argument: %s\n' "$1" >&2; exit 2 ;;
  esac
done

test -n "${artifact_dir}" || { printf '%s\n' '--artifact-dir is required' >&2; exit 2; }
test -n "${private_root}" || { printf '%s\n' '--private-root is required' >&2; exit 2; }
test -n "${cluster_context}" || { printf '%s\n' '--context is required' >&2; exit 2; }
test -n "${kubeconfig}" || { printf '%s\n' '--kubeconfig is required' >&2; exit 2; }
test -n "${namespace}" || { printf '%s\n' '--namespace is required' >&2; exit 2; }
test -n "${expected_namespace_uid}" || { printf '%s\n' '--expected-namespace-uid is required' >&2; exit 2; }
test -n "${image_pull_secret_file}" || { printf '%s\n' '--image-pull-secret-file is required' >&2; exit 2; }
test -n "${tls_cert_file}" || { printf '%s\n' '--tls-cert-file is required' >&2; exit 2; }
test -n "${tls_key_file}" || { printf '%s\n' '--tls-key-file is required' >&2; exit 2; }
test -n "${values_file}" || { printf '%s\n' '--values is required' >&2; exit 2; }
if test "${dry_run}" = false; then
  test -n "${transaction_directory}" || { printf '%s\n' '--transaction-directory is required for apply' >&2; exit 2; }
  test -n "${transaction_commit}" || { printf '%s\n' '--transaction-commit is required for apply' >&2; exit 2; }
elif test -n "${transaction_directory}${transaction_commit}"; then
  printf '%s\n' 'Secret transaction arguments are forbidden for dry-run' >&2
  exit 2
fi

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
namespace_validator="${script_dir}/../scripts/deploy/rke2/namespace_contract.py"
transaction_recorder="${script_dir}/../scripts/deploy/rke2/installation_transaction.py"
temporary_dir=$(mktemp -d "${private_root}/.identity-secrets.XXXXXXXX")
chmod 0700 "${temporary_dir}"
cleanup() {
  rm -rf -- "${temporary_dir}"
}
trap cleanup EXIT INT TERM

postgres_enabled=$(python3 - "${values_file}" <<'PY'
import json
import sys
from pathlib import Path

try:
    enabled = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))["postgres"]["enabled"]
except (OSError, UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError):
    raise SystemExit("Identity values are invalid")
if not isinstance(enabled, bool):
    raise SystemExit("Identity values postgres.enabled is invalid")
print("true" if enabled else "false")
PY
)
if test "${postgres_enabled}" = false; then
  test -n "${postgres_username_file}" || { printf '%s\n' '--postgres-username-file is required for external Identity PostgreSQL' >&2; exit 2; }
  test -n "${postgres_password_file}" || { printf '%s\n' '--postgres-password-file is required for external Identity PostgreSQL' >&2; exit 2; }
  test -n "${postgres_ca_file}" || { printf '%s\n' '--postgres-ca-file is required for external Identity PostgreSQL' >&2; exit 2; }
  test -s "${postgres_username_file}" || { printf '%s\n' 'external Identity PostgreSQL username is empty' >&2; exit 2; }
  test -s "${postgres_password_file}" || { printf '%s\n' 'external Identity PostgreSQL password is empty' >&2; exit 2; }
  openssl x509 -in "${postgres_ca_file}" -noout >/dev/null 2>&1 || {
    printf '%s\n' 'external Identity PostgreSQL CA is invalid' >&2
    exit 2
  }
elif test -n "${postgres_username_file}${postgres_password_file}${postgres_ca_file}"; then
  printf '%s\n' 'external Identity PostgreSQL inputs are forbidden in bundled mode' >&2
  exit 2
fi

python3 "${script_dir}/generate_secrets.py" \
  --private-root "${private_root}" \
  --output-dir "${artifact_dir}" \
  --values "${values_file}" \
  --validate-only >/dev/null
if test "${postgres_enabled}" = true; then
  python3 "${script_dir}/copy_private_inputs.py" \
    --private-root "${private_root}" \
    --destination-dir "${temporary_dir}" \
    --image-pull-secret "${image_pull_secret_file}" \
    --tls-certificate "${tls_cert_file}" \
    --tls-private-key "${tls_key_file}"
else
  python3 "${script_dir}/copy_private_inputs.py" \
    --private-root "${private_root}" \
    --destination-dir "${temporary_dir}" \
    --image-pull-secret "${image_pull_secret_file}" \
    --tls-certificate "${tls_cert_file}" \
    --tls-private-key "${tls_key_file}" \
    --postgres-username "${postgres_username_file}" \
    --postgres-password "${postgres_password_file}" \
    --postgres-ca "${postgres_ca_file}"
fi
image_pull_secret_file="${temporary_dir}/dockerconfig.json"
tls_cert_file="${temporary_dir}/tls.crt"
tls_key_file="${temporary_dir}/tls.key"
python3 - "${image_pull_secret_file}" <<'PY' || {
import json
import sys
from pathlib import Path

try:
    document = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    auths = document["auths"]
    valid = isinstance(auths, dict) and bool(auths)
    valid = valid and all(isinstance(registry, str) and registry and isinstance(credentials, dict) for registry, credentials in auths.items())
except (KeyError, OSError, UnicodeDecodeError, json.JSONDecodeError):
    valid = False
raise SystemExit(0 if valid else 1)
PY
  printf 'Harbor image pull input must be JSON with non-empty auths\n' >&2
  exit 1
}
command -v openssl >/dev/null 2>&1 || {
  printf 'openssl is required to validate Identity TLS inputs\n' >&2
  exit 1
}
openssl x509 -in "${tls_cert_file}" -noout >/dev/null 2>&1 || {
  printf 'Identity TLS certificate is invalid\n' >&2
  exit 1
}
openssl pkey -in "${tls_key_file}" -noout >/dev/null 2>&1 || {
  printf 'Identity TLS private key is invalid\n' >&2
  exit 1
}
certificate_public_key=$(openssl x509 -in "${tls_cert_file}" -pubkey -noout 2>/dev/null | \
  openssl pkey -pubin -outform DER 2>/dev/null | openssl dgst -sha256)
private_public_key=$(openssl pkey -in "${tls_key_file}" -pubout 2>/dev/null | \
  openssl pkey -pubin -outform DER 2>/dev/null | openssl dgst -sha256)
test -n "${certificate_public_key}" && test "${certificate_public_key}" = "${private_public_key}" || {
  printf 'Identity TLS certificate and private key do not match\n' >&2
  exit 1
}
validate_namespace_identity() {
  python3 "${namespace_validator}" validate \
    --kubeconfig "${kubeconfig}" \
    --context "${cluster_context}" \
    --namespace "${namespace}" \
    --expected-uid "${expected_namespace_uid}" || {
    printf 'Identity namespace identity changed: %s\n' "${namespace}" >&2
    exit 1
  }
}
validate_namespace_identity

apply_secret() {
  secret_name=$1
  shift
  validate_namespace_identity
  owner_label='platform.aileron.dev/secret-owner=aileron-installer'
  lookup_error="${temporary_dir}/${secret_name}.lookup-error"
  if existing_owner=$(kubectl --kubeconfig "${kubeconfig}" --context "${cluster_context}" --namespace "${namespace}" get secret "${secret_name}" \
    -o 'jsonpath={.metadata.labels.platform\.aileron\.dev/secret-owner}' 2>"${lookup_error}"); then
    test "${existing_owner}" = aileron-installer || {
      printf 'Identity Secret is owned by another installer: %s\n' "${secret_name}" >&2
      exit 1
    }
  elif ! grep -Eq '^Error from server \(NotFound\): .*not found$' "${lookup_error}"; then
    printf 'Identity Secret ownership lookup failed: %s\n' "${secret_name}" >&2
    sed -n '1,3p' "${lookup_error}" >&2
    exit 1
  fi
  rm -f -- "${lookup_error}"
  raw_manifest="${temporary_dir}/${secret_name}.raw.json"
  manifest="${temporary_dir}/${secret_name}.json"
  umask 077
  kubectl --kubeconfig "${kubeconfig}" --context "${cluster_context}" --namespace "${namespace}" create secret generic "${secret_name}" \
    "$@" --dry-run=client -o json >"${raw_manifest}"
  chmod 0600 "${raw_manifest}"
  kubectl --kubeconfig "${kubeconfig}" --context "${cluster_context}" --namespace "${namespace}" label --local -f "${raw_manifest}" \
    "${owner_label}" app.kubernetes.io/managed-by=aileron-installer \
    app.kubernetes.io/part-of=aileron-identity --overwrite -o json >"${manifest}"
  chmod 0600 "${manifest}"
  rm -f -- "${raw_manifest}"
  validate_namespace_identity
  kubectl --kubeconfig "${kubeconfig}" --context "${cluster_context}" --namespace "${namespace}" apply \
    --server-side --dry-run=server --field-manager=aileron-identity-installer -f "${manifest}" >/dev/null
  if test "${dry_run}" = false; then
    validate_namespace_identity
    mutation_binding="${temporary_dir}/${secret_name}.mutation.json"
    python3 "${transaction_recorder}" prepare-secret-mutation \
      --transaction-directory "${transaction_directory}" \
      --commit "${transaction_commit}" \
      --context "${cluster_context}" \
      --kubeconfig "${kubeconfig}" \
      --identity-mode bundledKeycloak \
      --namespace "${namespace}" \
      --name "${secret_name}" \
      --manifest "${manifest}" >"${mutation_binding}"
    chmod 0600 "${mutation_binding}"
    mutation_state=$(python3 - "${mutation_binding}" <<'PY'
import json
import re
import sys
from pathlib import Path

document = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
marker = document.get("transactionMarker") if isinstance(document, dict) else None
if not isinstance(marker, str) or re.fullmatch(r"[0-9a-f]{64}", marker) is None:
    raise SystemExit("Secret mutation binding is invalid")
if set(document) == {"state", "transactionMarker"} and document.get("state") == "absent":
    print("absent")
elif (
    isinstance(document, dict)
    and set(document) == {"state", "uid", "resourceVersion", "transactionMarker"}
    and document.get("state") == "existing"
    and all(isinstance(document.get(key), str) and document[key] for key in ("uid", "resourceVersion"))
):
    print("existing")
else:
    raise SystemExit("Secret mutation binding is invalid")
PY
    )
    mutation_manifest="${temporary_dir}/${secret_name}.mutation-manifest.json"
    python3 - "${mutation_binding}" "${manifest}" <<'PY' >"${mutation_manifest}"
import json
import sys
from pathlib import Path

marker_annotation = "platform.aileron.dev/installation-transaction-marker"
binding = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
document = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
metadata = document["metadata"]
annotations = metadata.setdefault("annotations", {})
if marker_annotation in annotations:
    raise SystemExit("Secret manifest uses a reserved annotation")
annotations[marker_annotation] = binding["transactionMarker"]
if binding["state"] == "existing":
    metadata["uid"] = binding["uid"]
    metadata["resourceVersion"] = binding["resourceVersion"]
print(json.dumps(document, separators=(",", ":"), sort_keys=True))
PY
    chmod 0600 "${mutation_manifest}"
    if test "${mutation_state}" = absent; then
      kubectl --kubeconfig "${kubeconfig}" --context "${cluster_context}" --namespace "${namespace}" create \
        --dry-run=server --filename "${mutation_manifest}" >/dev/null
    else
      kubectl --kubeconfig "${kubeconfig}" --context "${cluster_context}" --namespace "${namespace}" replace \
        --dry-run=server --filename "${mutation_manifest}" >/dev/null
    fi
    validate_namespace_identity
    if test "${mutation_state}" = absent; then
      kubectl --kubeconfig "${kubeconfig}" --context "${cluster_context}" --namespace "${namespace}" create \
        --filename "${mutation_manifest}" >/dev/null
    else
      kubectl --kubeconfig "${kubeconfig}" --context "${cluster_context}" --namespace "${namespace}" replace \
        --filename "${mutation_manifest}" >/dev/null
    fi
    python3 "${transaction_recorder}" record-secret-post-state \
      --transaction-directory "${transaction_directory}" \
      --commit "${transaction_commit}" \
      --context "${cluster_context}" \
      --kubeconfig "${kubeconfig}" \
      --identity-mode bundledKeycloak \
      --namespace "${namespace}" \
      --name "${secret_name}" \
      --manifest "${manifest}"
  fi
}

if test "${postgres_enabled}" = true; then
  postgres_username_source="${artifact_dir}/identity-postgres/username"
  postgres_password_source="${artifact_dir}/identity-postgres/password"
else
  postgres_username_source="${temporary_dir}/postgres-username"
  postgres_password_source="${temporary_dir}/postgres-password"
fi
apply_secret identity-postgres \
  --type=Opaque \
  --from-file="username=${postgres_username_source}" \
  --from-file="password=${postgres_password_source}"
if test "${postgres_enabled}" = false; then
  apply_secret aileron-identity-database-ca \
    --type=Opaque \
    --from-file="ca.crt=${temporary_dir}/postgres-ca.crt"
fi
apply_secret keycloak-bootstrap-admin \
  --type=Opaque \
  --from-file="username=${artifact_dir}/keycloak-bootstrap-admin/username" \
  --from-file="password=${artifact_dir}/keycloak-bootstrap-admin/password"
apply_secret keycloak-platform-admin \
  --type=Opaque \
  --from-file="subject=${artifact_dir}/keycloak-platform-admin/subject" \
  --from-file="username=${artifact_dir}/keycloak-platform-admin/username" \
  --from-file="email=${artifact_dir}/keycloak-platform-admin/email" \
  --from-file="password=${artifact_dir}/keycloak-platform-admin/password" \
  --from-file="import.json=${artifact_dir}/keycloak-platform-admin/import.json"
apply_secret keycloak-break-glass \
  --type=Opaque \
  --from-file="username=${artifact_dir}/keycloak-break-glass/username" \
  --from-file="email=${artifact_dir}/keycloak-break-glass/email" \
  --from-file="password=${artifact_dir}/keycloak-break-glass/password"
apply_secret keycloak-realm-import \
  --type=Opaque \
  --from-file="realm.json=${artifact_dir}/keycloak-realm-import/realm.json"
apply_secret harbor-rke-creds \
  --type=kubernetes.io/dockerconfigjson \
  --from-file=".dockerconfigjson=${image_pull_secret_file}"
apply_secret keycloak-apps-tls \
  --type=kubernetes.io/tls \
  --from-file="tls.crt=${tls_cert_file}" \
  --from-file="tls.key=${tls_key_file}"

printf 'Identity Secret references are ready in context %s namespace %s\n' "${cluster_context}" "${namespace}"
