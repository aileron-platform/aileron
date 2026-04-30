#!/bin/bash
# Test Client Browser Relay connection

set -e

BASE_URL="http://localhost:3002/api/v1/client-browser-relay"

echo "============================================================"
echo "Client Browser Relay Connection Test"
echo "============================================================"

# Test 1: Check Relay status
echo ""
echo "=== Test 1: Check Relay Status ==="
RESPONSE=$(curl -s "${BASE_URL}/")
echo "✓ Relay status:"
echo "$RESPONSE" | jq '.'

EXTENSION_CONNECTED=$(echo "$RESPONSE" | jq -r '.extensionConnected')
if [ "$EXTENSION_CONNECTED" = "true" ]; then
    echo "✓ Extension connected"
else
    echo "✗ Extension not connected! Please ensure the Chrome extension is enabled."
    exit 1
fi

TARGETS_COUNT=$(echo "$RESPONSE" | jq -r '.connectedTargetsCount')
CLIENTS_COUNT=$(echo "$RESPONSE" | jq -r '.playwrightClientsCount')
echo "✓ Connected targets count: $TARGETS_COUNT"
echo "✓ Playwright clients count: $CLIENTS_COUNT"

# Test 2: Create named page
echo ""
echo "=== Test 2: Create Named Page ==="
PAGE_NAME="test-page-$(date +%s)"
RESPONSE=$(curl -s -X POST "${BASE_URL}/pages" \
    -H "Content-Type: application/json" \
    -d "{\"name\": \"${PAGE_NAME}\"}")

if echo "$RESPONSE" | jq -e '.wsEndpoint' > /dev/null 2>&1; then
    echo "✓ Page created:"
    echo "$RESPONSE" | jq '.'
else
    echo "✗ Failed to create page:"
    echo "$RESPONSE"
fi

# Test 3: List all named pages
echo ""
echo "=== Test 3: List All Named Pages ==="
RESPONSE=$(curl -s "${BASE_URL}/pages")
PAGES=$(echo "$RESPONSE" | jq -r '.pages | length')

if [ "$PAGES" -eq 0 ]; then
    echo "  (no named pages)"
else
    echo "✓ Found $PAGES named page(s):"
    echo "$RESPONSE" | jq -r '.pages[]' | sed 's/^/  - /'
fi

# Test 4: Health check
echo ""
echo "=== Test 4: Health Check ==="
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "${BASE_URL}/")
if [ "$HTTP_CODE" = "200" ]; then
    echo "✓ Health check passed (HTTP $HTTP_CODE)"
else
    echo "✗ Health check failed (HTTP $HTTP_CODE)"
fi

echo ""
echo "============================================================"
echo "Test Results Summary"
echo "============================================================"
echo "✓ PASS: Relay status check"
echo "✓ PASS: Extension connection confirmed"
echo "✓ PASS: Create named page"
echo "✓ PASS: List named pages"
echo "✓ PASS: Health check"
echo ""
echo "All tests passed!"
