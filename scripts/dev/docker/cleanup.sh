#!/bin/bash

# Aileron 完整清理腳本
# 此腳本會清理所有 docker-compose 資料和 workspace-runtime 容器

set -e  # 遇到錯誤立即退出

echo "開始清理 Aileron 環境..."

# 顏色定義
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 確認提示
read -p "$(printf "${RED}警告：這將會刪除所有容器、資料庫資料、緩存資料和工作空間！確定要繼續嗎？ [y/N]: ${NC}")" -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${YELLOW}操作已取消${NC}"
    exit 1
fi

echo ""

# 1. 停止並清理所有動態建立的 workspace 容器
echo -e "${BLUE}步驟 1: 清理動態 workspace 容器...${NC}"

# 收集所有動態建立的 workspace 容器（runtime / browser / nextjs + uuid）
WORKSPACE_CONTAINERS=$(docker ps -a --format "{{.ID}} {{.Names}}" | \
    grep -E "workspace-runtime-|workspace-browser-|workspace-nextjs-" | \
    awk '{print $1}')

if [ ! -z "$WORKSPACE_CONTAINERS" ]; then
    echo "停止動態 workspace 容器..."
    echo "$WORKSPACE_CONTAINERS" | xargs -r docker stop 2>/dev/null || true

    echo "刪除動態 workspace 容器..."
    echo "$WORKSPACE_CONTAINERS" | xargs -r docker rm -f 2>/dev/null || true

    REMOVED_COUNT=$(echo "$WORKSPACE_CONTAINERS" | wc -w)
    echo -e "${GREEN}已清理 $REMOVED_COUNT 個動態 workspace 容器${NC}"
else
    echo "沒有找到動態 workspace 容器"
fi

# 2. 停止 docker-compose 服務
echo -e "${BLUE}步驟 2: 停止 docker-compose 服務...${NC}"
if [ -f "docker-compose.yml" ]; then
    docker compose down --remove-orphans 2>/dev/null || docker-compose down --remove-orphans 2>/dev/null || true
    echo -e "${GREEN}docker-compose 服務已停止${NC}"
else
    echo "未找到 docker-compose.yml 文件"
fi

# 3. 清理 docker-compose volumes
echo -e "${BLUE}步驟 3: 清理 volumes...${NC}"
VOLUMES=$(docker volume ls --filter "name=aileron" --format "{{.Name}}")
if [ ! -z "$VOLUMES" ]; then
    echo "刪除 volumes..."
    echo "$VOLUMES" | xargs -r docker volume rm 2>/dev/null || true
    VOLUME_COUNT=$(echo "$VOLUMES" | wc -w)
    echo -e "${GREEN}已清理 $VOLUME_COUNT 個 volumes${NC}"
else
    echo "沒有找到相關的 volumes"
fi

# 4. 清理 docker networks
echo -e "${BLUE}步驟 4: 清理 networks...${NC}"
NETWORKS=$(docker network ls --filter "name=aileron" --format "{{.ID}}")
if [ ! -z "$NETWORKS" ]; then
    echo "刪除 networks..."
    echo "$NETWORKS" | xargs -r docker network rm 2>/dev/null || true
    NETWORK_COUNT=$(echo "$NETWORKS" | wc -w)
    echo -e "${GREEN}已清理 $NETWORK_COUNT 個 networks${NC}"
else
    echo "沒有找到相關的 networks"
fi

# 5. 清理專案 Docker images
echo -e "${BLUE}步驟 5: 清理 Docker images...${NC}"
PROJECT_IMAGES=(
    "ailerondocker/workspace-manager:dev"
    "ailerondocker/workspace-runtime:dev"
    "ailerondocker/workspace-chrome:dev"
    "ailerondocker/workspace-nextjs:dev"
    "ailerondocker/workspace-ui:dev"
)
IMAGES=""
for img in "${PROJECT_IMAGES[@]}"; do
    ID=$(docker images --format "{{.ID}}" "$img" 2>/dev/null)
    [ ! -z "$ID" ] && IMAGES="$IMAGES $ID"
done
IMAGES=$(echo "$IMAGES" | xargs)  # trim whitespace

if [ ! -z "$IMAGES" ]; then
    read -p "$(printf "${YELLOW}是否要刪除專案 Docker images？這需要重新構建 [y/N]: ${NC}")" -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "刪除 Docker images..."
        echo "$IMAGES" | xargs -r docker rmi -f 2>/dev/null || true
        IMAGE_COUNT=$(echo "$IMAGES" | wc -w)
        echo -e "${GREEN}已清理 $IMAGE_COUNT 個 Docker images${NC}"
    else
        echo "跳過 Docker images 清理"
    fi
else
    echo "沒有找到相關的 Docker images"
fi

# 6. 清理 data 目錄中的容器產生檔案
echo -e "${BLUE}步驟 6: 清理 data 目錄容器產生檔案...${NC}"

if [ -d "data" ]; then
    # 定義需要清理的 data 子目錄
    DATA_DIRS=(
        "data/postgres"
        "data/redis"
        "data/keycloak"
        "data/workspace-data"
        "data/workspace-scripts"
        "data/claude-data"
        "data/template-center"
        "data/ssh-keys"
    )

    CLEANED_COUNT=0

    for dir in "${DATA_DIRS[@]}"; do
        if [ -d "$dir" ]; then
            echo "清理目錄: $dir"
            # 保留 .gitkeep 和 README.md 檔案，但清理其他內容
            find "$dir" -type f ! -name ".gitkeep" ! -name "README.md" -delete 2>/dev/null || true
            # 清理空目錄
            find "$dir" -type d -empty -delete 2>/dev/null || true
            ((CLEANED_COUNT++))
        fi
    done

    echo -e "${GREEN}已清理 $CLEANED_COUNT 個 data 目錄${NC}"
else
    echo "沒有找到 data 目錄"
fi

# 7. 清理可能的臨時文件和目錄
echo -e "${BLUE}步驟 7: 清理臨時文件...${NC}"

# 清理可能的臨時工作空間目錄
TEMP_DIRS=()
[ -d "/tmp/workspaces" ] && TEMP_DIRS+=("/tmp/workspaces")
[ -d "/tmp/claude-data" ] && TEMP_DIRS+=("/tmp/claude-data")
[ -d "./workspace-runtime/tmp" ] && TEMP_DIRS+=("./workspace-runtime/tmp")

if [ ${#TEMP_DIRS[@]} -ne 0 ]; then
    for dir in "${TEMP_DIRS[@]}"; do
        if [ -d "$dir" ]; then
            echo "清理臨時目錄: $dir"
            rm -rf "$dir" 2>/dev/null || {
                echo -e "${YELLOW}無法刪除 $dir (可能需要 sudo 權限)${NC}"
            }
        fi
    done
    echo -e "${GREEN}臨時文件清理完成${NC}"
else
    echo "沒有找到需要清理的臨時文件"
fi

# 8. Docker 系統清理（可選）
echo -e "${BLUE}步驟 8: Docker 系統清理...${NC}"
read -p "$(printf "${YELLOW}是否要執行 Docker 系統清理 (清理未使用的容器、網絡、images 等)？ [y/N]: ${NC}")" -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "執行 Docker 系統清理..."
    docker system prune -f --volumes 2>/dev/null || true
    echo -e "${GREEN}Docker 系統清理完成${NC}"
else
    echo "跳過 Docker 系統清理"
fi

echo ""
echo -e "${GREEN}清理完成${NC}"
echo ""
echo -e "${BLUE}清理摘要：${NC}"
echo "   - 所有動態 workspace 容器已清理"
echo "   - docker-compose 服務已停止"
echo "   - 資料庫和緩存資料已清除"
echo "   - Docker volumes 和 networks 已清理"
echo "   - data 目錄容器產生檔案已清理"
echo "   - 臨時文件已清理"
echo ""
echo -e "${YELLOW}提示：${NC}"
echo "   - 下次啟動時，資料庫將重新初始化"
echo "   - 所有用戶資料和工作空間資料已完全清除"
echo "   - 使用 'docker-compose up -d' 重新啟動服務"
echo ""
