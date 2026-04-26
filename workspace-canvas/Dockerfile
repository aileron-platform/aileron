# workspace-canvas: Standalone web canvas preview container
# Pre-installs common packages to reduce npm install time for Next.js renderer

FROM node:20-slim AS base

ENV npm_config_cache=/home/developer/.npm

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    lsof \
    procps \
    rsync \
    && rm -rf /var/lib/apt/lists/*

# Create developer user (matches workspace-runtime, UID/GID 1000)
# node:20-slim already has node:node (1000:1000); rename and configure home
RUN usermod -l developer -d /home/developer -m node && \
    groupmod -n developer node && \
    mkdir -p /home/developer && \
    chown -R developer:developer /home/developer

# Create directory structure:
# /workspace: shared volume (source code, read-only reference)
# /web-canvas: container working directory (rsynced source + isolated node_modules/.next)
RUN mkdir -p /workspace /web-canvas /default-canvas /canvas-management /opt/canvas-nextjs-template /scripts /var/log/canvas && \
    chown -R developer:developer /workspace /web-canvas /default-canvas /canvas-management /opt/canvas-nextjs-template /scripts /var/log/canvas

# Pre-install common Next.js packages to global npm cache (speeds up subsequent npm installs)
# All npm operations use HOME=/home/developer to ensure cache is in developer-accessible path
RUN HOME=/home/developer npm install -g npm@latest && \
    chown -R developer:developer /home/developer

COPY --chown=developer:developer nextjs-template/ /opt/canvas-nextjs-template/
WORKDIR /opt/canvas-nextjs-template
RUN HOME=/home/developer npm ci && \
    chown -R developer:developer /opt/canvas-nextjs-template /home/developer

COPY --chown=developer:developer default-canvas/ /default-canvas/

WORKDIR /default-canvas
RUN HOME=/home/developer npm install && \
    HOME=/home/developer npx next build 2>/dev/null || true && \
    chown -R developer:developer /default-canvas

COPY --chown=developer:developer management-server/ /canvas-management/
WORKDIR /canvas-management
RUN HOME=/home/developer npm install && \
    chown -R developer:developer /canvas-management

COPY --chown=developer:developer scripts/ /scripts/
RUN chmod +x /scripts/*.sh

WORKDIR /workspace

# 3003: Canvas render server
# 3013: Management API
EXPOSE 3003 3013

HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:3013/health || exit 1

# Start as root; entrypoint script switches to developer for renderer
CMD ["/scripts/entrypoint.sh"]
