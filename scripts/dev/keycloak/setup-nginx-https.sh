#!/bin/bash

# Keycloak HTTPS 設置腳本（使用 Nginx 反向代理）
# 此腳本設置本地開發環境的 HTTPS 訪問

set -e

# 顏色輸出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== Keycloak HTTPS 設置（Nginx 反向代理）===${NC}"
echo ""

# 檢查是否已安裝 nginx
if ! command -v nginx &> /dev/null; then
    echo -e "${YELLOW}Nginx 未安裝${NC}"
    echo ""
    echo "請先安裝 nginx："
    echo "  macOS:   brew install nginx"
    echo "  Ubuntu:  sudo apt-get install nginx"
    echo "  CentOS:  sudo yum install nginx"
    exit 1
fi

echo -e "${GREEN}✓ Nginx 已安裝${NC}"
echo ""

# 創建 SSL 證書目錄
SSL_DIR="/etc/nginx/ssl"
sudo mkdir -p "$SSL_DIR"

echo -e "${YELLOW}生成自簽名 SSL 證書...${NC}"
sudo openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
    -keyout "$SSL_DIR/keycloak.key" \
    -out "$SSL_DIR/keycloak.crt" \
    -subj "/C=TW/ST=Taipei/L=Taipei/O=Dev/CN=keycloak.local"

echo -e "${GREEN}✓ SSL 證書已生成${NC}"
echo ""

# 複製 nginx 配置
NGINX_CONF_DIR="/opt/homebrew/etc/nginx"  # macOS Homebrew 路徑
if [ ! -d "$NGINX_CONF_DIR" ]; then
    NGINX_CONF_DIR="/etc/nginx"  # Linux 路徑
fi

echo -e "${YELLOW}安裝 Nginx 配置...${NC}"
sudo cp "$(dirname "$0")/../../../nginx-keycloak.conf" "$NGINX_CONF_DIR/conf.d/keycloak.conf"

echo -e "${GREEN}✓ Nginx 配置已安裝${NC}"
echo ""

# 更新 /etc/hosts
echo -e "${YELLOW}更新 /etc/hosts...${NC}"
if ! grep -q "keycloak.local" /etc/hosts; then
    echo "127.0.0.1 keycloak.local" | sudo tee -a /etc/hosts > /dev/null
    echo -e "${GREEN}✓ /etc/hosts 已更新${NC}"
else
    echo -e "${YELLOW}⚠ /etc/hosts 已包含 keycloak.local${NC}"
fi
echo ""

# 測試 nginx 配置
echo -e "${YELLOW}測試 Nginx 配置...${NC}"
if sudo nginx -t; then
    echo -e "${GREEN}✓ Nginx 配置正確${NC}"
else
    echo -e "${RED}✗ Nginx 配置有誤${NC}"
    exit 1
fi
echo ""

# 重啟 nginx
echo -e "${YELLOW}重啟 Nginx...${NC}"
if sudo nginx -s reload 2>/dev/null || sudo brew services restart nginx 2>/dev/null; then
    echo -e "${GREEN}✓ Nginx 已重啟${NC}"
else
    echo -e "${YELLOW}⚠ 請手動重啟 Nginx${NC}"
fi
echo ""

echo -e "${GREEN}=== 設置完成 ===${NC}"
echo ""
echo -e "${YELLOW}訪問 Keycloak Admin Console:${NC}"
echo "  URL: https://keycloak.local/auth/admin"
echo "  用戶名: admin"
echo "  密碼: admin"
echo ""
echo -e "${YELLOW}注意：${NC}"
echo "  - 瀏覽器會顯示安全警告（自簽名證書）"
echo "  - 點擊「高級」→「繼續訪問」即可"
echo ""
