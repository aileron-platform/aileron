# Multi-stage build for workspace-manager
FROM python:3.11-slim AS base

# Set working directory
WORKDIR /workspace-manager

# Install system dependencies including Docker CLI, supervisor and tzdata
RUN apt-get update && apt-get install -y \
    curl \
    wget \
    git \
    docker.io \
    supervisor \
    redis-tools \
    tzdata \
    && rm -rf /var/lib/apt/lists/*

# Set timezone (can be overridden by environment variable)
ARG TZ=Asia/Taipei
ENV TZ=${TZ}
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# Install uv
RUN pip install uv

# Development stage: mount code instead of copying it.
FROM base AS development

# Copy project files for dependency installation
COPY pyproject.toml uv.lock* README.md ./

# Install dependencies with uv (including dev dependencies)
RUN uv sync --dev

# Create the app directory structure. Code is mounted at runtime.
RUN mkdir -p /workspace-manager/app

# Create data directories with proper permissions
RUN mkdir -p /data/templates-center /data/init-scripts \
    && chmod -R 755 /data

# Copy scripts and supervisor configs
COPY scripts/ ./scripts/
COPY supervisord.conf supervisord.dev.conf ./
RUN chmod +x ./scripts/*.sh

# Expose port
EXPOSE 3001

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://127.0.0.1:3001/health || exit 1

# Run FastAPI, Celery Worker and Flower using Supervisor
CMD ["/workspace-manager/scripts/start_services.sh"]

# Test stage (for containerized pytest/lint execution)
FROM development AS test

RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

CMD ["sh", "-lc", "uv sync --dev && uv run pytest tests/ -v"]

# Production stage: package the application into the container.
FROM base AS production

# Copy project files
COPY pyproject.toml uv.lock* README.md ./

# Install dependencies with uv (production only, no dev dependencies)
RUN uv sync --no-dev

# Copy the full application code into the container.
COPY app/ ./app/
COPY scripts/ ./scripts/
COPY supervisord.conf supervisord.dev.conf ./
COPY .env* ./
RUN chmod +x ./scripts/*.sh

# Create data directories with proper permissions
RUN mkdir -p /data/templates /data/templates/temp /data/templates/exports /data/init-scripts \
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
