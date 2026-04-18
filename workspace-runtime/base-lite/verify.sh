#!/usr/bin/env bash

set -euo pipefail

echo "Verifying workspace-runtime base-lite ..."
echo "- Python: $(python3 --version)"
echo "- uv: $(uv --version)"
echo "- Node.js: $(node --version)"
echo "- npm: $(npm --version)"
echo "- pnpm: $(pnpm --version)"
echo "- Go: $(go version)"
echo "- Java:"
java -version
echo "- Git: $(git --version)"
echo "- SSH: $(ssh -V 2>&1)"
