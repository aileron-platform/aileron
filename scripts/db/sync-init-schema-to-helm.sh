#!/bin/sh

set -eu

SCRIPT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
REPO_ROOT="$(CDPATH= cd -- "$SCRIPT_DIR/../.." && pwd)"

SOURCE_SQL="$REPO_ROOT/init-sql/001_init_schema.sql"
TARGET_SQL="$REPO_ROOT/helm/aileron/files/init-sql/001_init_schema.sql"

if [ ! -f "$SOURCE_SQL" ]; then
  echo "找不到來源 SQL: $SOURCE_SQL" >&2
  exit 1
fi

mkdir -p "$(dirname "$TARGET_SQL")"
cp "$SOURCE_SQL" "$TARGET_SQL"

echo "已同步 init schema:"
echo "  source: $SOURCE_SQL"
echo "  target: $TARGET_SQL"
