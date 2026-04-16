FROM golang:1.22-alpine AS base

WORKDIR /workspace-operator

COPY go.mod go.sum ./
RUN go mod download

COPY . .

FROM base AS test

CMD ["go", "test", "-v", "./..."]

FROM base AS builder

RUN CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build -o /workspace-operator/bin/workspace-operator ./cmd/main.go

FROM alpine:3.20

RUN apk add --no-cache ca-certificates tzdata

WORKDIR /app
COPY --from=builder /workspace-operator/bin/workspace-operator /app/workspace-operator

ENTRYPOINT ["/app/workspace-operator"]
