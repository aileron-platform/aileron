"""Marketplace Runtime command client contract tests."""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest
from aileron_marketplace_core import (
    PluginPackageFormat,
    PluginReleaseIdentity,
    UserCopyProjectionApplyMetadataContract,
    UserCopyProjectionPreflightRequestContract,
    UserCopyResourceType,
    UserCopySourceKind,
    UserCopySourceProfile,
    UserCopySourceProfilePreviewContract,
    UserCopySourceResource,
)

import app.modules.marketplace.runtime_client as runtime_client_module
from app.modules.marketplace.runtime_client import (
    MarketplaceRuntimeClient,
    MarketplaceRuntimeClientError,
)


class _RecordingHttpClient:
    def __init__(
        self,
        *,
        response: httpx.Response,
        requests: list[dict[str, Any]],
    ) -> None:
        self.response = response
        self.requests = requests

    def __enter__(self) -> _RecordingHttpClient:
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        self.requests.append({"method": method, "url": url, **kwargs})
        return self.response

    def post(self, url: str, **kwargs: Any) -> httpx.Response:
        return self.request("POST", url, **kwargs)


def _client(
    response: httpx.Response,
) -> tuple[MarketplaceRuntimeClient, list[dict[str, Any]]]:
    requests: list[dict[str, Any]] = []

    def factory(*, timeout: float) -> _RecordingHttpClient:
        assert timeout == 130
        return _RecordingHttpClient(response=response, requests=requests)

    return MarketplaceRuntimeClient(client_factory=factory), requests  # type: ignore[arg-type]


def _user_copy_contracts() -> tuple[
    UserCopyProjectionPreflightRequestContract,
    UserCopyProjectionApplyMetadataContract,
]:
    profile = UserCopySourceProfile(
        package_format=PluginPackageFormat.CLAUDE_NATIVE,
        release_identity=PluginReleaseIdentity(
            catalog_plugin_id="managed/document-skills",
            revision="a" * 64,
        ),
        resources=(),
    )
    preview = UserCopySourceProfilePreviewContract.model_validate(
        {**profile.canonical_dict(), "profileDigest": profile.profile_digest}
    )
    request = UserCopyProjectionPreflightRequestContract(
        packageFormat="claude-native",
        targetClient="claude-code",
        catalogPluginId="managed/document-skills",
        releaseRevision="a" * 64,
        workspaceId="workspace-1",
        runtimeInstanceId="11111111-1111-4111-8111-111111111111",
        expectedSourceDigest="9" * 64,
        expectedProfileVersion=2,
        expectedProfileDigest=profile.profile_digest,
        sourceProfile=preview,
    )
    metadata = UserCopyProjectionApplyMetadataContract(
        operationId="d" * 32,
        packageFormat="claude-native",
        targetClient="claude-code",
        catalogPluginId="managed/document-skills",
        releaseRevision="a" * 64,
        workspaceId="workspace-1",
        runtimeInstanceId="11111111-1111-4111-8111-111111111111",
        targetClientStateRootId=f"tcsr_{'e' * 64}",
        expectedSourceDigest="9" * 64,
        expectedArchiveDigest="c" * 64,
        expectedPackageTreeDigest="d" * 64,
        expectedProfileVersion=2,
        expectedProfileDigest=profile.profile_digest,
        expectedProjectionDigest="8" * 64,
        expectedMaterializationDigest="f" * 64,
        acceptPartialCopy=False,
        expectedSkippedCount=0,
        overwriteApprovals=[],
    )
    return request, metadata


def test_runtime_client_uses_one_shot_install_path_and_action(monkeypatch) -> None:
    actions: list[str] = []

    def headers(**kwargs: str) -> dict[str, str]:
        actions.append(kwargs["action"])
        return {"X-Test-Action": kwargs["action"]}

    monkeypatch.setattr(runtime_client_module, "runtime_command_headers", headers)
    client, requests = _client(httpx.Response(200, json={"ok": True}))
    common = {
        "runtime_url": "http://runtime/",
        "workspace_id": "workspace-1",
        "runtime_instance_id": "11111111-1111-4111-8111-111111111111",
    }

    payload = {
        "operationId": "operation-1",
        "target_client": "codex",
        "packageId": "github",
        "marketplaceId": "private-marketplace",
        "remoteUrl": "git@gitlab.example:team/marketplace.git",
        "registryRef": "main",
        "workspaceId": "workspace-1",
        "runtimeInstanceId": "11111111-1111-4111-8111-111111111111",
    }
    client.descriptor(**common)
    client.install_plugin(**common, payload=payload)

    assert actions == [
        "runtime.inspect",
        "marketplace.execute",
    ]
    assert [(item["method"], item["url"]) for item in requests] == [
        ("GET", "http://runtime/api/v1/internal/health"),
        (
            "POST",
            "http://runtime/api/v1/internal/marketplace/plugins/install",
        ),
    ]
    assert requests[1]["json"] == payload


def test_runtime_client_user_copy_uses_exact_paths_and_multipart(
    monkeypatch,
) -> None:
    actions: list[str] = []

    def headers(**kwargs: str) -> dict[str, str]:
        actions.append(kwargs["action"])
        return {
            "Content-Type": "application/json",
            "X-Test-Action": kwargs["action"],
        }

    monkeypatch.setattr(runtime_client_module, "runtime_command_headers", headers)
    request, metadata = _user_copy_contracts()
    preflight_response = {
        "status": "ready",
        "packageFormat": "claude-native",
        "targetClient": "claude-code",
        "catalogPluginId": "managed/document-skills",
        "releaseRevision": "a" * 64,
        "workspaceId": "workspace-1",
        "runtimeInstanceId": "11111111-1111-4111-8111-111111111111",
        "targetClientStateRootId": f"tcsr_{'e' * 64}",
        "sourceDigest": request.expected_source_digest,
        "profileVersion": 2,
        "profileDigest": request.expected_profile_digest,
        "projectionDigest": "8" * 64,
        "materializationDigest": "f" * 64,
        "resources": [],
        "skippedResources": [],
        "conflicts": [],
        "blockingIssues": [],
    }
    preflight_client, preflight_requests = _client(
        httpx.Response(200, json=preflight_response)
    )
    apply_client, apply_requests = _client(
        httpx.Response(
            200,
            json={
                "status": "completed",
                "operationId": "d" * 32,
                "packageFormat": "claude-native",
                "targetClient": "claude-code",
                "catalogPluginId": "managed/document-skills",
                "releaseRevision": "a" * 64,
                "workspaceId": "workspace-1",
                "createdCount": 0,
                "mergedCount": 0,
                "unchangedCount": 0,
                "overwrittenCount": 0,
                "skippedCount": 0,
            },
        )
    )
    common = {
        "runtime_url": "http://runtime/",
        "workspace_id": "workspace-1",
        "runtime_instance_id": "11111111-1111-4111-8111-111111111111",
    }
    preflight_client.preflight_user_copy(**common, request=request)
    apply_client.apply_user_copy(
        **common,
        metadata=metadata,
        bundle=b"PK\x03\x04",
    )

    requests = preflight_requests + apply_requests
    assert actions == ["marketplace.inspect", "marketplace.execute"]
    assert [(item["method"], item["url"]) for item in requests] == [
        (
            "POST",
            "http://runtime/api/v1/internal/marketplace/user-copies/preflight",
        ),
        (
            "POST",
            "http://runtime/api/v1/internal/marketplace/user-copies/apply",
        ),
    ]
    multipart = requests[1]
    assert multipart["headers"] == {"X-Test-Action": "marketplace.execute"}
    assert multipart["files"]["bundle"] == (
        "package.zip",
        b"PK\x03\x04",
        "application/zip",
    )
    metadata_part = multipart["files"]["metadata"]
    assert metadata_part[0] is None
    assert metadata_part[2] == "application/json"
    assert json.loads(metadata_part[1]) == metadata.to_wire()


def test_user_copy_preflight_omits_unset_structured_resource_fields(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        runtime_client_module,
        "runtime_command_headers",
        lambda **_kwargs: {},
    )
    profile = UserCopySourceProfile(
        package_format=PluginPackageFormat.CLAUDE_NATIVE,
        release_identity=PluginReleaseIdentity(
            catalog_plugin_id="managed/claude-api",
            revision="a" * 64,
        ),
        resources=(
            UserCopySourceResource(
                resource_type=UserCopyResourceType.SKILL,
                resource_id="claude-api",
                source_kind=UserCopySourceKind.PLUGIN_COMPONENT,
                source_locator="skills/claude-api",
                source_digest="c" * 64,
            ),
        ),
    )
    preview = UserCopySourceProfilePreviewContract.model_validate(
        {**profile.canonical_dict(), "profileDigest": profile.profile_digest}
    )
    request = UserCopyProjectionPreflightRequestContract(
        packageFormat="claude-native",
        targetClient="claude-code",
        catalogPluginId="managed/claude-api",
        releaseRevision="a" * 64,
        workspaceId="workspace-1",
        runtimeInstanceId="11111111-1111-4111-8111-111111111111",
        expectedSourceDigest="9" * 64,
        expectedProfileVersion=2,
        expectedProfileDigest=profile.profile_digest,
        sourceProfile=preview,
    )
    client, requests = _client(
        httpx.Response(
            200,
            json={
                "status": "ready",
                "packageFormat": "claude-native",
                "targetClient": "claude-code",
                "catalogPluginId": "managed/claude-api",
                "releaseRevision": "a" * 64,
                "workspaceId": "workspace-1",
                "runtimeInstanceId": "11111111-1111-4111-8111-111111111111",
                "targetClientStateRootId": f"tcsr_{'e' * 64}",
                "sourceDigest": "9" * 64,
                "profileVersion": 2,
                "profileDigest": profile.profile_digest,
                "projectionDigest": "8" * 64,
                "materializationDigest": "f" * 64,
                "resources": [],
                "skippedResources": [],
                "conflicts": [],
                "blockingIssues": [],
            },
        )
    )

    client.preflight_user_copy(
        runtime_url="http://runtime",
        workspace_id="workspace-1",
        runtime_instance_id="11111111-1111-4111-8111-111111111111",
        request=request,
    )

    resource_payload = requests[0]["json"]["sourceProfile"]["resources"][0]
    assert "structuredValue" not in resource_payload
    assert "sourceJsonPointer" not in resource_payload


def test_runtime_client_preserves_canonical_runtime_error(monkeypatch) -> None:
    monkeypatch.setattr(
        runtime_client_module,
        "runtime_command_headers",
        lambda **_kwargs: {},
    )
    client, _requests = _client(
        httpx.Response(
            409,
            json={"detail": {"code": "marketplace.user_copy.target_conflict"}},
        )
    )

    with pytest.raises(MarketplaceRuntimeClientError) as exc_info:
        client.install_plugin(
            runtime_url="http://runtime",
            workspace_id="workspace-1",
            runtime_instance_id="11111111-1111-4111-8111-111111111111",
            payload={},
        )

    assert exc_info.value.code == "marketplace.user_copy.target_conflict"


def test_user_copy_preflight_maps_router_validation_to_contract_error(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        runtime_client_module,
        "runtime_command_headers",
        lambda **_kwargs: {},
    )
    client, _requests = _client(
        httpx.Response(
            422,
            json={
                "detail": [
                    {
                        "type": "missing",
                        "loc": ["body", "sourceDigest"],
                        "msg": "Field required",
                    }
                ]
            },
        )
    )

    request, _metadata = _user_copy_contracts()
    with pytest.raises(MarketplaceRuntimeClientError) as exc_info:
        client.preflight_user_copy(
            runtime_url="http://runtime",
            workspace_id="workspace-1",
            runtime_instance_id="11111111-1111-4111-8111-111111111111",
            request=request,
        )

    assert exc_info.value.code == "marketplace.user_copy.runtime_contract_invalid"


def test_runtime_client_rejects_non_object_response(monkeypatch) -> None:
    monkeypatch.setattr(
        runtime_client_module,
        "runtime_command_headers",
        lambda **_kwargs: {},
    )
    client, _requests = _client(httpx.Response(200, json=[]))

    with pytest.raises(MarketplaceRuntimeClientError) as exc_info:
        client.install_plugin(
            runtime_url="http://runtime",
            workspace_id="workspace-1",
            runtime_instance_id="11111111-1111-4111-8111-111111111111",
            payload={},
        )

    assert exc_info.value.code == "marketplace.install.runtime_contract_invalid"
