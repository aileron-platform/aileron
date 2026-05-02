#!/bin/bash
# Aileron - Workspace Runtime service startup script
# Configures language runtimes, Python dependencies, permissions, Git clone, and Supervisor.

set -e

# Remove empty environment variables so blank .env entries such as ANTHROPIC_AUTH_TOKEN= do not affect container behavior.
while IFS= read -r line; do
    [[ "$line" =~ ^([^=]+)=$ ]] && unset "${BASH_REMATCH[1]}"
done < <(env)

echo "🚀 Starting Aileron Workspace Runtime..."
echo ""

# ============================================================================
# 1. Check environment variables
# ============================================================================
if [ -z "$WORKSPACE_ID" ]; then
    echo "❌ WORKSPACE_ID environment variable is not set"
    exit 1
fi

echo "📋 Workspace information:"
echo "   - Workspace ID: $WORKSPACE_ID"
echo "   - Node Env: ${NODE_ENV:-development}"
echo ""

# ============================================================================
# 2. Configure language runtimes
# ============================================================================
echo "🔧 Configuring language runtimes..."
if [ -f "/opt/codex/setup_universal.sh" ]; then
    source /opt/codex/setup_universal.sh
    echo "✅ Language runtime configuration complete"
else
    echo "⚠️  setup_universal.sh does not exist; skipping language runtime configuration"
fi
echo ""

# ============================================================================
# 3. Sync Python dependencies
# ============================================================================
echo "📦 Syncing Python dependencies..."
cd /workspace-runtime
if [ ! -f ".venv/bin/python" ]; then
    if [ "${NODE_ENV}" = "production" ]; then
        echo "📦 Using uv sync --no-dev (production mode)"
        uv sync --no-dev
    else
        echo "📦 Using uv sync --dev (development mode)"
        uv sync --dev
    fi
    echo "✅ Python dependencies installed"
else
    echo "✅ Python dependencies are already installed; skipping sync"
fi
echo ""

# ============================================================================
# 4. Configure Docker socket permissions so the developer user can run Docker commands.
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
# 5. Configure directory permissions
# ============================================================================
echo "📁 Configuring workspace directory permissions..."
mkdir -p /home/developer/.codex-sessions
chown -R developer:developer /workspace /workspace-runtime /workspace-terminal 2>/dev/null || true
chown -R developer:developer /home/developer/.codex-sessions 2>/dev/null || true
# Bind mounts can remove +x from host scripts, overriding Dockerfile chmod; restore it here.
chmod +x /workspace-runtime/scripts/*.sh 2>/dev/null || true

# Volume mounts can drop execute permissions from .venv/bin.
if [ -d "/workspace-runtime/.venv" ]; then
    echo "🔧 Fixing .venv execute permissions..."
    chmod -R u+x /workspace-runtime/.venv/bin 2>/dev/null || true
    chmod -R u+x /workspace-runtime/.venv/lib/python*/bin 2>/dev/null || true
fi

echo "✅ Directory permissions configured"
echo ""

# ============================================================================
# 5.1 Install agent default configuration (skills and mcp.json)
# ============================================================================
AGENT_DEFAULTS_DIR="/workspace-runtime/agent-defaults"
if [ -d "$AGENT_DEFAULTS_DIR" ]; then
    echo "📋 Installing agent default configuration..."

    # Copy default skills to ~/.claude/skills/ without overwriting existing directories.
    if [ -d "$AGENT_DEFAULTS_DIR/skills" ] && [ "$(ls -A "$AGENT_DEFAULTS_DIR/skills" 2>/dev/null)" ]; then
        CLAUDE_SKILLS_DIR="/home/developer/.claude/skills"
        mkdir -p "$CLAUDE_SKILLS_DIR"
        for skill_dir in "$AGENT_DEFAULTS_DIR/skills"/*/; do
            skill_name=$(basename "$skill_dir")
            target="$CLAUDE_SKILLS_DIR/$skill_name"
            # Remove conflicting symlinks or files so cp -r can write a directory.
            if [ -L "$target" ] || ([ -e "$target" ] && [ ! -d "$target" ]); then
                rm -f "$target"
            fi
            if [ ! -d "$target" ]; then
                cp -r "$skill_dir" "$target"
                echo "  ✓ Skill: $skill_name"
            else
                echo "  - Skill: $skill_name (already exists; skipping)"
            fi
        done
        chown -R developer:developer /home/developer/.claude
    fi

    # Copy default mcp.json to /workspace/.mcp.json without overwriting existing files.
    if [ -f "$AGENT_DEFAULTS_DIR/mcp.json" ]; then
        if [ ! -f "/workspace/.mcp.json" ]; then
            cp "$AGENT_DEFAULTS_DIR/mcp.json" /workspace/.mcp.json
            chown developer:developer /workspace/.mcp.json
            echo "  ✓ MCP configuration installed"
        else
            echo "  - MCP configuration already exists; skipping"
        fi
    fi

    echo "✅ Agent default configuration installed"
else
    echo "⚠️  agent-defaults directory does not exist; skipping default configuration installation"
fi
echo ""

# ============================================================================
# 6. Configure Git
# ============================================================================
echo "🔧 Configuring Git..."
if [ -n "${GIT_USER_NAME:-}" ] && [ -n "${GIT_USER_EMAIL:-}" ]; then
    git config --global user.name "$GIT_USER_NAME"
    git config --global user.email "$GIT_USER_EMAIL"
    echo "✅ Git user configuration set"
else
    echo "✅ Git user uses image default configuration"
fi
git config --global --add safe.directory /workspace 2>/dev/null || true
git config --global --add safe.directory /workspace-runtime 2>/dev/null || true
echo ""

# ============================================================================
# 7. Git Clone
# ============================================================================
if [ -n "${GIT_REPO_URL:-}" ]; then
    echo "🔀 Cloning Git repository..."

    # Ignore .git and .gitkeep when determining whether the workspace is empty.
    if [ -z "$(ls -A /workspace 2>/dev/null | grep -v '\.git' | grep -v '\.gitkeep')" ]; then
        GIT_BRANCH="${GIT_BRANCH:-main}"

        if [ -n "${SSH_PRIVATE_KEY:-}" ]; then
            echo "🔑 Configuring SSH keys..."
            mkdir -p /home/developer/.ssh
            echo "$SSH_PRIVATE_KEY" > /home/developer/.ssh/id_rsa
            chmod 600 /home/developer/.ssh/id_rsa
            if [ -n "${SSH_PUBLIC_KEY:-}" ]; then
                echo "$SSH_PUBLIC_KEY" > /home/developer/.ssh/id_rsa.pub
                chmod 644 /home/developer/.ssh/id_rsa.pub
            fi
            eval "$(ssh-agent -s)" 2>/dev/null || true
            ssh-add /home/developer/.ssh/id_rsa 2>/dev/null || true
            chown -R developer:developer /home/developer/.ssh
            echo "✅ SSH keys configured"
        fi

        cd /tmp
        git clone --branch "$GIT_BRANCH" "$GIT_REPO_URL" /tmp/repo-clone
        cp -r /tmp/repo-clone/* /workspace/ 2>/dev/null || true
        cp -r /tmp/repo-clone/.git /workspace/ 2>/dev/null || true
        rm -rf /tmp/repo-clone

        git config --global --add safe.directory /workspace
        git -C /workspace config --local user.name "${GIT_USER_NAME:-Developer}"
        git -C /workspace config --local user.email "${GIT_USER_EMAIL:-developer@workspace.local}"
        echo "✅ Repository clone complete"
    else
        echo "⚠️  /workspace directory is not empty; skipping clone"
    fi
else
    echo "⚠️  GIT_REPO_URL is not set; skipping Git clone"
fi

/workspace-runtime/scripts/bootstrap_git_repo.sh

chown -R developer:developer /workspace 2>/dev/null || true
echo ""

# ============================================================================
# 8. Initialize OpenSpec
# ============================================================================
echo "🧭 Checking OpenSpec initialization status..."
OPENSPEC_INIT_TOOLS="${OPENSPEC_INIT_TOOLS:-claude,codex,opencode,gemini}"
if [ "${OPENSPEC_AUTO_INIT:-1}" = "1" ]; then
    if command -v openspec >/dev/null 2>&1; then
        if [ ! -d "/workspace/openspec" ]; then
            echo "📋 Running OpenSpec initialization..."
            if HOME=/home/developer XDG_CONFIG_HOME=/home/developer/.config su developer -s /bin/bash -c "export PATH=/home/developer/.local/bin:/home/developer/.npm-global/bin:/home/developer/.cargo/bin:\$PATH; cd /workspace && openspec init --tools ${OPENSPEC_INIT_TOOLS}"; then
                echo "✅ OpenSpec initialization complete"
                chown -R developer:developer /workspace /home/developer/.config /home/developer/.claude /home/developer/.codex 2>/dev/null || true
            else
                echo "⚠️  OpenSpec initialization failed; skipping automatic initialization"
            fi
        else
            echo "✅ OpenSpec is already initialized; skipping"
        fi
    else
        echo "⚠️  openspec CLI not found; skipping automatic initialization"
    fi
else
    echo "⏭️  OPENSPEC_AUTO_INIT=0; skipping automatic initialization"
fi
echo ""

# ============================================================================
# 9. Configure SSH keys
# ============================================================================
if [ -n "${SSH_PUBLIC_KEY:-}" ] && [ -n "${SSH_PRIVATE_KEY:-}" ]; then
    echo "🔑 Configuring SSH access..."
    mkdir -p /home/developer/.ssh
    echo "$SSH_PRIVATE_KEY" > /home/developer/.ssh/id_rsa
    chmod 600 /home/developer/.ssh/id_rsa
    echo "$SSH_PUBLIC_KEY" > /home/developer/.ssh/id_rsa.pub
    chmod 644 /home/developer/.ssh/id_rsa.pub
    echo "$SSH_PUBLIC_KEY" > /home/developer/.ssh/authorized_keys
    chmod 600 /home/developer/.ssh/authorized_keys
    chown -R developer:developer /home/developer/.ssh
    echo "✅ SSH access configured"
else
    echo "⚠️  SSH_PUBLIC_KEY or SSH_PRIVATE_KEY is not set; skipping SSH key configuration"
fi
echo ""

# ============================================================================
# 10. Create Terminal Service cache directory
# ============================================================================
echo "🔧 Preparing Terminal Service cache directory..."
mkdir -p "${WORKSPACE_TERMINAL_CACHE_DIR:-/workspace/.cache/terminal-service}"
chown -R developer:developer "${WORKSPACE_TERMINAL_CACHE_DIR:-/workspace/.cache/terminal-service}" 2>/dev/null || true
echo "✅ Terminal Service will resolve its binary when started by supervisord"
echo ""

# ============================================================================
# 11. Start Supervisor
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
echo "✅ All services started"
echo ""
echo "🎉 Workspace Runtime is ready!"
echo ""
echo "📊 Active services:"
echo "   - FastAPI:          http://localhost:3002"
echo "   - SSH:              localhost:22"
echo "   - Terminal Service: http://localhost:3004"
echo "   - Canvas Runtime:  http://localhost:3003 (optional)"
echo ""

# nodaemon=true runs in the foreground to keep the container active.
exec /usr/bin/supervisord -c "$SUPERVISOR_CONFIG"
