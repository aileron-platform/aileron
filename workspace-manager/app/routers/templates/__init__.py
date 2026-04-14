"""模板路由模块"""

from fastapi import APIRouter

from app.routers.templates.base import router as base_router
from app.routers.templates.config import router as config_router
from app.routers.templates.files import router as files_router
from app.routers.templates.git import router as git_router
from app.routers.templates.install import router as install_router

# 創建統一的模板路由器，設定 /templates 前綴和標籤
router = APIRouter(prefix="/templates", tags=["templates"])

# 包含所有子路由
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
