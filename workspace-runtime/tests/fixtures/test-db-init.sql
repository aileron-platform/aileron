-- 測試資料庫初始化腳本
-- 此腳本在PostgreSQL測試容器首次啟動時執行

-- 啟用必要的擴展
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- 設置時區為UTC
SET timezone = 'UTC';

-- 創建測試用戶（唯讀）
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'test_readonly') THEN
        CREATE USER test_readonly WITH PASSWORD 'readonly_password';
    END IF;
END
$$;

-- 授予連接權限
GRANT CONNECT ON DATABASE test_workspace_runtime TO test_readonly;
GRANT USAGE ON SCHEMA public TO test_readonly;

-- 創建函數：授予現有和未來表的SELECT權限
CREATE OR REPLACE FUNCTION grant_readonly_permissions()
RETURNS void AS $$
BEGIN
    -- 授予現有表的SELECT權限
    EXECUTE (
        SELECT string_agg('GRANT SELECT ON ' || schemaname || '.' || tablename || ' TO test_readonly;', E'\n')
        FROM pg_tables
        WHERE schemaname = 'public'
    );

    -- 為未來的表設置默認權限
    ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO test_readonly;
END;
$$ LANGUAGE plpgsql;

-- 優化測試資料庫設置
-- 注意：fsync 和 full_page_writes 已在 docker-compose.test.yml 中通過 postgres 命令參數設置
ALTER DATABASE test_workspace_runtime SET synchronous_commit = off;

-- 輸出完成訊息
DO $$
BEGIN
    RAISE NOTICE '✅ Test database initialized successfully';
    RAISE NOTICE '📊 Available extensions: uuid-ossp, pg_trgm';
    RAISE NOTICE '👤 Test users: test_user (full access), test_readonly (read-only)';
END
$$;
