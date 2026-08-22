variable "IMAGE_NAMESPACE" {
  default     = "ailerondocker"
  description = "Container image namespace used for local and release tags."
}

variable "LOCAL_TAG" {
  default     = "dev"
  description = "Architecture-neutral tag used by the local Docker Compose stack."
}

variable "RELEASE_TAG" {
  default     = "latest"
  description = "Release tag. Override this value in CI for immutable releases."
}

variable "PYTHON_IMAGE" {
  default     = "python:3.14.6-slim@sha256:cea0e6040540fb2b965b6e7fb5ffa00871e632eef63719f0ea54bca189ce14a6"
  description = "Python base image shared by Runtime and Manager."
}

variable "NODE_SLIM_IMAGE" {
  default     = "node:24.18.0-slim@sha256:6f7b03f7c2c8e2e784dcf9295400527b9b1270fd37b7e9a7285cf83b6951452d"
  description = "Node.js base image for Debian-based application images."
}

variable "NODE_ALPINE_IMAGE" {
  default     = "node:24.18.0-alpine@sha256:a0b9bf06e4e6193cf7a0f58816cc935ff8c2a908f81e6f1a95432d679c54fbfd"
  description = "Node.js base image for the frontend development and build images."
}

variable "NGINX_IMAGE" {
  default     = "nginx:alpine"
  description = "Nginx runtime image for the production frontend."
}

variable "NPM_VERSION" {
  default     = "12.0.1"
  description = "npm version installed in Node.js-based application images."
}

variable "PNPM_VERSION" {
  default     = "11.17.0"
  description = "pnpm version installed in the Runtime base image."
}

variable "UV_VERSION" {
  default     = "0.11.32"
  description = "uv version installed in Python application images."
}

variable "SUPERVISOR_VERSION" {
  default     = "4.3.0"
  description = "Supervisor version installed in the immutable Manager image."
}

variable "CLAUDE_CLI_VERSION" {
  default     = "2.1.220"
  description = "Claude Code CLI version installed in Runtime images."
}

variable "CODEX_CLI_VERSION" {
  default     = "0.145.0"
  description = "Codex CLI version installed in Runtime and Manager images."
}

variable "PLAYWRIGHT_CLI_VERSION" {
  default     = "0.1.17"
  description = "Playwright CLI version installed in Runtime images."
}

variable "OPENCODE_VERSION" {
  default     = "1.18.5"
  description = "OpenCode CLI version installed in Runtime images."
}

variable "OPENCODE_SHA256_AMD64" {
  default     = "cd4a2557a3d6550f27cb5c0257ebe8d73388bb34beda8b6121e6428a74c1eae2"
  description = "OpenCode amd64 archive checksum for OPENCODE_VERSION."
}

variable "OPENCODE_SHA256_ARM64" {
  default     = "18b643362fdf0b8d5b8711b3e160dafb4e68d0bfc00288f56fd1298fd72da69d"
  description = "OpenCode arm64 archive checksum for OPENCODE_VERSION."
}

variable "RUNTIME_GO_IMAGE" {
  default     = "golang:1.23"
  description = "Go builder image used for the Runtime terminal service."
}

variable "MAVEN_VERSION" {
  default     = "3.9.16"
  description = "Maven version installed in the Java Runtime base image."
}

variable "MAVEN_SHA512" {
  default     = "831a8591fe20c8243b1dbe7d71e3244f31d1665b0804b2e825e38cbbe5ce0cafb8338851f90780735568773e0a6cd07bbec107cda0b896b008b861075358b6f6"
  description = "Maven archive checksum for MAVEN_VERSION."
}

variable "BROWSER_BASE_IMAGE" {
  default     = "ghcr.io/m1k1o/neko/chromium:3.1.4@sha256:8caebd42dade3c8903dad07a39f0fbd1ad238357e5cfbbc207201c52b70f678e"
  description = "Pinned Neko Chromium image used by Workspace Browser."
}

variable "OPERATOR_GO_IMAGE" {
  default     = "golang:1.22-alpine"
  description = "Go builder image used by Workspace Operator."
}

variable "OPERATOR_RUNTIME_IMAGE" {
  default     = "alpine:3.20"
  description = "Runtime base image used by Workspace Operator."
}

group "default" {
  targets = [
    "runtime-base-lite",
    "runtime-base-java",
    "workspace-runtime-lite",
    "workspace-runtime-java",
    "workspace-browser",
    "workspace-canvas",
    "workspace-manager",
    "workspace-ui",
    "workspace-operator",
    "platform-coturn",
    "platform-keycloak",
  ]
}

group "local" {
  targets = [
    "runtime-base-lite",
    "runtime-base-java",
    "workspace-runtime-lite",
    "workspace-runtime-java",
    "workspace-browser",
    "workspace-canvas",
    "workspace-manager",
    "workspace-ui",
    "workspace-operator",
    "platform-coturn",
    "platform-keycloak",
  ]
}

group "release" {
  targets = [
    "workspace-runtime-production",
    "workspace-runtime-kubernetes",
    "workspace-browser-kubernetes",
    "workspace-canvas-kubernetes",
    "workspace-manager-production",
    "workspace-manager-kubernetes",
    "workspace-ui-production",
    "workspace-operator-kubernetes",
    "platform-keycloak-kubernetes",
  ]
}

group "test-support" {
  targets = [
    "workspace-operator-test",
    "workspace-terminal-test",
  ]
}

group "kubernetes-arbitrary-uid" {
  targets = [
    "workspace-operator-arbitrary-uid",
    "workspace-manager-arbitrary-uid",
    "workspace-runtime-arbitrary-uid",
    "workspace-ui-arbitrary-uid",
    "workspace-browser-arbitrary-uid",
    "workspace-canvas-arbitrary-uid",
  ]
}

group "k3s-e2e" {
  targets = [
    "workspace-operator-k3s-e2e",
    "workspace-manager-k3s-e2e",
    "workspace-runtime-k3s-e2e",
    "workspace-browser-k3s-e2e",
    "workspace-canvas-k3s-e2e",
    "product-conformance-k3s-e2e",
    "platform-redis-k3s-e2e",
    "platform-postgres-k3s-e2e",
    "platform-keycloak-k3s-e2e",
    "nfs-ganesha-k3s-e2e",
    "kubernetes-conformance-probe-k3s-e2e",
    "k3s-node-e2e",
  ]
}

target "runtime-base-lite" {
  context    = "workspace-runtime/base-images/lite"
  dockerfile = "Dockerfile"
  tags       = ["${IMAGE_NAMESPACE}/workspace-runtime-base-lite:${LOCAL_TAG}"]
  args = {
    PYTHON_IMAGE = PYTHON_IMAGE
    NODE_IMAGE   = NODE_SLIM_IMAGE
    NPM_VERSION  = NPM_VERSION
    PNPM_VERSION = PNPM_VERSION
    UV_VERSION   = UV_VERSION
  }
}

target "runtime-base-java" {
  context    = "workspace-runtime/base-images/java21"
  dockerfile = "Dockerfile"
  tags       = ["${IMAGE_NAMESPACE}/workspace-runtime-base-java:${LOCAL_TAG}"]
  contexts = {
    workspace-runtime-base-lite = "target:runtime-base-lite"
  }
  args = {
    MAVEN_VERSION = MAVEN_VERSION
    MAVEN_SHA512  = MAVEN_SHA512
  }
}

target "_workspace-runtime-common" {
  context    = "."
  dockerfile = "workspace-runtime/Dockerfile"
  args = {
    GO_IMAGE                = RUNTIME_GO_IMAGE
    CLAUDE_CLI_VERSION      = CLAUDE_CLI_VERSION
    PLAYWRIGHT_CLI_VERSION  = PLAYWRIGHT_CLI_VERSION
    CODEX_CLI_VERSION       = CODEX_CLI_VERSION
    OPENCODE_VERSION        = OPENCODE_VERSION
    OPENCODE_SHA256_AMD64   = OPENCODE_SHA256_AMD64
    OPENCODE_SHA256_ARM64   = OPENCODE_SHA256_ARM64
  }
}

target "workspace-runtime-lite" {
  inherits = ["_workspace-runtime-common"]
  target   = "development"
  tags     = ["${IMAGE_NAMESPACE}/workspace-runtime:${LOCAL_TAG}-lite"]
  contexts = {
    runtime-base = "target:runtime-base-lite"
  }
}

target "workspace-runtime-java" {
  inherits = ["_workspace-runtime-common"]
  target   = "development"
  tags     = ["${IMAGE_NAMESPACE}/workspace-runtime:${LOCAL_TAG}-java"]
  contexts = {
    runtime-base = "target:runtime-base-java"
  }
}

target "workspace-runtime-production" {
  inherits = ["_workspace-runtime-common"]
  target   = "production"
  tags     = ["${IMAGE_NAMESPACE}/workspace-runtime:${RELEASE_TAG}"]
  contexts = {
    runtime-base = "target:runtime-base-lite"
  }
}

target "workspace-runtime-kubernetes" {
  inherits = ["_workspace-runtime-common"]
  target   = "kubernetes"
  tags     = ["${IMAGE_NAMESPACE}/workspace-runtime:${RELEASE_TAG}-kubernetes"]
  contexts = {
    runtime-base = "target:runtime-base-lite"
  }
}

target "_workspace-manager-common" {
  context    = "."
  dockerfile = "workspace-manager/Dockerfile"
  args = {
    PYTHON_IMAGE       = PYTHON_IMAGE
    NODE_IMAGE         = NODE_SLIM_IMAGE
    NPM_VERSION        = NPM_VERSION
    UV_VERSION         = UV_VERSION
    SUPERVISOR_VERSION = SUPERVISOR_VERSION
    CODEX_CLI_VERSION  = CODEX_CLI_VERSION
    RELEASE_TAG        = RELEASE_TAG
  }
}

target "workspace-manager" {
  inherits = ["_workspace-manager-common"]
  target   = "development"
  tags     = ["${IMAGE_NAMESPACE}/workspace-manager:${LOCAL_TAG}"]
}

target "workspace-manager-production" {
  inherits = ["_workspace-manager-common"]
  target   = "production"
  tags     = ["${IMAGE_NAMESPACE}/workspace-manager:${RELEASE_TAG}"]
}

target "workspace-manager-kubernetes" {
  inherits = ["_workspace-manager-common"]
  target   = "kubernetes"
  tags     = ["${IMAGE_NAMESPACE}/workspace-manager:${RELEASE_TAG}-kubernetes"]
}

target "_workspace-ui-common" {
  context = "frontend"
  args = {
    NODE_IMAGE  = NODE_ALPINE_IMAGE
    NPM_VERSION = NPM_VERSION
  }
}

target "workspace-ui" {
  inherits   = ["_workspace-ui-common"]
  dockerfile = "Dockerfile.dev"
  tags       = ["${IMAGE_NAMESPACE}/workspace-ui:${LOCAL_TAG}"]
}

target "workspace-ui-production" {
  inherits   = ["_workspace-ui-common"]
  dockerfile = "Dockerfile"
  tags       = ["${IMAGE_NAMESPACE}/workspace-ui:${RELEASE_TAG}"]
  args = {
    NGINX_IMAGE = NGINX_IMAGE
  }
}

target "_workspace-browser-common" {
  context    = "workspace-chrome"
  dockerfile = "Dockerfile.webrtc"
  args = {
    BROWSER_BASE_IMAGE = BROWSER_BASE_IMAGE
  }
}

target "workspace-browser" {
  inherits = ["_workspace-browser-common"]
  target   = "development"
  tags     = ["${IMAGE_NAMESPACE}/workspace-chrome:${LOCAL_TAG}"]
}

target "workspace-browser-kubernetes" {
  inherits = ["_workspace-browser-common"]
  target   = "kubernetes"
  tags     = ["${IMAGE_NAMESPACE}/workspace-chrome:${RELEASE_TAG}-kubernetes"]
}

target "_workspace-canvas-common" {
  context    = "workspace-canvas"
  dockerfile = "Dockerfile"
  args = {
    NODE_IMAGE  = NODE_SLIM_IMAGE
    NPM_VERSION = NPM_VERSION
  }
}

target "workspace-canvas" {
  inherits = ["_workspace-canvas-common"]
  target   = "development"
  tags     = ["${IMAGE_NAMESPACE}/workspace-canvas:${LOCAL_TAG}"]
}

target "workspace-canvas-kubernetes" {
  inherits = ["_workspace-canvas-common"]
  target   = "kubernetes"
  tags     = ["${IMAGE_NAMESPACE}/workspace-canvas:${RELEASE_TAG}-kubernetes"]
}

target "_workspace-operator-common" {
  context    = "workspace-operator"
  dockerfile = "Dockerfile"
  args = {
    GO_IMAGE      = OPERATOR_GO_IMAGE
    RUNTIME_IMAGE = OPERATOR_RUNTIME_IMAGE
  }
}

target "workspace-operator-test" {
  inherits = ["_workspace-operator-common"]
  target   = "test"
  tags     = ["${IMAGE_NAMESPACE}/workspace-operator-test:${LOCAL_TAG}"]
}

target "workspace-operator" {
  inherits = ["_workspace-operator-common"]
  target   = "kubernetes"
  tags     = ["${IMAGE_NAMESPACE}/workspace-operator:${LOCAL_TAG}"]
}

target "workspace-operator-kubernetes" {
  inherits = ["_workspace-operator-common"]
  target   = "kubernetes"
  tags     = ["${IMAGE_NAMESPACE}/workspace-operator:${RELEASE_TAG}"]
}

target "platform-coturn" {
  context    = "platform/coturn"
  dockerfile = "Dockerfile"
  tags       = ["${IMAGE_NAMESPACE}/platform-coturn:${LOCAL_TAG}"]
}

target "platform-keycloak" {
  context    = "platform/keycloak"
  dockerfile = "Dockerfile"
  tags       = ["${IMAGE_NAMESPACE}/platform-keycloak:${LOCAL_TAG}"]
}

target "platform-keycloak-kubernetes" {
  context    = "platform/keycloak"
  dockerfile = "Dockerfile"
  tags       = ["${IMAGE_NAMESPACE}/platform-keycloak:${RELEASE_TAG}-kubernetes"]
}

target "platform-keycloak-k3s-e2e" {
  context    = "platform/keycloak"
  dockerfile = "Dockerfile"
  tags       = ["aileron/platform-keycloak:k3s-e2e"]
}

target "workspace-terminal-test" {
  context    = "workspace-terminal"
  dockerfile = "Dockerfile.ci"
  tags       = ["${IMAGE_NAMESPACE}/workspace-terminal-test:${LOCAL_TAG}"]
  args = {
    GO_IMAGE = RUNTIME_GO_IMAGE
  }
}

target "workspace-operator-arbitrary-uid" {
  inherits = ["workspace-operator-kubernetes"]
  tags     = ["aileron/workspace-operator:kubernetes-arbitrary-uid-test"]
}

target "workspace-manager-arbitrary-uid" {
  inherits = ["workspace-manager-kubernetes"]
  tags     = ["aileron/workspace-manager:kubernetes-arbitrary-uid-test"]
}

target "workspace-runtime-arbitrary-uid" {
  inherits = ["workspace-runtime-kubernetes"]
  tags     = ["aileron/workspace-runtime:kubernetes-arbitrary-uid-test"]
}

target "workspace-ui-arbitrary-uid" {
  inherits = ["workspace-ui-production"]
  tags     = ["aileron/workspace-ui:kubernetes-arbitrary-uid-test"]
}

target "workspace-browser-arbitrary-uid" {
  inherits = ["workspace-browser-kubernetes"]
  tags     = ["aileron/workspace-chrome:kubernetes-arbitrary-uid-test"]
}

target "workspace-canvas-arbitrary-uid" {
  inherits = ["workspace-canvas-kubernetes"]
  tags     = ["aileron/workspace-canvas:kubernetes-arbitrary-uid-test"]
}

target "workspace-operator-k3s-e2e" {
  inherits = ["workspace-operator-kubernetes"]
  tags     = ["aileron/workspace-operator:k3s-e2e"]
}

target "workspace-manager-k3s-e2e" {
  inherits = ["workspace-manager-kubernetes"]
  tags     = ["aileron/workspace-manager:k3s-e2e"]
}

target "workspace-runtime-k3s-e2e" {
  inherits = ["workspace-runtime-kubernetes"]
  tags     = ["aileron/workspace-runtime:k3s-e2e"]
}

target "workspace-browser-k3s-e2e" {
  inherits = ["workspace-browser-kubernetes"]
  tags     = ["aileron/workspace-chrome:k3s-e2e"]
}

target "workspace-canvas-k3s-e2e" {
  inherits = ["workspace-canvas-kubernetes"]
  tags     = ["aileron/workspace-canvas:k3s-e2e"]
}

target "product-conformance-k3s-e2e" {
  context    = "."
  dockerfile = "scripts/test/kubernetes/product-conformance/Dockerfile"
  tags       = ["aileron/product-conformance:k3s-e2e"]
}

target "platform-redis-k3s-e2e" {
  context    = "platform/redis"
  dockerfile = "Dockerfile"
  tags       = ["aileron/platform-redis:k3s-e2e"]
}

target "platform-postgres-k3s-e2e" {
  context    = "platform/postgres"
  dockerfile = "Dockerfile"
  tags       = ["aileron/platform-postgres:k3s-e2e"]
}

target "nfs-ganesha-k3s-e2e" {
  context    = "."
  dockerfile = "scripts/test/kubernetes/nfs-ganesha/Dockerfile"
  tags       = ["aileron/nfs-ganesha:k3s-e2e"]
}

target "kubernetes-conformance-probe-k3s-e2e" {
  context    = "."
  dockerfile = "scripts/test/kubernetes/Dockerfile.probe-workload"
  tags       = ["aileron/kubernetes-conformance-probe:k3s-e2e"]
}

target "k3s-node-e2e" {
  context    = "."
  dockerfile = "scripts/test/kubernetes/Dockerfile.k3s-node"
  tags       = ["aileron/k3s-nfs-node:v1.31.6-k3s1"]
}
