#!/bin/bash

# Keycloak Realm 配置驗證腳本
# 在完成 realm 和 client 創建後運行此腳本驗證配置

set -e

# 顏色輸出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Keycloak 配置
KEYCLOAK_URL="http://localhost:8080"
REALM_NAME="aileron"
CLIENT_ID="aileron-frontend"

echo -e "${GREEN}=== Keycloak Realm 配置驗證 ===${NC}"
echo ""

# 1. 測試 Realm 端點
echo -e "${YELLOW}1. 測試 Realm 端點...${NC}"
REALM_ENDPOINT="${KEYCLOAK_URL}/realms/${REALM_NAME}"
if curl -s -f "${REALM_ENDPOINT}" > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Realm 端點可訪問${NC}"
    echo "  URL: ${REALM_ENDPOINT}"
else
    echo -e "${RED}✗ Realm 端點無法訪問${NC}"
    echo -e "${YELLOW}  請確認 realm '${REALM_NAME}' 已創建${NC}"
    exit 1
fi
echo ""

# 2. 測試 OpenID Connect 配置
echo -e "${YELLOW}2. 測試 OpenID Connect 配置...${NC}"
OIDC_CONFIG=$(curl -s "${REALM_ENDPOINT}/.well-known/openid-configuration")
if echo "$OIDC_CONFIG" | jq -e '.issuer' > /dev/null 2>&1; then
    echo -e "${GREEN}✓ OpenID Connect 配置正確${NC}"
    echo "  Issuer: $(echo "$OIDC_CONFIG" | jq -r '.issuer')"
    echo "  Auth endpoint: $(echo "$OIDC_CONFIG" | jq -r '.authorization_endpoint')"
    echo "  Token endpoint: $(echo "$OIDC_CONFIG" | jq -r '.token_endpoint')"
else
    echo -e "${RED}✗ OpenID Connect 配置錯誤${NC}"
    exit 1
fi
echo ""

# 3. 測試 JWKS 端點
echo -e "${YELLOW}3. 測試 JWKS 端點（公鑰）...${NC}"
JWKS=$(curl -s "${REALM_ENDPOINT}/protocol/openid-connect/certs")
if echo "$JWKS" | jq -e '.keys' > /dev/null 2>&1; then
    KEY_COUNT=$(echo "$JWKS" | jq '.keys | length')
    echo -e "${GREEN}✓ JWKS 端點正常${NC}"
    echo "  可用公鑰數量: ${KEY_COUNT}"
else
    echo -e "${RED}✗ JWKS 端點錯誤${NC}"
    exit 1
fi
echo ""

# 4. 顯示 Realm 資訊
echo -e "${YELLOW}4. Realm 資訊...${NC}"
REALM_INFO=$(curl -s "${REALM_ENDPOINT}")
echo "  Realm: $(echo "$REALM_INFO" | jq -r '.realm')"
echo "  Display name: $(echo "$REALM_INFO" | jq -r '.displayName // "N/A"')"
echo "  Enabled: $(echo "$REALM_INFO" | jq -r '.enabled')"
echo ""

# 5. 顯示配置摘要
echo -e "${GREEN}=== 配置摘要 ===${NC}"
echo ""
echo "Realm URL:"
echo "  ${REALM_ENDPOINT}"
echo ""
echo "OpenID Connect 配置:"
echo "  ${REALM_ENDPOINT}/.well-known/openid-configuration"
echo ""
echo "JWKS 端點:"
echo "  ${REALM_ENDPOINT}/protocol/openid-connect/certs"
echo ""
echo "授權端點:"
AUTH_ENDPOINT=$(echo "$OIDC_CONFIG" | jq -r '.authorization_endpoint')
echo "  ${AUTH_ENDPOINT}"
echo ""
echo "Token 端點:"
TOKEN_ENDPOINT=$(echo "$OIDC_CONFIG" | jq -r '.token_endpoint')
echo "  ${TOKEN_ENDPOINT}"
echo ""
echo "登出端點:"
LOGOUT_ENDPOINT=$(echo "$OIDC_CONFIG" | jq -r '.end_session_endpoint')
echo "  ${LOGOUT_ENDPOINT}"
echo ""

# 6. 測試授權 URL 生成
echo -e "${YELLOW}6. 測試授權 URL（可選登入測試）...${NC}"
AUTH_URL="${AUTH_ENDPOINT}?client_id=${CLIENT_ID}&redirect_uri=http://localhost:8082/&response_type=code&scope=openid"
echo "  測試 URL:"
echo "  ${AUTH_URL}"
echo ""
echo -e "${YELLOW}  在瀏覽器中打開上述 URL 進行登入測試${NC}"
echo ""

echo -e "${GREEN}=== 驗證完成 ===${NC}"
echo ""
echo -e "${YELLOW}下一步：${NC}"
echo "1. 更新 workspace-manager/.env 中的 KEYCLOAK_CLIENT_SECRET"
echo "2. 設置 ENABLE_AUTH=true"
echo "3. 執行資料庫遷移: ./scripts/db/run-migrations.sh"
echo "4. 啟動 Workspace Manager 並測試認證流程"
echo ""
