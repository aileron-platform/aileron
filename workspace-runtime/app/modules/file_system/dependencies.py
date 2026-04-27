"""File module dependency injection"""

from __future__ import annotations

import asyncio
import logging
from functools import lru_cache
from pathlib import Path
from typing import Optional

from .service import FileService
from .workspace_service import WorkspaceDataService

logger = logging.getLogger(__name__)

# Global workspace data service
_workspace_service: Optional[WorkspaceDataService] = None
_file_service: Optional[FileService] = None


def get_workspace_service() -> WorkspaceDataService:
    """Get workspace data service"""
    global _workspace_service
    if _workspace_service is None:
        _workspace_service = WorkspaceDataService()
    return _workspace_service


async def get_workspace_path() -> str:
    """Get workspace path"""
    try:
        workspace_service = get_workspace_service()
        workspace_id = workspace_service.get_current_workspace_id()
        workspace_info = await workspace_service.get_workspace(workspace_id)

        if workspace_info:
            logger.info(f"Got workspace path: {workspace_info.workspace_path}")
            return workspace_info.workspace_path
        else:
            logger.warning(f"Unable to get workspace {workspace_id} info, using default path")
            return "/workspace"
    except Exception as e:
        logger.error(f"Error getting workspace path: {e}")
        return "/workspace"


async def get_file_service() -> FileService:
    """Get file module service (async version)"""
    global _file_service
    if _file_service is None:
        workspace_path = await get_workspace_path()
        _file_service = FileService(root_path=workspace_path)
        logger.info(f"Initialized file service, workspace path: {workspace_path}")
    return _file_service


def get_file_service_sync() -> FileService:
    """Get file service (sync version, for dependency injection)"""
    global _file_service
    if _file_service is None:
        # If not initialized yet, use default path first
        from app.config.settings import get_settings
        settings = get_settings()
        _file_service = FileService(root_path=settings.WORKSPACE_PATH)
        logger.info(f"Sync initialized file service, using config path: {settings.WORKSPACE_PATH}")
    return _file_service


__all__ = ["get_file_service", "get_file_service_sync", "get_workspace_service", "get_workspace_path"]
