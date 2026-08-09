"""Platform Admin resource inventory and audited Owner reassignment."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import uuid4

from pydantic import ConfigDict, Field, field_validator
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session, aliased

from app.config.settings import get_settings
from app.core.pydantic import CamelModel
from app.db import models as db_models
from app.modules.audit.events import AuditEventService
from app.modules.authorization.actor import AuthorizationActor
from app.modules.authorization.operation_policy import (
    AuthorizationOperationPolicy,
    OperationId,
)
from app.modules.authorization.resource_access import ResourceAccessRole
from app.modules.identity.user_authorization_policy import UserAuthorizationPolicy
from app.modules.knowledge_base.access_repository import KnowledgeBaseAccessResolver
from app.modules.platform_resource_capacity.inventory import (
    PlatformResourceCapacityInventory,
)
from app.modules.platform_resource_capacity.models import PlatformCapacityProjection
from app.modules.workspace.access_repository import WorkspaceAccessResolver
from app.modules.workspace.runtime.job_repository import WorkspaceRuntimeJobRepository

logger = logging.getLogger(__name__)


class PlatformResourceOwner(CamelModel):
    """Non-sensitive Owner projection for resource administration."""

    id: str
    username: str
    display_name: str | None = Field(None, alias="displayName")
    avatar_url: str | None = Field(None, alias="avatarUrl")


class PlatformWorkspaceSummary(CamelModel):
    """Workspace inventory row without credentials or mutable settings."""

    id: str
    name: str
    description: str | None = None
    owner: PlatformResourceOwner
    runtime_status: str = Field(..., alias="runtimeStatus")
    provisioner: str
    created_at: datetime = Field(..., alias="createdAt")
    updated_at: datetime | None = Field(None, alias="updatedAt")
    workspace_data: "PlatformCapacityProjection | None" = Field(
        None, alias="workspaceData"
    )
    runtime_home: "PlatformCapacityProjection | None" = Field(None, alias="runtimeHome")
    capacity_risk: str = Field("unknown", alias="capacityRisk")


class PlatformKnowledgeBaseSummary(CamelModel):
    """Knowledge Base inventory row without Git or storage credentials."""

    id: str
    name: str
    slug: str
    description: str | None = None
    owner: PlatformResourceOwner
    visibility: str
    current_size_bytes: int = Field(..., alias="currentSizeBytes")
    quota_bytes: int | None = Field(None, alias="quotaBytes")
    effective_quota_bytes: int = Field(..., alias="effectiveQuotaBytes")
    quota_source: str = Field(..., alias="quotaSource")
    utilization_percent: float = Field(..., alias="utilizationPercent")
    capacity_risk: str = Field(..., alias="capacityRisk")
    indexing_health: str = Field(..., alias="indexingHealth")
    created_at: datetime = Field(..., alias="createdAt")
    updated_at: datetime | None = Field(None, alias="updatedAt")


class PlatformWorkspaceListResponse(CamelModel):
    items: list[PlatformWorkspaceSummary]
    total: int
    page: int
    page_size: int = Field(..., alias="pageSize")


class PlatformKnowledgeBaseListResponse(CamelModel):
    items: list[PlatformKnowledgeBaseSummary]
    total: int
    page: int
    page_size: int = Field(..., alias="pageSize")


class OwnerReassignmentRequest(CamelModel):
    """Admin command payload with a mandatory human-readable reason."""

    model_config = ConfigDict(extra="forbid")

    target_user_id: str = Field(..., min_length=1, max_length=128, alias="targetUserId")
    reason: str = Field(..., min_length=3, max_length=500)

    @field_validator("target_user_id", "reason")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("value must not be blank")
        return normalized

    @field_validator("reason")
    @classmethod
    def reject_control_characters(cls, value: str) -> str:
        if any(ord(character) < 32 for character in value):
            raise ValueError("reason contains control characters")
        return value


@dataclass
class OwnerReassignmentError(Exception):
    """Stable domain error for Owner reassignment failures."""

    error_code: str
    http_status: int


class OwnershipNotificationPublisher(Protocol):
    """Delivery seam for informing the previous Owner after commit."""

    def publish_owner_reassigned(
        self,
        *,
        resource_type: str,
        resource_id: str,
        previous_owner_id: str,
        new_owner_id: str,
        reason: str,
    ) -> None: ...


class ResourceAccessRecyclePublisher(Protocol):
    """Delivery seam for invalidating post-commit resource access projections."""

    def publish_access_recycle(
        self,
        *,
        resource_type: str,
        resource_id: str,
        actor_user_id: str,
        correlation_id: str,
        root_correlation_id: str,
    ) -> None: ...


class DatabaseOwnershipNotificationPublisher:
    """Persist a durable previous-owner notification for downstream delivery."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.audit_events = AuditEventService(db)

    def publish_owner_reassigned(
        self,
        *,
        resource_type: str,
        resource_id: str,
        previous_owner_id: str,
        new_owner_id: str,
        reason: str,
    ) -> None:
        correlation_id = str(uuid4())
        self.audit_events.record(
            event_type="platform_resource.owner_reassigned_notification",
            actor_type="service",
            actor_id="platform-resource-authorization",
            actor_user_id=None,
            target_type="user",
            target_id=previous_owner_id,
            action="notify_previous_owner",
            result="success",
            error_code=None,
            correlation_id=correlation_id,
            root_correlation_id=correlation_id,
            metadata={
                "previous_owner_id": previous_owner_id,
                "new_owner_id": new_owner_id,
                "owner_reassignment_reason": reason,
                (
                    "workspace_id" if resource_type == "workspace" else "kb_id"
                ): resource_id,
            },
        )
        self.db.commit()


class DatabaseResourceAccessRecyclePublisher:
    """Persist runtime access invalidation after ownership has committed."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.jobs = WorkspaceRuntimeJobRepository(db)
        self.audit_events = AuditEventService(db)

    def publish_access_recycle(
        self,
        *,
        resource_type: str,
        resource_id: str,
        actor_user_id: str,
        correlation_id: str,
        root_correlation_id: str,
    ) -> None:
        workspaces = self._lock_affected_workspaces(
            resource_type=resource_type,
            resource_id=resource_id,
        )
        try:
            for workspace in workspaces:
                workspace.runtime_access_revision += 1
                self.jobs.supersede_queued_and_enqueue_access_recycle(
                    workspace=workspace,
                    correlation_id=correlation_id,
                    root_correlation_id=root_correlation_id,
                    scheduled_at=datetime.utcnow(),
                    job_metadata={"reason": "platform_owner_reassigned"},
                )
                self.audit_events.record(
                    event_type="runtime.access_recycle_requested",
                    actor_type="user",
                    actor_id=actor_user_id,
                    actor_user_id=actor_user_id,
                    target_type="workspace",
                    target_id=workspace.id,
                    action="request_access_recycle",
                    result="success",
                    error_code=None,
                    correlation_id=correlation_id,
                    root_correlation_id=root_correlation_id,
                    metadata={
                        "workspace_id": workspace.id,
                        "runtime_access_revision": workspace.runtime_access_revision,
                        "reason": "platform_owner_reassigned",
                    },
                )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

    def _lock_affected_workspaces(
        self,
        *,
        resource_type: str,
        resource_id: str,
    ) -> list[db_models.Workspace]:
        if resource_type == "workspace":
            workspace_ids = {resource_id}
        else:
            workspace_ids = set(
                self.db.scalars(
                    select(db_models.WorkspaceKnowledgeBaseAttachment.workspace_id)
                    .where(
                        db_models.WorkspaceKnowledgeBaseAttachment.kb_id == resource_id
                    )
                    .order_by(
                        db_models.WorkspaceKnowledgeBaseAttachment.workspace_id.asc()
                    )
                ).all()
            )
            candidate_workspaces = self.db.scalars(
                select(db_models.Workspace).where(
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
            ).all()
            for workspace in candidate_workspaces:
                snapshots = (
                    workspace.knowledge_base_mount_candidate_snapshot,
                    workspace.knowledge_base_mount_failed_snapshot,
                )
                if any(
                    any(
                        isinstance(entry, dict)
                        and entry.get("knowledgeBaseId") == resource_id
                        for entry in (snapshot if isinstance(snapshot, list) else [])
                    )
                    for snapshot in snapshots
                ):
                    workspace_ids.add(workspace.id)
        if not workspace_ids:
            return []
        return list(
            self.db.scalars(
                select(db_models.Workspace)
                .where(db_models.Workspace.id.in_(workspace_ids))
                .order_by(db_models.Workspace.id.asc())
                .with_for_update()
                .execution_options(populate_existing=True)
            ).all()
        )


class PlatformResourceInventory:
    """Provide a separate global inventory without polluting member list caches."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.authorization = AuthorizationOperationPolicy(db)

    def list_workspaces(
        self,
        *,
        actor: AuthorizationActor,
        q: str | None,
        page: int,
        page_size: int,
        health: str | None = None,
        capacity_risk: str | None = None,
        sort: str = "createdAt",
        order: str = "desc",
    ) -> PlatformWorkspaceListResponse:
        self.authorization.require_platform_operation(
            actor,
            OperationId.PLATFORM_RESOURCES_READ,
        )
        self._validate_page(page=page, page_size=page_size)
        owner = db_models.User
        workspace_data = aliased(db_models.ResourceCapacityObservation)
        runtime_home = aliased(db_models.ResourceCapacityObservation)
        query = (
            select(db_models.Workspace, owner)
            .join(owner, owner.id == db_models.Workspace.owner_id)
            .outerjoin(
                workspace_data,
                and_(
                    workspace_data.resource_type == "workspace",
                    workspace_data.resource_id == db_models.Workspace.id,
                    workspace_data.storage_kind == "workspace_data",
                ),
            )
            .outerjoin(
                runtime_home,
                and_(
                    runtime_home.resource_type == "workspace",
                    runtime_home.resource_id == db_models.Workspace.id,
                    runtime_home.storage_kind == "runtime_home",
                ),
            )
        )
        normalized_q = self._normalize_query(q)
        if normalized_q is not None:
            pattern = f"%{normalized_q}%"
            query = query.where(
                or_(
                    db_models.Workspace.name.ilike(pattern),
                    owner.username.ilike(pattern),
                    owner.display_name.ilike(pattern),
                )
            )
        if health is not None:
            statuses = {
                "running": ("running",),
                "transitioning": ("starting", "stopping", "restarting"),
                "stopped": ("stopped",),
                "error": ("error",),
                "deleting": ("deleting",),
            }.get(health)
            if statuses is None:
                raise OwnerReassignmentError("PLATFORM_RESOURCE_INVALID_REQUEST", 422)
            query = query.where(db_models.Workspace.runtime_status.in_(statuses))
        capacity = PlatformResourceCapacityInventory.workspace_expressions(
            workspace_data, runtime_home
        )
        if capacity_risk is not None:
            if capacity_risk not in {
                "unknown",
                "stale",
                "critical",
                "warning",
                "normal",
            }:
                raise OwnerReassignmentError("PLATFORM_RESOURCE_INVALID_REQUEST", 422)
            query = query.where(capacity.risk == capacity_risk)
        sort_expression = {
            "createdAt": db_models.Workspace.created_at,
            "name": db_models.Workspace.name,
            "usedBytes": capacity.used_bytes,
            "utilization": capacity.utilization,
        }.get(sort)
        if sort_expression is None or order not in {"asc", "desc"}:
            raise OwnerReassignmentError("PLATFORM_RESOURCE_INVALID_REQUEST", 422)
        ordering = sort_expression.asc() if order == "asc" else sort_expression.desc()
        total = self.db.scalar(select(func.count()).select_from(query.subquery())) or 0
        rows = self.db.execute(
            query.order_by(ordering, db_models.Workspace.id.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
        workspace_ids = [resource.id for resource, _owner in rows]
        observations = (
            self.db.scalars(
                select(db_models.ResourceCapacityObservation).where(
                    db_models.ResourceCapacityObservation.resource_type == "workspace",
                    db_models.ResourceCapacityObservation.resource_id.in_(
                        workspace_ids
                    ),
                )
            ).all()
            if workspace_ids
            else []
        )
        allocations = (
            self.db.scalars(
                select(db_models.WorkspaceStorageAllocation).where(
                    db_models.WorkspaceStorageAllocation.workspace_id.in_(workspace_ids)
                )
            ).all()
            if workspace_ids
            else []
        )
        capacities = {(row.resource_id, row.storage_kind): row for row in observations}
        expansion_support = {
            (row.workspace_id, row.storage_kind): row.expansion_supported is True
            for row in allocations
        }
        return PlatformWorkspaceListResponse(
            items=[
                _workspace_summary(
                    resource,
                    row_owner,
                    capacities,
                    expansion_support,
                )
                for resource, row_owner in rows
            ],
            total=total,
            page=page,
            pageSize=page_size,
        )

    def list_knowledge_bases(
        self,
        *,
        actor: AuthorizationActor,
        q: str | None,
        page: int,
        page_size: int,
        visibility: str | None = None,
        indexing_health: str | None = None,
        capacity_risk: str | None = None,
        sort: str = "createdAt",
        order: str = "desc",
    ) -> PlatformKnowledgeBaseListResponse:
        self.authorization.require_platform_operation(
            actor,
            OperationId.PLATFORM_RESOURCES_READ,
        )
        self._validate_page(page=page, page_size=page_size)
        owner = db_models.User
        query = select(db_models.KnowledgeBase, owner).join(
            owner, owner.id == db_models.KnowledgeBase.owner_id
        )
        normalized_q = self._normalize_query(q)
        if normalized_q is not None:
            pattern = f"%{normalized_q}%"
            query = query.where(
                or_(
                    db_models.KnowledgeBase.name.ilike(pattern),
                    db_models.KnowledgeBase.slug.ilike(pattern),
                    owner.username.ilike(pattern),
                    owner.display_name.ilike(pattern),
                )
            )
        if visibility is not None:
            if visibility not in {"public", "private"}:
                raise OwnerReassignmentError("PLATFORM_RESOURCE_INVALID_REQUEST", 422)
            query = query.where(db_models.KnowledgeBase.visibility == visibility)
        if indexing_health is not None:
            statuses = {
                "success": ("success", "completed"),
                "processing": ("processing", "pending"),
                "failure": ("failure", "failed", "error"),
            }.get(indexing_health)
            if indexing_health == "never_indexed":
                query = query.where(db_models.KnowledgeBase.last_index_status.is_(None))
            elif statuses is None:
                raise OwnerReassignmentError("PLATFORM_RESOURCE_INVALID_REQUEST", 422)
            else:
                query = query.where(
                    db_models.KnowledgeBase.last_index_status.in_(statuses)
                )
        capacity = PlatformResourceCapacityInventory.knowledge_base_expressions(
            get_settings().DEFAULT_KB_QUOTA_BYTES
        )
        if capacity_risk is not None:
            if capacity_risk not in {"critical", "warning", "normal"}:
                raise OwnerReassignmentError("PLATFORM_RESOURCE_INVALID_REQUEST", 422)
            query = query.where(capacity.risk == capacity_risk)
        sort_expression = {
            "createdAt": db_models.KnowledgeBase.created_at,
            "name": db_models.KnowledgeBase.name,
            "usedBytes": db_models.KnowledgeBase.current_size_bytes,
            "utilization": capacity.utilization,
        }.get(sort)
        if sort_expression is None or order not in {"asc", "desc"}:
            raise OwnerReassignmentError("PLATFORM_RESOURCE_INVALID_REQUEST", 422)
        ordering = sort_expression.asc() if order == "asc" else sort_expression.desc()
        total = self.db.scalar(select(func.count()).select_from(query.subquery())) or 0
        rows = self.db.execute(
            query.order_by(ordering, db_models.KnowledgeBase.id.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
        return PlatformKnowledgeBaseListResponse(
            items=[
                _knowledge_base_summary(resource, row_owner)
                for resource, row_owner in rows
            ],
            total=total,
            page=page,
            pageSize=page_size,
        )

    @staticmethod
    def _validate_page(*, page: int, page_size: int) -> None:
        if page < 1 or not 1 <= page_size <= 100:
            raise OwnerReassignmentError("PLATFORM_RESOURCE_INVALID_REQUEST", 422)

    @staticmethod
    def _normalize_query(q: str | None) -> str | None:
        if q is None:
            return None
        normalized = q.strip()
        if len(normalized) > 200:
            raise OwnerReassignmentError("PLATFORM_RESOURCE_INVALID_REQUEST", 422)
        return normalized or None


class OwnerReassignment:
    """Atomically reassign resource ownership and deliver committed effects."""

    def __init__(
        self,
        db: Session,
        *,
        notification_publisher: OwnershipNotificationPublisher | None = None,
        access_recycle_publisher: ResourceAccessRecyclePublisher | None = None,
    ) -> None:
        self.db = db
        self.authorization = AuthorizationOperationPolicy(db)
        self.audit_events = AuditEventService(db)
        self.authorization_policy = UserAuthorizationPolicy()
        self.workspace_access = WorkspaceAccessResolver(db)
        self.knowledge_base_access = KnowledgeBaseAccessResolver(db)
        self.notification_publisher = (
            notification_publisher or DatabaseOwnershipNotificationPublisher(db)
        )
        self.access_recycle_publisher = (
            access_recycle_publisher or DatabaseResourceAccessRecyclePublisher(db)
        )

    def reassign_workspace_owner(
        self,
        *,
        actor: AuthorizationActor,
        workspace_id: str,
        payload: OwnerReassignmentRequest,
        correlation_id: str,
        root_correlation_id: str,
    ) -> PlatformWorkspaceSummary:
        return self._reassign_owner(
            actor=actor,
            resource_type="workspace",
            resource_id=workspace_id,
            payload=payload,
            correlation_id=correlation_id,
            root_correlation_id=root_correlation_id,
        )

    def reassign_knowledge_base_owner(
        self,
        *,
        actor: AuthorizationActor,
        kb_id: str,
        payload: OwnerReassignmentRequest,
        correlation_id: str,
        root_correlation_id: str,
    ) -> PlatformKnowledgeBaseSummary:
        return self._reassign_owner(
            actor=actor,
            resource_type="knowledge_base",
            resource_id=kb_id,
            payload=payload,
            correlation_id=correlation_id,
            root_correlation_id=root_correlation_id,
        )

    def _reassign_owner(
        self,
        *,
        actor: AuthorizationActor,
        resource_type: str,
        resource_id: str,
        payload: OwnerReassignmentRequest,
        correlation_id: str,
        root_correlation_id: str,
    ) -> PlatformWorkspaceSummary | PlatformKnowledgeBaseSummary:
        self.authorization.require_platform_operation(
            actor,
            OperationId.PLATFORM_RESOURCES_OWNER_REASSIGN,
        )
        model = (
            db_models.Workspace
            if resource_type == "workspace"
            else db_models.KnowledgeBase
        )
        try:
            resource = self.db.scalar(
                select(model)
                .where(model.id == resource_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
            if resource is None:
                raise OwnerReassignmentError("PLATFORM_RESOURCE_NOT_FOUND", 404)
            previous_owner = self.db.scalar(
                select(db_models.User)
                .where(db_models.User.id == resource.owner_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
            target = self.db.scalar(
                select(db_models.User)
                .where(db_models.User.id == payload.target_user_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
            if previous_owner is None:
                raise OwnerReassignmentError("PLATFORM_RESOURCE_OWNER_NOT_FOUND", 409)
            if target is None or not self.authorization_policy.is_authorized(target):
                raise OwnerReassignmentError(
                    "PLATFORM_RESOURCE_TARGET_NOT_AUTHORIZABLE", 409
                )
            if target.id == previous_owner.id:
                raise OwnerReassignmentError("PLATFORM_RESOURCE_OWNER_UNCHANGED", 409)
            if not self._target_is_effective_manager(
                target=target,
                resource_type=resource_type,
                resource_id=resource_id,
            ):
                raise OwnerReassignmentError(
                    "PLATFORM_RESOURCE_TARGET_MANAGER_REQUIRED", 409
                )

            self._lock_resource_shares(
                resource_type=resource_type,
                resource_id=resource_id,
            )
            previous_owner_id = previous_owner.id
            resource.owner_id = target.id
            self._remove_direct_share(
                resource_type=resource_type,
                resource_id=resource_id,
                user_id=target.id,
            )
            if self.authorization_policy.is_authorized(previous_owner):
                self._upsert_previous_owner_manager_share(
                    resource_type=resource_type,
                    resource_id=resource_id,
                    previous_owner_id=previous_owner.id,
                    actor_user_id=actor.user_id,
                )
            else:
                self._remove_direct_share(
                    resource_type=resource_type,
                    resource_id=resource_id,
                    user_id=previous_owner.id,
                )

            self.audit_events.record(
                event_type=f"platform_resource.{resource_type}_owner_reassigned",
                actor_type="user",
                actor_id=actor.user_id,
                actor_user_id=actor.user_id,
                target_type=resource_type,
                target_id=resource_id,
                action="reassign_resource_owner",
                result="success",
                error_code=None,
                correlation_id=correlation_id,
                root_correlation_id=root_correlation_id,
                metadata={
                    "changed_fields": ["owner_id"],
                    "previous_owner_id": previous_owner_id,
                    "new_owner_id": target.id,
                    "owner_reassignment_reason": payload.reason,
                    **(
                        {"workspace_id": resource_id}
                        if resource_type == "workspace"
                        else {"kb_id": resource_id}
                    ),
                },
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        self._publish_after_commit(
            resource_type=resource_type,
            resource_id=resource_id,
            previous_owner_id=previous_owner_id,
            new_owner_id=target.id,
            reason=payload.reason,
            actor_user_id=actor.user_id,
            correlation_id=correlation_id,
            root_correlation_id=root_correlation_id,
        )
        refreshed = self.db.get(model, resource_id)
        refreshed_owner = self.db.get(db_models.User, target.id)
        if refreshed is None or refreshed_owner is None:
            raise OwnerReassignmentError("PLATFORM_RESOURCE_NOT_FOUND", 404)
        if resource_type == "workspace":
            return _workspace_summary(refreshed, refreshed_owner)
        return _knowledge_base_summary(refreshed, refreshed_owner)

    def _target_is_effective_manager(
        self,
        *,
        target: db_models.User,
        resource_type: str,
        resource_id: str,
    ) -> bool:
        if resource_type == "workspace":
            workspace = self.db.get(db_models.Workspace, resource_id)
            if workspace is None:
                return False
            access = self.workspace_access.resolve(
                workspace=workspace,
                user_id=target.id,
            )
        else:
            access = self.knowledge_base_access.resolve(
                knowledge_base_id=resource_id,
                user_id=target.id,
            )
        return bool(
            access is not None and access.access_role is ResourceAccessRole.MANAGER
        )

    def _lock_resource_shares(self, *, resource_type: str, resource_id: str) -> None:
        share_model = (
            db_models.WorkspaceShare
            if resource_type == "workspace"
            else db_models.KnowledgeBaseShare
        )
        foreign_key = (
            share_model.workspace_id
            if resource_type == "workspace"
            else share_model.kb_id
        )
        list(
            self.db.scalars(
                select(share_model)
                .where(foreign_key == resource_id)
                .order_by(share_model.id)
                .with_for_update()
            ).all()
        )

    def _remove_direct_share(
        self, *, resource_type: str, resource_id: str, user_id: str
    ) -> None:
        share_model = (
            db_models.WorkspaceShare
            if resource_type == "workspace"
            else db_models.KnowledgeBaseShare
        )
        foreign_key = (
            share_model.workspace_id
            if resource_type == "workspace"
            else share_model.kb_id
        )
        shares = self.db.scalars(
            select(share_model).where(
                foreign_key == resource_id,
                share_model.target_type == "user",
                share_model.target_id == user_id,
            )
        ).all()
        for share in shares:
            self.db.delete(share)

    def _upsert_previous_owner_manager_share(
        self,
        *,
        resource_type: str,
        resource_id: str,
        previous_owner_id: str,
        actor_user_id: str,
    ) -> None:
        share_model = (
            db_models.WorkspaceShare
            if resource_type == "workspace"
            else db_models.KnowledgeBaseShare
        )
        foreign_key = (
            share_model.workspace_id
            if resource_type == "workspace"
            else share_model.kb_id
        )
        share = self.db.scalar(
            select(share_model).where(
                foreign_key == resource_id,
                share_model.target_type == "user",
                share_model.target_id == previous_owner_id,
            )
        )
        grant_field = (
            "granted_by_user_id" if resource_type == "workspace" else "granted_by_id"
        )
        if share is not None:
            share.role = "manager"
            setattr(share, grant_field, actor_user_id)
            return
        values = {
            "id": str(uuid4()),
            "target_type": "user",
            "target_id": previous_owner_id,
            "role": "manager",
            grant_field: actor_user_id,
            ("workspace_id" if resource_type == "workspace" else "kb_id"): resource_id,
        }
        self.db.add(share_model(**values))

    def _publish_after_commit(
        self,
        *,
        resource_type: str,
        resource_id: str,
        previous_owner_id: str,
        new_owner_id: str,
        reason: str,
        actor_user_id: str,
        correlation_id: str,
        root_correlation_id: str,
    ) -> None:
        deliveries = (
            (
                "notification",
                lambda: self.notification_publisher.publish_owner_reassigned(
                    resource_type=resource_type,
                    resource_id=resource_id,
                    previous_owner_id=previous_owner_id,
                    new_owner_id=new_owner_id,
                    reason=reason,
                ),
            ),
            (
                "access_recycle",
                lambda: self.access_recycle_publisher.publish_access_recycle(
                    resource_type=resource_type,
                    resource_id=resource_id,
                    actor_user_id=actor_user_id,
                    correlation_id=correlation_id,
                    root_correlation_id=root_correlation_id,
                ),
            ),
        )
        for delivery_name, publish in deliveries:
            try:
                publish()
            except Exception:
                logger.exception(
                    "platform_resource.owner_reassignment_delivery_failed "
                    "delivery=%s resource_type=%s resource_id=%s",
                    delivery_name,
                    resource_type,
                    resource_id,
                )
                self._record_delivery_failure(
                    delivery_name=delivery_name,
                    resource_type=resource_type,
                    resource_id=resource_id,
                    previous_owner_id=previous_owner_id,
                    new_owner_id=new_owner_id,
                    actor_user_id=actor_user_id,
                    correlation_id=correlation_id,
                    root_correlation_id=root_correlation_id,
                )

    def _record_delivery_failure(
        self,
        *,
        delivery_name: str,
        resource_type: str,
        resource_id: str,
        previous_owner_id: str,
        new_owner_id: str,
        actor_user_id: str,
        correlation_id: str,
        root_correlation_id: str,
    ) -> None:
        self.db.rollback()
        self.audit_events.record(
            event_type=(f"platform_resource.owner_reassignment_{delivery_name}_failed"),
            actor_type="user",
            actor_id=actor_user_id,
            actor_user_id=actor_user_id,
            target_type=resource_type,
            target_id=resource_id,
            action=f"publish_owner_reassignment_{delivery_name}",
            result="failure",
            error_code=(
                "PLATFORM_RESOURCE_OWNER_NOTIFICATION_FAILED"
                if delivery_name == "notification"
                else "PLATFORM_RESOURCE_ACCESS_RECYCLE_FAILED"
            ),
            correlation_id=correlation_id,
            root_correlation_id=root_correlation_id,
            metadata={
                "previous_owner_id": previous_owner_id,
                "new_owner_id": new_owner_id,
                **(
                    {"workspace_id": resource_id}
                    if resource_type == "workspace"
                    else {"kb_id": resource_id}
                ),
            },
        )
        self.db.commit()


def _workspace_summary(
    workspace: db_models.Workspace,
    owner: db_models.User,
    capacities: (
        dict[tuple[str, str], db_models.ResourceCapacityObservation] | None
    ) = None,
    expansion_support: dict[tuple[str, str], bool] | None = None,
) -> PlatformWorkspaceSummary:
    capacities = capacities or {}
    expansion_support = expansion_support or {}
    workspace_data = PlatformResourceCapacityInventory.workspace_projection(
        capacities.get((workspace.id, "workspace_data")),
        expansion_supported=expansion_support.get(
            (workspace.id, "workspace_data"), False
        ),
    )
    runtime_home = PlatformResourceCapacityInventory.workspace_projection(
        capacities.get((workspace.id, "runtime_home")),
        expansion_supported=expansion_support.get(
            (workspace.id, "runtime_home"), False
        ),
    )
    risks = [
        projection.risk
        for projection in (workspace_data, runtime_home)
        if projection is not None
    ]
    return PlatformWorkspaceSummary(
        id=workspace.id,
        name=workspace.name,
        description=workspace.description,
        owner=_owner_summary(owner),
        runtimeStatus=workspace.runtime_status,
        provisioner=workspace.provisioner,
        createdAt=workspace.created_at,
        updatedAt=workspace.updated_at,
        workspaceData=workspace_data,
        runtimeHome=runtime_home,
        capacityRisk=PlatformResourceCapacityInventory.highest(risks),
    )


def _knowledge_base_summary(
    knowledge_base: db_models.KnowledgeBase, owner: db_models.User
) -> PlatformKnowledgeBaseSummary:
    settings = get_settings()
    capacity = PlatformResourceCapacityInventory.knowledge_base_projection(
        knowledge_base,
        default_quota_bytes=settings.DEFAULT_KB_QUOTA_BYTES,
    )
    indexing_health = {
        "success": "success",
        "completed": "success",
        "processing": "processing",
        "pending": "processing",
        "failure": "failure",
        "failed": "failure",
        "error": "failure",
    }.get(knowledge_base.last_index_status or "", "never_indexed")
    return PlatformKnowledgeBaseSummary(
        id=knowledge_base.id,
        name=knowledge_base.name,
        slug=knowledge_base.slug,
        description=knowledge_base.description,
        owner=_owner_summary(owner),
        visibility=knowledge_base.visibility,
        currentSizeBytes=knowledge_base.current_size_bytes,
        quotaBytes=knowledge_base.quota_bytes,
        effectiveQuotaBytes=capacity.effective_quota_bytes,
        quotaSource=capacity.quota_source,
        utilizationPercent=capacity.utilization_percent,
        capacityRisk=capacity.risk,
        indexingHealth=indexing_health,
        createdAt=knowledge_base.created_at,
        updatedAt=knowledge_base.updated_at,
    )


def _owner_summary(owner: db_models.User) -> PlatformResourceOwner:
    return PlatformResourceOwner(
        id=owner.id,
        username=owner.username,
        displayName=owner.display_name,
        avatarUrl=owner.avatar_url,
    )


__all__ = [
    "OwnerReassignmentError",
    "OwnerReassignment",
    "OwnerReassignmentRequest",
    "PlatformKnowledgeBaseListResponse",
    "PlatformKnowledgeBaseSummary",
    "PlatformResourceInventory",
    "PlatformWorkspaceListResponse",
    "PlatformWorkspaceSummary",
]
