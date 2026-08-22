ARG TARGETOS=linux
ARG TARGETARCH
ARG BUILDPLATFORM
ARG GO_IMAGE
ARG RUNTIME_IMAGE

FROM --platform=${BUILDPLATFORM} ${GO_IMAGE} AS base

WORKDIR /workspace-operator

COPY go.mod go.sum ./
RUN go mod download

COPY . .

FROM base AS test

ARG SOURCE_REVISION=development
LABEL org.opencontainers.image.revision=${SOURCE_REVISION}

CMD ["go", "test", "-v", "./..."]

FROM base AS builder

ARG TARGETOS
ARG TARGETARCH

RUN target_os="${TARGETOS:-linux}" \
    && target_arch="${TARGETARCH:-$(go env GOARCH)}" \
    && CGO_ENABLED=0 GOOS="${target_os}" GOARCH="${target_arch}" \
        go build -trimpath -ldflags="-s -w" \
        -o /workspace-operator/bin/workspace-operator ./cmd

FROM ${RUNTIME_IMAGE} AS kubernetes

RUN apk add --no-cache ca-certificates tzdata

WORKDIR /app
COPY --from=builder /workspace-operator/bin/workspace-operator /app/workspace-operator

USER 65532:65532

ENTRYPOINT ["/app/workspace-operator"]
