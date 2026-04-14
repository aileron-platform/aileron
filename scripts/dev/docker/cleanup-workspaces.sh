#!/bin/bash

# Aileron 工作空間清理腳本
# 此腳本只清理 workspace-runtime 容器，不影響主要的 docker-compose 服務

set -e  # 遇到錯誤立即退出

echo "🧹 開始清理工作空間容器..."

# 顏色定義
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 1. 顯示當前的 workspace-runtime 容器
echo -e "${BLUE}📦 當前的 workspace-runtime 容器：${NC}"
WORKSPACE_CONTAINERS=$(docker ps -a --filter "name=workspace-runtime" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}")

if [ -z "$(docker ps -a --filter "name=workspace-runtime" -q)" ]; then
    echo "ℹ️  沒有找到 workspace-runtime 容器"
    exit 0
fi

echo "$WORKSPACE_CONTAINERS"
echo ""

# 確認提示
CONTAINER_COUNT=$(docker ps -a --filter "name=workspace-runtime" -q | wc -l)
read -p "$(echo -e ${YELLOW}⚠️  找到 $CONTAINER_COUNT 個 workspace-runtime 容器。確定要清理嗎？ [y/N]: ${NC})" -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${YELLOW}❌ 操作已取消${NC}"
    exit 1
fi

# 2. 停止並刪除所有 workspace-runtime 容器
echo -e "${BLUE}🛑 停止並刪除 workspace-runtime 容器...${NC}"

WORKSPACE_CONTAINER_IDS=$(docker ps -a --filter "name=workspace-runtime" -q)

if [ ! -z "$WORKSPACE_CONTAINER_IDS" ]; then
    # 停止運行中的容器
    RUNNING_CONTAINERS=$(docker ps --filter "name=workspace-runtime" -q)
    if [ ! -z "$RUNNING_CONTAINERS" ]; then
        echo "🛑 停止運行中的容器..."
        echo "$RUNNING_CONTAINERS" | xargs -r docker stop
    fi

    # 刪除所有容器
    echo "🗑️  刪除容器..."
    echo "$WORKSPACE_CONTAINER_IDS" | xargs -r docker rm -f

    echo -e "${GREEN}✅ 已清理 $CONTAINER_COUNT 個 workspace-runtime 容器${NC}"
else
    echo "ℹ️  沒有找到需要清理的容器"
fi

# 3. 清理懸掛的 workspace-runtime volumes（可選）
echo -e "${BLUE}📦 檢查是否有相關的 volumes 需要清理...${NC}"
WORKSPACE_VOLUMES=$(docker volume ls --filter "label=workspace-runtime" -q 2>/dev/null || true)

if [ ! -z "$WORKSPACE_VOLUMES" ]; then
    echo "發現 workspace 相關的 volumes："
    docker volume ls --filter "label=workspace-runtime"
    echo ""

    read -p "$(echo -e ${YELLOW}是否要刪除這些 volumes？ [y/N]: ${NC})" -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "$WORKSPACE_VOLUMES" | xargs -r docker volume rm
        VOLUME_COUNT=$(echo "$WORKSPACE_VOLUMES" | wc -w)
        echo -e "${GREEN}✅ 已清理 $VOLUME_COUNT 個 volumes${NC}"
    else
        echo "ℹ️  跳過 volumes 清理"
    fi
else
    echo "ℹ️  沒有找到相關的 volumes"
fi

# 4. 清理未使用的網絡（排除主要的 aileron 網絡）
echo -e "${BLUE}📦 清理未使用的 Docker 網絡...${NC}"
docker network prune -f 2>/dev/null || true

echo ""
echo -e "${GREEN}🎉 工作空間清理完成！${NC}"
echo ""
echo -e "${BLUE}📋 清理摘要：${NC}"
echo "   ✅ 已清理所有 workspace-runtime 容器"
echo "   ✅ 主要服務（database, redis, workspace-manager）保持運行"
echo "   ✅ 未使用的網絡已清理"
echo ""
echo -e "${YELLOW}💡 提示：${NC}"
echo "   • 主要的 docker-compose 服務未受影響"
echo "   • 新的工作空間將自動重新創建"
echo "   • 如需重新啟動主要服務，請使用 'docker-compose restart'"
echo ""