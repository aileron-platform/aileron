#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if command -v python3 >/dev/null 2>&1; then
  exec python3 "$SCRIPT_DIR/ops.py" up "$@"
elif command -v python >/dev/null 2>&1; then
  exec python "$SCRIPT_DIR/ops.py" up "$@"
else
  echo "找不到 python3 或 python，無法執行跨平台 docker compose CLI。" >&2
  exit 1
fi
