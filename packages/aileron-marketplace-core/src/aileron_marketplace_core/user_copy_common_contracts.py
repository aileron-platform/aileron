"""Shared wire primitives for package-format User Copy projections."""

from __future__ import annotations

from typing import Any, Literal, Mapping, Optional, TypeVar

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .resource_resolution import (
    PackageSourceError,
    validate_logical_target_locator,
    validate_source_locator,
    validate_wire_identity,
)

UserCopyPlanResourceType = Literal[
    "instructions",
    "skill",
    "subagent",
    "command",
    "output-style",
    "prompt",
    "rule",
    "mcp",
    "hook",
    "dependency-payload",
    "extension",
    "component",
]
UserCopyBlockingCode = Literal[
    "marketplace.user_copy.inventory_unavailable",
    "marketplace.user_copy.duplicate_target",
    "marketplace.user_copy.dependency_payload_unprojectable",
    "marketplace.user_copy.effective_identity_conflict",
    "marketplace.user_copy.profile_empty",
    "marketplace.user_copy.target_not_writable",
    "marketplace.user_copy.target_unsafe",
    "marketplace.user_copy.target_document_invalid",
    "marketplace.user_copy.profile_invalid",
    "marketplace.user_copy.source_reference_invalid",
    "marketplace.user_copy.source_not_allowed",
    "marketplace.user_copy.source_document_invalid",
    "marketplace.user_copy.source_missing",
    "marketplace.user_copy.duplicate_resource_id",
    "marketplace.user_copy.unsupported_resource",
    "marketplace.user_copy.projection_not_supported",
]

MAX_USER_COPY_ITEMS = 500
MAX_USER_COPY_FIELD_LENGTH = 1024
ContractModel = TypeVar("ContractModel", bound="UserCopyContractModel")


class UserCopyContractModel(BaseModel):
    """Strict model with canonical wire serialization."""

    model_config = ConfigDict(populate_by_name=True, extra="forbid", strict=True)

    @classmethod
    def from_wire(
        cls: type[ContractModel], payload: Mapping[str, Any]
    ) -> ContractModel:
        return cls.model_validate(payload)

    def to_wire(self, *, exclude_unset: bool = False) -> dict[str, Any]:
        return self.model_dump(by_alias=True, mode="json", exclude_unset=exclude_unset)

    def to_wire_json(self) -> str:
        return self.model_dump_json(by_alias=True)


def _source_locator(value: str) -> str:
    try:
        return validate_source_locator(value)
    except PackageSourceError as exc:
        raise ValueError("marketplace.user_copy.profile_invalid") from exc


def _target_locator(value: str) -> str:
    try:
        return validate_logical_target_locator(value)
    except PackageSourceError as exc:
        raise ValueError("marketplace.user_copy.runtime_contract_invalid") from exc


def _identity(value: str) -> str:
    try:
        return validate_wire_identity(value)
    except PackageSourceError as exc:
        raise ValueError("marketplace.user_copy.runtime_contract_invalid") from exc


class UserCopyOverwriteApprovalContract(UserCopyContractModel):
    """Exact approval for one preflight conflict."""

    target_identity: str = Field(
        alias="targetIdentity", min_length=1, max_length=MAX_USER_COPY_FIELD_LENGTH
    )
    expected_revision: str = Field(alias="expectedRevision", pattern=r"^[0-9a-f]{64}$")

    @field_validator("target_identity")
    @classmethod
    def validate_target_identity(cls, value: str) -> str:
        return _identity(value)


class UserCopyPlanResourceContract(UserCopyContractModel):
    """Sanitized one-shot source-to-target projection."""

    resource_type: UserCopyPlanResourceType = Field(alias="resourceType")
    resource_id: str = Field(
        alias="resourceId", min_length=1, max_length=MAX_USER_COPY_FIELD_LENGTH
    )
    source_locator: str = Field(
        alias="sourceLocator", min_length=1, max_length=MAX_USER_COPY_FIELD_LENGTH
    )
    target_locator: str = Field(
        alias="targetLocator", min_length=1, max_length=MAX_USER_COPY_FIELD_LENGTH
    )
    target_identity: str = Field(
        alias="targetIdentity", min_length=1, max_length=MAX_USER_COPY_FIELD_LENGTH
    )
    action: Literal["create", "merge", "unchanged"]
    incoming_digest: str = Field(alias="incomingDigest", pattern=r"^[0-9a-f]{64}$")

    @field_validator("resource_id", "target_identity")
    @classmethod
    def validate_identity(cls, value: str) -> str:
        return _identity(value)

    @field_validator("source_locator")
    @classmethod
    def validate_source_locator(cls, value: str) -> str:
        return _source_locator(value)

    @field_validator("target_locator")
    @classmethod
    def validate_target_locator(cls, value: str) -> str:
        return _target_locator(value)


class UserCopyConflictContract(UserCopyContractModel):
    """One exact overwrite-confirmation item."""

    code: Literal["marketplace.user_copy.target_conflict"]
    resource_type: UserCopyPlanResourceType = Field(alias="resourceType")
    resource_id: str = Field(
        alias="resourceId", min_length=1, max_length=MAX_USER_COPY_FIELD_LENGTH
    )
    source_locator: str = Field(
        alias="sourceLocator", min_length=1, max_length=MAX_USER_COPY_FIELD_LENGTH
    )
    target_locator: str = Field(
        alias="targetLocator", min_length=1, max_length=MAX_USER_COPY_FIELD_LENGTH
    )
    target_identity: str = Field(
        alias="targetIdentity", min_length=1, max_length=MAX_USER_COPY_FIELD_LENGTH
    )
    baseline_revision: str = Field(alias="baselineRevision", pattern=r"^[0-9a-f]{64}$")
    incoming_digest: str = Field(alias="incomingDigest", pattern=r"^[0-9a-f]{64}$")
    overwritable: Literal[True] = True

    @field_validator("overwritable", mode="before")
    @classmethod
    def validate_overwritable(cls, value: Any) -> Any:
        if type(value) is not bool or value is not True:
            raise ValueError("marketplace.user_copy.runtime_contract_invalid")
        return value

    @field_validator("resource_id", "target_identity")
    @classmethod
    def validate_identity(cls, value: str) -> str:
        return _identity(value)

    @field_validator("source_locator")
    @classmethod
    def validate_source_locator(cls, value: str) -> str:
        return _source_locator(value)

    @field_validator("target_locator")
    @classmethod
    def validate_target_locator(cls, value: str) -> str:
        return _target_locator(value)


class UserCopyBlockingIssueContract(UserCopyContractModel):
    """One non-overridable one-shot preflight issue."""

    code: UserCopyBlockingCode
    resource_type: Optional[str] = Field(
        default=None,
        alias="resourceType",
        min_length=1,
        max_length=MAX_USER_COPY_FIELD_LENGTH,
    )
    resource_id: Optional[str] = Field(
        default=None,
        alias="resourceId",
        min_length=1,
        max_length=MAX_USER_COPY_FIELD_LENGTH,
    )
    source_locator: Optional[str] = Field(
        default=None,
        alias="sourceLocator",
        min_length=1,
        max_length=MAX_USER_COPY_FIELD_LENGTH,
    )
    target_locator: Optional[str] = Field(
        default=None,
        alias="targetLocator",
        min_length=1,
        max_length=MAX_USER_COPY_FIELD_LENGTH,
    )

    @field_validator("resource_type", "resource_id")
    @classmethod
    def validate_identities(cls, value: Optional[str]) -> Optional[str]:
        return _identity(value) if value is not None else None

    @field_validator("source_locator")
    @classmethod
    def validate_source_locator(cls, value: Optional[str]) -> Optional[str]:
        return _source_locator(value) if value is not None else None

    @field_validator("target_locator")
    @classmethod
    def validate_target_locator(cls, value: Optional[str]) -> Optional[str]:
        return _target_locator(value) if value is not None else None


__all__ = [
    "MAX_USER_COPY_FIELD_LENGTH",
    "MAX_USER_COPY_ITEMS",
    "UserCopyBlockingCode",
    "UserCopyBlockingIssueContract",
    "UserCopyConflictContract",
    "UserCopyContractModel",
    "UserCopyOverwriteApprovalContract",
    "UserCopyPlanResourceContract",
    "UserCopyPlanResourceType",
]
