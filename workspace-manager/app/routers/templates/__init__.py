"""Template routes module"""

from fastapi import APIRouter

from app.routers.templates.base import router as base_router
from app.routers.templates.config import router as config_router
from app.routers.templates.files import router as files_router
from app.routers.templates.git import router as git_router
from app.routers.templates.install import router as install_router

# Create unified template router, set /templates prefix and tags
router = APIRouter(prefix="/templates", tags=["templates"])

# Include all sub-routes
router.include_router(base_router)
router.include_router(config_router)
router.include_router(files_router)
router.include_router(git_router)
router.include_router(install_router)

__all__ = [
    "router",
    "base_router",
    "config_router",
    "files_router",
    "git_router",
    "install_router",
]
