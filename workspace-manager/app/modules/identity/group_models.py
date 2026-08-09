"""User group API contracts."""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import ConfigDict, Field, field_validator, model_validator

from app.modules.identity.admin_models import AccountState, PlatformRole, RoleStatus
from app.core.pydantic import CamelModel


class UserGroup(CamelModel):
    id: str
    name: str
    description: Optional[str] = None
    member_count: int = Field(..., alias="memberCount")
    knowledge_base_share_count: int = Field(..., alias="knowledgeBaseShareCount")
    created_at: datetime = Field(..., alias="createdAt")
    updated_at: datetime = Field(..., alias="updatedAt")


class UserGroupListResponse(CamelModel):
    items: list[UserGroup]
    total: int
    page: int
    page_size: int = Field(..., alias="pageSize")


class UserGroupCreateRequest(CamelModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("name must not be blank")
        return normalized

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip() or None


class UserGroupPatchRequest(CamelModel):
    model_config = ConfigDict(extra="forbid")

    name: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str | None) -> str:
        if value is None or not value.strip():
            raise ValueError("name must not be blank")
        return value.strip()

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip() or None

    @model_validator(mode="after")
    def require_patch_field(self) -> "UserGroupPatchRequest":
        if not self.model_fields_set.intersection({"name", "description"}):
            raise ValueError("at least one field is required")
        return self


class UserGroupMember(CamelModel):
    user_id: str = Field(..., alias="userId")
    username: str
    email: Optional[str] = None
    first_name: Optional[str] = Field(None, alias="firstName")
    last_name: Optional[str] = Field(None, alias="lastName")
    enabled: bool
    account_state: AccountState = Field(..., alias="accountState")
    role: Optional[PlatformRole] = None
    role_status: RoleStatus = Field(..., alias="roleStatus")
    source: Literal["manual"] = "manual"
    joined_at: datetime = Field(..., alias="joinedAt")
    updated_at: datetime = Field(..., alias="updatedAt")


class UserGroupMemberCandidate(CamelModel):
    user_id: str = Field(..., alias="userId")
    username: str
    email: Optional[str] = None
    first_name: Optional[str] = Field(None, alias="firstName")
    last_name: Optional[str] = Field(None, alias="lastName")
    enabled: bool
    account_state: AccountState = Field(..., alias="accountState")
    role: Optional[PlatformRole] = None
    role_status: RoleStatus = Field(..., alias="roleStatus")
    membership_status: Literal["member", "not_member"] = Field(
        ..., alias="membershipStatus"
    )
    created_at: datetime = Field(..., alias="createdAt")
    updated_at: datetime = Field(..., alias="updatedAt")


class UserGroupMemberListResponse(CamelModel):
    items: list[UserGroupMember]
    total: int
    page: int
    page_size: int = Field(..., alias="pageSize")


class UserGroupMemberCandidateListResponse(CamelModel):
    items: list[UserGroupMemberCandidate]
    total: int
    page: int
    page_size: int = Field(..., alias="pageSize")


class UserGroupMemberMutationRequest(CamelModel):
    model_config = ConfigDict(extra="forbid")

    user_ids: list[str] = Field(..., alias="userIds", min_length=1, max_length=100)

    @field_validator("user_ids")
    @classmethod
    def validate_user_ids(cls, value: list[str]) -> list[str]:
        if len(set(value)) != len(value):
            raise ValueError("userIds must be unique")
        if any(not user_id or user_id.strip() != user_id for user_id in value):
            raise ValueError("userIds must contain non-empty local user ids")
        return value


class UserGroupMemberFailure(CamelModel):
    user_id: str = Field(..., alias="userId")
    error_code: str = Field(..., alias="errorCode")


class UserGroupMemberAddResponse(CamelModel):
    added_user_ids: list[str] = Field(default_factory=list, alias="addedUserIds")
    skipped_user_ids: list[str] = Field(default_factory=list, alias="skippedUserIds")
    failed_users: list[UserGroupMemberFailure] = Field(
        default_factory=list, alias="failedUsers"
    )


class UserGroupMemberRemoveResponse(CamelModel):
    removed_user_ids: list[str] = Field(default_factory=list, alias="removedUserIds")
    skipped_user_ids: list[str] = Field(default_factory=list, alias="skippedUserIds")
    failed_users: list[UserGroupMemberFailure] = Field(
        default_factory=list, alias="failedUsers"
    )
