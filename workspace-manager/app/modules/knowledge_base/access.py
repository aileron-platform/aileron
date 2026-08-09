"""Knowledge base core service."""

from __future__ import annotations

import logging
import re
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

import app.modules.knowledge_base.errors as kb_errors
from app.config.settings import get_settings
from app.db import models as db_models
from app.modules.audit.events import AuditEventService
from app.modules.authorization.actor import AuthorizationActor
from app.modules.authorization.operation_policy import (
    AuthorizationOperationError,
    AuthorizationOperationPolicy,
    OperationId,
)
from app.modules.authorization.resource_access import (
    RESOURCE_SHARE_ROLES,
    ResourceAccessRole,
    ResourceAccessSource,
    normalize_resource_role,
)
from app.modules.knowledge_base.access_repository import KnowledgeBaseAccessResolver
from app.modules.platform_resource_analytics.analytics import PlatformResourceActivityLedger

logger = logging.getLogger(__name__)

_SLUG_SANITIZER = re.compile(r"[^a-z0-9]+")
KB_OWNER_NOT_FOUND_MESSAGE = "Knowledge base owner does not exist"
KB_SLUG_REQUIRED_MESSAGE = "Knowledge base slug cannot be empty"
KB_NOT_FOUND_MESSAGE = "Knowledge base does not exist"
KB_ACCESS_DENIED_MESSAGE = "No knowledge base access permission"
KB_PERMISSION_DENIED_MESSAGE = "Insufficient knowledge base permissions"
KB_DELETE_ATTACHMENT_CONFLICT_MESSAGE = "Knowledge base is still mounted by workspace"
RESOURCE_DELETE_CONFIRMATION_MISMATCH_MESSAGE = (
    "Knowledge base name confirmation does not match"
)
KB_SLUG_CONFLICT_MESSAGE = "Knowledge base slug already exists"
KB_SHARE_OWNER_FORBIDDEN_MESSAGE = "Cannot share knowledge base with owner"
KB_SHARE_INVALID_TARGET_TYPE_MESSAGE = "Invalid knowledge base share target type"
KB_SHARE_TARGET_NOT_FOUND_MESSAGE = "Knowledge base share target does not exist"
KB_SHARE_INVALID_ROLE_MESSAGE = "Invalid knowledge base sharing role"
KB_SHARE_CONFLICT_MESSAGE = "Knowledge base share already exists"
KB_INVALID_QUOTA_MESSAGE = "Knowledge base quota is invalid"
KB_QUOTA_BELOW_USAGE_MESSAGE = "Knowledge base quota cannot be lower than current usage"


class KnowledgeBaseAccessDeniedError(PermissionError):
    """Insufficient knowledge base permissions."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "KB_ACCESS_DENIED",
        params: dict | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.params = params or {}


class KnowledgeBaseNotFoundError(LookupError):
    """Knowledge base does not exist."""

    def __init__(
        self, message: str, *, code: str = "KB_NOT_FOUND", params: dict | None = None
    ) -> None:
        super().__init__(message)
        self.code = code
        self.params = params or {}


class KnowledgeBaseConflictError(kb_errors.KnowledgeBaseError):
    """Knowledge base resource conflict."""

    def __init__(
        self, message: str, *, code: str = "KB_CONFLICT", params: dict | None = None
    ) -> None:
        super().__init__(message, code=code, params=params)


@dataclass(frozen=True)
class KnowledgeBaseAccessContext:
    access_role: ResourceAccessRole
    access_source: ResourceAccessSource | None = None
    access_sources: tuple[ResourceAccessSource, ...] = ()


def normalize_kb_slug(value: str) -> str:
    """Normalize KB slug to lowercase dash format."""
    normalized = _SLUG_SANITIZER.sub("-", value.strip().lower()).strip("-")
    if not normalized:
        raise kb_errors.KnowledgeBaseError(
            KB_SLUG_REQUIRED_MESSAGE, code="KB_INVALID_SLUG"
        )
    return normalized


class KnowledgeBaseService:
    """Manage knowledge base and basic authorization determination."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self._access_resolver = KnowledgeBaseAccessResolver(db)
        self.operation_authorization = AuthorizationOperationPolicy(db)
        self.audit_events = AuditEventService(db)
        self.storage_root = Path(get_settings().MANAGER_KNOWLEDGE_BASES_DIR)

    def create_kb(
        self,
        *,
        actor: AuthorizationActor,
        name: str,
        slug: str,
        description: Optional[str] = None,
    ) -> db_models.KnowledgeBase:
        self.operation_authorization.require_platform_operation(
            actor,
            OperationId.KNOWLEDGE_BASE_CREATE,
        )
        owner_id = actor.user_id
        owner_exists = self.db.scalar(
            select(func.count())
            .select_from(db_models.User)
            .where(db_models.User.id == owner_id)
        )
        if not owner_exists:
            raise kb_errors.KnowledgeBaseError(
                KB_OWNER_NOT_FOUND_MESSAGE, code="KB_OWNER_NOT_FOUND"
            )

        normalized_slug = normalize_kb_slug(slug)
        self._ensure_unique_slug(owner_id=owner_id, slug=normalized_slug)

        knowledge_base = db_models.KnowledgeBase(
            id=str(uuid4()),
            owner_id=owner_id,
            slug=normalized_slug,
            name=name.strip(),
            description=description,
            current_size_bytes=0,
            quota_bytes=None,
            version_control_enabled=False,
        )
        self.db.add(knowledge_base)
        PlatformResourceActivityLedger(self.db).record_manager_activity(
            event_id=f"manager:{uuid4()}",
            resource_type="knowledge_base",
            resource_id=knowledge_base.id,
            event_type="created",
        )
        self.db.commit()
        self.db.refresh(knowledge_base)
        return knowledge_base

    def rename_kb(
        self,
        *,
        actor: AuthorizationActor,
        kb_id: str,
        name: str,
    ) -> db_models.KnowledgeBase:
        kb, _ = self.get_kb_for_operation(
            actor=actor,
            kb_id=kb_id,
            operation=OperationId.KNOWLEDGE_BASE_SETTINGS_MANAGE,
        )
        kb.name = name.strip()
        kb.updated_at = datetime.utcnow()
        PlatformResourceActivityLedger(self.db).record_manager_activity(
            event_id=f"manager:{uuid4()}",
            resource_type="knowledge_base",
            resource_id=kb.id,
            event_type="metadata_edited",
        )
        self.db.commit()
        self.db.refresh(kb)
        return kb

    def update_description(
        self,
        *,
        actor: AuthorizationActor,
        kb_id: str,
        description: Optional[str],
    ) -> db_models.KnowledgeBase:
        kb, _ = self.get_kb_for_operation(
            actor=actor,
            kb_id=kb_id,
            operation=OperationId.KNOWLEDGE_BASE_SETTINGS_MANAGE,
        )
        kb.description = description
        kb.updated_at = datetime.utcnow()
        PlatformResourceActivityLedger(self.db).record_manager_activity(
            event_id=f"manager:{uuid4()}",
            resource_type="knowledge_base",
            resource_id=kb.id,
            event_type="metadata_edited",
        )
        self.db.commit()
        self.db.refresh(kb)
        return kb

    def update_visibility(
        self,
        *,
        actor: AuthorizationActor,
        kb_id: str,
        visibility: str,
        correlation_id: str | None = None,
    ) -> db_models.KnowledgeBase:
        if visibility not in {"private", "public"}:
            raise kb_errors.KnowledgeBaseError(
                "Invalid knowledge base visibility",
                code="KB_INVALID_VISIBILITY",
            )
        kb, _ = self.get_kb_for_operation(
            actor=actor,
            kb_id=kb_id,
            operation=OperationId.KNOWLEDGE_BASE_VISIBILITY_MANAGE,
        )
        if kb.visibility == visibility:
            return kb
        correlation_id = correlation_id or str(uuid4())
        previous_visibility = kb.visibility
        if previous_visibility == "public" and visibility == "private":
            from app.modules.knowledge_base.attachments import (
                KnowledgeBaseAttachmentService,
            )

            KnowledgeBaseAttachmentService(self.db).revoke_knowledge_base_mounts(
                actor_user_id=actor.user_id,
                kb=kb,
                correlation_id=correlation_id,
            )
        kb.visibility = visibility
        kb.updated_at = datetime.utcnow()
        AuditEventService(self.db).record(
            event_type="knowledge_base.visibility_updated",
            actor_type="user",
            actor_id=actor.user_id,
            actor_user_id=actor.user_id,
            target_type="knowledge_base",
            target_id=kb.id,
            action="update_visibility",
            result="success",
            error_code=None,
            correlation_id=correlation_id,
            root_correlation_id=correlation_id,
            metadata={
                "before": previous_visibility,
                "after": visibility,
            },
        )
        self.db.commit()
        self.db.refresh(kb)
        return kb

    def delete_kb(
        self,
        *,
        actor: AuthorizationActor,
        kb_id: str,
        confirmation_name: str,
        correlation_id: str | None = None,
        root_correlation_id: str | None = None,
    ) -> db_models.KnowledgeBase:
        correlation_id = correlation_id or str(uuid4())
        root_correlation_id = root_correlation_id or correlation_id
        storage_path: Path | None = None
        staged_path: Path | None = None
        committed = False
        try:
            self.operation_authorization.require_knowledge_base_operation(
                actor,
                kb_id,
                OperationId.KNOWLEDGE_BASE_DELETE,
            )
            kb = self.db.scalar(
                select(db_models.KnowledgeBase)
                .where(db_models.KnowledgeBase.id == kb_id)
                .with_for_update()
            )
            if kb is None:
                raise KnowledgeBaseNotFoundError(
                    KB_NOT_FOUND_MESSAGE,
                    code="KB_NOT_FOUND",
                )
            if confirmation_name != kb.name:
                raise kb_errors.KnowledgeBaseError(
                    RESOURCE_DELETE_CONFIRMATION_MISMATCH_MESSAGE,
                    code="RESOURCE_DELETE_CONFIRMATION_MISMATCH",
                )

            attachments = list(
                self.db.scalars(
                    select(db_models.WorkspaceKnowledgeBaseAttachment)
                    .where(db_models.WorkspaceKnowledgeBaseAttachment.kb_id == kb.id)
                    .order_by(db_models.WorkspaceKnowledgeBaseAttachment.id)
                    .with_for_update()
                ).all()
            )
            candidate_workspaces = list(
                self.db.scalars(
                    select(db_models.Workspace)
                    .where(
                        (
                            db_models.Workspace.knowledge_base_mount_candidate_snapshot.is_not(
                                None
                            )
                        )
                        | (
                            db_models.Workspace.knowledge_base_mount_failed_snapshot.is_not(
                                None
                            )
                        )
                    )
                    .order_by(db_models.Workspace.id)
                    .with_for_update()
                ).all()
            )
            workspace_ids = {attachment.workspace_id for attachment in attachments} | {
                workspace.id for workspace in candidate_workspaces
            }
            locked_workspaces = (
                list(
                    self.db.scalars(
                        select(db_models.Workspace)
                        .where(db_models.Workspace.id.in_(workspace_ids))
                        .order_by(db_models.Workspace.id)
                        .with_for_update()
                    ).all()
                )
                if workspace_ids
                else []
            )
            workspace_by_id = {
                workspace.id: workspace for workspace in locked_workspaces
            }
            references: dict[str, tuple[str, str, str]] = {
                attachment.id: (
                    attachment.workspace_id,
                    attachment.mount_alias,
                    "active",
                )
                for attachment in attachments
            }
            for workspace in candidate_workspaces:
                for snapshot, status_value in (
                    (
                        workspace.knowledge_base_mount_candidate_snapshot,
                        "pending",
                    ),
                    (
                        workspace.knowledge_base_mount_failed_snapshot,
                        "failed",
                    ),
                ):
                    entries = snapshot if isinstance(snapshot, list) else []
                    for entry in entries:
                        if (
                            not isinstance(entry, dict)
                            or entry.get("knowledgeBaseId") != kb.id
                            or not isinstance(entry.get("attachmentId"), str)
                            or not isinstance(entry.get("mountAlias"), str)
                        ):
                            continue
                        references.setdefault(
                            entry["attachmentId"],
                            (
                                workspace.id,
                                entry["mountAlias"],
                                status_value,
                            ),
                        )

            if references:
                visible_workspaces: list[dict[str, str]] = []
                hidden_workspace_count = 0
                for attachment_id, (
                    workspace_id,
                    mount_alias,
                    attachment_status,
                ) in references.items():
                    workspace = workspace_by_id.get(workspace_id)
                    if workspace is None or not self._workspace_visible_to_user(
                        workspace,
                        user_id=actor.user_id,
                    ):
                        hidden_workspace_count += 1
                        continue
                    visible_workspaces.append(
                        {
                            "attachmentId": attachment_id,
                            "workspaceId": workspace.id,
                            "workspaceName": workspace.name,
                            "mountAlias": mount_alias,
                            "attachmentStatus": attachment_status,
                        }
                    )
                raise KnowledgeBaseConflictError(
                    KB_DELETE_ATTACHMENT_CONFLICT_MESSAGE,
                    code="KB_DELETE_ATTACHMENT_CONFLICT",
                    params={
                        "attachmentCount": len(references),
                        "visibleWorkspaces": visible_workspaces,
                        "hiddenWorkspaceCount": hidden_workspace_count,
                    },
                )

            storage_path = self.storage_root / kb.id
            if storage_path.exists():
                staging_root = self.storage_root / ".delete-staging"
                staging_root.mkdir(parents=True, exist_ok=True)
                staged_path = staging_root / f"{kb.id}-{uuid4()}"
                storage_path.rename(staged_path)
            self.audit_events.record(
                event_type="knowledge_base.deleted",
                actor_type="user",
                actor_id=actor.user_id,
                actor_user_id=actor.user_id,
                target_type="knowledge_base",
                target_id=kb.id,
                action="delete_knowledge_base",
                result="success",
                error_code=None,
                correlation_id=correlation_id,
                root_correlation_id=root_correlation_id,
                metadata={"changed_fields": ["deleted"]},
            )
            self.db.delete(kb)
            self.db.commit()
            committed = True
            if staged_path is not None:
                try:
                    shutil.rmtree(staged_path)
                except OSError as exc:
                    logger.exception(
                        "knowledge_base.delete_staging_cleanup_failed kb_id=%s path=%s",
                        kb.id,
                        staged_path,
                    )
                    raise kb_errors.KnowledgeBaseError(
                        "Knowledge base storage cleanup failed",
                        code="KB_DELETE_STORAGE_CLEANUP_FAILED",
                    ) from exc
            return kb
        except Exception as exc:
            self.db.rollback()
            if (
                not committed
                and staged_path is not None
                and staged_path.exists()
                and storage_path is not None
                and not storage_path.exists()
            ):
                storage_path.parent.mkdir(parents=True, exist_ok=True)
                staged_path.rename(storage_path)
            self._persist_delete_failure_audit(
                actor_user_id=actor.user_id,
                kb_id=kb_id,
                error_code=getattr(exc, "code", "KB_DELETE_FAILED"),
                correlation_id=correlation_id,
                root_correlation_id=root_correlation_id,
            )
            raise

    def _persist_delete_failure_audit(
        self,
        *,
        actor_user_id: str,
        kb_id: str,
        error_code: str,
        correlation_id: str,
        root_correlation_id: str,
    ) -> None:
        try:
            with Session(bind=self.db.get_bind()) as audit_db:
                AuditEventService(audit_db).record(
                    event_type="knowledge_base.deleted",
                    actor_type="user",
                    actor_id=actor_user_id,
                    actor_user_id=actor_user_id,
                    target_type="knowledge_base",
                    target_id=kb_id,
                    action="delete_knowledge_base",
                    result="failure",
                    error_code=error_code,
                    correlation_id=correlation_id,
                    root_correlation_id=root_correlation_id,
                    metadata=None,
                )
                audit_db.commit()
        except Exception:
            logger.exception(
                "knowledge_base.delete_failure_audit_failed kb_id=%s",
                kb_id,
            )

    def list_accessible(
        self, *, actor: AuthorizationActor
    ) -> list[tuple[db_models.KnowledgeBase, ResourceAccessRole]]:
        self.operation_authorization.require_platform_operation(
            actor,
            OperationId.KNOWLEDGE_BASE_COLLECTION_READ,
        )
        user_id = actor.user_id
        query = select(db_models.KnowledgeBase).order_by(
            db_models.KnowledgeBase.created_at.desc()
        )
        rows = self.db.scalars(query).all()
        accessible: list[tuple[db_models.KnowledgeBase, ResourceAccessRole]] = []
        for knowledge_base in rows:
            role = self._resolve_role(knowledge_base, user_id=user_id)
            if role is not None:
                accessible.append((knowledge_base, role))
        return accessible

    def get_kb_for_operation(
        self,
        *,
        actor: AuthorizationActor,
        kb_id: str,
        operation: OperationId,
    ) -> tuple[db_models.KnowledgeBase, KnowledgeBaseAccessContext]:
        """Resolve one KB only through the fixed operation policy."""

        try:
            grant = self.operation_authorization.require_knowledge_base_operation(
                actor,
                kb_id,
                operation,
            )
        except AuthorizationOperationError as exc:
            if exc.http_status == 404:
                raise KnowledgeBaseNotFoundError(
                    KB_NOT_FOUND_MESSAGE,
                    code=exc.error_code,
                ) from exc
            raise KnowledgeBaseAccessDeniedError(
                KB_PERMISSION_DENIED_MESSAGE,
                code=exc.error_code,
            ) from exc
        kb = self.db.get(db_models.KnowledgeBase, kb_id)
        if kb is None:
            raise KnowledgeBaseNotFoundError(KB_NOT_FOUND_MESSAGE, code="KB_NOT_FOUND")
        if grant.access_role is None:
            raise KnowledgeBaseAccessDeniedError(
                KB_ACCESS_DENIED_MESSAGE,
                code="KB_ACCESS_DENIED",
            )
        return kb, KnowledgeBaseAccessContext(
            access_role=grant.access_role,
            access_source=grant.access_source,
            access_sources=grant.access_sources,
        )

    def _resolve_role(
        self, kb: db_models.KnowledgeBase, *, user_id: str
    ) -> Optional[ResourceAccessRole]:
        access = self._access_resolver.resolve(
            knowledge_base_id=kb.id,
            user_id=user_id,
        )
        return access.access_role if access is not None else None

    def _resolve_share_role(
        self,
        *,
        kb_id: str,
        user_id: str,
    ) -> Optional[ResourceAccessRole]:
        access = self._access_resolver.resolve(
            knowledge_base_id=kb_id,
            user_id=user_id,
        )
        return access.access_role if access is not None else None

    def _workspace_visible_to_user(
        self,
        workspace: db_models.Workspace,
        *,
        user_id: str,
    ) -> bool:
        if workspace.owner_id == user_id:
            return True
        share_id = self.db.scalar(
            select(db_models.WorkspaceShare.id).where(
                db_models.WorkspaceShare.workspace_id == workspace.id,
                db_models.WorkspaceShare.target_type == "user",
                db_models.WorkspaceShare.target_id == user_id,
            )
        )
        return share_id is not None

    def _ensure_unique_slug(
        self, *, owner_id: str, slug: str, exclude_kb_id: Optional[str] = None
    ) -> None:
        query = select(db_models.KnowledgeBase).where(
            db_models.KnowledgeBase.owner_id == owner_id,
            db_models.KnowledgeBase.slug == slug,
        )
        if exclude_kb_id:
            query = query.where(db_models.KnowledgeBase.id != exclude_kb_id)

        existing = self.db.scalar(query)
        if existing is not None:
            raise KnowledgeBaseConflictError(
                KB_SLUG_CONFLICT_MESSAGE, code="KB_SLUG_CONFLICT"
            )


class KnowledgeBaseSharingService:
    """Knowledge base sharing management service."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.kb_service = KnowledgeBaseService(db)
        self.audit_events = AuditEventService(db)

    def list_shares(
        self, *, actor: AuthorizationActor, kb_id: str
    ) -> list[db_models.KnowledgeBaseShare]:
        self.kb_service.get_kb_for_operation(
            actor=actor,
            kb_id=kb_id,
            operation=OperationId.KNOWLEDGE_BASE_SHARE_MANAGE,
        )
        return list(
            self.db.scalars(
                select(db_models.KnowledgeBaseShare)
                .where(db_models.KnowledgeBaseShare.kb_id == kb_id)
                .order_by(db_models.KnowledgeBaseShare.created_at.asc())
            ).all()
        )

    def resolve_share_target_labels(
        self,
        shares: list[db_models.KnowledgeBaseShare],
    ) -> dict[str, str]:
        """Resolve share labels in stable, batched local database queries."""
        user_ids = sorted(
            {share.target_id for share in shares if share.target_type == "user"}
        )
        group_ids = sorted(
            {share.target_id for share in shares if share.target_type == "user_group"}
        )

        users: dict[str, str] = {}
        if user_ids:
            user_rows = self.db.execute(
                select(
                    db_models.User.id,
                    db_models.User.display_name,
                    db_models.User.username,
                    db_models.User.email,
                ).where(db_models.User.id.in_(user_ids))
            ).all()
            users = {
                row.id: row.display_name or row.username or row.email or row.id
                for row in user_rows
            }

        groups: dict[str, str] = {}
        if group_ids:
            group_rows = self.db.execute(
                select(db_models.UserGroup.id, db_models.UserGroup.name).where(
                    db_models.UserGroup.id.in_(group_ids)
                )
            ).all()
            groups = {row.id: row.name for row in group_rows}

        return {
            share.id: (
                users.get(share.target_id, share.target_id)
                if share.target_type == "user"
                else groups.get(share.target_id, share.target_id)
            )
            for share in shares
        }

    def list_share_candidate_groups(
        self,
        *,
        actor: AuthorizationActor,
        kb_id: str,
        query: str,
        limit: int,
    ) -> list[db_models.UserGroup]:
        """List unshared user groups for a knowledge base manager."""
        self.kb_service.get_kb_for_operation(
            actor=actor,
            kb_id=kb_id,
            operation=OperationId.KNOWLEDGE_BASE_SHARE_MANAGE,
        )
        shared_group_ids = select(db_models.KnowledgeBaseShare.target_id).where(
            db_models.KnowledgeBaseShare.kb_id == kb_id,
            db_models.KnowledgeBaseShare.target_type == "user_group",
        )
        filters = [db_models.UserGroup.id.not_in(shared_group_ids)]
        normalized_query = query.strip()
        if normalized_query:
            filters.append(db_models.UserGroup.name.ilike(f"%{normalized_query}%"))
        return list(
            self.db.scalars(
                select(db_models.UserGroup)
                .where(*filters)
                .order_by(db_models.UserGroup.name.asc(), db_models.UserGroup.id.asc())
                .limit(limit)
            ).all()
        )

    def grant_share(
        self,
        *,
        actor: AuthorizationActor,
        kb_id: str,
        target_type: str,
        target_id: str,
        role: str,
        correlation_id: str | None = None,
        root_correlation_id: str | None = None,
    ) -> db_models.KnowledgeBaseShare:
        correlation_id = correlation_id or str(uuid4())
        root_correlation_id = root_correlation_id or correlation_id
        audit_target_type = (
            target_type
            if target_type in {"user", "user_group"}
            else "knowledge_base_share_target"
        )
        try:
            kb, _ = self.kb_service.get_kb_for_operation(
                actor=actor,
                kb_id=kb_id,
                operation=OperationId.KNOWLEDGE_BASE_SHARE_MANAGE,
            )
            if target_type not in {"user", "user_group"}:
                raise kb_errors.KnowledgeBaseError(
                    KB_SHARE_INVALID_TARGET_TYPE_MESSAGE,
                    code="KB_SHARE_INVALID_TARGET_TYPE",
                )
            canonical_role = normalize_resource_role(role)
            if canonical_role not in RESOURCE_SHARE_ROLES:
                raise kb_errors.KnowledgeBaseError(
                    KB_SHARE_INVALID_ROLE_MESSAGE,
                    code="KB_SHARE_INVALID_ROLE",
                )
            if target_type == "user" and target_id == kb.owner_id:
                raise KnowledgeBaseConflictError(
                    KB_SHARE_OWNER_FORBIDDEN_MESSAGE,
                    code="KB_SHARE_OWNER_TARGET_FORBIDDEN",
                )

            self._lock_share_target(target_type=target_type, target_id=target_id)
            existing = self.db.scalar(
                select(db_models.KnowledgeBaseShare)
                .where(
                    db_models.KnowledgeBaseShare.kb_id == kb_id,
                    db_models.KnowledgeBaseShare.target_type == target_type,
                    db_models.KnowledgeBaseShare.target_id == target_id,
                )
                .with_for_update()
            )
            if existing is not None:
                raise KnowledgeBaseConflictError(
                    KB_SHARE_CONFLICT_MESSAGE,
                    code="KB_SHARE_DUPLICATE_TARGET",
                )

            share = db_models.KnowledgeBaseShare(
                id=str(uuid4()),
                kb_id=kb_id,
                target_type=target_type,
                target_id=target_id,
                role=canonical_role.value,
                granted_by_id=actor.user_id,
            )
            self.db.add(share)
            self.db.flush()
            self.audit_events.record(
                event_type="knowledge_base.share_created",
                actor_type="user",
                actor_id=actor.user_id,
                actor_user_id=actor.user_id,
                target_type=target_type,
                target_id=target_id,
                action="create_share",
                result="success",
                error_code=None,
                correlation_id=correlation_id,
                root_correlation_id=root_correlation_id,
                metadata={"kb_id": kb_id, "after": canonical_role.value},
            )
            self.db.refresh(share)
            self.db.commit()
            return share
        except IntegrityError as exc:
            self.db.rollback()
            if "knowledge_base_shares" not in str(exc.orig):
                self._persist_failure_audit(
                    event_type="knowledge_base.share_created",
                    user_id=actor.user_id,
                    target_type=audit_target_type,
                    target_id=target_id,
                    action="create_share",
                    error_code="KB_SHARE_FORBIDDEN",
                    correlation_id=correlation_id,
                    root_correlation_id=root_correlation_id,
                    metadata={"kb_id": kb_id},
                )
                raise
            self._persist_failure_audit(
                event_type="knowledge_base.share_created",
                user_id=actor.user_id,
                target_type=audit_target_type,
                target_id=target_id,
                action="create_share",
                error_code="KB_SHARE_DUPLICATE_TARGET",
                correlation_id=correlation_id,
                root_correlation_id=root_correlation_id,
                metadata={"kb_id": kb_id},
            )
            raise KnowledgeBaseConflictError(
                KB_SHARE_CONFLICT_MESSAGE,
                code="KB_SHARE_DUPLICATE_TARGET",
            ) from exc
        except Exception as exc:
            self.db.rollback()
            normalized = self._normalize_share_error(exc)
            self._persist_failure_audit(
                event_type="knowledge_base.share_created",
                user_id=actor.user_id,
                target_type=audit_target_type,
                target_id=target_id,
                action="create_share",
                error_code=self._share_failure_code(normalized),
                correlation_id=correlation_id,
                root_correlation_id=root_correlation_id,
                metadata={"kb_id": kb_id},
            )
            if normalized is not exc:
                raise normalized from exc
            raise

    def update_share_role(
        self,
        *,
        actor: AuthorizationActor,
        kb_id: str,
        share_id: str,
        role: str,
        correlation_id: str | None = None,
        root_correlation_id: str | None = None,
    ) -> db_models.KnowledgeBaseShare:
        correlation_id = correlation_id or str(uuid4())
        root_correlation_id = root_correlation_id or correlation_id
        audit_target_type = "knowledge_base_share"
        audit_target_id = share_id
        audit_metadata: dict[str, object] | None = None
        try:
            self.kb_service.get_kb_for_operation(
                actor=actor,
                kb_id=kb_id,
                operation=OperationId.KNOWLEDGE_BASE_SHARE_MANAGE,
            )
            share = self.db.scalar(
                select(db_models.KnowledgeBaseShare)
                .where(
                    db_models.KnowledgeBaseShare.id == share_id,
                    db_models.KnowledgeBaseShare.kb_id == kb_id,
                )
                .with_for_update()
            )
            if share is None:
                raise KnowledgeBaseNotFoundError(
                    KB_SHARE_TARGET_NOT_FOUND_MESSAGE,
                    code="KB_SHARE_TARGET_NOT_FOUND",
                )
            audit_target_type = share.target_type
            audit_target_id = share.target_id
            audit_metadata = {"kb_id": share.kb_id}
            canonical_role = normalize_resource_role(role)
            if canonical_role not in RESOURCE_SHARE_ROLES:
                raise kb_errors.KnowledgeBaseError(
                    KB_SHARE_INVALID_ROLE_MESSAGE,
                    code="KB_SHARE_INVALID_ROLE",
                )
            previous_role = share.role
            share.role = canonical_role.value
            self.db.flush()
            self.audit_events.record(
                event_type="knowledge_base.share_updated",
                actor_type="user",
                actor_id=actor.user_id,
                actor_user_id=actor.user_id,
                target_type=share.target_type,
                target_id=share.target_id,
                action="update_share",
                result="success",
                error_code=None,
                correlation_id=correlation_id,
                root_correlation_id=root_correlation_id,
                metadata={
                    "kb_id": share.kb_id,
                    "before": previous_role,
                    "after": role,
                },
            )
            self.db.refresh(share)
            self.db.commit()
            return share
        except Exception as exc:
            self.db.rollback()
            normalized = self._normalize_share_error(exc)
            self._persist_failure_audit(
                event_type="knowledge_base.share_updated",
                user_id=actor.user_id,
                target_type=audit_target_type,
                target_id=audit_target_id,
                action="update_share",
                error_code=self._share_failure_code(normalized),
                correlation_id=correlation_id,
                root_correlation_id=root_correlation_id,
                metadata=audit_metadata,
            )
            if normalized is not exc:
                raise normalized from exc
            raise

    def revoke_share(
        self,
        *,
        actor: AuthorizationActor,
        kb_id: str,
        share_id: str,
        correlation_id: str | None = None,
        root_correlation_id: str | None = None,
    ) -> None:
        correlation_id = correlation_id or str(uuid4())
        root_correlation_id = root_correlation_id or correlation_id
        audit_target_type = "knowledge_base_share"
        audit_target_id = share_id
        audit_metadata: dict[str, object] | None = None
        try:
            self.kb_service.get_kb_for_operation(
                actor=actor,
                kb_id=kb_id,
                operation=OperationId.KNOWLEDGE_BASE_SHARE_MANAGE,
            )
            share = self.db.scalar(
                select(db_models.KnowledgeBaseShare)
                .where(
                    db_models.KnowledgeBaseShare.id == share_id,
                    db_models.KnowledgeBaseShare.kb_id == kb_id,
                )
                .with_for_update()
            )
            if share is None:
                raise KnowledgeBaseNotFoundError(
                    KB_SHARE_TARGET_NOT_FOUND_MESSAGE,
                    code="KB_SHARE_TARGET_NOT_FOUND",
                )
            audit_target_type = share.target_type
            audit_target_id = share.target_id
            audit_metadata = {"kb_id": share.kb_id}
            self.db.delete(share)
            self.db.flush()
            self.audit_events.record(
                event_type="knowledge_base.share_deleted",
                actor_type="user",
                actor_id=actor.user_id,
                actor_user_id=actor.user_id,
                target_type=share.target_type,
                target_id=share.target_id,
                action="delete_share",
                result="success",
                error_code=None,
                correlation_id=correlation_id,
                root_correlation_id=root_correlation_id,
                metadata={"kb_id": share.kb_id, "before": share.role},
            )
            self.db.commit()
        except Exception as exc:
            self.db.rollback()
            normalized = self._normalize_share_error(exc)
            self._persist_failure_audit(
                event_type="knowledge_base.share_deleted",
                user_id=actor.user_id,
                target_type=audit_target_type,
                target_id=audit_target_id,
                action="delete_share",
                error_code=self._share_failure_code(normalized),
                correlation_id=correlation_id,
                root_correlation_id=root_correlation_id,
                metadata=audit_metadata,
            )
            if normalized is not exc:
                raise normalized from exc
            raise

    def _lock_share_target(self, *, target_type: str, target_id: str) -> None:
        target_model = db_models.User if target_type == "user" else db_models.UserGroup
        locked_target_id = self.db.scalar(
            select(target_model.id)
            .where(target_model.id == target_id)
            .with_for_update()
        )
        if locked_target_id is None:
            raise KnowledgeBaseNotFoundError(
                KB_SHARE_TARGET_NOT_FOUND_MESSAGE,
                code="KB_SHARE_TARGET_NOT_FOUND",
            )

    def _persist_failure_audit(
        self,
        *,
        event_type: str,
        user_id: str,
        target_type: str,
        target_id: str,
        action: str,
        error_code: str,
        correlation_id: str,
        root_correlation_id: str,
        metadata: dict[str, object] | None,
    ) -> None:
        try:
            with Session(bind=self.db.get_bind()) as audit_db:
                AuditEventService(audit_db).record(
                    event_type=event_type,
                    actor_type="user",
                    actor_id=user_id,
                    actor_user_id=user_id,
                    target_type=target_type,
                    target_id=target_id,
                    action=action,
                    result="failure",
                    error_code=error_code,
                    correlation_id=correlation_id,
                    root_correlation_id=root_correlation_id,
                    metadata=metadata,
                )
                audit_db.commit()
        except Exception:
            logger.exception(
                "Failed to persist knowledge base share failure audit",
                extra={"event_type": event_type, "target_id": target_id},
            )

    @staticmethod
    def _normalize_share_error(exc: Exception) -> Exception:
        if isinstance(exc, KnowledgeBaseAccessDeniedError):
            return KnowledgeBaseAccessDeniedError(
                str(exc),
                code="KB_SHARE_FORBIDDEN",
                params=exc.params,
            )
        return exc

    @staticmethod
    def _share_failure_code(exc: Exception) -> str:
        error_code = getattr(exc, "code", None)
        if isinstance(error_code, str) and error_code:
            return error_code
        return "KB_SHARE_FORBIDDEN"
