ARG NODE_IMAGE
FROM ${NODE_IMAGE}

ENV NEXT_TELEMETRY_DISABLED=1 \
    npm_config_audit=false \
    npm_config_fetch_retries=4 \
    npm_config_fetch_retry_maxtimeout=30000 \
    npm_config_fetch_retry_mintimeout=1000 \
    npm_config_fetch_timeout=60000 \
    npm_config_fund=false

WORKDIR /opt/canvas-builder
COPY package.json package-lock.json ./
RUN npm ci --ignore-scripts --prefer-offline

COPY build-nextjs.sh /usr/local/bin/build-nextjs
RUN chmod 0755 /usr/local/bin/build-nextjs \
    && install -d -m 1777 /output

USER 10001:10001

ENTRYPOINT ["/usr/local/bin/build-nextjs"]
