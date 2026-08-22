#!/bin/sh
set -eu

staged_secret_dir=$(mktemp -d /dev/shm/aileron-postgres-secrets.XXXXXX)
chown postgres:postgres "$staged_secret_dir"
chmod 0700 "$staged_secret_dir"

for secret_name in postgres-platform-username postgres-platform-password; do
  cp "/run/secrets/$secret_name" "$staged_secret_dir/$secret_name"
  chown postgres:postgres "$staged_secret_dir/$secret_name"
  chmod 0400 "$staged_secret_dir/$secret_name"
done

export AILERON_POSTGRES_STAGED_SECRET_DIR="$staged_secret_dir"
export AILERON_POSTGRES_PLATFORM_USERNAME_FILE="$staged_secret_dir/postgres-platform-username"
export AILERON_POSTGRES_PLATFORM_PASSWORD_FILE="$staged_secret_dir/postgres-platform-password"

exec /usr/local/bin/docker-entrypoint.sh "$@"
