FROM mikefarah/yq:4.44.3@sha256:8595be35467456dc336a8f85e00cfb13b27e93c9a7b7f14173accb3e3122573f AS yq

FROM alpine/helm:3.19.0@sha256:e4e787415a4964fc6559cba60ed13f7b46e435c2f91529894bca7a7a33a0841e

ARG SOURCE_REVISION=development
LABEL org.opencontainers.image.revision=${SOURCE_REVISION}

COPY --from=yq /usr/bin/yq /usr/local/bin/yq

RUN helm version --short | grep -Fq 'v3.19.0' \
    && yq --version | grep -Fq 'v4.44.3'

WORKDIR /repo

ENTRYPOINT ["/bin/sh", "/repo/scripts/test/helm/assert-kubernetes-platform-contracts.sh"]
