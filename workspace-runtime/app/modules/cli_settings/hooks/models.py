"""CLI Hooks module data models

Reuses base models from Claude Code Hooks (HookActionType, HookAction, HookRule),
and defines CLI-specific response models.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Dict, List

from pydantic import BaseModel, Field

from ...claude_code.hooks.models import HookAction, HookActionType, HookRule

# Re-export base models
__all__ = [
    "HookActionType",
    "HookAction",
    "HookRule",
    "CliHookScope",
    "CliHookScopeDocument",
    "CliHookScopesResponse",
    "CliHookScopeResponse",
    "CliHookScopeUpsertRequest",
    "CliHookDeleteResponse",
    "CliHookExportResponse",
    "CliHookImportMode",
    "CliHookImportRequest",
    "CliHookImportResponse",
]


class CliHookScope(str, Enum):
    """Configuration scopes supported by CLI Hooks"""

    PROJECT = "project"
    USER = "user"


class CliHookScopeDocument(BaseModel):
    """Hook configuration for single scope"""

    scope: CliHookScope = Field(..., description="Hook scope")
    hooks: Dict[str, List[HookRule]] = Field(default_factory=dict, description="Event mapping")

    model_config = {"populate_by_name": True}


class CliHookScopesResponse(BaseModel):
    """List all hooks by scope"""

    workspace_id: str = Field(..., alias="workspaceId", description="Workspace ID")
    scopes: List[CliHookScopeDocument] = Field(default_factory=list, description="Scope list")

    model_config = {"populate_by_name": True}


class CliHookScopeResponse(BaseModel):
    """Get single scope hooks"""

    workspace_id: str = Field(..., alias="workspaceId", description="Workspace ID")
    scope: CliHookScope = Field(..., description="Hook scope")
    hooks: Dict[str, List[HookRule]] = Field(default_factory=dict, description="Event mapping")

    model_config = {"populate_by_name": True}


class CliHookScopeUpsertRequest(BaseModel):
    """Update hook configuration request"""

    hooks: Dict[str, List[HookRule]] = Field(..., description="Complete hook configuration")

    model_config = {"populate_by_name": True}


class CliHookDeleteResponse(BaseModel):
    """Delete hook response"""

    workspace_id: str = Field(..., alias="workspaceId", description="Workspace ID")
    scope: CliHookScope = Field(..., description="Hook scope")
    deleted: bool = Field(True, description="Deletion status")
    deleted_at: datetime = Field(..., alias="deletedAt", description="Deletion time")

    model_config = {"populate_by_name": True}


class CliHookExportResponse(BaseModel):
    """Export hook result"""

    workspace_id: str = Field(..., alias="workspaceId", description="Workspace ID")
    exported_at: datetime = Field(..., alias="exportedAt", description="Export time")
    scopes: List[CliHookScopeDocument] = Field(default_factory=list, description="Exported scopes")

    model_config = {"populate_by_name": True}


class CliHookImportMode(str, Enum):
    MERGE = "merge"
    REPLACE = "replace"


class CliHookImportRequest(BaseModel):
    """Import hook request"""

    mode: CliHookImportMode = Field(..., description="Import mode")
    scopes: List[CliHookScopeDocument] = Field(..., description="Import data")


class CliHookImportResponse(BaseModel):
    """Import result"""

    workspace_id: str = Field(..., alias="workspaceId", description="Workspace ID")
    mode: CliHookImportMode = Field(..., description="Import mode")
    imported: int = Field(..., description="Number created")
    updated: int = Field(..., description="Number updated")
    skipped: int = Field(..., description="Number skipped")

    model_config = {"populate_by_name": True}
