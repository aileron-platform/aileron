"""WorkspaceService"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional
from uuid import uuid4

import httpx
from sqlalchemy import func, or_, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, selectinload

from app.config.settings import get_settings
from app.db import models as db_models
from app.modules.authorization.operation_policy import (
    AuthorizationOperationPolicy,
    OperationId,
    allowed_workspace_operations,
)
from app.modules.authorization.actor import AuthorizationActor
from app.modules.authorization.resource_access import (
    ResourceAccessRole,
    ResourceAccessSource,
)
from app.modules.identity.user_authorization_policy import UserAuthorizationPolicy
from app.modules.workspace.access_repository import (
    WorkspaceAccessResolver,
    visible_workspace_ids,
)
from app.modules.workspace.firewall_contract import FirewallConfig
from app.modules.workspace.models import (
    Pagination,
    BrowserConnectivityStatus,
    RuntimeStatus,
    WorkspaceAccessSource,
    WorkspaceBootstrapStatus,
    WorkspaceComponents,
    WorkspaceComponentStatus,
    WorkspaceCreateRequest,
    WorkspaceReadDetail,
    WorkspaceKnowledgeBaseAttachment,
    WorkspaceListResponse,
    WorkspaceOwner,
    WorkspaceRuntimeJobSummary,
    WorkspaceSensitiveEnvVar,
    WorkspaceSensitiveSettings,
    WorkspaceSensitiveSettingsReplaceRequest,
    WorkspaceShare,
    WorkspaceShareCreateRequest,
    WorkspaceShareListResponse,
    WorkspaceShareUpdateRequest,
    WorkspaceShareUser,
    WorkspaceSummary,
    WorkspaceUpdateRequest,
)
from app.modules.workspace.public_urls import WorkspacePublicUrls
from app.modules.workspace.capabilities import (
    WorkspaceCapabilities,
    build_capabilities_from_settings,
)
from app.modules.settings.models import UserSettings
from app.modules.workspace.firewall_command_repository import (
    WorkspaceFirewallSyncCommandRepository,
)
from app.modules.workspace.runtime.job_repository import (
    RUNTIME_RESTART,
    WORKSPACE_START,
    WorkspaceRuntimeJobRepository,
)
from app.modules.audit.events import AuditEventService
from app.modules.workspace.browser_credentials import (
    BROWSER_CREDENTIAL_ALGORITHM,
    BrowserCredentialService,
)
from app.modules.workspace.advisory_lock import (
    acquire_workspace_transaction_lock,
)
from app.modules.workspace.runtime.command_auth import runtime_command_headers
from app.core.strings import snake_case

if TYPE_CHECKING:
    from app.modules.automation.repository import RunningCancellation

logger = logging.getLogger(__name__)

WORKSPACE_OWNER_NOT_FOUND_MESSAGE = "Workspace owner does not exist"
WORKSPACE_NOT_FOUND_MESSAGE = "Workspace does not exist"
WORKSPACE_ACCESS_DENIED_MESSAGE = "Insufficient workspace permissions"
WORKSPACE_SHARE_TARGET_NOT_FOUND_MESSAGE = "User to share with not found"
WORKSPACE_SHARE_OWNER_FORBIDDEN_MESSAGE = "Cannot share workspace with owner"
WORKSPACE_SHARE_CONFLICT_MESSAGE = "Workspace share already exists"


class WorkspaceError(ValueError):
    """Workspace related expected errors."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "WORKSPACE_INVALID_REQUEST",
        params: dict | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.params = params or {}


class WorkspaceNotFoundError(WorkspaceError):
    """Workspace or related resources do not exist."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "WORKSPACE_NOT_FOUND",
        params: dict | None = None,
    ) -> None:
        super().__init__(message, code=code, params=params)


class WorkspaceAccessDeniedError(PermissionError):
    """User does not have required permissions for workspace."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "WORKSPACE_ACCESS_DENIED",
        params: dict | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.params = params or {}


@dataclass(frozen=True)
class WorkspaceAuthorizationContext:
    """Read-only workspace authorization data for transaction-safe checks."""

    access_role: ResourceAccessRole
    access_source: WorkspaceAccessSource
    capabilities: WorkspaceCapabilities


class WorkspaceService:
    """Responsible for managing workspace data"""

    def __init__(self, db: Session) -> None:
        self.db = db
        self.settings = get_settings()
        self._access_resolver = WorkspaceAccessResolver(db)
        self.audit_events = AuditEventService(db)
        self.runtime_jobs = WorkspaceRuntimeJobRepository(db)
        self.firewall_commands = WorkspaceFirewallSyncCommandRepository(db)

    # -- DataQuery ---------------------------------------------------------

    def list(
        self,
        *,
        page: int,
        page_size: int,
        current_user_id: Optional[str] = None,
        owner_id: Optional[str] = None,
        status: Optional[str] = None,
        search: Optional[str] = None,
    ) -> WorkspaceListResponse:
        if current_user_id:
            query = select(db_models.Workspace).where(
                db_models.Workspace.id.in_(visible_workspace_ids(current_user_id))
            )
            if status:
                query = query.where(db_models.Workspace.runtime_status == status)
            if search:
                like_pattern = f"%{search}%"
                query = query.where(db_models.Workspace.name.ilike(like_pattern))

            total = (
                self.db.scalar(select(func.count()).select_from(query.subquery())) or 0
            )
            rows = self.db.scalars(
                query.order_by(db_models.Workspace.created_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            ).all()

            items = []
            for workspace in rows:
                access = self._access_resolver.resolve(
                    workspace=workspace,
                    user_id=current_user_id,
                )
                if access is None:
                    continue
                items.append(
                    self._to_summary(
                        workspace,
                        access_role=access.access_role,
                        access_source=access.access_source,
                        access_sources=access.access_sources,
                        current_user_id=current_user_id,
                    )
                )
        else:
            query = select(db_models.Workspace)

            if owner_id:
                query = query.where(db_models.Workspace.owner_id == owner_id)
            if status:
                query = query.where(db_models.Workspace.runtime_status == status)
            if search:
                like_pattern = f"%{search}%"
                query = query.where(db_models.Workspace.name.ilike(like_pattern))

            total = (
                self.db.scalar(select(func.count()).select_from(query.subquery())) or 0
            )

            records = (
                self.db.execute(
                    query.order_by(db_models.Workspace.created_at.desc())
                    .offset((page - 1) * page_size)
                    .limit(page_size)
                )
                .scalars()
                .all()
            )
            items = [
                self._to_summary(
                    workspace,
                    access_role=ResourceAccessRole.OWNER,
                    access_source="owned",
                    current_user_id=workspace.owner_id,
                )
                for workspace in records
            ]

        pagination = Pagination(page=page, page_size=page_size, total=total)
        return WorkspaceListResponse(items=items, pagination=pagination)

    def get(
        self,
        workspace_id: str,
        *,
        actor: AuthorizationActor,
    ) -> Optional[WorkspaceReadDetail]:
        workspace = self.db.get(db_models.Workspace, workspace_id)
        if not workspace:
            return None
        grant = AuthorizationOperationPolicy(self.db).require_workspace_operation(
            actor,
            workspace_id,
            OperationId.WORKSPACE_DETAIL_READ,
        )
        assert grant.access_role is not None
        return self._to_detail(
            workspace,
            access_role=grant.access_role,
            access_source=grant.access_source or ResourceAccessSource.DIRECT_SHARE,
            access_sources=grant.access_sources,
            current_user_id=actor.user_id,
        )

    def get_capabilities(
        self,
        workspace_id: str,
        *,
        actor: AuthorizationActor,
    ) -> Optional[WorkspaceCapabilities]:
        workspace = self.db.get(db_models.Workspace, workspace_id)
        if not workspace:
            return None
        AuthorizationOperationPolicy(self.db).require_workspace_operation(
            actor,
            workspace_id,
            OperationId.WORKSPACE_SENSITIVE_SETTINGS_MANAGE,
        )
        if workspace.agentic_capabilities is None:
            return build_capabilities_from_settings(UserSettings())
        return WorkspaceCapabilities.model_validate(workspace.agentic_capabilities)

    def get_sensitive_settings(
        self,
        workspace_id: str,
        *,
        actor: AuthorizationActor,
    ) -> WorkspaceSensitiveSettings | None:
        """Return only masked secrets after manager-level authorization."""

        workspace = self.db.get(db_models.Workspace, workspace_id)
        if workspace is None:
            return None
        AuthorizationOperationPolicy(self.db).require_workspace_operation(
            actor,
            workspace_id,
            OperationId.WORKSPACE_SENSITIVE_SETTINGS_MANAGE,
        )
        return self._to_sensitive_settings(workspace)

    def replace_sensitive_settings(
        self,
        workspace_id: str,
        payload: WorkspaceSensitiveSettingsReplaceRequest,
        *,
        actor: AuthorizationActor,
    ) -> WorkspaceSensitiveSettings | None:
        """Replace, clear, or retain sensitive settings without echoing values."""

        workspace = self.db.get(db_models.Workspace, workspace_id)
        if workspace is None:
            return None
        AuthorizationOperationPolicy(self.db).require_workspace_operation(
            actor,
            workspace_id,
            OperationId.WORKSPACE_SENSITIVE_SETTINGS_MANAGE,
        )

        fields = payload.model_fields_set
        if "setup_script" in fields:
            workspace.setup_script = payload.setup_script
        if "env_vars" in fields:
            workspace.env_vars = [
                item.model_dump() for item in (payload.env_vars or [])
            ]
        if "acp_cli_args" in fields:
            workspace.acp_cli_args = list(payload.acp_cli_args or [])
        if fields:
            workspace.bootstrap_revision += 1
            workspace.updated_at = datetime.utcnow()
            self.db.commit()
            self.db.refresh(workspace)
        return self._to_sensitive_settings(workspace)

    def get_authorization_context(
        self,
        workspace_id: str,
        *,
        current_user_id: str,
    ) -> Optional[WorkspaceAuthorizationContext]:
        """Read workspace authorization data without sync or transaction control."""
        workspace = self.db.get(db_models.Workspace, workspace_id)
        if workspace is None:
            return None
        access = self._access_resolver.resolve(
            workspace=workspace,
            user_id=current_user_id,
        )
        if access is None:
            return None
        capabilities = (
            build_capabilities_from_settings(UserSettings())
            if workspace.agentic_capabilities is None
            else WorkspaceCapabilities.model_validate(workspace.agentic_capabilities)
        )
        return WorkspaceAuthorizationContext(
            access_role=access.access_role,
            access_source=access.access_source,
            capabilities=capabilities,
        )

    def list_accessible_workspace_ids(self, *, current_user_id: str) -> list[str]:
        """Read all accessible workspace IDs without sync or transaction control."""
        return list(self.db.scalars(visible_workspace_ids(current_user_id)))

    def update_capabilities(
        self,
        workspace_id: str,
        capabilities: WorkspaceCapabilities,
        *,
        actor: AuthorizationActor,
    ) -> Optional[WorkspaceCapabilities]:
        try:
            workspace = self.db.get(db_models.Workspace, workspace_id)
            if not workspace:
                self.db.rollback()
                return None
            acquire_workspace_transaction_lock(self.db, workspace_id)
            workspace = self.db.scalar(
                select(db_models.Workspace)
                .where(db_models.Workspace.id == workspace_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
            if not workspace:
                self.db.rollback()
                return None
            AuthorizationOperationPolicy(self.db).require_workspace_operation(
                actor,
                workspace_id,
                OperationId.WORKSPACE_SENSITIVE_SETTINGS_MANAGE,
            )
            snapshot = capabilities.model_dump(by_alias=True)
            workspace.agentic_capabilities = snapshot
            workspace.updated_at = datetime.utcnow()
            result = WorkspaceCapabilities.model_validate(snapshot)
            self.db.commit()
            return result
        except Exception:
            self.db.rollback()
            raise

    # -- DataWrite ---------------------------------------------------------

    def create(
        self,
        payload: WorkspaceCreateRequest,
        *,
        correlation_id: str | None = None,
    ) -> WorkspaceReadDetail:
        owner = self.db.get(db_models.User, payload.owner_id)
        if not owner:
            raise WorkspaceError(
                WORKSPACE_OWNER_NOT_FOUND_MESSAGE, code="WORKSPACE_OWNER_NOT_FOUND"
            )

        provisioner = self._resolve_workspace_provisioner()
        if payload.firewall is not None:
            self._ensure_firewall_available(provisioner=provisioner)
        target_namespace = self._resolve_target_namespace(
            provisioner=provisioner,
        )
        initial_firewall = payload.firewall or self.settings.firewall_seed
        browser_credential_key_id = (
            BrowserCredentialService.from_settings().active_key_id
        )

        default_internal_port = 3002
        workspace = db_models.Workspace(
            id=str(uuid4()),
            owner_id=payload.owner_id,
            name=payload.name,
            description=payload.description,
            git_url=None,
            branch="main",
            runtime=payload.runtime,
            provisioner=provisioner,
            target_namespace=target_namespace,
            agentic_tools=payload.agentic_tools,
            setup_script=None,
            env_vars=[],
            workspace_firewall_egress_mode=initial_firewall.workspace.egress_mode,
            workspace_firewall_allowed_domains=(
                initial_firewall.workspace.allowed_domains
            ),
            browser_firewall_egress_mode=initial_firewall.browser.egress_mode,
            browser_firewall_allowed_domains=initial_firewall.browser.allowed_domains,
            firewall_revision=1,
            firewall_observed_revision=0,
            firewall_sync_status="pending",
            firewall_error_code=None,
            preferred_cli=payload.preferred_cli or "claude-code",
            fallback_enabled=(
                payload.fallback_enabled
                if payload.fallback_enabled is not None
                else True
            ),
            workspace_path=payload.workspace_path or "/workspace",
            worktree_subdir=payload.worktree_subdir or ".worktrees",
            acp_cli_args=[],
            bootstrap_revision=1,
            bootstrap_observed_revision=0,
            bootstrap_status="pending",
            runtime_desired_state="running",
            runtime_desired_revision=1,
            runtime_observed_revision=0,
            runtime_status="starting",
            browser_desired_state="running",
            browser_desired_revision=1,
            browser_observed_revision=0,
            browser_credential_revision=1,
            browser_credential_observed_revision=0,
            browser_credential_key_id=browser_credential_key_id,
            browser_credential_observed_key_id=None,
            browser_credential_algorithm=BROWSER_CREDENTIAL_ALGORITHM,
            browser_credential_observed_algorithm=None,
            browser_status="starting",
            browser_connectivity_state="pending",
            browser_connectivity_contract_version="browser-connectivity/v1",
            browser_connectivity_admission="denied",
            browser_connectivity_browser_generation=None,
            browser_connectivity_profile_revision=None,
            browser_connectivity_credential_revision=None,
            browser_connectivity_accepted_at=None,
            browser_connectivity_expires_at=None,
            browser_connectivity_reason="BrowserConnectivityPending",
            browser_connectivity_error_code=None,
            browser_connectivity_last_transition_at=None,
            browser_connectivity_backend_state="pending",
            browser_connectivity_backend_accepted_at=None,
            browser_connectivity_backend_expires_at=None,
            browser_connectivity_backend_reason=None,
            browser_connectivity_backend_error_code=None,
            browser_connectivity_frontend_state="pending",
            browser_connectivity_frontend_accepted_at=None,
            browser_connectivity_frontend_expires_at=None,
            browser_connectivity_frontend_reason=None,
            browser_connectivity_frontend_error_code=None,
            canvas_desired_state="running",
            canvas_desired_revision=1,
            canvas_observed_revision=0,
            canvas_status="starting",
            knowledge_base_mount_active_revision=0,
            knowledge_base_mount_desired_revision=0,
            knowledge_base_mount_observed_revision=0,
            knowledge_base_mount_sync_status="ready",
            knowledge_base_mount_error_code=None,
            knowledge_base_mount_active_snapshot=[],
            knowledge_base_mount_candidate_snapshot=None,
            knowledge_base_mount_failed_snapshot=None,
            runtime_access_revision=0,
            runtime_access_observed_revision=0,
            runtime_instance_id=None,
            runtime_internal_port=default_internal_port,
            runtime_last_seen=None,
        )

        command_correlation_id = correlation_id or str(uuid4())
        requested_at = datetime.now(timezone.utc)
        try:
            self.db.add(workspace)
            self.db.flush()
            self.firewall_commands.enqueue(
                workspace=workspace,
                scheduled_at=requested_at,
            )
            self.runtime_jobs.enqueue_lifecycle_job(
                workspace=workspace,
                operation=WORKSPACE_START,
                correlation_id=command_correlation_id,
                root_correlation_id=command_correlation_id,
                scheduled_at=requested_at,
                target_runtime_instance_id=None,
            )
            self.audit_events.record(
                event_type="workspace.lifecycle_start_requested",
                actor_type="user",
                actor_id=payload.owner_id,
                actor_user_id=payload.owner_id,
                target_type="workspace",
                target_id=workspace.id,
                action="start_workspace",
                result="success",
                error_code=None,
                correlation_id=command_correlation_id,
                root_correlation_id=command_correlation_id,
                metadata={"workspace_id": workspace.id},
            )
            self.db.commit()
            self.db.refresh(workspace)
        except Exception:
            self.db.rollback()
            raise

        return self._to_detail(
            workspace,
            access_role=ResourceAccessRole.OWNER,
            access_source="owned",
            current_user_id=workspace.owner_id,
        )

    def _resolve_workspace_provisioner(self) -> str:
        runtime_provisioner = self.settings.RUNTIME_PROVISIONER
        if runtime_provisioner == "kubernetes":
            return "kubernetes"
        return "docker"

    def update(
        self,
        workspace_id: str,
        payload: WorkspaceUpdateRequest,
        *,
        actor: AuthorizationActor,
        correlation_id: str | None = None,
    ) -> Optional[WorkspaceReadDetail]:
        workspace = self.db.get(db_models.Workspace, workspace_id)
        if workspace is None:
            return None
        acquire_workspace_transaction_lock(self.db, workspace_id)
        self.db.refresh(workspace, with_for_update=True)
        grant = AuthorizationOperationPolicy(self.db).require_workspace_operation(
            actor,
            workspace_id,
            OperationId.WORKSPACE_METADATA_WRITE,
        )
        assert grant.access_role is not None
        if workspace.runtime_status == "deleting":
            self.db.rollback()
            raise WorkspaceError(
                "Workspace lifecycle is busy",
                code="WORKSPACE_LIFECYCLE_BUSY",
            )

        previous_worktree_subdir = workspace.worktree_subdir
        data = payload.model_dump(exclude_unset=True, by_alias=True)
        kubernetes_runtime_fields = {
            "runtime",
            "agenticTools",
            "preferredCli",
            "fallbackEnabled",
            "workspacePath",
            "worktreeSubdir",
        }
        requires_kubernetes_restart = bool(
            workspace.provisioner == "kubernetes"
            and kubernetes_runtime_fields.intersection(data)
        )
        if requires_kubernetes_restart and workspace.runtime_status in {
            "starting",
            "stopping",
            "restarting",
            "deleting",
        }:
            self.db.rollback()
            raise WorkspaceError(
                "Workspace lifecycle is busy",
                code="WORKSPACE_LIFECYCLE_BUSY",
            )

        for attr, value in data.items():
            setattr(workspace, snake_case(attr), value)

        if requires_kubernetes_restart and workspace.runtime_status == "running":
            command_correlation_id = correlation_id or str(uuid4())
            active_job = self.runtime_jobs.find_active_component_job(
                workspace_id=workspace.id,
                component="runtime",
                for_update=True,
            )
            if active_job is None:
                workspace.runtime_desired_revision += 1
                enqueued = self.runtime_jobs.enqueue_component_job(
                    workspace=workspace,
                    operation=RUNTIME_RESTART,
                    correlation_id=command_correlation_id,
                    scheduled_at=datetime.now(timezone.utc),
                )
            if active_job is None and enqueued.created:
                workspace.runtime_status = "restarting"
                actor_user_id = actor.user_id
                self.audit_events.record(
                    event_type="workspace.component_restart_requested",
                    actor_type="user",
                    actor_id=actor_user_id,
                    actor_user_id=actor_user_id,
                    target_type="workspace",
                    target_id=workspace.id,
                    action="restart_workspace",
                    result="success",
                    error_code=None,
                    correlation_id=command_correlation_id,
                    root_correlation_id=command_correlation_id,
                    metadata={
                        "workspace_id": workspace.id,
                        "reason": "kubernetes_runtime_configuration_changed",
                    },
                )

        workspace.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(workspace)
        if (
            "worktreeSubdir" in data
            and workspace.worktree_subdir != previous_worktree_subdir
            and workspace.runtime_status == "running"
        ):
            self._push_worktree_gitignore_sync(
                workspace,
                subdir=workspace.worktree_subdir,
                previous=previous_worktree_subdir,
            )
        return self._to_detail(
            workspace,
            access_role=grant.access_role,
            access_source=grant.access_source or ResourceAccessSource.DIRECT_SHARE,
            access_sources=grant.access_sources,
            current_user_id=actor.user_id,
        )

    def list_share_candidate_users(
        self,
        *,
        actor: AuthorizationActor,
        workspace_id: str,
        query: str,
        limit: int,
    ) -> list[tuple[str, str]]:
        """Return a minimal projection of active, unshared Member candidates."""
        workspace = self._lock_workspace(workspace_id)
        AuthorizationOperationPolicy(self.db).require_workspace_operation(
            actor,
            workspace_id,
            OperationId.WORKSPACE_ACCESS_MANAGE,
        )
        shared_user_ids = select(db_models.WorkspaceShare.target_id).where(
            db_models.WorkspaceShare.workspace_id == workspace_id,
            db_models.WorkspaceShare.target_type == "user",
        )
        filters = [
            db_models.User.id != workspace.owner_id,
            db_models.User.id.not_in(shared_user_ids),
            db_models.User.platform_role == "member",
            db_models.User.role_status == "valid",
            db_models.User.is_active.is_(True),
            db_models.User.identity_enabled.is_(True),
        ]
        normalized_query = query.strip()
        if normalized_query:
            like_pattern = f"%{normalized_query}%"
            filters.append(
                or_(
                    db_models.User.display_name.ilike(like_pattern),
                    db_models.User.username.ilike(like_pattern),
                    db_models.User.email.ilike(like_pattern),
                )
            )
        users = list(
            self.db.scalars(
                select(db_models.User)
                .where(*filters)
                .order_by(db_models.User.display_name.asc(), db_models.User.id.asc())
                .limit(limit)
            ).all()
        )
        return [
            (user.id, user.display_name or user.username or user.email or user.id)
            for user in users
        ]

    def list_share_candidate_groups(
        self,
        *,
        actor: AuthorizationActor,
        workspace_id: str,
        query: str,
        limit: int,
    ) -> list[tuple[str, str]]:
        """Return a minimal projection of unshared group candidates."""
        self._lock_workspace(workspace_id)
        AuthorizationOperationPolicy(self.db).require_workspace_operation(
            actor,
            workspace_id,
            OperationId.WORKSPACE_ACCESS_MANAGE,
        )
        shared_group_ids = select(db_models.WorkspaceShare.target_id).where(
            db_models.WorkspaceShare.workspace_id == workspace_id,
            db_models.WorkspaceShare.target_type == "user_group",
        )
        filters = [db_models.UserGroup.id.not_in(shared_group_ids)]
        normalized_query = query.strip()
        if normalized_query:
            filters.append(db_models.UserGroup.name.ilike(f"%{normalized_query}%"))
        groups = list(
            self.db.scalars(
                select(db_models.UserGroup)
                .where(*filters)
                .order_by(db_models.UserGroup.name.asc(), db_models.UserGroup.id.asc())
                .limit(limit)
            ).all()
        )
        return [(group.id, group.name) for group in groups]

    def list_shares(
        self,
        workspace_id: str,
        *,
        actor: AuthorizationActor,
    ) -> WorkspaceShareListResponse:
        workspace = self.db.get(db_models.Workspace, workspace_id)
        if not workspace:
            raise WorkspaceNotFoundError(WORKSPACE_NOT_FOUND_MESSAGE)
        AuthorizationOperationPolicy(self.db).require_workspace_operation(
            actor,
            workspace_id,
            OperationId.WORKSPACE_ACCESS_MANAGE,
        )

        rows = (
            self.db.execute(
                select(db_models.WorkspaceShare)
                .options(
                    selectinload(db_models.WorkspaceShare.granted_by_user),
                )
                .where(db_models.WorkspaceShare.workspace_id == workspace_id)
                .order_by(db_models.WorkspaceShare.created_at.asc())
            )
            .scalars()
            .all()
        )
        return WorkspaceShareListResponse(items=[self._to_share(row) for row in rows])

    def create_share(
        self,
        workspace_id: str,
        payload: WorkspaceShareCreateRequest,
        *,
        actor: AuthorizationActor,
        correlation_id: str | None = None,
        root_correlation_id: str | None = None,
    ) -> WorkspaceShare:
        correlation_id = correlation_id or str(uuid4())
        root_correlation_id = root_correlation_id or correlation_id
        target_model = (
            db_models.User if payload.target_type == "user" else db_models.UserGroup
        )
        target = self.db.scalar(
            select(target_model)
            .where(target_model.id == payload.target_id)
            .with_for_update()
        )
        if target is None:
            raise WorkspaceNotFoundError(
                WORKSPACE_SHARE_TARGET_NOT_FOUND_MESSAGE,
                code="WORKSPACE_SHARE_TARGET_NOT_FOUND",
            )

        workspace = self._lock_workspace(workspace_id)
        AuthorizationOperationPolicy(self.db).require_workspace_operation(
            actor,
            workspace_id,
            OperationId.WORKSPACE_ACCESS_MANAGE,
        )
        if payload.target_type == "user" and not UserAuthorizationPolicy().is_authorized(
            target
        ):
            raise WorkspaceError(
                WORKSPACE_SHARE_TARGET_NOT_FOUND_MESSAGE,
                code="WORKSPACE_SHARE_TARGET_NOT_AUTHORIZABLE",
            )
        if payload.target_type == "user" and payload.target_id == workspace.owner_id:
            raise WorkspaceError(
                WORKSPACE_SHARE_OWNER_FORBIDDEN_MESSAGE,
                code="WORKSPACE_INVALID_SHARE_TARGET",
            )

        existing_share = self.db.scalar(
            select(db_models.WorkspaceShare).where(
                db_models.WorkspaceShare.workspace_id == workspace_id,
                db_models.WorkspaceShare.target_type == payload.target_type,
                db_models.WorkspaceShare.target_id == payload.target_id,
            )
        )
        if existing_share:
            raise WorkspaceError(
                WORKSPACE_SHARE_CONFLICT_MESSAGE, code="WORKSPACE_SHARE_CONFLICT"
            )

        share = db_models.WorkspaceShare(
            id=str(uuid4()),
            workspace_id=workspace_id,
            target_type=payload.target_type,
            target_id=payload.target_id,
            role=payload.role,
            granted_by_user_id=actor.user_id,
        )
        self.db.add(share)
        self.audit_events.record(
            event_type="workspace.share_created",
            actor_type="user",
            actor_id=actor.user_id,
            actor_user_id=actor.user_id,
            target_type=payload.target_type,
            target_id=payload.target_id,
            action="create_share",
            result="success",
            error_code=None,
            correlation_id=correlation_id,
            root_correlation_id=root_correlation_id,
            metadata={"workspace_id": workspace_id, "after": payload.role},
        )
        self.db.commit()
        self.db.refresh(share)
        return self._reload_share(share.id)

    def update_share(
        self,
        workspace_id: str,
        share_id: str,
        payload: WorkspaceShareUpdateRequest,
        *,
        actor: AuthorizationActor,
        correlation_id: str,
        root_correlation_id: str,
    ) -> Optional[WorkspaceShare]:
        cancellations = []
        try:
            workspace = self._lock_workspace(workspace_id)
            AuthorizationOperationPolicy(self.db).require_workspace_operation(
                actor,
                workspace_id,
                OperationId.WORKSPACE_ACCESS_MANAGE,
            )

            share = self._lock_workspace_share(
                workspace_id=workspace_id,
                share_id=share_id,
            )
            if share is None:
                self.db.rollback()
                return None

            previous_role = share.role
            share.role = payload.role
            share.updated_at = datetime.utcnow()
            if previous_role == "manager" and payload.role == "reader":
                for principal_user_id in self._share_principal_user_ids(share):
                    cancellations.extend(
                        self._record_access_reduction(
                            workspace=workspace,
                            principal_user_id=principal_user_id,
                            actor_user_id=actor.user_id,
                            correlation_id=correlation_id,
                            root_correlation_id=root_correlation_id,
                            reason="workspace_share_downgraded",
                        )
                    )
            self.audit_events.record(
                event_type="workspace.share_updated",
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
                    "workspace_id": workspace_id,
                    "before": previous_role,
                    "after": payload.role,
                },
            )
            self.db.flush()
            result = self._reload_share(share.id)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        self._cancel_automation_after_commit(cancellations)
        return result

    def delete_share(
        self,
        workspace_id: str,
        share_id: str,
        *,
        actor: AuthorizationActor,
        correlation_id: str,
        root_correlation_id: str,
    ) -> bool:
        cancellations = []
        try:
            workspace = self._lock_workspace(workspace_id)
            AuthorizationOperationPolicy(self.db).require_workspace_operation(
                actor,
                workspace_id,
                OperationId.WORKSPACE_ACCESS_MANAGE,
            )

            share = self._lock_workspace_share(
                workspace_id=workspace_id,
                share_id=share_id,
            )
            if share is None:
                self.db.rollback()
                return False

            principal_user_ids = self._share_principal_user_ids(share)
            self.db.delete(share)
            for principal_user_id in principal_user_ids:
                cancellations.extend(
                    self._record_access_reduction(
                        workspace=workspace,
                        principal_user_id=principal_user_id,
                        actor_user_id=actor.user_id,
                        correlation_id=correlation_id,
                        root_correlation_id=root_correlation_id,
                        reason="workspace_share_deleted",
                    )
                )
            self.audit_events.record(
                event_type="workspace.share_deleted",
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
                metadata={"workspace_id": workspace_id, "before": share.role},
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

        self._cancel_automation_after_commit(cancellations)
        return True

    def _record_access_reduction(
        self,
        *,
        workspace: db_models.Workspace,
        principal_user_id: str,
        actor_user_id: str,
        correlation_id: str,
        root_correlation_id: str,
        reason: str,
    ) -> list[RunningCancellation]:
        from app.modules.automation.repository import AutomationRepository
        from app.modules.automation.execution import AutomationExecutionService

        service = AutomationExecutionService(AutomationRepository(self.db))
        cancellations = service.converge_principal_authorization_in_transaction(
            principal_user_id=principal_user_id,
            workspace_id=workspace.id,
        )
        workspace.runtime_access_revision += 1
        self.runtime_jobs.supersede_queued_and_enqueue_access_recycle(
            workspace=workspace,
            correlation_id=correlation_id,
            root_correlation_id=root_correlation_id,
            scheduled_at=datetime.utcnow(),
            job_metadata={"reason": reason},
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
                "reason": reason,
            },
        )
        return cancellations

    def _cancel_automation_after_commit(
        self,
        cancellations: list[RunningCancellation],
    ) -> None:
        if not cancellations:
            return
        from app.modules.automation.repository import AutomationRepository
        from app.modules.automation.execution import AutomationExecutionService

        service = AutomationExecutionService(AutomationRepository(self.db))
        service.cancel_running_after_commit(cancellations)

    def _lock_workspace(self, workspace_id: str) -> db_models.Workspace:
        acquire_workspace_transaction_lock(self.db, workspace_id)
        workspace = self.db.scalar(
            select(db_models.Workspace)
            .where(db_models.Workspace.id == workspace_id)
            .with_for_update()
        )
        if workspace is None:
            raise WorkspaceNotFoundError(WORKSPACE_NOT_FOUND_MESSAGE)
        return workspace

    def _lock_workspace_share(
        self,
        *,
        workspace_id: str,
        share_id: str,
    ) -> db_models.WorkspaceShare | None:
        return self.db.scalar(
            select(db_models.WorkspaceShare)
            .where(
                db_models.WorkspaceShare.id == share_id,
                db_models.WorkspaceShare.workspace_id == workspace_id,
            )
            .with_for_update()
        )

    # -- Conversion functions ---------------------------------------------------------

    def _to_owner(self, user: db_models.User) -> WorkspaceOwner:
        return WorkspaceOwner(
            id=user.id,
            display_name=user.display_name or user.username,
            avatar_url=user.avatar_url,
            username=user.username,
            email=user.email,
        )

    def _to_owner_by_id_with_stable_columns(self, owner_id: str) -> WorkspaceOwner:
        row = (
            self.db.execute(
                text("""
                SELECT id, username, email, display_name, avatar_url
                FROM users
                WHERE id = :owner_id
                LIMIT 1
                """),
                {"owner_id": owner_id},
            )
            .mappings()
            .first()
        )
        if not row:
            raise WorkspaceNotFoundError(WORKSPACE_OWNER_NOT_FOUND_MESSAGE)

        return WorkspaceOwner(
            id=row["id"],
            display_name=row["display_name"] or row["username"],
            avatar_url=row["avatar_url"],
            username=row["username"],
            email=row["email"],
        )

    def _to_workspace_owner(self, workspace: db_models.Workspace) -> WorkspaceOwner:
        try:
            return self._to_owner(workspace.owner)
        except SQLAlchemyError as exc:
            logger.warning(
                "Falling back to stable-column workspace owner lookup: workspace_id=%s owner_id=%s error=%s",
                workspace.id,
                workspace.owner_id,
                exc,
            )
            self.db.rollback()
            return self._to_owner_by_id_with_stable_columns(workspace.owner_id)

    def _to_share_user(self, user: db_models.User) -> WorkspaceShareUser:
        return WorkspaceShareUser(
            id=user.id,
            display_name=user.display_name or user.username,
            avatar_url=user.avatar_url,
            username=user.username,
            email=user.email,
        )

    def _to_share(self, share: db_models.WorkspaceShare) -> WorkspaceShare:
        if share.target_type == "user":
            target = self.db.get(db_models.User, share.target_id)
            target_label = (
                target.display_name or target.username or target.email or target.id
                if target is not None
                else share.target_id
            )
        else:
            target = self.db.get(db_models.UserGroup, share.target_id)
            target_label = target.name if target is not None else share.target_id
        return WorkspaceShare(
            id=share.id,
            target_type=share.target_type,
            target_id=share.target_id,
            target_label=target_label,
            role=share.role,
            granted_by=self._to_share_user(share.granted_by_user),
            created_at=share.created_at,
            updated_at=share.updated_at,
        )

    def _share_principal_user_ids(
        self,
        share: db_models.WorkspaceShare,
    ) -> list[str]:
        if share.target_type == "user":
            return [share.target_id]
        return list(
            self.db.scalars(
                select(db_models.UserGroupMember.user_id).where(
                    db_models.UserGroupMember.group_id == share.target_id
                )
            ).all()
        )

    def _to_summary(
        self,
        workspace: db_models.Workspace,
        *,
        access_role: ResourceAccessRole,
        access_source: WorkspaceAccessSource,
        current_user_id: str,
        access_sources: tuple[ResourceAccessSource, ...] | None = None,
    ) -> WorkspaceSummary:
        owner = self._to_workspace_owner(workspace)
        public_urls = WorkspacePublicUrls.for_workspace(workspace.id)
        return WorkspaceSummary(
            id=workspace.id,
            name=workspace.name,
            description=workspace.description,
            owner=owner,
            git_url=workspace.git_url,
            branch=workspace.branch,
            runtime=workspace.runtime,
            provisioner=workspace.provisioner,
            target_namespace=workspace.target_namespace,
            overall_phase=workspace.runtime_status,
            agentic_tools=(
                workspace.agentic_tools
                if workspace.agentic_tools is not None
                else ["claude-code"]
            ),
            runtime_status=workspace.runtime_status,
            runtime_url=public_urls.runtime,
            runtime_last_seen=workspace.runtime_last_seen,
            access_role=access_role,
            access_source=access_source,
            access_sources=list(access_sources or (access_source,)),
            allowed_operations=list(allowed_workspace_operations(access_role)),
            worktree_subdir=getattr(workspace, "worktree_subdir", ".worktrees")
            or ".worktrees",
            created_at=workspace.created_at,
            updated_at=workspace.updated_at,
        )

    @staticmethod
    def _canvas_type_or_default(value: object) -> str:
        return value if value in {"html", "nextjs", "default"} else "default"

    @staticmethod
    def _canvas_manifest_status_or_default(value: object) -> str:
        return value if value in {"missing", "valid", "invalid"} else "missing"

    @staticmethod
    def _datetime_or_none(value: object) -> Optional[datetime]:
        return value if isinstance(value, datetime) else None

    def _to_detail(
        self,
        workspace: db_models.Workspace,
        *,
        access_role: ResourceAccessRole,
        access_source: WorkspaceAccessSource,
        current_user_id: str,
        access_sources: tuple[ResourceAccessSource, ...] | None = None,
    ) -> WorkspaceReadDetail:
        owner = self._to_workspace_owner(workspace)
        public_urls = WorkspacePublicUrls.for_workspace(workspace.id)
        runtime_status = RuntimeStatus(
            status=workspace.runtime_status,
            container_id=workspace.runtime_container_id,
            runtime_url=public_urls.runtime,
            browser_url=public_urls.browser,
            canvas_url=public_urls.canvas,
            last_seen=workspace.runtime_last_seen,
            # Browser related columns
            browser_container_id=workspace.browser_container_id,
            browser_status=workspace.browser_status,
            browser_created_at=workspace.browser_created_at,
            browser_last_seen=workspace.browser_last_seen,
            # Canvas ContainerColumn
            canvas_container_id=workspace.canvas_container_id,
            canvas_status=workspace.canvas_status,
            canvas_created_at=workspace.canvas_created_at,
            canvas_last_seen=workspace.canvas_last_seen,
            canvas_type=self._canvas_type_or_default(
                getattr(workspace, "canvas_type", None)
            ),
            canvas_manifest_status=self._canvas_manifest_status_or_default(
                getattr(workspace, "canvas_manifest_status", None)
            ),
            canvas_last_sync_at=self._datetime_or_none(
                getattr(workspace, "canvas_last_sync_at", None)
            ),
            canvas_last_reset_at=self._datetime_or_none(
                getattr(workspace, "canvas_last_reset_at", None)
            ),
        )
        # Keep both firewall groups in the API response because the manager stores a
        # symmetric configuration surface across provisioners. Verified enforcement
        # still differs by provisioner: Docker currently enforces the workspace
        # runtime scope through workspace-runtime, while Kubernetes delegates both
        # groups through the custom resource / policy-controller path.
        firewall = FirewallConfig(
            workspace={
                "egressMode": workspace.workspace_firewall_egress_mode,
                "allowedDomains": workspace.workspace_firewall_allowed_domains or [],
            },
            browser={
                "egressMode": workspace.browser_firewall_egress_mode,
                "allowedDomains": workspace.browser_firewall_allowed_domains or [],
            },
        )

        components = self._to_components(workspace)
        attached_knowledge_bases = self._to_workspace_kb_attachments(workspace)
        runtime_job = None
        if workspace.runtime_jobs:
            runtime_job = self._to_runtime_job(workspace.runtime_jobs[0])

        return WorkspaceReadDetail(
            id=workspace.id,
            owner=owner,
            name=workspace.name,
            description=workspace.description,
            git_url=workspace.git_url,
            branch=workspace.branch,
            runtime=workspace.runtime,
            provisioner=workspace.provisioner,
            target_namespace=workspace.target_namespace,
            overall_phase=workspace.runtime_status,
            agentic_tools=(
                workspace.agentic_tools
                if workspace.agentic_tools is not None
                else ["claude-code"]
            ),
            runtime_status=runtime_status,
            bootstrap=WorkspaceBootstrapStatus(
                desired_revision=workspace.bootstrap_revision,
                observed_revision=workspace.bootstrap_observed_revision,
                phase=workspace.bootstrap_status.title(),
                error_code=workspace.bootstrap_error_code,
                last_transition_at=workspace.bootstrap_last_transition_at,
            ),
            components=components,
            browser_connectivity=BrowserConnectivityStatus(
                contract_version=workspace.browser_connectivity_contract_version,
                state=workspace.browser_connectivity_state,
                admission=workspace.browser_connectivity_admission,
                profile_revision=workspace.browser_connectivity_profile_revision,
                credential_revision=workspace.browser_connectivity_credential_revision,
                browser_generation=workspace.browser_connectivity_browser_generation,
                backend_state=workspace.browser_connectivity_backend_state,
                backend_accepted_at=workspace.browser_connectivity_backend_accepted_at,
                backend_expires_at=workspace.browser_connectivity_backend_expires_at,
                backend_reason=workspace.browser_connectivity_backend_reason,
                backend_error_code=workspace.browser_connectivity_backend_error_code,
                frontend_state=workspace.browser_connectivity_frontend_state,
                frontend_accepted_at=workspace.browser_connectivity_frontend_accepted_at,
                frontend_expires_at=workspace.browser_connectivity_frontend_expires_at,
                frontend_reason=workspace.browser_connectivity_frontend_reason,
                frontend_error_code=workspace.browser_connectivity_frontend_error_code,
                accepted_at=workspace.browser_connectivity_accepted_at,
                expires_at=workspace.browser_connectivity_expires_at,
                reason=workspace.browser_connectivity_reason,
                error_code=workspace.browser_connectivity_error_code,
                last_transition_at=workspace.browser_connectivity_last_transition_at,
            ),
            firewall_available=self._is_firewall_available_for_provisioner(
                workspace.provisioner
            ),
            firewall_unavailable_reason=self._firewall_unavailable_reason_for_provisioner(
                workspace.provisioner
            ),
            firewall=firewall,
            preferred_cli=workspace.preferred_cli,
            fallback_enabled=workspace.fallback_enabled,
            workspace_path=workspace.workspace_path,
            worktree_subdir=getattr(workspace, "worktree_subdir", ".worktrees")
            or ".worktrees",
            access_role=access_role,
            access_source=access_source,
            access_sources=list(access_sources or (access_source,)),
            allowed_operations=list(allowed_workspace_operations(access_role)),
            attached_knowledge_bases=attached_knowledge_bases,
            knowledge_base_mount_active_revision=(
                workspace.knowledge_base_mount_active_revision
            ),
            knowledge_base_mount_desired_revision=workspace.knowledge_base_mount_desired_revision,
            knowledge_base_mount_observed_revision=(
                workspace.knowledge_base_mount_observed_revision
            ),
            knowledge_base_mount_sync_status=workspace.knowledge_base_mount_sync_status,
            knowledge_base_mount_error_code=workspace.knowledge_base_mount_error_code,
            runtime_access_revision=workspace.runtime_access_revision,
            runtime_access_observed_revision=(
                workspace.runtime_access_observed_revision
            ),
            runtime_instance_id=(
                str(workspace.runtime_instance_id)
                if workspace.runtime_instance_id is not None
                else None
            ),
            created_at=workspace.created_at,
            updated_at=workspace.updated_at,
            runtime_job=runtime_job,
        )

    def _push_worktree_gitignore_sync(
        self,
        workspace: db_models.Workspace,
        *,
        subdir: str,
        previous: str,
    ) -> None:
        if not workspace.runtime_internal_url:
            logger.warning(
                "Skipping worktree gitignore sync for workspace %s because runtime_internal_url is missing",
                workspace.id,
            )
            return

        url = f"{workspace.runtime_internal_url.rstrip('/')}/api/v1/internal/worktree/sync-gitignore"
        runtime_instance_id = workspace.runtime_instance_id
        if not isinstance(runtime_instance_id, str) or not runtime_instance_id:
            logger.warning(
                "Skipping worktree gitignore sync for workspace %s because runtime identity is missing",
                workspace.id,
            )
            return
        headers = runtime_command_headers(
            workspace_id=workspace.id,
            runtime_instance_id=runtime_instance_id,
            action="worktree.sync",
        )
        try:
            with httpx.Client(timeout=3.0) as client:
                client.post(
                    url,
                    json={"subdir": subdir, "previous": previous},
                    headers=headers,
                ).raise_for_status()
        except Exception as exc:
            logger.warning(
                "Failed to push worktree gitignore sync for workspace %s: %s",
                workspace.id,
                exc,
            )

    def _to_workspace_kb_attachments(
        self,
        workspace: db_models.Workspace,
    ) -> list[WorkspaceKnowledgeBaseAttachment]:
        attachments: list[WorkspaceKnowledgeBaseAttachment] = []
        raw_attachments = getattr(workspace, "knowledge_base_attachments", [])
        if not isinstance(raw_attachments, list):
            return []

        for attachment in raw_attachments:
            kb = attachment.knowledge_base
            attachments.append(
                WorkspaceKnowledgeBaseAttachment(
                    id=attachment.id,
                    kb_id=kb.id,
                    name=kb.name,
                    slug=kb.slug,
                    mount_alias=attachment.mount_alias,
                    status="active",
                    attached_by_id=attachment.attached_by_id,
                    created_at=attachment.created_at,
                    updated_at=attachment.updated_at,
                )
            )
        return attachments

    def _reload_share(self, share_id: str) -> WorkspaceShare:
        share = self.db.execute(
            select(db_models.WorkspaceShare)
            .options(
                selectinload(db_models.WorkspaceShare.granted_by_user),
            )
            .where(db_models.WorkspaceShare.id == share_id)
        ).scalar_one()
        return self._to_share(share)

    @staticmethod
    def _to_sensitive_settings(
        workspace: db_models.Workspace,
    ) -> WorkspaceSensitiveSettings:
        return WorkspaceSensitiveSettings(
            setup_script=workspace.setup_script,
            env_vars=[
                WorkspaceSensitiveEnvVar(
                    key=item["key"],
                    is_configured=bool(item.get("value")),
                )
                for item in (workspace.env_vars or [])
                if isinstance(item, dict) and isinstance(item.get("key"), str)
            ],
            acp_cli_args=list(workspace.acp_cli_args or []),
        )

    def _is_firewall_available_for_provisioner(
        self, provisioner: Optional[str]
    ) -> bool:
        if provisioner == "kubernetes":
            return self.settings.CILIUM_ENABLED
        return True

    def _firewall_unavailable_reason_for_provisioner(
        self, provisioner: Optional[str]
    ) -> Optional[str]:
        if self._is_firewall_available_for_provisioner(provisioner):
            return None
        return "CILIUM_NOT_ENABLED"

    def _resolve_target_namespace(
        self,
        *,
        provisioner: str,
    ) -> Optional[str]:
        if provisioner != "kubernetes":
            return None
        return self.settings.RUNTIME_K8S_NAMESPACE

    def _to_runtime_job(
        self, job: db_models.WorkspaceRuntimeJob
    ) -> WorkspaceRuntimeJobSummary:
        return WorkspaceRuntimeJobSummary(
            id=job.id,
            operation=job.operation,
            strategy=job.strategy,
            status=job.status,
            retries=job.retries,
            target_component=job.target_component,
            scheduled_at=job.scheduled_at,
            started_at=job.started_at,
            finished_at=job.finished_at,
            target_revision=job.target_revision,
            target_runtime_instance_id=(
                str(job.target_runtime_instance_id)
                if job.target_runtime_instance_id is not None
                else None
            ),
            correlation_id=job.correlation_id,
            root_correlation_id=job.root_correlation_id,
            error_code=job.error_code,
            phase=(
                job.job_metadata.get("phase")
                if isinstance(job.job_metadata.get("phase"), str)
                else None
            ),
        )

    def _ensure_firewall_available(self, *, provisioner: Optional[str]) -> None:
        if not self._is_firewall_available_for_provisioner(provisioner):
            raise WorkspaceError(
                self._firewall_unavailable_reason_for_provisioner(provisioner),
                code="WORKSPACE_FIREWALL_UNAVAILABLE",
                params={
                    "reason": self._firewall_unavailable_reason_for_provisioner(
                        provisioner
                    )
                },
            )

    def _to_components(self, workspace: db_models.Workspace) -> WorkspaceComponents:
        restart_metadata = self._collect_restart_metadata(workspace)
        return WorkspaceComponents(
            runtime=WorkspaceComponentStatus(
                phase=workspace.runtime_status.title(),
                desired_revision=workspace.runtime_desired_revision,
                observed_revision=workspace.runtime_observed_revision,
                ready=(
                    workspace.runtime_status == "running"
                    and workspace.runtime_observed_revision
                    == workspace.runtime_desired_revision
                ),
                terminal_ready=workspace.runtime_status == "running",
                workload_id=workspace.runtime_container_id,
                reason=workspace.runtime_reason,
                error_code=workspace.runtime_error_code,
                last_transition_at=workspace.runtime_last_transition_at,
                last_seen=workspace.runtime_last_seen,
                last_restart_requested_at=restart_metadata["runtime"],
            ),
            browser=WorkspaceComponentStatus(
                phase=workspace.browser_status.title(),
                desired_revision=workspace.browser_desired_revision,
                observed_revision=workspace.browser_observed_revision,
                ready=(
                    workspace.browser_status == "running"
                    and workspace.browser_observed_revision
                    == workspace.browser_desired_revision
                ),
                workload_id=workspace.browser_container_id,
                reason=workspace.browser_reason,
                error_code=workspace.browser_error_code,
                last_transition_at=workspace.browser_last_transition_at,
                last_seen=workspace.browser_last_seen,
                last_restart_requested_at=restart_metadata["browser"],
            ),
            canvas=WorkspaceComponentStatus(
                phase=workspace.canvas_status.title(),
                desired_revision=workspace.canvas_desired_revision,
                observed_revision=workspace.canvas_observed_revision,
                ready=(
                    workspace.canvas_status == "running"
                    and workspace.canvas_observed_revision
                    == workspace.canvas_desired_revision
                ),
                workload_id=workspace.canvas_container_id,
                reason=workspace.canvas_reason,
                error_code=workspace.canvas_error_code,
                last_transition_at=workspace.canvas_last_transition_at,
                last_seen=workspace.canvas_last_seen,
                last_restart_requested_at=restart_metadata["canvas"],
            ),
        )

    def _collect_restart_metadata(
        self,
        workspace: db_models.Workspace,
    ) -> dict[str, Optional[datetime]]:
        restart_metadata: dict[str, Optional[datetime]] = {
            "runtime": None,
            "browser": None,
            "canvas": None,
        }

        for job in workspace.runtime_jobs or []:
            if job.operation not in {
                "runtime_restart",
                "browser_restart",
                "canvas_restart",
            }:
                continue
            component = job.target_component
            if component in restart_metadata:
                restart_metadata[component] = (
                    restart_metadata[component] or job.scheduled_at
                )

        for log in workspace.runtime_logs or []:
            if log.stage == "restarting" and restart_metadata["runtime"] is None:
                restart_metadata["runtime"] = log.created_at
            elif (
                log.stage == "browser_restarting"
                and restart_metadata["browser"] is None
            ):
                restart_metadata["browser"] = log.created_at
            elif (
                log.stage == "canvas_restarting" and restart_metadata["canvas"] is None
            ):
                restart_metadata["canvas"] = log.created_at

        return restart_metadata


__all__ = ["WorkspaceService"]
