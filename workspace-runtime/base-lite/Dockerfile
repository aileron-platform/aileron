FROM ubuntu:24.04

ARG TARGETARCH
ARG GO_VERSION=1.23.4
ARG NODE_MAJOR=22

ENV DEBIAN_FRONTEND=noninteractive
ENV LANG=C.UTF-8
ENV HOME=/home/developer
ENV PATH=/home/developer/.local/bin:/usr/local/go/bin:${PATH}

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        bash \
        build-essential \
        ca-certificates \
        curl \
        fd-find \
        git \
        git-lfs \
        jq \
        make \
        netcat-openbsd \
        openjdk-21-jdk \
        openssh-client \
        pkg-config \
        python3 \
        python3-dev \
        python3-pip \
        python3-venv \
        ripgrep \
        rsync \
        sudo \
        unzip \
        wget \
        zip \
    && rm -rf /var/lib/apt/lists/* \
    && useradd -m -s /bin/bash developer \
    && echo "developer ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/developer \
    && chmod 440 /etc/sudoers.d/developer \
    && git lfs install --system \
    && ln -sf /usr/bin/fdfind /usr/local/bin/fd

RUN ARCH="$(dpkg --print-architecture)" \
    && case "${ARCH}" in \
        amd64) GO_ARCH=amd64 ;; \
        arm64) GO_ARCH=arm64 ;; \
        *) echo "Unsupported architecture: ${ARCH}" >&2; exit 1 ;; \
    esac \
    && wget -q "https://go.dev/dl/go${GO_VERSION}.linux-${GO_ARCH}.tar.gz" \
    && tar -C /usr/local -xzf "go${GO_VERSION}.linux-${GO_ARCH}.tar.gz" \
    && rm "go${GO_VERSION}.linux-${GO_ARCH}.tar.gz"

RUN curl -fsSL https://deb.nodesource.com/setup_${NODE_MAJOR}.x | bash - \
    && apt-get update \
    && apt-get install -y --no-install-recommends nodejs \
    && npm install -g pnpm \
    && npm cache clean --force \
    && rm -rf /var/lib/apt/lists/*

USER developer

RUN curl -LsSf https://astral.sh/uv/install.sh | sh \
    && /home/developer/.local/bin/uv tool update-shell

COPY verify.sh /opt/verify.sh
RUN sudo chmod +x /opt/verify.sh \
    && bash /opt/verify.sh
