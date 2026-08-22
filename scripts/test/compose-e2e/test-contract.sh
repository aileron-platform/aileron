#!/bin/sh
set -eu

repo_root=$(CDPATH='' cd -- "$(dirname -- "$0")/../../.." && pwd)
output_file=$(mktemp)
trap 'rm -f "$output_file"' EXIT

if [ -e "$repo_root/scripts/test/compose-e2e/.state" ]; then
  echo "Repository-local Compose E2E state is forbidden" >&2
  exit 1
fi

for yaml_file in \
  "$repo_root"/scripts/test/compose-e2e/*.yml \
  "$repo_root"/scripts/test/compose-e2e/*.yaml; do
  [ -f "$yaml_file" ] || continue
  if grep -n -E '!(reset|override)' "$yaml_file"; then
    echo "Compose E2E YAML must use only safe_load-compatible standard tags" >&2
    exit 1
  fi
done

if ! "$repo_root/scripts/test/compose-e2e/run.sh" --preflight-only >"$output_file" 2>&1; then
  cat "$output_file" >&2
  exit 1
fi

grep -q '^COMPOSE_E2E_PREFLIGHT_OK ' "$output_file"
grep -q 'project=aileron-compose-e2e-' "$output_file"
grep -q 'network=aileron-compose-e2e-' "$output_file"
grep -q '^collect_dynamic_workspace_diagnostics()' \
  "$repo_root/scripts/test/compose-e2e/run.sh"
# The contract intentionally matches a literal variable.
# shellcheck disable=SC2016
grep -q 'docker logs --tail 200 "$diagnostic_container_id"' \
  "$repo_root/scripts/test/compose-e2e/run.sh"

test ! -e "$repo_root/scripts/test/compose-e2e/.state"

echo "Compose E2E preflight contract passed"
