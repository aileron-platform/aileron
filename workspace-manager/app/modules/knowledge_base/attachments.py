"""Knowledge base attachment transactions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.modules.knowledge_base.mount_contract import validate_mount_alias
from app.db import models as db_models
from app.modules.workspace.runtime.job_repository import (
    WorkspaceRuntimeJobRepository,
)
from app.modules.audit.events import AuditEventService
from app.modules.knowledge_base.mount_snapshot import (
    KnowledgeBaseMountSnapshotEntry,
    canonical_mount_snapshot,
)
from app.modules.knowledge_base.access import (
    KnowledgeBaseConflictError,
    KnowledgeBaseNotFoundError,
    KnowledgeBaseService,
)
from app.modules.knowledge_base.access_repository import KnowledgeBaseAccessResolver
from app.modules.authorization.actor import AuthorizationActor, actor_from_valid_user
from app.modules.identity.platform_role import PlatformRole
from app.modules.identity.user_authorization_policy import UserAuthorizationPolicy
from app.modules.authorization.operation_policy import (
    AuthorizationOperationPolicy,
    OperationId,
)
from app.modules.authorization.resource_access import (
    ResourceAccessRole,
    role_satisfies,
)
from app.modules.workspace.advisory_lock import (
    acquire_workspace_transaction_lock,
)
from app.modules.workspace.access_repository import WorkspaceAccessResolver

KB_ATTACHMENT_NOT_FOUND_MESSAGE = "Knowledge base attachment does not exist"
KB_ALREADY_ATTACHED_MESSAGE = "Knowledge base already attached to this workspace"
KB_MOUNT_ALIAS_CONFLICT_MESSAGE = "Knowledge base mount alias already exists"
WORKSPACE_NOT_FOUND_MESSAGE = "Workspace does not exist"
WORKSPACE_MUTATION_BLOCKED_MESSAGE = "Workspace lifecycle blocks mount changes"

_BLOCKED_MUTATION_STATES = {"stopping", "deleting"}


@dataclass(frozen=True)
class AttachmentMutationProjection:
    """Pending mutation projection returned before candidate promotion."""

    id: str
    kb_id: str
    name: str
    slug: str
    mount_alias: str
    status: str
    attached_by_id: str | None
    workspace_id: str | None = None
    workspace_name: str | None = None


@dataclass(frozen=True)
class AttachmentMutationResult:
    """Committed attachment mutation and its durable intent."""

    attachment: AttachmentMutationProjection
    workspace: db_models.Workspace
    job: db_models.WorkspaceRuntimeJob


@dataclass(frozen=True)
class KnowledgeBaseAttachmentUsage:
    """Workspace-visibility-filtered knowledge base usage."""

    visible_attachments: list[
        db_models.WorkspaceKnowledgeBaseAttachment | AttachmentMutationProjection
    ]
    hidden_workspace_count: int
    attachment_count: int


class KnowledgeBaseAttachmentService:
    """Own attachment authorization, locks, audit, revision, job, and commit."""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.kb_service = KnowledgeBaseService(db)
        self.workspace_access = WorkspaceAccessResolver(db)
        self.knowledge_base_access = KnowledgeBaseAccessResolver(db)
        self.authorization = AuthorizationOperationPolicy(db)
        self.audit_events = AuditEventService(db)
        self.runtime_jobs = WorkspaceRuntimeJobRepository(db)

    def list_attachments_for_workspace(
        self,
        *,
        actor: AuthorizationActor,
        workspace_id: str,
    ) -> list[
        db_models.WorkspaceKnowledgeBaseAttachment | AttachmentMutationProjection
    ]:
        self.authorization.require_workspace_operation(
            actor,
            workspace_id,
            OperationId.WORKSPACE_DETAIL_READ,
        )
        workspace = self.db.get(db_models.Workspace, workspace_id)
        if workspace is None:
            raise KnowledgeBaseNotFoundError(
                WORKSPACE_NOT_FOUND_MESSAGE,
                code="WORKSPACE_NOT_FOUND",
            )
        active = list(
            self.db.scalars(
                select(db_models.WorkspaceKnowledgeBaseAttachment)
                .options(
                    selectinload(
                        db_models.WorkspaceKnowledgeBaseAttachment.knowledge_base
                    )
                )
                .where(
                    db_models.WorkspaceKnowledgeBaseAttachment.workspace_id
                    == workspace.id
                )
                .order_by(db_models.WorkspaceKnowledgeBaseAttachment.id)
            ).all()
        )
        return self._project_workspace_attachments(
            workspace=workspace,
            active=active,
        )

    def revoke_knowledge_base_mounts(
        self,
        *,
        actor_user_id: str,
        kb: db_models.KnowledgeBase,
        correlation_id: str,
    ) -> int:
        """Stage removal from every mounted consumer in the caller transaction."""
        workspaces = list(
            self.db.scalars(
                select(db_models.Workspace).order_by(db_models.Workspace.id)
            ).all()
        )
        affected = 0
        for candidate_workspace in workspaces:
            base_snapshot = self._candidate_base(candidate_workspace)
            removed = [
                entry
                for entry in base_snapshot
                if entry["knowledgeBaseId"] == kb.id
                and not self._mount_principal_can_keep_private(
                    kb_id=kb.id,
                    user_id=entry.get("attachedById"),
                )
            ]
            if not removed:
                continue
            workspace = self._lock_workspace(candidate_workspace.id)
            self._require_mutable_lifecycle(workspace)
            base_snapshot = self._candidate_base(workspace)
            removed_ids = {entry["attachmentId"] for entry in removed}
            candidate = [
                entry
                for entry in base_snapshot
                if entry["attachmentId"] not in removed_ids
            ]
            target_revision = self._stage_candidate(workspace, candidate)
            first = removed[0]
            projection = AttachmentMutationProjection(
                id=first["attachmentId"],
                kb_id=kb.id,
                name=kb.name,
                slug=kb.slug,
                mount_alias=first["mountAlias"],
                status="pending_removal",
                attached_by_id=first.get("attachedById"),
            )
            self._record_mutation(
                actor_user_id=actor_user_id,
                workspace=workspace,
                attachment=projection,
                kb_id=kb.id,
                correlation_id=correlation_id,
                target_revision=target_revision,
                event_type="knowledge_base.public_mounts_revoked",
                action="revoke_public_mounts",
                job_metadata={
                    "knowledge_base_id": kb.id,
                    "attachment_ids": [entry["attachmentId"] for entry in removed],
                    "mutation_action": "visibility_private",
                },
            )
            affected += 1
        return affected

    def _mount_principal_can_keep_private(
        self,
        *,
        kb_id: str,
        user_id: str | None,
    ) -> bool:
        if not user_id:
            return False
        user = self.db.get(db_models.User, user_id)
        if user is not None and UserAuthorizationPolicy().is_authorized(user):
            try:
                if actor_from_valid_user(user).platform_role is PlatformRole.ADMIN:
                    return True
            except ValueError:
                return False
        access = self.knowledge_base_access.resolve(
            knowledge_base_id=kb_id,
            user_id=user_id,
        )
        return bool(
            access is not None
            and any(source.value != "public" for source in access.access_sources)
            and role_satisfies(access.access_role, ResourceAccessRole.READER)
        )

    def list_attachments_for_kb(
        self,
        *,
        actor: AuthorizationActor,
        kb_id: str,
    ) -> KnowledgeBaseAttachmentUsage:
        kb, _ = self.kb_service.get_kb_for_operation(
            actor=actor,
            kb_id=kb_id,
            operation=OperationId.KNOWLEDGE_BASE_SETTINGS_MANAGE,
        )
        active_attachments = list(
            self.db.scalars(
                select(db_models.WorkspaceKnowledgeBaseAttachment)
                .options(
                    selectinload(db_models.WorkspaceKnowledgeBaseAttachment.workspace)
                )
                .where(db_models.WorkspaceKnowledgeBaseAttachment.kb_id == kb.id)
                .order_by(db_models.WorkspaceKnowledgeBaseAttachment.id)
            ).all()
        )
        candidate_workspaces = list(
            self.db.scalars(
                select(db_models.Workspace).where(
                    db_models.Workspace.knowledge_base_mount_sync_status.in_(
                        {"preflighting", "applying"}
                    ),
                    db_models.Workspace.knowledge_base_mount_candidate_snapshot.is_not(
                        None
                    ),
                )
            ).all()
        )
        active_workspace_ids = {
            attachment.workspace_id for attachment in active_attachments
        }
        candidate_workspace_ids = {
            workspace.id
            for workspace in candidate_workspaces
            if any(
                entry["knowledgeBaseId"] == kb.id
                for entry in canonical_mount_snapshot(
                    workspace.knowledge_base_mount_candidate_snapshot
                )
            )
        }
        workspace_ids = active_workspace_ids | candidate_workspace_ids
        workspaces = (
            list(
                self.db.scalars(
                    select(db_models.Workspace)
                    .options(
                        selectinload(
                            db_models.Workspace.knowledge_base_attachments
                        ).selectinload(
                            db_models.WorkspaceKnowledgeBaseAttachment.knowledge_base
                        )
                    )
                    .where(db_models.Workspace.id.in_(workspace_ids))
                    .order_by(db_models.Workspace.id)
                ).all()
            )
            if workspace_ids
            else []
        )
        visible: list[
            db_models.WorkspaceKnowledgeBaseAttachment | AttachmentMutationProjection
        ] = []
        hidden_workspace_count = 0
        attachment_count = 0
        for workspace in workspaces:
            projections = [
                attachment
                for attachment in self._project_workspace_attachments(
                    workspace=workspace,
                    active=list(workspace.knowledge_base_attachments),
                )
                if attachment.kb_id == kb.id
            ]
            if not projections:
                continue
            attachment_count += len(projections)
            context = self.workspace_access.resolve(
                workspace=workspace,
                user_id=actor.user_id,
            )
            if context is None:
                hidden_workspace_count += len(projections)
            else:
                visible.extend(projections)
        return KnowledgeBaseAttachmentUsage(
            visible_attachments=visible,
            hidden_workspace_count=hidden_workspace_count,
            attachment_count=attachment_count,
        )

    def _project_workspace_attachments(
        self,
        *,
        workspace: db_models.Workspace,
        active: list[db_models.WorkspaceKnowledgeBaseAttachment],
    ) -> list[
        db_models.WorkspaceKnowledgeBaseAttachment | AttachmentMutationProjection
    ]:
        if (
            workspace.knowledge_base_mount_sync_status
            not in {"preflighting", "applying"}
            or workspace.knowledge_base_mount_candidate_snapshot is None
        ):
            return active

        candidate = canonical_mount_snapshot(
            workspace.knowledge_base_mount_candidate_snapshot
        )
        active_by_id = {attachment.id: attachment for attachment in active}
        candidate_by_id = {str(entry["attachmentId"]): entry for entry in candidate}
        knowledge_base_ids = {str(entry["knowledgeBaseId"]) for entry in candidate}
        knowledge_bases = {
            knowledge_base.id: knowledge_base
            for knowledge_base in self.db.scalars(
                select(db_models.KnowledgeBase).where(
                    db_models.KnowledgeBase.id.in_(knowledge_base_ids)
                )
            ).all()
        }
        projections: list[
            db_models.WorkspaceKnowledgeBaseAttachment | AttachmentMutationProjection
        ] = []
        for attachment_id in sorted(active_by_id.keys() | candidate_by_id.keys()):
            active_attachment = active_by_id.get(attachment_id)
            entry = candidate_by_id.get(attachment_id)
            if entry is None:
                if active_attachment is None:
                    continue
                projections.append(
                    AttachmentMutationProjection(
                        id=active_attachment.id,
                        kb_id=active_attachment.kb_id,
                        name=active_attachment.knowledge_base.name,
                        slug=active_attachment.knowledge_base.slug,
                        mount_alias=active_attachment.mount_alias,
                        status="pending_removal",
                        attached_by_id=active_attachment.attached_by_id,
                        workspace_id=workspace.id,
                        workspace_name=workspace.name,
                    )
                )
                continue

            kb_id = str(entry["knowledgeBaseId"])
            mount_alias = str(entry["mountAlias"])
            if (
                active_attachment is not None
                and active_attachment.kb_id == kb_id
                and active_attachment.mount_alias == mount_alias
                and active_attachment.attached_by_id == entry.get("attachedById")
            ):
                projections.append(active_attachment)
                continue
            knowledge_base = knowledge_bases.get(kb_id)
            if knowledge_base is None:
                raise KnowledgeBaseNotFoundError(
                    "Knowledge base does not exist",
                    code="KB_NOT_FOUND",
                )
            projections.append(
                AttachmentMutationProjection(
                    id=attachment_id,
                    kb_id=kb_id,
                    name=knowledge_base.name,
                    slug=knowledge_base.slug,
                    mount_alias=mount_alias,
                    status="pending",
                    attached_by_id=(
                        str(entry["attachedById"])
                        if entry.get("attachedById") is not None
                        else None
                    ),
                    workspace_id=workspace.id,
                    workspace_name=workspace.name,
                )
            )
        return projections

    def attach(
        self,
        *,
        actor: AuthorizationActor,
        workspace_id: str,
        kb_id: str,
        mount_alias: str,
        correlation_id: str | None = None,
    ) -> AttachmentMutationResult:
        correlation_id = correlation_id or str(uuid4())
        try:
            self.authorization.require_knowledge_base_mount(
                actor,
                workspace_id,
                kb_id,
            )
            kb = self._lock_knowledge_base(kb_id)
            workspace = self._lock_workspace(workspace_id)
            self._require_mutable_lifecycle(workspace)
            candidate = self._candidate_base(workspace)
            duplicate = next(
                (entry for entry in candidate if entry["knowledgeBaseId"] == kb.id),
                None,
            )
            if duplicate is not None:
                raise KnowledgeBaseConflictError(
                    KB_ALREADY_ATTACHED_MESSAGE,
                    code="KB_ALREADY_ATTACHED",
                )

            alias = validate_mount_alias(mount_alias)
            self._require_unused_alias(candidate, alias=alias)
            attachment_id = str(uuid4())
            candidate.append(
                {
                    "attachmentId": attachment_id,
                    "knowledgeBaseId": kb.id,
                    "mountAlias": alias,
                    "attachedById": actor.user_id,
                }
            )
            target_revision = self._stage_candidate(workspace, candidate)
            attachment = AttachmentMutationProjection(
                id=attachment_id,
                kb_id=kb.id,
                name=kb.name,
                slug=kb.slug,
                mount_alias=alias,
                status="pending",
                attached_by_id=actor.user_id,
            )
            job = self._record_mutation(
                actor_user_id=actor.user_id,
                workspace=workspace,
                attachment=attachment,
                kb_id=kb.id,
                correlation_id=correlation_id,
                target_revision=target_revision,
                event_type="workspace.knowledge_base_attached",
                action="attach",
                job_metadata={
                    "attachment_id": attachment.id,
                    "knowledge_base_id": kb.id,
                    "mutation_action": "attach",
                },
            )
            self.db.commit()
            self.db.refresh(workspace)
            return AttachmentMutationResult(attachment, workspace, job)
        except IntegrityError as exc:
            self.db.rollback()
            raise self._translate_integrity_error(exc) from exc
        except Exception:
            self.db.rollback()
            raise

    def update_attachment(
        self,
        *,
        actor: AuthorizationActor,
        workspace_id: str,
        attachment_id: str,
        mount_alias: str,
        correlation_id: str | None = None,
    ) -> AttachmentMutationResult:
        correlation_id = correlation_id or str(uuid4())
        try:
            self.authorization.require_workspace_operation(
                actor,
                workspace_id,
                OperationId.WORKSPACE_ATTACHMENT_WRITE,
            )
            workspace = self._lock_workspace(workspace_id)
            self._require_mutable_lifecycle(workspace)
            candidate = self._candidate_base(workspace)
            entry = self._snapshot_entry(
                candidate,
                attachment_id=attachment_id,
            )
            kb_id = entry["knowledgeBaseId"]
            kb = self._lock_knowledge_base(kb_id)
            alias = validate_mount_alias(mount_alias)
            self._require_unused_alias(
                candidate,
                alias=alias,
                exclude_attachment_id=attachment_id,
            )
            entry["mountAlias"] = alias
            target_revision = self._stage_candidate(workspace, candidate)
            projection = AttachmentMutationProjection(
                id=attachment_id,
                kb_id=kb.id,
                name=kb.name,
                slug=kb.slug,
                mount_alias=alias,
                status="pending",
                attached_by_id=entry.get("attachedById"),
            )
            job = self._record_mutation(
                actor_user_id=actor.user_id,
                workspace=workspace,
                attachment=projection,
                kb_id=kb_id,
                correlation_id=correlation_id,
                target_revision=target_revision,
                event_type="workspace.knowledge_base_alias_updated",
                action="update_alias",
                job_metadata={
                    "attachment_id": attachment_id,
                    "knowledge_base_id": kb_id,
                    "mutation_action": "update_alias",
                },
            )
            self.db.commit()
            self.db.refresh(workspace)
            return AttachmentMutationResult(projection, workspace, job)
        except IntegrityError as exc:
            self.db.rollback()
            raise self._translate_integrity_error(exc) from exc
        except Exception:
            self.db.rollback()
            raise

    def detach(
        self,
        *,
        actor: AuthorizationActor,
        workspace_id: str,
        attachment_id: str,
        correlation_id: str | None = None,
    ) -> AttachmentMutationResult:
        correlation_id = correlation_id or str(uuid4())
        try:
            self.authorization.require_workspace_operation(
                actor,
                workspace_id,
                OperationId.WORKSPACE_ATTACHMENT_WRITE,
            )
            workspace = self._lock_workspace(workspace_id)
            self._require_mutable_lifecycle(workspace)
            base_snapshot = self._candidate_base(workspace)
            entry = self._snapshot_entry(
                base_snapshot,
                attachment_id=attachment_id,
            )
            kb_id = entry["knowledgeBaseId"]
            kb = self._lock_knowledge_base(kb_id)
            offline_promotion = (
                workspace.runtime_status == "stopped"
                and workspace.runtime_instance_id is None
                and workspace.knowledge_base_mount_observed_revision
                == workspace.knowledge_base_mount_active_revision
            )
            candidate = [
                candidate_entry
                for candidate_entry in base_snapshot
                if candidate_entry["attachmentId"] != attachment_id
            ]
            target_revision = self._stage_candidate(workspace, candidate)
            job_metadata: dict[str, object] = {
                "attachment_id": attachment_id,
                "knowledge_base_id": kb_id,
                "mutation_action": "detach",
            }
            if offline_promotion:
                job_metadata["offline_promotion"] = True
            projection = AttachmentMutationProjection(
                id=attachment_id,
                kb_id=kb.id,
                name=kb.name,
                slug=kb.slug,
                mount_alias=entry["mountAlias"],
                status="pending_removal",
                attached_by_id=entry.get("attachedById"),
            )
            job = self._record_mutation(
                actor_user_id=actor.user_id,
                workspace=workspace,
                attachment=projection,
                kb_id=kb_id,
                correlation_id=correlation_id,
                target_revision=target_revision,
                event_type="workspace.knowledge_base_detach_requested",
                action="detach",
                job_metadata=job_metadata,
            )
            self.db.commit()
            self.db.refresh(workspace)
            return AttachmentMutationResult(projection, workspace, job)
        except IntegrityError as exc:
            self.db.rollback()
            raise self._translate_integrity_error(exc) from exc
        except Exception:
            self.db.rollback()
            raise

    def _record_mutation(
        self,
        *,
        actor_user_id: str,
        workspace: db_models.Workspace,
        attachment: AttachmentMutationProjection,
        kb_id: str,
        correlation_id: str,
        target_revision: int,
        event_type: str,
        action: str,
        job_metadata: dict[str, object],
    ) -> db_models.WorkspaceRuntimeJob:
        scheduled_at = datetime.utcnow()
        job, superseded_jobs = (
            self.runtime_jobs.supersede_queued_and_enqueue_mount_reconcile(
                workspace=workspace,
                correlation_id=correlation_id,
                scheduled_at=scheduled_at,
                job_metadata={
                    **job_metadata,
                    "mount_action": "apply_candidate",
                },
            )
        )
        for superseded_job in superseded_jobs:
            self.audit_events.record(
                event_type="runtime.mount_sync_superseded",
                actor_type="user",
                actor_id=actor_user_id,
                actor_user_id=actor_user_id,
                target_type="workspace",
                target_id=workspace.id,
                action="supersede_mount_sync",
                result="success",
                error_code=None,
                correlation_id=superseded_job.correlation_id,
                root_correlation_id=superseded_job.root_correlation_id,
                metadata={
                    "workspace_id": workspace.id,
                    "target_revision": superseded_job.target_revision or 0,
                    "reason": "newer_mutation",
                },
            )
        self.audit_events.record(
            event_type=event_type,
            actor_type="user",
            actor_id=actor_user_id,
            actor_user_id=actor_user_id,
            target_type="knowledge_base_attachment",
            target_id=attachment.id,
            action=action,
            result="success",
            error_code=None,
            correlation_id=correlation_id,
            root_correlation_id=correlation_id,
            metadata={
                "workspace_id": workspace.id,
                "kb_id": kb_id,
                "target_revision": target_revision,
            },
        )
        return job

    def _lock_knowledge_base(
        self,
        kb_id: str,
    ) -> db_models.KnowledgeBase:
        conditions = [db_models.KnowledgeBase.id == kb_id]
        kb = self.db.scalar(
            select(db_models.KnowledgeBase).where(*conditions).with_for_update()
        )
        if kb is None:
            raise KnowledgeBaseNotFoundError(
                "Knowledge base does not exist",
                code="KB_NOT_FOUND",
            )
        return kb

    def _lock_workspace(self, workspace_id: str) -> db_models.Workspace:
        acquire_workspace_transaction_lock(self.db, workspace_id)
        workspace = self.db.scalar(
            select(db_models.Workspace)
            .where(db_models.Workspace.id == workspace_id)
            .with_for_update()
        )
        if workspace is None:
            raise KnowledgeBaseNotFoundError(
                WORKSPACE_NOT_FOUND_MESSAGE,
                code="WORKSPACE_NOT_FOUND",
            )
        return workspace

    @staticmethod
    def _require_mutable_lifecycle(workspace: db_models.Workspace) -> None:
        if (
            workspace.runtime_status in _BLOCKED_MUTATION_STATES
            or workspace.knowledge_base_mount_sync_status == "compensating"
        ):
            raise KnowledgeBaseConflictError(
                WORKSPACE_MUTATION_BLOCKED_MESSAGE,
                code="WORKSPACE_KB_MOUNT_SYNC_IN_PROGRESS",
            )

    @staticmethod
    def _candidate_base(
        workspace: db_models.Workspace,
    ) -> list[KnowledgeBaseMountSnapshotEntry]:
        source = (
            workspace.knowledge_base_mount_candidate_snapshot
            if workspace.knowledge_base_mount_sync_status
            in {"preflighting", "applying"}
            and workspace.knowledge_base_mount_candidate_snapshot is not None
            else workspace.knowledge_base_mount_active_snapshot
        )
        return canonical_mount_snapshot(source)

    @staticmethod
    def _stage_candidate(
        workspace: db_models.Workspace,
        candidate: list[KnowledgeBaseMountSnapshotEntry],
    ) -> int:
        canonical_candidate = canonical_mount_snapshot(candidate)
        workspace.knowledge_base_mount_desired_revision += 1
        workspace.knowledge_base_mount_candidate_snapshot = canonical_candidate
        workspace.knowledge_base_mount_failed_snapshot = None
        workspace.knowledge_base_mount_sync_status = "preflighting"
        workspace.knowledge_base_mount_error_code = None
        return workspace.knowledge_base_mount_desired_revision

    @staticmethod
    def _snapshot_entry(
        snapshot: list[KnowledgeBaseMountSnapshotEntry],
        *,
        attachment_id: str,
    ) -> KnowledgeBaseMountSnapshotEntry:
        entry = next(
            (
                candidate
                for candidate in snapshot
                if candidate["attachmentId"] == attachment_id
            ),
            None,
        )
        if entry is None:
            raise KnowledgeBaseNotFoundError(
                KB_ATTACHMENT_NOT_FOUND_MESSAGE,
                code="KB_ATTACHMENT_NOT_FOUND",
            )
        return entry

    @staticmethod
    def _require_unused_alias(
        snapshot: list[KnowledgeBaseMountSnapshotEntry],
        *,
        alias: str,
        exclude_attachment_id: str | None = None,
    ) -> None:
        if any(
            entry["mountAlias"] == alias
            and entry["attachmentId"] != exclude_attachment_id
            for entry in snapshot
        ):
            raise KnowledgeBaseConflictError(
                KB_MOUNT_ALIAS_CONFLICT_MESSAGE,
                code="KB_MOUNT_ALIAS_CONFLICT",
            )

    @staticmethod
    def _translate_integrity_error(exc: IntegrityError) -> KnowledgeBaseConflictError:
        detail = str(exc.orig)
        if (
            "workspace_kb_attachments_workspace_kb_unique" in detail
            or "workspace_id, kb_id" in detail
        ):
            return KnowledgeBaseConflictError(
                KB_ALREADY_ATTACHED_MESSAGE,
                code="KB_ALREADY_ATTACHED",
            )
        if (
            "workspace_kb_attachments_workspace_alias_unique" in detail
            or "workspace_id, mount_alias" in detail
        ):
            return KnowledgeBaseConflictError(
                KB_MOUNT_ALIAS_CONFLICT_MESSAGE,
                code="KB_MOUNT_ALIAS_CONFLICT",
            )
        raise exc
