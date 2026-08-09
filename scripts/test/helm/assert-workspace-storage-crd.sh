#!/bin/sh
set -eu

crd_file="helm/aileron/crds/platform.aileron.io_workspaces.yaml"
spec_path='.spec.versions[0].schema.openAPIV3Schema.properties.spec'
status_path='.spec.versions[0].schema.openAPIV3Schema.properties.status'

fail() {
  echo "Workspace storage CRD assertion failed: $*" >&2
  exit 1
}

yq -e "${spec_path}.required | contains([\"storage\"])" "${crd_file}" >/dev/null ||
  fail "spec.storage must be required"
yq -e "${spec_path}.properties.storage.type == \"object\" and
  (${spec_path}.properties.storage.required | contains([\"workspaceData\", \"runtimeHome\"]))" "${crd_file}" >/dev/null ||
  fail "spec.storage object contract is invalid"
for storage_kind in workspaceData runtimeHome; do
  yq -e "${spec_path}.properties.storage.properties.${storage_kind}.type == \"object\" and
    (${spec_path}.properties.storage.properties.${storage_kind}.required | contains([\"capacityBytes\", \"revision\"])) and
    ${spec_path}.properties.storage.properties.${storage_kind}.properties.capacityBytes.type == \"integer\" and
    ${spec_path}.properties.storage.properties.${storage_kind}.properties.capacityBytes.format == \"int64\" and
    ${spec_path}.properties.storage.properties.${storage_kind}.properties.capacityBytes.minimum == 1 and
    ${spec_path}.properties.storage.properties.${storage_kind}.properties.revision.type == \"integer\" and
    ${spec_path}.properties.storage.properties.${storage_kind}.properties.revision.format == \"int64\" and
    ${spec_path}.properties.storage.properties.${storage_kind}.properties.revision.minimum == 1" "${crd_file}" >/dev/null ||
    fail "spec.storage.${storage_kind} capacity contract is invalid"
done

yq -e "${status_path}.properties.storage.type == \"object\"" "${crd_file}" >/dev/null ||
  fail "status.storage object contract is invalid"
for storage_kind in workspaceData runtimeHome; do
  status_kind="${status_path}.properties.storage.properties.${storage_kind}"
  yq -e "${status_kind}.type == \"object\" and
    (${status_kind}.required | contains([\"allocatedBytes\", \"observedRevision\", \"expansionSupported\"])) and
    ${status_kind}.properties.allocatedBytes.type == \"integer\" and
    ${status_kind}.properties.allocatedBytes.format == \"int64\" and
    ${status_kind}.properties.allocatedBytes.minimum == 0 and
    ${status_kind}.properties.observedRevision.type == \"integer\" and
    ${status_kind}.properties.observedRevision.format == \"int64\" and
    ${status_kind}.properties.observedRevision.minimum == 0 and
    ${status_kind}.properties.expansionSupported.type == \"boolean\" and
    ${status_kind}.properties.observedAt.format == \"date-time\" and
    ${status_kind}.properties.errorCode.type == \"string\" and
    (${status_kind}.properties.errorCode.enum | contains([\"STORAGE_CAPACITY_INVALID\", \"STORAGE_CAPACITY_SHRINK_UNSUPPORTED\", \"STORAGE_CLASS_EXPANSION_UNSUPPORTED\", \"STORAGE_CLASS_NOT_FOUND\"])) and
    (${status_kind}.properties | has(\"requestedBytes\") | not) and
    (${status_kind}.properties | has(\"phase\") | not)" "${crd_file}" >/dev/null ||
    fail "status.storage.${storage_kind} capacity contract is invalid"
done

echo "Workspace storage CRD contracts passed"
