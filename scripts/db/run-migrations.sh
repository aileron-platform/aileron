#!/bin/bash
# 執行 Keycloak 認證相關的資料庫遷移
# 用於在 Workspace Manager 中添加 Keycloak 整合所需的欄位和表

set -e

# 顏色定義
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "=== Keycloak 認證資料庫遷移 ==="
echo ""

# 檢查 PostgreSQL 是否運行
echo -n "檢查 PostgreSQL 連接... "
if docker ps --filter "name=aileron-postgres-dev" --format "{{.Status}}" | grep -q "Up"; then
    echo -e "${GREEN}✓ PostgreSQL 運行中${NC}"
else
    echo -e "${RED}✗ PostgreSQL 未運行${NC}"
    echo "請先啟動 PostgreSQL：docker-compose up -d postgres"
    exit 1
fi

# 等待 PostgreSQL 準備就緒
echo "等待 PostgreSQL 準備就緒..."
until docker exec aileron-postgres-dev pg_isready -U postgres > /dev/null 2>&1; do
    sleep 1
    echo -n "."
done
echo -e " ${GREEN}✓ 就緒${NC}"
echo ""

# 執行遷移腳本
MIGRATIONS_DIR="workspace-manager/app/db/migrations"
MIGRATION_FILES=(
    "010_add_keycloak_id_to_users.sql"
    "011_add_roles_to_users.sql"
    "012_create_refresh_tokens_table.sql"
)

for migration in "${MIGRATION_FILES[@]}"; do
    migration_path="$MIGRATIONS_DIR/$migration"

    if [ ! -f "$migration_path" ]; then
        echo -e "${RED}✗ 遷移文件不存在: $migration_path${NC}"
        exit 1
    fi

    echo -n "執行 $migration... "

    # 複製並執行 SQL 文件
    if docker exec -i aileron-postgres-dev psql -U postgres -d aileron < "$migration_path" > /dev/null 2>&1; then
        echo -e "${GREEN}✓ 成功${NC}"
    else
        echo -e "${RED}✗ 失敗${NC}"
        echo "請檢查遷移文件語法"
        exit 1
    fi
done

echo ""
echo "=== 驗證資料庫結構 ==="
echo ""

# 驗證 users 表結構
echo "檢查 users 表欄位..."
docker exec aileron-postgres-dev psql -U postgres -d aileron -c "
    SELECT
        column_name,
        data_type,
        is_nullable,
        column_default
    FROM information_schema.columns
    WHERE table_name = 'users'
        AND column_name IN ('keycloak_id', 'roles')
    ORDER BY column_name;
" | tail -n +4

echo ""
echo "檢查索引..."
docker exec aileron-postgres-dev psql -U postgres -d aileron -c "
    SELECT
        indexname,
        indexdef
    FROM pg_indexes
    WHERE tablename = 'users'
        AND indexname LIKE '%keycloak_id%'
        OR indexname LIKE '%roles%';
" | tail -n +4

echo ""
echo "檢查 refresh_tokens 表結構..."
docker exec aileron-postgres-dev psql -U postgres -d aileron -c "
    SELECT
        column_name,
        data_type,
        is_nullable,
        column_default
    FROM information_schema.columns
    WHERE table_name = 'refresh_tokens'
    ORDER BY ordinal_position;
" | tail -n +4

echo ""
echo -e "${GREEN}=== 遷移完成 ===${NC}"
echo ""
echo "已完成的遷移："
echo "  ✓ 添加 keycloak_id 欄位到 users 表"
echo "  ✓ 添加 roles 欄位到 users 表"
echo "  ✓ 創建 refresh_tokens 表"
echo ""
echo "下一步："
echo "  1. 開始實作階段 3：Workspace Manager 認證模組基礎設施"
echo "  2. 安裝 Python 依賴：python-keycloak, python-jose[cryptography], httpx"
