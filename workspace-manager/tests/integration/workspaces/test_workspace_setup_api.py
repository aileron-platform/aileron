from __future__ import annotations

import uuid
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest
from fastapi import status

from app.services.git_service import GitBranchLookupError
from app.services.workspace_setup_service import WorkspaceSetupError


class TestWorkspaceSetupAPI:
    @pytest.mark.integration
    def test_workspace_setup_sync_error_is_localized(self, authenticated_client):
        client, _ = authenticated_client
        workspace_id = str(uuid.uuid4())

        with patch(
            "app.routers.workspace_setup.WorkspaceSetupService.run_initial_sync",
            side_effect=WorkspaceSetupError("Workspace runtime is not ready. Unable to start sync", code="WORKSPACE_SETUP_SYNC_RUNTIME_NOT_READY"),
        ):
            en_response = client.post(f"/api/v1/workspaces/{workspace_id}/setup/sync")
            assert en_response.status_code == status.HTTP_409_CONFLICT
            assert en_response.json()["detail"] == "Workspace runtime is not ready. Unable to start sync."

        client.headers.update({"Accept-Language": "zh-TW", "X-Language": "zh-TW"})
        with patch(
            "app.routers.workspace_setup.WorkspaceSetupService.run_initial_sync",
            side_effect=WorkspaceSetupError("Workspace runtime is not ready. Unable to start sync", code="WORKSPACE_SETUP_SYNC_RUNTIME_NOT_READY"),
        ):
            zh_response = client.post(f"/api/v1/workspaces/{workspace_id}/setup/sync")
            assert zh_response.status_code == status.HTTP_409_CONFLICT
            assert zh_response.json()["detail"] == "Workspace runtime 尚未就緒，無法啟動同步。"

    @pytest.mark.integration
    def test_workspace_setup_git_branches_error_is_localized(self, authenticated_client):
        client, _ = authenticated_client
        workspace_id = str(uuid.uuid4())

        mock_git_service = MagicMock()
        mock_git_service.get_remote_branches.side_effect = GitBranchLookupError(
            "Authentication failed. Verify the SSH key or use a public repository",
            code="WORKSPACE_SETUP_GIT_AUTH_FAILED",
        )
        with patch(
            "app.routers.workspace_setup.get_git_service",
            return_value=mock_git_service,
        ):
            en_response = client.get(
                f"/api/v1/workspaces/{workspace_id}/setup/git-branches",
                params={"git_url": "git@github.com:test/repo.git"},
            )
            assert en_response.status_code == status.HTTP_400_BAD_REQUEST
            assert (
                en_response.json()["detail"]
                == "Authentication failed. Verify the SSH key or use a public repository."
            )

        mock_git_service = MagicMock()
        mock_git_service.get_remote_branches.side_effect = GitBranchLookupError(
            "Branch list retrieval timeout. Please try again later",
            code="WORKSPACE_SETUP_GIT_TIMEOUT",
        )
        client.headers.update({"Accept-Language": "zh-TW", "X-Language": "zh-TW"})
        with patch(
            "app.routers.workspace_setup.get_git_service",
            return_value=mock_git_service,
        ):
            zh_response = client.get(
                f"/api/v1/workspaces/{workspace_id}/setup/git-branches",
                params={"git_url": "git@github.com:test/repo.git"},
            )
            assert zh_response.status_code == status.HTTP_400_BAD_REQUEST
            assert zh_response.json()["detail"] == "取得分支列表逾時，請稍後再試。"
