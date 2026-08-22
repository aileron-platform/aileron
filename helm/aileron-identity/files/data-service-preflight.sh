#!/bin/sh
set -eu

database_url=${IDENTITY_DATABASE_JDBC_URL#jdbc:}
PGUSER=$(cat "$POSTGRES_USERNAME_FILE")
PGPASSWORD=$(cat "$POSTGRES_PASSWORD_FILE")
export PGUSER PGPASSWORD
probe_suffix=$(printf '%s' "$POD_UID" | tr -d '-' | cut -c 1-24)
probe_table="aileron_identity_pf_${probe_suffix}"

until pg_isready --dbname "$database_url"; do
  echo "waiting for identity database..."
  sleep 2
done

psql --dbname "$database_url" -v ON_ERROR_STOP=1 -v probe_table="$probe_table" <<'SQL'
BEGIN;
SELECT current_database(), current_user, current_setting('server_version_num');
CREATE TABLE public.:"probe_table" (value text NOT NULL);
INSERT INTO public.:"probe_table" VALUES ('identity-preflight');
SELECT value FROM public.:"probe_table";
DROP TABLE public.:"probe_table";
ROLLBACK;
SQL
echo "Identity data-service preflight completed successfully"
