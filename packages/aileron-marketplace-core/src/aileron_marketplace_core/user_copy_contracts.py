"""Typed wire contract for one-shot Marketplace user-copy operations."""

from __future__ import annotations

import json
from typing import Any, Literal, Mapping, Optional, TypeVar

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .resource_resolution import (
    PackageSourceError,
    validate_logical_target_locator,
    validate_source_locator,
    validate_wire_identity,
)
from .user_copy_profiles import (
    USER_COPY_PAYLOAD_ROOT_SENTINEL,
    BlockedUserCopyResource,
    UserCopyBlockReason,
    UserCopyProfile,
    UserCopyResource,
    UserCopyResourceType,
    UserCopySemantics,
    UserCopySourceKind,
    UserCopyTargetResource,
    user_copy_source_digest_from_preview,
)

MarketplaceProvider = Literal["claude-code", "codex"]
UserCopyProfileResourceType = Literal[
    "instructions",
    "skill",
    "subagent",
    "command",
    "output-style",
    "prompt",
    "rule",
    "mcp",
    "hook",
]
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
]
UserCopyTargetResourceName = Literal[
    "agents_md",
    "claude_md",
    "skills",
    "subagents",
    "commands",
    "output_styles",
    "prompts",
    "rules",
    "mcp",
    "hooks",
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
    "marketplace.user_copy.unsupported_resource",
]

MAX_USER_COPY_ITEMS = 500
MAX_USER_COPY_FIELD_LENGTH = 1024
MAX_USER_COPY_PREVIEW_BYTES = 2 * 1024 * 1024

ContractModel = TypeVar("ContractModel", bound="UserCopyContractModel")


class UserCopyContractError(ValueError):
    """Fail-closed proof mismatch at the Manager/Runtime seam."""


class UserCopyContractModel(BaseModel):
    """Strict model with canonical wire serialization."""

    model_config = ConfigDict(
        populate_by_name=True,
        extra="forbid",
        strict=True,
    )

    @classmethod
    def from_wire(
        cls: type[ContractModel],
        payload: Mapping[str, Any],
    ) -> ContractModel:
        return cls.model_validate(payload)

    def to_wire(self, *, exclude_unset: bool = False) -> dict[str, Any]:
        return self.model_dump(
            by_alias=True,
            mode="json",
            exclude_unset=exclude_unset,
        )

    def to_wire_json(self) -> str:
        return self.model_dump_json(by_alias=True)


def _validate_source_locator(value: str) -> str:
    try:
        return validate_source_locator(value)
    except PackageSourceError as exc:
        raise ValueError("marketplace.user_copy.profile_invalid") from exc


def _validate_target_locator(value: str) -> str:
    try:
        return validate_logical_target_locator(value)
    except PackageSourceError as exc:
        raise ValueError("marketplace.user_copy.runtime_contract_invalid") from exc


def _validate_identity(value: str) -> str:
    try:
        return validate_wire_identity(value)
    except PackageSourceError as exc:
        raise ValueError("marketplace.user_copy.runtime_contract_invalid") from exc


def _validate_profile_version(value: Any) -> Any:
    if type(value) is not int or value != 1:
        raise ValueError("marketplace.user_copy.profile_invalid")
    return value


def _validate_structured_value_template(value: Any) -> frozenset[str]:
    node_count = 0
    payload_locators: set[str] = set()

    def visit(current: Any, depth: int) -> None:
        nonlocal node_count
        node_count += 1
        if depth > 32 or node_count > 2_000:
            raise ValueError("marketplace.user_copy.profile_invalid")
        if isinstance(current, dict):
            for key, child in current.items():
                if (
                    not isinstance(key, str)
                    or USER_COPY_PAYLOAD_ROOT_SENTINEL in key
                    or len(key.encode("utf-8")) > 16 * 1024
                ):
                    raise ValueError("marketplace.user_copy.profile_invalid")
                visit(child, depth + 1)
            return
        if isinstance(current, list):
            for child in current:
                visit(child, depth + 1)
            return
        if isinstance(current, str):
            if len(current.encode("utf-8")) > 16 * 1024:
                raise ValueError("marketplace.user_copy.profile_invalid")
            if USER_COPY_PAYLOAD_ROOT_SENTINEL in current:
                prefix = f"{USER_COPY_PAYLOAD_ROOT_SENTINEL}/"
                if (
                    not current.startswith(prefix)
                    or current.count(USER_COPY_PAYLOAD_ROOT_SENTINEL) != 1
                ):
                    raise ValueError("marketplace.user_copy.profile_invalid")
                payload_locators.add(
                    _validate_source_locator(current.removeprefix(prefix))
                )
            return
        if current is None or type(current) in {bool, int, float}:
            return
        raise ValueError("marketplace.user_copy.profile_invalid")

    visit(value, 0)
    try:
        encoded = json.dumps(
            value,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ValueError("marketplace.user_copy.profile_invalid") from exc
    if len(encoded) > 256 * 1024:
        raise ValueError("marketplace.user_copy.profile_invalid")
    return frozenset(payload_locators)


def _structured_json_type(value: Any) -> str:
    if value is None:
        return "null"
    if type(value) is bool:
        return "boolean"
    if isinstance(value, dict):
        return "object"
    if isinstance(value, list):
        return "array"
    if isinstance(value, str):
        return "string"
    if type(value) in {int, float}:
        return "number"
    raise ValueError("marketplace.user_copy.profile_invalid")


class MarketplaceUserCopyProfileResourcePreview(UserCopyContractModel):
    """Manager-derived source profile used only for read-only preflight."""

    resource_type: UserCopyProfileResourceType = Field(alias="resourceType")
    resource_id: str = Field(
        alias="resourceId",
        min_length=1,
        max_length=MAX_USER_COPY_FIELD_LENGTH,
    )
    source_kind: Literal["plugin-component", "copy-convention"] = Field(
        alias="sourceKind"
    )
    source_locator: str = Field(
        alias="sourceLocator",
        min_length=1,
        max_length=MAX_USER_COPY_FIELD_LENGTH,
    )
    target_resource: UserCopyTargetResourceName = Field(alias="targetResource")
    copy_semantics: Literal[
        "create-file",
        "create-directory",
        "merge-config-entry",
    ] = Field(alias="copySemantics")
    relative_target: Optional[str] = Field(
        default=None,
        alias="relativeTarget",
        max_length=MAX_USER_COPY_FIELD_LENGTH,
    )
    json_pointer: Optional[str] = Field(
        default=None,
        alias="jsonPointer",
        max_length=MAX_USER_COPY_FIELD_LENGTH,
    )
    source_digest: str = Field(alias="sourceDigest", pattern=r"^[0-9a-f]{64}$")
    dependency_payload_required: bool = Field(alias="dependencyPayloadRequired")
    dependency_payload_projectable: bool = Field(alias="dependencyPayloadProjectable")
    structured_value_type: Optional[
        Literal["object", "array", "string", "number", "boolean", "null"]
    ] = Field(default=None, alias="structuredValueType")
    structured_value_template: Optional[Any] = Field(
        default=None,
        alias="structuredValueTemplate",
    )

    @field_validator("resource_id")
    @classmethod
    def validate_resource_id(cls, value: str) -> str:
        return _validate_identity(value)

    @field_validator("source_locator")
    @classmethod
    def validate_source_locator(cls, value: str) -> str:
        return _validate_source_locator(value)

    @field_validator("relative_target")
    @classmethod
    def validate_relative_target(cls, value: Optional[str]) -> Optional[str]:
        return _validate_source_locator(value) if value is not None else None

    @model_validator(mode="after")
    def validate_semantics(self) -> "MarketplaceUserCopyProfileResourcePreview":
        if (self.copy_semantics == "merge-config-entry") != (
            self.structured_value_type is not None
        ):
            raise ValueError("marketplace.user_copy.profile_invalid")
        template_required = (
            self.copy_semantics == "merge-config-entry"
            and self.dependency_payload_required
            and self.dependency_payload_projectable
        )
        template_present = "structured_value_template" in self.model_fields_set
        if template_required != template_present:
            raise ValueError("marketplace.user_copy.profile_invalid")
        if self.copy_semantics != "merge-config-entry" and (
            self.dependency_payload_required or not self.dependency_payload_projectable
        ):
            raise ValueError("marketplace.user_copy.profile_invalid")
        if (
            not self.dependency_payload_required
            and not self.dependency_payload_projectable
        ):
            raise ValueError("marketplace.user_copy.profile_invalid")
        if template_present:
            payload_locators = _validate_structured_value_template(
                self.structured_value_template
            )
            if (
                _structured_json_type(self.structured_value_template)
                != self.structured_value_type
                or not payload_locators
            ):
                raise ValueError("marketplace.user_copy.profile_invalid")
        return self


class MarketplaceBlockedUserCopyResourcePreview(UserCopyContractModel):
    """Sanitized unsupported source found in the Manager snapshot."""

    resource_type: str = Field(alias="resourceType", min_length=1, max_length=64)
    source_locator: str = Field(
        alias="sourceLocator",
        min_length=1,
        max_length=MAX_USER_COPY_FIELD_LENGTH,
    )
    reason: Literal[
        "source-not-allowed",
        "source-reference-invalid",
        "source-document-invalid",
        "source-missing",
        "duplicate-resource-id",
        "unsupported-resource",
    ]

    @field_validator("resource_type")
    @classmethod
    def validate_resource_type(cls, value: str) -> str:
        return _validate_identity(value)

    @field_validator("source_locator")
    @classmethod
    def validate_source_locator(cls, value: str) -> str:
        return _validate_source_locator(value)


class MarketplaceDependencyPayloadPreview(UserCopyContractModel):
    """Exact dependency payload proof bound into the sparse source digest."""

    source_locator: str = Field(
        alias="sourceLocator",
        min_length=1,
        max_length=MAX_USER_COPY_FIELD_LENGTH,
    )
    source_kind: Literal["file", "directory"] = Field(alias="sourceKind")
    content_digest: str = Field(alias="contentDigest", pattern=r"^[0-9a-f]{64}$")

    @field_validator("source_locator")
    @classmethod
    def validate_source_locator(cls, value: str) -> str:
        return _validate_source_locator(value)


class MarketplaceUserCopyProfilePreview(UserCopyContractModel):
    """Canonical non-authoritative source proof sent to Runtime."""

    profile_version: Literal[1] = Field(alias="profileVersion")
    provider: MarketplaceProvider
    profile_digest: str = Field(alias="profileDigest", pattern=r"^[0-9a-f]{64}$")
    resources: list[MarketplaceUserCopyProfileResourcePreview] = Field(
        max_length=MAX_USER_COPY_ITEMS
    )
    dependency_payloads: list[MarketplaceDependencyPayloadPreview] = Field(
        alias="dependencyPayloads",
        max_length=MAX_USER_COPY_ITEMS,
    )
    blocked_resources: list[MarketplaceBlockedUserCopyResourcePreview] = Field(
        default_factory=list,
        alias="blockedResources",
        max_length=MAX_USER_COPY_ITEMS,
    )

    @field_validator("profile_version", mode="before")
    @classmethod
    def validate_profile_version(cls, value: Any) -> Any:
        return _validate_profile_version(value)

    @model_validator(mode="after")
    def validate_proof(self) -> "MarketplaceUserCopyProfilePreview":
        if (
            len(self.resources)
            + len(self.dependency_payloads)
            + len(self.blocked_resources)
            > MAX_USER_COPY_ITEMS
        ):
            raise ValueError("marketplace.user_copy.profile_invalid")

        resource_sort_keys = [
            (
                resource.resource_type,
                resource.resource_id,
                resource.source_locator,
                resource.json_pointer or "",
            )
            for resource in self.resources
        ]
        resource_identities = [
            (resource.resource_type, resource.resource_id.casefold())
            for resource in self.resources
        ]
        if resource_sort_keys != sorted(resource_sort_keys) or len(
            set(resource_identities)
        ) != len(resource_identities):
            raise ValueError("marketplace.user_copy.profile_invalid")

        blocked_sort_keys = [
            (resource.resource_type, resource.source_locator, resource.reason)
            for resource in self.blocked_resources
        ]
        if blocked_sort_keys != sorted(blocked_sort_keys) or len(
            set(blocked_sort_keys)
        ) != len(blocked_sort_keys):
            raise ValueError("marketplace.user_copy.profile_invalid")

        locators = [payload.source_locator for payload in self.dependency_payloads]
        if locators != sorted(locators) or len(
            {locator.casefold() for locator in locators}
        ) != len(locators):
            raise ValueError("marketplace.user_copy.profile_invalid")
        if any(
            any(
                later.casefold().startswith(f"{locator.casefold()}/")
                for later in locators[index + 1 :]
            )
            for index, locator in enumerate(locators)
        ):
            raise ValueError("marketplace.user_copy.profile_invalid")

        referenced_locators: set[str] = set()
        for resource in self.resources:
            if "structured_value_template" in resource.model_fields_set:
                referenced_locators.update(
                    _validate_structured_value_template(
                        resource.structured_value_template
                    )
                )
        payloads_by_locator = {
            payload.source_locator: payload for payload in self.dependency_payloads
        }
        if bool(payloads_by_locator) != bool(referenced_locators):
            raise ValueError("marketplace.user_copy.profile_invalid")
        for referenced in referenced_locators:
            if not any(
                referenced == locator
                or (
                    payload.source_kind == "directory"
                    and referenced.startswith(f"{locator}/")
                )
                for locator, payload in payloads_by_locator.items()
            ):
                raise ValueError("marketplace.user_copy.profile_invalid")
        for locator, payload in payloads_by_locator.items():
            if not any(
                referenced == locator
                or (
                    payload.source_kind == "directory"
                    and referenced.startswith(f"{locator}/")
                )
                for referenced in referenced_locators
            ):
                raise ValueError("marketplace.user_copy.profile_invalid")

        encoded = json.dumps(
            self.to_wire(exclude_unset=True),
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
            allow_nan=False,
        ).encode("utf-8")
        if len(encoded) > MAX_USER_COPY_PREVIEW_BYTES:
            raise ValueError("marketplace.user_copy.profile_invalid")
        return self

    @property
    def source_digest(self) -> str:
        return user_copy_source_digest_from_preview(self.to_wire(exclude_unset=True))

    def to_profile(self) -> UserCopyProfile:
        return UserCopyProfile(
            profile_version=self.profile_version,
            provider=self.provider,
            resources=tuple(
                UserCopyResource(
                    resource_type=UserCopyResourceType(resource.resource_type),
                    resource_id=resource.resource_id,
                    source_kind=UserCopySourceKind(resource.source_kind),
                    source_locator=resource.source_locator,
                    target_resource=UserCopyTargetResource(resource.target_resource),
                    copy_semantics=UserCopySemantics(resource.copy_semantics),
                    relative_target=resource.relative_target,
                    json_pointer=resource.json_pointer,
                )
                for resource in self.resources
            ),
            blocked_resources=tuple(
                BlockedUserCopyResource(
                    resource_type=resource.resource_type,
                    source_locator=resource.source_locator,
                    reason=UserCopyBlockReason(resource.reason),
                )
                for resource in self.blocked_resources
            ),
        )


class UserCopyOverwriteApprovalContract(UserCopyContractModel):
    """Exact approval for one preflight conflict."""

    target_identity: str = Field(
        alias="targetIdentity",
        min_length=1,
        max_length=MAX_USER_COPY_FIELD_LENGTH,
    )
    expected_revision: str = Field(
        alias="expectedRevision",
        pattern=r"^[0-9a-f]{64}$",
    )

    @field_validator("target_identity")
    @classmethod
    def validate_target_identity(cls, value: str) -> str:
        return _validate_identity(value)


class UserCopyPreflightRequestContract(UserCopyContractModel):
    """Read-only one-shot user-copy target preflight."""

    provider: MarketplaceProvider
    package_id: str = Field(
        alias="packageId",
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$",
    )
    revision: str = Field(pattern=r"^[0-9a-f]{64}$")
    workspace_id: str = Field(alias="workspaceId", min_length=1, max_length=255)
    runtime_instance_id: str = Field(
        alias="runtimeInstanceId",
        pattern=(
            r"^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-"
            r"[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
        ),
    )
    expected_source_digest: str = Field(
        alias="expectedSourceDigest",
        pattern=r"^[0-9a-f]{64}$",
    )
    expected_profile_version: Literal[1] = Field(alias="expectedProfileVersion")
    expected_profile_digest: str = Field(
        alias="expectedProfileDigest",
        pattern=r"^[0-9a-f]{64}$",
    )
    profile_preview: MarketplaceUserCopyProfilePreview = Field(
        alias="userCopyProfilePreview"
    )

    @field_validator("expected_profile_version", mode="before")
    @classmethod
    def validate_expected_profile_version(cls, value: Any) -> Any:
        return _validate_profile_version(value)

    @model_validator(mode="after")
    def validate_profile_proof(self) -> "UserCopyPreflightRequestContract":
        if (
            self.profile_preview.provider != self.provider
            or self.profile_preview.profile_version != self.expected_profile_version
            or self.profile_preview.profile_digest != self.expected_profile_digest
            or self.profile_preview.source_digest != self.expected_source_digest
        ):
            raise ValueError("marketplace.user_copy.profile_mismatch")
        return self

    def verify_response(
        self,
        response: "UserCopyPreflightResultContract",
        *,
        provider_state_root_id: str,
    ) -> None:
        expected = (
            response.provider == self.provider
            and response.package_id == self.package_id
            and response.revision == self.revision
            and response.workspace_id == self.workspace_id
            and response.runtime_instance_id == self.runtime_instance_id
            and response.provider_state_root_id == provider_state_root_id
            and response.source_digest == self.expected_source_digest
            and response.profile_version == self.expected_profile_version
            and response.profile_digest == self.expected_profile_digest
        )
        if not expected:
            raise UserCopyContractError(
                "marketplace.user_copy.runtime_contract_invalid"
            )


class UserCopyPlanResourceContract(UserCopyContractModel):
    """Sanitized one-shot source-to-target projection."""

    resource_type: UserCopyPlanResourceType = Field(alias="resourceType")
    resource_id: str = Field(
        alias="resourceId",
        min_length=1,
        max_length=MAX_USER_COPY_FIELD_LENGTH,
    )
    source_locator: str = Field(
        alias="sourceLocator",
        min_length=1,
        max_length=MAX_USER_COPY_FIELD_LENGTH,
    )
    target_locator: str = Field(
        alias="targetLocator",
        min_length=1,
        max_length=MAX_USER_COPY_FIELD_LENGTH,
    )
    target_identity: str = Field(
        alias="targetIdentity",
        min_length=1,
        max_length=MAX_USER_COPY_FIELD_LENGTH,
    )
    action: Literal["create", "merge", "unchanged"]
    incoming_digest: str = Field(
        alias="incomingDigest",
        pattern=r"^[0-9a-f]{64}$",
    )

    @field_validator("resource_id", "target_identity")
    @classmethod
    def validate_identity(cls, value: str) -> str:
        return _validate_identity(value)

    @field_validator("source_locator")
    @classmethod
    def validate_source_locator(cls, value: str) -> str:
        return _validate_source_locator(value)

    @field_validator("target_locator")
    @classmethod
    def validate_target_locator(cls, value: str) -> str:
        return _validate_target_locator(value)


class UserCopyConflictContract(UserCopyContractModel):
    """One exact overwrite-confirmation item."""

    code: Literal["marketplace.user_copy.target_conflict"]
    resource_type: UserCopyPlanResourceType = Field(alias="resourceType")
    resource_id: str = Field(
        alias="resourceId",
        min_length=1,
        max_length=MAX_USER_COPY_FIELD_LENGTH,
    )
    source_locator: str = Field(
        alias="sourceLocator",
        min_length=1,
        max_length=MAX_USER_COPY_FIELD_LENGTH,
    )
    target_locator: str = Field(
        alias="targetLocator",
        min_length=1,
        max_length=MAX_USER_COPY_FIELD_LENGTH,
    )
    target_identity: str = Field(
        alias="targetIdentity",
        min_length=1,
        max_length=MAX_USER_COPY_FIELD_LENGTH,
    )
    baseline_revision: str = Field(
        alias="baselineRevision",
        pattern=r"^[0-9a-f]{64}$",
    )
    incoming_digest: str = Field(
        alias="incomingDigest",
        pattern=r"^[0-9a-f]{64}$",
    )
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
        return _validate_identity(value)

    @field_validator("source_locator")
    @classmethod
    def validate_source_locator(cls, value: str) -> str:
        return _validate_source_locator(value)

    @field_validator("target_locator")
    @classmethod
    def validate_target_locator(cls, value: str) -> str:
        return _validate_target_locator(value)


class UserCopyBlockingIssueContract(UserCopyContractModel):
    """One non-overridable one-shot preflight issue."""

    code: UserCopyBlockingCode
    resource_type: Optional[UserCopyPlanResourceType] = Field(
        default=None,
        alias="resourceType",
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

    @field_validator("resource_id")
    @classmethod
    def validate_resource_id(cls, value: Optional[str]) -> Optional[str]:
        return _validate_identity(value) if value is not None else None

    @field_validator("source_locator")
    @classmethod
    def validate_source_locator(cls, value: Optional[str]) -> Optional[str]:
        return _validate_source_locator(value) if value is not None else None

    @field_validator("target_locator")
    @classmethod
    def validate_target_locator(cls, value: Optional[str]) -> Optional[str]:
        return _validate_target_locator(value) if value is not None else None


class UserCopyPreflightResultContract(UserCopyContractModel):
    """One-shot preflight result without installation lifecycle state."""

    status: Literal["ready", "confirmation-required", "blocked"]
    provider: MarketplaceProvider
    package_id: str = Field(
        alias="packageId",
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$",
    )
    revision: str = Field(pattern=r"^[0-9a-f]{64}$")
    workspace_id: str = Field(alias="workspaceId", min_length=1, max_length=255)
    runtime_instance_id: str = Field(
        alias="runtimeInstanceId",
        pattern=(
            r"^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-"
            r"[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
        ),
    )
    provider_state_root_id: str = Field(
        alias="providerStateRootId",
        pattern=r"^psr_[0-9a-f]{64}$",
    )
    source_digest: str = Field(alias="sourceDigest", pattern=r"^[0-9a-f]{64}$")
    profile_version: Literal[1] = Field(alias="profileVersion")
    profile_digest: str = Field(alias="profileDigest", pattern=r"^[0-9a-f]{64}$")
    materialization_digest: str = Field(
        alias="materializationDigest",
        pattern=r"^[0-9a-f]{64}$",
    )
    resources: list[UserCopyPlanResourceContract] = Field(
        max_length=MAX_USER_COPY_ITEMS
    )
    conflicts: list[UserCopyConflictContract] = Field(max_length=MAX_USER_COPY_ITEMS)
    blocking_issues: list[UserCopyBlockingIssueContract] = Field(
        alias="blockingIssues",
        max_length=MAX_USER_COPY_ITEMS,
    )

    @field_validator("profile_version", mode="before")
    @classmethod
    def validate_profile_version(cls, value: Any) -> Any:
        return _validate_profile_version(value)

    @model_validator(mode="after")
    def validate_status(self) -> "UserCopyPreflightResultContract":
        expected = (
            "blocked"
            if self.blocking_issues
            else ("confirmation-required" if self.conflicts else "ready")
        )
        if self.status != expected:
            raise ValueError("marketplace.user_copy.runtime_contract_invalid")
        if len(self.resources) + len(self.conflicts) > MAX_USER_COPY_ITEMS:
            raise ValueError("marketplace.user_copy.runtime_contract_invalid")
        target_identities = [
            resource.target_identity for resource in self.resources
        ] + [conflict.target_identity for conflict in self.conflicts]
        if len(target_identities) != len(
            {identity.casefold() for identity in target_identities}
        ):
            raise ValueError("marketplace.user_copy.runtime_contract_invalid")
        return self

    @property
    def expected_result_counts(self) -> tuple[int, int, int, int]:
        return (
            sum(resource.action == "create" for resource in self.resources),
            sum(resource.action == "merge" for resource in self.resources),
            sum(resource.action == "unchanged" for resource in self.resources),
            len(self.conflicts),
        )


class UserCopyApplyMetadataContract(UserCopyContractModel):
    """Proof metadata sent beside the canonical ZIP bundle."""

    operation_id: str = Field(alias="operationId", pattern=r"^[0-9a-f]{32}$")
    provider: MarketplaceProvider
    package_id: str = Field(
        alias="packageId",
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$",
    )
    revision: str = Field(pattern=r"^[0-9a-f]{64}$")
    workspace_id: str = Field(alias="workspaceId", min_length=1, max_length=255)
    runtime_instance_id: str = Field(
        alias="runtimeInstanceId",
        pattern=(
            r"^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-"
            r"[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
        ),
    )
    provider_state_root_id: str = Field(
        alias="providerStateRootId",
        pattern=r"^psr_[0-9a-f]{64}$",
    )
    expected_source_digest: str = Field(
        alias="expectedSourceDigest",
        pattern=r"^[0-9a-f]{64}$",
    )
    expected_archive_digest: str = Field(
        alias="expectedArchiveDigest",
        pattern=r"^[0-9a-f]{64}$",
    )
    expected_package_tree_digest: str = Field(
        alias="expectedPackageTreeDigest",
        pattern=r"^[0-9a-f]{64}$",
    )
    expected_profile_version: Literal[1] = Field(alias="expectedProfileVersion")
    expected_profile_digest: str = Field(
        alias="expectedProfileDigest",
        pattern=r"^[0-9a-f]{64}$",
    )
    expected_materialization_digest: str = Field(
        alias="expectedMaterializationDigest",
        pattern=r"^[0-9a-f]{64}$",
    )
    overwrite_approvals: list[UserCopyOverwriteApprovalContract] = Field(
        default_factory=list,
        alias="overwriteApprovals",
        max_length=MAX_USER_COPY_ITEMS,
    )

    @field_validator("expected_profile_version", mode="before")
    @classmethod
    def validate_expected_profile_version(cls, value: Any) -> Any:
        return _validate_profile_version(value)

    @model_validator(mode="after")
    def validate_approval_identities(self) -> "UserCopyApplyMetadataContract":
        identities = [
            approval.target_identity.casefold() for approval in self.overwrite_approvals
        ]
        if len(identities) != len(set(identities)):
            raise ValueError("marketplace.user_copy.runtime_contract_invalid")
        return self

    def verify_result(
        self,
        result: "UserCopyApplyResultContract",
        *,
        preflight: UserCopyPreflightResultContract,
    ) -> None:
        identity_matches = (
            result.operation_id == self.operation_id
            and result.provider == self.provider
            and result.package_id == self.package_id
            and result.revision == self.revision
            and result.workspace_id == self.workspace_id
        )
        actual_counts = (
            result.created_count,
            result.merged_count,
            result.unchanged_count,
            result.overwritten_count,
        )
        if not identity_matches or actual_counts != preflight.expected_result_counts:
            raise UserCopyContractError(
                "marketplace.user_copy.runtime_contract_invalid"
            )


class UserCopyApplyResultContract(UserCopyContractModel):
    """Completed one-shot copy receipt."""

    status: Literal["completed"] = "completed"
    operation_id: str = Field(alias="operationId", pattern=r"^[0-9a-f]{32}$")
    provider: MarketplaceProvider
    package_id: str = Field(
        alias="packageId",
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$",
    )
    revision: str = Field(pattern=r"^[0-9a-f]{64}$")
    workspace_id: str = Field(alias="workspaceId", min_length=1, max_length=255)
    created_count: int = Field(alias="createdCount", ge=0, le=MAX_USER_COPY_ITEMS)
    merged_count: int = Field(alias="mergedCount", ge=0, le=MAX_USER_COPY_ITEMS)
    unchanged_count: int = Field(
        alias="unchangedCount",
        ge=0,
        le=MAX_USER_COPY_ITEMS,
    )
    overwritten_count: int = Field(
        alias="overwrittenCount",
        ge=0,
        le=MAX_USER_COPY_ITEMS,
    )

    @model_validator(mode="after")
    def validate_total_count(self) -> "UserCopyApplyResultContract":
        if (
            sum(
                (
                    self.created_count,
                    self.merged_count,
                    self.unchanged_count,
                    self.overwritten_count,
                )
            )
            > MAX_USER_COPY_ITEMS
        ):
            raise ValueError("marketplace.user_copy.runtime_contract_invalid")
        return self


__all__ = [
    "MAX_USER_COPY_FIELD_LENGTH",
    "MAX_USER_COPY_ITEMS",
    "MAX_USER_COPY_PREVIEW_BYTES",
    "MarketplaceBlockedUserCopyResourcePreview",
    "MarketplaceDependencyPayloadPreview",
    "MarketplaceProvider",
    "MarketplaceUserCopyProfilePreview",
    "MarketplaceUserCopyProfileResourcePreview",
    "UserCopyApplyMetadataContract",
    "UserCopyApplyResultContract",
    "UserCopyBlockingCode",
    "UserCopyBlockingIssueContract",
    "UserCopyConflictContract",
    "UserCopyContractError",
    "UserCopyContractModel",
    "UserCopyOverwriteApprovalContract",
    "UserCopyPlanResourceContract",
    "UserCopyPlanResourceType",
    "UserCopyPreflightRequestContract",
    "UserCopyPreflightResultContract",
    "UserCopyProfileResourceType",
    "UserCopyTargetResourceName",
]
