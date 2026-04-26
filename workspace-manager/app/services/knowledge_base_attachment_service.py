"""Knowledge base attachment service."""

from __future__ import annotations

from typing import Optional
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import models as db_models
from app.services.knowledge_base_service import (
    KnowledgeBaseConflictError,
    KnowledgeBaseNotFoundError,
    KnowledgeBaseService,
    compute_attachment_signature,
    normalize_kb_slug,
)
from app.services.workspace_service import WorkspaceService

KB_ATTACHMENT_NOT_FOUND_MESSAGE = "Knowledge base attachment does not exist"
KB_ALREADY_ATTACHED_MESSAGE = "Knowledge base already attached to this workspace"
KB_MOUNT_ALIAS_CONFLICT_MESSAGE = "Knowledge base mount alias already exists"
WORKSPACE_NOT_FOUND_MESSAGE = "Workspace does not exist"


class KnowledgeBaseAttachmentService:
    """Handle workspace and knowledge base attachment."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.workspace_service = WorkspaceService(db)
        self.kb_service = KnowledgeBaseService(db)

    def list_attachments_for_workspace(
        self,
        *,
        user_id: str,
        workspace_id: str,
    ) -> list[db_models.WorkspaceKnowledgeBaseAttachment]:
        workspace = self._require_workspace(workspace_id, user_id=user_id, minimum_role="viewer")
        return list(workspace.knowledge_base_attachments)

    def list_attachments_for_kb(
        self,
        *,
        user_id: str,
        kb_id: str,
    ) -> list[db_models.WorkspaceKnowledgeBaseAttachment]:
        kb, _ = self.kb_service.get_kb(user_id=user_id, kb_id=kb_id, minimum_role="viewer")
        return list(kb.attachments)

    def attach(
        self,
        *,
        user_id: str,
        workspace_id: str,
        kb_id: str,
        mount_alias: Optional[str] = None,
        mode: str = "rw",
    ) -> db_models.WorkspaceKnowledgeBaseAttachment:
        workspace = self._require_workspace(workspace_id, user_id=user_id, minimum_role="editor")
        kb, kb_access = self.kb_service.get_kb(user_id=user_id, kb_id=kb_id, minimum_role="viewer")

        duplicate = self.db.scalar(
            select(db_models.WorkspaceKnowledgeBaseAttachment).where(
                db_models.WorkspaceKnowledgeBaseAttachment.workspace_id == workspace_id,
                db_models.WorkspaceKnowledgeBaseAttachment.kb_id == kb_id,
            )
        )
        if duplicate is not None:
            raise KnowledgeBaseConflictError(KB_ALREADY_ATTACHED_MESSAGE, code="KB_ALREADY_ATTACHED")

        requested_alias = normalize_kb_slug(mount_alias or kb.slug)
        resolved_alias = (
            self._resolve_unique_alias(workspace_id=workspace_id, preferred_alias=requested_alias)
            if mount_alias is None
            else self._require_unused_alias(workspace_id=workspace_id, alias=requested_alias)
        )
        resolved_mode = "ro" if kb_access.access_role == "viewer" else mode

        attachment = db_models.WorkspaceKnowledgeBaseAttachment(
            id=str(uuid4()),
            workspace_id=workspace.id,
            kb_id=kb.id,
            mount_alias=resolved_alias,
            mode=resolved_mode,
            attached_by_id=user_id,
        )
        self.db.add(attachment)
        self.db.commit()
        self.db.refresh(attachment)
        return attachment

    def detach(
        self,
        *,
        user_id: str,
        attachment_id: str,
    ) -> None:
        attachment = self.db.get(db_models.WorkspaceKnowledgeBaseAttachment, attachment_id)
        if attachment is None:
            raise KnowledgeBaseNotFoundError(KB_ATTACHMENT_NOT_FOUND_MESSAGE, code="KB_ATTACHMENT_NOT_FOUND")
        self._require_workspace(attachment.workspace_id, user_id=user_id, minimum_role="editor")
        self.db.delete(attachment)
        self.db.commit()

    def update_attachment(
        self,
        *,
        user_id: str,
        attachment_id: str,
        mount_alias: Optional[str] = None,
        mode: Optional[str] = None,
    ) -> db_models.WorkspaceKnowledgeBaseAttachment:
        attachment = self.db.get(db_models.WorkspaceKnowledgeBaseAttachment, attachment_id)
        if attachment is None:
            raise KnowledgeBaseNotFoundError(KB_ATTACHMENT_NOT_FOUND_MESSAGE, code="KB_ATTACHMENT_NOT_FOUND")

        self._require_workspace(attachment.workspace_id, user_id=user_id, minimum_role="editor")
        _, kb_access = self.kb_service.get_kb(
            user_id=user_id,
            kb_id=attachment.kb_id,
            minimum_role="viewer",
        )

        if mount_alias is not None:
            alias = normalize_kb_slug(mount_alias)
            self._require_unused_alias(
                workspace_id=attachment.workspace_id,
                alias=alias,
                exclude_attachment_id=attachment.id,
            )
            attachment.mount_alias = alias
        if mode is not None:
            attachment.mode = "ro" if kb_access.access_role == "viewer" else mode

        self.db.commit()
        self.db.refresh(attachment)
        return attachment

    def compute_desired_kb_signature(self, *, user_id: str, workspace_id: str) -> str:
        workspace = self._require_workspace(workspace_id, user_id=user_id, minimum_role="viewer")
        return compute_attachment_signature(list(workspace.knowledge_base_attachments))

    def reconcile_on_start(self, *, workspace_id: str) -> str:
        workspace = self.db.get(db_models.Workspace, workspace_id)
        if workspace is None:
            raise KnowledgeBaseNotFoundError(WORKSPACE_NOT_FOUND_MESSAGE, code="WORKSPACE_NOT_FOUND")

        raw_attachments = getattr(workspace, "knowledge_base_attachments", [])
        if not isinstance(raw_attachments, list):
            raw_attachments = []

        active_attachments: list[db_models.WorkspaceKnowledgeBaseAttachment] = []
        for attachment in raw_attachments:
            knowledge_base = getattr(attachment, "knowledge_base", None)
            if getattr(knowledge_base, "tombstoned_at", None) is not None:
                self.db.delete(attachment)
                continue
            active_attachments.append(attachment)

        self.db.flush()
        return compute_attachment_signature(active_attachments)

    def _require_workspace(
        self,
        workspace_id: str,
        *,
        user_id: str,
        minimum_role: str,
    ) -> db_models.Workspace:
        workspace = self.db.get(db_models.Workspace, workspace_id)
        if workspace is None:
            raise KnowledgeBaseNotFoundError(WORKSPACE_NOT_FOUND_MESSAGE, code="WORKSPACE_NOT_FOUND")
        self.workspace_service._require_workspace_access(
            workspace,
            current_user_id=user_id,
            minimum_role=minimum_role,
        )
        return workspace

    def _resolve_unique_alias(self, *, workspace_id: str, preferred_alias: str) -> str:
        suffix = 1
        candidate = preferred_alias
        while self._alias_exists(workspace_id=workspace_id, alias=candidate):
            suffix += 1
            candidate = f"{preferred_alias}-{suffix}"
        return candidate

    def _require_unused_alias(
        self,
        *,
        workspace_id: str,
        alias: str,
        exclude_attachment_id: Optional[str] = None,
    ) -> str:
        if self._alias_exists(
            workspace_id=workspace_id,
            alias=alias,
            exclude_attachment_id=exclude_attachment_id,
        ):
            raise KnowledgeBaseConflictError(KB_MOUNT_ALIAS_CONFLICT_MESSAGE, code="KB_MOUNT_ALIAS_CONFLICT")
        return alias

    def _alias_exists(
        self,
        *,
        workspace_id: str,
        alias: str,
        exclude_attachment_id: Optional[str] = None,
    ) -> bool:
        query = select(db_models.WorkspaceKnowledgeBaseAttachment).where(
            db_models.WorkspaceKnowledgeBaseAttachment.workspace_id == workspace_id,
            db_models.WorkspaceKnowledgeBaseAttachment.mount_alias == alias,
        )
        if exclude_attachment_id:
            query = query.where(db_models.WorkspaceKnowledgeBaseAttachment.id != exclude_attachment_id)
        return self.db.scalar(query) is not None
