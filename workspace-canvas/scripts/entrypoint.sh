#!/bin/bash
# workspace-canvas 容器入口腳本
# 啟動 Canvas 管理 API 伺服器

set -e

echo "[Entrypoint] Starting workspace-canvas container..."
echo "[Entrypoint] WORKSPACE_DIR: ${WORKSPACE_DIR:-/workspace}"
echo "[Entrypoint] WEB_CANVAS_DIR: /web-canvas"
echo "[Entrypoint] PORT: ${PORT:-3003}"
echo "[Entrypoint] API_PORT: ${API_PORT:-3013}"

# 確保目錄權限正確
chown -R developer:developer /web-canvas 2>/dev/null || true
chown -R developer:developer /workspace 2>/dev/null || true

# 確保日誌目錄存在
mkdir -p /var/log/canvas
chown -R developer:developer /var/log/canvas

# 啟動管理 API（以 root 啟動，管理 API 會以 developer 身份啟動 renderer）
echo "[Entrypoint] Starting management server..."
exec node /canvas-management/server.js 2>&1 | tee /var/log/canvas/management.log
