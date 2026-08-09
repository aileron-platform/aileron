from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock

from aileron_git_core import MutationResult, OperationKind, OperationMetadata
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.modules.version_control.dependencies import get_git_service
from app.modules.version_control.git_operations import GitService
from app.modules.version_control.models import (
    BranchMutationResponse,
    ChangesResponse,
    CommitListResponse,
    LfsPatternsResponse,
    LfsSnapshotConvertRequest,
    LfsSnapshotPreviewRequest,
    LfsSnapshotPreviewResponse,
    RemoteSettingsResponse,
    RepositoryInitializeRequest,
    StageRequest,
    VersionControlOperationStatus,
    VersionControlStatus,
)
from app.modules.version_control.repository import VersionControlError
from app.modules.version_control.router import router


def test_shared_wire_models_expose_only_contract_fields() -> None:
    assert set(VersionControlStatus.model_fields) == {
        "isInitialized",
        "currentBranch",
        "detachedHead",
        "headSha",
        "hasOrigin",
        "upstream",
        "ahead",
        "behind",
        "hasConflicts",
        "stagedTotal",
        "unstagedTotal",
        "untrackedTotal",
        "conflictTotal",
        "operationStatus",
    }
    assert set(VersionControlOperationStatus.model_fields) == {
        "isActive",
        "operation",
        "actorDisplayName",
        "startedAt",
        "blockingScope",
        "stale",
        "retryable",
        "progressCurrent",
        "progressTotal",
        "phase",
        "cancellable",
        "cancelRequested",
    }
    assert set(ChangesResponse.model_fields) == {
        "staged",
        "unstaged",
        "untracked",
        "conflicts",
    }
    assert set(CommitListResponse.model_fields) == {
        "items",
        "total",
        "nextCursor",
        "hasMore",
        "queryScope",
    }
    assert set(RepositoryInitializeRequest.model_fields) == {"defaultBranch"}
    assert set(StageRequest.model_fields) == {"paths", "all"}
    assert set(RemoteSettingsResponse.model_fields) == {
        "remoteName",
        "remoteUrl",
        "hasOrigin",
    }
    assert set(LfsPatternsResponse.model_fields) == {"patterns"}
    assert set(LfsSnapshotPreviewRequest.model_fields) == {"patterns"}
    assert set(LfsSnapshotPreviewResponse.model_fields) == {
        "matchedTotal",
        "totalSize",
        "pathSample",
    }
    assert set(LfsSnapshotConvertRequest.model_fields) == {"paths"}


class _ContractService:
    def __init__(self) -> None:
        self.init_default_branch: str | None = None
        self.force_unlock_result = BranchMutationResponse(
            commandId="operation.forceUnlock",
            affectedTotal=1,
        )
        self.error: VersionControlError | None = None
        self.lfs_patterns = ["*.pdf"]

    def initialize_repository(
        self, workspace_id: str, *, default_branch: str
    ) -> VersionControlStatus:
        self.init_default_branch = default_branch
        return VersionControlStatus(isInitialized=True, currentBranch=default_branch)

    def force_unlock(
        self, *, workspace_id: str, context_id: str | None = None
    ) -> BranchMutationResponse:
        if self.error is not None:
            raise self.error
        return self.force_unlock_result

    def get_remote_settings(self, workspace_id: str, context_id: str | None = None):
        return RemoteSettingsResponse(
            remoteName="origin",
            remoteUrl="https://example.com/repo.git",
            hasOrigin=True,
        )

    def set_remote_settings(self, workspace_id: str, payload, context_id=None):
        return BranchMutationResponse(commandId="remote.settings.update")

    def get_lfs_patterns(self, workspace_id: str, context_id: str | None = None):
        return LfsPatternsResponse(patterns=self.lfs_patterns)

    def update_lfs_patterns(self, workspace_id: str, **kwargs):
        return BranchMutationResponse(
            commandId="lfs.patterns.update",
            affectedTotal=len(kwargs["patterns"] or []),
        )

    def preview_lfs_snapshot(self, workspace_id: str, **kwargs):
        return LfsSnapshotPreviewResponse(
            matchedTotal=2,
            totalSize=2048,
            pathSample=["assets/a.bin", "assets/b.bin"],
        )

    def convert_lfs_snapshot(self, workspace_id: str, **kwargs):
        return BranchMutationResponse(
            commandId="lfs.snapshot.convert",
            affectedTotal=len(kwargs["paths"]),
        )

    def cancel_operation(self, workspace_id: str, **kwargs):
        return BranchMutationResponse(commandId="operation.cancel")


def _client(service: _ContractService) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_git_service] = lambda: service
    return TestClient(app)


def test_initialize_route_requires_strict_default_branch_body() -> None:
    service = _ContractService()
    client = _client(service)

    response = client.post(
        "/workspaces/ws/version-control/init",
        json={"defaultBranch": "develop"},
    )

    assert response.status_code == 200
    assert response.json()["currentBranch"] == "develop"
    assert service.init_default_branch == "develop"
    assert client.post("/workspaces/ws/version-control/init", json={}).status_code == 422
    assert (
        client.post(
            "/workspaces/ws/version-control/init",
            json={"defaultBranch": "main", "branch": "legacy"},
        ).status_code
        == 422
    )


def test_force_unlock_uses_common_mutation_result_without_host_paths() -> None:
    service = _ContractService()
    response = _client(service).post("/workspaces/ws/version-control/force-unlock")

    assert response.status_code == 200
    assert response.json() == {
        "commandId": "operation.forceUnlock",
        "headSha": None,
        "branch": None,
        "affectedTotal": 1,
        "skippedTotal": 0,
        "output": "",
    }
    assert "cleared" not in response.json()


def test_error_envelope_has_six_peer_fields_without_compatibility_payload() -> None:
    service = _ContractService()
    service.error = VersionControlError(
        "operation_locked",
        status_code=409,
        error_code="operation_locked",
        message_key="operation_locked",
        blocking_scope="common_repository",
        operation_status=OperationMetadata(
            operation_id="op-1",
            key="workspace:ws:repository",
            kind=OperationKind.WRITE,
            operation_name="branch.renameLocal",
            blocking=True,
            actor_display_name="Tester",
            started_at=datetime(2026, 8, 1, tzinfo=timezone.utc),
        ),
        stale=True,
        can_force_unlock=True,
    )

    response = _client(service).post("/workspaces/ws/version-control/force-unlock")

    assert response.status_code == 409
    assert set(response.json()["detail"]) == {
        "errorCode",
        "messageKey",
        "blockingScope",
        "operationStatus",
        "stale",
        "canForceUnlock",
    }
    assert "lockState" not in response.json()["detail"]


def test_force_unlock_service_returns_shared_mutation_result() -> None:
    service = GitService.__new__(GitService)
    service._execute_shared = MagicMock(
        return_value=MutationResult(
            command_id="operation.forceUnlock",
            head_sha="a" * 40,
            affected_total=2,
        )
    )

    response = service.force_unlock(workspace_id="ws")

    assert response == BranchMutationResponse(
        commandId="operation.forceUnlock",
        headSha="a" * 40,
        affectedTotal=2,
    )


def test_remote_lfs_and_cancel_routes_match_manager_suffixes_and_payloads() -> None:
    client = _client(_ContractService())

    remote = client.get("/workspaces/ws/version-control/remote")
    remote_update = client.put(
        "/workspaces/ws/version-control/remote",
        json={"remoteUrl": "https://example.com/updated.git"},
    )
    patterns = client.get("/workspaces/ws/version-control/lfs")
    update = client.post(
        "/workspaces/ws/version-control/lfs", json={"patterns": ["*.bin"]}
    )
    preview = client.post(
        "/workspaces/ws/version-control/lfs/preview",
        json={"patterns": ["assets/**"]},
    )
    convert = client.post(
        "/workspaces/ws/version-control/lfs/convert",
        json={"paths": ["assets/a.bin", "assets/b.bin"]},
    )
    cancel = client.post("/workspaces/ws/version-control/operation/cancel")

    assert remote.json() == {
        "remoteName": "origin",
        "remoteUrl": "https://example.com/repo.git",
        "hasOrigin": True,
    }
    assert remote_update.json()["commandId"] == "remote.settings.update"
    assert patterns.json() == {"patterns": ["*.pdf"]}
    assert update.json()["commandId"] == "lfs.patterns.update"
    assert preview.json() == {
        "matchedTotal": 2,
        "totalSize": 2048,
        "pathSample": ["assets/a.bin", "assets/b.bin"],
    }
    assert convert.json()["commandId"] == "lfs.snapshot.convert"
    assert cancel.json()["commandId"] == "operation.cancel"


def test_lfs_convert_requires_non_empty_paths_and_rejects_legacy_fields() -> None:
    client = _client(_ContractService())

    assert (
        client.post(
            "/workspaces/ws/version-control/lfs/convert", json={"paths": []}
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/workspaces/ws/version-control/lfs/preview",
            json={"patterns": ["*.bin"], "includeUntracked": True},
        ).status_code
        == 422
    )
