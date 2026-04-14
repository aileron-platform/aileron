#!/bin/bash

# 啟動 FastAPI + Celery Worker + Flower 服務腳本 (使用 Supervisor)

set -e

# 清除空值環境變數，避免 .env 的空設定（如 ANTHROPIC_AUTH_TOKEN=）影響 container 行為
while IFS= read -r line; do
    [[ "$line" =~ ^([^=]+)=$ ]] && unset "${BASH_REMATCH[1]}"
done < <(env)

echo "🚀 啟動 Workspace Manager 服務..."

# 創建日誌目錄
mkdir -p /var/log/supervisor

# 設定環境變數
export PYTHONPATH="${PYTHONPATH}:/workspace-manager"

# 切換到工作目錄
cd /workspace-manager

# 確保虛擬環境正確安裝（解決 volume mount 導致的 .venv 失效問題）
echo "🔧 檢查並同步 Python 依賴..."
if [ "${NODE_ENV}" = "development" ]; then
    # 開發環境：包含 dev dependencies
    uv sync --dev 2>&1 | grep -v "warning:" || true
else
    # 生產環境：僅安裝生產依賴
    uv sync --no-dev 2>&1 | grep -v "warning:" || true
fi
echo "✅ Python 依賴已就緒"
echo ""

# 顯示配置資訊
echo "📋 服務配置:"
echo "   - FastAPI: http://0.0.0.0:3001"
echo "   - Celery Worker: 2 個並發進程"
echo "   - Celery Flower: http://0.0.0.0:5555"
echo "   - Celery Queues: default,container,docker,rebuild,local,firewall"
echo "   - Broker: ${CELERY_BROKER_URL:-redis://redis:6379/0}"
echo "   - Result Backend: ${CELERY_RESULT_BACKEND:-redis://redis:6379/1}"
echo ""

# 從 REDIS_URL 推導 host/port，避免 Kubernetes 僅提供 URL 時白等 30 秒
redis_url="${REDIS_URL:-redis://redis:6379/0}"
redis_target="${redis_url#redis://}"
redis_target="${redis_target#rediss://}"
redis_target="${redis_target#*@}"
redis_target="${redis_target%%/*}"

redis_host="${REDIS_HOST:-${redis_target%%:*}}"
redis_port="${REDIS_PORT:-6379}"

if [[ -n "${redis_target}" && "${redis_target}" == *:* ]]; then
    redis_port="${REDIS_PORT:-${redis_target##*:}}"
fi

if [ -z "${redis_host}" ]; then
    redis_host="redis"
fi

# 等待 Redis 可用
echo "⏳ 等待 Redis 服務..."
timeout=30
echo "   - Redis Host: ${redis_host}"
echo "   - Redis Port: ${redis_port}"
while ! redis-cli -h "${redis_host}" -p "${redis_port}" ping > /dev/null 2>&1; do
    timeout=$((timeout - 1))
    if [ $timeout -eq 0 ]; then
        echo "❌ Redis 服務不可用，但繼續啟動服務"
        break
    fi
    sleep 1
done

if [ $timeout -gt 0 ]; then
    echo "✅ Redis 服務已就緒"
fi

# 選擇配置文件
if [ "${NODE_ENV}" = "development" ]; then
    SUPERVISOR_CONF="/workspace-manager/supervisord.dev.conf"
    echo "🔧 使用開發環境配置 (支持熱重載)"
else
    SUPERVISOR_CONF="/workspace-manager/supervisord.conf"
    echo "🏭 使用生產環境配置"
fi

# 啟動 supervisor
echo "🎯 啟動 Supervisor 管理服務..."
echo "   - FastAPI"
echo "   - Celery Worker"
echo "   - Celery Flower"
echo ""
exec /usr/bin/supervisord -c $SUPERVISOR_CONF
