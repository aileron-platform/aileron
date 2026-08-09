from __future__ import annotations

import pytest
from aileron_marketplace_core import (
    MarketplaceUserCopyProfilePreview,
    UserCopyApplyMetadataContract,
    UserCopyApplyResultContract,
    UserCopyContractError,
    UserCopyPreflightRequestContract,
    UserCopyPreflightResultContract,
)
from pydantic import ValidationError

RUNTIME_ID = "11111111-1111-4111-8111-111111111111"
PROVIDER_STATE_ROOT_ID = f"psr_{'e' * 64}"


def _preview() -> MarketplaceUserCopyProfilePreview:
    return MarketplaceUserCopyProfilePreview.model_validate(
        {
            "profileVersion": 1,
            "provider": "codex",
            "profileDigest": "b" * 64,
            "resources": [],
            "dependencyPayloads": [],
            "blockedResources": [],
        }
    )


def _request() -> UserCopyPreflightRequestContract:
    preview = _preview()
    return UserCopyPreflightRequestContract(
        provider="codex",
        packageId="review-helper",
        revision="a" * 64,
        workspaceId="workspace-1",
        runtimeInstanceId=RUNTIME_ID,
        expectedSourceDigest=preview.source_digest,
        expectedProfileVersion=1,
        expectedProfileDigest="b" * 64,
        userCopyProfilePreview=preview,
    )


def _preflight() -> UserCopyPreflightResultContract:
    request = _request()
    return UserCopyPreflightResultContract(
        status="ready",
        provider="codex",
        packageId="review-helper",
        revision="a" * 64,
        workspaceId="workspace-1",
        runtimeInstanceId=RUNTIME_ID,
        providerStateRootId=PROVIDER_STATE_ROOT_ID,
        sourceDigest=request.expected_source_digest,
        profileVersion=1,
        profileDigest="b" * 64,
        materializationDigest="f" * 64,
        resources=[],
        conflicts=[],
        blockingIssues=[],
    )


def test_preflight_request_owns_exact_profile_source_proof() -> None:
    payload = _request().to_wire()
    payload["expectedSourceDigest"] = "0" * 64

    with pytest.raises(ValidationError):
        UserCopyPreflightRequestContract.from_wire(payload)


def test_preflight_response_verification_is_fail_closed() -> None:
    request = _request()

    with pytest.raises(UserCopyContractError):
        request.verify_response(
            _preflight(),
            provider_state_root_id=f"psr_{'0' * 64}",
        )


def test_apply_receipt_must_match_operation_and_preflight_counts() -> None:
    request = _request()
    metadata = UserCopyApplyMetadataContract(
        operationId="d" * 32,
        provider="codex",
        packageId="review-helper",
        revision="a" * 64,
        workspaceId="workspace-1",
        runtimeInstanceId=RUNTIME_ID,
        providerStateRootId=PROVIDER_STATE_ROOT_ID,
        expectedSourceDigest=request.expected_source_digest,
        expectedArchiveDigest="c" * 64,
        expectedPackageTreeDigest="d" * 64,
        expectedProfileVersion=1,
        expectedProfileDigest="b" * 64,
        expectedMaterializationDigest="f" * 64,
    )
    result = UserCopyApplyResultContract(
        status="completed",
        operationId="d" * 32,
        provider="codex",
        packageId="review-helper",
        revision="a" * 64,
        workspaceId="workspace-1",
        createdCount=1,
        mergedCount=0,
        unchangedCount=0,
        overwrittenCount=0,
    )

    with pytest.raises(UserCopyContractError):
        metadata.verify_result(result, preflight=_preflight())


def test_wire_contract_rejects_unknown_lifecycle_state() -> None:
    payload = _preflight().to_wire()
    payload["installationId"] = "legacy"

    with pytest.raises(ValidationError):
        UserCopyPreflightResultContract.from_wire(payload)
