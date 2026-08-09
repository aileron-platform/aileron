#!/bin/sh
# Start the Canvas management API with all runtime state on writable /tmp.

set -eu
umask 0007

echo "[Entrypoint] Starting workspace-canvas container..."
echo "[Entrypoint] WORKSPACE_DIR: ${WORKSPACE_DIR:-/workspace}"
echo "[Entrypoint] PORT: ${PORT:-3003}"
echo "[Entrypoint] API_PORT: ${API_PORT:-3013}"

runtime_root="${CANVAS_RUNTIME_ROOT:-/tmp/aileron-canvas}"
export CANVAS_RUNTIME_HOME="${CANVAS_RUNTIME_HOME:-${runtime_root}/home}"
export CANVAS_NPM_CACHE_DIR="${CANVAS_NPM_CACHE_DIR:-${runtime_root}/npm-cache}"
export HOME="${CANVAS_RUNTIME_HOME}"
export npm_config_cache="${CANVAS_NPM_CACHE_DIR}"
export NEXT_TELEMETRY_DISABLED=1

default_canvas_dir="${DEFAULT_CANVAS_DIR:-${runtime_root}/default-canvas}"
export DEFAULT_CANVAS_DIR="${default_canvas_dir}"

mkdir -p \
  "${CANVAS_RUNTIME_HOME}" \
  "${CANVAS_NPM_CACHE_DIR}" \
  "${default_canvas_dir}"

if [ ! -f "${default_canvas_dir}/package.json" ]; then
  cp -R /opt/canvas-default-source/. "${default_canvas_dir}/"
fi

if [ -L "${default_canvas_dir}/node_modules" ] || [ ! -d "${default_canvas_dir}/node_modules" ]; then
  rm -rf "${default_canvas_dir}/node_modules"
  mkdir -p "${default_canvas_dir}/node_modules"
  cp -R /opt/canvas-nextjs-template/node_modules/. "${default_canvas_dir}/node_modules/"
fi

echo "[Entrypoint] Starting management server..."
exec node /canvas-management/server.js
