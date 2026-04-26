#!/bin/bash

# Start FastAPI, Celery Worker, and Flower services with Supervisor.

set -e

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
echo "   - Celery Flower: http://0.0.0.0:5555"
echo "   - Celery Queues: default,container,docker,rebuild,local,firewall"
echo "   - Broker: ${CELERY_BROKER_URL:-redis://redis:6379/0}"
echo "   - Result Backend: ${CELERY_RESULT_BACKEND:-redis://redis:6379/1}"
echo ""

# Derive host and port from REDIS_URL so Kubernetes deployments that only set
# the URL do not wait the full 30 seconds.
redis_url="${REDIS_URL:-redis://redis:6379/0}"
redis_target="${redis_url#redis://}"
redis_target="${redis_target#rediss://}"
redis_target="${redis_target#*@}"
redis_target="${redis_target%%/*}"

redis_host="${REDIS_HOST:-${redis_target%%:*}}"
redis_port="${REDIS_PORT:-6379}"

if [[ -n "${redis_target}" && "${redis_target}" == *:* ]]; then
    redis_port="${REDIS_PORT:-${redis_target##*:}}"
fi

if [ -z "${redis_host}" ]; then
    redis_host="redis"
fi

# Wait for Redis availability.
echo "⏳ Waiting for Redis service..."
timeout=30
echo "   - Redis Host: ${redis_host}"
echo "   - Redis Port: ${redis_port}"
while ! redis-cli -h "${redis_host}" -p "${redis_port}" ping > /dev/null 2>&1; do
    timeout=$((timeout - 1))
    if [ $timeout -eq 0 ]; then
        echo "❌ Redis service is unavailable, continuing service startup"
        break
    fi
    sleep 1
done

if [ $timeout -gt 0 ]; then
    echo "✅ Redis service is ready"
fi

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
echo "   - Celery Flower"
echo ""
exec /usr/bin/supervisord -c $SUPERVISOR_CONF
