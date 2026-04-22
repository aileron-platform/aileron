#!/bin/bash

set -euo pipefail

TERMINAL_SOURCE_DIR="${WORKSPACE_TERMINAL_SOURCE_DIR:-${WORKSPACE_TERMINAL_DIR:-/workspace-terminal}}"
TERMINAL_PREBUILT_BINARY="${WORKSPACE_TERMINAL_PREBUILT_BINARY:-/opt/terminal-service/bin/terminal-service}"
TERMINAL_CACHE_ROOT="${WORKSPACE_TERMINAL_CACHE_DIR:-/workspace/.cache/terminal-service}"
TERMINAL_REBUILD_FROM_SOURCE="${WORKSPACE_TERMINAL_REBUILD_FROM_SOURCE:-0}"
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

is_truthy() {
    case "${1,,}" in
        1|true|yes|on)
            return 0
            ;;
        *)
            return 1
            ;;
    esac
}

terminal_source_available() {
    [ -f "${TERMINAL_SOURCE_DIR}/go.mod" ] && [ -f "${TERMINAL_SOURCE_DIR}/cmd/server/main.go" ]
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

compute_source_hash() {
    local files

    if ! terminal_source_available; then
        echo "terminal-service sources not found in ${TERMINAL_SOURCE_DIR}" >&2
        return 1
    fi

    files="$(
        find "${TERMINAL_SOURCE_DIR}" \
            \( -path "${TERMINAL_SOURCE_DIR}/.git" -o -path "${TERMINAL_SOURCE_DIR}/bin" -o -path "${TERMINAL_SOURCE_DIR}/.cache" \) -prune \
            -o \
            \( -name 'go.mod' -o -name 'go.sum' -o -name '*.go' \) -type f -print \
            | LC_ALL=C sort
    )"

    if [ -z "$files" ]; then
        echo "terminal-service source set is empty in ${TERMINAL_SOURCE_DIR}" >&2
        return 1
    fi

    (
        while IFS= read -r file; do
            [ -n "$file" ] || continue
            sha256sum "$file"
        done <<< "$files"
    ) | sha256sum | awk '{print $1}'
}

cache_binary_path() {
    local target_goarch="$1"
    local source_hash="$2"
    echo "${TERMINAL_CACHE_ROOT}/${target_goarch}/${source_hash}/terminal-service"
}

build_terminal_binary() {
    local output_path="$1"
    local target_goarch="$2"

    if ! terminal_source_available; then
        echo "terminal-service sources not found in ${TERMINAL_SOURCE_DIR}" >&2
        return 1
    fi

    echo "Rebuilding terminal-service for linux/${target_goarch} -> ${output_path}" >&2
    mkdir -p "$(dirname "${output_path}")"
    (
        cd "${TERMINAL_SOURCE_DIR}"
        CGO_ENABLED=0 GOOS=linux GOARCH="${target_goarch}" go build -o "${output_path}" ./cmd/server
    )
    chmod +x "${output_path}"
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

resolve_source_rebuild_binary() {
    local target_goarch="$1"
    local source_hash cache_binary

    source_hash="$(compute_source_hash)"
    cache_binary="$(cache_binary_path "${target_goarch}" "${source_hash}")"

    if is_binary_compatible "${cache_binary}" "${target_goarch}"; then
        echo "Using cached terminal-service binary: ${cache_binary}" >&2
        RESOLVED_TERMINAL_BINARY="${cache_binary}"
        return 0
    fi

    build_terminal_binary "${cache_binary}" "${target_goarch}"
    RESOLVED_TERMINAL_BINARY="${cache_binary}"
    return 0
}

ensure_terminal_binary() {
    local target_goarch
    target_goarch="$(detect_target_goarch)"

    if is_truthy "${TERMINAL_REBUILD_FROM_SOURCE}"; then
        resolve_source_rebuild_binary "${target_goarch}"
        return 0
    fi

    if resolve_prebuilt_binary "${target_goarch}"; then
        return 0
    fi

    echo "Falling back to architecture-safe terminal-service rebuild" >&2
    resolve_source_rebuild_binary "${target_goarch}"
}

ensure_terminal_binary

if [ "${1:-}" = "--exec" ]; then
    exec "${RESOLVED_TERMINAL_BINARY}"
fi

echo "Using terminal-service binary: ${RESOLVED_TERMINAL_BINARY}"
