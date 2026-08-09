"""FastAPI dependencies owned by the Knowledge Base module."""

from fastapi import Depends
from sqlalchemy.orm import Session

from app.db.database import get_db

from .archive import KnowledgeBaseArchiveService
from .attachments import KnowledgeBaseAttachmentService
from .files import KnowledgeBaseFileService
from .git import KnowledgeBaseGitService
from .mount_reconcile import KnowledgeBaseMountReconcileService
from .query import KnowledgeBaseQueryService
from .access import KnowledgeBaseService, KnowledgeBaseSharingService
from .sources import KnowledgeBaseSourceService


def get_knowledge_base_service(
    db: Session = Depends(get_db),
) -> KnowledgeBaseService:
    return KnowledgeBaseService(db)


def get_knowledge_base_sharing_service(
    db: Session = Depends(get_db),
) -> KnowledgeBaseSharingService:
    return KnowledgeBaseSharingService(db)


def get_knowledge_base_attachment_service(
    db: Session = Depends(get_db),
) -> KnowledgeBaseAttachmentService:
    return KnowledgeBaseAttachmentService(db)


def get_knowledge_base_mount_reconcile_service(
    db: Session = Depends(get_db),
) -> KnowledgeBaseMountReconcileService:
    return KnowledgeBaseMountReconcileService(db)


def get_knowledge_base_file_service(
    db: Session = Depends(get_db),
) -> KnowledgeBaseFileService:
    return KnowledgeBaseFileService(db)


def get_knowledge_base_archive_service(
    db: Session = Depends(get_db),
) -> KnowledgeBaseArchiveService:
    return KnowledgeBaseArchiveService(db)


def get_knowledge_base_source_service(
    db: Session = Depends(get_db),
) -> KnowledgeBaseSourceService:
    return KnowledgeBaseSourceService(db)


def get_knowledge_base_git_service(
    db: Session = Depends(get_db),
) -> KnowledgeBaseGitService:
    return KnowledgeBaseGitService(db)


def get_knowledge_base_query_service(
    db: Session = Depends(get_db),
) -> KnowledgeBaseQueryService:
    return KnowledgeBaseQueryService(db)
