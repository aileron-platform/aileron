ARG PYTHON_IMAGE
ARG NODE_IMAGE

FROM ${NODE_IMAGE} AS node-toolchain

FROM ${PYTHON_IMAGE}

ARG NPM_VERSION
ARG PNPM_VERSION
ARG UV_VERSION

ENV DEBIAN_FRONTEND=noninteractive
ENV LANG=C.UTF-8
ENV HOME=/home/developer

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
        libatomic1 \
        make \
        netcat-openbsd \
        openssh-client \
        pkg-config \
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

COPY --from=node-toolchain /usr/local/ /usr/local/

RUN npm install -g "npm@${NPM_VERSION}" "pnpm@${PNPM_VERSION}" \
    && npm cache clean --force \
    && test "$(npm --version)" = "${NPM_VERSION}"

RUN curl -LsSf "https://astral.sh/uv/${UV_VERSION}/install.sh" \
    | env UV_UNMANAGED_INSTALL=/usr/local/bin sh \
    && test "$(uv --version | awk '{print $2}')" = "${UV_VERSION}"

USER developer

COPY --chown=developer:developer verify.sh /tmp/verify.sh
RUN bash /tmp/verify.sh \
    && rm /tmp/verify.sh

USER root
RUN find /home/developer -mindepth 1 -maxdepth 1 -exec rm -rf -- {} +

USER developer
