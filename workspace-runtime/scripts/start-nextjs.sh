#!/bin/bash
# Next.js 啟動腳本 - 支持優雅降級和自動重試
#
# 此腳本會檢查工作區是否包含 Next.js 專案
# 如果不包含，會進入待機模式，等待手動觸發啟動

PORT=${PORT:-3003}
WORK_DIR=${WORK_DIR:-/workspace}
STATUS_FILE="/tmp/nextjs-status.json"

echo "[Next.js] 準備啟動 Next.js 服務..."
echo "[Next.js] 工作目錄: $WORK_DIR"
echo "[Next.js] 端口: $PORT"

# 寫入初始狀態
cat > "$STATUS_FILE" <<EOF
{
  "status": "checking",
  "message": "正在檢查 Next.js 專案...",
  "timestamp": "$(date -Iseconds)"
}
EOF

# 1. 清理端口
echo "[Next.js] 步驟 1/5: 清理端口..."
/workspace-runtime/scripts/cleanup-port.sh $PORT || {
    echo "[Next.js] 警告: 端口清理失敗，但繼續嘗試啟動..."
}

# 2. 檢查工作目錄
echo "[Next.js] 步驟 2/5: 檢查工作目錄..."
if [ ! -d "$WORK_DIR" ]; then
    echo "[Next.js] 錯誤: 工作目錄不存在: $WORK_DIR"
    cat > "$STATUS_FILE" <<EOF
{
  "status": "error",
  "message": "工作目錄不存在: $WORK_DIR",
  "timestamp": "$(date -Iseconds)"
}
EOF
    exit 1
fi

cd "$WORK_DIR"

# 3. 檢查 package.json
echo "[Next.js] 步驟 3/5: 檢查 package.json..."
if [ ! -f "package.json" ]; then
    echo "[Next.js] 警告: package.json 不存在，進入待機模式"
    cat > "$STATUS_FILE" <<EOF
{
  "status": "standby",
  "message": "工作區中未找到 Next.js 專案，請點擊「同步」按鈕初始化",
  "timestamp": "$(date -Iseconds)"
}
EOF
    # 進入待機模式 - 每 30 秒檢查一次
    while true; do
        sleep 30
        if [ -f "package.json" ]; then
            echo "[Next.js] 檢測到 package.json，準備啟動..."
            break
        fi
    done
fi

# 4. 檢查是否為 Next.js 專案
echo "[Next.js] 步驟 4/5: 檢查 Next.js 依賴..."
if ! grep -q '"next"' package.json; then
    echo "[Next.js] 警告: 不是 Next.js 專案，進入待機模式"
    cat > "$STATUS_FILE" <<EOF
{
  "status": "standby",
  "message": "工作區中未找到 Next.js 專案，請確認專案類型",
  "timestamp": "$(date -Iseconds)"
}
EOF
    # 進入待機模式
    while true; do
        sleep 30
        if grep -q '"next"' package.json 2>/dev/null; then
            echo "[Next.js] 檢測到 Next.js 依賴，準備啟動..."
            break
        fi
    done
fi

# 5. 啟動 Next.js
echo "[Next.js] 步驟 5/5: 啟動 Next.js 開發服務器..."
cat > "$STATUS_FILE" <<EOF
{
  "status": "starting",
  "message": "正在啟動 Next.js 服務...",
  "timestamp": "$(date -Iseconds)"
}
EOF

# 啟動成功後更新狀態
(sleep 5 && cat > "$STATUS_FILE" <<EOF
{
  "status": "running",
  "message": "Next.js 服務運行中",
  "port": $PORT,
  "timestamp": "$(date -Iseconds)"
}
EOF
) &

exec npm run dev -- -p $PORT

