# workspace-canvas: Standalone web canvas preview container.
# Dependency stages keep immutable application layers reproducible and cacheable.

ARG NODE_IMAGE

FROM ${NODE_IMAGE} AS node-base

ARG NPM_VERSION
RUN npm install -g "npm@${NPM_VERSION}"

FROM node-base AS nextjs-dependencies

WORKDIR /opt/canvas-nextjs-template
COPY nextjs-template/package.json nextjs-template/package-lock.json ./
RUN npm ci --no-audit --no-fund

FROM node-base AS management-dependencies

WORKDIR /canvas-management
COPY management-server/package.json management-server/package-lock.json ./
RUN npm ci --omit=dev --ignore-scripts --no-audit --no-fund

FROM node-base AS base

ENV CANVAS_RUNTIME_HOME=/tmp/aileron-canvas/home \
    CANVAS_NPM_CACHE_DIR=/tmp/aileron-canvas/npm-cache \
    npm_config_cache=/tmp/aileron-canvas/npm-cache \
    HOME=/tmp/aileron-canvas/home \
    NEXT_TELEMETRY_DISABLED=1

RUN install -d -m 0755 \
      /workspace \
      /canvas-management \
      /opt/canvas-default-source \
      /opt/canvas-nextjs-template \
      /scripts

COPY nextjs-template/ /opt/canvas-nextjs-template/
COPY --from=nextjs-dependencies /opt/canvas-nextjs-template/node_modules /opt/canvas-nextjs-template/node_modules

COPY default-canvas/ /opt/canvas-default-source/
WORKDIR /opt/canvas-default-source
RUN mkdir -p node_modules \
    && cp -R /opt/canvas-nextjs-template/node_modules/. node_modules/ \
    && npx next build \
    && rm -rf node_modules \
    && rm -rf .next

COPY management-server/ /canvas-management/
COPY --from=management-dependencies /canvas-management/node_modules /canvas-management/node_modules

COPY scripts/ /scripts/
RUN chmod 0755 /scripts/*.sh

# Build commands use the runtime HOME and npm cache paths as root. Remove those
# build artifacts so every runtime UID can create its own isolated state.
RUN rm -rf /tmp/aileron-canvas \
    && install -d -m 1777 /tmp/aileron-canvas

WORKDIR /workspace

# 3003: Canvas render server
# 3013: Management API
EXPOSE 3003 3013

HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
    CMD node -e 'fetch("http://127.0.0.1:3013/health").then((response) => process.exit(response.ok ? 0 : 1)).catch(() => process.exit(1))'

FROM base AS kubernetes

# Kubernetes may replace this UID (for example, OpenShift arbitrary UID). Runtime
# code must therefore depend only on the effective identity and supplemental GID.
USER 10001:10001
CMD ["/scripts/entrypoint.sh"]

FROM base AS development

USER 1000:1000
CMD ["/scripts/entrypoint.sh"]
