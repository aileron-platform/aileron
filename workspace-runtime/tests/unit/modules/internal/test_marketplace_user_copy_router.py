from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from aileron_marketplace_core import UserCopyApplyResultContract
from fastapi import HTTPException

from app.modules.internal.dependencies import _manager_command_action
from app.modules.internal.router import (
    _MAX_USER_COPY_METADATA_BYTES,
    _MAX_USER_COPY_MULTIPART_OVERHEAD_BYTES,
    apply_marketplace_user_copy,
)
from app.modules.internal.router import router as internal_router

RUNTIME_ID = "11111111-1111-4111-8111-111111111111"
PROVIDER_STATE_ROOT_ID = f"psr_{'e' * 64}"


class _TrackingUpload:
    def __init__(
        self,
        payload: bytes = b"zip",
        *,
        content_type: str = "application/zip",
    ) -> None:
        self.payload = payload
        self.content_type = content_type
        self.read_sizes: list[int] = []
        self.close_count = 0

    async def read(self, size: int) -> bytes:
        self.read_sizes.append(size)
        return self.payload[:size]

    async def close(self) -> None:
        self.close_count += 1


def _metadata() -> dict[str, object]:
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
        "overwriteApprovals": [],
    }


def _service(*, max_archive_bytes: int = 8) -> SimpleNamespace:
    return SimpleNamespace(
        marketplace_user_copy_max_archive_bytes=max_archive_bytes,
        apply_marketplace_user_copy=AsyncMock(
            return_value=UserCopyApplyResultContract(
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
        ),
    )


def test_user_copy_routes_and_manager_actions_are_exact() -> None:
    routes = {
        (route.path, method)
        for route in internal_router.routes
        if (
            isinstance(getattr(route, "path", None), str)
            and route.path.startswith("/internal/marketplace/user-copies")
        )
        for method in getattr(route, "methods", set())
    }

    assert routes == {
        ("/internal/marketplace/user-copies/preflight", "POST"),
        ("/internal/marketplace/user-copies/apply", "POST"),
    }
    base = "/api/v1/internal/marketplace/user-copies"
    assert _manager_command_action(f"{base}/preflight", method="POST") == (
        "marketplace.inspect"
    )
    assert _manager_command_action(f"{base}/apply", method="POST") == (
        "marketplace.execute"
    )
    assert _manager_command_action(f"{base}/preflight", method="GET") is None
    assert _manager_command_action(f"{base}/apply", method="GET") is None


@pytest.mark.asyncio
async def test_apply_rejects_oversized_content_length_before_reading_upload() -> None:
    service = _service()
    bundle = _TrackingUpload()
    content_length = (
        service.marketplace_user_copy_max_archive_bytes
        + _MAX_USER_COPY_METADATA_BYTES
        + _MAX_USER_COPY_MULTIPART_OVERHEAD_BYTES
        + 1
    )

    with pytest.raises(HTTPException) as exc_info:
        await apply_marketplace_user_copy(
            service,
            json.dumps(_metadata()),
            bundle,  # type: ignore[arg-type]
            content_length,
        )

    assert exc_info.value.status_code == 413
    assert exc_info.value.detail == {"code": "marketplace.user_copy.request_too_large"}
    assert bundle.read_sizes == []
    assert bundle.close_count == 1
    service.apply_marketplace_user_copy.assert_not_awaited()


@pytest.mark.asyncio
async def test_apply_rejects_oversized_metadata_bytes_before_reading_upload() -> None:
    service = _service()
    bundle = _TrackingUpload()
    oversized_metadata = "界" * (_MAX_USER_COPY_METADATA_BYTES // 3 + 1)

    with pytest.raises(HTTPException) as exc_info:
        await apply_marketplace_user_copy(
            service,
            oversized_metadata,
            bundle,  # type: ignore[arg-type]
            None,
        )

    assert exc_info.value.status_code == 413
    assert exc_info.value.detail == {"code": "marketplace.user_copy.request_too_large"}
    assert bundle.read_sizes == []
    assert bundle.close_count == 1
    service.apply_marketplace_user_copy.assert_not_awaited()


@pytest.mark.asyncio
async def test_apply_rejects_non_zip_part_before_reading_upload() -> None:
    service = _service()
    bundle = _TrackingUpload(content_type="application/octet-stream")

    with pytest.raises(HTTPException) as exc_info:
        await apply_marketplace_user_copy(
            service,
            json.dumps(_metadata()),
            bundle,  # type: ignore[arg-type]
            None,
        )

    assert exc_info.value.status_code == 422
    assert exc_info.value.detail == {
        "code": "marketplace.user_copy.archive_content_type_invalid"
    }
    assert bundle.read_sizes == []
    assert bundle.close_count == 1
    service.apply_marketplace_user_copy.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "metadata",
    [
        "{",
        json.dumps({**_metadata(), "installationId": "legacy"}),
        json.dumps({**_metadata(), "expectedProfileVersion": "1"}),
    ],
)
async def test_apply_rejects_invalid_metadata_before_reading_upload(
    metadata: str,
) -> None:
    service = _service()
    bundle = _TrackingUpload()

    with pytest.raises(HTTPException) as exc_info:
        await apply_marketplace_user_copy(
            service,
            metadata,
            bundle,  # type: ignore[arg-type]
            None,
        )

    assert exc_info.value.status_code == 422
    assert exc_info.value.detail == {
        "code": "marketplace.user_copy.runtime_contract_invalid"
    }
    assert bundle.read_sizes == []
    assert bundle.close_count == 1
    service.apply_marketplace_user_copy.assert_not_awaited()


@pytest.mark.asyncio
async def test_apply_rejects_oversized_archive_and_closes_upload() -> None:
    service = _service(max_archive_bytes=8)
    bundle = _TrackingUpload(b"x" * 9)

    with pytest.raises(HTTPException) as exc_info:
        await apply_marketplace_user_copy(
            service,
            json.dumps(_metadata()),
            bundle,  # type: ignore[arg-type]
            None,
        )

    assert exc_info.value.status_code == 413
    assert exc_info.value.detail == {"code": "marketplace.user_copy.archive_too_large"}
    assert bundle.read_sizes == [9]
    assert bundle.close_count == 1
    service.apply_marketplace_user_copy.assert_not_awaited()


@pytest.mark.asyncio
async def test_apply_passes_exact_metadata_and_archive_then_closes_upload() -> None:
    service = _service(max_archive_bytes=8)
    bundle = _TrackingUpload(b"zip")

    result = await apply_marketplace_user_copy(
        service,
        json.dumps(_metadata()),
        bundle,  # type: ignore[arg-type]
        None,
    )

    assert result.status == "completed"
    assert bundle.read_sizes == [9]
    assert bundle.close_count == 1
    service.apply_marketplace_user_copy.assert_awaited_once()
    parsed_metadata, archive = service.apply_marketplace_user_copy.await_args.args
    assert parsed_metadata.operation_id == "d" * 32
    assert archive == b"zip"
