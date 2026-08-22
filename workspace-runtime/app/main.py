"""
Aileron - Workspace Runtime Main Application

Provides runtime support for development environments, including Claude Code integration, file monitoring, WebSocket communication, etc.
"""

import asyncio
import logging
import os
import signal
from contextlib import asynccontextmanager, suppress
from typing import AsyncGenerator
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config.settings import get_settings
from app.core.logging import setup_logging
from app.database.models import Base
from app.database.session import (
    async_session_scope,
    dispose_async_engine,
    get_async_engine,
    get_async_session_local,
)
from app.middleware.auth import AuthenticationMiddleware
from app.middleware.error_handler import ErrorHandlerMiddleware, internal_error_content
from app.middleware.i18n import I18nMiddleware
from app.middleware.target_client_settings_lock import (
    TargetClientSettingsMutationMiddleware,
)
from app.middleware.request_id import RequestIDMiddleware
from app.modules.audio.router import router as audio_router
from app.modules.automation.control_plane_client import AutomationControlPlaneClient
from app.modules.automation.dependencies import get_automation_worktree_service
from app.modules.automation.router import router as automation_router
from app.modules.automation.runner import AutomationRunner
from app.modules.canvas.router import router as canvas_router
from app.modules.claude_code.router import router as claude_code_router
from app.modules.cli_settings.router import router as cli_settings_router
from app.modules.client_browser_relay.router import (
    router as client_browser_relay_router,
)
from app.modules.file_system.router import router as file_system_router
from app.modules.health.router import router as health_router
from app.modules.internal.router import router as internal_router
from app.modules.marketplace_operations.user_copy import (
    MarketplaceUserCopyService,
)
from app.modules.resource_telemetry.lifecycle import build_resource_telemetry_reporter
from app.modules.resource_telemetry.reporter import ResourceTelemetryReporter
from app.modules.resource_telemetry.triggers import set_resource_telemetry_scheduler
from app.modules.workspace_access.route_inventory import get_runtime_route_inventory
from app.modules.thread.router import router as thread_router
from app.modules.thread.agent_runner_factory import (
    evict_idle_agent_runners,
    get_agent_runner,
)
from app.modules.thread.reconciliation import reconcile_stale_running_threads
from app.modules.thread.websocket.router import router as thread_websocket_router
from app.modules.version_control.router import router as version_control_router
from app.modules.version_control.dependencies import get_git_service
from app.modules.version_control.worktree_config import (
    DEFAULT_WORKTREE_SUBDIR,
    set_worktree_subdir,
)
from app.modules.version_control.worktree_gitignore import WorktreeGitignoreManager

# Load settings
settings = get_settings()

# Setup logging
setup_logging({"log_level": settings.LOG_LEVEL})
logger = logging.getLogger(__name__)


async def _evict_idle_agent_runner_loop(interval_seconds: int = 60) -> None:
    while True:
        await asyncio.sleep(interval_seconds)
        try:
            evicted = await evict_idle_agent_runners()
            if evicted:
                logger.info("Evicted %s idle Codex SDK thread state(s)", evicted)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Failed to evict idle Codex SDK thread states")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifecycle management"""
    logger.info("🚀 Aileron - Workspace Runtime starting...")
    idle_runner_cleanup_task: asyncio.Task[None] | None = None
    automation_client: AutomationControlPlaneClient | None = None
    automation_runner: AutomationRunner | None = None
    resource_telemetry_reporter: ResourceTelemetryReporter | None = None

    try:
        # Basic initialization
        get_runtime_route_inventory()
        logger.info("✅ Basic service initialization complete")
        marketplace_user_copies = MarketplaceUserCopyService(settings=settings)
        marketplace_user_copies.recover_incomplete_operations()
        subdir = settings.AILERON_WORKTREE_SUBDIR

        try:
            subdir = set_worktree_subdir(subdir)
            get_git_service().set_worktree_subdir(subdir)
            WorktreeGitignoreManager(settings.AILERON_WORKSPACE_PATH).ensure(subdir)
        except Exception as exc:
            logger.warning(
                "Failed to reconcile worktree gitignore during startup; falling back to default subdir: %s",
                exc,
            )
            subdir = set_worktree_subdir(DEFAULT_WORKTREE_SUBDIR)
            get_git_service().set_worktree_subdir(subdir)

        async with get_async_engine().begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        async with async_session_scope() as session:
            reconciled = await reconcile_stale_running_threads(
                session,
                workspace_id=settings.AILERON_WORKSPACE_ID,
                runner=get_agent_runner(settings.AILERON_WORKSPACE_ID),
            )
            if reconciled:
                logger.info("Reconciled %s stale running thread(s)", reconciled)

        runner_instance_id = uuid4()
        automation_client = AutomationControlPlaneClient(
            manager_url=settings.AILERON_MANAGER_INTERNAL_URL,
            runtime_control_token=(
                settings.AILERON_RUNTIME_CONTROL_TOKEN_FILE.get_secret_value()
            ),
            runtime_instance_id=settings.AILERON_RUNTIME_INSTANCE_ID,
            workspace_id=settings.AILERON_WORKSPACE_ID,
        )

        def fatal_shutdown(reason: str) -> None:
            logger.critical("Automation Runner fatal failure: %s", reason)
            os.kill(os.getpid(), signal.SIGTERM)

        automation_runner = AutomationRunner(
            runner_instance_id=runner_instance_id,
            workspace_id=settings.AILERON_WORKSPACE_ID,
            control_plane=automation_client,
            worktree_service=get_automation_worktree_service(),
            session_factory=get_async_session_local(),
            agent_runner=get_agent_runner(settings.AILERON_WORKSPACE_ID),
            fatal_shutdown=fatal_shutdown,
            max_concurrent_executions=settings.AUTOMATION_MAX_CONCURRENT_EXECUTIONS,
            execution_timeout_seconds=settings.AUTOMATION_EXECUTION_TIMEOUT_SECONDS,
            stop_grace_seconds=settings.AUTOMATION_AGENT_STOP_GRACE_SECONDS,
        )
        app.state.automation_runner = automation_runner

        resource_telemetry_reporter = build_resource_telemetry_reporter(settings)
        app.state.resource_telemetry_reporter = resource_telemetry_reporter
        await resource_telemetry_reporter.start()
        set_resource_telemetry_scheduler(resource_telemetry_reporter)
        await automation_runner.start()

        # TODO: Will add workspace manager and system monitor later

        idle_runner_cleanup_task = asyncio.create_task(
            _evict_idle_agent_runner_loop(),
            name="codex-sdk-idle-runner-cleanup",
        )
        logger.info("✅ Workspace Runtime startup complete")
        yield

    except Exception as e:
        logger.error(f"❌ Application startup failed: {e}")
        # Do not use sys.exit, let FastAPI handle the error
        raise
    finally:
        if resource_telemetry_reporter is not None:
            try:
                await resource_telemetry_reporter.stop()
            finally:
                set_resource_telemetry_scheduler(None)
        if automation_runner is not None:
            await automation_runner.shutdown()
        if automation_client is not None:
            await automation_client.close()
        if idle_runner_cleanup_task is not None:
            idle_runner_cleanup_task.cancel()
            with suppress(asyncio.CancelledError):
                await idle_runner_cleanup_task
        await dispose_async_engine()
        logger.info("🛑 Workspace Runtime shutting down...")
        logger.info("✅ Resource cleanup complete")


# Create FastAPI application
app = FastAPI(
    title="Aileron - Workspace Runtime",
    description="""
    ## Aileron Workspace Runtime Service

    Provides complete runtime support for development workspaces:

    ### 🏃‍♂️ Core Features
    - **Claude Code Integration**: Seamless integration with Claude Code
    - **File System Monitoring**: Real-time file change monitoring
    - **WebSocket Communication**: Real-time bidirectional communication
    - **System Monitoring**: CPU, memory, disk usage monitoring
    - **Process Management**: Development process lifecycle management

    ### 🔧 Technical Features
    - High-performance service based on FastAPI
    - WebSocket real-time communication
    - File system monitoring and synchronization
    - System resource monitoring
    - Containerized execution environment

    ### 📡 Communication Protocols
    - **HTTP API**: RESTful API services
    - **WebSocket**: Real-time communication channels
    - **Claude Code**: Native integration support

    ### 🔗 Related Services
    - **Workspace Manager**: [http://localhost:3001/docs](http://localhost:3001/docs)
    - **Frontend UI**: [http://localhost:8080](http://localhost:8080)
    - **Celery Flower**: [http://localhost:5555](http://localhost:5555) (Task monitoring)
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
        # Core services
        {
            "name": "Health Check",
            "description": "Service health status check and monitoring",
        },
        {
            "name": "Internal API",
            "description": "Internal management and configuration API (for system internal use only)",
        },
        # File and version control
        {
            "name": "File Management",
            "description": "File system operations and management",
        },
        {
            "name": "Version Control",
            "description": "Git version control operations",
        },
        # Workspace management
        {
            "name": "Preview Service",
            "description": "Application preview and synchronization service",
        },
        # Claude Code
        {
            "name": "Claude Code - Settings",
            "description": "Claude Code global settings management",
        },
        {
            "name": "Claude Code - CLAUDE.md",
            "description": "CLAUDE.md configuration file management",
        },
        {
            "name": "Claude Code - Hooks",
            "description": "Lifecycle Hooks management",
        },
        {
            "name": "Claude Code - MCP Servers",
            "description": "Model Context Protocol server management",
        },
        {
            "name": "claude-code - Skills",
            "description": "Skills file management",
        },
        {
            "name": "Claude Code - Slash Commands",
            "description": "Slash commands management",
        },
        {
            "name": "Claude Code - Subagents",
            "description": "Subagents configuration management",
        },
        {
            "name": "Claude Code - Output Styles",
            "description": "Output styles management",
        },
        {
            "name": "Claude Code - Usage Statistics",
            "description": "API usage statistics and quota management",
        },
        # Client Browser Relay
        {
            "name": "Client Browser Relay",
            "description": "Client browser CDP Relay Server, controls user's local Chrome browser",
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

# Add middleware (note: last added middleware executes first, i.e., outermost layer)
# CORSMiddleware must be at the outermost layer, ensuring all responses (including auth failed 401) have CORS headers
app.add_middleware(RequestIDMiddleware)
app.add_middleware(I18nMiddleware)
app.add_middleware(ErrorHandlerMiddleware)
app.add_middleware(TargetClientSettingsMutationMiddleware)
app.add_middleware(AuthenticationMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.effective_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# Register routes
app.include_router(health_router)
app.include_router(automation_router)

app.include_router(audio_router, prefix="/api/v1")
app.include_router(thread_router, prefix="/api/v1")
app.include_router(thread_websocket_router, prefix="/api/v1")
app.include_router(claude_code_router, prefix="/api/v1")
app.include_router(cli_settings_router, prefix="/api/v1")
app.include_router(internal_router, prefix="/api/v1")
app.include_router(file_system_router, prefix="/api/v1")
app.include_router(canvas_router, prefix="/api/v1")
app.include_router(version_control_router, prefix="/api/v1")

# Client Browser Relay routes
logger.info("🟢 [MAIN] Registering client_browser_relay_router...")
app.include_router(client_browser_relay_router, prefix="/api/v1")

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """HTTP exception handler"""
    logger.warning(f"HTTP exception: {exc.status_code} - {exc.detail}")

    response = JSONResponse(
        status_code=exc.status_code,
        content={
            "error": "HTTP Error",
            "detail": exc.detail,
            "status_code": exc.status_code,
            "request_id": getattr(request.state, "request_id", None),
        },
    )

    # Add CORS headers
    response.headers["Access-Control-Allow-Origin"] = (
        settings.AILERON_PLATFORM_PUBLIC_ORIGIN
    )
    response.headers["Access-Control-Allow-Credentials"] = "true"

    return response


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Global exception handler"""
    logger.error(
        "Unhandled runtime exception: type=%s path=%s request_id=%s",
        type(exc).__name__,
        request.url.path,
        getattr(request.state, "request_id", None),
    )

    response = JSONResponse(
        status_code=500,
        content=internal_error_content(request),
    )

    # Add CORS headers to ensure error responses also support cross-origin requests
    response.headers["Access-Control-Allow-Origin"] = (
        settings.AILERON_PLATFORM_PUBLIC_ORIGIN
    )
    response.headers["Access-Control-Allow-Credentials"] = "true"

    return response


@app.get("/", include_in_schema=False)
async def root() -> dict[str, str]:
    """Root path redirect to API docs"""
    return {
        "message": "Aileron - Workspace Runtime",
        "version": "1.0.0",
        "status": "running",
        "workspace_id": settings.AILERON_WORKSPACE_ID,
        "docs": "/docs",
        "redoc": "/redoc",
    }


def main() -> None:
    """Main program entry point"""
    import uvicorn

    application = "app.main:app" if settings.DEBUG else app
    uvicorn.run(
        application,
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level="info" if not settings.DEBUG else "debug",
        access_log=True,
    )


if __name__ == "__main__":
    main()
