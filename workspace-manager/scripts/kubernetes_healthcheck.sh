#!/bin/bash

set -euo pipefail

supervisor_socket="unix:///tmp/supervisor/supervisor.sock"

curl --fail --silent --show-error \
    --max-time 5 \
    http://127.0.0.1:3001/health \
    >/dev/null

if [[ "${1:-}" == "--ready" ]]; then
    curl --fail --silent --show-error \
        --max-time 10 \
        http://127.0.0.1:3001/health/oidc \
        >/dev/null
fi

worker_status="$(
    /usr/bin/supervisorctl \
        --serverurl "${supervisor_socket}" \
        status celery-worker
)"
grep -q "RUNNING" <<< "${worker_status}"
