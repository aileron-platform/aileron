"""V2 wire contracts for package-format to target-client User Copy."""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import Field, field_validator, model_validator

from .resource_resolution import (
    PackageSourceError,
    validate_source_locator,
    validate_wire_identity,
)
from .user_copy_common_contracts import (
    MAX_USER_COPY_FIELD_LENGTH,
    MAX_USER_COPY_ITEMS,
    UserCopyBlockingIssueContract,
    UserCopyConflictContract,
    UserCopyContractModel,
    UserCopyOverwriteApprovalContract,
    UserCopyPlanResourceContract,
    UserCopyPlanResourceType,
)
from .user_copy_profiles import UserCopyResourceType, UserCopySourceKind
from .user_copy_source_profiles import (
    PluginPackageFormat,
    PluginReleaseIdentity,
    UserCopyDependencyReference,
    UserCopySourceDiagnostic,
    UserCopySourceProfile,
    UserCopySourceResource,
)

PluginPackageFormatName = Literal[
    "codex-native",
    "claude-native",
    "agent-plugin/1.0.0",
]
TargetClientName = Literal["codex", "claude-code"]


def _identity(value: str) -> str:
    try:
        return validate_wire_identity(value)
    except PackageSourceError as exc:
        raise ValueError("marketplace.user_copy.profile_invalid") from exc


def _source_locator(value: str) -> str:
    try:
        return validate_source_locator(value)
    except PackageSourceError as exc:
        raise ValueError("marketplace.user_copy.profile_invalid") from exc


class UserCopyReleaseIdentityContract(UserCopyContractModel):
    """Immutable catalog release identity embedded in the source proof."""

    catalog_plugin_id: str = Field(
        alias="catalogPluginId",
        min_length=1,
        max_length=MAX_USER_COPY_FIELD_LENGTH,
    )
    revision: str = Field(pattern=r"^[0-9a-f]{64}$")

    @field_validator("catalog_plugin_id")
    @classmethod
    def validate_catalog_plugin_id(cls, value: str) -> str:
        return _identity(value)


class UserCopyDependencyReferenceContract(UserCopyContractModel):
    """One package-relative dependency referenced by a source resource."""

    source_locator: str = Field(
        alias="sourceLocator",
        min_length=1,
        max_length=MAX_USER_COPY_FIELD_LENGTH,
    )
    source_kind: Literal["file", "directory"] = Field(alias="sourceKind")
    source_digest: str = Field(alias="sourceDigest", pattern=r"^[0-9a-f]{64}$")

    @field_validator("source_locator")
    @classmethod
    def validate_source_locator(cls, value: str) -> str:
        return _source_locator(value)


class UserCopySourceResourcePreviewContract(UserCopyContractModel):
    """One source-only resource crossing the Manager/Runtime seam."""

    resource_type: UserCopyPlanResourceType = Field(alias="resourceType")
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
    source_digest: str = Field(alias="sourceDigest", pattern=r"^[0-9a-f]{64}$")
    source_json_pointer: Optional[str] = Field(
        default=None,
        alias="sourceJsonPointer",
        max_length=MAX_USER_COPY_FIELD_LENGTH,
    )
    structured_value: Optional[Any] = Field(
        default=None,
        alias="structuredValue",
    )
    dependency_references: list[UserCopyDependencyReferenceContract] = Field(
        default_factory=list,
        alias="dependencyReferences",
        max_length=MAX_USER_COPY_ITEMS,
    )

    @field_validator("resource_id")
    @classmethod
    def validate_resource_id(cls, value: str) -> str:
        return _identity(value)

    @field_validator("source_locator")
    @classmethod
    def validate_source_locator(cls, value: str) -> str:
        return _source_locator(value)


class UserCopySourceDiagnosticContract(UserCopyContractModel):
    """One package-format extraction diagnostic."""

    code: str = Field(min_length=1, max_length=MAX_USER_COPY_FIELD_LENGTH)
    source_locator: str = Field(
        alias="sourceLocator",
        min_length=1,
        max_length=MAX_USER_COPY_FIELD_LENGTH,
    )
    resource_type: Optional[str] = Field(default=None, alias="resourceType")
    resource_id: Optional[str] = Field(default=None, alias="resourceId")

    @field_validator("code", "resource_type", "resource_id")
    @classmethod
    def validate_identities(cls, value: Optional[str]) -> Optional[str]:
        return _identity(value) if value is not None else None

    @field_validator("source_locator")
    @classmethod
    def validate_source_locator(cls, value: str) -> str:
        return _source_locator(value)


class UserCopySourceProfilePreviewContract(UserCopyContractModel):
    """Canonical source-only profile proof."""

    profile_version: Literal[2] = Field(alias="profileVersion")
    package_format: PluginPackageFormatName = Field(alias="packageFormat")
    release_identity: UserCopyReleaseIdentityContract = Field(
        alias="releaseIdentity"
    )
    profile_digest: str = Field(alias="profileDigest", pattern=r"^[0-9a-f]{64}$")
    resources: list[UserCopySourceResourcePreviewContract] = Field(
        max_length=MAX_USER_COPY_ITEMS
    )
    diagnostics: list[UserCopySourceDiagnosticContract] = Field(
        max_length=MAX_USER_COPY_ITEMS
    )

    def to_profile(self) -> UserCopySourceProfile:
        profile = UserCopySourceProfile(
            package_format=PluginPackageFormat(self.package_format),
            release_identity=PluginReleaseIdentity(
                catalog_plugin_id=self.release_identity.catalog_plugin_id,
                revision=self.release_identity.revision,
            ),
            profile_version=self.profile_version,
            resources=tuple(
                UserCopySourceResource(
                    resource_type=UserCopyResourceType(resource.resource_type),
                    resource_id=resource.resource_id,
                    source_locator=resource.source_locator,
                    source_kind=UserCopySourceKind(resource.source_kind),
                    source_digest=resource.source_digest,
                    source_json_pointer=resource.source_json_pointer,
                    structured_value=resource.structured_value,
                    dependency_references=tuple(
                        UserCopyDependencyReference(
                            source_locator=reference.source_locator,
                            source_kind=reference.source_kind,
                            source_digest=reference.source_digest,
                        )
                        for reference in resource.dependency_references
                    ),
                )
                for resource in self.resources
            ),
            diagnostics=tuple(
                UserCopySourceDiagnostic(
                    code=diagnostic.code,
                    source_locator=diagnostic.source_locator,
                    resource_type=diagnostic.resource_type,
                    resource_id=diagnostic.resource_id,
                )
                for diagnostic in self.diagnostics
            ),
        )
        if profile.profile_digest != self.profile_digest:
            raise ValueError("marketplace.user_copy.profile_mismatch")
        return profile


class UserCopyProjectionPreflightRequestContract(UserCopyContractModel):
    """Read-only preflight request bound to source format and target client."""

    package_format: PluginPackageFormatName = Field(alias="packageFormat")
    target_client: TargetClientName = Field(alias="targetClient")
    catalog_plugin_id: str = Field(
        alias="catalogPluginId",
        min_length=1,
        max_length=MAX_USER_COPY_FIELD_LENGTH,
    )
    release_revision: str = Field(
        alias="releaseRevision",
        pattern=r"^[0-9a-f]{64}$",
    )
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
    expected_profile_version: Literal[2] = Field(alias="expectedProfileVersion")
    expected_profile_digest: str = Field(
        alias="expectedProfileDigest",
        pattern=r"^[0-9a-f]{64}$",
    )
    source_profile: UserCopySourceProfilePreviewContract = Field(
        alias="sourceProfile"
    )

    @field_validator("catalog_plugin_id")
    @classmethod
    def validate_catalog_plugin_id(cls, value: str) -> str:
        return _identity(value)

    @model_validator(mode="after")
    def validate_source_proof(self) -> "UserCopyProjectionPreflightRequestContract":
        profile = self.source_profile
        if (
            profile.package_format != self.package_format
            or profile.release_identity.catalog_plugin_id != self.catalog_plugin_id
            or profile.release_identity.revision != self.release_revision
            or profile.profile_version != self.expected_profile_version
            or profile.profile_digest != self.expected_profile_digest
        ):
            raise ValueError("marketplace.user_copy.profile_mismatch")
        profile.to_profile()
        return self


class SkippedUserCopyResourceContract(UserCopyContractModel):
    """One source resource omitted by the exact projection pair."""

    code: str = Field(min_length=1, max_length=MAX_USER_COPY_FIELD_LENGTH)
    resource_type: str = Field(
        alias="resourceType",
        min_length=1,
        max_length=MAX_USER_COPY_FIELD_LENGTH,
    )
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

    @field_validator("code", "resource_type", "resource_id")
    @classmethod
    def validate_identities(cls, value: str) -> str:
        return _identity(value)

    @field_validator("source_locator")
    @classmethod
    def validate_source_locator(cls, value: str) -> str:
        return _source_locator(value)


class UserCopyProjectionPreflightResultContract(UserCopyContractModel):
    """Projected preflight result with exact partial-copy diagnostics."""

    status: Literal["ready", "confirmation-required", "blocked"]
    package_format: PluginPackageFormatName = Field(alias="packageFormat")
    target_client: TargetClientName = Field(alias="targetClient")
    catalog_plugin_id: str = Field(alias="catalogPluginId")
    release_revision: str = Field(
        alias="releaseRevision",
        pattern=r"^[0-9a-f]{64}$",
    )
    workspace_id: str = Field(alias="workspaceId", min_length=1, max_length=255)
    runtime_instance_id: str = Field(
        alias="runtimeInstanceId",
        pattern=(
            r"^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-"
            r"[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
        ),
    )
    target_client_state_root_id: str = Field(
        alias="targetClientStateRootId",
        pattern=r"^tcsr_[0-9a-f]{64}$",
    )
    source_digest: str = Field(alias="sourceDigest", pattern=r"^[0-9a-f]{64}$")
    profile_version: Literal[2] = Field(alias="profileVersion")
    profile_digest: str = Field(alias="profileDigest", pattern=r"^[0-9a-f]{64}$")
    projection_digest: str = Field(
        alias="projectionDigest",
        pattern=r"^[0-9a-f]{64}$",
    )
    materialization_digest: str = Field(
        alias="materializationDigest",
        pattern=r"^[0-9a-f]{64}$",
    )
    resources: list[UserCopyPlanResourceContract] = Field(
        max_length=MAX_USER_COPY_ITEMS
    )
    skipped_resources: list[SkippedUserCopyResourceContract] = Field(
        alias="skippedResources",
        max_length=MAX_USER_COPY_ITEMS,
    )
    conflicts: list[UserCopyConflictContract] = Field(max_length=MAX_USER_COPY_ITEMS)
    blocking_issues: list[UserCopyBlockingIssueContract] = Field(
        alias="blockingIssues",
        max_length=MAX_USER_COPY_ITEMS,
    )

    @field_validator("catalog_plugin_id")
    @classmethod
    def validate_catalog_plugin_id(cls, value: str) -> str:
        return _identity(value)

    @model_validator(mode="after")
    def validate_status(self) -> "UserCopyProjectionPreflightResultContract":
        expected = (
            "blocked"
            if self.blocking_issues
            else (
                "confirmation-required"
                if self.conflicts or self.skipped_resources
                else "ready"
            )
        )
        if self.status != expected:
            raise ValueError("marketplace.user_copy.runtime_contract_invalid")
        if (
            len(self.resources)
            + len(self.skipped_resources)
            + len(self.conflicts)
            > MAX_USER_COPY_ITEMS
        ):
            raise ValueError("marketplace.user_copy.runtime_contract_invalid")
        target_identities = [
            item.target_identity.casefold()
            for item in [*self.resources, *self.conflicts]
        ]
        if len(target_identities) != len(set(target_identities)):
            raise ValueError("marketplace.user_copy.runtime_contract_invalid")
        return self

    @property
    def expected_result_counts(self) -> tuple[int, int, int, int, int]:
        return (
            sum(resource.action == "create" for resource in self.resources),
            sum(resource.action == "merge" for resource in self.resources),
            sum(resource.action == "unchanged" for resource in self.resources),
            len(self.conflicts),
            len(self.skipped_resources),
        )


class UserCopyProjectionApplyMetadataContract(UserCopyContractModel):
    """Proof metadata sent beside the canonical User Copy archive."""

    operation_id: str = Field(alias="operationId", pattern=r"^[0-9a-f]{32}$")
    package_format: PluginPackageFormatName = Field(alias="packageFormat")
    target_client: TargetClientName = Field(alias="targetClient")
    catalog_plugin_id: str = Field(alias="catalogPluginId")
    release_revision: str = Field(
        alias="releaseRevision",
        pattern=r"^[0-9a-f]{64}$",
    )
    workspace_id: str = Field(alias="workspaceId", min_length=1, max_length=255)
    runtime_instance_id: str = Field(
        alias="runtimeInstanceId",
        pattern=(
            r"^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-"
            r"[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
        ),
    )
    target_client_state_root_id: str = Field(
        alias="targetClientStateRootId",
        pattern=r"^tcsr_[0-9a-f]{64}$",
    )
    expected_source_digest: str = Field(
        alias="expectedSourceDigest", pattern=r"^[0-9a-f]{64}$"
    )
    expected_archive_digest: str = Field(
        alias="expectedArchiveDigest", pattern=r"^[0-9a-f]{64}$"
    )
    expected_package_tree_digest: str = Field(
        alias="expectedPackageTreeDigest", pattern=r"^[0-9a-f]{64}$"
    )
    expected_profile_version: Literal[2] = Field(alias="expectedProfileVersion")
    expected_profile_digest: str = Field(
        alias="expectedProfileDigest", pattern=r"^[0-9a-f]{64}$"
    )
    expected_projection_digest: str = Field(
        alias="expectedProjectionDigest", pattern=r"^[0-9a-f]{64}$"
    )
    expected_materialization_digest: str = Field(
        alias="expectedMaterializationDigest", pattern=r"^[0-9a-f]{64}$"
    )
    accept_partial_copy: bool = Field(alias="acceptPartialCopy")
    expected_skipped_count: int = Field(
        alias="expectedSkippedCount", ge=0, le=MAX_USER_COPY_ITEMS
    )
    overwrite_approvals: list[UserCopyOverwriteApprovalContract] = Field(
        default_factory=list,
        alias="overwriteApprovals",
        max_length=MAX_USER_COPY_ITEMS,
    )

    @field_validator("catalog_plugin_id")
    @classmethod
    def validate_catalog_plugin_id(cls, value: str) -> str:
        return _identity(value)

    @field_validator("accept_partial_copy", mode="before")
    @classmethod
    def validate_accept_partial_copy(cls, value: Any) -> Any:
        if type(value) is not bool:
            raise ValueError("marketplace.user_copy.runtime_contract_invalid")
        return value

    @model_validator(mode="after")
    def validate_partial_copy_confirmation(
        self,
    ) -> "UserCopyProjectionApplyMetadataContract":
        if self.accept_partial_copy != (self.expected_skipped_count > 0):
            raise ValueError("marketplace.user_copy.partial_copy_confirmation_invalid")
        identities = [
            approval.target_identity.casefold() for approval in self.overwrite_approvals
        ]
        if len(identities) != len(set(identities)):
            raise ValueError("marketplace.user_copy.runtime_contract_invalid")
        return self

    def verify_result(
        self,
        result: "UserCopyProjectionApplyResultContract",
        *,
        expected_counts: tuple[int, int, int, int, int],
    ) -> None:
        identity_matches = (
            result.operation_id == self.operation_id
            and result.package_format == self.package_format
            and result.target_client == self.target_client
            and result.catalog_plugin_id == self.catalog_plugin_id
            and result.release_revision == self.release_revision
            and result.workspace_id == self.workspace_id
        )
        actual_counts = (
            result.created_count,
            result.merged_count,
            result.unchanged_count,
            result.overwritten_count,
            result.skipped_count,
        )
        if not identity_matches or actual_counts != expected_counts:
            raise ValueError("marketplace.user_copy.runtime_contract_invalid")


class UserCopyProjectionApplyResultContract(UserCopyContractModel):
    """Completed standalone-resource materialization receipt."""

    status: Literal["completed"] = "completed"
    operation_id: str = Field(alias="operationId", pattern=r"^[0-9a-f]{32}$")
    package_format: PluginPackageFormatName = Field(alias="packageFormat")
    target_client: TargetClientName = Field(alias="targetClient")
    catalog_plugin_id: str = Field(alias="catalogPluginId")
    release_revision: str = Field(
        alias="releaseRevision", pattern=r"^[0-9a-f]{64}$"
    )
    workspace_id: str = Field(alias="workspaceId", min_length=1, max_length=255)
    created_count: int = Field(alias="createdCount", ge=0, le=MAX_USER_COPY_ITEMS)
    merged_count: int = Field(alias="mergedCount", ge=0, le=MAX_USER_COPY_ITEMS)
    unchanged_count: int = Field(
        alias="unchangedCount", ge=0, le=MAX_USER_COPY_ITEMS
    )
    overwritten_count: int = Field(
        alias="overwrittenCount", ge=0, le=MAX_USER_COPY_ITEMS
    )
    skipped_count: int = Field(alias="skippedCount", ge=0, le=MAX_USER_COPY_ITEMS)

    @field_validator("catalog_plugin_id")
    @classmethod
    def validate_catalog_plugin_id(cls, value: str) -> str:
        return _identity(value)

    @model_validator(mode="after")
    def validate_total_count(self) -> "UserCopyProjectionApplyResultContract":
        if sum(
            (
                self.created_count,
                self.merged_count,
                self.unchanged_count,
                self.overwritten_count,
                self.skipped_count,
            )
        ) > MAX_USER_COPY_ITEMS:
            raise ValueError("marketplace.user_copy.runtime_contract_invalid")
        return self
