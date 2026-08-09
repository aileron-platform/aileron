"""Capacity administration and expansion lifecycle implementation."""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Literal, cast
from uuid import uuid4

from kubernetes.utils.quantity import parse_quantity  # type: ignore[import-untyped]
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config.settings import get_settings
from app.db import models as db_models
from app.modules.audit.events import AuditEventService
from app.modules.authorization.actor import AuthorizationActor
from app.modules.authorization.operation_policy import (
    AuthorizationOperationPolicy,
    OperationId,
)

from .errors import PlatformResourceError
from .models import (
    KnowledgeBaseQuotaRequest,
    KnowledgeBaseQuotaResponse,
    StorageDesired,
    WorkspaceCapacityExpansionResponse,
    WorkspaceStorageDesiredState,
    WorkspaceStorageKind,
    WorkspaceStorageObservation,
)
from .policy import WORKSPACE_STORAGE_KINDS, CapacityGovernancePolicy

logger = logging.getLogger(__name__)

StorageDelivery = Callable[[db_models.Workspace, WorkspaceStorageDesiredState], None]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class PlatformResourceCapacityAdministration:
    """Own quota commands and the complete Workspace expansion state machine."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.settings = get_settings()
        self.authorization = AuthorizationOperationPolicy(db)
        self.audit_events = AuditEventService(db)

    def set_knowledge_base_quota(
        self,
        *,
        actor: AuthorizationActor,
        knowledge_base_id: str,
        payload: KnowledgeBaseQuotaRequest,
    ) -> KnowledgeBaseQuotaResponse:
        self.authorization.require_platform_operation(
            actor, OperationId.PLATFORM_RESOURCES_KNOWLEDGE_BASE_QUOTA_UPDATE
        )
        knowledge_base = self.db.get(db_models.KnowledgeBase, knowledge_base_id)
        if knowledge_base is None:
            raise PlatformResourceError("PLATFORM_RESOURCE_NOT_FOUND", 404)
        if payload.quota_bytes is not None and payload.quota_bytes < (
            knowledge_base.current_size_bytes or 0
        ):
            raise PlatformResourceError("KNOWLEDGE_BASE_QUOTA_BELOW_USAGE", 409)
        knowledge_base.quota_bytes = payload.quota_bytes
        knowledge_base.updated_at = _utcnow()
        correlation_id = str(uuid4())
        self.audit_events.record(
            event_type="platform_resource.knowledge_base_quota_updated",
            actor_type="user",
            actor_id=actor.user_id,
            actor_user_id=actor.user_id,
            target_type="knowledge_base",
            target_id=knowledge_base_id,
            action="update_knowledge_base_quota",
            result="success",
            error_code=None,
            correlation_id=correlation_id,
            root_correlation_id=correlation_id,
            metadata={"kb_id": knowledge_base_id, "changed_fields": ["quota_bytes"]},
        )
        self.db.commit()
        return self._quota_response(knowledge_base)

    def request_workspace_expansion(
        self,
        *,
        actor: AuthorizationActor,
        workspace_id: str,
        storage_kind: str,
        requested_bytes: int,
    ) -> WorkspaceCapacityExpansionResponse:
        self.authorization.require_platform_operation(
            actor, OperationId.PLATFORM_RESOURCES_WORKSPACE_CAPACITY_EXPAND
        )
        try:
            normalized_kind = CapacityGovernancePolicy.require_workspace_storage_kind(
                storage_kind
            )
            CapacityGovernancePolicy.require_expansion_bytes(requested_bytes)
        except ValueError as exc:
            raise PlatformResourceError(
                "WORKSPACE_CAPACITY_INVALID_REQUEST", 422
            ) from exc
        workspace = self.db.get(db_models.Workspace, workspace_id)
        if workspace is None:
            raise PlatformResourceError("PLATFORM_RESOURCE_NOT_FOUND", 404)
        if workspace.provisioner != "kubernetes":
            raise PlatformResourceError("WORKSPACE_CAPACITY_EXPANSION_UNSUPPORTED", 409)
        self._lock_workspace(workspace_id)
        workspace = self.db.get(
            db_models.Workspace,
            workspace_id,
            populate_existing=True,
            with_for_update=True,
        )
        if workspace is None:
            raise PlatformResourceError("PLATFORM_RESOURCE_NOT_FOUND", 404)
        active = self._active_request(workspace_id, normalized_kind)
        if active is not None:
            raise PlatformResourceError("WORKSPACE_CAPACITY_EXPANSION_IN_FLIGHT", 409)
        allocation = self._allocation(workspace_id, normalized_kind)
        if allocation is not None and allocation.expansion_supported is False:
            raise PlatformResourceError("WORKSPACE_CAPACITY_EXPANSION_UNSUPPORTED", 409)
        observation = self.db.scalar(
            select(db_models.ResourceCapacityObservation).where(
                db_models.ResourceCapacityObservation.resource_type == "workspace",
                db_models.ResourceCapacityObservation.resource_id == workspace_id,
                db_models.ResourceCapacityObservation.storage_kind == normalized_kind,
            )
        )
        observed_bytes = (
            allocation.observed_bytes
            if allocation is not None and allocation.observed_bytes is not None
            else (
                observation.allocated_bytes
                if observation is not None and observation.allocated_bytes is not None
                else 0
            )
        )
        current = (
            observed_bytes
            if allocation is None or allocation.phase in {"completed", "failed"}
            else allocation.desired_bytes
        )
        if requested_bytes <= current:
            raise PlatformResourceError("WORKSPACE_CAPACITY_EXPANSION_ONLY", 409)
        if allocation is None:
            allocation = db_models.WorkspaceStorageAllocation(
                workspace_id=workspace_id,
                storage_kind=normalized_kind,
                desired_bytes=requested_bytes,
                observed_bytes=current,
                revision=1,
                observed_revision=0,
                phase="pending",
            )
            self.db.add(allocation)
        else:
            allocation.desired_bytes = requested_bytes
            allocation.revision += 1
            allocation.phase = "pending"
            allocation.operator_error_code = None
        request = db_models.WorkspaceCapacityExpansionRequest(
            id=str(uuid4()),
            workspace_id=workspace_id,
            storage_kind=normalized_kind,
            previous_bytes=current,
            requested_bytes=requested_bytes,
            target_revision=allocation.revision,
            requested_by_user_id=actor.user_id,
            phase="pending",
            created_at=_utcnow(),
            updated_at=_utcnow(),
        )
        self.db.add(request)
        correlation_id = str(uuid4())
        self.audit_events.record(
            event_type="platform_resource.workspace_capacity_expansion_requested",
            actor_type="user",
            actor_id=actor.user_id,
            actor_user_id=actor.user_id,
            target_type="workspace",
            target_id=workspace_id,
            action="request_workspace_capacity_expansion",
            result="success",
            error_code=None,
            correlation_id=correlation_id,
            root_correlation_id=correlation_id,
            metadata={
                "workspace_id": workspace_id,
                "changed_fields": ["desired_bytes"],
                "target_revision": allocation.revision,
            },
        )
        self.db.commit()
        return self._expansion_response(request)

    def get_expansion(
        self, *, actor: AuthorizationActor, workspace_id: str, request_id: str
    ) -> WorkspaceCapacityExpansionResponse:
        self.authorization.require_platform_operation(
            actor, OperationId.PLATFORM_RESOURCES_READ
        )
        request = self.db.get(db_models.WorkspaceCapacityExpansionRequest, request_id)
        if request is None or request.workspace_id != workspace_id:
            raise PlatformResourceError("PLATFORM_RESOURCE_NOT_FOUND", 404)
        return self._expansion_response(request)

    def desired_storage_spec(
        self, workspace: db_models.Workspace
    ) -> WorkspaceStorageDesiredState:
        allocations = {
            allocation.storage_kind: allocation
            for allocation in self.db.scalars(
                select(db_models.WorkspaceStorageAllocation).where(
                    db_models.WorkspaceStorageAllocation.workspace_id == workspace.id
                )
            ).all()
            if allocation.storage_kind in WORKSPACE_STORAGE_KINDS
        }
        defaults = {
            "workspace_data": self.settings.WORKSPACE_STORAGE_SIZE,
            "runtime_home": self.settings.RUNTIME_HOME_STORAGE_SIZE,
        }
        for storage_kind in WORKSPACE_STORAGE_KINDS:
            if storage_kind in allocations:
                continue
            allocation = db_models.WorkspaceStorageAllocation(
                workspace_id=workspace.id,
                storage_kind=storage_kind,
                desired_bytes=self._quantity_bytes(defaults[storage_kind]),
                observed_bytes=None,
                revision=1,
                observed_revision=0,
                phase="pending",
            )
            self.db.add(allocation)
            allocations[storage_kind] = allocation
        self.db.flush()
        return WorkspaceStorageDesiredState(
            workspace_data=StorageDesired(
                storage_kind="workspace_data",
                capacity_bytes=allocations["workspace_data"].desired_bytes,
                revision=allocations["workspace_data"].revision,
            ),
            runtime_home=StorageDesired(
                storage_kind="runtime_home",
                capacity_bytes=allocations["runtime_home"].desired_bytes,
                revision=allocations["runtime_home"].revision,
            ),
        )

    def deliver_reconciling(self, deliver: StorageDelivery) -> int:
        workspace_ids = self.db.scalars(
            select(db_models.WorkspaceStorageAllocation.workspace_id)
            .where(
                db_models.WorkspaceStorageAllocation.phase.in_(("pending", "applying"))
            )
            .distinct()
            .order_by(db_models.WorkspaceStorageAllocation.workspace_id)
        ).all()
        self.db.commit()
        delivered = 0
        for workspace_id in workspace_ids:
            try:
                self._lock_workspace(workspace_id)
                workspace = self.db.get(
                    db_models.Workspace,
                    workspace_id,
                    populate_existing=True,
                    with_for_update=True,
                )
                workspace_allocations = self.db.scalars(
                    select(db_models.WorkspaceStorageAllocation)
                    .where(
                        db_models.WorkspaceStorageAllocation.workspace_id
                        == workspace_id,
                        db_models.WorkspaceStorageAllocation.phase.in_(
                            ("pending", "applying")
                        ),
                    )
                    .with_for_update()
                ).all()
                if not workspace_allocations:
                    self.db.commit()
                    continue
                if workspace is None or workspace.provisioner != "kubernetes":
                    for allocation in workspace_allocations:
                        self._fail_allocation(
                            allocation, "WORKSPACE_CAPACITY_WORKSPACE_UNAVAILABLE"
                        )
                    self.db.commit()
                    continue
                desired_spec = self.desired_storage_spec(workspace)
                workspace_allocations = self.db.scalars(
                    select(db_models.WorkspaceStorageAllocation)
                    .where(
                        db_models.WorkspaceStorageAllocation.workspace_id
                        == workspace_id,
                        db_models.WorkspaceStorageAllocation.phase.in_(
                            ("pending", "applying")
                        ),
                    )
                    .with_for_update()
                ).all()
                try:
                    deliver(workspace, desired_spec)
                except Exception:
                    self.db.commit()
                    logger.exception(
                        "Workspace capacity desired state delivery failed",
                        extra={"workspace_id": workspace_id},
                    )
                    continue
                for allocation in workspace_allocations:
                    allocation.phase = "applying"
                    request = self._active_request(
                        allocation.workspace_id,
                        cast(WorkspaceStorageKind, allocation.storage_kind),
                    )
                    if (
                        request is not None
                        and request.target_revision == allocation.revision
                    ):
                        request.phase = "applying"
                        request.updated_at = _utcnow()
                    delivered += 1
                self.db.commit()
            except Exception:
                self.db.rollback()
                raise
        return delivered

    def reconcile_operator_observation(
        self, *, workspace_id: str, observation: WorkspaceStorageObservation
    ) -> bool:
        self._lock_workspace(workspace_id)
        changed = False
        for item in observation.items:
            allocation = self._allocation(
                workspace_id, item.storage_kind, with_for_update=True
            )
            if allocation is None:
                continue
            if item.observed_revision != allocation.revision:
                continue
            if allocation.phase in {"completed", "failed"}:
                terminal_observed_bytes = max(
                    allocation.observed_bytes or 0,
                    item.allocated_bytes,
                )
                terminal_observation_changed = (
                    allocation.observed_bytes != terminal_observed_bytes
                    or allocation.expansion_supported != item.expansion_supported
                )
                allocation.observed_revision = item.observed_revision
                allocation.observed_bytes = terminal_observed_bytes
                allocation.expansion_supported = item.expansion_supported
                changed = changed or terminal_observation_changed
                continue
            stable_error = item.error_code
            phase = (
                "failed"
                if stable_error is not None
                else (
                    "completed"
                    if item.allocated_bytes >= allocation.desired_bytes
                    else "applying"
                )
            )
            allocation.observed_revision = item.observed_revision
            allocation.observed_bytes = item.allocated_bytes
            allocation.expansion_supported = item.expansion_supported
            allocation.phase = phase
            allocation.operator_error_code = stable_error
            request = self._active_request(workspace_id, item.storage_kind)
            if (
                request is not None
                and request.target_revision == item.observed_revision
            ):
                request.phase = phase
                request.error_code = allocation.operator_error_code
                request.updated_at = _utcnow()
            changed = True
        return changed

    def _allocation(
        self,
        workspace_id: str,
        storage_kind: WorkspaceStorageKind,
        *,
        with_for_update: bool = False,
    ) -> db_models.WorkspaceStorageAllocation | None:
        statement = select(db_models.WorkspaceStorageAllocation).where(
            db_models.WorkspaceStorageAllocation.workspace_id == workspace_id,
            db_models.WorkspaceStorageAllocation.storage_kind == storage_kind,
        )
        if with_for_update:
            statement = statement.with_for_update()
        return self.db.scalar(statement)

    def _lock_workspace(self, workspace_id: str) -> None:
        from app.modules.workspace.advisory_lock import (
            acquire_workspace_transaction_lock,
        )

        acquire_workspace_transaction_lock(self.db, workspace_id)

    def _active_request(
        self, workspace_id: str, storage_kind: WorkspaceStorageKind
    ) -> db_models.WorkspaceCapacityExpansionRequest | None:
        return self.db.scalar(
            select(db_models.WorkspaceCapacityExpansionRequest)
            .where(
                db_models.WorkspaceCapacityExpansionRequest.workspace_id
                == workspace_id,
                db_models.WorkspaceCapacityExpansionRequest.storage_kind
                == storage_kind,
                db_models.WorkspaceCapacityExpansionRequest.phase.in_(
                    ("pending", "applying")
                ),
            )
            .order_by(db_models.WorkspaceCapacityExpansionRequest.created_at.desc())
        )

    def _fail_allocation(
        self, allocation: db_models.WorkspaceStorageAllocation, error_code: str
    ) -> None:
        allocation.phase = "failed"
        allocation.operator_error_code = error_code
        request = self._active_request(
            allocation.workspace_id,
            cast(WorkspaceStorageKind, allocation.storage_kind),
        )
        if request is not None and request.target_revision == allocation.revision:
            request.phase = "failed"
            request.error_code = error_code
            request.updated_at = _utcnow()

    def _quota_response(
        self, knowledge_base: db_models.KnowledgeBase
    ) -> KnowledgeBaseQuotaResponse:
        custom = knowledge_base.quota_bytes is not None
        return KnowledgeBaseQuotaResponse(
            knowledgeBaseId=knowledge_base.id,
            currentSizeBytes=knowledge_base.current_size_bytes or 0,
            quotaBytes=knowledge_base.quota_bytes,
            effectiveQuotaBytes=(
                knowledge_base.quota_bytes
                if knowledge_base.quota_bytes is not None
                else self.settings.DEFAULT_KB_QUOTA_BYTES
            ),
            quotaSource="custom" if custom else "platform_default",
        )

    @staticmethod
    def _expansion_response(
        request: db_models.WorkspaceCapacityExpansionRequest,
    ) -> WorkspaceCapacityExpansionResponse:
        return WorkspaceCapacityExpansionResponse(
            requestId=request.id,
            workspaceId=request.workspace_id,
            storageKind=cast(WorkspaceStorageKind, request.storage_kind),
            previousBytes=request.previous_bytes,
            requestedBytes=request.requested_bytes,
            phase=cast(
                Literal["pending", "applying", "completed", "failed"],
                request.phase,
            ),
            errorCode=request.error_code,
            createdAt=request.created_at,
            updatedAt=request.updated_at,
        )

    @staticmethod
    def _quantity_bytes(quantity: str) -> int:
        try:
            parsed = parse_quantity(quantity)
        except (TypeError, ValueError) as exc:
            raise ValueError("Workspace storage quantity is invalid") from exc
        if parsed <= 0 or parsed != parsed.to_integral_value():
            raise ValueError(
                "Workspace storage quantity must resolve to positive bytes"
            )
        return int(parsed)
