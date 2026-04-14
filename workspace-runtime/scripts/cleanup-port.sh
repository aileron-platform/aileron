#!/bin/bash
# 端口清理腳本 - 在啟動 Next.js 服務前清理佔用的端口

PORT=${1:-3003}
MAX_RETRIES=5
RETRY_DELAY=1

echo "[Port Cleanup] 檢查端口 $PORT..."

for i in $(seq 1 $MAX_RETRIES); do
    # 查找佔用端口的進程
    PIDS=$(lsof -ti:$PORT 2>/dev/null || fuser -n tcp $PORT 2>/dev/null | awk '{print $1}')
    
    if [ -z "$PIDS" ]; then
        echo "[Port Cleanup] 端口 $PORT 可用"
        exit 0
    fi
    
    echo "[Port Cleanup] 嘗試 $i/$MAX_RETRIES: 發現進程佔用端口 $PORT: $PIDS"
    
    # 嘗試優雅地終止進程
    for PID in $PIDS; do
        if [ -n "$PID" ] && kill -0 $PID 2>/dev/null; then
            echo "[Port Cleanup] 終止進程 $PID (SIGTERM)..."
            kill -15 $PID 2>/dev/null || true
        fi
    done
    
    # 等待進程終止
    sleep $RETRY_DELAY
    
    # 檢查是否還有進程
    PIDS=$(lsof -ti:$PORT 2>/dev/null || fuser -n tcp $PORT 2>/dev/null | awk '{print $1}')
    
    if [ -z "$PIDS" ]; then
        echo "[Port Cleanup] 端口 $PORT 已清理"
        exit 0
    fi
    
    # 如果是最後一次嘗試，使用 SIGKILL
    if [ $i -eq $MAX_RETRIES ]; then
        echo "[Port Cleanup] 強制終止進程 (SIGKILL)..."
        for PID in $PIDS; do
            if [ -n "$PID" ] && kill -0 $PID 2>/dev/null; then
                kill -9 $PID 2>/dev/null || true
            fi
        done
        sleep 1
    fi
done

# 最終檢查
PIDS=$(lsof -ti:$PORT 2>/dev/null || fuser -n tcp $PORT 2>/dev/null | awk '{print $1}')
if [ -z "$PIDS" ]; then
    echo "[Port Cleanup] 端口 $PORT 清理成功"
    exit 0
else
    echo "[Port Cleanup] 警告: 無法清理端口 $PORT，仍有進程: $PIDS"
    exit 1
fi

