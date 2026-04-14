#!/bin/bash
# workspace-nextjs 容器入口腳本
# 啟動管理 API 伺服器（會自動啟動 Next.js dev server）

set -e

echo "[Entrypoint] Starting workspace-nextjs container..."
echo "[Entrypoint] WORKSPACE_DIR: ${WORKSPACE_DIR:-/workspace}"
echo "[Entrypoint] WEB_PREVIEW_DIR: /web-preview"
echo "[Entrypoint] PORT: ${PORT:-3003}"
echo "[Entrypoint] API_PORT: ${API_PORT:-3013}"

# 確保目錄權限正確
chown -R developer:developer /web-preview 2>/dev/null || true
chown -R developer:developer /workspace 2>/dev/null || true

# 確保日誌目錄存在
mkdir -p /var/log/nextjs
chown -R developer:developer /var/log/nextjs

# 啟動管理 API（以 root 啟動，管理 API 會以 developer 身份啟動 Next.js）
echo "[Entrypoint] Starting management server..."
exec node /nextjs-management/server.js 2>&1 | tee /var/log/nextjs/management.log
