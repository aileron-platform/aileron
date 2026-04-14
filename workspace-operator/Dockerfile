FROM golang:1.22-alpine AS builder

WORKDIR /workspace-operator

COPY go.mod ./
RUN go mod download

COPY . .

RUN CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build -o /workspace-operator/bin/workspace-operator ./cmd/main.go

FROM alpine:3.20

RUN apk add --no-cache ca-certificates tzdata

WORKDIR /app
COPY --from=builder /workspace-operator/bin/workspace-operator /app/workspace-operator

ENTRYPOINT ["/app/workspace-operator"]
