-- 建立 Keycloak 所需的資料庫（若不存在）
-- 此腳本在 PostgreSQL 初始化時自動執行
SELECT 'CREATE DATABASE keycloak'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'keycloak')\gexec
