#!/bin/bash
# Aileron - Workspace Runtime 啟動服務腳本
# 整合語言環境配置、Python 依賴、權限設定、Git Clone 和 Supervisor 啟動

set -e

# 清除空值環境變數，避免 .env 的空設定（如 ANTHROPIC_AUTH_TOKEN=）影響 container 行為
while IFS= read -r line; do
    [[ "$line" =~ ^([^=]+)=$ ]] && unset "${BASH_REMATCH[1]}"
done < <(env)

echo "🚀 Aileron - Workspace Runtime 啟動中..."
echo ""

# ============================================================================
# 1. 檢查環境變數
# ============================================================================
if [ -z "$WORKSPACE_ID" ]; then
    echo "❌ WORKSPACE_ID 環境變數未設定"
    exit 1
fi

echo "📋 工作區信息："
echo "   - Workspace ID: $WORKSPACE_ID"
echo "   - Node Env: ${NODE_ENV:-development}"
echo ""

# ============================================================================
# 2. 配置語言運行環境
# ============================================================================
echo "🔧 配置語言運行環境..."
if [ -f "/opt/codex/setup_universal.sh" ]; then
    source /opt/codex/setup_universal.sh
    echo "✅ 語言環境配置完成"
else
    echo "⚠️  setup_universal.sh 不存在，跳過語言環境配置"
fi
echo ""

# ============================================================================
# 3. Python 依賴同步
# ============================================================================
echo "📦 同步 Python 依賴..."
cd /workspace-runtime
if [ ! -f ".venv/bin/python" ]; then
    if [ "${NODE_ENV}" = "production" ]; then
        echo "📦 使用 uv sync --no-dev (生產模式)"
        uv sync --no-dev
    else
        echo "📦 使用 uv sync --dev (開發模式)"
        uv sync --dev
    fi
    echo "✅ Python 依賴安裝完成"
else
    echo "✅ Python 依賴已安裝，跳過同步"
fi
echo ""

# ============================================================================
# 4. 設定 Docker Socket 權限（讓 developer 用戶可以執行 docker 指令）
# ============================================================================
if [ -S /var/run/docker.sock ]; then
    echo "🐳 設定 Docker Socket 權限..."
    DOCKER_SOCK_GID=$(stat -c '%g' /var/run/docker.sock)
    if [ "$DOCKER_SOCK_GID" = "0" ]; then
        # macOS Docker Desktop: socket 屬於 root，改用 docker 群組管控（chmod 660）
        groupadd -g 999 docker 2>/dev/null || true
        usermod -aG docker developer 2>/dev/null || true
        chmod 660 /var/run/docker.sock 2>/dev/null || true
        chgrp docker /var/run/docker.sock 2>/dev/null || true
        echo "  ✓ Docker socket 權限已設定 (chmod 660 + docker 群組)"
    else
        # Linux: 同步容器內 docker GID 與 host 一致
        groupmod -g ${DOCKER_SOCK_GID} docker 2>/dev/null || true
        usermod -aG docker developer 2>/dev/null || true
        echo "  ✓ Docker 群組 GID 已調整為 ${DOCKER_SOCK_GID}"
    fi
fi
echo ""

# ============================================================================
# 5. 設定目錄權限
# ============================================================================
echo "📁 設定工作區目錄權限..."
chown -R developer:developer /workspace /workspace-runtime /workspace-terminal 2>/dev/null || true
# bind-mount 可能讓 host 上的 script 失去 +x（Dockerfile 的 chmod 被覆蓋），在這裡補回
chmod +x /workspace-runtime/scripts/*.sh 2>/dev/null || true

echo "🔧 修復 /root 目錄訪問權限（developer 用戶需要執行語言工具）..."
for dir in /root /root/.pyenv/versions /root/.nvm/versions /root/.cargo/bin \
           /root/.local/bin /root/.local/share/mise/shims; do
    [ -d "$dir" ] && chmod o+x "$dir" 2>/dev/null && echo "  ✓ $dir" || true
done

# volume mount 可能導致 .venv/bin 執行權限丟失
if [ -d "/workspace-runtime/.venv" ]; then
    echo "🔧 修復 .venv 執行權限..."
    chmod -R u+x /workspace-runtime/.venv/bin 2>/dev/null || true
    chmod -R u+x /workspace-runtime/.venv/lib/python*/bin 2>/dev/null || true
fi

# agent-browser daemon 若以 root 執行會建立 root 所有的 socket 目錄，需預先修正
mkdir -p /home/developer/.agent-browser
chown -R developer:developer /home/developer/.agent-browser

echo "✅ 目錄權限設定完成"
echo ""

# ============================================================================
# 5.1 安裝 Agent 預設配置（skills、mcp.json）
# ============================================================================
AGENT_DEFAULTS_DIR="/workspace-runtime/agent-defaults"
if [ -d "$AGENT_DEFAULTS_DIR" ]; then
    echo "📋 安裝 Agent 預設配置..."

    # 複製預設 skills 到 ~/.claude/skills/（不覆蓋已存在的）
    if [ -d "$AGENT_DEFAULTS_DIR/skills" ] && [ "$(ls -A "$AGENT_DEFAULTS_DIR/skills" 2>/dev/null)" ]; then
        CLAUDE_SKILLS_DIR="/home/developer/.claude/skills"
        mkdir -p "$CLAUDE_SKILLS_DIR"
        for skill_dir in "$AGENT_DEFAULTS_DIR/skills"/*/; do
            skill_name=$(basename "$skill_dir")
            target="$CLAUDE_SKILLS_DIR/$skill_name"
            # 移除衝突的 symlink 或檔案（非目錄），確保 cp -r 能正常寫入
            if [ -L "$target" ] || ([ -e "$target" ] && [ ! -d "$target" ]); then
                rm -f "$target"
            fi
            if [ ! -d "$target" ]; then
                cp -r "$skill_dir" "$target"
                echo "  ✓ Skill: $skill_name"
            else
                echo "  - Skill: $skill_name (已存在，跳過)"
            fi
        done
        chown -R developer:developer /home/developer/.claude
    fi

    # 複製預設 mcp.json 到 /workspace/.mcp.json（不覆蓋已存在的）
    if [ -f "$AGENT_DEFAULTS_DIR/mcp.json" ]; then
        if [ ! -f "/workspace/.mcp.json" ]; then
            cp "$AGENT_DEFAULTS_DIR/mcp.json" /workspace/.mcp.json
            chown developer:developer /workspace/.mcp.json
            echo "  ✓ MCP 配置已安裝"
        else
            echo "  - MCP 配置已存在，跳過"
        fi
    fi

    echo "✅ Agent 預設配置安裝完成"
else
    echo "⚠️  agent-defaults 目錄不存在，跳過預設配置安裝"
fi
echo ""

# ============================================================================
# 6. 設定 Git 配置
# ============================================================================
echo "🔧 設定 Git 配置..."
if [ -n "${GIT_USER_NAME:-}" ] && [ -n "${GIT_USER_EMAIL:-}" ]; then
    git config --global user.name "$GIT_USER_NAME"
    git config --global user.email "$GIT_USER_EMAIL"
    echo "✅ Git 用戶配置已設定"
else
    git config --global user.name "Developer"
    git config --global user.email "developer@workspace.local"
    echo "✅ Git 用戶使用默認配置"
fi
git config --global --add safe.directory /workspace 2>/dev/null || true
git config --global --add safe.directory /workspace-runtime 2>/dev/null || true
echo ""

# ============================================================================
# 7. Git Clone
# ============================================================================
if [ -n "${GIT_REPO_URL:-}" ]; then
    echo "🔀 克隆 Git 倉庫..."

    # 忽略 .git / .gitkeep，判斷工作區是否為空
    if [ -z "$(ls -A /workspace 2>/dev/null | grep -v '\.git' | grep -v '\.gitkeep')" ]; then
        GIT_BRANCH="${GIT_BRANCH:-main}"

        if [ -n "${SSH_PRIVATE_KEY:-}" ]; then
            echo "🔑 配置 SSH 密鑰..."
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
            echo "✅ SSH 密鑰已配置"
        fi

        cd /tmp
        git clone --branch "$GIT_BRANCH" "$GIT_REPO_URL" /tmp/repo-clone
        cp -r /tmp/repo-clone/* /workspace/ 2>/dev/null || true
        cp -r /tmp/repo-clone/.git /workspace/ 2>/dev/null || true
        rm -rf /tmp/repo-clone

        git config --global --add safe.directory /workspace
        git -C /workspace config --local user.name "${GIT_USER_NAME:-Developer}"
        git -C /workspace config --local user.email "${GIT_USER_EMAIL:-developer@workspace.local}"
        echo "✅ 倉庫克隆完成"
    else
        echo "⚠️  /workspace 目錄不為空，跳過克隆"
    fi
else
    echo "⚠️  GIT_REPO_URL 未設定，跳過 Git 克隆"
fi

/workspace-runtime/scripts/bootstrap_git_repo.sh

chown -R developer:developer /workspace 2>/dev/null || true
echo ""

# ============================================================================
# 8. 初始化 OpenSpec
# ============================================================================
echo "🧭 檢查 OpenSpec 初始化狀態..."
OPENSPEC_INIT_TOOLS="${OPENSPEC_INIT_TOOLS:-claude,codex,opencode,gemini}"
if [ "${OPENSPEC_AUTO_INIT:-1}" = "1" ]; then
    if command -v openspec >/dev/null 2>&1; then
        if [ ! -d "/workspace/openspec" ]; then
            echo "📋 執行 OpenSpec 初始化..."
            if HOME=/home/developer XDG_CONFIG_HOME=/home/developer/.config su developer -s /bin/bash -c "export PATH=/home/developer/.local/bin:/home/developer/.npm-global/bin:/home/developer/.cargo/bin:\$PATH; cd /workspace && openspec init --tools ${OPENSPEC_INIT_TOOLS}"; then
                echo "✅ OpenSpec 初始化完成"
                chown -R developer:developer /workspace /home/developer/.config /home/developer/.claude /home/developer/.codex 2>/dev/null || true
            else
                echo "⚠️  OpenSpec 初始化失敗，略過自動初始化"
            fi
        else
            echo "✅ OpenSpec 已初始化，跳過"
        fi
    else
        echo "⚠️  找不到 openspec CLI，跳過自動初始化"
    fi
else
    echo "⏭️  OPENSPEC_AUTO_INIT=0，跳過自動初始化"
fi
echo ""

# ============================================================================
# 9. 設定 SSH 密鑰
# ============================================================================
if [ -n "${SSH_PUBLIC_KEY:-}" ] && [ -n "${SSH_PRIVATE_KEY:-}" ]; then
    echo "🔑 設定 SSH 訪問..."
    mkdir -p /home/developer/.ssh
    echo "$SSH_PRIVATE_KEY" > /home/developer/.ssh/id_rsa
    chmod 600 /home/developer/.ssh/id_rsa
    echo "$SSH_PUBLIC_KEY" > /home/developer/.ssh/id_rsa.pub
    chmod 644 /home/developer/.ssh/id_rsa.pub
    echo "$SSH_PUBLIC_KEY" > /home/developer/.ssh/authorized_keys
    chmod 600 /home/developer/.ssh/authorized_keys
    chown -R developer:developer /home/developer/.ssh
    echo "✅ SSH 訪問已配置"
else
    echo "⚠️  SSH_PUBLIC_KEY 或 SSH_PRIVATE_KEY 未設定，跳過 SSH 密鑰配置"
fi
echo ""

# ============================================================================
# 10. 設定日誌目錄
# ============================================================================
echo "📋 設定日誌目錄..."
mkdir -p /var/log/supervisor
chown -R developer:developer /var/log/supervisor 2>/dev/null || true
echo "✅ 日誌目錄設定完成"
echo ""

# ============================================================================
# 11. 建立 Terminal Service 快取目錄
# ============================================================================
echo "🔧 準備 Terminal Service 快取目錄..."
mkdir -p "${WORKSPACE_TERMINAL_CACHE_DIR:-/workspace/.cache/terminal-service}"
chown -R developer:developer "${WORKSPACE_TERMINAL_CACHE_DIR:-/workspace/.cache/terminal-service}" 2>/dev/null || true
echo "✅ Terminal Service 將由 supervisord 啟動時自行解析 binary"
echo ""

# ============================================================================
# 12. 啟動 Supervisor
# ============================================================================
echo "🎯 啟動服務管理器..."

if [ "${NODE_ENV}" = "production" ]; then
    SUPERVISOR_CONFIG="/workspace-runtime/supervisord.conf"
    echo "📋 使用生產環境配置: $SUPERVISOR_CONFIG"
else
    SUPERVISOR_CONFIG="/workspace-runtime/supervisord.dev.conf"
    if [ ! -f "$SUPERVISOR_CONFIG" ]; then
        SUPERVISOR_CONFIG="/workspace-runtime/supervisord.conf"
        echo "📋 開發配置不存在，使用標準配置: $SUPERVISOR_CONFIG"
    else
        echo "📋 使用開發環境配置: $SUPERVISOR_CONFIG"
    fi
fi

echo ""
echo "✅ 所有服務已啟動"
echo ""
echo "🎉 Workspace Runtime 已準備就緒！"
echo ""
echo "📊 活動服務："
echo "   - FastAPI:          http://localhost:3002"
echo "   - SSH:              localhost:22"
echo "   - Terminal Service: http://localhost:3004"
echo "   - Canvas Runtime:  http://localhost:3003 (可選)"
echo ""

# nodaemon=true：前台運行，保持容器活動
exec /usr/bin/supervisord -c "$SUPERVISOR_CONFIG"
