"""Provider-neutral administrator user DTOs."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, cast

from pydantic import Field

from app.core.pydantic import CamelModel
from app.db import models as db_models
from app.modules.identity.platform_role import PlatformRole, normalize_platform_role

RoleStatus = Literal["valid", "missing", "multiple"]
RoleIssue = Literal["missing_platform_role", "multiple_platform_roles"]
AccountState = Literal[
    "active",
    "local_disabled",
    "identity_disabled",
    "sync_failed",
    "shadow_missing",
]
SyncStatus = Literal[
    "synced",
    "local_shadow_imported",
    "local_shadow_missing",
    "identity_sync_failed",
]

PLATFORM_ROLE_ORDER: tuple[PlatformRole, ...] = (
    PlatformRole.ADMIN,
    PlatformRole.MEMBER,
)
ROLE_STATUS_VALUES = frozenset({"valid", "missing", "multiple"})
ACCOUNT_STATE_VALUES = frozenset(
    {
        "active",
        "local_disabled",
        "identity_disabled",
        "sync_failed",
        "shadow_missing",
    }
)


class AdminUser(CamelModel):
    id: str
    issuer: str | None = None
    subject: str | None = None
    username: str
    email: str | None = None
    first_name: str | None = Field(None, alias="firstName")
    last_name: str | None = Field(None, alias="lastName")
    enabled: bool
    local_active: bool = Field(..., alias="localActive")
    identity_enabled: bool = Field(..., alias="identityEnabled")
    account_state: AccountState = Field(..., alias="accountState")
    role: PlatformRole | None = None
    role_status: RoleStatus
    role_issues: list[RoleIssue] = Field(default_factory=list, alias="roleIssues")
    sync_status: SyncStatus = Field(..., alias="syncStatus")
    created_at: datetime = Field(..., alias="createdAt")
    updated_at: datetime = Field(..., alias="updatedAt")


class AdminUserListResponse(CamelModel):
    items: list[AdminUser]
    total: int
    page: int
    page_size: int = Field(..., alias="pageSize")


class AdminRoleOption(CamelModel):
    id: PlatformRole
    label_key: str = Field(..., alias="labelKey")
    description_key: str = Field(..., alias="descriptionKey")


class AdminRoleListResponse(CamelModel):
    items: list[AdminRoleOption]


class AdminUserRoleRequest(CamelModel):
    role: PlatformRole


def derive_account_state(user: db_models.User | None) -> AccountState:
    if user is None or user.sync_status == "local_shadow_missing":
        return "shadow_missing"
    if user.sync_status == "identity_sync_failed":
        return "sync_failed"
    if not user.is_active:
        return "local_disabled"
    if not user.identity_enabled:
        return "identity_disabled"
    return "active"


def admin_user_from_model(user: Any) -> AdminUser:
    role = normalize_platform_role(user.platform_role)
    return AdminUser(
        id=user.id,
        issuer=user.oidc_issuer,
        subject=user.oidc_subject,
        username=user.username,
        email=user.email,
        firstName=user.first_name,
        lastName=user.last_name,
        enabled=(
            user.is_active
            and user.identity_enabled
            and user.sync_status in {"synced", "local_shadow_imported"}
        ),
        localActive=user.is_active,
        identityEnabled=user.identity_enabled,
        accountState=derive_account_state(user),
        role=role,
        roleStatus=user.role_status,
        roleIssues=cast(list[RoleIssue], list(user.role_issues)),
        syncStatus=user.sync_status,
        createdAt=user.created_at,
        updatedAt=user.updated_at,
    )


__all__ = [
    "ACCOUNT_STATE_VALUES",
    "PLATFORM_ROLE_ORDER",
    "ROLE_STATUS_VALUES",
    "AdminRoleListResponse",
    "AdminRoleOption",
    "AdminUser",
    "AdminUserListResponse",
    "AdminUserRoleRequest",
    "admin_user_from_model",
]
