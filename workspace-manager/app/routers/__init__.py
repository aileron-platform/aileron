"""Workspace Manager router aggregator module"""

from .automation import router as automation_router
from .container_images import router as container_images_router
from .health import router as health_router
from .knowledge_bases import router as knowledge_bases_router
from .oauth import router as oauth_router
from .settings import router as settings_router
from .teams import router as teams_router
from .templates import router as templates_router
from .users import router as users_router
from .workspaces import router as workspaces_router
from .workspace_setup import router as workspace_setup_router

__all__ = [
    "automation_router",
    "container_images_router",
    "health_router",
    "knowledge_bases_router",
    "oauth_router",
    "settings_router",
    "teams_router",
    "templates_router",
    "users_router",
    "workspaces_router",
    "workspace_setup_router",
]
