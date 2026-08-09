#!/bin/sh

set -eu

repo_root="$(CDPATH= cd -- "$(dirname "$0")/../../.." && pwd)"
chart_dir="${repo_root}/helm/aileron"
release_namespace="workspace-system"

platform_render="$(
    helm template aileron "${chart_dir}" \
        --namespace "${release_namespace}"
)"
if printf "%s" "${platform_render}" | grep -q "CANVAS_PUBLISH"; then
    echo "Canvas publishing must not be coupled to Helm-rendered platform resources." >&2
    exit 1
fi

if [ -e "${chart_dir}/templates/secret.yaml" ]; then
    echo "Aileron Helm must not create the installation Secret." >&2
    exit 1
fi

if helm template aileron "${chart_dir}" \
    --namespace "${release_namespace}" \
    --set-string workspaceManager.env.ARBITRARY_UNSUPPORTED_ENV=rejected \
    --set-string workspaceManager.extraEnv[0].name=ARBITRARY_UNSUPPORTED_ENV \
    --set-string workspaceManager.extraEnv[0].value=rejected \
    --set-string workspaceOperator.env.ARBITRARY_UNSUPPORTED_ENV=rejected \
    >/dev/null 2>&1; then
    echo "Unknown Helm environment surfaces must fail closed." >&2
    exit 1
fi

echo "Canvas publish Helm decoupling contract passed."
