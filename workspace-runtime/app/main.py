"""
Aileron - Workspace Runtime 主應用程式

提供開發環境運行時支援，包含 Claude Code 整合、檔案監控、WebSocket 通訊等
"""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config.settings import get_settings
from app.core.logging import setup_logging
from app.middleware.auth import AuthenticationMiddleware
from app.middleware.error_handler import ErrorHandlerMiddleware
from app.middleware.i18n import I18nMiddleware
from app.middleware.request_id import RequestIDMiddleware
from app.modules.claude_code import router as claude_code_router
from app.modules.health import router as health_router
from app.modules.internal import router as internal_router
from app.modules.openspec import router as openspec_router
from app.modules.openspec.service import OpenSpecService
from app.modules.agent_session.routers import (
    agent_session_router,
    task_router as agent_task_router,
    message_router as agent_message_router,
)
from app.modules.agent_session.websocket import websocket_router as agent_websocket_router
from app.modules.file_system import router as file_system_router
from app.modules.preview import router as preview_router
from app.modules.version_control import router as version_control_router
from app.modules.cli_settings import router as cli_settings_router
from app.modules.client_browser_relay import router as client_browser_relay_router
# Services 將在後續實作
# from app.services.system_monitor import SystemMonitor
# from app.services.workspace_manager import WorkspaceManager

# 載入設定
settings = get_settings()

# 設定日誌
setup_logging({"log_level": "INFO"})
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """應用程式生命週期管理"""
    logger.info("🚀 Aileron - Workspace Runtime 啟動中...")

    try:
        # 基本初始化
        logger.info("✅ 基本服務初始化完成")
        OpenSpecService().log_cli_probe()

        # TODO: 後續將加入工作區管理器和系統監控

        logger.info("✅ Workspace Runtime 啟動完成")
        yield

    except Exception as e:
        logger.error(f"❌ 應用程式啟動失敗: {e}")
        # 不要使用 sys.exit，讓 FastAPI 處理錯誤
        raise
    finally:
        logger.info("🛑 Workspace Runtime 關閉中...")
        logger.info("✅ 資源清理完成")


# 創建 FastAPI 應用程式
app = FastAPI(
    title="Aileron - Workspace Runtime",
    description="""
    ## Aileron 工作區運行時服務

    為開發工作區提供完整的運行時支援：

    ### 🏃‍♂️ 核心功能
    - **Claude Code 整合**: 與 Claude Code 的無縫整合
    - **檔案系統監控**: 即時監控檔案變更
    - **WebSocket 通訊**: 即時雙向通訊
    - **系統監控**: CPU、記憶體、磁碟使用率監控
    - **程序管理**: 開發程序的生命週期管理

    ### 🔧 技術特性
    - 基於 FastAPI 的高效能服務
    - WebSocket 即時通訊
    - 檔案系統監控與同步
    - 系統資源監控
    - 容器化執行環境

    ### 📡 通訊協定
    - **HTTP API**: RESTful API 服務
    - **WebSocket**: 即時通訊頻道
    - **Claude Code**: 原生整合支援

    ### 🔗 相關服務
    - **Workspace Manager**: [http://localhost:3001/docs](http://localhost:3001/docs)
    - **Frontend UI**: [http://localhost:8080](http://localhost:8080)
    - **Celery Flower**: [http://localhost:5555](http://localhost:5555) (任務監控)
    """,
    version="1.0.0",
    contact={
        "name": "Aileron Team",
        "email": "dev@aileron.com",
        "url": "https://github.com/your-org/aileron",
    },
    license_info={
        "name": "MIT",
        "url": "https://opensource.org/licenses/MIT",
    },
    openapi_tags=[
        # 核心服務
        {
            "name": "健康檢查",
            "description": "服務健康狀態檢查和監控",
        },
        {
            "name": "agent-sessions",
            "description": "Agent Session 主資源管理",
        },
        {
            "name": "agent-session-messages",
            "description": "Agent Session 訊息查詢與佇列管理",
        },
        {
            "name": "agent-session-tasks",
            "description": "Agent Session 任務建立與查詢",
        },
        {
            "name": "agent-session-websocket",
            "description": "Agent Session 的 WebSocket 即時通訊端點",
        },
        {
            "name": "內部 API",
            "description": "內部管理和設定 API（僅供系統內部使用）",
        },
        # 檔案與版本控制
        {
            "name": "檔案管理",
            "description": "檔案系統操作和管理",
        },
        {
            "name": "版本控制",
            "description": "Git 版本控制操作",
        },
        {
            "name": "OpenSpec",
            "description": "Workspace 內建 OpenSpec 狀態與 workflow actions",
        },
        {
            "name": "Draw.io 整合",
            "description": "Draw.io 圖表檢視和編輯整合",
        },
        # 工作區管理
        {
            "name": "預覽服務",
            "description": "應用程式預覽和同步服務",
        },
        # Claude Code
        {
            "name": "Claude Code - 設定",
            "description": "Claude Code 全域設定管理",
        },
        {
            "name": "Claude Code - CLAUDE.md",
            "description": "CLAUDE.md 配置檔案管理",
        },
        {
            "name": "Claude Code - Hooks",
            "description": "生命週期 Hooks 管理",
        },
        {
            "name": "Claude Code - MCP 伺服器",
            "description": "Model Context Protocol 伺服器管理",
        },
        {
            "name": "Claude Code - 腳本",
            "description": "自訂腳本檔案管理",
        },
        {
            "name": "Claude Code - 技能",
            "description": "技能（Skills）檔案管理",
        },
        {
            "name": "Claude Code - 斜線命令",
            "description": "斜線命令（Slash Commands）管理",
        },
        {
            "name": "Claude Code - 子代理",
            "description": "子代理（Subagents）配置管理",
        },
        {
            "name": "Claude Code - 輸出樣式",
            "description": "輸出樣式（Output Styles）管理",
        },
        {
            "name": "Claude Code - 使用統計",
            "description": "API 使用統計和配額管理",
        },
        # Client Browser Relay
        {
            "name": "Client Browser Relay",
            "description": "用戶端瀏覽器 CDP Relay Server，控制用戶本機的 Chrome 瀏覽器",
        },
    ],
    swagger_ui_parameters={
        "deepLinking": True,
        "displayRequestDuration": True,
        "docExpansion": "list",
        "operationsSorter": "method",
        "filter": True,
        "showExtensions": True,
        "showCommonExtensions": True,
        "tryItOutEnabled": True,
    },
    lifespan=lifespan,
)

# 添加中間件（注意：最後添加的中間件最先執行，即最外層）
# CORSMiddleware 必須在最外層，確保所有回應（包含認證失敗的 401）都帶有 CORS 標頭
app.add_middleware(RequestIDMiddleware)
app.add_middleware(I18nMiddleware)
app.add_middleware(ErrorHandlerMiddleware)
app.add_middleware(AuthenticationMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.effective_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# 註冊路由
app.include_router(health_router)

# Agent Session 路由 (優先於 core_router，避免路由衝突)
logger.info("🟢 [MAIN] 註冊 agent_session_router...")
app.include_router(agent_session_router, prefix="/api/v1")
logger.info("🟢 [MAIN] 註冊 agent_task_router...")
app.include_router(agent_task_router, prefix="/api/v1")
logger.info("🟢 [MAIN] 註冊 agent_message_router...")
app.include_router(agent_message_router, prefix="/api/v1")
# Agent Session WebSocket 路由
logger.info("🔴 [MAIN] 正在註冊 agent_websocket_router (WebSocket routes)...")
app.include_router(agent_websocket_router, prefix="/api/v1")
logger.info("🔴 [MAIN] agent_websocket_router 已註冊!")

app.include_router(claude_code_router, prefix="/api/v1")
app.include_router(cli_settings_router, prefix="/api/v1")
app.include_router(internal_router, prefix="/api/v1")
app.include_router(file_system_router, prefix="/api/v1")
app.include_router(preview_router, prefix="/api/v1")
app.include_router(version_control_router, prefix="/api/v1")
app.include_router(openspec_router, prefix="/api/v1")

# Client Browser Relay 路由
logger.info("🟢 [MAIN] 註冊 client_browser_relay_router...")
app.include_router(client_browser_relay_router, prefix="/api/v1")

# Draw.io 整合路由
from app.modules.drawio.router import router as drawio_router
app.include_router(drawio_router, prefix="/api/v1")


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """HTTP 例外處理器"""
    logger.warning(f"HTTP 例外: {exc.status_code} - {exc.detail}")

    response = JSONResponse(
        status_code=exc.status_code,
        content={
            "error": "HTTP Error",
            "detail": exc.detail,
            "status_code": exc.status_code,
            "request_id": getattr(request.state, "request_id", None),
        },
    )

    # 添加 CORS 標頭
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Credentials"] = "true"

    return response


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """全域例外處理器"""
    logger.error(f"未處理的例外: {exc}", exc_info=True)

    response = JSONResponse(
        status_code=500,
        content={
            "error": "內部伺服器錯誤",
            "detail": str(exc),
            "request_id": getattr(request.state, "request_id", None),
        },
    )

    # 添加 CORS 標頭以確保錯誤響應也支援跨域請求
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Credentials"] = "true"

    return response


@app.options("/{path:path}", include_in_schema=False)
async def options_handler(path: str):
    """處理 CORS 預檢請求"""
    return {"status": "ok"}


@app.get("/", include_in_schema=False)
async def root():
    """根路徑重導向到 API 文件"""
    return {
        "message": "Aileron - Workspace Runtime",
        "version": "1.0.0",
        "status": "running",
        "workspace_id": settings.WORKSPACE_ID,
        "docs": "/docs",
        "redoc": "/redoc",
    }


def main() -> None:
    """主程式入口點"""
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level="info" if not settings.DEBUG else "debug",
        access_log=True,
    )


if __name__ == "__main__":
    main()
