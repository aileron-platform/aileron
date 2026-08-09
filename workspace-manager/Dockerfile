# Multi-stage build for workspace-manager
ARG PYTHON_IMAGE
ARG NODE_IMAGE

FROM ${NODE_IMAGE} AS node-toolchain

FROM ${PYTHON_IMAGE} AS base

# Set working directory
WORKDIR /workspace-manager

# Install system dependencies including Docker CLI, supervisor and tzdata.
RUN apt-get update && apt-get install -y \
    curl \
    wget \
    git \
    libatomic1 \
    docker.io \
    supervisor \
    redis-tools \
    tzdata \
    && rm -rf /var/lib/apt/lists/*

# Install the Bake-selected Node.js and npm toolchain.
COPY --from=node-toolchain /usr/local/ /usr/local/
ARG NPM_VERSION
RUN npm install -g "npm@${NPM_VERSION}" \
    && test "$(npm --version)" = "${NPM_VERSION}"

# Set timezone (can be overridden by environment variable)
ARG TZ=Asia/Taipei
ARG DEBIAN_FRONTEND=noninteractive
ENV TZ=${TZ}
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# Install uv.
ARG UV_VERSION
RUN pip install --no-cache-dir "uv==${UV_VERSION}"

ARG CODEX_CLI_VERSION
RUN npm install -g "@openai/codex@${CODEX_CLI_VERSION}" && \
    codex --version

# Development stage: mount code instead of copying it.
FROM base AS development

# Copy project files for dependency installation
COPY workspace-manager/pyproject.toml workspace-manager/uv.lock* workspace-manager/README.md ./
COPY packages/ /packages/
COPY contracts/ /contracts/

# Install dependencies with uv (including dev dependencies)
RUN uv sync --dev

# Create the app directory structure. Code is mounted at runtime.
RUN mkdir -p /workspace-manager/app

# Create data directories with proper permissions
RUN mkdir -p /data/init-scripts \
    && chmod -R 755 /data

# Copy scripts and supervisor configs
COPY workspace-manager/scripts/ ./scripts/
COPY workspace-manager/supervisord.conf workspace-manager/supervisord.dev.conf ./
RUN chmod +x ./scripts/*.sh

# Expose port
EXPOSE 3001

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://127.0.0.1:3001/health || exit 1

# Run FastAPI, Celery Worker and Flower using Supervisor
CMD ["/workspace-manager/scripts/start_services.sh"]

# Production stage: package the application into the container.
FROM base AS production

# Copy project files
COPY workspace-manager/pyproject.toml workspace-manager/uv.lock* workspace-manager/README.md ./
COPY packages/ /packages/
COPY contracts/ /contracts/

# Install dependencies with uv (production only, no dev dependencies)
RUN uv sync --no-dev

# Copy the full application code into the container.
COPY workspace-manager/app/ ./app/
COPY workspace-manager/scripts/ ./scripts/
COPY workspace-manager/supervisord.conf workspace-manager/supervisord.dev.conf ./
RUN chmod +x ./scripts/*.sh

# Create data directories with proper permissions
RUN mkdir -p /data/init-scripts \
    && chmod -R 755 /data

# For Docker socket access, run as root in production
# In production environment, this should be properly configured with correct group permissions
# RUN useradd --create-home --shell /bin/bash app \
#     && chown -R app:app /app
# USER app

# Expose port
EXPOSE 3001

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://127.0.0.1:3001/health || exit 1

# Run both FastAPI and Celery Worker (production)
CMD ["/workspace-manager/scripts/start_services.sh"]

# Build the Kubernetes Python environment without carrying build tooling into the
# final image.
FROM ${PYTHON_IMAGE} AS kubernetes-python-builder

WORKDIR /workspace-manager

COPY workspace-manager/pyproject.toml workspace-manager/uv.lock* workspace-manager/README.md ./
COPY packages/ /packages/

ARG UV_VERSION
ARG SUPERVISOR_VERSION
RUN pip install --no-cache-dir "uv==${UV_VERSION}" \
    && uv sync --frozen --no-dev \
    && uv pip install --python /workspace-manager/.venv/bin/python "supervisor==${SUPERVISOR_VERSION}"

# Extract the platform-native Codex executable. Node and npm are build-time only.
FROM ${NODE_IMAGE} AS kubernetes-codex-builder

ARG CODEX_CLI_VERSION

RUN --mount=type=cache,target=/root/.npm \
    npm install -g --omit=dev "@openai/codex@${CODEX_CLI_VERSION}" \
    && codex_binary="$(find /usr/local/lib/node_modules/@openai -type f -path '*/vendor/*/bin/codex' -print -quit)" \
    && test -n "${codex_binary}" \
    && install -D -m 0755 "${codex_binary}" /opt/aileron/bin/codex \
    && /opt/aileron/bin/codex --version

# Kubernetes stage: a slim, immutable image with no Docker daemon/client layer.
FROM ${PYTHON_IMAGE} AS kubernetes

ARG TZ=Asia/Taipei

ENV TZ=${TZ} \
    AILERON_EXECUTION_PROFILE=kubernetes \
    HOME=/state/home \
    CODEX_HOME=/state/codex \
    PATH=/workspace-manager/.venv/bin:${PATH} \
    PYTHONPATH=/workspace-manager \
    UV_CACHE_DIR=/tmp/uv-cache

WORKDIR /workspace-manager

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        bash \
        ca-certificates \
        curl \
        git \
        grep \
        openssh-client \
        tzdata \
    && rm -rf /var/lib/apt/lists/* \
    && ln -snf "/usr/share/zoneinfo/${TZ}" /etc/localtime \
    && printf '%s\n' "${TZ}" > /etc/timezone \
    && groupadd --gid 10001 aileron \
    && useradd --uid 10001 --gid 10001 --home-dir /state/home --no-create-home --shell /usr/sbin/nologin aileron \
    && mkdir -p /state /tmp/supervisor \
    && chmod 1777 /tmp

RUN /usr/local/bin/python -m pip uninstall -y pip setuptools wheel

COPY --from=kubernetes-python-builder /workspace-manager/.venv /workspace-manager/.venv
COPY --from=kubernetes-python-builder /packages /packages
COPY --from=kubernetes-codex-builder /opt/aileron/bin/codex /usr/local/bin/codex
COPY workspace-manager/app/ ./app/
COPY workspace-manager/scripts/ ./scripts/
COPY contracts/ /contracts/
COPY workspace-manager/supervisord.kubernetes.conf ./supervisord.kubernetes.conf

RUN chmod -R a+rX ./app ./scripts /packages \
    && chmod 0555 ./scripts/*.sh \
    && ln -s /workspace-manager/supervisord.kubernetes.conf /workspace-manager/supervisord.conf \
    && ln -s /workspace-manager/.venv/bin/supervisord /usr/bin/supervisord \
    && ln -s /workspace-manager/.venv/bin/supervisorctl /usr/bin/supervisorctl \
    && mkdir -p /tmp/codex \
    && CODEX_HOME=/tmp/codex codex --version \
    && git --version \
    && supervisord --version

EXPOSE 3001

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://127.0.0.1:3001/health || exit 1

USER 10001:10001

ENTRYPOINT []
CMD ["/workspace-manager/scripts/start_services.sh"]
