from __future__ import annotations

from copy import deepcopy

import pytest
from aileron_marketplace_core import (
    USER_COPY_PAYLOAD_ROOT_SENTINEL,
    MarketplaceUserCopyProfilePreview,
    UserCopyApplyMetadataContract,
    UserCopyApplyResultContract,
    UserCopyPreflightRequestContract,
    UserCopyPreflightResultContract,
)
from pydantic import ValidationError

from app.modules.internal.models import (
    MarketplacePluginCommandResult,
    MarketplacePluginInstallRequest,
)

RUNTIME_ID = "11111111-1111-4111-8111-111111111111"
PROVIDER_STATE_ROOT_ID = f"psr_{'e' * 64}"


def _plugin_request() -> dict[str, object]:
    return {
        "operationId": "d" * 32,
        "provider": "codex",
        "packageId": "review-helper",
        "marketplaceId": "aileron-tools",
        "remoteUrl": "git@git.example.com:team/marketplace.git",
        "publishRef": "main",
        "workspaceId": "workspace-1",
        "runtimeInstanceId": RUNTIME_ID,
    }


def _plugin_result() -> dict[str, object]:
    return {
        "status": "installed",
        "operationId": "d" * 32,
        "provider": "codex",
        "packageId": "review-helper",
        "marketplaceId": "aileron-tools",
        "workspaceId": "workspace-1",
        "stage": "completed",
        "exitCode": 0,
        "cliMessage": None,
        "stdout": "[]",
        "stderr": None,
        "truncated": False,
    }


def _profile_resource() -> dict[str, object]:
    return {
        "resourceType": "skill",
        "resourceId": "review",
        "sourceKind": "plugin-component",
        "sourceLocator": "skills/review",
        "targetResource": "skills",
        "copySemantics": "create-directory",
        "relativeTarget": "review",
        "sourceDigest": "a" * 64,
        "dependencyPayloadRequired": False,
        "dependencyPayloadProjectable": True,
    }


def _profile_preview() -> dict[str, object]:
    return {
        "profileVersion": 1,
        "provider": "codex",
        "profileDigest": "b" * 64,
        "resources": [_profile_resource()],
        "dependencyPayloads": [],
        "blockedResources": [],
    }


def _dependency_profile_preview() -> dict[str, object]:
    return {
        "profileVersion": 1,
        "provider": "codex",
        "profileDigest": "b" * 64,
        "resources": [
            {
                "resourceType": "mcp",
                "resourceId": "local",
                "sourceKind": "plugin-component",
                "sourceLocator": ".codex-plugin/plugin.json",
                "targetResource": "mcp",
                "copySemantics": "merge-config-entry",
                "jsonPointer": "/mcpServers/local",
                "sourceDigest": "a" * 64,
                "dependencyPayloadRequired": True,
                "dependencyPayloadProjectable": True,
                "structuredValueType": "object",
                "structuredValueTemplate": {
                    "command": (f"{USER_COPY_PAYLOAD_ROOT_SENTINEL}/bin/server.js")
                },
            }
        ],
        "dependencyPayloads": [
            {
                "sourceLocator": "bin/server.js",
                "sourceKind": "file",
                "contentDigest": "c" * 64,
            }
        ],
        "blockedResources": [],
    }


def _user_copy_preflight_request() -> dict[str, object]:
    preview = _profile_preview()
    return {
        "provider": "codex",
        "packageId": "review-helper",
        "revision": "a" * 64,
        "workspaceId": "workspace-1",
        "runtimeInstanceId": RUNTIME_ID,
        "expectedSourceDigest": MarketplaceUserCopyProfilePreview.model_validate(
            preview
        ).source_digest,
        "expectedProfileVersion": 1,
        "expectedProfileDigest": "b" * 64,
        "userCopyProfilePreview": preview,
    }


def _planned_resource() -> dict[str, object]:
    return {
        "resourceType": "skill",
        "resourceId": "review",
        "sourceLocator": "skills/review",
        "targetLocator": "~/.codex/skills/review",
        "targetIdentity": "codex:skill:review",
        "action": "create",
        "incomingDigest": "a" * 64,
    }


def _conflict() -> dict[str, object]:
    return {
        "code": "marketplace.user_copy.target_conflict",
        "resourceType": "skill",
        "resourceId": "review",
        "sourceLocator": "skills/review",
        "targetLocator": "~/.codex/skills/review",
        "targetIdentity": "codex:skill:review",
        "baselineRevision": "d" * 64,
        "incomingDigest": "a" * 64,
        "overwritable": True,
    }


def _user_copy_preflight_result(
    *,
    status: str = "ready",
) -> dict[str, object]:
    resources: list[dict[str, object]] = []
    conflicts: list[dict[str, object]] = []
    blocking_issues: list[dict[str, object]] = []
    if status == "ready":
        resources = [_planned_resource()]
    elif status == "confirmation-required":
        conflicts = [_conflict()]
    elif status == "blocked":
        blocking_issues = [{"code": "marketplace.user_copy.profile_empty"}]
    return {
        "status": status,
        "provider": "codex",
        "packageId": "review-helper",
        "revision": "a" * 64,
        "workspaceId": "workspace-1",
        "runtimeInstanceId": RUNTIME_ID,
        "providerStateRootId": PROVIDER_STATE_ROOT_ID,
        "sourceDigest": "c" * 64,
        "profileVersion": 1,
        "profileDigest": "b" * 64,
        "materializationDigest": "e" * 64,
        "resources": resources,
        "conflicts": conflicts,
        "blockingIssues": blocking_issues,
    }


def _apply_metadata() -> dict[str, object]:
    return {
        "operationId": "d" * 32,
        "provider": "codex",
        "packageId": "review-helper",
        "revision": "a" * 64,
        "workspaceId": "workspace-1",
        "runtimeInstanceId": RUNTIME_ID,
        "providerStateRootId": PROVIDER_STATE_ROOT_ID,
        "expectedSourceDigest": "b" * 64,
        "expectedArchiveDigest": "c" * 64,
        "expectedPackageTreeDigest": "d" * 64,
        "expectedProfileVersion": 1,
        "expectedProfileDigest": "e" * 64,
        "expectedMaterializationDigest": "f" * 64,
        "overwriteApprovals": [
            {
                "targetIdentity": "codex:skill:review",
                "expectedRevision": "1" * 64,
            }
        ],
    }


def _apply_result() -> dict[str, object]:
    return {
        "status": "completed",
        "operationId": "d" * 32,
        "provider": "codex",
        "packageId": "review-helper",
        "revision": "a" * 64,
        "workspaceId": "workspace-1",
        "createdCount": 1,
        "mergedCount": 0,
        "unchangedCount": 0,
        "overwrittenCount": 0,
    }


def test_plugin_install_request_is_minimal_and_strict() -> None:
    parsed = MarketplacePluginInstallRequest.model_validate(_plugin_request())
    assert parsed.provider == "codex"
    assert parsed.remote_url == "git@git.example.com:team/marketplace.git"

    for legacy_field in (
        "installationId",
        "operationKind",
        "providerStateRootId",
        "expectedCommit",
        "expectedPackageTreeDigest",
        "providerInstallScope",
    ):
        invalid = _plugin_request()
        invalid[legacy_field] = "legacy"
        with pytest.raises(ValidationError):
            MarketplacePluginInstallRequest.model_validate(invalid)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("workspaceId", 1),
        ("publishRef", 1),
        ("operationId", True),
        ("operationId", "11111111-1111-4111-8111-111111111111"),
    ],
)
def test_plugin_install_request_rejects_scalar_coercion(
    field: str,
    value: object,
) -> None:
    payload = _plugin_request()
    payload[field] = value

    with pytest.raises(ValidationError):
        MarketplacePluginInstallRequest.model_validate(payload)


def test_plugin_command_result_is_strict_and_terminal() -> None:
    parsed = MarketplacePluginCommandResult.model_validate(_plugin_result())
    assert parsed.status == "installed"
    assert parsed.stage == "completed"

    failed = _plugin_result()
    failed.update(
        {
            "status": "failed",
            "stage": "plugin-install",
            "exitCode": 2,
            "stderr": "permission denied",
        }
    )
    assert MarketplacePluginCommandResult.model_validate(failed).exit_code == 2

    for status, stage in (
        ("installed", "plugin-list"),
        ("failed", "completed"),
    ):
        inconsistent = _plugin_result()
        inconsistent.update({"status": status, "stage": stage})
        with pytest.raises(
            ValidationError,
            match="marketplace.install.runtime_contract_invalid",
        ):
            MarketplacePluginCommandResult.model_validate(inconsistent)

    extra = _plugin_result()
    for legacy_field in (
        "installationId",
        "remoteUrl",
        "publishRef",
        "runtimeInstanceId",
    ):
        extra = _plugin_result()
        extra[legacy_field] = "legacy"
        with pytest.raises(ValidationError):
            MarketplacePluginCommandResult.model_validate(extra)


def test_user_copy_profile_preview_accepts_plain_and_dependency_resources() -> None:
    plain = MarketplaceUserCopyProfilePreview.model_validate(_profile_preview())
    dependency = MarketplaceUserCopyProfilePreview.model_validate(
        _dependency_profile_preview()
    )

    assert plain.resources[0].dependency_payload_required is False
    assert dependency.dependency_payloads[0].source_locator == "bin/server.js"


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("profileVersion",), "1"),
        (("resources", 0, "dependencyPayloadRequired"), 0),
        (("resources", 0, "dependencyPayloadProjectable"), 1),
        (("resources", 0, "sourceDigest"), 1),
        (("resources", 0, "unexpected"), "value"),
    ],
)
def test_user_copy_profile_preview_rejects_coercion_and_extra_fields(
    path: tuple[object, ...],
    value: object,
) -> None:
    payload = _profile_preview()
    current: object = payload
    for part in path[:-1]:
        current = current[part]  # type: ignore[index]
    current[path[-1]] = value  # type: ignore[index]

    with pytest.raises(ValidationError):
        MarketplaceUserCopyProfilePreview.model_validate(payload)


def test_dependency_preview_rejects_missing_or_unused_payload_proofs() -> None:
    missing = _dependency_profile_preview()
    missing["dependencyPayloads"] = []
    with pytest.raises(
        ValidationError,
        match="marketplace.user_copy.profile_invalid",
    ):
        MarketplaceUserCopyProfilePreview.model_validate(missing)

    unused = _profile_preview()
    unused["dependencyPayloads"] = [
        {
            "sourceLocator": "bin/server.js",
            "sourceKind": "file",
            "contentDigest": "c" * 64,
        }
    ]
    with pytest.raises(
        ValidationError,
        match="marketplace.user_copy.profile_invalid",
    ):
        MarketplaceUserCopyProfilePreview.model_validate(unused)


@pytest.mark.parametrize(
    "template",
    [
        USER_COPY_PAYLOAD_ROOT_SENTINEL,
        f"prefix/{USER_COPY_PAYLOAD_ROOT_SENTINEL}/bin/server.js",
        f"{USER_COPY_PAYLOAD_ROOT_SENTINEL}/../server.js",
        f"{USER_COPY_PAYLOAD_ROOT_SENTINEL}/bin//server.js",
    ],
)
def test_dependency_preview_rejects_malformed_sentinel(
    template: str,
) -> None:
    payload = _dependency_profile_preview()
    payload["resources"][0]["structuredValueTemplate"] = {"command": template}

    with pytest.raises(
        ValidationError,
        match="marketplace.user_copy.profile_invalid",
    ):
        MarketplaceUserCopyProfilePreview.model_validate(payload)


def test_dependency_preview_requires_consistent_flags_type_and_template() -> None:
    payload = _dependency_profile_preview()
    resource = payload["resources"][0]
    resource["dependencyPayloadRequired"] = False
    resource["dependencyPayloadProjectable"] = False
    resource.pop("structuredValueTemplate")
    payload["dependencyPayloads"] = []
    with pytest.raises(ValidationError):
        MarketplaceUserCopyProfilePreview.model_validate(payload)

    missing_template = _dependency_profile_preview()
    missing_template["resources"][0].pop("structuredValueTemplate")
    with pytest.raises(ValidationError):
        MarketplaceUserCopyProfilePreview.model_validate(missing_template)

    wrong_type = _dependency_profile_preview()
    wrong_type["resources"][0]["structuredValueType"] = "array"
    with pytest.raises(ValidationError):
        MarketplaceUserCopyProfilePreview.model_validate(wrong_type)


def test_dependency_preview_accepts_unprojectable_proof_without_template() -> None:
    payload = _dependency_profile_preview()
    resource = payload["resources"][0]
    resource["dependencyPayloadProjectable"] = False
    resource.pop("structuredValueTemplate")
    payload["dependencyPayloads"] = []

    parsed = MarketplaceUserCopyProfilePreview.model_validate(payload)

    assert parsed.resources[0].dependency_payload_required is True
    assert parsed.resources[0].dependency_payload_projectable is False


def test_dependency_preview_rejects_overlapping_or_unsorted_payloads() -> None:
    payload = _dependency_profile_preview()
    payload["resources"][0]["structuredValueTemplate"] = {
        "command": f"{USER_COPY_PAYLOAD_ROOT_SENTINEL}/bin/server.js",
        "config": f"{USER_COPY_PAYLOAD_ROOT_SENTINEL}/bin/config.json",
    }
    payload["dependencyPayloads"] = [
        {
            "sourceLocator": "bin",
            "sourceKind": "directory",
            "contentDigest": "c" * 64,
        },
        {
            "sourceLocator": "bin/server.js",
            "sourceKind": "file",
            "contentDigest": "d" * 64,
        },
    ]
    with pytest.raises(ValidationError):
        MarketplaceUserCopyProfilePreview.model_validate(payload)

    unsorted = _dependency_profile_preview()
    unsorted["resources"][0]["structuredValueTemplate"] = {
        "command": f"{USER_COPY_PAYLOAD_ROOT_SENTINEL}/z/server.js",
        "config": f"{USER_COPY_PAYLOAD_ROOT_SENTINEL}/a/config.json",
    }
    unsorted["dependencyPayloads"] = [
        {
            "sourceLocator": "z/server.js",
            "sourceKind": "file",
            "contentDigest": "c" * 64,
        },
        {
            "sourceLocator": "a/config.json",
            "sourceKind": "file",
            "contentDigest": "d" * 64,
        },
    ]
    with pytest.raises(ValidationError):
        MarketplaceUserCopyProfilePreview.model_validate(unsorted)


def test_dependency_preview_applies_template_string_and_depth_bounds() -> None:
    oversized = _dependency_profile_preview()
    oversized["resources"][0]["structuredValueTemplate"] = {
        "command": "x" * (16 * 1024 + 1),
        "payload": f"{USER_COPY_PAYLOAD_ROOT_SENTINEL}/bin/server.js",
    }
    with pytest.raises(ValidationError):
        MarketplaceUserCopyProfilePreview.model_validate(oversized)

    too_deep = _dependency_profile_preview()
    nested: object = f"{USER_COPY_PAYLOAD_ROOT_SENTINEL}/bin/server.js"
    for _ in range(34):
        nested = [nested]
    too_deep["resources"][0]["structuredValueTemplate"] = nested
    too_deep["resources"][0]["structuredValueType"] = "array"
    with pytest.raises(ValidationError):
        MarketplaceUserCopyProfilePreview.model_validate(too_deep)


@pytest.mark.parametrize(
    "locator",
    [
        "/absolute/path",
        "../escape",
        "nested/../escape",
        "nested//file",
        r"nested\file",
        "C:relative-path",
        "C:/windows/path",
        "nested/file\nforged",
        "nested/file\rforged",
        "nested/file\x00forged",
    ],
)
def test_user_copy_profile_rejects_unsafe_source_locator(locator: str) -> None:
    payload = _profile_preview()
    payload["resources"][0]["sourceLocator"] = locator

    with pytest.raises(ValidationError):
        MarketplaceUserCopyProfilePreview.model_validate(payload)


def test_user_copy_profile_rejects_unsafe_blocked_resource_fields() -> None:
    for field, value in (
        ("resourceType", "skill\nforged"),
        ("sourceLocator", "C:relative-path"),
        ("sourceLocator", "skills/review\rforged"),
    ):
        payload = _profile_preview()
        payload["blockedResources"] = [
            {
                "resourceType": "skill",
                "sourceLocator": "skills/review",
                "reason": "unsupported-resource",
                field: value,
            }
        ]

        with pytest.raises(ValidationError):
            MarketplaceUserCopyProfilePreview.model_validate(payload)


def test_user_copy_profile_applies_500_item_total_bound() -> None:
    payload = _profile_preview()
    resources = []
    for index in range(500):
        resource = _profile_resource()
        resource["resourceId"] = f"review-{index:03d}"
        resource["sourceLocator"] = f"skills/review-{index:03d}"
        resource["relativeTarget"] = f"review-{index:03d}"
        resources.append(resource)
    payload["resources"] = resources
    payload["blockedResources"] = [
        {
            "resourceType": "skill",
            "sourceLocator": "unsupported/review",
            "reason": "unsupported-resource",
        }
    ]

    with pytest.raises(
        ValidationError,
        match="marketplace.user_copy.profile_invalid",
    ):
        MarketplaceUserCopyProfilePreview.model_validate(payload)


def test_user_copy_preflight_request_matches_exact_profile_proof() -> None:
    parsed = UserCopyPreflightRequestContract.model_validate(
        _user_copy_preflight_request()
    )
    assert parsed.expected_profile_version == 1

    mismatch = _user_copy_preflight_request()
    mismatch["expectedProfileDigest"] = "f" * 64
    with pytest.raises(
        ValidationError,
        match="marketplace.user_copy.profile_mismatch",
    ):
        UserCopyPreflightRequestContract.model_validate(mismatch)


def test_user_copy_preflight_request_rejects_lifecycle_fields() -> None:
    for legacy_field in (
        "installationId",
        "installationMode",
        "resourceScope",
        "ownedResources",
        "currentDigest",
        "drift",
        "reconcile",
        "cleanupTask",
    ):
        payload = _user_copy_preflight_request()
        payload[legacy_field] = "legacy"

        with pytest.raises(ValidationError):
            UserCopyPreflightRequestContract.model_validate(payload)


@pytest.mark.parametrize(
    "status",
    ["ready", "confirmation-required", "blocked"],
)
def test_user_copy_preflight_result_has_exact_one_shot_states(
    status: str,
) -> None:
    parsed = UserCopyPreflightResultContract.model_validate(
        _user_copy_preflight_result(status=status)
    )

    assert parsed.status == status


def test_user_copy_preflight_result_rejects_inconsistent_status() -> None:
    payload = _user_copy_preflight_result()
    payload["status"] = "confirmation-required"

    with pytest.raises(
        ValidationError,
        match="marketplace.user_copy.runtime_contract_invalid",
    ):
        UserCopyPreflightResultContract.model_validate(payload)


def test_user_copy_preflight_result_rejects_hidden_runtime_paths() -> None:
    payload = _user_copy_preflight_result()
    payload["resources"][0]["targetLocator"] = "/home/aileron/.codex/skills/review"

    with pytest.raises(ValidationError):
        UserCopyPreflightResultContract.model_validate(payload)


def test_user_copy_preflight_result_rejects_duplicate_target_identity() -> None:
    payload = _user_copy_preflight_result(status="confirmation-required")
    payload["resources"] = [_planned_resource()]

    with pytest.raises(
        ValidationError,
        match="marketplace.user_copy.runtime_contract_invalid",
    ):
        UserCopyPreflightResultContract.model_validate(payload)


def test_user_copy_conflict_rejects_integer_true_coercion() -> None:
    payload = _user_copy_preflight_result(status="confirmation-required")
    payload["conflicts"][0]["overwritable"] = 1

    with pytest.raises(ValidationError):
        UserCopyPreflightResultContract.model_validate(payload)


def test_user_copy_preflight_result_rejects_lifecycle_fields() -> None:
    for legacy_field in (
        "installationId",
        "installationMode",
        "ownedResources",
        "modifiedAction",
        "resourceTypeCounts",
        "drift",
    ):
        payload = _user_copy_preflight_result()
        payload[legacy_field] = "legacy"

        with pytest.raises(ValidationError):
            UserCopyPreflightResultContract.model_validate(payload)


def test_user_copy_apply_metadata_is_strict_and_has_unique_approvals() -> None:
    parsed = UserCopyApplyMetadataContract.model_validate(_apply_metadata())
    assert len(parsed.overwrite_approvals) == 1

    duplicate = _apply_metadata()
    duplicate["overwriteApprovals"].append(deepcopy(duplicate["overwriteApprovals"][0]))
    with pytest.raises(
        ValidationError,
        match="marketplace.user_copy.runtime_contract_invalid",
    ):
        UserCopyApplyMetadataContract.model_validate(duplicate)

    coerced = _apply_metadata()
    coerced["expectedProfileVersion"] = True
    with pytest.raises(ValidationError):
        UserCopyApplyMetadataContract.model_validate(coerced)


def test_user_copy_apply_metadata_rejects_lifecycle_fields() -> None:
    for legacy_field in (
        "installationId",
        "installationMode",
        "ownedResources",
        "payloadReferenceCounts",
        "reconcile",
        "uninstall",
    ):
        payload = _apply_metadata()
        payload[legacy_field] = "legacy"

        with pytest.raises(ValidationError):
            UserCopyApplyMetadataContract.model_validate(payload)


def test_user_copy_apply_result_contains_only_one_shot_counts() -> None:
    parsed = UserCopyApplyResultContract.model_validate(_apply_result())
    assert parsed.created_count == 1

    coerced = _apply_result()
    coerced["createdCount"] = True
    with pytest.raises(ValidationError):
        UserCopyApplyResultContract.model_validate(coerced)

    excessive = _apply_result()
    excessive.update(
        {
            "createdCount": 500,
            "mergedCount": 1,
        }
    )
    with pytest.raises(
        ValidationError,
        match="marketplace.user_copy.runtime_contract_invalid",
    ):
        UserCopyApplyResultContract.model_validate(excessive)


def test_user_copy_apply_result_rejects_lifecycle_fields() -> None:
    for legacy_field in (
        "installationId",
        "ownedResources",
        "currentDigest",
        "drift",
        "cleanupPending",
        "quarantined",
    ):
        payload = _apply_result()
        payload[legacy_field] = "legacy"

        with pytest.raises(ValidationError):
            UserCopyApplyResultContract.model_validate(payload)
