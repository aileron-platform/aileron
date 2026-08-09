"""Marketplace API models."""

from __future__ import annotations

from typing import Any, Literal, get_args

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.modules.version_control.models import FileChange

MarketplaceProvider = Literal["claude-code", "codex"]
MarketplaceImportProvider = Literal["all", "claude-code", "codex"]
MarketplaceRegistryStatus = Literal["uninitialized", "ready", "busy", "error"]
MarketplaceSourceType = Literal["created", "imported", "cloned"]
MarketplaceValidationSeverity = Literal["none", "info", "warning", "error"]
MarketplaceLifecycleStatus = Literal["draft", "ready"]
MarketplaceActivityAction = Literal[
    "import",
    "install",
    "copy",
    "delete",
]
MarketplaceActivityStatus = Literal["succeeded", "failed"]
MarketplaceImportSourceKind = Literal["git", "local"]
MarketplaceDuplicateAction = Literal["skip", "overwrite", "import-as-new"]
MarketplaceUserCopyResourceType = Literal[
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
MarketplaceUserCopyBlockingErrorCode = Literal[
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
MARKETPLACE_COPYABLE_RESOURCE_TYPES = frozenset(
    get_args(MarketplaceUserCopyResourceType)
)
MARKETPLACE_USER_COPY_BLOCKING_ERROR_CODES = frozenset(
    get_args(MarketplaceUserCopyBlockingErrorCode)
)
MarketplaceUserCopyOperation = Literal["create", "merge", "unchanged"]
MarketplaceImportVariantStatus = Literal[
    "new-family",
    "add-variant",
    "duplicate-variant",
    "unrelated-duplicate",
    "invalid",
]
MarketplacePluginCommandStatus = Literal["installed", "failed"]
MarketplacePluginCommandStage = Literal[
    "marketplace-add",
    "plugin-install",
    "marketplace-list",
    "plugin-list",
    "completed",
]


class MarketplaceOwnerMetadata(BaseModel):
    """Marketplace root owner metadata."""

    name: str = Field(description="Maintainer name")
    email: str = Field(description="Maintainer email")

    model_config = {"extra": "forbid"}


class MarketplaceCatalogPackagePolicy(BaseModel):
    """Provider policy stored in the canonical Marketplace catalog."""

    installation: str
    authentication: str

    model_config = {"extra": "forbid"}


class MarketplaceCatalogPackage(BaseModel):
    """One provider package entry in the canonical Marketplace catalog."""

    provider: MarketplaceProvider
    package_id: str = Field(alias="packageId")
    category: str | None = None
    tags: list[str] = Field(default_factory=list)
    policy: MarketplaceCatalogPackagePolicy | None = None

    model_config = {"populate_by_name": True, "extra": "forbid"}


class MarketplaceRegistryCatalog(BaseModel):
    """Canonical registry catalog committed at marketplace/catalog.json."""

    schema_version: Literal[1] = Field(alias="schemaVersion")
    marketplace_id: str = Field(
        alias="marketplaceId",
        min_length=1,
        max_length=64,
        pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$",
    )
    display_name: str = Field(alias="displayName")
    owner: MarketplaceOwnerMetadata
    description: str
    publish_branch: str = Field(
        alias="publishBranch",
        min_length=1,
        max_length=128,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,127}$",
    )
    packages: list[MarketplaceCatalogPackage] = Field(default_factory=list)

    model_config = {"populate_by_name": True, "extra": "forbid"}

    @field_validator("marketplace_id")
    @classmethod
    def validate_marketplace_id(cls, value: str) -> str:
        """Reject provider-reserved immutable marketplace identities."""

        if value in {"claude-plugins-official", "claude-community"}:
            raise ValueError("Marketplace ID is reserved")
        return value

    @field_validator("publish_branch")
    @classmethod
    def validate_publish_branch(cls, value: str) -> str:
        """Reject Git ref forms that the conservative API regex still permits."""

        if (
            ".." in value
            or "//" in value
            or "@{" in value
            or value.endswith(("/", ".", ".lock"))
        ):
            raise ValueError("Publish branch is invalid")
        return value


class MarketplaceRegistryRootMetadataSavePayload(BaseModel):
    """Root metadata saved through Marketplace Settings General."""

    name: str = Field(description="Marketplace registry display name")
    owner: MarketplaceOwnerMetadata = Field(description="Marketplace owner metadata")
    description: str = Field(description="Marketplace registry description")

    model_config = {"extra": "forbid"}


class MarketplaceRegistrySettings(BaseModel):
    """Marketplace registry settings response."""

    display_name: str = Field(alias="displayName")
    marketplace_id: str | None = Field(alias="marketplaceId")
    publish_branch: str | None = Field(alias="publishBranch")
    root_path: str = Field(alias="rootPath")
    status: MarketplaceRegistryStatus
    description: str = ""
    maintainer_name: str = Field(alias="maintainerName")
    maintainer_email: str = Field(alias="maintainerEmail")
    model_config = {"populate_by_name": True, "extra": "forbid"}

    @model_validator(mode="after")
    def validate_ready_identity(self) -> MarketplaceRegistrySettings:
        """A ready registry must expose its immutable catalog identity."""

        if self.status == "ready" and (
            self.marketplace_id is None or self.publish_branch is None
        ):
            raise ValueError("Ready Marketplace registry identity is missing")
        return self


class MarketplaceRegistryInitResult(BaseModel):
    """Marketplace registry initialization result."""

    root_path: str = Field(alias="rootPath")
    created: bool
    claude_manifest_path: str = Field(alias="claudeManifestPath")
    codex_manifest_path: str = Field(alias="codexManifestPath")

    model_config = {"populate_by_name": True}


class MarketplaceSettingsSaveResult(BaseModel):
    """Marketplace settings save result."""

    settings: MarketplaceRegistrySettings
    claude_written: bool = Field(alias="claudeWritten")
    codex_written: bool = Field(alias="codexWritten")
    partial_success_provider: MarketplaceProvider | None = Field(
        default=None,
        alias="partialSuccessProvider",
    )
    error_code: str | None = Field(default=None, alias="errorCode")

    model_config = {"populate_by_name": True}


class MarketplaceRegistryRepositoryStatus(BaseModel):
    """Marketplace registry Git repository lifecycle status."""

    is_git_repo: bool = Field(alias="isGitRepo")
    current_branch: str | None = Field(default=None, alias="currentBranch")
    remote_url: str | None = Field(default=None, alias="remoteUrl")
    has_origin: bool = Field(default=False, alias="hasOrigin")
    has_local_content: bool = Field(default=False, alias="hasLocalContent")
    can_clone_safely: bool = Field(default=False, alias="canCloneSafely")
    can_init_safely: bool = Field(default=False, alias="canInitSafely")
    clone_blocked_reason: str | None = Field(default=None, alias="cloneBlockedReason")

    model_config = {"populate_by_name": True}


class MarketplaceRegistryCloneRequest(BaseModel):
    """Marketplace registry clone request."""

    remote_url: str = Field(alias="remoteUrl")
    branch: str | None = None

    model_config = {"populate_by_name": True}


class MarketplaceRegistryGitOperationResult(BaseModel):
    """Marketplace registry Git operation result."""

    success: bool
    message_key: str = Field(alias="messageKey")
    repository: MarketplaceRegistryRepositoryStatus | None = None
    error_code: str | None = Field(default=None, alias="errorCode")

    model_config = {"populate_by_name": True}


class MarketplaceLocalHistoryEntry(BaseModel):
    """Marketplace registry local history entry."""

    id: str
    domain: str
    resource_id: str = Field(alias="resourceId")
    path: str
    operation: str
    timestamp: str
    revision_before: str | None = Field(default=None, alias="revisionBefore")
    revision_after: str | None = Field(default=None, alias="revisionAfter")
    snapshot_path: str | None = Field(default=None, alias="snapshotPath")
    size: int

    model_config = {"populate_by_name": True}


class MarketplaceLocalHistoryListResponse(BaseModel):
    """Marketplace registry local history list response."""

    items: list[MarketplaceLocalHistoryEntry]

    model_config = {"populate_by_name": True}


class MarketplaceLocalHistoryRestoreRequest(BaseModel):
    """Marketplace registry local history restore request."""

    revision: str | None = None

    model_config = {"populate_by_name": True}


class MarketplaceLocalHistoryRestoreResponse(BaseModel):
    """Marketplace registry local history restore response."""

    path: str
    restored_from: str = Field(alias="restoredFrom")
    revision: str

    model_config = {"populate_by_name": True}


class MarketplaceGitDiffResponse(BaseModel):
    """Marketplace registry file diff response."""

    path: str
    patch: str = ""
    diff: str = ""
    binary: bool = False
    commit_id: str | None = Field(default=None, alias="commitId")
    head: Literal["WORKTREE", "INDEX"] | None = None

    model_config = {"populate_by_name": True}


class MarketplaceGitPathRequest(BaseModel):
    """Marketplace registry Git path selection request."""

    paths: list[str] = Field(default_factory=list)
    all: bool = False


class MarketplaceGitStageResult(BaseModel):
    """Marketplace registry stage operation result."""

    staged: list[str] = Field(default_factory=list)
    unstaged: list[str] = Field(default_factory=list)


class MarketplaceGitUnstageResult(BaseModel):
    """Marketplace registry unstage operation result."""

    unstaged: list[str] = Field(default_factory=list)
    remaining_staged: int = Field(default=0, alias="remainingStaged")

    model_config = {"populate_by_name": True}


class MarketplaceGitCommitRequest(BaseModel):
    """Marketplace registry Git commit request."""

    message: str

    model_config = {"extra": "forbid"}


class MarketplaceGitCommitSummary(BaseModel):
    """Marketplace registry Git commit summary."""

    id: str
    message: str
    author: str
    email: str
    timestamp: str
    additions: int = 0
    deletions: int = 0
    files_changed: int = Field(default=0, alias="filesChanged")

    model_config = {"populate_by_name": True}


class MarketplaceGitCommitResult(BaseModel):
    """Marketplace registry Git commit operation result."""

    success: bool
    message_key: str = Field(alias="messageKey")
    commit: MarketplaceGitCommitSummary | None = None
    error_code: str | None = Field(default=None, alias="errorCode")

    model_config = {"populate_by_name": True}


class MarketplaceGitCommitFilesResult(BaseModel):
    """Marketplace registry Git commit changed files response."""

    commit_id: str = Field(alias="commitId")
    files: list[FileChange] = Field(default_factory=list)

    model_config = {"populate_by_name": True}


class MarketplaceValidationResult(BaseModel):
    """Provider-native Marketplace validation result."""

    severity: Literal["info", "warning", "error"]
    code: str
    message_key: str = Field(alias="messageKey")
    file_path: str | None = Field(default=None, alias="filePath")
    details: dict[str, Any] | None = None

    model_config = {"populate_by_name": True}


class MarketplacePackageFamilySource(BaseModel):
    """External source identity for a Marketplace package family."""

    kind: MarketplaceImportSourceKind
    source: str
    normalized_url: str | None = Field(default=None, alias="normalizedUrl")

    model_config = {"populate_by_name": True}


class MarketplaceProviderVariant(BaseModel):
    """Provider-native package variant that belongs to a package family."""

    provider: MarketplaceProvider
    package_id: str = Field(alias="packageId")
    registry_path: str = Field(default="", alias="registryPath")
    display_name: str | None = Field(default=None, alias="displayName")

    model_config = {"populate_by_name": True}


class MarketplacePackageFamily(BaseModel):
    """Marketplace package family grouping provider-native variants."""

    family_id: str = Field(alias="familyId")
    display_name: str = Field(alias="displayName")
    source: MarketplacePackageFamilySource
    variants: list[MarketplaceProviderVariant] = Field(default_factory=list)

    model_config = {"populate_by_name": True}


class MarketplacePackageFamiliesDocument(BaseModel):
    """Persisted package family metadata document."""

    families: list[MarketplacePackageFamily] = Field(default_factory=list)

    model_config = {"populate_by_name": True}


class MarketplacePackageSummary(BaseModel):
    """Marketplace package summary for list cards and rows."""

    provider: MarketplaceProvider
    package_type: Literal["plugin"] = Field(alias="packageType")
    package_id: str = Field(alias="packageId")
    display_name: str = Field(alias="displayName")
    version: str | None = None
    description: str | None = None
    category: str | None = None
    tags: list[str] = Field(default_factory=list)
    source_type: MarketplaceSourceType = Field(default="created", alias="sourceType")
    indexed_resource_names: list[str] = Field(
        default_factory=list, alias="indexedResourceNames"
    )
    validation_severity: MarketplaceValidationSeverity = Field(
        default="none", alias="validationSeverity"
    )
    lifecycle_status: MarketplaceLifecycleStatus = Field(
        default="draft", alias="lifecycleStatus"
    )
    registry_path: str = Field(alias="registryPath")
    revision: str
    updated_at: str = Field(alias="updatedAt")
    family_id: str | None = Field(default=None, alias="familyId")
    family_display_name: str | None = Field(default=None, alias="familyDisplayName")
    source_identity: str | None = Field(default=None, alias="sourceIdentity")
    variants: list[MarketplaceProviderVariant] = Field(default_factory=list)

    model_config = {"populate_by_name": True}


class MarketplacePackageListResult(BaseModel):
    """Marketplace package list response."""

    items: list[MarketplacePackageSummary]
    total: int
    page: int
    page_size: int = Field(alias="pageSize")
    total_pages: int = Field(alias="totalPages")
    categories: list[str] = Field(default_factory=list)
    source_types: list[MarketplaceSourceType] = Field(
        default_factory=list, alias="sourceTypes"
    )
    validation_severities: list[MarketplaceValidationSeverity] = Field(
        default_factory=list,
        alias="validationSeverities",
    )
    registry_fingerprint: str = Field(default="", alias="registryFingerprint")

    model_config = {"populate_by_name": True}


class MarketplaceFeatureContentItem(BaseModel):
    """Provider-native feature content shown on Marketplace detail pages."""

    id: str
    name: str
    description: str | None = None
    path: str | None = None
    content: str | None = None
    data: dict[str, Any] | None = None
    owner_file_path: str | None = Field(default=None, alias="ownerFilePath")
    base_entry_fingerprint: str | None = Field(
        default=None, alias="baseEntryFingerprint"
    )

    model_config = {"populate_by_name": True}


class MarketplacePackageFile(BaseModel):
    """A provider package file included in the package detail file tree."""

    path: str
    content: str = ""
    binary: bool = False
    mime_type: str | None = Field(default=None, alias="mimeType")
    size: int = 0

    model_config = {"populate_by_name": True}


class MarketplacePackageDetail(MarketplacePackageSummary):
    """Summary-first Marketplace package overview."""

    catalog_metadata: dict[str, Any] = Field(
        default_factory=dict, alias="catalogMetadata"
    )
    manifest_metadata: dict[str, Any] = Field(
        default_factory=dict, alias="manifestMetadata"
    )
    metadata_conflict: bool = Field(default=False, alias="metadataConflict")
    validation_results: list[MarketplaceValidationResult] = Field(
        default_factory=list, alias="validationResults"
    )

    model_config = {"populate_by_name": True}


class MarketplacePackageSaveRequest(BaseModel):
    """Save a provider package snapshot."""

    provider: MarketplaceProvider
    package_id: str = Field(alias="packageId")
    revision: str
    listing: dict[str, Any] = Field(default_factory=dict)
    manifest: dict[str, Any] = Field(default_factory=dict)
    readme_markdown: str | None = Field(default=None, alias="readmeMarkdown")
    package_files: list[MarketplacePackageFile] = Field(alias="packageFiles")

    model_config = {"populate_by_name": True}


class MarketplaceActivityRecord(BaseModel):
    """Per-user Marketplace activity record."""

    id: str
    action: MarketplaceActivityAction
    provider: MarketplaceProvider | None = None
    package_id: str | None = Field(default=None, alias="packageId")
    operation_id: str | None = Field(default=None, alias="operationId")
    workspace_id: str | None = Field(default=None, alias="workspaceId")
    marketplace_id: str | None = Field(default=None, alias="marketplaceId")
    status: MarketplaceActivityStatus
    error_code: str | None = Field(default=None, alias="errorCode")
    created_at: str = Field(alias="createdAt")

    model_config = {"populate_by_name": True, "extra": "forbid"}


class MarketplaceActivityListResult(BaseModel):
    """Marketplace activity list response."""

    items: list[MarketplaceActivityRecord]
    total: int
    page: int
    page_size: int = Field(alias="pageSize")
    total_pages: int = Field(alias="totalPages")

    model_config = {"populate_by_name": True}


class MarketplaceImportSource(BaseModel):
    """External source selected for Marketplace import scanning."""

    provider: MarketplaceImportProvider
    source_kind: MarketplaceImportSourceKind = Field(alias="sourceKind")
    source: str

    model_config = {"populate_by_name": True}


class MarketplaceImportUploadResult(BaseModel):
    """Uploaded local Marketplace import source."""

    source: MarketplaceImportSource
    file_name: str = Field(alias="fileName")

    model_config = {"populate_by_name": True}


class MarketplaceImportCandidate(BaseModel):
    """Marketplace package candidate found in an external source."""

    id: str
    provider: MarketplaceProvider
    package_id: str = Field(alias="packageId")
    display_name: str = Field(alias="displayName")
    source_path: str = Field(alias="sourcePath")
    duplicate: bool
    duplicate_action: MarketplaceDuplicateAction = Field(
        default="skip", alias="duplicateAction"
    )
    new_package_id: str | None = Field(default=None, alias="newPackageId")
    local_revision: str | None = Field(default=None, alias="localRevision")
    validation_severity: MarketplaceValidationSeverity = Field(
        default="none", alias="validationSeverity"
    )
    validation_results: list[MarketplaceValidationResult] = Field(
        default_factory=list, alias="validationResults"
    )
    source_metadata: dict[str, Any] = Field(
        default_factory=dict, alias="sourceMetadata"
    )
    family_id: str | None = Field(default=None, alias="familyId")
    family_display_name: str | None = Field(default=None, alias="familyDisplayName")
    source_identity: str | None = Field(default=None, alias="sourceIdentity")
    variant_status: MarketplaceImportVariantStatus = Field(
        default="new-family", alias="variantStatus"
    )
    variants: list[MarketplaceProviderVariant] = Field(default_factory=list)

    model_config = {"populate_by_name": True}


class MarketplaceImportRequest(BaseModel):
    """Import selected Marketplace candidates from an external source."""

    source: MarketplaceImportSource
    candidates: list[MarketplaceImportCandidate]

    model_config = {"populate_by_name": True}


class MarketplaceImportFailedCandidate(MarketplaceImportCandidate):
    """Import candidate that failed during copy."""

    error_code: str = Field(alias="errorCode")

    model_config = {"populate_by_name": True}


class MarketplaceImportResult(BaseModel):
    """Marketplace import result for selected candidates."""

    imported: list[MarketplacePackageSummary] = Field(default_factory=list)
    skipped: list[MarketplaceImportCandidate] = Field(default_factory=list)
    failed: list[MarketplaceImportFailedCandidate] = Field(default_factory=list)
    warnings: list[MarketplaceValidationResult] = Field(default_factory=list)

    model_config = {"populate_by_name": True}


class MarketplacePluginInstallRequest(BaseModel):
    """Install a Marketplace plugin into a workspace runtime."""

    provider: MarketplaceProvider
    package_id: str = Field(
        alias="packageId",
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$",
    )
    revision: str = Field(pattern=r"^[0-9a-f]{64}$")
    workspace_id: str = Field(alias="workspaceId", min_length=1, max_length=255)

    model_config = ConfigDict(
        populate_by_name=True,
        extra="forbid",
        strict=True,
    )


class MarketplaceUserCopyRequest(BaseModel):
    """Identify one package and workspace for a one-shot user-scope copy."""

    provider: MarketplaceProvider
    package_id: str = Field(
        alias="packageId",
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$",
    )
    revision: str = Field(pattern=r"^[0-9a-f]{64}$")
    workspace_id: str = Field(alias="workspaceId", min_length=1, max_length=255)

    model_config = ConfigDict(
        populate_by_name=True,
        extra="forbid",
        strict=True,
    )


class MarketplaceUserCopyOverwriteApproval(BaseModel):
    """Authorize overwriting one exact target revision."""

    target_identity: str = Field(
        alias="targetIdentity",
        min_length=1,
        max_length=1024,
    )
    expected_revision: str = Field(
        alias="expectedRevision",
        pattern=r"^[0-9a-f]{64}$",
    )

    model_config = ConfigDict(
        populate_by_name=True,
        extra="forbid",
        strict=True,
    )


class MarketplaceUserCopyApplyRequest(MarketplaceUserCopyRequest):
    """Apply one preflighted user-scope copy plan."""

    expected_source_digest: str = Field(
        alias="expectedSourceDigest",
        pattern=r"^[0-9a-f]{64}$",
    )
    expected_materialization_digest: str = Field(
        alias="expectedMaterializationDigest",
        pattern=r"^[0-9a-f]{64}$",
    )
    overwrite_approvals: list[MarketplaceUserCopyOverwriteApproval] = Field(
        default_factory=list,
        alias="overwriteApprovals",
        max_length=500,
    )

    model_config = ConfigDict(
        populate_by_name=True,
        extra="forbid",
        strict=True,
    )


class MarketplaceUserCopyResource(BaseModel):
    """One safe, non-conflicting operation in a user-copy plan."""

    resource_type: MarketplaceUserCopyResourceType = Field(alias="resourceType")
    resource_id: str = Field(alias="resourceId", min_length=1, max_length=1024)
    source_locator: str = Field(
        alias="sourceLocator",
        min_length=1,
        max_length=1024,
    )
    target_locator: str = Field(
        alias="targetLocator",
        min_length=1,
        max_length=1024,
    )
    operation: MarketplaceUserCopyOperation

    model_config = ConfigDict(
        populate_by_name=True,
        extra="forbid",
        strict=True,
    )


class MarketplaceUserCopyConflict(BaseModel):
    """One exact target conflict that can require overwrite approval."""

    resource_type: MarketplaceUserCopyResourceType = Field(alias="resourceType")
    resource_id: str = Field(alias="resourceId", min_length=1, max_length=1024)
    source_locator: str = Field(
        alias="sourceLocator",
        min_length=1,
        max_length=1024,
    )
    target_locator: str = Field(
        alias="targetLocator",
        min_length=1,
        max_length=1024,
    )
    target_identity: str = Field(
        alias="targetIdentity",
        min_length=1,
        max_length=1024,
    )
    baseline_revision: str = Field(
        alias="baselineRevision",
        pattern=r"^[0-9a-f]{64}$",
    )
    incoming_digest: str = Field(
        alias="incomingDigest",
        pattern=r"^[0-9a-f]{64}$",
    )
    overwritable: Literal[True]

    model_config = ConfigDict(
        populate_by_name=True,
        extra="forbid",
        strict=True,
    )

    @field_validator("overwritable", mode="before")
    @classmethod
    def validate_overwritable_is_boolean_true(cls, value: Any) -> Any:
        """Reject equality-compatible scalar coercion such as integer one."""

        if type(value) is not bool or value is not True:
            raise ValueError("User-copy conflicts must be explicitly overwritable")
        return value


class MarketplaceUserCopyBlockingIssue(BaseModel):
    """Sanitized issue that blocks a one-shot user copy."""

    resource_type: MarketplaceUserCopyResourceType | None = Field(
        default=None, alias="resourceType"
    )
    resource_id: str | None = Field(
        default=None,
        alias="resourceId",
        min_length=1,
        max_length=1024,
    )
    source_locator: str | None = Field(
        default=None,
        alias="sourceLocator",
        min_length=1,
        max_length=1024,
    )
    target_locator: str | None = Field(
        default=None,
        alias="targetLocator",
        min_length=1,
        max_length=1024,
    )
    error_code: MarketplaceUserCopyBlockingErrorCode = Field(alias="errorCode")

    model_config = ConfigDict(
        populate_by_name=True,
        extra="forbid",
        strict=True,
    )


class MarketplaceUserCopyPreflightResult(BaseModel):
    """One-shot user-copy plan returned by Runtime through Manager."""

    status: Literal["ready", "confirmation-required", "blocked"]
    provider: MarketplaceProvider
    package_id: str = Field(
        alias="packageId",
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$",
    )
    workspace_id: str = Field(alias="workspaceId", min_length=1, max_length=255)
    source_digest: str = Field(alias="sourceDigest", pattern=r"^[0-9a-f]{64}$")
    profile_digest: str = Field(
        alias="profileDigest",
        pattern=r"^[0-9a-f]{64}$",
    )
    materialization_digest: str = Field(
        alias="materializationDigest",
        pattern=r"^[0-9a-f]{64}$",
    )
    resources: list[MarketplaceUserCopyResource] = Field(
        default_factory=list,
        max_length=500,
    )
    conflicts: list[MarketplaceUserCopyConflict] = Field(
        default_factory=list,
        max_length=500,
    )
    blocking_issues: list[MarketplaceUserCopyBlockingIssue] = Field(
        default_factory=list,
        alias="blockingIssues",
        max_length=500,
    )

    model_config = ConfigDict(
        populate_by_name=True,
        extra="forbid",
        strict=True,
    )

    @model_validator(mode="after")
    def validate_status(self) -> MarketplaceUserCopyPreflightResult:
        """Status must agree with conflicts and blocking issues."""

        if len(self.resources) + len(self.conflicts) > 500:
            raise ValueError("User-copy plan exceeds the resource limit")
        conflict_identities = [
            conflict.target_identity.casefold() for conflict in self.conflicts
        ]
        if len(conflict_identities) != len(set(conflict_identities)):
            raise ValueError("User-copy conflict identities must be unique")
        if self.status == "blocked" and not self.blocking_issues:
            raise ValueError("Blocked user-copy plan is missing a blocking issue")
        if self.status == "confirmation-required" and (
            self.blocking_issues or not self.conflicts
        ):
            raise ValueError("User-copy confirmation state is inconsistent")
        if self.status == "ready" and (self.blocking_issues or self.conflicts):
            raise ValueError("Ready user-copy plan contains unresolved issues")
        return self


class MarketplaceUserCopyApplyResult(BaseModel):
    """Completed one-shot user-copy result with no durable installation."""

    status: Literal["completed"]
    operation_id: str = Field(
        alias="operationId",
        pattern=r"^[0-9a-f]{32}$",
    )
    provider: MarketplaceProvider
    package_id: str = Field(
        alias="packageId",
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$",
    )
    workspace_id: str = Field(alias="workspaceId", min_length=1, max_length=255)
    created_count: int = Field(alias="createdCount", ge=0, le=500)
    merged_count: int = Field(alias="mergedCount", ge=0, le=500)
    unchanged_count: int = Field(alias="unchangedCount", ge=0, le=500)
    overwritten_count: int = Field(alias="overwrittenCount", ge=0, le=500)

    model_config = ConfigDict(
        populate_by_name=True,
        extra="forbid",
        strict=True,
    )

    @model_validator(mode="after")
    def validate_resource_count(self) -> MarketplaceUserCopyApplyResult:
        """One operation cannot report more resources than its bounded plan."""

        if (
            self.created_count
            + self.merged_count
            + self.unchanged_count
            + self.overwritten_count
            > 500
        ):
            raise ValueError("User-copy result exceeds the resource limit")
        return self


class MarketplacePluginCommandResult(BaseModel):
    """Terminal result from one provider CLI installation command."""

    status: MarketplacePluginCommandStatus
    provider: MarketplaceProvider
    package_id: str = Field(
        alias="packageId",
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$",
    )
    marketplace_id: str = Field(
        alias="marketplaceId",
        pattern=r"^[a-z0-9][a-z0-9._-]{0,127}$",
    )
    workspace_id: str = Field(alias="workspaceId", min_length=1, max_length=255)
    operation_id: str = Field(
        alias="operationId",
        pattern=r"^[0-9a-f]{32}$",
    )
    stage: MarketplacePluginCommandStage
    exit_code: int | None = Field(alias="exitCode")
    cli_message: str | None = Field(
        default=None,
        alias="cliMessage",
        max_length=4096,
    )
    stdout: str | None = Field(default=None, max_length=65536)
    stderr: str | None = Field(default=None, max_length=65536)
    truncated: bool = False

    model_config = ConfigDict(
        populate_by_name=True,
        extra="forbid",
        strict=True,
    )

    @model_validator(mode="after")
    def validate_terminal_outcome(self) -> MarketplacePluginCommandResult:
        """Keep Runtime terminal status and command stage consistent."""

        if (self.status == "installed") != (self.stage == "completed"):
            raise ValueError("marketplace.install.runtime_contract_invalid")
        return self


class MarketplacePackageCreateRequest(BaseModel):
    """Create Marketplace package request."""

    provider: MarketplaceProvider
    package_id: str = Field(alias="packageId")
    display_name: str = Field(alias="displayName")
    description: str = ""

    model_config = {"populate_by_name": True}


class MarketplacePackageMutationResult(BaseModel):
    """Resource-scoped Marketplace package mutation result."""

    success: Literal[True] = True
    path: str
    revision: str
    owner_file_path: str | None = Field(default=None, alias="ownerFilePath")
    base_entry_fingerprint: str | None = Field(
        default=None,
        alias="baseEntryFingerprint",
    )

    model_config = {
        "populate_by_name": True,
        "extra": "forbid",
        "strict": True,
    }


class MarketplaceDocumentMutationRequest(BaseModel):
    """Resource-scoped Marketplace document mutation request."""

    revision: str
    path: str
    content: str = ""
    owner_file_path: str | None = Field(default=None, alias="ownerFilePath")
    base_entry_fingerprint: str | None = Field(
        default=None, alias="baseEntryFingerprint"
    )

    model_config = {"populate_by_name": True}


class MarketplaceDocumentRenameRequest(BaseModel):
    """Resource-scoped Marketplace document rename request."""

    revision: str
    previous_path: str = Field(alias="previousPath")
    next_path: str = Field(alias="nextPath")
    owner_file_path: str | None = Field(default=None, alias="ownerFilePath")
    base_entry_fingerprint: str | None = Field(
        default=None, alias="baseEntryFingerprint"
    )

    model_config = {"populate_by_name": True}


class MarketplaceDocumentRemoveRequest(BaseModel):
    """Resource-scoped Marketplace document delete request."""

    revision: str
    path: str = ""
    owner_file_path: str | None = Field(default=None, alias="ownerFilePath")
    base_entry_fingerprint: str | None = Field(
        default=None, alias="baseEntryFingerprint"
    )

    model_config = {"populate_by_name": True}


class MarketplaceMcpServerCreateRequest(BaseModel):
    """Create one MCP server in the provider's canonical default owner."""

    revision: str
    name: str
    server: dict[str, Any] = Field(default_factory=dict)

    model_config = {
        "populate_by_name": True,
        "extra": "forbid",
        "strict": True,
    }


class MarketplaceMcpServerMutationRequest(BaseModel):
    """Revision- and owner-fenced MCP server update request."""

    revision: str
    server: dict[str, Any]
    owner_file_path: str = Field(alias="ownerFilePath", min_length=1)
    base_entry_fingerprint: str = Field(
        alias="baseEntryFingerprint",
        min_length=1,
    )

    model_config = {
        "populate_by_name": True,
        "extra": "forbid",
        "strict": True,
    }


class MarketplaceMcpServerDeleteRequest(BaseModel):
    """Revision- and owner-fenced MCP server delete request."""

    revision: str
    owner_file_path: str = Field(alias="ownerFilePath", min_length=1)
    base_entry_fingerprint: str = Field(
        alias="baseEntryFingerprint",
        min_length=1,
    )

    model_config = {
        "populate_by_name": True,
        "extra": "forbid",
        "strict": True,
    }


class MarketplaceBasicUpdateRequest(BaseModel):
    """Marketplace basic metadata update request."""

    revision: str
    display_name: str | None = Field(default=None, alias="displayName")
    description: str | None = None
    catalog_metadata: dict[str, Any] = Field(
        default_factory=dict, alias="catalogMetadata"
    )
    manifest_metadata: dict[str, Any] = Field(
        default_factory=dict, alias="manifestMetadata"
    )

    model_config = {"populate_by_name": True}


class MarketplacePackageDeleteRequest(BaseModel):
    """Delete Marketplace package request."""

    provider: MarketplaceProvider
    package_id: str = Field(alias="packageId")
    revision: str

    model_config = {"populate_by_name": True}


class MarketplacePackageDeleteResult(BaseModel):
    """Delete Marketplace package result."""

    deleted: bool
    revision: str | None = None
    error_code: str | None = Field(default=None, alias="errorCode")

    model_config = {"populate_by_name": True}
