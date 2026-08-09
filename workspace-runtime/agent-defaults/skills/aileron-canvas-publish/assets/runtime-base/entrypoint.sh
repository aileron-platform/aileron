#!/bin/sh

set -eu

site_dir="${CANVAS_SITE_DIR:-/opt/canvas/site}"
export PORT="${PORT:-8080}"
export HOSTNAME="${CANVAS_HOST:-0.0.0.0}"

if [ -f "${site_dir}/server.js" ]; then
    exec node /opt/canvas/publication-proxy.js
fi

exec node /opt/canvas/static-server.js
