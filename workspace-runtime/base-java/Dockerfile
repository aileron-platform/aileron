# Java 21 + Maven workspace runtime base image.
# Extends workspace-runtime-base-lite via the build-context mechanism, so the
# developer toolchain (bash, build-essential, curl, git, Node.js, uv, etc.)
# is inherited verbatim. Only Java + Maven are added here.
#
# Build:
#   docker build \
#     --build-context workspace-runtime-base-lite=docker-image://<lite-ref> \
#     -t workspace-runtime-base-java workspace-runtime/base-java
FROM workspace-runtime-base-lite

USER root

ENV DEBIAN_FRONTEND=noninteractive

# Install Eclipse Temurin JDK 21 from the Adoptium APT repository plus Apache
# Maven 3.9.x from the Ubuntu archive. Both keep amd64 / arm64 parity.
RUN install -d -m 0755 /etc/apt/keyrings \
    && curl -fsSL https://packages.adoptium.net/artifactory/api/gpg/key/public \
       -o /etc/apt/keyrings/adoptium.asc \
    && . /etc/os-release \
    && echo "deb [signed-by=/etc/apt/keyrings/adoptium.asc] https://packages.adoptium.net/artifactory/deb ${VERSION_CODENAME} main" \
       > /etc/apt/sources.list.d/adoptium.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
        temurin-21-jdk \
        maven \
    && rm -rf /var/lib/apt/lists/*

# Provide a stable JAVA_HOME symlink that does not depend on the host architecture.
RUN ARCH="$(dpkg --print-architecture)" \
    && JDK_DIR="/usr/lib/jvm/temurin-21-jdk-${ARCH}" \
    && test -d "${JDK_DIR}" \
    && ln -sfn "${JDK_DIR}" /opt/java-21

ENV JAVA_HOME=/opt/java-21
ENV PATH=${JAVA_HOME}/bin:${PATH}

# Maven settings: keep the local repository under the developer home so it
# survives volume mounts of /workspace.
ENV MAVEN_USER_HOME=/home/developer/.m2
RUN mkdir -p "${MAVEN_USER_HOME}" \
    && chown -R developer:developer "${MAVEN_USER_HOME}"

COPY --chown=root:root verify.sh /tmp/verify.sh
RUN bash /tmp/verify.sh \
    && rm /tmp/verify.sh

USER developer
