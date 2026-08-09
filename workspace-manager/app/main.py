"""
Aileron - Workspace Manager Main Application

Manages core functionality including workspace management and container control.
"""

import asyncio
import logging
from contextlib import asynccontextmanager, suppress
from typing import AsyncGenerator, Dict, Optional
from uuid import uuid4

from fastapi import FastAPI, Request, status
from fastapi.exception_handlers import http_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config.settings import Settings, get_settings
from app.core.logging import setup_logging
from app.db.database import SessionLocal, create_tables, engine
from app.middleware.error_handler import ErrorHandlerMiddleware
from app.middleware.i18n import I18nMiddleware
from app.middleware.request_id import RequestIDMiddleware
from app.modules.auth.middleware import ManagerSessionAuthenticationMiddleware
from app.modules.auth.router import router as oidc_auth_router
from app.modules.auth.token_validation import JWTUtils, get_jwt_utils
from app.modules.authorization.platform_resources_router import (
    router as platform_resources_router,
)
from app.modules.automation.internal_router import router as internal_automation_router
from app.modules.automation.router import router as automation_router
from app.modules.automation.scheduler import AutomationScheduler
from app.modules.container_images.router import router as container_images_router
from app.modules.health.router import router as health_router
from app.modules.identity.admin_router import router as admin_users_router
from app.modules.identity.group_router import router as user_groups_router
from app.modules.identity.oauth_router import router as oauth_router
from app.modules.identity.router import router as users_router
from app.modules.knowledge_base.router import router as knowledge_bases_router
from app.modules.marketplace.router import router as marketplace_router
from app.modules.platform_resource_analytics.internal_router import (
    router as internal_platform_resource_analytics_router,
)
from app.modules.platform_resource_analytics.router import (
    router as platform_resource_analytics_router,
)
from app.modules.platform_resource_capacity.router import (
    router as platform_resource_capacity_router,
)
from app.modules.settings.router import router as settings_router
from app.modules.workspace.browser_turn_credentials import BrowserTurnCredentialIssuer
from app.modules.workspace.router import router as workspaces_router
from app.modules.workspace.runtime.assertions import RuntimeAssertionService
from app.modules.workspace.runtime.database import WorkspaceRuntimeDatabaseService
from app.modules.workspace.runtime.sync import RuntimeSyncService
from app.modules.workspace.setup_router import router as workspace_setup_router

# Setup logging
setup_logging()
logger = logging.getLogger(__name__)

# Load settings
settings = get_settings()


async def verify_oidc_configuration(
    config: Settings | None = None,
    jwt_utils: JWTUtils | None = None,
) -> None:
    """Validate Discovery and a usable signing key without changing liveness."""

    config = config or settings
    if config.ENV == "testing":
        return
    config.oidc_client_secret
    jwt_utils = jwt_utils or get_jwt_utils()
    jwt_utils.config = config
    await jwt_utils.fetch_discovery(force=True)
    jwks = await jwt_utils.fetch_jwks(force=True)
    usable_keys = [
        key
        for key in jwks.get("keys", [])
        if isinstance(key, dict)
        and key.get("use") in (None, "sig")
        and key.get("alg") in config.OIDC_ALLOWED_ALGORITHMS
        and isinstance(key.get("kid"), str)
        and key["kid"]
    ]
    if not usable_keys:
        raise RuntimeError("OIDC JWKS contains no allowed signing key")


async def _sync_oidc_readiness_until_ready(app: FastAPI) -> None:
    """Retry OIDC readiness while keeping the Manager process live."""

    retry_delay_seconds = 1
    while True:
        try:
            await verify_oidc_configuration()
            app.state.oidc_ready = True
            logger.info("OIDC provider is ready")
            return
        except Exception as exc:
            app.state.oidc_ready = False
            logger.warning(
                "OIDC provider is not ready; retrying in %s seconds: %s",
                retry_delay_seconds,
                exc,
            )
            await asyncio.sleep(retry_delay_seconds)
            retry_delay_seconds = min(retry_delay_seconds * 2, 30)


def _verify_runtime_database_configuration_on_startup() -> None:
    """Fail startup when Kubernetes Runtime database isolation is unusable."""

    if settings.RUNTIME_PROVISIONER != "kubernetes":
        return
    WorkspaceRuntimeDatabaseService(settings=settings, engine=engine).prepare(
        workspace_id="00000000-0000-4000-8000-000000000000",
        runtime_instance_id="00000000-0000-4000-8000-000000000001",
    )


def _verify_browser_turn_configuration_on_startup() -> None:
    """Fail startup when Browser TURN credential issuance is incomplete."""

    BrowserTurnCredentialIssuer.from_settings(settings)


def _verify_runtime_assertion_configuration_on_startup() -> None:
    """Fail startup unless the active signing key matches the published JWKS."""

    RuntimeAssertionService.from_settings(settings)


async def _sync_runtime_capabilities_on_startup() -> dict[str, int]:
    """Attempt to synchronize capability snapshots to running runtimes."""
    db = SessionLocal()
    try:
        result = await RuntimeSyncService(db).sync_running_runtime_capabilities()
        logger.info(
            "Startup capabilities sync completed - synced: %s, failed: %s",
            result["synced"],
            result["failed"],
        )
        return result
    finally:
        db.close()


async def _sync_runtime_capabilities_until_ready() -> None:
    """Retry startup capability synchronization without blocking manager readiness."""
    retry_delay_seconds = 1
    while True:
        result = await _sync_runtime_capabilities_on_startup()
        if result["failed"] == 0:
            return

        logger.warning(
            "Startup capabilities sync will retry in %s seconds",
            retry_delay_seconds,
        )
        await asyncio.sleep(retry_delay_seconds)
        retry_delay_seconds = min(retry_delay_seconds * 2, 30)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifecycle management"""
    logger.info("🚀 Aileron - Workspace Manager starting...")

    automation_scheduler = AutomationScheduler()
    capabilities_sync_task: Optional[asyncio.Task[None]] = None
    oidc_readiness_task: Optional[asyncio.Task[None]] = None
    try:
        create_tables()
        logger.info("✅ Database initialized")
        _verify_runtime_database_configuration_on_startup()
        logger.info("✅ Runtime database isolation configuration verified")
        _verify_runtime_assertion_configuration_on_startup()
        logger.info("✅ Runtime assertion signing authority verified")
        app.state.oidc_ready = settings.ENV == "testing"
        oidc_readiness_task = asyncio.create_task(
            _sync_oidc_readiness_until_ready(app),
            name="oidc-readiness-sync",
        )
        _verify_browser_turn_configuration_on_startup()
        logger.info("✅ Browser TURN credential configuration verified")

        await automation_scheduler.start()
        capabilities_sync_task = asyncio.create_task(
            _sync_runtime_capabilities_until_ready(),
            name="startup-runtime-capabilities-sync",
        )

        logger.info("✅ Workspace Manager started")
        yield

    except Exception as e:
        logger.error(f"❌ Application startup failed: {e}")
        raise
    finally:
        logger.info("🛑 Workspace Manager shutting down...")
        if capabilities_sync_task is not None:
            capabilities_sync_task.cancel()
            with suppress(asyncio.CancelledError):
                await capabilities_sync_task
        if oidc_readiness_task is not None:
            oidc_readiness_task.cancel()
            with suppress(asyncio.CancelledError):
                await oidc_readiness_task
        await automation_scheduler.stop()
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
    - **Marketplace**: Package discovery, installation, and registry management
    - **Task Scheduling**: Automated task execution and management

    ### 🔧 Technical Features
    - High-performance API based on FastAPI
    - PostgreSQL database
    - Redis cache and task queue
    - Docker containerized deployment
    - Provider-neutral OIDC authentication

    ### 🔗 Related Services
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
            "name": "workspaces",
            "description": "Workspace lifecycle management and configuration",
            "externalDocs": {
                "description": "Workspace documentation",
                "url": "https://docs.aileron.com/workspaces",
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
            "name": "OIDC OAuth2",
            "description": "Provider-neutral OIDC authentication integration",
            "externalDocs": {
                "description": "OpenID Connect documentation",
                "url": "https://openid.net/developers/how-connect-works/",
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

app.add_middleware(ErrorHandlerMiddleware)

app.add_middleware(
    ManagerSessionAuthenticationMiddleware,
    exclude_paths=[
        "/",
        "/health",
        "/health/oidc",
        "/docs",
        "/redoc",
        "/openapi.json",
        "/metrics",
        "/api/v1/oauth2/login",
        "/api/v1/oauth2/callback",
    ],
)

app.add_middleware(I18nMiddleware)
app.add_middleware(RequestIDMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=[
        "Content-Type",
        "X-CSRF-Token",
        "X-Correlation-ID",
        "X-Language",
    ],
    expose_headers=["X-Correlation-ID"],
    max_age=3600,
)

app.include_router(health_router)
app.include_router(oauth_router, prefix="/api/v1")
app.include_router(admin_users_router, prefix="/api/v1")
app.include_router(platform_resources_router, prefix="/api/v1")
app.include_router(platform_resource_analytics_router, prefix="/api/v1")
app.include_router(platform_resource_capacity_router, prefix="/api/v1")
app.include_router(user_groups_router, prefix="/api/v1")
app.include_router(users_router, prefix="/api/v1")
app.include_router(workspaces_router, prefix="/api/v1")
app.include_router(knowledge_bases_router, prefix="/api/v1")
app.include_router(marketplace_router, prefix="/api/v1")
app.include_router(workspace_setup_router, prefix="/api/v1")
app.include_router(settings_router, prefix="/api/v1")
app.include_router(automation_router, prefix="/api/v1")
app.include_router(internal_automation_router, prefix="/api/v1")
app.include_router(internal_platform_resource_analytics_router, prefix="/api/v1")
app.include_router(container_images_router, prefix="/api/v1")

app.include_router(oidc_auth_router, prefix="/api/v1")


def _admin_management_error_code(request: Request) -> Optional[str]:
    path = request.url.path
    if path == "/api/v1/admin/users" or path.startswith("/api/v1/admin/users/"):
        return "USER_ADMIN_INVALID_REQUEST"
    if path == "/api/v1/platform-resources" or path.startswith(
        "/api/v1/platform-resources/"
    ):
        return "PLATFORM_RESOURCE_INVALID_REQUEST"
    if path == "/api/v1/admin/user-groups" or path.startswith(
        "/api/v1/admin/user-groups/"
    ):
        return "KB_GROUP_ADMIN_INVALID_REQUEST"
    return None


def _request_correlation_id(request: Request) -> str:
    correlation_id = getattr(request.state, "correlation_id", None)
    if isinstance(correlation_id, str) and correlation_id:
        return correlation_id
    correlation_id = str(uuid4())
    request.state.correlation_id = correlation_id
    request.state.request_id = correlation_id
    return correlation_id


@app.exception_handler(RequestValidationError)
async def admin_management_validation_error_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    """Return a stable validation envelope only for user management APIs."""

    error_code = _admin_management_error_code(request)
    if error_code is None:
        from fastapi.exception_handlers import request_validation_exception_handler

        return await request_validation_exception_handler(request, exc)

    field_names = sorted(
        {
            str(location[-1])
            for error in exc.errors()
            if (location := error.get("loc"))
            and isinstance(location, (list, tuple))
            and len(location) > 1
        }
    )
    if error_code == "USER_ADMIN_INVALID_REQUEST":
        if "email" in field_names:
            error_code = "USER_ADMIN_INVALID_EMAIL"
        elif "role" in field_names:
            error_code = "USER_ADMIN_INVALID_ROLE"
    return JSONResponse(
        status_code=(
            status.HTTP_422_UNPROCESSABLE_ENTITY
            if error_code == "PLATFORM_RESOURCE_INVALID_REQUEST"
            else status.HTTP_400_BAD_REQUEST
        ),
        content={
            "errorCode": error_code,
            "correlationId": _request_correlation_id(request),
            "details": {"fields": field_names},
        },
    )


@app.exception_handler(StarletteHTTPException)
async def admin_management_http_error_handler(
    request: Request,
    exc: StarletteHTTPException,
) -> Response:
    """Return stable domain errors without changing unrelated API responses."""

    fallback_code = _admin_management_error_code(request)
    if fallback_code is None:
        return await http_exception_handler(request, exc)

    detail = exc.detail if isinstance(exc.detail, str) else None
    if exc.status_code == status.HTTP_403_FORBIDDEN:
        error_code = (
            "PLATFORM_AUTHORIZATION_DENIED"
            if fallback_code == "PLATFORM_RESOURCE_INVALID_REQUEST"
            else "USER_ADMIN_FORBIDDEN"
        )
    elif detail and detail.startswith("USER_"):
        error_code = detail
    elif (
        detail
        and fallback_code == "KB_GROUP_ADMIN_INVALID_REQUEST"
        and detail.startswith("KB_GROUP_ADMIN_")
    ):
        error_code = detail
    elif (
        detail
        and fallback_code == "PLATFORM_RESOURCE_INVALID_REQUEST"
        and detail.startswith("PLATFORM_RESOURCE_")
    ):
        error_code = detail
    else:
        error_code = fallback_code
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "errorCode": error_code,
            "correlationId": _request_correlation_id(request),
        },
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Global exception handler"""
    logger.error(
        "Unhandled Manager exception: type=%s path=%s request_id=%s",
        type(exc).__name__,
        request.url.path,
        getattr(request.state, "request_id", None),
    )
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
async def root(request: Request) -> Dict[str, str]:
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
