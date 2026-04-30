#!/bin/bash

set -euo pipefail

TERMINAL_SOURCE_DIR="${WORKSPACE_TERMINAL_SOURCE_DIR:-${WORKSPACE_TERMINAL_DIR:-/workspace-terminal}}"
TERMINAL_PREBUILT_BINARY="${WORKSPACE_TERMINAL_PREBUILT_BINARY:-/opt/terminal-service/bin/terminal-service}"
TERMINAL_CACHE_ROOT="${WORKSPACE_TERMINAL_CACHE_DIR:-/workspace/.cache/terminal-service}"
RESOLVED_TERMINAL_BINARY=""

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
    local binary_path="$1"
    [ -f "$binary_path" ] && head -c 4 "$binary_path" | od -An -tx1 | grep -q "7f 45 4c 46"
}

binary_machine_code() {
    local binary_path="$1"
    od -An -tu2 -j 18 -N 2 "$binary_path" | tr -d '[:space:]'
}

is_binary_compatible() {
    local binary_path="$1"
    local target_goarch="$2"
    local expected_machine actual_machine

    expected_machine="$(expected_machine_code "${target_goarch}")"
    if ! is_elf_binary "$binary_path"; then
        return 1
    fi

    actual_machine="$(binary_machine_code "$binary_path")"
    [ "${actual_machine}" = "${expected_machine}" ]
}

resolve_prebuilt_binary() {
    local target_goarch="$1"

    if is_binary_compatible "${TERMINAL_PREBUILT_BINARY}" "${target_goarch}"; then
        RESOLVED_TERMINAL_BINARY="${TERMINAL_PREBUILT_BINARY}"
        return 0
    fi

    echo "terminal-service prebuilt binary missing or incompatible: ${TERMINAL_PREBUILT_BINARY}" >&2
    return 1
}

ensure_terminal_binary() {
    local target_goarch
    target_goarch="$(detect_target_goarch)"

    if ! resolve_prebuilt_binary "${target_goarch}"; then
        echo "ERROR: terminal-service prebuilt binary not found or incompatible: ${TERMINAL_PREBUILT_BINARY}" >&2
        echo "Please ensure the prebuilt binary exists and matches the container architecture." >&2
        exit 1
    fi
}

ensure_terminal_binary

if [ "${1:-}" = "--exec" ]; then
    echo "Using terminal-service binary: ${RESOLVED_TERMINAL_BINARY}"
    exec "${RESOLVED_TERMINAL_BINARY}"
fi

echo "Using terminal-service binary: ${RESOLVED_TERMINAL_BINARY}"
