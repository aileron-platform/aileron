# workspace-canvas: 獨立的 Web Canvas 預覽容器
# 預裝常用套件以減少 Next.js renderer 的 npm install 時間

FROM node:20-slim AS base

ENV npm_config_cache=/home/developer/.npm

# 安裝系統依賴
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    lsof \
    procps \
    rsync \
    && rm -rf /var/lib/apt/lists/*

# 建立 developer 使用者（與 workspace-runtime 一致，UID/GID 1000）
# node:20-slim 已有 node:node (1000:1000)，重新命名並配置 home
RUN usermod -l developer -d /home/developer -m node && \
    groupmod -n developer node && \
    mkdir -p /home/developer && \
    chown -R developer:developer /home/developer

# 建立目錄結構
# /workspace: 共享 volume（原始碼來源，唯讀參考）
# /web-canvas: 容器內部工作目錄（rsync 原始碼 + 獨立 node_modules/.next）
RUN mkdir -p /workspace /web-canvas /default-canvas /canvas-management /opt/canvas-nextjs-template /scripts /var/log/canvas && \
    chown -R developer:developer /workspace /web-canvas /default-canvas /canvas-management /opt/canvas-nextjs-template /scripts /var/log/canvas

# 預裝常用 Next.js 套件到全域 npm cache（加速後續 npm install）
# 所有 npm 操作統一使用 HOME=/home/developer，確保 cache 在 developer 可存取的路徑
RUN HOME=/home/developer npm install -g npm@latest && \
    chown -R developer:developer /home/developer

# 複製並安裝標準 Next.js Canvas template 依賴
COPY --chown=developer:developer nextjs-template/ /opt/canvas-nextjs-template/
WORKDIR /opt/canvas-nextjs-template
RUN HOME=/home/developer npm ci && \
    chown -R developer:developer /opt/canvas-nextjs-template /home/developer

# 複製預設空白應用
COPY --chown=developer:developer default-canvas/ /default-canvas/

# 預先安裝預設應用的依賴（包含常用 Next.js 套件）
WORKDIR /default-canvas
RUN HOME=/home/developer npm install && \
    HOME=/home/developer npx next build 2>/dev/null || true && \
    chown -R developer:developer /default-canvas

# 複製管理 API 伺服器
COPY --chown=developer:developer management-server/ /canvas-management/
WORKDIR /canvas-management
RUN HOME=/home/developer npm install && \
    chown -R developer:developer /canvas-management

# 複製腳本
COPY --chown=developer:developer scripts/ /scripts/
RUN chmod +x /scripts/*.sh

WORKDIR /workspace

# 暴露端口
# 3003: Canvas render server
# 3013: 管理 API
EXPOSE 3003 3013

# 健康檢查
HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:3013/health || exit 1

# 以 root 啟動（腳本會切換到 developer 執行 renderer）
CMD ["/scripts/entrypoint.sh"]
