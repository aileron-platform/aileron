#!/bin/bash

# Start FastAPI, Celery Worker, and Flower services with Supervisor.

set -e

if [ "${AILERON_EXECUTION_PROFILE:-docker}" = "kubernetes" ]; then
    export HOME="${HOME:-/state/home}"
    export CODEX_HOME="${CODEX_HOME:-/state/codex}"
    export PYTHONPATH="/workspace-manager"
    export UV_CACHE_DIR="/tmp/uv-cache"
    mkdir -p \
        "${HOME}" \
        "${CODEX_HOME}" \
        /state/local-history \
        /state/uploads \
        /state/marketplace \
        /tmp/runtime-scripts \
        /tmp/supervisor \
        "${UV_CACHE_DIR}"
    exec /usr/bin/supervisord -c /workspace-manager/supervisord.kubernetes.conf
fi

# Clear empty environment variables so blank .env settings, such as ANTHROPIC_AUTH_TOKEN=,
# do not affect container behavior.
while IFS= read -r line; do
    [[ "$line" =~ ^([^=]+)=$ ]] && unset "${BASH_REMATCH[1]}"
done < <(env)

echo "🚀 Starting Workspace Manager services..."

# Create log directories.
mkdir -p /var/log/supervisor

# Configure environment variables.
export PYTHONPATH="${PYTHONPATH}:/workspace-manager"

# Switch to the working directory.
cd /workspace-manager

# Ensure the virtual environment is installed correctly. This fixes stale .venv
# state caused by volume mounts.
echo "🔧 Checking and syncing Python dependencies..."
if [ "${NODE_ENV}" = "development" ]; then
    # Development environment: include dev dependencies.
    uv sync --dev 2>&1 | grep -v "warning:" || true
else
    # Production environment: install only production dependencies.
    uv sync --no-dev 2>&1 | grep -v "warning:" || true
fi
echo "✅ Python dependencies are ready"
echo ""

# Show service configuration.
echo "📋 Service configuration:"
echo "   - FastAPI: http://0.0.0.0:3001"
echo "   - Celery Worker: 2 concurrent processes"
echo "   - Celery Beat: durable job recovery and dispatch"
echo "   - Celery Flower: http://0.0.0.0:5555"
echo "   - Celery Queue: celery"
echo ""

# Select Supervisor configuration.
if [ "${NODE_ENV}" = "development" ]; then
    SUPERVISOR_CONF="/workspace-manager/supervisord.dev.conf"
    echo "🔧 Using development configuration with hot reload"
else
    SUPERVISOR_CONF="/workspace-manager/supervisord.conf"
    echo "🏭 Using production configuration"
fi

# Start Supervisor.
echo "🎯 Starting Supervisor-managed services..."
echo "   - FastAPI"
echo "   - Celery Worker"
echo "   - Celery Beat"
echo "   - Celery Flower"
echo ""
exec /usr/bin/supervisord -c $SUPERVISOR_CONF
