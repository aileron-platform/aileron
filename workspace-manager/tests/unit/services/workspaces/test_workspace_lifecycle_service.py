"""Unit Tests for WorkspaceLifecycleService"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import docker.errors

from app.services.workspace_lifecycle_service import WorkspaceLifecycleService


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_db_session():
    """Mock Database Session"""
    session = MagicMock()
    session.get = MagicMock(return_value=None)
    session.add = MagicMock()
    session.delete = MagicMock()
    session.commit = MagicMock()
    session.rollback = MagicMock()
    return session


@pytest.fixture
def mock_docker_client():
    """Mock Docker Client"""
    client = MagicMock()
    container = MagicMock()
    container.stop = MagicMock()
    container.remove = MagicMock()
    container.restart = MagicMock()
    client.containers.get.return_value = container
    return client, container


@pytest.fixture
def mock_settings():
    """Mock Settings"""
    settings = MagicMock()
    settings.HOST_WORKSPACES_DIR = "/tmp/workspaces"
    settings.HOST_WORKSPACE_SCRIPTS_DIR = "/tmp/workspace-scripts"
    settings.HOST_CLAUDE_DATA_DIR = "/tmp/claude-data"
    settings.MANAGER_WORKSPACES_DIR = "/mnt/workspaces"
    settings.MANAGER_WORKSPACE_SCRIPTS_DIR = "/mnt/workspace-scripts"
    settings.MANAGER_CLAUDE_DATA_DIR = "/mnt/claude-data"
    return settings


@pytest.fixture
def sample_workspace():
    """Sample workspace"""
    workspace = MagicMock()
    workspace.id = "workspace-123"
    workspace.provisioner = "docker"
    workspace.runtime_container_id = "container-abc"
    workspace.runtime_status = "running"
    workspace.browser_container_id = "browser-container-abc"
    workspace.browser_status = "running"
    workspace.canvas_container_id = None
    workspace.canvas_status = "stopped"
    workspace.setup_script = None
    return workspace


@pytest.fixture
def lifecycle_service(mock_db_session, mock_settings):
    """WorkspaceLifecycleService Instance"""
    with patch("app.services.workspace_lifecycle_service.get_settings", return_value=mock_settings):
        service = WorkspaceLifecycleService(mock_db_session)
        return service


# ============================================================================
# Delete Workspace Tests
# ============================================================================

@pytest.mark.unit
@pytest.mark.workspace
class TestDeleteWorkspace:
    """Delete Workspace Tests"""

    def test_delete_workspace_success(
        self, lifecycle_service, mock_db_session, sample_workspace, mock_docker_client
    ):
        """Test: Successfully Delete Workspace"""
        # Arrange
        mock_db_session.get.return_value = sample_workspace
        docker_client, container = mock_docker_client

        with patch("docker.from_env", return_value=docker_client):
            with patch.object(lifecycle_service, "_cleanup_workspace_volumes"):
                # Act
                lifecycle_service.delete_workspace_task("workspace-123")

                # Assert
                # Verify container is stopped and deleted
                container.stop.assert_called_once_with(timeout=10)
                container.remove.assert_called_once_with(force=True)

                # Verify workspace is deleted
                mock_db_session.delete.assert_called_once_with(sample_workspace)
                mock_db_session.commit.assert_called()

    def test_delete_workspace_not_found(
        self, lifecycle_service, mock_db_session
    ):
        """Test: Graceful Handle When Workspace Does Not Exist"""
        # Arrange
        mock_db_session.get.return_value = None

        # Act
        lifecycle_service.delete_workspace_task("nonexistent-workspace")

        # Assert
        # Should not attempt delete
        mock_db_session.delete.assert_not_called()

    def test_delete_workspace_without_container(
        self, lifecycle_service, mock_db_session, sample_workspace
    ):
        """Test: Delete Workspace Without Linked Container"""
        # Arrange
        sample_workspace.runtime_container_id = None
        mock_db_session.get.return_value = sample_workspace

        with patch.object(lifecycle_service, "_cleanup_workspace_volumes"):
            # Act
            lifecycle_service.delete_workspace_task("workspace-123")

            # Assert
            # Should still delete workspace
            mock_db_session.delete.assert_called_once_with(sample_workspace)

    def test_delete_workspace_with_docker_error(
        self, lifecycle_service, mock_db_session, sample_workspace, mock_docker_client
    ):
        """Test: Continue Execution and Complete Delete Despite Docker Error"""
        # Arrange
        mock_db_session.get.return_value = sample_workspace
        docker_client, container = mock_docker_client
        container.stop.side_effect = docker.errors.APIError("Docker API error")

        with patch("docker.from_env", return_value=docker_client):
            with patch.object(lifecycle_service, "_cleanup_workspace_volumes"):
                # Act
                lifecycle_service.delete_workspace_task("workspace-123")

                # Assert
                # Docker error does not block delete flow, should still delete workspace
                mock_db_session.delete.assert_called_once_with(sample_workspace)

    def test_delete_workspace_with_container_not_found(
        self, lifecycle_service, mock_db_session, sample_workspace, mock_docker_client
    ):
        """Test: Graceful Handle When Container Does Not Exist"""
        # Arrange
        mock_db_session.get.return_value = sample_workspace
        docker_client, _ = mock_docker_client
        docker_client.containers.get.side_effect = docker.errors.NotFound("Container not found")

        with patch("docker.from_env", return_value=docker_client):
            with patch.object(lifecycle_service, "_cleanup_workspace_volumes"):
                # Act
                lifecycle_service.delete_workspace_task("workspace-123")

                # Assert
                # Should continue execution, delete workspace
                mock_db_session.delete.assert_called_once_with(sample_workspace)

    def test_delete_workspace_failure_marks_workspace_error(
        self, lifecycle_service, mock_db_session, sample_workspace
    ):
        """Test: Rollback and Mark Workspace as Error When Delete Fails"""
        mock_db_session.get.side_effect = [sample_workspace, sample_workspace]

        with patch.object(
            lifecycle_service,
            "_cleanup_workspace_volumes",
            side_effect=RuntimeError("cleanup failed"),
        ):
            lifecycle_service.delete_workspace_task("workspace-123")

        mock_db_session.rollback.assert_called_once()
        assert sample_workspace.runtime_status == "error"
        assert mock_db_session.commit.call_count >= 1

    def test_delete_kubernetes_workspace_dispatches_to_k8s_handler(
        self, lifecycle_service, mock_db_session, sample_workspace
    ):
        sample_workspace.provisioner = "kubernetes"
        mock_db_session.get.return_value = sample_workspace

        with patch.object(lifecycle_service, "_delete_kubernetes_workspace") as mock_delete_k8s:
            lifecycle_service.delete_workspace_task("workspace-123")

        mock_delete_k8s.assert_called_once_with(sample_workspace)
        mock_db_session.delete.assert_not_called()

    def test_delete_kubernetes_workspace_uses_custom_resource_service(
        self, lifecycle_service, sample_workspace
    ):
        with patch(
            "app.services.workspace_custom_resource_service.WorkspaceCustomResourceService"
        ) as mock_service_cls:
            mock_service = mock_service_cls.return_value
            mock_service.delete_workspace_custom_resource.return_value = True

            lifecycle_service._delete_kubernetes_workspace(sample_workspace)

        mock_service.delete_workspace_custom_resource.assert_called_once_with("workspace-123")

    def test_restart_kubernetes_workspace_uses_custom_resource_service(
        self, lifecycle_service, sample_workspace
    ):
        with patch(
            "app.services.workspace_custom_resource_service.WorkspaceCustomResourceService"
        ) as mock_service_cls:
            mock_service = mock_service_cls.return_value

            lifecycle_service._restart_kubernetes_workspace(sample_workspace)

        mock_service.request_workspace_restart.assert_called_once_with("workspace-123")

    def test_restart_kubernetes_browser_uses_custom_resource_service(
        self, lifecycle_service, sample_workspace
    ):
        with patch(
            "app.services.workspace_custom_resource_service.WorkspaceCustomResourceService"
        ) as mock_service_cls:
            mock_service = mock_service_cls.return_value

            lifecycle_service._restart_kubernetes_browser(sample_workspace)

        mock_service.request_browser_restart.assert_called_once_with("workspace-123")

    def test_restart_kubernetes_canvas_uses_custom_resource_service(
        self, lifecycle_service, sample_workspace
    ):
        with patch(
            "app.services.workspace_custom_resource_service.WorkspaceCustomResourceService"
        ) as mock_service_cls:
            mock_service = mock_service_cls.return_value

            lifecycle_service._restart_kubernetes_canvas(sample_workspace)

        mock_service.request_canvas_restart.assert_called_once_with("workspace-123")


# ============================================================================
# Restart Workspace Tests
# ============================================================================

@pytest.mark.unit
@pytest.mark.workspace
class TestRestartWorkspace:
    """Restart Workspace Tests"""

    def test_restart_workspace_success(
        self, lifecycle_service, mock_db_session, sample_workspace
    ):
        """Test: Successfully Restart Workspace"""
        # Arrange
        mock_db_session.get.return_value = sample_workspace
        with patch(
            "app.services.runtime_provision_service.RuntimeProvisionService.execute_runtime_provision"
        ) as mock_execute_runtime_provision:
            # Act
            lifecycle_service.restart_workspace_task("workspace-123")

        # Assert
        mock_execute_runtime_provision.assert_called_once_with("workspace-123")
        mock_db_session.commit.assert_called()

    def test_restart_workspace_uses_runtime_provision_instead_of_recreate_container(
        self, lifecycle_service, mock_db_session, sample_workspace
    ):
        mock_db_session.get.return_value = sample_workspace

        with patch.object(lifecycle_service, "_recreate_container") as mock_recreate_container:
            with patch(
                "app.services.runtime_provision_service.RuntimeProvisionService.execute_runtime_provision"
            ) as mock_execute_runtime_provision:
                lifecycle_service.restart_workspace_task("workspace-123")

        mock_execute_runtime_provision.assert_called_once_with("workspace-123")
        mock_recreate_container.assert_not_called()

    def test_restart_workspace_not_found(
        self, lifecycle_service, mock_db_session
    ):
        """Test: Graceful Handle When Workspace Does Not Exist"""
        # Arrange
        mock_db_session.get.return_value = None

        # Act
        lifecycle_service.restart_workspace_task("nonexistent-workspace")

        # Assert
        # Should not attempt any operation
        mock_db_session.commit.assert_not_called()

    def test_restart_kubernetes_workspace_dispatches_to_k8s_handler(
        self, lifecycle_service, mock_db_session, sample_workspace
    ):
        sample_workspace.provisioner = "kubernetes"
        mock_db_session.get.return_value = sample_workspace

        with patch.object(lifecycle_service, "_restart_kubernetes_workspace") as mock_restart_k8s:
            lifecycle_service.restart_workspace_task("workspace-123")

        mock_restart_k8s.assert_called_once_with(sample_workspace)

    def test_restart_kubernetes_browser_dispatches_to_k8s_handler(
        self, lifecycle_service, mock_db_session, sample_workspace
    ):
        sample_workspace.provisioner = "kubernetes"
        mock_db_session.get.return_value = sample_workspace

        with patch.object(lifecycle_service, "_restart_kubernetes_browser") as mock_restart_k8s:
            lifecycle_service.restart_browser_task("workspace-123")

        mock_restart_k8s.assert_called_once_with(sample_workspace)

    def test_restart_kubernetes_canvas_dispatches_to_k8s_handler(
        self, lifecycle_service, mock_db_session, sample_workspace
    ):
        sample_workspace.provisioner = "kubernetes"
        mock_db_session.get.return_value = sample_workspace

        with patch.object(lifecycle_service, "_restart_kubernetes_canvas") as mock_restart_k8s:
            lifecycle_service.restart_canvas_task("workspace-123")

        mock_restart_k8s.assert_called_once_with(sample_workspace)

    def test_restart_workspace_without_container(
        self, lifecycle_service, mock_db_session, sample_workspace
    ):
        """Test: Restart Workspace Without Linked Container"""
        # Arrange
        sample_workspace.runtime_container_id = None
        mock_db_session.get.return_value = sample_workspace

        # Act
        lifecycle_service.restart_workspace_task("workspace-123")

        # Assert
        # Should not update status to running (because no container exists)
        assert sample_workspace.runtime_status == "running"  # Initial value

    def test_restart_workspace_with_docker_error(
        self, lifecycle_service, mock_db_session, sample_workspace
    ):
        """Test: Error Handle When Docker Error Occurs"""
        # Arrange
        mock_db_session.get.side_effect = [sample_workspace, sample_workspace]
        with patch(
            "app.services.runtime_provision_service.RuntimeProvisionService.execute_runtime_provision",
            side_effect=docker.errors.APIError("Docker API error"),
        ):
            # Act
            lifecycle_service.restart_workspace_task("workspace-123")

        # Assert
        mock_db_session.rollback.assert_called()
        assert sample_workspace.runtime_status == "error"

    def test_restart_workspace_with_container_not_found(
        self, lifecycle_service, mock_db_session, sample_workspace
    ):
        """Test: Error Handle When Container Does Not Exist"""
        # Arrange
        mock_db_session.get.side_effect = [sample_workspace, sample_workspace]
        with patch(
            "app.services.runtime_provision_service.RuntimeProvisionService.execute_runtime_provision",
            side_effect=ValueError("Container container-abc does not exist"),
        ):
            # Act
            lifecycle_service.restart_workspace_task("workspace-123")

        # Assert
        mock_db_session.rollback.assert_called()
        assert sample_workspace.runtime_status == "error"


@pytest.mark.unit
@pytest.mark.workspace
class TestRestartBrowser:
    """Restart Browser Tests"""

    def test_restart_browser_success(
        self, lifecycle_service, mock_db_session, sample_workspace
    ):
        mock_db_session.get.return_value = sample_workspace

        with patch.object(lifecycle_service, "_recreate_container", return_value="browser-new"):
            lifecycle_service.restart_browser_task("workspace-123")

        assert sample_workspace.browser_container_id == "browser-new"
        assert sample_workspace.browser_status == "running"
        mock_db_session.commit.assert_called()

    def test_restart_browser_without_container(
        self, lifecycle_service, mock_db_session, sample_workspace
    ):
        sample_workspace.browser_container_id = None
        mock_db_session.get.return_value = sample_workspace

        lifecycle_service.restart_browser_task("workspace-123")

        assert sample_workspace.browser_status == "running"
        mock_db_session.commit.assert_called()

    def test_restart_browser_failure_sets_error(
        self, lifecycle_service, mock_db_session, sample_workspace
    ):
        mock_db_session.get.side_effect = [sample_workspace, sample_workspace]

        with patch.object(
            lifecycle_service,
            "_recreate_container",
            side_effect=docker.errors.APIError("Docker API error"),
        ):
            lifecycle_service.restart_browser_task("workspace-123")

        mock_db_session.rollback.assert_called()
        assert sample_workspace.browser_status == "error"


# ============================================================================
# Container Operations Tests
# ============================================================================

@pytest.mark.unit
@pytest.mark.workspace
class TestContainerOperations:
    """Container Operations Tests"""

    def test_stop_and_remove_container_success(
        self, lifecycle_service, mock_docker_client
    ):
        """Test: Successfully Stop and Remove Container"""
        # Arrange
        docker_client, container = mock_docker_client

        with patch("docker.from_env", return_value=docker_client):
            # Act
            lifecycle_service._stop_and_remove_container("container-123", "workspace-123")

            # Assert
            container.stop.assert_called_once_with(timeout=10)
            container.remove.assert_called_once_with(force=True)

    def test_stop_and_remove_container_not_found(
        self, lifecycle_service, mock_docker_client
    ):
        """Test: Graceful Handle When Container Does Not Exist"""
        # Arrange
        docker_client, _ = mock_docker_client
        docker_client.containers.get.side_effect = docker.errors.NotFound("Container not found")

        with patch("docker.from_env", return_value=docker_client):
            # Act & Assert (should not raise exception)
            lifecycle_service._stop_and_remove_container("container-123", "workspace-123")

    def test_stop_and_remove_container_api_error(
        self, lifecycle_service, mock_docker_client
    ):
        """Test: Graceful Handle When Docker API Error Occurs"""
        # Arrange
        docker_client, container = mock_docker_client
        container.stop.side_effect = docker.errors.APIError("API error")

        with patch("docker.from_env", return_value=docker_client):
            # Act & Assert (should not raise exception)
            lifecycle_service._stop_and_remove_container("container-123", "workspace-123")

    def test_recreate_container_success(
        self, lifecycle_service, mock_docker_client
    ):
        """Test: Successfully Recreate Container"""
        docker_client, container = mock_docker_client
        container.name = "workspace-runtime"
        container.attrs = {
            "Config": {
                "Image": "workspace-image:latest",
                "Cmd": ["/start_services.sh"],
                "Env": ["NODE_ENV=development"],
                "WorkingDir": "/workspace-runtime",
                "Labels": {"service": "workspace"},
                "Volumes": {"/workspace": {}},
                "ExposedPorts": {"3002/tcp": {}},
            },
            "HostConfig": {
                "PortBindings": {"3002/tcp": [{"HostPort": "3200"}]},
                "Binds": ["/tmp/workspaces:/workspace"],
                "CapAdd": None,
                "LogConfig": {"Type": "json-file", "Config": {}},
                "RestartPolicy": {"Name": "always"},
                "ShmSize": 1024,
            },
            "NetworkSettings": {"Networks": {"bridge": {}}},
        }
        docker_client.api.create_host_config.return_value = {"host_config": True}
        docker_client.api.create_endpoint_config.return_value = {"endpoint": True}
        docker_client.api.create_networking_config.return_value = {"network": True}
        docker_client.api.create_container.return_value = {"Id": "container-new"}

        with patch("docker.from_env", return_value=docker_client):
            result = lifecycle_service._recreate_container("container-123", "workspace-123")

        assert result == "container-new"
        container.stop.assert_called_once_with(timeout=10)
        container.remove.assert_called_once_with(force=True)
        docker_client.api.start.assert_called_once_with("container-new")

    def test_recreate_container_not_found(
        self, lifecycle_service, mock_docker_client
    ):
        """Test: Raise Error When Container Does Not Exist"""
        docker_client, _ = mock_docker_client
        docker_client.containers.get.side_effect = docker.errors.NotFound("Container not found")

        with patch("docker.from_env", return_value=docker_client):
            with pytest.raises(ValueError, match="Container .* does not exist"):
                lifecycle_service._recreate_container("container-123", "workspace-123")

    def test_recreate_container_api_error(
        self, lifecycle_service, mock_docker_client
    ):
        """Test: Raise Exception When Docker API Error Occurs"""
        docker_client, container = mock_docker_client
        container.name = "workspace-runtime"
        container.attrs = {
            "Config": {"Image": "workspace-image:latest", "ExposedPorts": {}},
            "HostConfig": {"LogConfig": {"Type": "json-file", "Config": {}}, "RestartPolicy": {}},
            "NetworkSettings": {"Networks": {}},
        }
        container.stop.side_effect = docker.errors.APIError("API error")

        with patch("docker.from_env", return_value=docker_client):
            with pytest.raises(docker.errors.APIError):
                lifecycle_service._recreate_container("container-123", "workspace-123")


# ============================================================================
# Volume Cleanup Tests
# ============================================================================

@pytest.mark.unit
@pytest.mark.workspace
class TestVolumeCleanup:
    """Volume Cleanup Tests"""

    def test_cleanup_workspace_volumes_success(
        self, lifecycle_service, mock_settings
    ):
        """Test: Successfully Clean Workspace Volumes"""
        # Arrange
        workspace_id = "workspace-123-456"

        with patch("shutil.rmtree") as mock_rmtree:
            with patch("pathlib.Path.exists", return_value=True):
                # Act
                lifecycle_service._cleanup_workspace_volumes(workspace_id)

                # Assert
                removed_paths = [call.args[0] for call in mock_rmtree.call_args_list]
                assert removed_paths == [
                    Path("/mnt/workspaces/workspace_123_456"),
                    Path("/mnt/workspace-scripts/workspace_123_456"),
                    Path("/mnt/claude-data/workspace_123_456"),
                ]

    def test_cleanup_workspace_volumes_directory_not_exists(
        self, lifecycle_service
    ):
        """Test: Graceful Handle When Directory Does Not Exist"""
        # Arrange
        workspace_id = "workspace-123"

        with patch("shutil.rmtree") as mock_rmtree:
            with patch("pathlib.Path.exists", return_value=False):
                # Act
                lifecycle_service._cleanup_workspace_volumes(workspace_id)

                # Assert
                # Should not attempt to delete non-existent directory
                mock_rmtree.assert_not_called()

    def test_cleanup_workspace_volumes_with_error(
        self, lifecycle_service
    ):
        """Test: Graceful Handle When Deletion Fails"""
        # Arrange
        workspace_id = "workspace-123"

        with patch("shutil.rmtree", side_effect=PermissionError("Permission denied")):
            with patch("pathlib.Path.exists", return_value=True):
                # Act & Assert (should not raise exception)
                lifecycle_service._cleanup_workspace_volumes(workspace_id)


# ============================================================================
# Event Logging Tests
# ============================================================================

@pytest.mark.unit
@pytest.mark.workspace
class TestEventLogging:
    """Event Logging Tests"""

    def test_log_event_success(
        self, lifecycle_service, mock_db_session
    ):
        """Test: Successfully Record Event Log"""
        # Act
        lifecycle_service._log_event(
            workspace_id="workspace-123",
            stage="deleting",
            message="Start Deleting",
            metadata={"key": "value"}
        )

        # Assert
        mock_db_session.add.assert_called_once()
        mock_db_session.commit.assert_called_once()

    def test_log_event_without_metadata(
        self, lifecycle_service, mock_db_session
    ):
        """Test: Event Log Without Metadata"""
        # Act
        lifecycle_service._log_event(
            workspace_id="workspace-123",
            stage="deleting",
            message="Start Deleting"
        )

        # Assert
        mock_db_session.add.assert_called_once()

    def test_log_event_with_database_error(
        self, lifecycle_service, mock_db_session
    ):
        """Test: Graceful Handle When Database Error Occurs"""
        # Arrange
        mock_db_session.add.side_effect = Exception("Database error")

        # Act & Assert (should not raise exception)
        lifecycle_service._log_event(
            workspace_id="workspace-123",
            stage="error",
            message="Error"
        )

        # Should rollback
        mock_db_session.rollback.assert_called()


# ============================================================================
# Background Task Entry Points Tests
# ============================================================================

@pytest.mark.unit
@pytest.mark.workspace
class TestBackgroundTaskEntryPoints:
    """Background Task Entry Points Tests"""

    def test_run_delete_workspace_task(self, sample_workspace):
        """Test: Delete Workspace Background Task Entry Point"""
        # Arrange
        mock_db = MagicMock()
        mock_db.get.return_value = sample_workspace

        with patch("app.db.database.SessionLocal", return_value=mock_db):
            with patch.object(WorkspaceLifecycleService, "delete_workspace_task") as mock_delete:
                # Import and run
                from app.services.workspace_lifecycle_service import run_delete_workspace_task

                # Act
                run_delete_workspace_task("workspace-123")

                # Assert
                mock_delete.assert_called_once_with("workspace-123")
                mock_db.close.assert_called_once()

    def test_run_restart_workspace_task(self, sample_workspace):
        """Test: Restart Workspace Background Task Entry Point"""
        # Arrange
        mock_db = MagicMock()
        mock_db.get.return_value = sample_workspace

        with patch("app.db.database.SessionLocal", return_value=mock_db):
            with patch.object(WorkspaceLifecycleService, "restart_workspace_task") as mock_restart:
                # Import and run
                from app.services.workspace_lifecycle_service import run_restart_workspace_task

                # Act
                run_restart_workspace_task("workspace-123")

                # Assert
                mock_restart.assert_called_once_with("workspace-123")
                mock_db.close.assert_called_once()

    def test_run_restart_browser_task(self, sample_workspace):
        """Test: Restart Browser Background Task Entry Point"""
        mock_db = MagicMock()
        mock_db.get.return_value = sample_workspace

        with patch("app.db.database.SessionLocal", return_value=mock_db):
            with patch.object(WorkspaceLifecycleService, "restart_browser_task") as mock_restart:
                from app.services.workspace_lifecycle_service import run_restart_browser_task

                run_restart_browser_task("workspace-123")

                mock_restart.assert_called_once_with("workspace-123")
                mock_db.close.assert_called_once()
