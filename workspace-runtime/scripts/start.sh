#!/bin/bash
set -e

# Check required environment variables injected during container provisioning.
if [ -z "$ANTHROPIC_BASE_URL" ]; then
    echo "WARNING: ANTHROPIC_BASE_URL not set"
fi
if [ -z "$ANTHROPIC_AUTH_TOKEN" ]; then
    echo "WARNING: ANTHROPIC_AUTH_TOKEN not set"
fi

echo "Starting Workspace Runtime service..."
echo "ANTHROPIC_BASE_URL: ${ANTHROPIC_BASE_URL:-<not set>}"
echo "ANTHROPIC_AUTH_TOKEN: ${ANTHROPIC_AUTH_TOKEN:+${ANTHROPIC_AUTH_TOKEN:0:8}...}"

SYNC_DEPENDENCIES="${WORKSPACE_RUNTIME_SYNC_DEPENDENCIES:-}"
if [ -z "$SYNC_DEPENDENCIES" ]; then
    if [ "${DEPLOYMENT_ENV}" = "kubernetes" ] || [ "${NODE_ENV}" = "production" ]; then
        SYNC_DEPENDENCIES="false"
    else
        SYNC_DEPENDENCIES="true"
    fi
fi

if [ "$SYNC_DEPENDENCIES" = "true" ]; then
    echo "Checking dependencies..."
    if [ -f "/workspace-runtime/pyproject.toml" ]; then
        cd /workspace-runtime
        uv sync --quiet 2>/dev/null || echo "Dependency sync completed with warnings"
    fi
else
    echo "Skipping dependency sync (WORKSPACE_RUNTIME_SYNC_DEPENDENCIES=${SYNC_DEPENDENCIES})"
fi

# Start FastAPI using the full path.
exec /workspace-runtime/.venv/bin/python -m app.main
