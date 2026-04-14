#!/bin/bash

# Keycloak Realm 和 Client 自動設置腳本
# 此腳本自動創建 realm、client 並生成 client secret

set -e

# 顏色輸出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Keycloak 配置
KEYCLOAK_URL="http://localhost:8080"
ADMIN_USERNAME="admin"
ADMIN_PASSWORD="admin"
REALM_NAME="aileron"
CLIENT_ID="aileron-frontend"
REDIRECT_URI="http://localhost:8082/*"

echo -e "${GREEN}=== Keycloak Realm 和 Client 自動設置 ===${NC}"
echo ""

# 檢查 Keycloak 是否運行
echo -e "${YELLOW}1. 檢查 Keycloak 服務...${NC}"
if ! curl -s "${KEYCLOAK_URL}/realms/master" | jq -e '.realm == "master"' > /dev/null 2>&1; then
    echo -e "${RED}✗ Keycloak 服務未運行${NC}"
    echo "請先啟動 Keycloak: docker-compose up -d keycloak"
    exit 1
fi
echo -e "${GREEN}✓ Keycloak 服務正常${NC}"
echo ""

# 獲取 Admin Token
echo -e "${YELLOW}2. 獲取 Admin Token...${NC}"
ADMIN_TOKEN=$(curl -s -X POST "${KEYCLOAK_URL}/realms/master/protocol/openid-connect/token" \
    -H "Content-Type: application/x-www-form-urlencoded" \
    -d "username=${ADMIN_USERNAME}" \
    -d "password=${ADMIN_PASSWORD}" \
    -d "grant_type=password" \
    -d "client_id=admin-cli" | jq -r '.access_token')

if [ "$ADMIN_TOKEN" == "null" ] || [ -z "$ADMIN_TOKEN" ]; then
    echo -e "${RED}✗ 無法獲取 Admin Token${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Admin Token 獲取成功${NC}"
echo ""

# 創建 Realm
echo -e "${YELLOW}3. 創建 Realm: ${REALM_NAME}...${NC}"
REALM_EXISTS=$(curl -s -X GET "${KEYCLOAK_URL}/admin/realms" \
    -H "Authorization: Bearer ${ADMIN_TOKEN}" | jq -r ".[] | select(.realm==\"${REALM_NAME}\") | .realm")

if [ "$REALM_EXISTS" == "$REALM_NAME" ]; then
    echo -e "${YELLOW}⚠ Realm '${REALM_NAME}' 已存在${NC}"
else
    curl -s -X POST "${KEYCLOAK_URL}/admin/realms" \
        -H "Authorization: Bearer ${ADMIN_TOKEN}" \
        -H "Content-Type: application/json" \
        -d "{
            \"realm\": \"${REALM_NAME}\",
            \"enabled\": true,
            \"displayName\": \"Aileron\",
            \"registrationAllowed\": false,
            \"loginWithEmailAllowed\": true,
            \"duplicateEmailsAllowed\": false,
            \"resetPasswordAllowed\": true,
            \"editUsernameAllowed\": false,
            \"bruteForceProtected\": true
        }" > /dev/null

    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ Realm 創建成功${NC}"
    else
        echo -e "${RED}✗ Realm 創建失敗${NC}"
        exit 1
    fi
fi
echo ""

# 創建 Client
echo -e "${YELLOW}4. 創建 Client: ${CLIENT_ID}...${NC}"
CLIENT_EXISTS=$(curl -s -X GET "${KEYCLOAK_URL}/admin/realms/${REALM_NAME}/clients" \
    -H "Authorization: Bearer ${ADMIN_TOKEN}" | jq -r ".[] | select(.clientId==\"${CLIENT_ID}\") | .clientId")

if [ "$CLIENT_EXISTS" == "$CLIENT_ID" ]; then
    echo -e "${YELLOW}⚠ Client '${CLIENT_ID}' 已存在${NC}"
    # 獲取現有 client secret
    CLIENT_SECRET=$(curl -s -X GET "${KEYCLOAK_URL}/admin/realms/${REALM_NAME}/clients" \
        -H "Authorization: Bearer ${ADMIN_TOKEN}" | jq -r ".[] | select(.clientId==\"${CLIENT_ID}\") | .id")

    if [ "$CLIENT_SECRET" != "null" ] && [ -n "$CLIENT_SECRET" ]; then
        CLIENT_SECRET=$(curl -s -X GET "${KEYCLOAK_URL}/admin/realms/${REALM_NAME}/clients/${CLIENT_SECRET}/client-secret" \
            -H "Authorization: Bearer ${ADMIN_TOKEN}" | jq -r '.value')
    fi
else
    # 創建新 client
    CLIENT_RESPONSE=$(curl -s -X POST "${KEYCLOAK_URL}/admin/realms/${REALM_NAME}/clients" \
        -H "Authorization: Bearer ${ADMIN_TOKEN}" \
        -H "Content-Type: application/json" \
        -d "{
            \"clientId\": \"${CLIENT_ID}\",
            \"enabled\": true,
            \"clientAuthenticatorType\": \"client-secret\",
            \"redirectUris\": [\"${REDIRECT_URI}\"],
            \"webOrigins\": [\"http://localhost:8082\"],
            \"publicClient\": false,
            \"protocol\": \"openid-connect\",
            \"standardFlowEnabled\": true,
            \"implicitFlowEnabled\": false,
            \"directAccessGrantsEnabled\": true,
            \"serviceAccountsEnabled\": false,
            \"validRedirectUris\": [\"${REDIRECT_URI}\"],
            \"baseUrl\": \"http://localhost:8082\",
            \"adminUrl\": \"http://localhost:8082\"
        }")

    # 獲取 client ID (UUID)
    sleep 1  # 等待 client 創建完成
    CLIENT_UUID=$(curl -s -X GET "${KEYCLOAK_URL}/admin/realms/${REALM_NAME}/clients" \
        -H "Authorization: Bearer ${ADMIN_TOKEN}" | jq -r ".[] | select(.clientId==\"${CLIENT_ID}\") | .id")

    if [ "$CLIENT_UUID" != "null" ] && [ -n "$CLIENT_UUID" ]; then
        # 獲取 client secret
        CLIENT_SECRET=$(curl -s -X GET "${KEYCLOAK_URL}/admin/realms/${REALM_NAME}/clients/${CLIENT_UUID}/client-secret" \
            -H "Authorization: Bearer ${ADMIN_TOKEN}" | jq -r '.value')

        if [ "$CLIENT_SECRET" != "null" ] && [ -n "$CLIENT_SECRET" ]; then
            echo -e "${GREEN}✓ Client 創建成功${NC}"
        else
            echo -e "${RED}✗ 無法獲取 Client Secret${NC}"
            exit 1
        fi
    else
        echo -e "${RED}✗ Client 創建失敗${NC}"
        exit 1
    fi
fi
echo ""

# 創建測試用戶
echo -e "${YELLOW}5. 創建測試用戶...${NC}"
TEST_USER_EXISTS=$(curl -s -X GET "${KEYCLOAK_URL}/admin/realms/${REALM_NAME}/users?username=testuser" \
    -H "Authorization: Bearer ${ADMIN_TOKEN}" | jq -r '.[0].username')

if [ "$TEST_USER_EXISTS" == "testuser" ]; then
    echo -e "${YELLOW}⚠ 測試用戶 'testuser' 已存在${NC}"
else
    # 創建測試用戶
    curl -s -X POST "${KEYCLOAK_URL}/admin/realms/${REALM_NAME}/users" \
        -H "Authorization: Bearer ${ADMIN_TOKEN}" \
        -H "Content-Type: application/json" \
        -d "{
            \"username\": \"testuser\",
            \"enabled\": true,
            \"emailVerified\": true,
            \"email\": \"testuser@example.com\",
            \"firstName\": \"Test\",
            \"lastName\": \"User\",
            \"credentials\": [{
                \"type\": \"password\",
                \"value\": \"testpass123\",
                \"temporary\": false
            }]
        }" > /dev/null

    echo -e "${GREEN}✓ 測試用戶創建成功${NC}"
    echo "  用戶名: testuser"
    echo "  密碼: testpass123"
fi
echo ""

# 顯示配置信息
echo -e "${GREEN}=== 設置完成 ===${NC}"
echo ""
echo -e "${YELLOW}Realm 資訊:${NC}"
echo "  Realm Name: ${REALM_NAME}"
echo "  Realm URL: ${KEYCLOAK_URL}/realms/${REALM_NAME}"
echo ""
echo -e "${YELLOW}Client 資訊:${NC}"
echo "  Client ID: ${CLIENT_ID}"
echo -e "${GREEN}  Client Secret: ${CLIENT_SECRET}${NC}"
echo ""
echo -e "${YELLOW}測試帳號:${NC}"
echo "  用戶名: testuser"
echo "  密碼: testpass123"
echo ""
echo -e "${YELLOW}Admin Console:${NC}"
echo "  URL: ${KEYCLOAK_URL}/auth/admin"
echo "  用戶名: ${ADMIN_USERNAME}"
echo "  密碼: ${ADMIN_PASSWORD}"
echo ""

# 提示更新環境變數
echo -e "${GREEN}=== 下一步 ===${NC}"
echo ""
echo "請更新 workspace-manager/.env 文件："
echo ""
echo "KEYCLOAK_CLIENT_SECRET=${CLIENT_SECRET}"
echo ""
echo "並設置 ENABLE_AUTH=true 以啟用認證功能"
echo ""
