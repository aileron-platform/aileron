ARG NODE_IMAGE
ARG NGINX_IMAGE

FROM ${NODE_IMAGE} AS builder

ARG NPM_VERSION=12.0.1
RUN npm install -g "npm@${NPM_VERSION}" \
    && test "$(npm --version)" = "${NPM_VERSION}"

ARG TZ=Asia/Taipei
# Build capability flags with placeholder values replaced at container start.
ARG VITE_BROWSER_EXTENSION_ID=__VITE_BROWSER_EXTENSION_ID__
ENV TZ=${TZ}
ENV VITE_BROWSER_EXTENSION_ID=${VITE_BROWSER_EXTENSION_ID}
RUN apk add --no-cache tzdata && \
    ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && \
    echo $TZ > /etc/timezone

WORKDIR /app
COPY package*.json .npmrc ./
RUN test "$(node -p "require('./package.json').packageManager")" = "npm@${NPM_VERSION}" \
    && npm ci --no-audit --no-fund
COPY . .
RUN npm run build

FROM ${NGINX_IMAGE} AS runner

ARG TZ=Asia/Taipei
ENV TZ=${TZ}
RUN apk add --no-cache tzdata && \
    ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && \
    echo $TZ > /etc/timezone

COPY --from=builder /app/dist /opt/aileron/html
COPY nginx.conf /etc/nginx/nginx.conf
COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod 0555 /docker-entrypoint.sh \
    && find /opt/aileron/html -type d -exec chmod 0555 {} + \
    && find /opt/aileron/html -type f -exec chmod 0444 {} +

EXPOSE 8082

USER 101:101

ENTRYPOINT ["/docker-entrypoint.sh"]
CMD ["nginx", "-g", "daemon off;"]
