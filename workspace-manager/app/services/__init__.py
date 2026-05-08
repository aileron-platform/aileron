from __future__ import annotations

from functools import lru_cache

from fastapi import Depends
from sqlalchemy.orm import Session

from app.db.database import get_db

from .automation_service import AutomationService
from .i18n_service import get_i18n_service
from .runtime_provision_service import RuntimeProvisionService
from .settings_service import SettingsService
from .team_service import TeamService
from .user_service import UserService
from .knowledge_base_service import (
    KnowledgeBaseAccessDeniedError,
    KnowledgeBaseConflictError,
    KnowledgeBaseNotFoundError,
    KnowledgeBaseService,
    KnowledgeBaseSharingService,
)
from .knowledge_base_attachment_service import KnowledgeBaseAttachmentService
from .knowledge_base_file_service import KnowledgeBaseFileService
from .knowledge_base_git_service import KnowledgeBaseGitService
from .knowledge_base_graph_service import KnowledgeBaseGraphService
from .knowledge_base_ingest_service import KnowledgeBaseIngestService
from .knowledge_base_lint_service import KnowledgeBaseLintService
from .knowledge_base_maintenance_service import KnowledgeBaseMaintenanceService
from .knowledge_base_review_item_service import KnowledgeBaseReviewItemService
from .knowledge_base_query_service import KnowledgeBaseQueryService
from .knowledge_base_source_service import KnowledgeBaseSourceService
from .knowledge_base_wiki_browse_service import KnowledgeBaseWikiBrowseService
from .workspace_service import WorkspaceService
from .workspace_setup_service import WorkspaceSetupService
from .workspace_lifecycle_service import WorkspaceLifecycleService


def get_user_service(db: Session = Depends(get_db)) -> UserService:
    """GetUserService"""
    return UserService(db)


@lru_cache()
def get_team_service() -> TeamService:
    """Get team service singleton"""
    return TeamService()


def get_settings_service(db: Session = Depends(get_db)) -> SettingsService:
    """GetUserSettingsService"""
    return SettingsService(db)


def get_workspace_service(db: Session = Depends(get_db)) -> WorkspaceService:
    """GetWorkspaceService"""
    return WorkspaceService(db)


def get_knowledge_base_service(db: Session = Depends(get_db)) -> KnowledgeBaseService:
    """Get knowledge base Service"""
    return KnowledgeBaseService(db)


def get_knowledge_base_sharing_service(
    db: Session = Depends(get_db),
) -> KnowledgeBaseSharingService:
    """Get knowledge base sharing service"""
    return KnowledgeBaseSharingService(db)


def get_knowledge_base_attachment_service(
    db: Session = Depends(get_db),
) -> KnowledgeBaseAttachmentService:
    """Get knowledge base attachment Service"""
    return KnowledgeBaseAttachmentService(db)


def get_knowledge_base_file_service(
    db: Session = Depends(get_db),
) -> KnowledgeBaseFileService:
    """Get knowledge base file Service"""
    return KnowledgeBaseFileService(db)


def get_knowledge_base_source_service(
    db: Session = Depends(get_db),
) -> KnowledgeBaseSourceService:
    """Get knowledge base source service"""
    return KnowledgeBaseSourceService(db)


def get_knowledge_base_ingest_service(
    db: Session = Depends(get_db),
) -> KnowledgeBaseIngestService:
    """Get knowledge base ingest service"""
    return KnowledgeBaseIngestService(db)


def get_knowledge_base_git_service(
    db: Session = Depends(get_db),
) -> KnowledgeBaseGitService:
    """Get knowledge base Git service"""
    return KnowledgeBaseGitService(db)


def get_knowledge_base_graph_service(
    db: Session = Depends(get_db),
) -> KnowledgeBaseGraphService:
    """Get knowledge base graph service"""
    return KnowledgeBaseGraphService(db)


def get_knowledge_base_query_service(
    db: Session = Depends(get_db),
) -> KnowledgeBaseQueryService:
    """Get knowledge base query service"""
    return KnowledgeBaseQueryService(db)


def get_knowledge_base_lint_service(
    db: Session = Depends(get_db),
) -> KnowledgeBaseLintService:
    """Get knowledge base lint service"""
    return KnowledgeBaseLintService(db)


def get_knowledge_base_review_item_service(
    db: Session = Depends(get_db),
) -> KnowledgeBaseReviewItemService:
    """Get knowledge base review item service"""
    return KnowledgeBaseReviewItemService(db)


def get_knowledge_base_wiki_browse_service(
    db: Session = Depends(get_db),
) -> KnowledgeBaseWikiBrowseService:
    """Get knowledge base wiki browse service"""
    return KnowledgeBaseWikiBrowseService(db)


def get_knowledge_base_maintenance_service(
    db: Session = Depends(get_db),
) -> KnowledgeBaseMaintenanceService:
    """Get knowledge base maintenance service"""
    return KnowledgeBaseMaintenanceService(db)


def get_workspace_setup_service(db: Session = Depends(get_db)) -> WorkspaceSetupService:
    """Get workspace InitializeService"""
    return WorkspaceSetupService(db)


def get_runtime_provision_service(
    db: Session = Depends(get_db),
) -> RuntimeProvisionService:
    """Get runtime provisioning service"""

    return RuntimeProvisionService(db)


def get_automation_service(db: Session = Depends(get_db)) -> AutomationService:
    """Get automation service"""
    return AutomationService(db)


def get_workspace_lifecycle_service(db: Session = Depends(get_db)) -> WorkspaceLifecycleService:
    """Get Workspace LifecycleService"""
    return WorkspaceLifecycleService(db)


# Local authentication service has been removed, now using Keycloak OAuth2/OIDC
# For authentication-related features, use app.modules.auth module

__all__ = [
    "get_automation_service",
    "get_i18n_service",
    "get_runtime_provision_service",
    "get_settings_service",
    "get_team_service",
    "get_user_service",
    "KnowledgeBaseAccessDeniedError",
    "KnowledgeBaseConflictError",
    "KnowledgeBaseNotFoundError",
    "get_knowledge_base_service",
    "get_knowledge_base_sharing_service",
    "get_knowledge_base_attachment_service",
    "get_knowledge_base_file_service",
    "get_knowledge_base_git_service",
    "get_knowledge_base_graph_service",
    "get_knowledge_base_ingest_service",
    "get_knowledge_base_lint_service",
    "get_knowledge_base_review_item_service",
    "KnowledgeBaseReviewItemService",
    "get_knowledge_base_wiki_browse_service",
    "get_knowledge_base_query_service",
    "get_knowledge_base_source_service",
    "get_knowledge_base_maintenance_service",
    "get_workspace_service",
    "get_workspace_setup_service",
    "get_workspace_lifecycle_service",
]
