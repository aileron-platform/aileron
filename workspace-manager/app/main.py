"""
Aileron - Workspace Manager Main Application

Manages core functionality including workspace management, container control, and team collaboration
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
from app.db.migrations import apply_pending_migrations
from app.middleware.error_handler import ErrorHandlerMiddleware
from app.middleware.i18n import I18nMiddleware
from app.middleware.request_id import RequestIDMiddleware
from app.routers import (
    automation_router,
    container_images_router,
    gemini_oauth_router,
    health_router,
    knowledge_bases_router,
    marketplace_router,
    oauth_router,
    settings_router,
    teams_router,
    templates_router,
    users_router,
    workspaces_router,
    workspace_setup_router,
)

# Keycloak OAuth2 authentication module
from app.modules.auth import (
    auth_router as keycloak_auth_router,
    JWTAuthenticationMiddleware,
)

# Setup logging
setup_logging()
logger = logging.getLogger(__name__)

# Load settings
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifecycle management"""
    logger.info("🚀 Aileron - Workspace Manager starting...")

    try:
        create_tables()
        logger.info("✅ Database initialized")

        apply_pending_migrations(engine)

        try:
            from app.db.seed import load_seed_data

            load_seed_data()
        except Exception as seed_error:
            logger.warning(f"Seed data loading failed: {seed_error}")

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
                    logger.warning(
                        "Default workspace bootstrap retry completed but still not created"
                    )
            except Exception as bootstrap_error:
                logger.warning(
                    f"Default workspace CR bootstrap failed: {bootstrap_error}"
                )

        logger.info("✅ Workspace Manager started")
        yield

    except Exception as e:
        logger.error(f"❌ Application startup failed: {e}")
        sys.exit(1)
    finally:
        logger.info("🛑 Workspace Manager shutting down...")
        try:
            engine.dispose()
        except Exception as e:
            logger.warning(f"Error disposing database engine: {e}")
        logger.info("✅ Resource cleanup complete")


app = FastAPI(
    title="Aileron - Workspace Manager",
    description="""
    ## Aileron Workspace Management Service

    Provides complete development workspace lifecycle management:

    ### 🏢 Core Features
    - **Workspace Management**: Create, configure, start, stop development environments
    - **Container Management**: Docker container lifecycle control
    - **Team Collaboration**: Multi-user workspace sharing and permission management
    - **Template Hub**: Pre-configured project template management
    - **Task Scheduling**: Automated task execution and management

    ### 🔧 Technical Features
    - High-performance API based on FastAPI
    - PostgreSQL database
    - Redis cache and task queue
    - Docker containerized deployment
    - Keycloak OAuth2/OIDC authentication (local auth removed)

    ### 🔗 Related Services
    - **Workspace Runtime**: `http://localhost:3002/docs`
    - **Frontend UI**: [http://localhost:8080](http://localhost:8080)
    - **Celery Flower**: [http://localhost:5555](http://localhost:5555) (Task monitoring)

    ### 📚 API Documentation
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
            "name": "Health Check",
            "description": "Service health check and system status monitoring",
            "externalDocs": {
                "description": "Health check best practices",
                "url": "https://microservices.io/patterns/observability/health-check-api.html",
            },
        },
        {
            "name": "oauth",
            "description": "OAuth token exchange, refresh, and account authorization flow",
            "externalDocs": {
                "description": "OAuth documentation",
                "url": "https://docs.aileron.com/oauth",
            },
        },
        {
            "name": "Users",
            "description": "User account management and personal settings",
            "externalDocs": {
                "description": "User management documentation",
                "url": "https://docs.aileron.com/users",
            },
        },
        {
            "name": "Teams",
            "description": "Team management, member invitations, and collaboration settings",
            "externalDocs": {
                "description": "Team collaboration documentation",
                "url": "https://docs.aileron.com/teams",
            },
        },
        {
            "name": "workspaces",
            "description": "Workspace lifecycle management and configuration",
            "externalDocs": {
                "description": "Workspace documentation",
                "url": "https://docs.aileron.com/workspaces",
            },
        },
        {
            "name": "templates",
            "description": "Project template management and custom templates",
            "externalDocs": {
                "description": "Template documentation",
                "url": "https://docs.aileron.com/templates",
            },
        },
        {
            "name": "automation",
            "description": "Task scheduling, automation workflows, and cron jobs",
            "externalDocs": {
                "description": "Scheduler documentation",
                "url": "https://docs.aileron.com/scheduler",
            },
        },
        {
            "name": "container-images",
            "description": "Available container images and preset image settings for workspaces",
            "externalDocs": {
                "description": "Container image documentation",
                "url": "https://docs.aileron.com/container-images",
            },
        },
        {
            "name": "Keycloak OAuth2",
            "description": "Keycloak OAuth2/OIDC authentication integration",
            "externalDocs": {
                "description": "Keycloak authentication documentation",
                "url": "https://www.keycloak.org/documentation",
            },
        },
        {
            "name": "settings",
            "description": "User settings and SSH key synchronization management",
        },
        {
            "name": "workspace-setup",
            "description": "Workspace initialization sync and Git branch detection",
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

app.add_middleware(RequestIDMiddleware)
app.add_middleware(I18nMiddleware)
app.add_middleware(ErrorHandlerMiddleware)

app.add_middleware(
    JWTAuthenticationMiddleware,
    exclude_paths=["/health", "/api/v1/health", "/docs", "/redoc", "/metrics"],
    exclude_patterns=["/oauth2/*", "/api/v1/oauth2/*"],
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=3600,
)

app.include_router(health_router)
app.include_router(oauth_router, prefix="/api/v1")
app.include_router(gemini_oauth_router, prefix="/api/v1")
app.include_router(users_router, prefix="/api/v1")
app.include_router(teams_router, prefix="/api/v1")
app.include_router(workspaces_router, prefix="/api/v1")
app.include_router(knowledge_bases_router, prefix="/api/v1")
app.include_router(marketplace_router, prefix="/api/v1")
app.include_router(workspace_setup_router, prefix="/api/v1")
app.include_router(settings_router, prefix="/api/v1")
app.include_router(templates_router, prefix="/api/v1")
app.include_router(automation_router, prefix="/api/v1")
app.include_router(container_images_router, prefix="/api/v1")

app.include_router(keycloak_auth_router, prefix="/api/v1")


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Global exception handler"""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    translate = getattr(request.state, "translate", None)
    error_message = (
        translate("main.internal_server_error")
        if translate
        else "Internal server error, please try again later"
    )
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
    """Root path redirects to API documentation"""
    translate = getattr(request.state, "translate", None)
    app_title = (
        translate("main.app_title") if translate else "Aileron - Workspace Manager"
    )
    return {
        "message": app_title,
        "version": "1.0.0",
        "docs": "/docs",
        "redoc": "/redoc",
    }


def main() -> None:
    """Main program entry point"""
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
