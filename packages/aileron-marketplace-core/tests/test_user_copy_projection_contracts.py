from __future__ import annotations

import pytest
from aileron_marketplace_core import (
    PluginPackageFormat,
    PluginReleaseIdentity,
    UserCopyProjectionApplyMetadataContract,
    UserCopyProjectionApplyResultContract,
    UserCopyProjectionPreflightRequestContract,
    UserCopyProjectionPreflightResultContract,
    UserCopySourceProfile,
)
from pydantic import ValidationError


def _request_payload() -> dict[str, object]:
    profile = UserCopySourceProfile(
        package_format=PluginPackageFormat.AGENT_PLUGIN_V1,
        release_identity=PluginReleaseIdentity(
            catalog_plugin_id="managed/demo",
            revision="a" * 64,
        ),
        resources=(),
    )
    profile_payload = profile.canonical_dict()
    profile_payload["profileDigest"] = profile.profile_digest
    return {
        "packageFormat": "agent-plugin/1.0.0",
        "targetClient": "codex",
        "catalogPluginId": "managed/demo",
        "releaseRevision": "a" * 64,
        "workspaceId": "workspace-1",
        "runtimeInstanceId": "11111111-1111-4111-8111-111111111111",
        "expectedSourceDigest": "b" * 64,
        "expectedProfileVersion": 2,
        "expectedProfileDigest": profile.profile_digest,
        "sourceProfile": profile_payload,
    }


def test_projection_request_uses_format_and_client() -> None:
    request = UserCopyProjectionPreflightRequestContract.from_wire(_request_payload())

    assert request.package_format == "agent-plugin/1.0.0"
    assert request.target_client == "codex"


def test_projection_request_recomputes_the_source_profile_digest() -> None:
    payload = _request_payload()
    payload["sourceProfile"]["profileDigest"] = "c" * 64  # type: ignore[index]
    payload["expectedProfileDigest"] = "c" * 64
    with pytest.raises(ValidationError):
        UserCopyProjectionPreflightRequestContract.from_wire(payload)


def test_skipped_projection_requires_confirmation() -> None:
    result = UserCopyProjectionPreflightResultContract(
        status="confirmation-required",
        packageFormat="agent-plugin/1.0.0",
        targetClient="codex",
        catalogPluginId="managed/demo",
        releaseRevision="a" * 64,
        workspaceId="workspace-1",
        runtimeInstanceId="11111111-1111-4111-8111-111111111111",
        targetClientStateRootId=f"tcsr_{'d' * 64}",
        sourceDigest="b" * 64,
        profileVersion=2,
        profileDigest="c" * 64,
        projectionDigest="e" * 64,
        materializationDigest="f" * 64,
        resources=[],
        skippedResources=[
            {
                "code": "unsupported-resource",
                "resourceType": "apps",
                "resourceId": "apps",
                "sourceLocator": ".codex-plugin/plugin.json#/apps",
            },
            {
                "code": "mcp-transport-unsupported",
                "resourceType": "mcp",
                "resourceId": "legacy",
                "sourceLocator": "mcp.json",
            },
            {
                "code": "extension-unsupported",
                "resourceType": "extension",
                "resourceId": "com.example.review",
                "sourceLocator": "plugin.json",
            },
            {
                "code": "nonportable-component-unsupported",
                "resourceType": "component",
                "resourceId": "hooks",
                "sourceLocator": "hooks",
            },
        ],
        conflicts=[],
        blockingIssues=[],
    )

    assert result.status == "confirmation-required"
    assert result.skipped_resources[0].resource_type == "apps"
    invalid = result.to_wire()
    invalid["status"] = "ready"
    with pytest.raises(ValidationError):
        UserCopyProjectionPreflightResultContract.from_wire(invalid)


def test_blocking_issue_preserves_unsupported_source_resource_type() -> None:
    result = UserCopyProjectionPreflightResultContract(
        status="blocked",
        packageFormat="codex-native",
        targetClient="codex",
        catalogPluginId="managed/demo",
        releaseRevision="a" * 64,
        workspaceId="workspace-1",
        runtimeInstanceId="11111111-1111-4111-8111-111111111111",
        targetClientStateRootId=f"tcsr_{'d' * 64}",
        sourceDigest="b" * 64,
        profileVersion=2,
        profileDigest="c" * 64,
        projectionDigest="e" * 64,
        materializationDigest="f" * 64,
        resources=[],
        skippedResources=[],
        conflicts=[],
        blockingIssues=[
            {
                "code": "marketplace.user_copy.unsupported_resource",
                "resourceType": "apps",
                "resourceId": "apps",
                "sourceLocator": ".codex-plugin/plugin.json#/apps",
            },
            {
                "code": "marketplace.user_copy.source_missing",
                "resourceType": "structured",
                "sourceLocator": ".app.json",
            }
        ],
    )

    assert result.blocking_issues[0].resource_type == "apps"
    assert result.blocking_issues[1].code == "marketplace.user_copy.source_missing"


def test_preflight_rejects_duplicate_target_identities_across_plan_items() -> None:
    payload = UserCopyProjectionPreflightResultContract(
        status="ready",
        packageFormat="codex-native",
        targetClient="codex",
        catalogPluginId="managed/demo",
        releaseRevision="a" * 64,
        workspaceId="workspace-1",
        runtimeInstanceId="11111111-1111-4111-8111-111111111111",
        targetClientStateRootId=f"tcsr_{'d' * 64}",
        sourceDigest="b" * 64,
        profileVersion=2,
        profileDigest="c" * 64,
        projectionDigest="e" * 64,
        materializationDigest="f" * 64,
        resources=[
            {
                "resourceType": "skill",
                "resourceId": "one",
                "sourceLocator": "skills/one",
                "targetLocator": "~/.codex/skills/shared",
                "targetIdentity": "codex:skill:shared",
                "action": "create",
                "incomingDigest": "1" * 64,
            }
        ],
        skippedResources=[],
        conflicts=[],
        blockingIssues=[],
    ).to_wire()
    payload["resources"].append(
        {
            **payload["resources"][0],
            "resourceId": "two",
            "sourceLocator": "skills/two",
        }
    )

    with pytest.raises(ValidationError):
        UserCopyProjectionPreflightResultContract.from_wire(payload)


def test_apply_requires_exact_partial_copy_confirmation() -> None:
    metadata = _apply_metadata(accept_partial_copy=True)
    assert metadata.expected_projection_digest == "d" * 64

    rejected = metadata.to_wire()
    rejected["acceptPartialCopy"] = False
    with pytest.raises(ValidationError):
        UserCopyProjectionApplyMetadataContract.from_wire(rejected)


def test_apply_receipt_matches_projection_identity_and_counts() -> None:
    metadata = _apply_metadata(accept_partial_copy=True)
    result = UserCopyProjectionApplyResultContract(
        operationId="a" * 32,
        packageFormat="agent-plugin/1.0.0",
        targetClient="codex",
        catalogPluginId="catalog/plugin",
        releaseRevision="b" * 64,
        workspaceId="workspace-1",
        createdCount=1,
        mergedCount=0,
        unchangedCount=0,
        overwrittenCount=0,
        skippedCount=1,
    )

    metadata.verify_result(result, expected_counts=(1, 0, 0, 0, 1))

    with pytest.raises(ValueError):
        metadata.verify_result(result, expected_counts=(0, 0, 0, 0, 1))


def _apply_metadata(
    *,
    accept_partial_copy: bool,
) -> UserCopyProjectionApplyMetadataContract:
    return UserCopyProjectionApplyMetadataContract(
        operationId="a" * 32,
        packageFormat="agent-plugin/1.0.0",
        targetClient="codex",
        catalogPluginId="catalog/plugin",
        releaseRevision="b" * 64,
        workspaceId="workspace-1",
        runtimeInstanceId="123e4567-e89b-12d3-a456-426614174000",
        targetClientStateRootId="tcsr_" + "c" * 64,
        expectedSourceDigest="1" * 64,
        expectedArchiveDigest="2" * 64,
        expectedPackageTreeDigest="3" * 64,
        expectedProfileVersion=2,
        expectedProfileDigest="4" * 64,
        expectedProjectionDigest="d" * 64,
        expectedMaterializationDigest="5" * 64,
        acceptPartialCopy=accept_partial_copy,
        expectedSkippedCount=1,
        overwriteApprovals=[],
    )
