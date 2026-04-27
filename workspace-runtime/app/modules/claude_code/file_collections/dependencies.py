"""File Collections Dependency Injection"""

from __future__ import annotations

from app.modules.file_system.workspace_service import WorkspaceDataService


_workspace_service: WorkspaceDataService | None = None


def get_workspace_service() -> WorkspaceDataService:
    """Get workspace data service"""
    global _workspace_service
    if _workspace_service is None:
        _workspace_service = WorkspaceDataService()
    return _workspace_service


def get_workspace_id() -> str:
    """Get current workspace ID"""
    workspace_service = get_workspace_service()
    return workspace_service.get_current_workspace_id()


__all__ = ["get_workspace_id", "get_workspace_service"]

