#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OPS_SCRIPT="$SCRIPT_DIR/../dev/docker/ops.py"

if command -v python3 >/dev/null 2>&1; then
  exec python3 "$OPS_SCRIPT" test "$@"
elif command -v python >/dev/null 2>&1; then
  exec python "$OPS_SCRIPT" test "$@"
else
  echo "找不到 python3 或 python，無法執行跨平台測試 CLI。" >&2
  exit 1
fi
