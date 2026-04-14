"""
Aileron - Workspace Manager 主應用程式

負責工作區管理、容器控制、團隊協作等核心功能
"""

import logging
import sys
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config.settings import get_settings
from app.core.logging import setup_logging
from app.db.database import create_tables, engine
from app.middleware.error_handler import ErrorHandlerMiddleware
from app.middleware.i18n import I18nMiddleware
from app.middleware.request_id import RequestIDMiddleware
from app.routers import (
    automation_router,
    container_images_router,
    health_router,
    oauth_router,
    settings_router,
    teams_router,
    templates_router,
    users_router,
    workspaces_router,
    workspace_setup_router,
)

# Keycloak OAuth2 認證模組
from app.modules.auth import (
    auth_router as keycloak_auth_router,
    JWTAuthenticationMiddleware,
)

# 設定日誌
setup_logging()
logger = logging.getLogger(__name__)

# 載入設定
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """應用程式生命週期管理"""
    logger.info("🚀 Aileron - Workspace Manager 啟動中...")

    try:
        # 初始化資料庫
        create_tables()
        logger.info("✅ 資料庫初始化完成")

        # 載入種子資料
        try:
            from app.db.seed import load_seed_data
            load_seed_data()
        except Exception as seed_error:
            logger.warning(f"種子資料載入失敗: {seed_error}")

        if (
            settings.RUNTIME_PROVISIONER == "kubernetes"
            and settings.BOOTSTRAP_DEFAULT_WORKSPACE_ENABLED
        ):
            try:
                from app.db.seed import ensure_bootstrap_default_workspace
                from app.services.workspace_custom_resource_service import (
                    run_apply_workspace_custom_resource_task,
                )
                if ensure_bootstrap_default_workspace():
                    run_apply_workspace_custom_resource_task(
                        settings.BOOTSTRAP_DEFAULT_WORKSPACE_ID
                    )
                else:
                    logger.warning("預設 workspace bootstrap 重試完成但仍未建立")
            except Exception as bootstrap_error:
                logger.warning(f"預設 workspace CR bootstrap 失敗: {bootstrap_error}")

        # 可以在這裡加入其他初始化邏輯
        # - Redis 連接檢查
        # - Celery 檢查
        # - Docker 連接檢查

        logger.info("✅ Workspace Manager 啟動完成")
        yield

    except Exception as e:
        logger.error(f"❌ 應用程式啟動失敗: {e}")
        sys.exit(1)
    finally:
        logger.info("🛑 Workspace Manager 關閉中...")
        # 清理資源
        try:
            engine.dispose()
        except Exception as e:
            logger.warning(f"清理資料庫引擎時發生錯誤: {e}")
        logger.info("✅ 資源清理完成")


# 創建 FastAPI 應用程式
app = FastAPI(
    title="Aileron - Workspace Manager",
    description="""
    ## Aileron 工作區管理服務

    提供完整的開發工作區生命週期管理功能：

    ### 🏢 核心功能
    - **工作區管理**: 創建、配置、啟動、停止開發環境
    - **容器管理**: Docker 容器生命週期控制
    - **團隊協作**: 多用戶工作區共享與權限管理
    - **範本中心**: 預配置的專案範本管理
    - **任務調度**: 自動化任務執行與管理

    ### 🔧 技術特性
    - 基於 FastAPI 的高效能 API
    - PostgreSQL 資料庫
    - Redis 快取與任務佇列
    - Docker 容器化部署
    - Keycloak OAuth2/OIDC 認證（已移除本機認證）

    ### 🔗 相關服務
    - **Workspace Runtime**: `http://localhost:3002/docs`
    - **Frontend UI**: [http://localhost:8080](http://localhost:8080)
    - **Celery Flower**: [http://localhost:5555](http://localhost:5555) (任務監控)

    ### 📚 API 文件
    - **Swagger UI**: `/docs`
    - **ReDoc**: `/redoc`
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
        {
            "name": "健康檢查",
            "description": "服務健康狀態檢查和系統狀態監控",
            "externalDocs": {
                "description": "健康檢查最佳實踐",
                "url": "https://microservices.io/patterns/observability/health-check-api.html",
            },
        },
        {
            "name": "oauth",
            "description": "OAuth Token 交換、刷新與帳號授權流程",
            "externalDocs": {
                "description": "OAuth 文檔",
                "url": "https://docs.aileron.com/oauth",
            },
        },
        {
            "name": "使用者",
            "description": "用戶帳戶管理和個人資料設定",
            "externalDocs": {
                "description": "用戶管理文檔",
                "url": "https://docs.aileron.com/users",
            },
        },
        {
            "name": "團隊",
            "description": "團隊管理、成員邀請和協作設定",
            "externalDocs": {
                "description": "團隊協作文檔",
                "url": "https://docs.aileron.com/teams",
            },
        },
        {
            "name": "workspaces",
            "description": "工作區生命週期管理和配置",
            "externalDocs": {
                "description": "工作區文檔",
                "url": "https://docs.aileron.com/workspaces",
            },
        },
        {
            "name": "模板",
            "description": "專案範本管理和自定義範本",
            "externalDocs": {
                "description": "範本文檔",
                "url": "https://docs.aileron.com/templates",
            },
        },
        {
            "name": "自動化",
            "description": "任務調度、自動化流程和定時作業",
            "externalDocs": {
                "description": "調度器文檔",
                "url": "https://docs.aileron.com/scheduler",
            },
        },
        {
            "name": "container-images",
            "description": "Workspace 可用的容器映像與預設映像設定",
            "externalDocs": {
                "description": "容器映像文檔",
                "url": "https://docs.aileron.com/container-images",
            },
        },
        {
            "name": "Keycloak OAuth2",
            "description": "Keycloak OAuth2/OIDC 認證整合",
            "externalDocs": {
                "description": "Keycloak 認證文檔",
                "url": "https://www.keycloak.org/documentation",
            },
        },
        {
            "name": "settings",
            "description": "使用者設定與 SSH Key 同步管理",
        },
        {
            "name": "workspace-setup",
            "description": "Workspace 初始化同步與 Git 分支檢測",
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
        "persistAuthorization": True,
    },
    lifespan=lifespan,
)

# 添加中間件
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=3600,
)

app.add_middleware(RequestIDMiddleware)
app.add_middleware(I18nMiddleware)
app.add_middleware(ErrorHandlerMiddleware)

# Keycloak JWT 認證中間件（僅在啟用時生效）
app.add_middleware(
    JWTAuthenticationMiddleware,
    exclude_paths=["/health", "/api/v1/health", "/docs", "/redoc", "/metrics"],
    exclude_patterns=["/oauth2/*", "/api/v1/oauth2/*"],
)

# 註冊路由
app.include_router(health_router)
app.include_router(oauth_router, prefix="/api/v1")
app.include_router(users_router, prefix="/api/v1")
app.include_router(teams_router, prefix="/api/v1")
app.include_router(workspaces_router, prefix="/api/v1")
app.include_router(workspace_setup_router, prefix="/api/v1")
app.include_router(settings_router, prefix="/api/v1")
app.include_router(templates_router, prefix="/api/v1")
app.include_router(automation_router, prefix="/api/v1")
app.include_router(container_images_router, prefix="/api/v1")

# Keycloak OAuth2 認證路由
app.include_router(keycloak_auth_router, prefix="/api/v1")


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """全域例外處理器"""
    logger.error(f"未處理的例外: {exc}", exc_info=True)
    translate = getattr(request.state, "translate", None)
    error_message = translate("main.internal_server_error") if translate else "伺服器內部錯誤，請稍後再試"
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal Server Error",
            "message": error_message,
            "request_id": getattr(request.state, "request_id", None),
        },
    )


@app.get("/", include_in_schema=False)
async def root(request: Request):
    """根路徑重導向到 API 文件"""
    translate = getattr(request.state, "translate", None)
    app_title = translate("main.app_title") if translate else "Aileron - Workspace Manager"
    return {
        "message": app_title,
        "version": "1.0.0",
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
