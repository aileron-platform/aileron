"""Marketplace API models."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


MarketplaceProvider = Literal["claude-code", "codex", "gemini"]
MarketplaceImportProvider = Literal["all", "claude-code", "codex", "gemini"]
MarketplaceRegistryStatus = Literal["uninitialized", "ready", "busy", "error"]
MarketplacePackageType = Literal["plugin", "extension"]
MarketplaceSourceType = Literal["created", "imported", "cloned"]
MarketplaceValidationSeverity = Literal["none", "info", "warning", "error"]
MarketplaceActivityAction = Literal["import", "install", "delete"]
MarketplaceActivityStatus = Literal["success", "failed"]
MarketplaceImportSourceKind = Literal["git", "local"]
MarketplaceDuplicateAction = Literal["skip", "overwrite", "import-as-new"]
MarketplaceImportVariantStatus = Literal[
    "new-family",
    "add-variant",
    "duplicate-variant",
    "unrelated-duplicate",
    "invalid",
]
MarketplaceInstallStatus = Literal[
    "success",
    "failed",
    "timeout",
    "validation",
    "cliUnavailable",
    "cliVersionUnsupported",
    "cliCapabilityMissing",
    "runtimeUnavailable",
]


class MarketplaceCliCapabilities(BaseModel):
    """Detected provider CLI install capabilities."""

    supports_user_scope: bool = Field(default=False, alias="supportsUserScope")
    supports_marketplace_add: bool = Field(default=False, alias="supportsMarketplaceAdd")
    supports_extension_install: bool = Field(default=False, alias="supportsExtensionInstall")

    model_config = {"populate_by_name": True}


class MarketplaceOwnerMetadata(BaseModel):
    """Marketplace root owner metadata."""

    name: str = Field(description="Maintainer name")
    email: str = Field(description="Maintainer email")


class MarketplaceRegistryRootMetadataSavePayload(BaseModel):
    """Root metadata saved through Marketplace Settings General."""

    name: str = Field(description="Marketplace registry display name")
    owner: MarketplaceOwnerMetadata = Field(description="Marketplace owner metadata")
    description: str = Field(description="Marketplace registry description")


class MarketplaceRegistrySettings(BaseModel):
    """Marketplace registry settings response."""

    display_name: str = Field(alias="displayName")
    root_path: str = Field(alias="rootPath")
    status: MarketplaceRegistryStatus
    description: str = ""
    maintainer_name: str = Field(alias="maintainerName")
    maintainer_email: str = Field(alias="maintainerEmail")

    model_config = {"populate_by_name": True}


class MarketplaceRegistryInitResult(BaseModel):
    """Marketplace registry initialization result."""

    root_path: str = Field(alias="rootPath")
    created: bool
    claude_manifest_path: str = Field(alias="claudeManifestPath")
    codex_manifest_path: str = Field(alias="codexManifestPath")
    gemini_root_path: str = Field(alias="geminiRootPath")

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


class MarketplaceRegistryRemoteRequest(BaseModel):
    """Marketplace registry remote configuration request."""

    remote_url: str = Field(alias="remoteUrl")

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


class MarketplaceGitFileChange(BaseModel):
    """Marketplace registry Git file change."""

    path: str
    status: str
    type: Literal["added", "modified", "deleted", "renamed", "copied", "typechange", "unmerged", "untracked"]
    old_path: str | None = Field(default=None, alias="oldPath")

    model_config = {"populate_by_name": True}


class MarketplaceGitStatus(BaseModel):
    """Marketplace registry Git status response."""

    branch: str
    is_git_repo: bool = Field(alias="isGitRepo")
    staged: list[MarketplaceGitFileChange] = Field(default_factory=list)
    unstaged: list[MarketplaceGitFileChange] = Field(default_factory=list)
    untracked: list[MarketplaceGitFileChange] = Field(default_factory=list)
    staged_count: int = Field(alias="stagedCount")
    unstaged_count: int = Field(alias="unstagedCount")
    untracked_count: int = Field(alias="untrackedCount")

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

    paths: list[str]


class MarketplaceGitCommitRequest(BaseModel):
    """Marketplace registry Git commit request."""

    message: str
    paths: list[str] | None = None


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
    status: MarketplaceGitStatus | None = None

    model_config = {"populate_by_name": True}


class MarketplaceGitCommitListResult(BaseModel):
    """Marketplace registry Git commit list response."""

    page: int
    page_size: int = Field(alias="pageSize")
    total: int
    items: list[MarketplaceGitCommitSummary] = Field(default_factory=list)

    model_config = {"populate_by_name": True}


class MarketplaceGitCommitFilesResult(BaseModel):
    """Marketplace registry Git commit changed files response."""

    commit_id: str = Field(alias="commitId")
    files: list[MarketplaceGitFileChange] = Field(default_factory=list)

    model_config = {"populate_by_name": True}


class MarketplaceRegistrySshKeyResponse(BaseModel):
    """Marketplace registry SSH key metadata response."""

    exists: bool
    public_key: str | None = Field(default=None, alias="publicKey")
    fingerprint: str | None = None
    algorithm: str | None = None
    created_at: str | None = Field(default=None, alias="createdAt")

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
    package_type: MarketplacePackageType = Field(alias="packageType")
    package_id: str = Field(alias="packageId")
    display_name: str = Field(alias="displayName")
    version: str | None = None
    description: str | None = None
    category: str | None = None
    tags: list[str] = Field(default_factory=list)
    source_type: MarketplaceSourceType = Field(default="created", alias="sourceType")
    indexed_resource_names: list[str] = Field(default_factory=list, alias="indexedResourceNames")
    validation_severity: MarketplaceValidationSeverity = Field(default="none", alias="validationSeverity")
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
    source_types: list[MarketplaceSourceType] = Field(default_factory=list, alias="sourceTypes")
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

    model_config = {"populate_by_name": True}


class MarketplaceFeatureContent(BaseModel):
    """Aggregated provider-native content for Marketplace detail tabs."""

    agents_md: str | None = Field(default=None, alias="agentsMd")
    hooks: list[MarketplaceFeatureContentItem] = Field(default_factory=list)
    mcp_servers: list[MarketplaceFeatureContentItem] = Field(default_factory=list, alias="mcpServers")
    agents: list[MarketplaceFeatureContentItem] = Field(default_factory=list)
    commands: list[MarketplaceFeatureContentItem] = Field(default_factory=list)
    output_styles: list[MarketplaceFeatureContentItem] = Field(default_factory=list, alias="outputStyles")
    skills: list[MarketplaceFeatureContentItem] = Field(default_factory=list)
    policies: list[MarketplaceFeatureContentItem] = Field(default_factory=list)

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
    """Marketplace package detail response."""

    catalog_metadata: dict[str, Any] = Field(default_factory=dict, alias="catalogMetadata")
    manifest_metadata: dict[str, Any] = Field(default_factory=dict, alias="manifestMetadata")
    metadata_conflict: bool = Field(default=False, alias="metadataConflict")
    readme_markdown: str = Field(default="", alias="readmeMarkdown")
    feature_content: MarketplaceFeatureContent = Field(default_factory=MarketplaceFeatureContent, alias="featureContent")
    package_files: list[MarketplacePackageFile] = Field(default_factory=list, alias="packageFiles")
    validation_results: list[MarketplaceValidationResult] = Field(default_factory=list, alias="validationResults")
    activity: list[dict[str, Any]] = Field(default_factory=list)

    model_config = {"populate_by_name": True}


class MarketplaceActivityRecord(BaseModel):
    """Per-user Marketplace activity record."""

    id: str
    action: MarketplaceActivityAction
    provider: MarketplaceProvider | None = None
    package_id: str | None = Field(default=None, alias="packageId")
    status: MarketplaceActivityStatus
    error_code: str | None = Field(default=None, alias="errorCode")
    created_at: str = Field(alias="createdAt")

    model_config = {"populate_by_name": True}


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
    duplicate_action: MarketplaceDuplicateAction = Field(default="skip", alias="duplicateAction")
    new_package_id: str | None = Field(default=None, alias="newPackageId")
    local_revision: str | None = Field(default=None, alias="localRevision")
    validation_severity: MarketplaceValidationSeverity = Field(default="none", alias="validationSeverity")
    validation_results: list[MarketplaceValidationResult] = Field(default_factory=list, alias="validationResults")
    source_metadata: dict[str, Any] = Field(default_factory=dict, alias="sourceMetadata")
    family_id: str | None = Field(default=None, alias="familyId")
    family_display_name: str | None = Field(default=None, alias="familyDisplayName")
    source_identity: str | None = Field(default=None, alias="sourceIdentity")
    variant_status: MarketplaceImportVariantStatus = Field(default="new-family", alias="variantStatus")
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


class MarketplaceInstallRequest(BaseModel):
    """Install a Marketplace package into a workspace runtime."""

    provider: MarketplaceProvider
    package_id: str = Field(alias="packageId")
    revision: str
    workspace_id: str = Field(alias="workspaceId")

    model_config = {"populate_by_name": True}


class MarketplaceInstallResult(BaseModel):
    """Marketplace package install result."""

    status: MarketplaceInstallStatus
    provider: MarketplaceProvider
    package_id: str = Field(alias="packageId")
    workspace_id: str = Field(alias="workspaceId")
    error_code: str | None = Field(default=None, alias="errorCode")
    stdout: str | None = None
    stderr: str | None = None
    truncated: bool = False

    model_config = {"populate_by_name": True}


class MarketplaceInstallCommandPlan(BaseModel):
    """Provider CLI install command plan."""

    provider: MarketplaceProvider
    argv: list[str] = Field(min_length=1)
    cwd: str
    env: dict[str, str] = Field(default_factory=dict)
    timeout_ms: int = Field(default=120_000, alias="timeoutMs", ge=1)
    stdout_limit_bytes: int = Field(default=65_536, alias="stdoutLimitBytes", ge=1)
    stderr_limit_bytes: int = Field(default=65_536, alias="stderrLimitBytes", ge=1)
    redact_patterns: list[str] = Field(default_factory=list, alias="redactPatterns")

    model_config = {"populate_by_name": True}


class MarketplaceCliPreflightResult(BaseModel):
    """Provider CLI preflight result."""

    provider: MarketplaceProvider
    available: bool
    executable_path: str | None = Field(default=None, alias="executablePath")
    version: str | None = None
    capabilities: MarketplaceCliCapabilities = Field(default_factory=MarketplaceCliCapabilities)
    error_code: str | None = Field(default=None, alias="errorCode")

    model_config = {"populate_by_name": True}


class MarketplacePackageCreateRequest(BaseModel):
    """Create Marketplace package request."""

    provider: MarketplaceProvider
    package_id: str = Field(alias="packageId")
    display_name: str = Field(alias="displayName")
    description: str = ""

    model_config = {"populate_by_name": True}


class MarketplacePackageSaveRequest(BaseModel):
    """Save provider-native Marketplace package request."""

    provider: MarketplaceProvider
    package_id: str = Field(alias="packageId")
    revision: str
    listing: dict[str, Any] | None = None
    manifest: dict[str, Any] | None = None
    readme_markdown: str | None = Field(default=None, alias="readmeMarkdown")
    package_files: list[MarketplacePackageFile] | None = Field(default=None, alias="packageFiles")

    model_config = {"populate_by_name": True}


class MarketplacePackageSaveResult(BaseModel):
    """Save provider-native Marketplace package result."""

    package: MarketplacePackageDetail
    revision: str
    validation_results: list[MarketplaceValidationResult] = Field(default_factory=list, alias="validationResults")

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
