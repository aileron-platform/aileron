#!/bin/bash
# Keycloak 服務驗證腳本
# 用於驗證 Keycloak 服務是否正常啟動和配置

set -e

echo "=== Keycloak 服務驗證 ==="
echo ""

# 顏色定義
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 檢查 Keycloak 容器是否運行
echo -n "檢查 Keycloak 容器狀態... "
if docker ps --filter "name=aileron-keycloak-dev" --format "{{.Status}}" | grep -q "Up"; then
    echo -e "${GREEN}✓ 運行中${NC}"
else
    echo -e "${RED}✗ 未運行${NC}"
    echo ""
    echo "請先啟動 Keycloak："
    echo "  docker-compose up -d keycloak"
    exit 1
fi

# 等待 Keycloak 啟動
echo "等待 Keycloak 完全啟動..."
MAX_WAIT=60
WAIT_TIME=0
while [ $WAIT_TIME -lt $MAX_WAIT ]; do
    if curl -s http://localhost:8080/health/ready > /dev/null 2>&1; then
        echo -e "${GREEN}✓ Keycloak 已就緒${NC}"
        break
    fi
    sleep 2
    WAIT_TIME=$((WAIT_TIME + 2))
    echo -n "."
done

if [ $WAIT_TIME -ge $MAX_WAIT ]; then
    echo -e "${RED}✗ Keycloak 啟動超時${NC}"
    echo ""
    echo "請檢查 Keycloak 日誌："
    echo "  docker logs aileron-keycloak-dev"
    exit 1
fi

# 檢查 Keycloak OpenID Connect 配置
echo ""
echo -n "檢查 OpenID Connect 配置... "
if curl -s http://localhost:8080/realms/aileron/.well-known/openid-configuration > /dev/null 2>&1; then
    echo -e "${GREEN}✓ 配置正確${NC}"
else
    echo -e "${YELLOW}⚠ Realm 'aileron' 尚未創建${NC}"
    echo ""
    echo "請先創建 realm，參考文檔：docs/keycloak-setup.md"
fi

# 檢查 Keycloak Admin Console
echo ""
echo -n "檢查 Admin Console... "
if curl -s http://localhost:8080/auth/admin/ > /dev/null 2>&1; then
    echo -e "${GREEN}✓ 可訪問${NC}"
    echo "  URL: http://localhost:8080/auth/admin"
    echo "  用戶名: admin"
    echo "  密碼: admin"
    echo ""
    echo -e "${YELLOW}⚠ 警告：僅用於本地開發，請勿在生產環境使用預設密碼${NC}"
else
    echo -e "${RED}✗ 無法訪問${NC}"
fi

# 顯示環境變數配置
echo ""
echo "=== 環境變數配置 ==="
echo ""
echo "Keycloak Server URL: http://localhost:8080/realms/aileron"
echo "Realm: aileron"
echo "Client ID: aileron-frontend"
echo ""
echo "Frontend 配置 (frontend/.env.development):"
echo "  VITE_KEYCLOAK_SERVER_URL=http://localhost:8080"
echo "  VITE_KEYCLOAK_REALM=aileron"
echo "  VITE_KEYCLOAK_CLIENT_ID=aileron-frontend"
echo ""
echo "Workspace Manager 配置 (workspace-manager/.env):"
echo "  KEYCLOAK_SERVER_URL=http://keycloak:8080/realms/aileron"
echo "  KEYCLOAK_REALM=aileron"
echo "  KEYCLOAK_CLIENT_ID=aileron-frontend"
echo "  KEYCLOAK_CLIENT_SECRET=<your-client-secret>"
echo ""

# 測試端點訪問
echo "=== 測試 Keycloak 端點 ==="
echo ""

echo "1. OpenID Connect 配置端點："
echo "   http://localhost:8080/realms/aileron/.well-known/openid-configuration"
echo ""

echo "2. Realm Info 端點："
echo "   http://localhost:8080/realms/aileron"
echo ""

echo "3. Token 端點："
echo "   http://localhost:8080/realms/aileron/protocol/openid-connect/token"
echo ""

echo -e "${GREEN}=== 驗證完成 ===${NC}"
echo ""
echo "下一步："
echo "1. 如果 realm 尚未創建，請參考 docs/keycloak-setup.md"
echo "2. 設置完成後，可以開始實作 OAuth2 認證流程"
