# Keycloak 配置指南

**用途：** 配置 Keycloak 用於 Aileron OAuth2/OIDC 認證
**Keycloak 版本：** 25.0.0
**當前狀態：** Keycloak 已啟動但需要配置 realm 和 client

---

## 📋 前置條件

1. ✅ Docker 和 Docker Compose 已安裝
2. ✅ Keycloak 容器正在運行（http://localhost:8080）
3. ⚠️ 需要創建 realm 和 OAuth2 client

---

## 🔧 方法 1：使用 Web Console（推薦用於快速設置）

### 步驟 1：訪問 Keycloak Admin Console

1. 打開瀏覽器訪問：http://localhost:8080/admin
2. 使用管理員帳號登入：
   - 用戶名：`admin`
   - 密碼：`admin`

⚠️ **注意：** 如果看到 SSL 錯誤，這是因為 Keycloak 25.0.0 默認要求 HTTPS。由於我們在開發環境使用 HTTP，容器間通信沒問題，但瀏覽器訪問會有警告。

### 步驟 2：創建 Realm

1. 在左上角 realm 下拉菜單中，點擊 "Create realm"
2. 輸入 realm 名稱：`aileron`
3. 點擊 "Create"

### 步驟 3：創建 OAuth2 Client

1. 點擊左側菜單的 "Clients"
2. 點擊 "Create client"
3. 填寫表單：
   - **Client type:** OpenID Connect
   - **Client ID:** `workspace-manager`
   - **Client authentication:** ON
   - **Authentication flow:** 標準流程
     - ✅ Standard flow (勾選)
     - ✅ Direct access grants (勾選)
4. 點擊 "Next"
5. 配置 URL settings：
   - **Valid redirect URIs:**
     ```
     http://localhost:3001/api/v1/oauth2/callback
     http://localhost:8082/*
     ```
   - **Valid post logout redirect URIs:**
     ```
     http://localhost:3001/*
     http://localhost:8082/*
     ```
   - **Web origins:**
     ```
     http://localhost:3001
     http://localhost:8082
     ```
6. 點擊 "Save"

### 步驟 4：獲取 Client Secret

1. 點擊 "Clients" → 選擇 "workspace-manager"
2. 點擊 "Credentials" 標籤
3. 複製 **Client secret**（之後需要用於環境變數配置）

### 步驟 5：創建測試用戶（可選）

1. 點擊 "Users"
2. 點擊 "Add user"
3. 輸入：
   - **Username:** `testuser`
   - **Email:** `test@example.com`
   - **First name:** `Test`
   - **Last name:** `User`
   - **Email verified:** ON
4. 點擊 "Create"
5. 點擊 "Credentials" 標籤
6. 設置密碼：
   - 點擊 "Set password"
   - 輸入密碼：`test123`
   - 點擊 "Save"
   - **Temporary:** OFF（關閉臨時密碼）
7. 再次點擊 "Set password" 確認

### 步驟 6：配置用戶角色（可選）

1. 點擊 "Users" → 選擇 "testuser"
2. 點擊 "Role mapping" 標籤
3. 在 "Assign role" 下拉中：
   - 選擇 realm roles
   - 選擇 `admin` 或其他角色
4. 點擊 "Add assigned"

---

## 🔧 方法 2：使用 CLI 腳本（推薦用於自動化）

### 創建配置腳本<tool_call>Write<arg_key>content</arg_key><arg_value>#!/bin/bash

# Keycloak 配置腳本
# 用於自動化創建 realm、client 和用戶

set -e

# 配置變數
KEYCLOAK_URL="http://localhost:8080"
ADMIN_USER="admin"
ADMIN_PASSWORD="admin"
REALM_NAME="aileron"
CLIENT_ID="workspace-manager"
CLIENT_SECRET="workspace-manager-secret-12345"
REDIRECT_URI="http://localhost:3001/api/v1/oauth2/callback"
TEST_USER="testuser"
TEST_PASSWORD="test123"

echo "🔧 配置 Keycloak..."
echo "Realm: $REALM_NAME"
echo "Client: $CLIENT_ID"
echo ""

# 等待 Keycloak 啟動
echo "⏳ 等待 Keycloak 啟動..."
until curl -s "$KEYCLOAK_URL/health/ready" > /dev/null; do
    echo "   還未就緒，等待 5 秒..."
    sleep 5
done
echo "✅ Keycloak 已就緒"
echo ""

# 登入 Keycloak Admin CLI
echo "🔑 登入 Keycloak Admin..."
kcadm.sh config credentials \
    --server "$KEYCLOAK_URL" \
    --realm master \
    --user "$ADMIN_USER" \
    --password "$ADMIN_PASSWORD"

echo ""

# 創建 realm
echo "🌍 創建 realm: $REALM_NAME"
kcadm.sh create realms \
    -s realm="$REALM_NAME" \
    -s enabled=true \
    -s displayName="Aileron" \
    -s registrationAllowed=true \
    -s loginWithEmailAllowed=true \
    -s duplicateEmailsAllowed=false \
    -s resetPasswordAllowed=true \
    -s editUsernameAllowed=true \
    -s bruteForceProtected=true

echo "✅ Realm 創建成功"
echo ""

# 創建 client
echo "📱 創建 OAuth2 client: $CLIENT_ID"
CLIENT_ID=$(kcadm.sh create clients \
    -r "$REALM_NAME" \
    -s clientId="$CLIENT_ID" \
    -s enabled=true \
    -s clientAuthenticatorType=client-secret \
    -s secret="$CLIENT_SECRET" \
    -s redirectUris="[$REDIRECT_URI]" \
    -s webOrigins="[http://localhost:3001,http://localhost:8082]" \
    -s standardFlowEnabled=true \
    -s directAccessGrantsEnabled=true \
    -s serviceAccountsEnabled=true \
    -s publicClient=false \
    -s fullScopeAllowed=false \
    -i)

echo "✅ Client 創建成功: $CLIENT_ID"
echo ""

# 創建角色
echo "👤 創建角色..."
kcadm.sh create roles \
    -r "$REALM_NAME" \
    -s name=admin \
    -s description="Administrator"

kcadm.sh create roles \
    -r "$REALM_NAME" \
    -s name=developer \
    -s description="Developer"

kcadm.sh create roles \
    -r "$REALM_NAME" \
    -s name=user \
    -s description="Standard user"

kcadm.sh create roles \
    -r "$REALM_NAME" \
    -s name=viewer \
    -s description="Read-only viewer"

echo "✅ 角色創建成功"
echo ""

# 創建測試用戶
echo "👤 創建測試用戶: $TEST_USER"
USER_ID=$(kcadm.sh create users \
    -r "$REALM_NAME" \
    -s username="$TEST_USER" \
    -s enabled=true \
    -s emailVerified=true \
    -s email="test@example.com" \
    -s firstName="Test" \
    -s lastName="User" \
    -i)

# 設置用戶密碼
kcadm.sh set-password \
    -r "$REALM_NAME" \
    --username "$TEST_USER" \
    --new-password "$TEST_PASSWORD"

# 分配 user 角色給測試用戶
ROLE_ID=$(kcadm.sh get roles \
    -r "$REALM_NAME" \
    --role-name user \
    -q id)

kcadm.sh add-roles \
    -r "$REALM_NAME" \
    --uusername "$TEST_USER" \
    --rolename user \
    --cclientid "$CLIENT_ID"

echo "✅ 測試用戶創建成功"
echo ""

# 創建 admin 用戶
echo "👤 創建 admin 用戶: admin"
kcadm.sh create users \
    -r "$REALM_NAME" \
    -s username="admin" \
    -s enabled=true \
    -s emailVerified=true \
    -s email="admin@example.com" \
    -s firstName="Admin" \
    -s lastName="User"

kcadm.sh set-password \
    -r "$REALM_NAME" \
    --username "admin" \
    --new-password "admin123"

# 分配 admin 角色
kcadm.sh add-roles \
    -r "$REALM_NAME" \
    --uusername "admin" \
    --rolename admin \
    --cclientid "$CLIENT_ID"

echo "✅ Admin 用戶創建成功"
echo ""

echo "🎉 Keycloak 配置完成！"
echo ""
echo "📝 配置信息："
echo "   - Realm: $REALM_NAME"
echo "   - Client ID: $CLIENT_ID"
echo "   - Client Secret: $CLIENT_SECRET"
echo "   - 測試用戶: $TEST_USER / $TEST_PASSWORD"
echo "   - Admin 用戶: admin / admin123"
echo ""
echo "🔗 管理控制台: http://localhost:8080/admin"
echo "   - Realm: $REALM_NAME"
echo "   - 用戶名: $ADMIN_USER"
echo "   - 密碼: $ADMIN_PASSWORD"
echo ""
