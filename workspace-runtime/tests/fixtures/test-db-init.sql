-- Test database initialization script
-- This script runs on first startup of the PostgreSQL test container

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- Set timezone to UTC
SET timezone = 'UTC';

-- Create read-only test user
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'test_readonly') THEN
        CREATE USER test_readonly WITH PASSWORD 'readonly_password';
    END IF;
END
$$;

-- Grant connection privileges
GRANT CONNECT ON DATABASE test_workspace_runtime TO test_readonly;
GRANT USAGE ON SCHEMA public TO test_readonly;

-- Create function to grant SELECT on existing and future tables
CREATE OR REPLACE FUNCTION grant_readonly_permissions()
RETURNS void AS $$
BEGIN
    -- Grant SELECT on existing tables
    EXECUTE (
        SELECT string_agg('GRANT SELECT ON ' || schemaname || '.' || tablename || ' TO test_readonly;', E'\n')
        FROM pg_tables
        WHERE schemaname = 'public'
    );

    -- Set default privileges for future tables
    ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO test_readonly;
END;
$$ LANGUAGE plpgsql;

-- Optimize test database settings
-- Note: fsync and full_page_writes are set via postgres command parameters in docker-compose.test.yml
ALTER DATABASE test_workspace_runtime SET synchronous_commit = off;

-- Output completion message
DO $$
BEGIN
    RAISE NOTICE '✅ Test database initialized successfully';
    RAISE NOTICE '📊 Available extensions: uuid-ossp, pg_trgm';
    RAISE NOTICE '👤 Test users: test_user (full access), test_readonly (read-only)';
END
$$;
