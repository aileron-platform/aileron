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
from .template_service import TemplateService
from .template_install_service import TemplateInstallService
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
from .knowledge_base_maintenance_service import KnowledgeBaseMaintenanceService
from .workspace_service import WorkspaceService
from .workspace_setup_service import WorkspaceSetupService
from .workspace_lifecycle_service import WorkspaceLifecycleService


def get_user_service(db: Session = Depends(get_db)) -> UserService:
    """取得使用者服務"""
    return UserService(db)


@lru_cache()
def get_team_service() -> TeamService:
    """取得團隊服務單例"""
    return TeamService()


def get_settings_service(db: Session = Depends(get_db)) -> SettingsService:
    """取得使用者設定服務"""
    return SettingsService(db)


def get_workspace_service(db: Session = Depends(get_db)) -> WorkspaceService:
    """取得工作區服務"""
    return WorkspaceService(db)


def get_knowledge_base_service(db: Session = Depends(get_db)) -> KnowledgeBaseService:
    """取得 knowledge base 服務"""
    return KnowledgeBaseService(db)


def get_knowledge_base_sharing_service(
    db: Session = Depends(get_db),
) -> KnowledgeBaseSharingService:
    """取得 knowledge base 分享服務"""
    return KnowledgeBaseSharingService(db)


def get_knowledge_base_attachment_service(
    db: Session = Depends(get_db),
) -> KnowledgeBaseAttachmentService:
    """取得 knowledge base attachment 服務"""
    return KnowledgeBaseAttachmentService(db)


def get_knowledge_base_file_service(
    db: Session = Depends(get_db),
) -> KnowledgeBaseFileService:
    """取得 knowledge base file 服務"""
    return KnowledgeBaseFileService(db)


def get_knowledge_base_maintenance_service(
    db: Session = Depends(get_db),
) -> KnowledgeBaseMaintenanceService:
    """取得 knowledge base 維護服務"""
    return KnowledgeBaseMaintenanceService(db)


def get_workspace_setup_service(db: Session = Depends(get_db)) -> WorkspaceSetupService:
    """取得 workspace 初始化服務"""
    return WorkspaceSetupService(db)


def get_runtime_provision_service(
    db: Session = Depends(get_db),
) -> RuntimeProvisionService:
    """取得 Runtime 佈建服務"""

    return RuntimeProvisionService(db)


def get_automation_service(db: Session = Depends(get_db)) -> AutomationService:
    """取得自動化服務"""
    return AutomationService(db)


def get_template_install_service(db: Session = Depends(get_db)) -> TemplateInstallService:
    """取得模板安裝服務"""
    return TemplateInstallService(db)


def get_workspace_lifecycle_service(db: Session = Depends(get_db)) -> WorkspaceLifecycleService:
    """取得 Workspace 生命週期服務"""
    return WorkspaceLifecycleService(db)


# 本機認證服務已移除，現在使用 Keycloak OAuth2/OIDC
# 認證相關功能請使用 app.modules.auth 模組

__all__ = [
    "get_automation_service",
    "get_i18n_service",
    "get_runtime_provision_service",
    "get_settings_service",
    "get_team_service",
    "get_template_service",
    "get_template_install_service",
    "get_user_service",
    "KnowledgeBaseAccessDeniedError",
    "KnowledgeBaseConflictError",
    "KnowledgeBaseNotFoundError",
    "get_knowledge_base_service",
    "get_knowledge_base_sharing_service",
    "get_knowledge_base_attachment_service",
    "get_knowledge_base_file_service",
    "get_knowledge_base_maintenance_service",
    "get_workspace_service",
    "get_workspace_setup_service",
    "get_workspace_lifecycle_service",
]
