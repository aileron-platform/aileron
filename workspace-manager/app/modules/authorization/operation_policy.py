"""Closed authorization operation vocabulary and fixed requirements."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import Literal, Mapping

from sqlalchemy.orm import Session

from app.modules.authorization.actor import AuthorizationActor
from app.modules.authorization.admin_override_audit import (
    IndependentPlatformAdminOverrideAuditWriter,
    OverrideTargetType,
    PlatformAdminOverrideAuditRecord,
    PlatformAdminOverrideAuditWriter,
)
from app.modules.authorization.resource_access import (
    ResourceAccessRole,
    ResourceAccessSource,
    normalize_resource_role,
    role_satisfies,
)
from app.modules.identity.platform_role import PlatformRole
from app.modules.knowledge_base.access_repository import KnowledgeBaseAccessResolver
from app.modules.workspace.access_repository import WorkspaceAccessResolver

AuthorizationScope = Literal["platform", "workspace", "knowledge_base"]


class OperationId(str, Enum):
    """Stable wire identifiers for every supported authorization operation."""

    MARKETPLACE_CATALOG_READ = "marketplace.catalog.read"
    MARKETPLACE_INSTALL_EXECUTE = "marketplace.install.execute"
    MARKETPLACE_USER_COPY_MANAGE = "marketplace.user_copy.manage"
    MARKETPLACE_CONTENT_PUBLISH = "marketplace.content.publish"
    MARKETPLACE_CONTENT_MANAGE = "marketplace.content.manage"
    MARKETPLACE_DELETE_EXECUTE = "marketplace.delete.execute"
    MARKETPLACE_REGISTRY_MANAGE = "marketplace.registry.manage"
    WORKSPACE_COLLECTION_READ = "workspace.collection.read"
    WORKSPACE_CREATE = "workspace.create"
    KNOWLEDGE_BASE_COLLECTION_READ = "knowledge_base.collection.read"
    KNOWLEDGE_BASE_CREATE = "knowledge_base.create"
    USER_MANAGEMENT_MANAGE = "user_management.manage"
    PLATFORM_RESOURCES_READ = "platform_resources.read"
    PLATFORM_RESOURCES_OWNER_REASSIGN = "platform_resources.owner.reassign"
    PLATFORM_RESOURCES_KNOWLEDGE_BASE_QUOTA_UPDATE = (
        "platform_resources.knowledge_base.quota.update"
    )
    PLATFORM_RESOURCES_WORKSPACE_CAPACITY_EXPAND = (
        "platform_resources.workspace.capacity.expand"
    )
    WORKSPACE_DETAIL_READ = "workspace.detail.read"
    WORKSPACE_CONTENT_WRITE = "workspace.content.write"
    WORKSPACE_LIFECYCLE_EXECUTE = "workspace.lifecycle.execute"
    WORKSPACE_METADATA_WRITE = "workspace.metadata.write"
    WORKSPACE_ACCESS_MANAGE = "workspace.access.manage"
    WORKSPACE_ATTACHMENT_WRITE = "workspace.attachment.write"
    WORKSPACE_FIREWALL_READ = "workspace.firewall.read"
    WORKSPACE_FIREWALL_MANAGE = "workspace.firewall.manage"
    WORKSPACE_SENSITIVE_SETTINGS_READ = "workspace.sensitive_settings.read"
    WORKSPACE_SENSITIVE_SETTINGS_MANAGE = "workspace.sensitive_settings.manage"
    WORKSPACE_TERMINAL_USE = "workspace.terminal.use"
    WORKSPACE_AGENT_CHAT_USE = "workspace.agent_chat.use"
    WORKSPACE_AUTOMATION_EXECUTE = "workspace.automation.execute"
    WORKSPACE_BROWSER_AUTOMATION_USE = "workspace.browser_automation.use"
    WORKSPACE_DELETE = "workspace.delete"
    KNOWLEDGE_BASE_DETAIL_READ = "knowledge_base.detail.read"
    KNOWLEDGE_BASE_CONTENT_WRITE = "knowledge_base.content.write"
    KNOWLEDGE_BASE_SETTINGS_MANAGE = "knowledge_base.settings.manage"
    KNOWLEDGE_BASE_SHARE_MANAGE = "knowledge_base.share.manage"
    KNOWLEDGE_BASE_VISIBILITY_MANAGE = "knowledge_base.visibility.manage"
    KNOWLEDGE_BASE_DELETE = "knowledge_base.delete"

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class OperationRequirement:
    """Resource role or platform-admin requirement for one operation."""

    scope: AuthorizationScope
    minimum_resource_role: ResourceAccessRole | None = None
    platform_admin_only: bool = False


@dataclass(frozen=True)
class AuthorizationGrant:
    """Immutable result of one current-snapshot operation check."""

    actor: AuthorizationActor
    operation: OperationId
    access_role: ResourceAccessRole | None
    access_source: ResourceAccessSource | None = None
    access_sources: tuple[ResourceAccessSource, ...] = ()


@dataclass
class AuthorizationOperationError(Exception):
    """Stable denial emitted by the shared operation facade."""

    error_code: str
    http_status: int


def _platform_requirement(*, admin_only: bool = False) -> OperationRequirement:
    return OperationRequirement("platform", platform_admin_only=admin_only)


def _resource_requirement(
    scope: Literal["workspace", "knowledge_base"],
    minimum_resource_role: ResourceAccessRole,
) -> OperationRequirement:
    return OperationRequirement(scope, minimum_resource_role)


OPERATION_REQUIREMENTS: Mapping[OperationId, OperationRequirement] = MappingProxyType(
    {
        OperationId.MARKETPLACE_CATALOG_READ: _platform_requirement(),
        OperationId.MARKETPLACE_INSTALL_EXECUTE: _platform_requirement(),
        OperationId.MARKETPLACE_USER_COPY_MANAGE: _platform_requirement(),
        OperationId.MARKETPLACE_CONTENT_PUBLISH: _platform_requirement(admin_only=True),
        OperationId.MARKETPLACE_CONTENT_MANAGE: _platform_requirement(admin_only=True),
        OperationId.MARKETPLACE_DELETE_EXECUTE: _platform_requirement(admin_only=True),
        OperationId.MARKETPLACE_REGISTRY_MANAGE: _platform_requirement(admin_only=True),
        OperationId.WORKSPACE_COLLECTION_READ: _platform_requirement(),
        OperationId.WORKSPACE_CREATE: _platform_requirement(),
        OperationId.KNOWLEDGE_BASE_COLLECTION_READ: _platform_requirement(),
        OperationId.KNOWLEDGE_BASE_CREATE: _platform_requirement(),
        OperationId.USER_MANAGEMENT_MANAGE: _platform_requirement(admin_only=True),
        OperationId.PLATFORM_RESOURCES_READ: _platform_requirement(admin_only=True),
        OperationId.PLATFORM_RESOURCES_OWNER_REASSIGN: _platform_requirement(
            admin_only=True
        ),
        OperationId.PLATFORM_RESOURCES_KNOWLEDGE_BASE_QUOTA_UPDATE: (
            _platform_requirement(admin_only=True)
        ),
        OperationId.PLATFORM_RESOURCES_WORKSPACE_CAPACITY_EXPAND: (
            _platform_requirement(admin_only=True)
        ),
        OperationId.WORKSPACE_DETAIL_READ: _resource_requirement(
            "workspace", ResourceAccessRole.READER
        ),
        OperationId.WORKSPACE_CONTENT_WRITE: _resource_requirement(
            "workspace", ResourceAccessRole.MANAGER
        ),
        OperationId.WORKSPACE_LIFECYCLE_EXECUTE: _resource_requirement(
            "workspace", ResourceAccessRole.MANAGER
        ),
        OperationId.WORKSPACE_METADATA_WRITE: _resource_requirement(
            "workspace", ResourceAccessRole.MANAGER
        ),
        OperationId.WORKSPACE_ACCESS_MANAGE: _resource_requirement(
            "workspace", ResourceAccessRole.MANAGER
        ),
        OperationId.WORKSPACE_ATTACHMENT_WRITE: _resource_requirement(
            "workspace", ResourceAccessRole.MANAGER
        ),
        OperationId.WORKSPACE_FIREWALL_READ: _resource_requirement(
            "workspace", ResourceAccessRole.READER
        ),
        OperationId.WORKSPACE_FIREWALL_MANAGE: _resource_requirement(
            "workspace", ResourceAccessRole.MANAGER
        ),
        OperationId.WORKSPACE_SENSITIVE_SETTINGS_READ: _resource_requirement(
            "workspace", ResourceAccessRole.READER
        ),
        OperationId.WORKSPACE_SENSITIVE_SETTINGS_MANAGE: _resource_requirement(
            "workspace", ResourceAccessRole.MANAGER
        ),
        OperationId.WORKSPACE_TERMINAL_USE: _resource_requirement(
            "workspace", ResourceAccessRole.MANAGER
        ),
        OperationId.WORKSPACE_AGENT_CHAT_USE: _resource_requirement(
            "workspace", ResourceAccessRole.MANAGER
        ),
        OperationId.WORKSPACE_AUTOMATION_EXECUTE: _resource_requirement(
            "workspace", ResourceAccessRole.MANAGER
        ),
        OperationId.WORKSPACE_BROWSER_AUTOMATION_USE: _resource_requirement(
            "workspace", ResourceAccessRole.MANAGER
        ),
        OperationId.WORKSPACE_DELETE: _resource_requirement(
            "workspace", ResourceAccessRole.OWNER
        ),
        OperationId.KNOWLEDGE_BASE_DETAIL_READ: _resource_requirement(
            "knowledge_base", ResourceAccessRole.READER
        ),
        OperationId.KNOWLEDGE_BASE_CONTENT_WRITE: _resource_requirement(
            "knowledge_base", ResourceAccessRole.MANAGER
        ),
        OperationId.KNOWLEDGE_BASE_SETTINGS_MANAGE: _resource_requirement(
            "knowledge_base", ResourceAccessRole.MANAGER
        ),
        OperationId.KNOWLEDGE_BASE_SHARE_MANAGE: _resource_requirement(
            "knowledge_base", ResourceAccessRole.MANAGER
        ),
        OperationId.KNOWLEDGE_BASE_VISIBILITY_MANAGE: _resource_requirement(
            "knowledge_base", ResourceAccessRole.MANAGER
        ),
        OperationId.KNOWLEDGE_BASE_DELETE: _resource_requirement(
            "knowledge_base", ResourceAccessRole.OWNER
        ),
    }
)


def _allowed_operations(
    *,
    scope: AuthorizationScope,
    access_role: ResourceAccessRole | None = None,
    platform_role: PlatformRole | None = None,
) -> tuple[str, ...]:
    """Return ordered operations allowed by platform or resource role."""

    normalized_access_role = normalize_resource_role(access_role)
    valid_platform_role = (
        platform_role if isinstance(platform_role, PlatformRole) else None
    )
    allowed: list[str] = []
    for operation, requirement in OPERATION_REQUIREMENTS.items():
        if requirement.scope != scope:
            continue
        if scope == "platform":
            if valid_platform_role is None:
                continue
            if (
                requirement.platform_admin_only
                and valid_platform_role is not PlatformRole.ADMIN
            ):
                continue
        else:
            minimum = requirement.minimum_resource_role
            if (
                minimum is None
                or normalized_access_role is None
                or not role_satisfies(normalized_access_role, minimum)
            ):
                continue
        allowed.append(operation.value)
    return tuple(allowed)


def allowed_platform_operations(
    platform_role: PlatformRole | None,
) -> tuple[str, ...]:
    """Return platform operations allowed by one validated platform role."""

    return _allowed_operations(scope="platform", platform_role=platform_role)


def allowed_workspace_operations(
    access_role: ResourceAccessRole | None,
) -> tuple[str, ...]:
    """Return Workspace operations allowed by one effective resource role."""

    return _allowed_operations(scope="workspace", access_role=access_role)


def allowed_knowledge_base_operations(
    access_role: ResourceAccessRole | None,
) -> tuple[str, ...]:
    """Return Knowledge Base operations allowed by one effective resource role."""

    return _allowed_operations(scope="knowledge_base", access_role=access_role)


def operation_requirements_payload() -> dict[str, object]:
    """Build the committed cross-language snapshot from the fixed policy."""

    return {
        "schemaVersion": 2,
        "requirements": [
            {
                "operationId": operation.value,
                "scope": requirement.scope,
                "minimumResourceRole": (
                    requirement.minimum_resource_role.value
                    if requirement.minimum_resource_role is not None
                    else None
                ),
                "platformAdminOnly": requirement.platform_admin_only,
            }
            for operation, requirement in OPERATION_REQUIREMENTS.items()
        ],
    }


class AuthorizationOperationPolicy:
    """Resolve current platform and resource access in one place."""

    def __init__(
        self,
        db: Session,
        *,
        override_audit_writer: PlatformAdminOverrideAuditWriter | None = None,
    ) -> None:
        self.db = db
        self._workspace_access = WorkspaceAccessResolver(db)
        self._knowledge_base_access = KnowledgeBaseAccessResolver(db)
        self._override_audit_writer = (
            override_audit_writer
            if override_audit_writer is not None
            else IndependentPlatformAdminOverrideAuditWriter()
        )

    def require_platform_operation(
        self,
        actor: AuthorizationActor,
        operation: OperationId,
    ) -> AuthorizationGrant:
        requirement = self._require_scope(operation, "platform")
        verified_actor = self._valid_actor(actor)
        if (
            requirement.platform_admin_only
            and verified_actor.platform_role is not PlatformRole.ADMIN
        ):
            raise AuthorizationOperationError(
                "PLATFORM_AUTHORIZATION_DENIED",
                403,
            )
        return AuthorizationGrant(verified_actor, operation, None)

    def require_workspace_operation(
        self,
        actor: AuthorizationActor,
        workspace_id: str,
        operation: OperationId,
    ) -> AuthorizationGrant:
        from app.db import models as db_models

        requirement = self._require_scope(operation, "workspace")
        verified_actor = self._valid_actor(actor)
        workspace = self.db.get(db_models.Workspace, workspace_id)
        if workspace is None:
            if verified_actor.platform_role is PlatformRole.ADMIN:
                self._write_admin_override_audit(
                    actor=verified_actor,
                    target_type="workspace",
                    target_id=workspace_id,
                    operation=operation,
                    result="failure",
                    error_code="WORKSPACE_ACCESS_DENIED",
                )
            raise AuthorizationOperationError("WORKSPACE_ACCESS_DENIED", 404)
        access = self._workspace_access.resolve(
            workspace=workspace,
            user_id=verified_actor.user_id,
        )
        actual_role = (
            normalize_resource_role(access.access_role) if access is not None else None
        )
        return self._require_resource_role(
            actor=verified_actor,
            operation=operation,
            requirement=requirement,
            actual_role=actual_role,
            actual_sources=access.access_sources if access is not None else (),
            target_type="workspace",
            target_id=workspace_id,
            missing_error_code="WORKSPACE_ACCESS_DENIED",
            denied_error_code="WORKSPACE_OPERATION_DENIED",
        )

    def require_knowledge_base_operation(
        self,
        actor: AuthorizationActor,
        kb_id: str,
        operation: OperationId,
    ) -> AuthorizationGrant:
        from app.db import models as db_models

        requirement = self._require_scope(operation, "knowledge_base")
        verified_actor = self._valid_actor(actor)
        knowledge_base = self.db.get(db_models.KnowledgeBase, kb_id)
        if knowledge_base is None:
            if verified_actor.platform_role is PlatformRole.ADMIN:
                self._write_admin_override_audit(
                    actor=verified_actor,
                    target_type="knowledge_base",
                    target_id=kb_id,
                    operation=operation,
                    result="failure",
                    error_code="KB_ACCESS_DENIED",
                )
            raise AuthorizationOperationError("KB_ACCESS_DENIED", 404)
        access = self._knowledge_base_access.resolve(
            knowledge_base_id=kb_id,
            user_id=verified_actor.user_id,
        )
        return self._require_resource_role(
            actor=verified_actor,
            operation=operation,
            requirement=requirement,
            actual_role=access.access_role if access is not None else None,
            actual_sources=access.access_sources if access is not None else (),
            target_type="knowledge_base",
            target_id=kb_id,
            missing_error_code="KB_ACCESS_DENIED",
            denied_error_code="KB_PERMISSION_DENIED",
        )

    def require_knowledge_base_mount(
        self,
        actor: AuthorizationActor,
        workspace_id: str,
        kb_id: str,
    ) -> AuthorizationGrant:
        """Require Manager for Private KB mounts and implicit Reader for Public KBs."""

        from app.db import models as db_models

        self.require_workspace_operation(
            actor,
            workspace_id,
            OperationId.WORKSPACE_ATTACHMENT_WRITE,
        )
        knowledge_base = self.db.get(db_models.KnowledgeBase, kb_id)
        operation = (
            OperationId.KNOWLEDGE_BASE_DETAIL_READ
            if knowledge_base is not None and knowledge_base.visibility == "public"
            else OperationId.KNOWLEDGE_BASE_CONTENT_WRITE
        )
        return self.require_knowledge_base_operation(
            actor,
            kb_id,
            operation,
        )

    def allowed_workspace_operations(
        self,
        actor: AuthorizationActor,
        workspace_id: str,
    ) -> tuple[str, ...]:
        grant = self.require_workspace_operation(
            actor,
            workspace_id,
            OperationId.WORKSPACE_DETAIL_READ,
        )
        return allowed_workspace_operations(grant.access_role)

    def allowed_knowledge_base_operations(
        self,
        actor: AuthorizationActor,
        kb_id: str,
    ) -> tuple[str, ...]:
        grant = self.require_knowledge_base_operation(
            actor,
            kb_id,
            OperationId.KNOWLEDGE_BASE_DETAIL_READ,
        )
        return allowed_knowledge_base_operations(grant.access_role)

    def _require_resource_role(
        self,
        *,
        actor: AuthorizationActor,
        operation: OperationId,
        requirement: OperationRequirement,
        actual_role: ResourceAccessRole | str | None,
        actual_sources: tuple[ResourceAccessSource, ...],
        target_type: OverrideTargetType,
        target_id: str,
        missing_error_code: str,
        denied_error_code: str,
    ) -> AuthorizationGrant:
        normalized_actual = normalize_resource_role(actual_role)
        effective_role = normalized_actual
        sources = list(dict.fromkeys(actual_sources))
        uses_admin_override = actor.platform_role is PlatformRole.ADMIN and (
            normalized_actual is None
            or not role_satisfies(
                normalized_actual,
                ResourceAccessRole.MANAGER,
            )
        )
        if uses_admin_override:
            if ResourceAccessSource.PLATFORM_ADMIN not in sources:
                sources.append(ResourceAccessSource.PLATFORM_ADMIN)
            effective_role = ResourceAccessRole.MANAGER
        elif effective_role is None:
            raise AuthorizationOperationError(missing_error_code, 404)

        minimum = requirement.minimum_resource_role
        if (
            minimum is None
            or effective_role is None
            or not role_satisfies(effective_role, minimum)
        ):
            if uses_admin_override:
                self._write_admin_override_audit(
                    actor=actor,
                    target_type=target_type,
                    target_id=target_id,
                    operation=operation,
                    result="failure",
                    error_code=denied_error_code,
                )
            raise AuthorizationOperationError(denied_error_code, 403)

        primary_source = AuthorizationOperationPolicy._primary_source(
            effective_role=effective_role,
            actual_role=normalized_actual,
            sources=tuple(sources),
        )
        grant = AuthorizationGrant(
            actor=actor,
            operation=operation,
            access_role=effective_role,
            access_source=primary_source,
            access_sources=tuple(sources),
        )
        if uses_admin_override:
            self._write_admin_override_audit(
                actor=actor,
                target_type=target_type,
                target_id=target_id,
                operation=operation,
                result="success",
                error_code=None,
            )
        return grant

    def _write_admin_override_audit(
        self,
        *,
        actor: AuthorizationActor,
        target_type: OverrideTargetType,
        target_id: str,
        operation: OperationId,
        result: Literal["success", "failure"],
        error_code: str | None,
    ) -> None:
        self._override_audit_writer.write(
            PlatformAdminOverrideAuditRecord(
                actor_user_id=actor.user_id,
                target_type=target_type,
                target_id=target_id,
                operation=operation.value,
                result=result,
                error_code=error_code,
            )
        )

    @staticmethod
    def _primary_source(
        *,
        effective_role: ResourceAccessRole,
        actual_role: ResourceAccessRole | None,
        sources: tuple[ResourceAccessSource, ...],
    ) -> ResourceAccessSource | None:
        if actual_role is ResourceAccessRole.OWNER:
            return ResourceAccessSource.OWNED
        if (
            ResourceAccessSource.PLATFORM_ADMIN in sources
            and effective_role is not actual_role
        ):
            return ResourceAccessSource.PLATFORM_ADMIN
        return sources[0] if sources else None

    @staticmethod
    def _valid_actor(actor: AuthorizationActor) -> AuthorizationActor:
        if not isinstance(actor, AuthorizationActor):
            raise AuthorizationOperationError(
                "PLATFORM_AUTHORIZATION_DENIED",
                401,
            )
        return actor

    @staticmethod
    def _require_scope(
        operation: OperationId,
        expected_scope: AuthorizationScope,
    ) -> OperationRequirement:
        if not isinstance(operation, OperationId):
            raise AuthorizationOperationError(
                "PLATFORM_AUTHORIZATION_DENIED",
                403,
            )
        requirement = OPERATION_REQUIREMENTS.get(operation)
        if requirement is None or requirement.scope != expected_scope:
            raise AuthorizationOperationError(
                "PLATFORM_AUTHORIZATION_DENIED",
                403,
            )
        return requirement


__all__ = [
    "AuthorizationScope",
    "AuthorizationGrant",
    "AuthorizationOperationError",
    "AuthorizationOperationPolicy",
    "OPERATION_REQUIREMENTS",
    "OperationId",
    "OperationRequirement",
    "allowed_knowledge_base_operations",
    "allowed_platform_operations",
    "allowed_workspace_operations",
    "operation_requirements_payload",
]
