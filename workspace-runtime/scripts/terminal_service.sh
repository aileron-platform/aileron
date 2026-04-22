#!/bin/bash

set -euo pipefail

TERMINAL_SOURCE_DIR="${WORKSPACE_TERMINAL_SOURCE_DIR:-${WORKSPACE_TERMINAL_DIR:-/workspace-terminal}}"
TERMINAL_BINARY_DIR="${WORKSPACE_TERMINAL_BINARY_DIR:-/tmp/terminal-service/bin}"
TERMINAL_BINARY="${TERMINAL_BINARY_DIR}/terminal-service"

detect_target_goarch() {
    if [ -n "${WORKSPACE_TERMINAL_GOARCH:-}" ]; then
        echo "${WORKSPACE_TERMINAL_GOARCH}"
        return 0
    fi

    case "$(uname -m)" in
        x86_64|amd64)
            echo "amd64"
            ;;
        aarch64|arm64)
            echo "arm64"
            ;;
        *)
            echo "Unsupported container architecture: $(uname -m)" >&2
            return 1
            ;;
    esac
}

expected_machine_code() {
    case "$1" in
        amd64)
            echo "62"
            ;;
        arm64)
            echo "183"
            ;;
        *)
            echo "Unsupported Go architecture: $1" >&2
            return 1
            ;;
    esac
}

is_elf_binary() {
    [ -f "$TERMINAL_BINARY" ] && head -c 4 "$TERMINAL_BINARY" | od -An -tx1 | grep -q "7f 45 4c 46"
}

binary_machine_code() {
    od -An -tu2 -j 18 -N 2 "$TERMINAL_BINARY" | tr -d '[:space:]'
}

terminal_sources_changed() {
    [ ! -f "$TERMINAL_BINARY" ] && return 0

    find "${TERMINAL_SOURCE_DIR}" \
        \( -path "${TERMINAL_SOURCE_DIR}/.git" -o -path "${TERMINAL_SOURCE_DIR}/bin" \) -prune \
        -o \
        \( -name 'go.mod' -o -name 'go.sum' -o -name '*.go' \) -type f -newer "$TERMINAL_BINARY" -print -quit \
        | grep -q .
}

rebuild_terminal_binary() {
    local target_goarch
    target_goarch="$(detect_target_goarch)"

    if [ ! -f "${TERMINAL_SOURCE_DIR}/go.mod" ] || [ ! -f "${TERMINAL_SOURCE_DIR}/cmd/server/main.go" ]; then
        echo "terminal-service sources not found in ${TERMINAL_SOURCE_DIR}" >&2
        return 1
    fi

    echo "Rebuilding terminal-service for linux/${target_goarch}"
    (
        cd "${TERMINAL_SOURCE_DIR}"
        rm -f "${TERMINAL_BINARY}"
        mkdir -p "${TERMINAL_BINARY_DIR}"
        CGO_ENABLED=0 GOOS=linux GOARCH="${target_goarch}" go build -o "${TERMINAL_BINARY}" ./cmd/server
        chmod +x "${TERMINAL_BINARY}"
    )
}

ensure_terminal_binary() {
    local target_goarch expected_machine actual_machine
    target_goarch="$(detect_target_goarch)"
    expected_machine="$(expected_machine_code "${target_goarch}")"

    if ! is_elf_binary; then
        rebuild_terminal_binary
        return
    fi

    actual_machine="$(binary_machine_code)"
    if [ "${actual_machine}" != "${expected_machine}" ]; then
        echo "terminal-service architecture mismatch (${actual_machine} != ${expected_machine})" >&2
        rebuild_terminal_binary
        return
    fi

    if terminal_sources_changed; then
        echo "terminal-service sources changed; rebuilding cached binary" >&2
        rebuild_terminal_binary
    fi
}

ensure_terminal_binary

if [ "${1:-}" = "--exec" ]; then
    exec "${TERMINAL_BINARY}"
fi
