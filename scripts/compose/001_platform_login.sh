#!/bin/sh
set -eu

platform_username=$(cat "${AILERON_POSTGRES_PLATFORM_USERNAME_FILE:-/run/secrets/postgres-platform-username}")
platform_password=$(cat "${AILERON_POSTGRES_PLATFORM_PASSWORD_FILE:-/run/secrets/postgres-platform-password}")

psql --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  --set=ON_ERROR_STOP=1 \
  --set=platform_username="$platform_username" \
  --set=platform_password="$platform_password" <<'SQL'
SELECT format(
  'CREATE ROLE %I WITH LOGIN NOSUPERUSER NOCREATEDB CREATEROLE INHERIT NOREPLICATION NOBYPASSRLS PASSWORD %L',
  :'platform_username',
  :'platform_password'
)
WHERE NOT EXISTS (
  SELECT 1 FROM pg_roles WHERE rolname = :'platform_username'
) \gexec
SELECT format(
  'ALTER ROLE %I WITH LOGIN NOSUPERUSER NOCREATEDB CREATEROLE INHERIT NOREPLICATION NOBYPASSRLS',
  :'platform_username'
) \gexec
SELECT format(
  'ALTER DATABASE %I OWNER TO %I',
  current_database(),
  :'platform_username'
) \gexec
SELECT format('GRANT pg_signal_backend TO %I', :'platform_username') \gexec
SQL

unset platform_username platform_password

if [ -n "${AILERON_POSTGRES_STAGED_SECRET_DIR:-}" ]; then
  rm -f \
    "$AILERON_POSTGRES_STAGED_SECRET_DIR/postgres-platform-username" \
    "$AILERON_POSTGRES_STAGED_SECRET_DIR/postgres-platform-password"
  rmdir "$AILERON_POSTGRES_STAGED_SECRET_DIR"
fi
