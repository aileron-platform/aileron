# Multi-stage build for workspace-runtime
# go-terminal-builder -> base-common -> base-devtools -> development / production
#                                     -> kubernetes (skips base-devtools entirely)
# runtime-base is provided by a Bake target context.
ARG GO_IMAGE
FROM ${GO_IMAGE} AS go-terminal-builder

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

FROM runtime-base AS base-common

USER root

# Create runtime directory structure.
RUN mkdir -p /workspace-runtime /workspace /workspace-terminal /knowledge /var/log/supervisor

WORKDIR /workspace-runtime

ARG TZ=Asia/Taipei
ENV TZ=${TZ}
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# bubblewrap is Codex CLI's Linux sandbox and is needed everywhere Codex runs, including Kubernetes.
RUN apt-get update && apt-get install -y --fix-missing \
    bubblewrap \
    ca-certificates \
    curl \
    gnupg \
    supervisor \
    tzdata \
    locales \
    wget \
    && rm -rf /var/lib/apt/lists/*

RUN sed -i '/^# *en_US.UTF-8 UTF-8/s/^# *//' /etc/locale.gen \
    && locale-gen \
    && update-locale LANG=en_US.UTF-8
ENV LANG=en_US.UTF-8

# Keep image-managed defaults outside the persistent user home.
RUN mkdir -p /etc/ssh/ssh_config.d \
    && printf '%s\n' \
        'Host *' \
        '    StrictHostKeyChecking no' \
        '    UserKnownHostsFile=/dev/null' \
        > /etc/ssh/ssh_config.d/99-aileron.conf \
    && chmod 0644 /etc/ssh/ssh_config.d/99-aileron.conf \
    && printf '%s\n' \
        'export PYTHONPATH="/workspace-runtime:/workspace"' \
        'export PATH="/opt/aileron/bin:/opt/aileron/npm/bin:/workspace-runtime/.venv/bin:$HOME/.local/bin:$PATH"' \
        > /etc/profile.d/aileron.sh \
    && chmod 0644 /etc/profile.d/aileron.sh \
    && git config --system user.name "Developer" \
    && git config --system user.email "developer@workspace.local"

# Install platform-managed tools outside the persistent user home.
ARG CLAUDE_CLI_VERSION
ARG PLAYWRIGHT_CLI_VERSION
ARG CODEX_CLI_VERSION
ARG OPENCODE_VERSION
ARG OPENCODE_SHA256_AMD64
ARG OPENCODE_SHA256_ARM64
ARG TARGETARCH

ENV PATH="/opt/aileron/bin:/opt/aileron/npm/bin:$PATH"

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

RUN chmod +x /usr/local/bin/install-npm-global.sh \
    && mkdir -p /opt/aileron/bin /opt/aileron/npm

RUN --mount=type=cache,target=/var/cache/aileron-npm \
    NPM_CONFIG_PREFIX=/opt/aileron/npm \
    NPM_CONFIG_CACHE=/var/cache/aileron-npm \
    NPM_CONFIG_FETCH_RETRIES=5 \
    NPM_CONFIG_FETCH_RETRY_FACTOR=2 \
    NPM_CONFIG_FETCH_RETRY_MINTIMEOUT=10000 \
    NPM_CONFIG_FETCH_RETRY_MAXTIMEOUT=120000 \
    bash /usr/local/bin/install-npm-global.sh "@playwright/cli@${PLAYWRIGHT_CLI_VERSION}" \
    && NPM_CONFIG_PREFIX=/opt/aileron/npm \
       NPM_CONFIG_CACHE=/var/cache/aileron-npm \
       NPM_CONFIG_FETCH_RETRIES=5 \
       NPM_CONFIG_FETCH_RETRY_FACTOR=2 \
       NPM_CONFIG_FETCH_RETRY_MINTIMEOUT=10000 \
       NPM_CONFIG_FETCH_RETRY_MAXTIMEOUT=120000 \
       bash /usr/local/bin/install-npm-global.sh "@openai/codex@${CODEX_CLI_VERSION}" \
    && test -x /opt/aileron/npm/bin/playwright-cli \
    && test -x /opt/aileron/npm/bin/codex \
    && rm -f /usr/local/bin/install-npm-global.sh

RUN set -eu; \
    architecture="${TARGETARCH:-$(dpkg --print-architecture)}"; \
    case "${architecture}" in \
        amd64) asset_arch=x64; expected_sha256="${OPENCODE_SHA256_AMD64}" ;; \
        arm64) asset_arch=arm64; expected_sha256="${OPENCODE_SHA256_ARM64}" ;; \
        *) echo "Unsupported OpenCode architecture: ${architecture}" >&2; exit 1 ;; \
    esac; \
    archive="$(mktemp)"; \
    trap 'rm -f "${archive}"' EXIT HUP INT TERM; \
    curl --fail --silent --show-error --location --retry 5 --retry-all-errors \
        --output "${archive}" \
        "https://github.com/anomalyco/opencode/releases/download/v${OPENCODE_VERSION}/opencode-linux-${asset_arch}.tar.gz"; \
    printf '%s  %s\n' "${expected_sha256}" "${archive}" | sha256sum --check --strict; \
    verification_home="$(mktemp -d)"; \
    trap 'rm -f "${archive}"; rm -rf "${verification_home}"' EXIT HUP INT TERM; \
    tar -xzf "${archive}" -C /opt/aileron/bin opencode; \
    chmod 0555 /opt/aileron/bin/opencode; \
    test "$(HOME="${verification_home}" \
        XDG_CACHE_HOME="${verification_home}/.cache" \
        XDG_CONFIG_HOME="${verification_home}/.config" \
        XDG_DATA_HOME="${verification_home}/.local/share" \
        OPENCODE_DISABLE_AUTOUPDATE=1 \
        /opt/aileron/bin/opencode --version)" = "${OPENCODE_VERSION}"

COPY workspace-runtime/install-claude-cli.sh /usr/local/bin/install-claude-cli.sh
RUN chmod 0555 /usr/local/bin/install-claude-cli.sh && \
    /usr/local/bin/install-claude-cli.sh "${CLAUDE_CLI_VERSION}" && \
    rm -f /usr/local/bin/install-claude-cli.sh && \
    rm -rf /var/lib/apt/lists/*

RUN chown developer:developer /workspace-runtime /workspace /workspace-terminal /knowledge /var/log/supervisor && \
    chmod 755 /workspace /workspace-runtime /workspace-terminal /knowledge && \
    find /home/developer -mindepth 1 -maxdepth 1 -exec rm -rf -- {} +

# Anthropic settings are injected at runtime, not baked into the image.

ENV PYTHONPATH="/workspace-runtime:/workspace"
ENV PATH="/workspace-runtime/.venv/bin:${PATH}"
ENV DISABLE_AUTOUPDATER=1
ENV OPENCODE_DISABLE_AUTOUPDATE=1

# base-devtools: docker CLI, sshd and interactive tools for the non-Kubernetes
# (Docker-host) provisioner only. The Kubernetes target builds from base-common
# directly and never pulls in this layer, keeping the deployed image lean.
FROM base-common AS base-devtools

USER root

RUN mkdir -p /var/run/sshd

RUN apt-get update && apt-get install -y --no-install-recommends \
    docker-cli \
    docker-buildx \
    iptables \
    openssh-server \
    vim \
    nano \
    htop \
    && rm -rf /var/lib/apt/lists/*

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

# Add the docker group when the base image does not already provide it.
RUN usermod -aG docker developer 2>/dev/null || true

RUN ssh-keygen -A

# Stage 2: Development - source code is mounted through volumes.
FROM base-devtools AS development

COPY --chown=developer:developer workspace-runtime/pyproject.toml workspace-runtime/uv.lock* ./
COPY --chown=developer:developer workspace-runtime/vendor/ ./vendor/
COPY --chown=developer:developer packages/ /packages/
COPY --chown=developer:developer contracts/authorization/runtime-route-inventory.json ./contracts/authorization/runtime-route-inventory.json

USER developer
RUN --mount=type=cache,target=/tmp/uv-cache,uid=1000,gid=1000 \
    UV_CACHE_DIR=/tmp/uv-cache uv sync --dev

USER root
RUN test -z "$(find /home/developer -mindepth 1 -maxdepth 1 -print -quit)"

RUN mkdir -p /workspace-runtime/app /workspace-runtime/scripts
COPY --from=go-terminal-builder /opt/terminal-service/bin/terminal-service /opt/terminal-service/bin/terminal-service
COPY --chown=developer:developer workspace-runtime/scripts/ /workspace-runtime/scripts/
RUN chmod +x /workspace-runtime/scripts/*.sh /opt/terminal-service/bin/terminal-service

EXPOSE 3002 3004 22

HEALTHCHECK --interval=5s --timeout=5s --start-period=15s --retries=12 \
    CMD curl --fail --silent --show-error --max-time 3 http://localhost:3002/health || exit 1

COPY workspace-runtime/start_services.sh /start_services.sh
COPY workspace-runtime/supervisord.conf workspace-runtime/supervisord.dev.conf ./
COPY workspace-runtime/agent-defaults/ /opt/aileron/agent-defaults/
RUN find /opt/aileron/agent-defaults -type d -exec chmod a+rx {} + \
    && find /opt/aileron/agent-defaults -type f -exec chmod a+r {} +
RUN chmod +x /start_services.sh

# The container runs as root for sshd; app services run as developer in supervisord.dev.conf.
ENTRYPOINT []
CMD ["/start_services.sh"]

# Stage 3: Production - application code is packaged into the image.
FROM base-devtools AS production

COPY --chown=developer:developer workspace-runtime/pyproject.toml workspace-runtime/uv.lock* ./
COPY --chown=developer:developer workspace-runtime/vendor/ ./vendor/
COPY --chown=developer:developer packages/ /packages/
COPY --chown=developer:developer contracts/authorization/runtime-route-inventory.json ./contracts/authorization/runtime-route-inventory.json

USER developer
RUN --mount=type=cache,target=/tmp/uv-cache,uid=1000,gid=1000 \
    UV_CACHE_DIR=/tmp/uv-cache uv sync --no-dev

USER root
RUN test -z "$(find /home/developer -mindepth 1 -maxdepth 1 -print -quit)"

COPY --chown=developer:developer workspace-runtime/app/ ./app/

RUN mkdir -p /workspace-runtime/scripts
COPY --chown=developer:developer workspace-runtime/scripts/ /workspace-runtime/scripts/
RUN chmod +x /workspace-runtime/scripts/*.sh
COPY --from=go-terminal-builder /opt/terminal-service/bin/terminal-service /opt/terminal-service/bin/terminal-service
RUN chmod +x /opt/terminal-service/bin/terminal-service

COPY workspace-runtime/start_services.sh /start_services.sh
COPY workspace-runtime/supervisord.conf workspace-runtime/supervisord.dev.conf ./
COPY workspace-runtime/agent-defaults/ /opt/aileron/agent-defaults/
RUN find /opt/aileron/agent-defaults -type d -exec chmod a+rx {} + \
    && find /opt/aileron/agent-defaults -type f -exec chmod a+r {} +
RUN chmod +x /start_services.sh

EXPOSE 3002 3004 22

HEALTHCHECK --interval=5s --timeout=5s --start-period=15s --retries=12 \
    CMD curl --fail --silent --show-error --max-time 3 http://localhost:3002/health || exit 1

# The container runs as root for sshd; app services run as developer in supervisord.conf.
CMD ["/start_services.sh"]

# Stage 4: Kubernetes - application code packaged directly on base-common, so the
# deployed image never pulls in base-devtools (Docker client plugins,
# openssh-server, sshd config, vim/nano/htop). No rootful bootstrap, sshd or
# Docker tooling.
FROM base-common AS kubernetes

COPY --chown=developer:developer workspace-runtime/pyproject.toml workspace-runtime/uv.lock* ./
COPY --chown=developer:developer workspace-runtime/vendor/ ./vendor/
COPY --chown=developer:developer packages/ /packages/
COPY --chown=developer:developer contracts/authorization/runtime-route-inventory.json ./contracts/authorization/runtime-route-inventory.json

USER developer
RUN --mount=type=cache,target=/tmp/uv-cache,uid=1000,gid=1000 \
    UV_CACHE_DIR=/tmp/uv-cache uv sync --no-dev

USER root
RUN test -z "$(find /home/developer -mindepth 1 -maxdepth 1 -print -quit)"

COPY --chown=developer:developer workspace-runtime/app/ ./app/

RUN mkdir -p /workspace-runtime/scripts
COPY --chown=developer:developer workspace-runtime/scripts/ /workspace-runtime/scripts/
RUN chmod +x /workspace-runtime/scripts/*.sh
COPY workspace-runtime/agent-defaults/ /opt/aileron/agent-defaults/
RUN find /opt/aileron/agent-defaults -type d -exec chmod a+rx {} + \
    && find /opt/aileron/agent-defaults -type f -exec chmod a+r {} +
COPY --from=go-terminal-builder /opt/terminal-service/bin/terminal-service /opt/terminal-service/bin/terminal-service
RUN chmod +x /opt/terminal-service/bin/terminal-service

RUN (getent group 10001 >/dev/null || groupadd --gid 10001 aileron) \
    && (getent passwd 10001 >/dev/null || useradd --uid 10001 --gid 10001 --home-dir /home/developer --no-create-home --shell /usr/sbin/nologin aileron) \
    && mkdir -p /home/developer /tmp/supervisor \
    && chown 10001:10001 /home/developer \
    && chmod 1777 /tmp

COPY workspace-runtime/supervisord.kubernetes.conf /workspace-runtime/supervisord.kubernetes.conf
COPY workspace-runtime/start_services.kubernetes.sh /start_services.kubernetes.sh
RUN chmod 0555 /start_services.kubernetes.sh

ENV HOME=/home/developer \
    UV_CACHE_DIR=/tmp/uv-cache \
    PATH=/opt/aileron/bin:/opt/aileron/npm/bin:/workspace-runtime/.venv/bin:/home/developer/.local/bin:/usr/local/bin:/usr/bin:/bin

EXPOSE 3002 3004

HEALTHCHECK --interval=5s --timeout=5s --start-period=15s --retries=12 \
    CMD curl --fail --silent --show-error --max-time 3 http://localhost:3002/health || exit 1

USER 10001:10001

ENTRYPOINT []
CMD ["/start_services.kubernetes.sh"]
