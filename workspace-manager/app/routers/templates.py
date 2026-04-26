"""Template routes - Main entry

This file integrates all template-related sub-routes, including:
- base: Basic CRUD operations and category/feature queries
- config: MCP and Hooks configuration management
- files: Commands, Agents, Output Style, AGENTS.md, and general file management
- git: Git version control and SSH key management
- install: Template installation, import, and export
"""

from fastapi import APIRouter

from app.routers.templates import (
    base_router,
    config_router,
    files_router,
    git_router,
    install_router,
)

# Create main route
router = APIRouter(prefix="/templates", tags=["Template"])

# Integrate all sub-routes
# Basic CRUD and category/feature query routes (no additional prefix)
router.include_router(base_router)

# Config management routes (no additional prefix)
router.include_router(config_router)

# File management routes (no additional prefix)
router.include_router(files_router)

# Git and SSH keys management routes (no additional prefix)
router.include_router(git_router)

# Template installation/import/export routes (no additional prefix)
router.include_router(install_router)


__all__ = ["router"]
