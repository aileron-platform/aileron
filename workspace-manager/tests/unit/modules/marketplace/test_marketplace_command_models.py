"""Focused tests for Marketplace command, activity, and user-copy API models."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.modules.marketplace.models import (
    MARKETPLACE_COPYABLE_RESOURCE_TYPES,
    MarketplaceActivityRecord,
    MarketplacePackageDetail,
    MarketplacePluginCommandResult,
    MarketplacePluginInstallRequest,
    MarketplaceRegistryCatalog,
    MarketplaceRegistrySettings,
    MarketplaceUserCopyApplyRequest,
    MarketplaceUserCopyApplyResult,
    MarketplaceUserCopyBlockingIssue,
    MarketplaceUserCopyConflict,
    MarketplaceUserCopyPreflightResult,
    MarketplaceUserCopyRequest,
    MarketplaceUserCopyResource,
    MarketplaceSkippedUserCopyResource,
    MarketplaceImportRequest,
)


def test_import_request_requires_version_and_explicit_overwrite_choice() -> None:
    candidate = {
        "id": "codex:superpowers",
        "target_client": "codex",
        "packageFormat": "codex-native",
        "packageId": "superpowers",
        "version": "5.1.3",
        "displayName": "Superpowers",
        "sourcePath": "plugins/superpowers",
        "duplicate": False,
        "variantStatus": "new-family",
        "variants": [],
        "validationSeverity": "none",
        "validationResults": [],
    }
    payload = {
        "source": {
            "target_client": "codex",
            "sourceKind": "git",
            "source": "https://github.com/openai/plugins.git",
        },
        "candidates": [
            {
                **candidate,
                "import": {
                    "version": "5.1.3",
                    "overwrite": False,
                },
            }
        ],
    }

    request = MarketplaceImportRequest.model_validate(payload)

    assert request.candidates[0].import_options is not None
    assert request.candidates[0].import_options.version == "5.1.3"
    for invalid_candidate in (
        candidate,
        {
            **candidate,
            "import": {**payload["candidates"][0]["import"], "version": "latest"},
        },
    ):
        with pytest.raises(ValidationError):
            MarketplaceImportRequest.model_validate(
                {**payload, "candidates": [invalid_candidate]}
            )


def _plugin_result_payload(*, status: str = "installed") -> dict[str, object]:
    return {
        "status": status,
        "targetClient": "codex",
        "packageId": "review-helper",
        "marketplaceId": "aileron-team-tools",
        "workspaceId": "workspace-1",
        "operationId": "a" * 32,
        "stage": "completed" if status == "installed" else "plugin-install",
        "exitCode": 0 if status == "installed" else 1,
        "cliMessage": None if status == "installed" else "CLI rejected install",
        "stdout": "installed",
        "stderr": None,
        "truncated": False,
    }


def test_plugin_request_has_no_installation_mode_compatibility_field() -> None:
    payload = {
        "targetClient": "codex",
        "packageFormat": "codex-native",
        "packageId": "review-helper",
        "version": "1.2.3",
        "workspaceId": "workspace-1",
    }

    request = MarketplacePluginInstallRequest.model_validate(payload)

    assert request.package_id == "review-helper"
    with pytest.raises(ValidationError):
        MarketplacePluginInstallRequest.model_validate(
            {**payload, "installationMode": "plugin"}
        )
    with pytest.raises(ValidationError):
        MarketplacePluginInstallRequest.model_validate(
            {**payload, "sourceId": "codex:tools:repository", "revision": "a" * 40}
        )


def test_user_copy_request_and_approval_proofs_are_bounded() -> None:
    payload = {
        "packageFormat": "claude-native",
        "targetClient": "claude-code",
        "catalogPluginId": "managed/document-skills",
        "releaseRevision": "a" * 64,
        "workspaceId": "workspace-1",
    }

    assert (
        MarketplaceUserCopyRequest.model_validate(payload).release_revision == "a" * 64
    )
    for invalid in ("", "A" * 64, "a" * 63, "revision-1"):
        with pytest.raises(ValidationError):
            MarketplaceUserCopyRequest.model_validate(
                {**payload, "releaseRevision": invalid}
            )

    apply_payload = {
        **payload,
        "expectedProfileDigest": "f" * 64,
        "expectedSourceDigest": "b" * 64,
        "expectedProjectionDigest": "e" * 64,
        "expectedMaterializationDigest": "c" * 64,
        "acceptPartialCopy": False,
        "overwriteApprovals": [
            {
                "targetIdentity": "claude:skill:pdf",
                "expectedRevision": "d" * 64,
            }
        ],
    }
    assert (
        len(
            MarketplaceUserCopyApplyRequest.model_validate(
                apply_payload
            ).overwrite_approvals
        )
        == 1
    )
    with pytest.raises(ValidationError):
        MarketplaceUserCopyApplyRequest.model_validate(
            {
                **apply_payload,
                "overwriteApprovals": apply_payload["overwriteApprovals"] * 501,
            }
        )
    assert (
        MarketplaceUserCopyRequest.model_validate(
            {**payload, "catalogPluginId": "p" * 1024}
        ).catalog_plugin_id
        == "p" * 1024
    )
    with pytest.raises(ValidationError):
        MarketplaceUserCopyRequest.model_validate(
            {**payload, "catalogPluginId": "p" * 1025}
        )
    assert (
        MarketplaceUserCopyRequest.model_validate(
            {**payload, "workspaceId": "w" * 255}
        ).workspace_id
        == "w" * 255
    )
    with pytest.raises(ValidationError):
        MarketplaceUserCopyRequest.model_validate({**payload, "workspaceId": "w" * 256})


def test_user_copy_conflicts_are_explicitly_overwritable() -> None:
    payload = {
        "resourceType": "skill",
        "resourceId": "pdf",
        "sourceLocator": "skills/pdf",
        "targetLocator": "~/.claude/skills/pdf",
        "targetIdentity": "claude:skill:pdf",
        "baselineRevision": "a" * 64,
        "incomingDigest": "b" * 64,
        "overwritable": True,
    }

    assert MarketplaceUserCopyConflict.model_validate(payload).overwritable is True
    with pytest.raises(ValidationError):
        MarketplaceUserCopyConflict.model_validate({**payload, "overwritable": False})
    with pytest.raises(ValidationError):
        MarketplaceUserCopyConflict.model_validate({**payload, "overwritable": 1})
    with pytest.raises(ValidationError):
        MarketplaceUserCopyConflict.model_validate(
            {**payload, "targetIdentity": "i" * 1025}
        )
    assert (
        MarketplaceUserCopyConflict.model_validate(
            {**payload, "resourceId": "r" * 1024}
        ).resource_id
        == "r" * 1024
    )
    with pytest.raises(ValidationError):
        MarketplaceUserCopyConflict.model_validate(
            {**payload, "resourceId": "r" * 1025}
        )
    with pytest.raises(ValidationError):
        MarketplaceUserCopyConflict.model_validate({**payload, "resourceType": "agent"})
    with pytest.raises(ValidationError):
        MarketplaceUserCopyResource.model_validate(
            {
                "resourceType": "app",
                "resourceId": "unsupported",
                "sourceLocator": "apps/unsupported",
                "targetLocator": "~/.claude/apps/unsupported",
                "operation": "create",
            }
        )
    with pytest.raises(ValidationError):
        MarketplaceUserCopyBlockingIssue.model_validate(
            {
                "resourceType": "skill",
                "resourceId": "pdf",
                "errorCode": "marketplace.user_copy.unknown",
            }
        )
    assert (
        MarketplaceUserCopyBlockingIssue.model_validate(
            {
                "resourceType": "apps",
                "resourceId": "apps",
                "sourceLocator": ".codex-plugin/plugin.json#/apps",
                "errorCode": "marketplace.user_copy.unsupported_resource",
            }
        ).resource_type
        == "apps"
    )
    assert MarketplaceUserCopyBlockingIssue.model_validate(
        {
            "resourceType": "structured",
            "sourceLocator": ".app.json",
            "errorCode": "marketplace.user_copy.source_missing",
        }
    ).error_code == "marketplace.user_copy.source_missing"


def test_user_copy_models_reject_scalar_coercion_at_public_boundaries() -> None:
    request = {
        "packageFormat": "claude-native",
        "targetClient": "claude-code",
        "catalogPluginId": "managed/document-skills",
        "releaseRevision": "a" * 64,
        "workspaceId": "workspace-1",
    }
    apply_request = {
        **request,
        "expectedProfileDigest": "f" * 64,
        "expectedSourceDigest": "b" * 64,
        "expectedProjectionDigest": "e" * 64,
        "expectedMaterializationDigest": "c" * 64,
        "acceptPartialCopy": False,
        "overwriteApprovals": [],
    }
    preflight = {
        "status": "ready",
        "packageFormat": "claude-native",
        "targetClient": "claude-code",
        "catalogPluginId": "managed/document-skills",
        "releaseRevision": "a" * 64,
        "workspaceId": "workspace-1",
        "sourceDigest": "b" * 64,
        "profileDigest": "c" * 64,
        "materializationDigest": "d" * 64,
        "projectionDigest": "e" * 64,
        "resources": [],
        "skippedResources": [],
        "conflicts": [],
        "blockingIssues": [],
    }
    result = {
        "status": "completed",
        "operationId": "1" * 32,
        "packageFormat": "claude-native",
        "targetClient": "claude-code",
        "catalogPluginId": "managed/document-skills",
        "releaseRevision": "a" * 64,
        "workspaceId": "workspace-1",
        "createdCount": 1,
        "mergedCount": 0,
        "unchangedCount": 0,
        "overwrittenCount": 0,
        "skippedCount": 0,
    }

    with pytest.raises(ValidationError):
        MarketplaceUserCopyRequest.model_validate(
            {**request, "releaseRevision": b"a" * 64}
        )
    with pytest.raises(ValidationError):
        MarketplaceUserCopyApplyRequest.model_validate(
            {**apply_request, "expectedSourceDigest": b"b" * 64}
        )
    with pytest.raises(ValidationError):
        MarketplaceUserCopyPreflightResult.model_validate(
            {**preflight, "sourceDigest": b"b" * 64}
        )
    for coerced in (True, "1", 1.0):
        with pytest.raises(ValidationError):
            MarketplaceUserCopyApplyResult.model_validate(
                {**result, "createdCount": coerced}
            )
    with pytest.raises(ValidationError):
        MarketplaceUserCopyApplyResult.model_validate({**result, "createdCount": 501})
    with pytest.raises(ValidationError):
        MarketplaceUserCopyPreflightResult.model_validate(
            {
                **preflight,
                "resources": [
                    {
                        "resourceType": "skill",
                        "resourceId": "pdf",
                        "sourceLocator": "s" * 1025,
                        "targetLocator": "~/.claude/skills/pdf",
                        "operation": "create",
                    }
                ],
            }
        )
    bounded_resource = {
        "resourceType": "dependency-payload",
        "resourceId": "r" * 1024,
        "sourceLocator": "s" * 1024,
        "targetLocator": "t" * 1024,
        "operation": "create",
    }
    assert (
        MarketplaceUserCopyPreflightResult.model_validate(
            {**preflight, "resources": [bounded_resource]}
        )
        .resources[0]
        .resource_id
        == "r" * 1024
    )
    with pytest.raises(ValidationError):
        MarketplaceUserCopyPreflightResult.model_validate(
            {
                **preflight,
                "resources": [{**bounded_resource, "resourceId": "r" * 1025}],
            }
        )


def test_skipped_user_copy_resource_accepts_non_projectable_source_type() -> None:
    skipped = MarketplaceSkippedUserCopyResource.model_validate(
        {
            "code": "unsupported-resource",
            "resourceType": "apps",
            "resourceId": "apps",
            "sourceLocator": ".codex-plugin/plugin.json#/apps",
        }
    )

    assert skipped.resource_type == "apps"


def test_user_copy_preflight_status_matches_issues() -> None:
    base = {
        "packageFormat": "claude-native",
        "targetClient": "claude-code",
        "catalogPluginId": "managed/document-skills",
        "releaseRevision": "a" * 64,
        "workspaceId": "workspace-1",
        "sourceDigest": "a" * 64,
        "profileDigest": "b" * 64,
        "materializationDigest": "c" * 64,
        "projectionDigest": "d" * 64,
        "resources": [],
        "skippedResources": [],
        "conflicts": [],
        "blockingIssues": [],
    }

    assert (
        MarketplaceUserCopyPreflightResult.model_validate(
            {**base, "status": "ready"}
        ).status
        == "ready"
    )
    with pytest.raises(ValidationError):
        MarketplaceUserCopyPreflightResult.model_validate(
            {**base, "status": "confirmation-required"}
        )
    with pytest.raises(ValidationError):
        MarketplaceUserCopyPreflightResult.model_validate({**base, "status": "blocked"})


def test_user_copy_preflight_bounds_total_resources_and_casefold_identities() -> None:
    base = {
        "status": "confirmation-required",
        "packageFormat": "claude-native",
        "targetClient": "claude-code",
        "catalogPluginId": "managed/document-skills",
        "releaseRevision": "a" * 64,
        "workspaceId": "workspace-1",
        "sourceDigest": "a" * 64,
        "profileDigest": "b" * 64,
        "materializationDigest": "c" * 64,
        "projectionDigest": "f" * 64,
        "resources": [
            {
                "resourceType": "skill",
                "resourceId": "pdf",
                "sourceLocator": "skills/pdf",
                "targetLocator": "~/.claude/skills/pdf",
                "operation": "create",
            }
        ],
        "skippedResources": [],
        "conflicts": [
            {
                "resourceType": "skill",
                "resourceId": "docx",
                "sourceLocator": "skills/docx",
                "targetLocator": "~/.claude/skills/docx",
                "targetIdentity": "claude:skill:docx",
                "baselineRevision": "d" * 64,
                "incomingDigest": "e" * 64,
                "overwritable": True,
            }
        ],
        "blockingIssues": [],
    }

    with pytest.raises(ValidationError):
        MarketplaceUserCopyPreflightResult.model_validate(
            {**base, "resources": base["resources"] * 500}
        )
    with pytest.raises(ValidationError):
        MarketplaceUserCopyPreflightResult.model_validate(
            {
                **base,
                "conflicts": [
                    base["conflicts"][0],
                    {
                        **base["conflicts"][0],
                        "targetIdentity": "CLAUDE:SKILL:DOCX",
                    },
                ],
            }
        )


def test_user_copy_apply_result_bounds_total_resource_count() -> None:
    payload = {
        "status": "completed",
        "operationId": "1" * 32,
        "packageFormat": "claude-native",
        "targetClient": "claude-code",
        "catalogPluginId": "managed/document-skills",
        "releaseRevision": "a" * 64,
        "workspaceId": "workspace-1",
        "createdCount": 500,
        "mergedCount": 0,
        "unchangedCount": 0,
        "overwrittenCount": 0,
        "skippedCount": 0,
    }

    assert MarketplaceUserCopyApplyResult.model_validate(payload).created_count == 500
    with pytest.raises(ValidationError):
        MarketplaceUserCopyApplyResult.model_validate({**payload, "mergedCount": 1})


def test_plugin_result_is_terminal_cli_output_and_rejects_lifecycle_fields() -> None:
    result = MarketplacePluginCommandResult.model_validate(_plugin_result_payload())

    assert result.status == "installed"
    assert result.stage == "completed"
    assert result.exit_code == 0
    for field, value in (
        ("installationMode", "plugin"),
        ("installationId", "installation-1"),
        ("contentStatus", "verified"),
        ("projectionStale", False),
        ("cleanupPending", False),
    ):
        with pytest.raises(ValidationError):
            MarketplacePluginCommandResult.model_validate(
                {**_plugin_result_payload(), field: value}
            )


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("operationId", "not-hex"),
        ("packageId", "invalid package"),
        ("marketplaceId", "Invalid-Marketplace"),
        ("workspaceId", ""),
        ("cliMessage", "x" * 4097),
        ("stdout", "x" * 262145),
        ("stderr", "x" * 262145),
    ),
)
def test_plugin_result_rejects_out_of_contract_fields(
    field: str,
    value: object,
) -> None:
    with pytest.raises(ValidationError):
        MarketplacePluginCommandResult.model_validate(
            {**_plugin_result_payload(), field: value}
        )


@pytest.mark.parametrize(
    ("status", "stage"),
    (
        ("installed", "plugin-install"),
        ("failed", "completed"),
    ),
)
def test_plugin_result_requires_consistent_terminal_outcome(
    status: str,
    stage: str,
) -> None:
    with pytest.raises(ValidationError):
        MarketplacePluginCommandResult.model_validate(
            {
                **_plugin_result_payload(),
                "status": status,
                "stage": stage,
            }
        )


def test_activity_exposes_terminal_audit_without_installation_projection() -> None:
    activity = MarketplaceActivityRecord.model_validate(
        {
            "id": "activity-1",
            "action": "copy",
            "packageFormat": "claude-native",
            "targetClient": "claude-code",
            "packageId": "document-skills",
            "operationId": "operation-1",
            "workspaceId": "workspace-1",
            "marketplaceId": None,
            "status": "succeeded",
            "errorCode": None,
            "createdAt": "2026-07-25T00:00:00Z",
        }
    )

    assert activity.action == "copy"
    for field in ("installationId", "resolvedCommit", "contentDigest"):
        with pytest.raises(ValidationError):
            MarketplaceActivityRecord.model_validate(
                {
                    **activity.model_dump(by_alias=True),
                    field: "legacy",
                }
            )


def test_registry_catalog_and_settings_require_canonical_identity() -> None:
    catalog = MarketplaceRegistryCatalog.model_validate(
        {
            "schemaVersion": 1,
            "marketplaceId": "aileron-team-tools",
            "displayName": "Aileron Team Tools",
            "owner": {
                "name": "Marketplace Maintainer",
                "email": "marketplace@example.com",
            },
            "description": "Internal tools",
            "publishBranch": "main",
            "packages": [],
        }
    )
    assert catalog.marketplace_id == "aileron-team-tools"
    with pytest.raises(ValidationError):
        MarketplaceRegistryCatalog.model_validate(
            {
                **catalog.model_dump(by_alias=True),
                "marketplaceId": "claude-community",
            }
        )
    with pytest.raises(ValidationError):
        MarketplaceRegistrySettings.model_validate(
            {
                "displayName": "Aileron Team Tools",
                "rootPath": "/registry",
                "status": "ready",
                "description": "",
                "maintainerName": "",
                "maintainerEmail": "",
            }
        )


def test_copy_resource_types_do_not_model_plugin_install_projection() -> None:
    assert {"agent", "lsp", "app"}.isdisjoint(MARKETPLACE_COPYABLE_RESOURCE_TYPES)
    assert "subagent" in MARKETPLACE_COPYABLE_RESOURCE_TYPES


def test_package_detail_does_not_embed_user_copy_capability() -> None:
    assert "user_copy_capability" not in MarketplacePackageDetail.model_fields
