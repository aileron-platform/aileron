"""Marketplace Runtime command client contract tests."""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest
from aileron_marketplace_core import (
    MarketplaceUserCopyProfilePreview,
    UserCopyApplyMetadataContract,
    UserCopyPreflightRequestContract,
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
    UserCopyPreflightRequestContract,
    UserCopyApplyMetadataContract,
]:
    preview = MarketplaceUserCopyProfilePreview.model_validate(
        {
            "profileVersion": 1,
            "provider": "claude-code",
            "profileDigest": "b" * 64,
            "resources": [],
            "dependencyPayloads": [],
            "blockedResources": [],
        }
    )
    request = UserCopyPreflightRequestContract(
        provider="claude-code",
        packageId="document-skills",
        revision="a" * 64,
        workspaceId="workspace-1",
        runtimeInstanceId="11111111-1111-4111-8111-111111111111",
        expectedSourceDigest=preview.source_digest,
        expectedProfileVersion=1,
        expectedProfileDigest="b" * 64,
        userCopyProfilePreview=preview,
    )
    metadata = UserCopyApplyMetadataContract(
        operationId="d" * 32,
        provider="claude-code",
        packageId="document-skills",
        revision="a" * 64,
        workspaceId="workspace-1",
        runtimeInstanceId="11111111-1111-4111-8111-111111111111",
        providerStateRootId=f"psr_{'e' * 64}",
        expectedSourceDigest=preview.source_digest,
        expectedArchiveDigest="c" * 64,
        expectedPackageTreeDigest="d" * 64,
        expectedProfileVersion=1,
        expectedProfileDigest="b" * 64,
        expectedMaterializationDigest="f" * 64,
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
        "provider": "codex",
        "packageId": "github",
        "marketplaceId": "private-marketplace",
        "remoteUrl": "git@gitlab.example:team/marketplace.git",
        "publishRef": "main",
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
        "provider": "claude-code",
        "packageId": "document-skills",
        "revision": "a" * 64,
        "workspaceId": "workspace-1",
        "runtimeInstanceId": "11111111-1111-4111-8111-111111111111",
        "providerStateRootId": f"psr_{'e' * 64}",
        "sourceDigest": request.expected_source_digest,
        "profileVersion": 1,
        "profileDigest": "b" * 64,
        "materializationDigest": "f" * 64,
        "resources": [],
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
                "provider": "claude-code",
                "packageId": "document-skills",
                "revision": "a" * 64,
                "workspaceId": "workspace-1",
                "createdCount": 0,
                "mergedCount": 0,
                "unchangedCount": 0,
                "overwrittenCount": 0,
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
    preview = MarketplaceUserCopyProfilePreview.model_validate(
        {
            "profileVersion": 1,
            "provider": "claude-code",
            "profileDigest": "b" * 64,
            "resources": [
                {
                    "resourceType": "skill",
                    "resourceId": "claude-api",
                    "sourceKind": "plugin-component",
                    "sourceLocator": "skills/claude-api",
                    "targetResource": "skills",
                    "copySemantics": "create-directory",
                    "relativeTarget": "claude-api",
                    "sourceDigest": "c" * 64,
                    "dependencyPayloadRequired": False,
                    "dependencyPayloadProjectable": True,
                }
            ],
            "dependencyPayloads": [],
            "blockedResources": [],
        }
    )
    request = UserCopyPreflightRequestContract(
        provider="claude-code",
        packageId="claude-api",
        revision="a" * 64,
        workspaceId="workspace-1",
        runtimeInstanceId="11111111-1111-4111-8111-111111111111",
        expectedSourceDigest=preview.source_digest,
        expectedProfileVersion=1,
        expectedProfileDigest="b" * 64,
        userCopyProfilePreview=preview,
    )
    client, requests = _client(
        httpx.Response(
            200,
            json={
                "status": "ready",
                "provider": "claude-code",
                "packageId": "claude-api",
                "revision": "a" * 64,
                "workspaceId": "workspace-1",
                "runtimeInstanceId": "11111111-1111-4111-8111-111111111111",
                "providerStateRootId": f"psr_{'e' * 64}",
                "sourceDigest": preview.source_digest,
                "profileVersion": 1,
                "profileDigest": "b" * 64,
                "materializationDigest": "f" * 64,
                "resources": [],
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

    resource_payload = requests[0]["json"]["userCopyProfilePreview"]["resources"][0]
    assert "structuredValueType" not in resource_payload
    assert "structuredValueTemplate" not in resource_payload


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
