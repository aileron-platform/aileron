#!/bin/bash
# Aileron - Workspace Runtime service startup script
# Configures language runtimes, writable mounts, Workspace state, and Supervisor.

set -e

export HOME="${HOME:-/home/developer}"
export PATH="/opt/aileron/bin:/opt/aileron/npm/bin:/workspace-runtime/.venv/bin:${HOME}/.local/bin:${PATH}"
export CODEX_HOME="${CODEX_HOME:-${HOME}/.codex}"
export XDG_CONFIG_HOME="${XDG_CONFIG_HOME:-${HOME}/.config}"
export XDG_DATA_HOME="${XDG_DATA_HOME:-${HOME}/.local/share}"
export XDG_STATE_HOME="${XDG_STATE_HOME:-${HOME}/.local/state}"
export MARKETPLACE_OPERATION_JOURNAL_DIR="${MARKETPLACE_OPERATION_JOURNAL_DIR:-${XDG_STATE_HOME}/aileron/marketplace-operations}"
export UV_CACHE_DIR="${UV_CACHE_DIR:-/tmp/uv-cache}"
export NPM_CONFIG_CACHE="${NPM_CONFIG_CACHE:-/tmp/npm-cache}"
export NPM_CONFIG_PREFIX="${NPM_CONFIG_PREFIX:-${HOME}/.local}"

mkdir -p \
    "${HOME}" \
    "${CODEX_HOME}" \
    "${HOME}/.codex-sessions" \
    "${HOME}/.claude" \
    "${XDG_CONFIG_HOME}/opencode" \
    "${XDG_DATA_HOME}/opencode" \
    "${XDG_STATE_HOME}/aileron" \
    "${MARKETPLACE_OPERATION_JOURNAL_DIR}" \
    "${UV_CACHE_DIR}" \
    "${NPM_CONFIG_CACHE}"

# Remove empty environment variables so blank .env entries such as ANTHROPIC_AUTH_TOKEN= do not affect container behavior.
while IFS= read -r line; do
    [[ "$line" =~ ^([A-Za-z_][A-Za-z0-9_]*)=$ ]] && unset "${BASH_REMATCH[1]}"
done < <(env)

echo "🚀 Starting Aileron Workspace Runtime..."
echo ""

# ============================================================================
# 1. Check environment variables
# ============================================================================
if [ -z "$AILERON_WORKSPACE_ID" ]; then
    echo "❌ AILERON_WORKSPACE_ID environment variable is not set"
    exit 1
fi

echo "📋 Workspace information:"
echo "   - Workspace ID: $AILERON_WORKSPACE_ID"
echo "   - Node Env: ${NODE_ENV:-development}"
echo ""

# ============================================================================
# 2. Configure language runtimes
# ============================================================================
echo "🔧 Configuring language runtimes..."
if [ -f "/opt/codex/setup_universal.sh" ]; then
    source /opt/codex/setup_universal.sh
    export PATH="/workspace-runtime/.venv/bin:$PATH"
    echo "✅ Language runtime configuration complete"
else
    echo "⚠️  setup_universal.sh does not exist; skipping language runtime configuration"
fi
echo ""

if [ ! -x "/workspace-runtime/.venv/bin/python" ]; then
    echo "❌ Image-managed Python environment is unavailable"
    exit 1
fi

# ============================================================================
# 3. Configure Docker socket permissions so the developer user can run Docker commands.
# ============================================================================
if [ -S /var/run/docker.sock ]; then
    echo "🐳 Configuring Docker socket permissions..."
    DOCKER_SOCK_GID=$(stat -c '%g' /var/run/docker.sock)
    if [ "$DOCKER_SOCK_GID" = "0" ]; then
        # macOS Docker Desktop: the socket belongs to root, so use the docker group with chmod 660.
        groupadd -g 999 docker 2>/dev/null || true
        usermod -aG docker developer 2>/dev/null || true
        chmod 660 /var/run/docker.sock 2>/dev/null || true
        chgrp docker /var/run/docker.sock 2>/dev/null || true
        echo "  ✓ Docker socket permissions configured (chmod 660 + docker group)"
    else
        # Linux: align the docker GID inside the container with the host.
        groupmod -g ${DOCKER_SOCK_GID} docker 2>/dev/null || true
        usermod -aG docker developer 2>/dev/null || true
        echo "  ✓ Docker group GID adjusted to ${DOCKER_SOCK_GID}"
    fi
fi
echo ""

# ============================================================================
# 4. Configure directory permissions
# ============================================================================
echo "📁 Configuring workspace directory permissions..."
usermod --home "${HOME}" developer

ensure_developer_writable() {
    local path="$1"
    if runuser -u developer -- test -w "${path}"; then
        return
    fi

    echo "  - Repairing permissions for ${path}"
    chown -R developer:developer "${path}"
}

ensure_developer_writable "/workspace"
ensure_developer_writable "/workspace-terminal"
ensure_developer_writable "${HOME}"
# The Docker-host image creates these paths as root before the Runtime process
# drops to developer.  A writable HOME does not imply that its 0755 children
# are writable, especially when /home/developer is a bind-mounted Runtime home.
# Keep every fixed user-scope Runtime path writable so bootstrap and the agent
# CLIs can initialize without mutating image-managed dependencies.
ensure_developer_writable "${CODEX_HOME}"
ensure_developer_writable "${HOME}/.codex-sessions"
ensure_developer_writable "${HOME}/.claude"
ensure_developer_writable "${NPM_CONFIG_PREFIX}"
ensure_developer_writable "${XDG_CONFIG_HOME}"
ensure_developer_writable "${XDG_DATA_HOME}"
ensure_developer_writable "${XDG_STATE_HOME}"
ensure_developer_writable "${UV_CACHE_DIR}"
ensure_developer_writable "${NPM_CONFIG_CACHE}"

# Docker Runtime secret mounts are intentionally root-readable only.  FastAPI
# and the terminal service run as developer, so hand the required values to
# them through container-local files owned by developer without weakening the
# permissions of the mounted source files.
prepare_runtime_secret() {
    local source_path="$1"
    local filename="$2"
    local target_dir="/run/aileron-runtime-secrets"
    local target_path="${target_dir}/${filename}"

    if [ ! -f "${source_path}" ]; then
        echo "❌ Runtime secret file is unavailable: ${source_path}"
        return 1
    fi

    install -d -o developer -g developer -m 0700 "${target_dir}"
    install -o developer -g developer -m 0400 "${source_path}" "${target_path}"
    printf '%s\n' "${target_path}"
}

export AILERON_RUNTIME_DATABASE_CONNECTION_FILE="$({
    prepare_runtime_secret \
        "${AILERON_RUNTIME_DATABASE_CONNECTION_FILE}" \
        "runtime-database-connection"
})"
export AILERON_RUNTIME_CONTROL_TOKEN_FILE="$({
    prepare_runtime_secret \
        "${AILERON_RUNTIME_CONTROL_TOKEN_FILE}" \
        "runtime-control-token"
})"

# Bind mounts can remove +x from host scripts, overriding Dockerfile chmod; restore it here.
chmod +x /workspace-runtime/scripts/*.sh 2>/dev/null || true

echo "✅ Directory permissions configured"
echo ""

# ============================================================================
# 5. Initialize Workspace Runtime
# ============================================================================
runuser -u developer -- env \
    HOME="${HOME}" \
    CODEX_HOME="${CODEX_HOME}" \
    XDG_CONFIG_HOME="${XDG_CONFIG_HOME}" \
    XDG_DATA_HOME="${XDG_DATA_HOME}" \
    XDG_STATE_HOME="${XDG_STATE_HOME}" \
    AILERON_WORKSPACE_PATH="${AILERON_WORKSPACE_PATH}" \
    /workspace-runtime/.venv/bin/python \
    /workspace-runtime/scripts/initialize_workspace_runtime.py

echo ""

# ============================================================================
# 6. Configure SSH access
# ============================================================================
if [ -n "${SSH_PUBLIC_KEY:-}" ] && [ -n "${SSH_PRIVATE_KEY:-}" ]; then
    echo "🔑 Configuring SSH access..."
    mkdir -p "${HOME}/.ssh"
    echo "$SSH_PRIVATE_KEY" > "${HOME}/.ssh/id_rsa"
    chmod 600 "${HOME}/.ssh/id_rsa"
    echo "$SSH_PUBLIC_KEY" > "${HOME}/.ssh/id_rsa.pub"
    chmod 644 "${HOME}/.ssh/id_rsa.pub"
    echo "$SSH_PUBLIC_KEY" > "${HOME}/.ssh/authorized_keys"
    chmod 600 "${HOME}/.ssh/authorized_keys"
    chown -R developer:developer "${HOME}/.ssh"
    echo "✅ SSH access configured"
else
    echo "⚠️  SSH_PUBLIC_KEY or SSH_PRIVATE_KEY is not set; skipping SSH key configuration"
fi
echo ""

# ============================================================================
# 7. Start Supervisor
# ============================================================================
echo "🎯 Starting service manager..."

if [ "${NODE_ENV}" = "production" ]; then
    SUPERVISOR_CONFIG="/workspace-runtime/supervisord.conf"
    echo "📋 Using production configuration: $SUPERVISOR_CONFIG"
else
    SUPERVISOR_CONFIG="/workspace-runtime/supervisord.dev.conf"
    if [ ! -f "$SUPERVISOR_CONFIG" ]; then
        SUPERVISOR_CONFIG="/workspace-runtime/supervisord.conf"
        echo "📋 Development configuration does not exist; using standard configuration: $SUPERVISOR_CONFIG"
    else
        echo "📋 Using development configuration: $SUPERVISOR_CONFIG"
    fi
fi

echo ""
echo "📊 Launching services:"
echo "   - FastAPI:          http://localhost:3002"
echo "   - SSH:              localhost:22"
echo "   - Terminal Service: http://localhost:3004"
echo "   - Canvas Runtime:  http://localhost:3003 (optional)"
echo ""

# nodaemon=true runs in the foreground to keep the container active.
exec /usr/bin/supervisord -c "$SUPERVISOR_CONFIG"
