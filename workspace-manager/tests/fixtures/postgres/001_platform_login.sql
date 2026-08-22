CREATE ROLE platform_login
    WITH LOGIN NOSUPERUSER NOCREATEDB CREATEROLE INHERIT NOREPLICATION NOBYPASSRLS
    PASSWORD 'platform_password';

ALTER DATABASE test_workspace_manager OWNER TO platform_login;
GRANT pg_signal_backend TO platform_login;

CREATE ROLE platform_without_signal
    WITH LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS
    PASSWORD 'platform_without_signal_password';
