# Multi-stage build for workspace-runtime
# Stage 1: base → Stage 2: development / Stage 3: production
# codex-universal 可由下列任一方式提供：
#   1. docker buildx bake（自動從 codex-universal/Dockerfile 建置，推薦）
#   2. 預先建置的映像：docker build --build-context codex-universal=docker-image://codex-universal:custom
FROM codex-universal AS base

USER root

# 建立目錄結構
RUN mkdir -p /workspace-runtime /workspace /workspace-terminal /var/run/sshd /var/log/supervisor

WORKDIR /workspace-runtime

ARG TZ=Asia/Taipei
ENV TZ=${TZ}
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

RUN apt-get update && apt-get install -y --fix-missing \
    docker.io \
    openssh-server \
    supervisor \
    tzdata \
    vim \
    nano \
    htop \
    locales \
    wget \
    && rm -rf /var/lib/apt/lists/*

# 安裝 Go（用於編譯 workspace-terminal）
ENV GO_VERSION=1.23.4
RUN ARCH=$(dpkg --print-architecture) && \
    if [ "$ARCH" = "amd64" ]; then GO_ARCH="amd64"; \
    elif [ "$ARCH" = "arm64" ]; then GO_ARCH="arm64"; \
    else GO_ARCH="amd64"; fi && \
    wget -q https://go.dev/dl/go${GO_VERSION}.linux-${GO_ARCH}.tar.gz && \
    tar -C /usr/local -xzf go${GO_VERSION}.linux-${GO_ARCH}.tar.gz && \
    rm go${GO_VERSION}.linux-${GO_ARCH}.tar.gz
ENV PATH="/usr/local/go/bin:${PATH}"

RUN locale-gen en_US.UTF-8 && update-locale LANG=en_US.UTF-8
ENV LANG=en_US.UTF-8

# SSH：停用密碼驗證，僅允許 developer 使用金鑰登入
RUN sed -i 's/#PermitRootLogin prohibit-password/PermitRootLogin no/' /etc/ssh/sshd_config \
    && sed -i 's/#PasswordAuthentication yes/PasswordAuthentication no/' /etc/ssh/sshd_config \
    && sed -i 's/PasswordAuthentication yes/PasswordAuthentication no/' /etc/ssh/sshd_config \
    && sed -i 's/#PubkeyAuthentication yes/PubkeyAuthentication yes/' /etc/ssh/sshd_config \
    && sed -i 's/#AuthorizedKeysFile/AuthorizedKeysFile/' /etc/ssh/sshd_config \
    && sed -i 's/#ChallengeResponseAuthentication yes/ChallengeResponseAuthentication no/' /etc/ssh/sshd_config \
    && sed -i 's/ChallengeResponseAuthentication yes/ChallengeResponseAuthentication no/' /etc/ssh/sshd_config \
    && sed -i 's@session\s*required\s*pam_loginuid.so@session optional pam_loginuid.so@g' /etc/pam.d/sshd \
    && echo 'AllowUsers developer' >> /etc/ssh/sshd_config

# codex-universal 已建立 developer 用戶（UID 1000），補充 SSH config
RUN mkdir -p /home/developer/.ssh \
    && echo 'Host *' > /home/developer/.ssh/config \
    && echo '    StrictHostKeyChecking no' >> /home/developer/.ssh/config \
    && echo '    UserKnownHostsFile=/dev/null' >> /home/developer/.ssh/config \
    && chown -R developer:developer /home/developer/.ssh \
    && chmod 700 /home/developer/.ssh \
    && chmod 600 /home/developer/.ssh/config

# 加入 docker 群組（codex-universal 未預設）
RUN usermod -aG docker developer 2>/dev/null || true

# 讓 developer 可存取 root 的 Rust 工具鏈（symlink cargo bin）
RUN mkdir -p /home/developer/.cargo && \
    chmod 755 /root/.cargo 2>/dev/null || true && \
    ln -sf /root/.cargo/bin /home/developer/.cargo/bin || true && \
    chown developer:developer /home/developer/.cargo 2>/dev/null || true && \
    if [ -f /root/.cargo/env ]; then ln -sf /root/.cargo/env /home/developer/.cargo/env 2>/dev/null || true; fi

# developer .bashrc：環境變數與 PATH
# Java 直接路徑放在 mise shims 之前，避免 PTY 環境下 mise shim 卡住
RUN echo 'export PYTHONPATH="/workspace-runtime:/workspace"' >> /home/developer/.bashrc && \
    echo 'export CARGO_HOME="/home/developer/.cargo"' >> /home/developer/.bashrc && \
    echo 'export RUSTUP_HOME="/root/.rustup"' >> /home/developer/.bashrc && \
    echo 'if [ -f "$HOME/.cargo/env" ]; then source "$HOME/.cargo/env" 2>/dev/null || true; fi' >> /home/developer/.bashrc && \
    echo 'export PATH="/root/.local/share/mise/installs/java/21/bin:/root/.local/share/mise/installs/java/17/bin:$HOME/.local/bin:$HOME/.npm-global/bin:$HOME/.cargo/bin:$PATH"' >> /home/developer/.bashrc && \
    echo "export PS1='\$(whoami)@\$(hostname -s):\${PWD}\$ '" >> /home/developer/.bashrc && \
    chown developer:developer /home/developer/.bashrc

RUN git config --global --add safe.directory /workspace && \
    git config --global --add safe.directory /workspace-runtime && \
    ssh-keygen -A

USER developer
RUN git config --global --add safe.directory /workspace 2>/dev/null || true && \
    git config --global --add safe.directory /workspace-runtime 2>/dev/null || true && \
    git config --global user.name "Developer" 2>/dev/null || true && \
    git config --global user.email "developer@workspace.local" 2>/dev/null || true

USER root

# 以 developer 身份安裝全域工具
ARG OPENSPEC_VERSION=1.3.0
ARG CLAUDE_CLI_VERSION=stable
ARG GEMINI_VERSION=latest
ARG AGENT_BROWSER_CLI_VERSION=latest
ARG CODEX_CLI_VERSION=latest
RUN cat <<'EOF' > /usr/local/bin/install-npm-global.sh
#!/bin/sh
set -eu

package="$1"
attempts=0
until [ "$attempts" -ge 3 ]; do
    if npm install -g "$package"; then
        exit 0
    fi
    attempts=$((attempts + 1))
    echo "npm install failed for ${package}, retry ${attempts}/3" >&2
    sleep 5
done

echo "npm install failed for ${package} after 3 attempts" >&2
exit 1
EOF

RUN chmod +x /usr/local/bin/install-npm-global.sh && \
    mkdir -p /home/developer/.agent-browser && \
    mkdir -p /home/developer/.config/opencode && \
    chown -R developer:developer /home/developer/.agent-browser /home/developer/.config/opencode

USER developer
RUN mise use -g node@lts && \
    npm config set fetch-retries 5 && \
    npm config set fetch-retry-factor 2 && \
    npm config set fetch-retry-mintimeout 10000 && \
    npm config set fetch-retry-maxtimeout 120000
RUN /usr/local/bin/install-npm-global.sh "@fission-ai/openspec@${OPENSPEC_VERSION}"
RUN /usr/local/bin/install-npm-global.sh "@google/gemini-cli@${GEMINI_VERSION}"
RUN /usr/local/bin/install-npm-global.sh "agent-browser@${AGENT_BROWSER_CLI_VERSION}"
RUN curl -fsSL https://opencode.ai/install | bash
RUN /usr/local/bin/install-npm-global.sh "@openai/codex@${CODEX_CLI_VERSION}"
RUN curl -fsSL https://claude.ai/install.sh | bash -s "${CLAUDE_CLI_VERSION}"

USER root

RUN chown -R developer:developer /workspace-runtime /workspace /workspace-terminal && \
    chmod 755 /workspace /workspace-runtime /workspace-terminal

# Anthropic 設定由執行時環境變數注入，不在映像中提供預設值

# Java 直接路徑放在 mise shims 之前，避免 PTY 環境下 mise shim 卡住
ENV PATH="/home/developer/.local/share/mise/installs/java/21/bin:/home/developer/.local/share/mise/installs/java/17/bin:/home/developer/.local/bin:/home/developer/.npm-global/bin:$PATH"

# /etc/profile.d/ 腳本確保 mise activate 覆蓋 PATH 後 Java 路徑仍正確
RUN echo '#!/bin/bash' > /etc/profile.d/fix-mise-path.sh && \
    echo 'export PATH="/home/developer/.local/share/mise/installs/java/21/bin:/home/developer/.local/share/mise/installs/java/17/bin:$PATH"' >> /etc/profile.d/fix-mise-path.sh && \
    chmod +x /etc/profile.d/fix-mise-path.sh

ENV PYTHONPATH="/workspace-runtime:/workspace"
ENV DISABLE_AUTOUPDATER=1
ENV OPENSPEC_AUTO_INIT=1
ENV OPENSPEC_INIT_TOOLS="claude,codex,opencode,gemini"

# Stage 2: Development - 程式碼透過 volume mount 掛入
FROM base AS development

COPY --chown=developer:developer workspace-runtime/pyproject.toml workspace-runtime/uv.lock* ./

USER developer
RUN uv sync --dev

USER root

RUN mkdir -p /workspace-runtime/app /workspace-runtime/scripts

EXPOSE 3002 3004 22

# 修復 /root 目錄訪問權限（developer 需存取 pyenv/nvm/cargo 等工具）
RUN chmod o+rx /root 2>/dev/null || true && \
    chmod o+rx /root/.pyenv 2>/dev/null || true && \
    chmod o+rwx /root/.pyenv/shims 2>/dev/null || true && \
    chmod o+rx /root/.nvm 2>/dev/null || true && \
    chmod o+rx /root/.nvm/versions 2>/dev/null || true && \
    chmod o+rx /root/.cargo 2>/dev/null || true && \
    chmod o+rx /root/.cargo/bin 2>/dev/null || true && \
    chmod o+rx /root/.local 2>/dev/null || true && \
    chmod o+rx /root/.local/bin 2>/dev/null || true && \
    chmod o+rx /root/.local/share 2>/dev/null || true && \
    chmod o+rx /root/.local/share/mise 2>/dev/null || true && \
    chmod o+rwx /root/.local/share/mise/shims 2>/dev/null || true

HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:3002/health || exit 1

COPY workspace-runtime/start_services.sh /start_services.sh
COPY workspace-runtime/supervisord.conf workspace-runtime/supervisord.dev.conf ./
COPY workspace-runtime/agent-defaults/ ./agent-defaults/
RUN chmod +x /start_services.sh

# 容器以 root 執行（sshd 需要），應用服務以 developer 執行（supervisord.dev.conf 中設定）
ENTRYPOINT []
CMD ["/start_services.sh"]

# Stage 3: Production - 應用程式打包進容器
FROM base AS production

COPY --chown=developer:developer workspace-runtime/pyproject.toml workspace-runtime/uv.lock* ./

USER developer
RUN uv sync --no-dev

USER root

COPY workspace-runtime/app/ ./app/
COPY workspace-runtime/.env* ./

RUN mkdir -p /workspace-runtime/scripts
COPY workspace-runtime/scripts/ /workspace-runtime/scripts/
RUN chmod +x /workspace-runtime/scripts/*.sh

# 編譯 workspace-terminal Go 服務
RUN mkdir -p /workspace-terminal
WORKDIR /workspace-terminal
COPY workspace-terminal/go.mod workspace-terminal/go.sum ./
RUN go mod download
COPY workspace-terminal/ ./
RUN rm -rf bin && mkdir -p bin
ARG GOARCH=arm64
RUN CGO_ENABLED=0 GOOS=linux GOARCH=${GOARCH} go build -o bin/terminal-service ./cmd/server && \
    chmod +x bin/terminal-service
WORKDIR /workspace-runtime

RUN chown -R developer:developer /workspace-runtime /workspace /workspace-terminal && \
    chmod 755 /workspace /workspace-runtime /workspace-terminal

# 修復 /root 目錄訪問權限（developer 需存取 pyenv/nvm/cargo 等工具）
RUN chmod o+rx /root 2>/dev/null || true && \
    chmod o+rx /root/.pyenv 2>/dev/null || true && \
    chmod o+rwx /root/.pyenv/shims 2>/dev/null || true && \
    chmod o+rx /root/.nvm 2>/dev/null || true && \
    chmod o+rx /root/.nvm/versions 2>/dev/null || true && \
    chmod o+rx /root/.cargo 2>/dev/null || true && \
    chmod o+rx /root/.cargo/bin 2>/dev/null || true && \
    chmod o+rx /root/.local 2>/dev/null || true && \
    chmod o+rx /root/.local/bin 2>/dev/null || true && \
    chmod o+rx /root/.local/share 2>/dev/null || true && \
    chmod o+rx /root/.local/share/mise 2>/dev/null || true && \
    chmod o+rwx /root/.local/share/mise/shims 2>/dev/null || true

COPY workspace-runtime/start_services.sh /start_services.sh
COPY workspace-runtime/supervisord.conf workspace-runtime/supervisord.dev.conf ./
COPY workspace-runtime/agent-defaults/ ./agent-defaults/
RUN chmod +x /start_services.sh

EXPOSE 3002 3004 22

HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:3002/health || exit 1

# 容器以 root 執行（sshd 需要），應用服務以 developer 執行（supervisord.conf 中設定）
CMD ["/start_services.sh"]
