#!/bin/sh
set -eu

crd="helm/aileron/crds/platform.aileron.io_workspaces.yaml"
expected='^[a-z0-9](?:[a-z0-9._:/-]*[a-z0-9])?@sha256:[0-9a-f]{64}$'
base='.spec.versions[0].schema.openAPIV3Schema.properties.spec.properties'

for component in runtime browser canvas; do
  required="$(yq eval "${base}.${component}.required | contains([\"image\"])" "$crd")"
  pattern="$(yq eval "${base}.${component}.properties.image.pattern" "$crd")"
  if [ "$required" != "true" ]; then
    echo "${component}.image must be required" >&2
    exit 1
  fi
  if [ "$pattern" != "$expected" ]; then
    echo "${component}.image immutable digest pattern mismatch" >&2
    exit 1
  fi
done

if [ "$(yq eval "${base}.runtime.properties.imageKey" "$crd")" != "null" ]; then
  echo "runtime.imageKey must not remain in the CRD" >&2
  exit 1
fi

echo "Workspace immutable image CRD contracts passed"
