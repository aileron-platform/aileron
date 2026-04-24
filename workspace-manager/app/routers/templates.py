"""模板路由 - 主入口

该文件整合了所有模板相关的子路由，包括：
- base: 基础 CRUD 操作和分类/功能查询
- config: MCP、Hooks、Marketplace 配置管理
- files: Commands、Agents、Output Style、AGENTS.md、通用文件管理
- git: Git 版本控制和 SSH Keys 管理
- install: 模板安装、导入、导出
"""

from fastapi import APIRouter

from app.routers.templates import (
    base_router,
    config_router,
    files_router,
    git_router,
    install_router,
)

# 创建主路由
router = APIRouter(prefix="/templates", tags=["模板"])

# 整合所有子路由
# 基础 CRUD 和分类/功能查询路由（无额外前缀）
router.include_router(base_router)

# 配置管理路由（无额外前缀）
router.include_router(config_router)

# 文件管理路由（无额外前缀）
router.include_router(files_router)

# Git 和 SSH Keys 管理路由（无额外前缀）
router.include_router(git_router)

# 模板安装/导入/导出路由（无额外前缀）
router.include_router(install_router)


__all__ = ["router"]
