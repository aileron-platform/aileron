#!/bin/sh

set -eu

repo_root="${REPO_ROOT:-/repo}"
work_dir="$(mktemp -d)"
generated_dir="${work_dir}/generated"
digest="$(printf '%064d' 0)"

trap 'rm -rf "${work_dir}"' EXIT HUP INT TERM

env \
  REPO_ROOT="${repo_root}" \
  ARTIFACT_DIR="${work_dir}/artifacts" \
  E2E_RUN_ID=workspace-cr-contract \
  E2E_NAMESPACE=workspace-cr-contract \
  OPERATOR_IMAGE="registry.example/operator@sha256:${digest}" \
  MANAGER_IMAGE="registry.example/manager@sha256:${digest}" \
  WORKLOAD_PROBE_IMAGE="registry.example/probe@sha256:${digest}" \
  WORKSPACE_CR_CONTRACT_OUTPUT_DIR="${generated_dir}" \
  "${repo_root}/scripts/test/kubernetes/run-kubernetes-conformance-e2e.sh"

python3 - "${repo_root}" "${generated_dir}" <<'PY'
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import jsonschema
import yaml


def merge_patch(document: object, patch: object) -> object:
    if not isinstance(patch, dict):
        return copy.deepcopy(patch)
    result = copy.deepcopy(document) if isinstance(document, dict) else {}
    for key, value in patch.items():
        if value is None:
            result.pop(key, None)
        else:
            result[key] = merge_patch(result.get(key), value)
    return result


repo_root = Path(sys.argv[1])
generated_dir = Path(sys.argv[2])
crd = yaml.safe_load(
    (repo_root / "helm/aileron/crds/platform.aileron.io_workspaces.yaml").read_text(
        encoding="utf-8"
    )
)
schema = crd["spec"]["versions"][0]["schema"]["openAPIV3Schema"]
validator = jsonschema.Draft7Validator(schema)
database_trust_schema = schema["properties"]["spec"]["properties"]["runtime"][
    "properties"
]["databaseTrust"]
assert "properties" in database_trust_schema
assert "additionalProperties" not in database_trust_schema

workspace = yaml.safe_load(
    (generated_dir / "workspace.yaml").read_text(encoding="utf-8")
)
mount_patch = json.loads(
    (generated_dir / "mount-patch.json").read_text(encoding="utf-8")
)
access_patch = json.loads(
    (generated_dir / "access-patch.json").read_text(encoding="utf-8")
)
mounted_workspace = merge_patch(workspace, mount_patch)
access_workspace = merge_patch(mounted_workspace, access_patch)

for label, document in (
    ("workspace fixture", workspace),
    ("mount patch result", mounted_workspace),
    ("access patch result", access_workspace),
):
    errors = sorted(validator.iter_errors(document), key=lambda item: list(item.path))
    if errors:
        details = "; ".join(
            f"{'/'.join(str(value) for value in error.path)}: {error.message}"
            for error in errors
        )
        raise AssertionError(f"{label} violates the chart CRD: {details}")

spec = workspace["spec"]
runtime = spec["runtime"]
assert set(mount_patch) == {"spec"}
assert set(mount_patch["spec"]) == {"knowledgeBases", "runtime"}
assert set(mount_patch["spec"]["runtime"]) == {
    "instanceId",
    "mountRevision",
    "accessRevision",
}
assert set(access_patch) == {"spec"}
assert set(access_patch["spec"]) == {"runtime"}
assert set(access_patch["spec"]["runtime"]) == {
    "instanceId",
    "accessRevision",
}

legacy_fields = {
    "runtimeInstanceId",
    "knowledgeBaseMountRevision",
    "runtimeAccessRevision",
}
assert legacy_fields.isdisjoint(spec)
assert runtime["desiredState"] == "Running"
assert runtime["revision"] == 1
assert runtime["mountRevision"] == 0
assert runtime["accessRevision"] == 0
assert spec["browser"]["instanceId"] == runtime["instanceId"]
assert spec["canvas"]["instanceId"] == runtime["instanceId"]
assert runtime["resources"] == {
    "requests": {"cpu": "500m", "memory": "1Gi"},
    "limits": {"cpu": "2", "memory": "3Gi"},
}
assert spec["browser"]["resources"] == {
    "requests": {"cpu": "500m", "memory": "1Gi"},
    "limits": {"cpu": "2", "memory": "2Gi"},
}
assert spec["canvas"]["resources"] == {
    "requests": {"cpu": "100m", "memory": "1Gi"},
    "limits": {"cpu": "1", "memory": "2Gi"},
}
assert spec["bootstrap"] == {"revision": 1}
assert spec["firewall"]["revision"] == 1

assert mounted_workspace["spec"]["runtime"]["mountRevision"] == 1
assert mounted_workspace["spec"]["runtime"]["accessRevision"] == 0
assert mounted_workspace["spec"]["knowledgeBases"] == [
    {
        "kbId": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
        "alias": "product",
    }
]
assert access_workspace["spec"]["runtime"]["mountRevision"] == 1
assert access_workspace["spec"]["runtime"]["accessRevision"] == 1
assert (
    access_workspace["spec"]["knowledgeBases"]
    == mounted_workspace["spec"]["knowledgeBases"]
)

invalid_workspace = copy.deepcopy(workspace)
del invalid_workspace["spec"]["runtime"]["resources"]
assert list(validator.iter_errors(invalid_workspace))
PY

printf '%s\n' "workspace conformance CR fixture and patch contract passed"
