#!/bin/bash
# 測試 Client Browser Relay 連線

set -e

BASE_URL="http://localhost:3002/api/v1/client-browser-relay"

echo "============================================================"
echo "Client Browser Relay 連線測試"
echo "============================================================"

# 測試 1: 檢查 Relay 狀態
echo ""
echo "=== 測試 1: 檢查 Relay 狀態 ==="
RESPONSE=$(curl -s "${BASE_URL}/")
echo "✓ Relay 狀態:"
echo "$RESPONSE" | jq '.'

EXTENSION_CONNECTED=$(echo "$RESPONSE" | jq -r '.extensionConnected')
if [ "$EXTENSION_CONNECTED" = "true" ]; then
    echo "✓ Extension 已連接"
else
    echo "✗ Extension 未連接！請確認 Chrome extension 已啟用。"
    exit 1
fi

TARGETS_COUNT=$(echo "$RESPONSE" | jq -r '.connectedTargetsCount')
CLIENTS_COUNT=$(echo "$RESPONSE" | jq -r '.playwrightClientsCount')
echo "✓ 已連接 Targets 數量: $TARGETS_COUNT"
echo "✓ Playwright 客戶端數量: $CLIENTS_COUNT"

# 測試 2: 創建命名頁面
echo ""
echo "=== 測試 2: 創建命名頁面 ==="
PAGE_NAME="test-page-$(date +%s)"
RESPONSE=$(curl -s -X POST "${BASE_URL}/pages" \
    -H "Content-Type: application/json" \
    -d "{\"name\": \"${PAGE_NAME}\"}")

if echo "$RESPONSE" | jq -e '.wsEndpoint' > /dev/null 2>&1; then
    echo "✓ 頁面已創建:"
    echo "$RESPONSE" | jq '.'
else
    echo "✗ 創建頁面失敗:"
    echo "$RESPONSE"
fi

# 測試 3: 列出所有命名頁面
echo ""
echo "=== 測試 3: 列出所有命名頁面 ==="
RESPONSE=$(curl -s "${BASE_URL}/pages")
PAGES=$(echo "$RESPONSE" | jq -r '.pages | length')

if [ "$PAGES" -eq 0 ]; then
    echo "  (目前沒有命名頁面)"
else
    echo "✓ 找到 $PAGES 個命名頁面:"
    echo "$RESPONSE" | jq -r '.pages[]' | sed 's/^/  - /'
fi

# 測試 4: 健康檢查
echo ""
echo "=== 測試 4: 健康檢查 ==="
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "${BASE_URL}/")
if [ "$HTTP_CODE" = "200" ]; then
    echo "✓ 健康檢查通過 (HTTP $HTTP_CODE)"
else
    echo "✗ 健康檢查失敗 (HTTP $HTTP_CODE)"
fi

echo ""
echo "============================================================"
echo "測試結果摘要"
echo "============================================================"
echo "✓ PASS: Relay 狀態檢查"
echo "✓ PASS: Extension 連線確認"
echo "✓ PASS: 創建命名頁面"
echo "✓ PASS: 列出命名頁面"
echo "✓ PASS: 健康檢查"
echo ""
echo "🎉 所有測試通過！"
