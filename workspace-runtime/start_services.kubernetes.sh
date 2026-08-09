#!/bin/sh

set -eu

export HOME="${HOME:-/home/developer}"
export CODEX_HOME="${CODEX_HOME:-${HOME}/.codex}"
export XDG_CONFIG_HOME="${XDG_CONFIG_HOME:-${HOME}/.config}"
export XDG_DATA_HOME="${XDG_DATA_HOME:-${HOME}/.local/share}"
export XDG_STATE_HOME="${XDG_STATE_HOME:-${HOME}/.local/state}"
export MARKETPLACE_OPERATION_JOURNAL_DIR="${MARKETPLACE_OPERATION_JOURNAL_DIR:-${XDG_STATE_HOME}/aileron/marketplace-operations}"
export UV_CACHE_DIR="${UV_CACHE_DIR:-/tmp/uv-cache}"
export NPM_CONFIG_CACHE="${NPM_CONFIG_CACHE:-/tmp/npm-cache}"
export NPM_CONFIG_PREFIX="${NPM_CONFIG_PREFIX:-${HOME}/.local}"
export PYTHONPATH="/workspace-runtime:/workspace"
export PATH="/opt/aileron/bin:/opt/aileron/npm/bin:/workspace-runtime/.venv/bin:${HOME}/.local/bin:${PATH}"

mkdir -p \
  "${HOME}" \
  "${CODEX_HOME}" \
  "${HOME}/.codex-sessions" \
  "${HOME}/.claude" \
  "${XDG_CONFIG_HOME}/opencode" \
  "${XDG_DATA_HOME}/opencode" \
  "${XDG_STATE_HOME}/aileron" \
  "${MARKETPLACE_OPERATION_JOURNAL_DIR}" \
  "${UV_CACHE_DIR}" \
  "${NPM_CONFIG_CACHE}" \
  /tmp/supervisor

/workspace-runtime/.venv/bin/python \
  /workspace-runtime/scripts/initialize_workspace_runtime.py

exec /usr/bin/supervisord -c /workspace-runtime/supervisord.kubernetes.conf
