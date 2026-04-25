#!/bin/bash
# 端口清理腳本

PORT=${1:-3003}
MAX_RETRIES=5
RETRY_DELAY=1

echo "[Port Cleanup] Checking port $PORT..."

for i in $(seq 1 $MAX_RETRIES); do
    PIDS=$(lsof -ti:$PORT 2>/dev/null || true)

    if [ -z "$PIDS" ]; then
        echo "[Port Cleanup] Port $PORT is available"
        exit 0
    fi

    echo "[Port Cleanup] Attempt $i/$MAX_RETRIES: Found processes on port $PORT: $PIDS"

    for PID in $PIDS; do
        if [ -n "$PID" ] && kill -0 $PID 2>/dev/null; then
            echo "[Port Cleanup] Killing process $PID (SIGTERM)..."
            kill -15 $PID 2>/dev/null || true
        fi
    done

    sleep $RETRY_DELAY

    PIDS=$(lsof -ti:$PORT 2>/dev/null || true)
    if [ -z "$PIDS" ]; then
        echo "[Port Cleanup] Port $PORT cleared"
        exit 0
    fi

    if [ $i -eq $MAX_RETRIES ]; then
        echo "[Port Cleanup] Force killing (SIGKILL)..."
        for PID in $PIDS; do
            if [ -n "$PID" ] && kill -0 $PID 2>/dev/null; then
                kill -9 $PID 2>/dev/null || true
            fi
        done
        sleep 1
    fi
done

PIDS=$(lsof -ti:$PORT 2>/dev/null || true)
if [ -z "$PIDS" ]; then
    echo "[Port Cleanup] Port $PORT cleanup successful"
    exit 0
else
    echo "[Port Cleanup] Warning: Could not cleanup port $PORT, remaining processes: $PIDS"
    exit 1
fi
