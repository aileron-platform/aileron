#!/bin/sh

set -eu

source_namespace="${IMAGE_PULL_SECRET_SOURCE_NAMESPACE:?IMAGE_PULL_SECRET_SOURCE_NAMESPACE is required}"
source_name="${IMAGE_PULL_SECRET_SOURCE_NAME:?IMAGE_PULL_SECRET_SOURCE_NAME is required}"
target_namespace="${IMAGE_PULL_SECRET_TARGET_NAMESPACE:?IMAGE_PULL_SECRET_TARGET_NAMESPACE is required}"
target_name="${IMAGE_PULL_SECRET_NAME:?IMAGE_PULL_SECRET_NAME is required}"
artifact_dir="${IMAGE_PULL_SECRET_ARTIFACT_DIR:?IMAGE_PULL_SECRET_ARTIFACT_DIR is required}"

fail() {
  printf '[image-pull-secret] FAILED: %s\n' "$*" >&2
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

command -v jq >/dev/null 2>&1 || fail "jq is required"
case "${target_name}" in
  *[!a-z0-9.-]*|.*|*.) fail "IMAGE_PULL_SECRET_NAME must be a DNS subdomain" ;;
esac

kube get secret "${source_name}" -n "${source_namespace}" -o json | \
  jq -e '
    .type == "kubernetes.io/dockerconfigjson"
    and (.data[".dockerconfigjson"] | type == "string" and length > 0)
  ' >/dev/null || fail "source Secret is not a non-empty dockerconfigjson Secret"

kube get secret "${source_name}" -n "${source_namespace}" -o json | \
  jq \
    --arg namespace "${target_namespace}" \
    --arg name "${target_name}" '
      {
        apiVersion: "v1",
        kind: "Secret",
        metadata: {namespace: $namespace, name: $name},
        type,
        data
      }
    ' | kube create -f - >/dev/null

attempts=60
while [ "${attempts}" -gt 0 ]; do
  if kube get serviceaccount default -n "${target_namespace}" >/dev/null 2>&1; then
    break
  fi
  attempts=$((attempts - 1))
  sleep 1
done
[ "${attempts}" -gt 0 ] || fail "default ServiceAccount was not created"
kube patch serviceaccount default -n "${target_namespace}" --type=merge \
  -p "{\"imagePullSecrets\":[{\"name\":\"${target_name}\"}]}" >/dev/null

mkdir -p "${artifact_dir}"
{
  printf 'source_namespace=%s\n' "${source_namespace}"
  printf 'source_name=%s\n' "${source_name}"
  printf 'target_name=%s\n' "${target_name}"
  printf 'type=kubernetes.io/dockerconfigjson\n'
} > "${artifact_dir}/image-pull-secret-metadata.txt"
