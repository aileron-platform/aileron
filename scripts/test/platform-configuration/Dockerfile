FROM alpine/helm:3.18.4 AS helm

FROM alpine:3.22

COPY --from=helm /usr/bin/helm /usr/local/bin/helm

RUN apk add --no-cache \
    docker-cli \
    docker-cli-compose \
    py3-jsonschema \
    py3-yaml \
    python3

WORKDIR /repo

ENTRYPOINT ["python3", "/repo/scripts/test/platform-configuration/test_validator.py"]
