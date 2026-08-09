#!/bin/sh

set -eu

crd_file="helm/aileron/crds/platform.aileron.io_workspaces.yaml"

fail() {
  echo "Workspace lifecycle CRD assertion failed: $*" >&2
  exit 1
}

assert_schema() {
  expression="$1"
  description="$2"
  yq eval -e "${expression}" "${crd_file}" >/dev/null || fail "${description}"
}

spec_path='.spec.versions[0].schema.openAPIV3Schema.properties.spec'
status_path='.spec.versions[0].schema.openAPIV3Schema.properties.status'

assert_schema \
  "${spec_path}.required | contains([\"bootstrap\", \"runtime\", \"browser\", \"canvas\"])" \
  "component and bootstrap specs must be required"
assert_schema \
  "${spec_path}.properties.bootstrap.properties.revision.minimum == 1" \
  "bootstrap revision must start at one"
assert_schema \
  "${spec_path}.properties.runtime.required | contains([\"desiredState\", \"instanceId\", \"revision\", \"mountRevision\", \"accessRevision\"])" \
  "runtime lifecycle identity must be explicit"
assert_schema \
  "${spec_path}.properties | has(\"runtimeInstanceId\") | not" \
  "legacy global runtime instance identity must be removed"
assert_schema \
  "${spec_path}.properties | has(\"knowledgeBaseMountRevision\") | not" \
  "legacy global mount revision must be removed"
assert_schema \
  "${spec_path}.properties | has(\"runtimeAccessRevision\") | not" \
  "legacy global access revision must be removed"
assert_schema \
  "${spec_path}.properties.browser.required | contains([\"desiredState\", \"instanceId\", \"revision\"])" \
  "browser lifecycle identity must be explicit"
assert_schema \
  "${spec_path}.properties.canvas.required | contains([\"desiredState\", \"instanceId\", \"revision\"])" \
  "canvas lifecycle identity must be explicit"
for component in runtime browser canvas; do
  assert_schema \
    "${spec_path}.properties.${component}.required | contains([\"resources\"])" \
    "${component} resource requirements must be explicit"
  assert_schema \
    "${spec_path}.properties.${component}.properties.resources.required | contains([\"requests\", \"limits\"])" \
    "${component} requests and limits must be explicit"
  assert_schema \
    "${spec_path}.properties.${component}.properties.resources.properties.requests.required | contains([\"cpu\", \"memory\"])" \
    "${component} CPU and memory requests must be explicit"
  assert_schema \
    "${spec_path}.properties.${component}.properties.resources.properties.limits.required | contains([\"cpu\", \"memory\"])" \
    "${component} CPU and memory limits must be explicit"
  assert_schema \
    "${status_path}.properties.components.properties.${component}.properties.observedInstanceId.type == \"string\"" \
    "${component} observed instance identity must be exposed"
done
assert_schema \
  "${spec_path}.properties.runtime.properties.desiredState.enum | join(\",\") == \"Running,Stopped\"" \
  "runtime desired state enum is invalid"
assert_schema \
  "${status_path}.properties.bootstrap.properties.phase.enum | join(\",\") == \"Pending,Running,Succeeded,Error\"" \
  "bootstrap phase enum is invalid"
assert_schema \
  "${status_path}.properties.components.properties.runtime.properties.phase.enum | join(\",\") == \"Disabled,Stopped,Pending,Starting,Running,Stopping,Error\"" \
  "component phase enum is invalid"
assert_schema \
  "${status_path}.properties.components.properties.runtime.properties.observedRevision.minimum == 0" \
  "runtime observed revision must be non-negative"
assert_schema \
  "${status_path}.properties.components.properties.runtime.properties.lastKnownGoodMountRevision.minimum == 0" \
  "runtime last-known-good mount revision must be non-negative"
assert_schema \
  "(${status_path}.properties.firewall.properties | has(\"workspacePolicyName\")) and (${status_path}.properties.firewall.properties | has(\"runtimePeerPolicyName\")) and (${status_path}.properties.firewall.properties | has(\"browserPolicyName\"))" \
  "firewall status must identify all rendered policies"
assert_schema \
  "${status_path}.properties.firewall.properties.targetRevision.minimum == 0" \
  "firewall target revision must be explicit and non-negative"
assert_schema \
  "${status_path}.properties.firewall.properties.targetDeliveryId.type == \"string\"" \
  "firewall target delivery identity must be exposed"
assert_schema \
  "${status_path}.properties.firewall.properties.phase.enum | contains([\"Applied\", \"Applying\", \"Degraded\", \"Error\"])" \
  "firewall status must distinguish pending enforcement from applied and degraded states"
assert_schema \
  "${status_path}.properties.conditions.items.required | contains([\"lastTransitionTime\", \"message\", \"reason\", \"status\", \"type\"])" \
  "Kubernetes conditions contract is incomplete"

echo "Workspace component lifecycle CRD contracts passed"
