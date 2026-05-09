"""
Aileron - Workspace Runtime Main Application

Provides runtime support for development environments, including Claude Code integration, file monitoring, WebSocket communication, etc.
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
from app.modules.file_system.workspace_service import WorkspaceDataService
from app.modules.canvas import router as canvas_router
from app.modules.version_control import router as version_control_router
from app.modules.version_control.dependencies import get_git_service
from app.modules.version_control.worktree_config import (
    DEFAULT_WORKTREE_SUBDIR,
    set_worktree_subdir,
)
from app.modules.version_control.worktree_gitignore import WorktreeGitignoreManager
from app.modules.cli_settings import router as cli_settings_router
from app.modules.client_browser_relay import router as client_browser_relay_router
# Services to be implemented later
# from app.services.system_monitor import SystemMonitor
# from app.services.workspace_manager import WorkspaceManager

# Load settings
settings = get_settings()

# Setup logging
setup_logging({"log_level": "INFO"})
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifecycle management"""
    logger.info("🚀 Aileron - Workspace Runtime starting...")
    workspace_data_service = WorkspaceDataService()

    try:
        # Basic initialization
        logger.info("✅ Basic service initialization complete")
        OpenSpecService().log_cli_probe()
        subdir = DEFAULT_WORKTREE_SUBDIR
        workspace_info = await workspace_data_service.get_workspace(settings.WORKSPACE_ID)
        if workspace_info is None:
            logger.warning(
                "Unable to fetch workspace information during startup; using default worktree subdir"
            )
        else:
            subdir = workspace_info.worktree_subdir or DEFAULT_WORKTREE_SUBDIR

        try:
            subdir = set_worktree_subdir(subdir)
            get_git_service().set_worktree_subdir(subdir)
            WorktreeGitignoreManager(settings.WORKSPACE_PATH).ensure(subdir)
        except Exception as exc:
            logger.warning(
                "Failed to reconcile worktree gitignore during startup; falling back to default subdir: %s",
                exc,
            )
            subdir = set_worktree_subdir(DEFAULT_WORKTREE_SUBDIR)
            get_git_service().set_worktree_subdir(subdir)

        # TODO: Will add workspace manager and system monitor later

        logger.info("✅ Workspace Runtime startup complete")
        yield

    except Exception as e:
        logger.error(f"❌ Application startup failed: {e}")
        # Do not use sys.exit, let FastAPI handle the error
        raise
    finally:
        await workspace_data_service.close()
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
            "name": "agent-sessions",
            "description": "Agent Session main resource management",
        },
        {
            "name": "agent-session-messages",
            "description": "Agent Session message query and queue management",
        },
        {
            "name": "agent-session-tasks",
            "description": "Agent Session task creation and query",
        },
        {
            "name": "agent-session-websocket",
            "description": "WebSocket real-time communication endpoint for Agent Session",
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
        {
            "name": "OpenSpec",
            "description": "Workspace built-in OpenSpec state and workflow actions",
        },
        {
            "name": "Draw.io Integration",
            "description": "Draw.io diagram viewing and editing integration",
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
            "name": "Claude Code - Scripts",
            "description": "Custom script file management",
        },
        {
            "name": "Claude Code - Skills",
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

# Agent Session routes (prioritize over core_router to avoid route conflicts)
logger.info("🟢 [MAIN] Registering agent_session_router...")
app.include_router(agent_session_router, prefix="/api/v1")
logger.info("🟢 [MAIN] Registering agent_task_router...")
app.include_router(agent_task_router, prefix="/api/v1")
logger.info("🟢 [MAIN] Registering agent_message_router...")
app.include_router(agent_message_router, prefix="/api/v1")
# Agent Session WebSocket routes
logger.info("🔴 [MAIN] Registering agent_websocket_router (WebSocket routes)...")
app.include_router(agent_websocket_router, prefix="/api/v1")
logger.info("🔴 [MAIN] agent_websocket_router registered!")

app.include_router(claude_code_router, prefix="/api/v1")
app.include_router(cli_settings_router, prefix="/api/v1")
app.include_router(internal_router, prefix="/api/v1")
app.include_router(file_system_router, prefix="/api/v1")
app.include_router(canvas_router, prefix="/api/v1")
app.include_router(version_control_router, prefix="/api/v1")
app.include_router(openspec_router, prefix="/api/v1")

# Client Browser Relay routes
logger.info("🟢 [MAIN] Registering client_browser_relay_router...")
app.include_router(client_browser_relay_router, prefix="/api/v1")

# Draw.io integration routes
from app.modules.drawio.router import router as drawio_router
app.include_router(drawio_router, prefix="/api/v1")


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
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Credentials"] = "true"

    return response


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Global exception handler"""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)

    response = JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "detail": str(exc),
            "request_id": getattr(request.state, "request_id", None),
        },
    )

    # Add CORS headers to ensure error responses also support cross-origin requests
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Credentials"] = "true"

    return response


@app.options("/{path:path}", include_in_schema=False)
async def options_handler(path: str):
    """Handle CORS preflight requests"""
    return {"status": "ok"}


@app.get("/", include_in_schema=False)
async def root():
    """Root path redirect to API docs"""
    return {
        "message": "Aileron - Workspace Runtime",
        "version": "1.0.0",
        "status": "running",
        "workspace_id": settings.WORKSPACE_ID,
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
