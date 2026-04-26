#!/usr/bin/env bash

set -euo pipefail

echo "Verifying workspace-runtime base-lite ..."
echo "- Python: $(python3 --version)"
echo "- uv: $(uv --version)"
echo "- Node.js: $(node --version)"
echo "- npm: $(npm --version)"
echo "- pnpm: $(pnpm --version)"
if command -v go >/dev/null 2>&1; then
    echo "Go must not be installed in base-lite" >&2
    exit 1
fi
echo "- Go: absent"
if command -v java >/dev/null 2>&1; then
    echo "Java must not be installed in base-lite" >&2
    exit 1
fi
echo "- Java: absent"
echo "- Git: $(git --version)"
echo "- SSH: $(ssh -V 2>&1)"
