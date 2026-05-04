# Multi-stage build for workspace-runtime
# Stage 1: go-terminal-builder / Stage 2: base / Stage 3: development / Stage 4: production
# runtime-base can be provided by build context, for example:
#   1. codex-universal
#   2. workspace-runtime/base-lite
FROM golang:1.23 AS go-terminal-builder

WORKDIR /workspace-terminal

COPY workspace-terminal/go.mod workspace-terminal/go.sum ./
RUN go mod download
COPY workspace-terminal/ ./

ARG TARGETARCH
RUN mkdir -p /opt/terminal-service/bin && \
    GOARCH_VALUE="${TARGETARCH:-$(go env GOARCH)}" && \
    case "${GOARCH_VALUE}" in \
        amd64|arm64) ;; \
        x86_64) GOARCH_VALUE="amd64" ;; \
        aarch64) GOARCH_VALUE="arm64" ;; \
        *) echo "Unsupported TARGETARCH: ${GOARCH_VALUE}" >&2; exit 1 ;; \
    esac && \
    CGO_ENABLED=0 GOOS=linux GOARCH="${GOARCH_VALUE}" go build -o /opt/terminal-service/bin/terminal-service ./cmd/server && \
    chmod +x /opt/terminal-service/bin/terminal-service

FROM runtime-base AS base

USER root

# Create runtime directory structure.
RUN mkdir -p /workspace-runtime /workspace /workspace-terminal /knowledge /var/run/sshd /var/log/supervisor

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

RUN locale-gen en_US.UTF-8 && update-locale LANG=en_US.UTF-8
ENV LANG=en_US.UTF-8

# SSH: disable password authentication and allow only developer key login.
RUN sed -i 's/#PermitRootLogin prohibit-password/PermitRootLogin no/' /etc/ssh/sshd_config \
    && sed -i 's/#PasswordAuthentication yes/PasswordAuthentication no/' /etc/ssh/sshd_config \
    && sed -i 's/PasswordAuthentication yes/PasswordAuthentication no/' /etc/ssh/sshd_config \
    && sed -i 's/#PubkeyAuthentication yes/PubkeyAuthentication yes/' /etc/ssh/sshd_config \
    && sed -i 's/#AuthorizedKeysFile/AuthorizedKeysFile/' /etc/ssh/sshd_config \
    && sed -i 's/#ChallengeResponseAuthentication yes/ChallengeResponseAuthentication no/' /etc/ssh/sshd_config \
    && sed -i 's/ChallengeResponseAuthentication yes/ChallengeResponseAuthentication no/' /etc/ssh/sshd_config \
    && sed -i 's@session\s*required\s*pam_loginuid.so@session optional pam_loginuid.so@g' /etc/pam.d/sshd \
    && echo 'AllowUsers developer' >> /etc/ssh/sshd_config

# The base image already creates the developer user (UID 1000); add SSH config.
RUN mkdir -p /home/developer/.ssh \
    && echo 'Host *' > /home/developer/.ssh/config \
    && echo '    StrictHostKeyChecking no' >> /home/developer/.ssh/config \
    && echo '    UserKnownHostsFile=/dev/null' >> /home/developer/.ssh/config \
    && chown -R developer:developer /home/developer/.ssh \
    && chmod 700 /home/developer/.ssh \
    && chmod 600 /home/developer/.ssh/config

# Add the docker group when the base image does not already provide it.
RUN usermod -aG docker developer 2>/dev/null || true

# Allow developer to access the root Cargo toolchain when the base image provides it.
RUN mkdir -p /home/developer/.cargo && \
    (chmod o+x /root 2>/dev/null || true) && \
    (chmod 755 /root/.cargo /root/.cargo/bin 2>/dev/null || true) && \
    (ln -sf /root/.cargo/bin /home/developer/.cargo/bin || true) && \
    (chown developer:developer /home/developer/.cargo 2>/dev/null || true) && \
    if [ -f /root/.cargo/env ]; then ln -sf /root/.cargo/env /home/developer/.cargo/env 2>/dev/null || true; fi

# Configure developer .bashrc environment variables and PATH.
RUN echo 'export PYTHONPATH="/workspace-runtime:/workspace"' >> /home/developer/.bashrc && \
    echo 'export CARGO_HOME="/home/developer/.cargo"' >> /home/developer/.bashrc && \
    echo 'export RUSTUP_HOME="/root/.rustup"' >> /home/developer/.bashrc && \
    echo 'if [ -f "$HOME/.cargo/env" ]; then source "$HOME/.cargo/env" 2>/dev/null || true; fi' >> /home/developer/.bashrc && \
    echo 'export PATH="$HOME/.local/bin:$HOME/.npm-global/bin:$HOME/.cargo/bin:$PATH"' >> /home/developer/.bashrc && \
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

# Install global tools as developer.
ARG OPENSPEC_VERSION=1.3.0
ARG CLAUDE_CLI_VERSION=stable
ARG GEMINI_VERSION=0.40.0
ARG AGENT_BROWSER_CLI_VERSION=latest
ARG CODEX_CLI_VERSION=latest
RUN printf '%s\n' \
    '#!/bin/sh' \
    'set -eu' \
    '' \
    'package="$1"' \
    'attempts=0' \
    'until [ "$attempts" -ge 3 ]; do' \
    '    if npm install -g "$package"; then' \
    '        exit 0' \
    '    fi' \
    '    attempts=$((attempts + 1))' \
    '    echo "npm install failed for ${package}, retry ${attempts}/3" >&2' \
    '    sleep 5' \
    'done' \
    '' \
    'echo "npm install failed for ${package} after 3 attempts" >&2' \
    'exit 1' \
    > /usr/local/bin/install-npm-global.sh

RUN chmod +x /usr/local/bin/install-npm-global.sh && \
    mkdir -p /home/developer/.agent-browser && \
    mkdir -p /home/developer/.config/opencode && \
    mkdir -p /home/developer/.npm && \
    mkdir -p /home/developer/.npm-global && \
    chown -R developer:developer /home/developer/.agent-browser /home/developer/.config/opencode /home/developer/.npm /home/developer/.npm-global

USER developer
RUN if command -v mise >/dev/null 2>&1; then mise use -g node@lts; fi && \
    npm config set cache /home/developer/.npm && \
    npm config set prefix /home/developer/.npm-global && \
    npm config set fetch-retries 5 && \
    npm config set fetch-retry-factor 2 && \
    npm config set fetch-retry-mintimeout 10000 && \
    npm config set fetch-retry-maxtimeout 120000
RUN bash /usr/local/bin/install-npm-global.sh "@fission-ai/openspec@${OPENSPEC_VERSION}"
RUN bash /usr/local/bin/install-npm-global.sh "@google/gemini-cli@${GEMINI_VERSION}"
RUN gemini --version | grep -F "${GEMINI_VERSION}"
RUN bash /usr/local/bin/install-npm-global.sh "agent-browser@${AGENT_BROWSER_CLI_VERSION}"
RUN curl -fsSL https://opencode.ai/install | bash
RUN bash /usr/local/bin/install-npm-global.sh "@openai/codex@${CODEX_CLI_VERSION}"
RUN curl -fsSL https://claude.ai/install.sh | bash -s "${CLAUDE_CLI_VERSION}"

USER root

RUN chown -R developer:developer /workspace-runtime /workspace /workspace-terminal /knowledge /var/log/supervisor && \
    chmod 755 /workspace /workspace-runtime /workspace-terminal /knowledge

# Anthropic settings are injected at runtime, not baked into the image.

ENV PATH="/home/developer/.local/bin:/home/developer/.npm-global/bin:$PATH"

ENV PYTHONPATH="/workspace-runtime:/workspace"
ENV DISABLE_AUTOUPDATER=1
ENV OPENSPEC_AUTO_INIT=1
ENV OPENSPEC_INIT_TOOLS="claude,codex,opencode,gemini"

# Stage 2: Development - source code is mounted through volumes.
FROM base AS development

COPY --chown=developer:developer workspace-runtime/pyproject.toml workspace-runtime/uv.lock* ./
COPY --chown=developer:developer workspace-runtime/vendor/ ./vendor/

USER developer
RUN uv sync --dev

USER root

RUN mkdir -p /workspace-runtime/app /workspace-runtime/scripts
COPY --from=go-terminal-builder /opt/terminal-service/bin/terminal-service /opt/terminal-service/bin/terminal-service
COPY workspace-runtime/scripts/ /workspace-runtime/scripts/
COPY workspace-terminal/ /workspace-terminal/
RUN chmod +x /workspace-runtime/scripts/*.sh /opt/terminal-service/bin/terminal-service

EXPOSE 3002 3004 22

HEALTHCHECK --interval=30s --timeout=30s --start-period=20s --retries=3 \
    CMD curl -f http://localhost:3002/health || exit 1

COPY workspace-runtime/start_services.sh /start_services.sh
COPY workspace-runtime/supervisord.conf workspace-runtime/supervisord.dev.conf ./
COPY workspace-runtime/agent-defaults/ ./agent-defaults/
RUN chmod +x /start_services.sh

# The container runs as root for sshd; app services run as developer in supervisord.dev.conf.
ENTRYPOINT []
CMD ["/start_services.sh"]

# Stage 3: Production - application code is packaged into the image.
FROM base AS production

COPY --chown=developer:developer workspace-runtime/pyproject.toml workspace-runtime/uv.lock* ./
COPY --chown=developer:developer workspace-runtime/vendor/ ./vendor/

USER developer
RUN uv sync --no-dev

USER root

COPY workspace-runtime/app/ ./app/
COPY workspace-runtime/.env* ./

RUN mkdir -p /workspace-runtime/scripts
COPY workspace-runtime/scripts/ /workspace-runtime/scripts/
RUN chmod +x /workspace-runtime/scripts/*.sh
COPY --from=go-terminal-builder /opt/terminal-service/bin/terminal-service /opt/terminal-service/bin/terminal-service
RUN chmod +x /opt/terminal-service/bin/terminal-service

RUN mkdir -p /workspace-terminal
WORKDIR /workspace-terminal
COPY workspace-terminal/ ./
WORKDIR /workspace-runtime

RUN chown -R developer:developer /workspace-runtime /workspace /workspace-terminal /knowledge && \
    chmod 755 /workspace /workspace-runtime /workspace-terminal /knowledge

COPY workspace-runtime/start_services.sh /start_services.sh
COPY workspace-runtime/supervisord.conf workspace-runtime/supervisord.dev.conf ./
COPY workspace-runtime/agent-defaults/ ./agent-defaults/
RUN chmod +x /start_services.sh

EXPOSE 3002 3004 22

HEALTHCHECK --interval=30s --timeout=30s --start-period=20s --retries=3 \
    CMD curl -f http://localhost:3002/health || exit 1

# The container runs as root for sshd; app services run as developer in supervisord.conf.
CMD ["/start_services.sh"]
