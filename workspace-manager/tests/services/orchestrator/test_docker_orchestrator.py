import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime
import docker
from app.services.orchestrator.docker_orchestrator import DockerOrchestrator
from app.services.orchestrator.models import RuntimeContext, PortMapping, VolumeMount, NetworkConfig, RuntimeStatusType

@pytest.fixture
def mock_settings():
    settings = MagicMock()
    settings.DOCKER_NETWORK = "test-network"
    return settings

@pytest.fixture
def mock_docker_client():
    with patch("docker.from_env") as mock:
        yield mock

@pytest.fixture
def docker_orchestrator(mock_settings, mock_docker_client):
    return DockerOrchestrator(mock_settings)

@pytest.fixture
def sample_workspace():
    workspace = MagicMock()
    workspace.id = "test-ws-123"
    return workspace

@pytest.fixture
def sample_context():
    return RuntimeContext(
        environment={"KEY": "VALUE"},
        volumes=[VolumeMount(source="/host/path", target="/container/path")],
        ports=[PortMapping(container_port=3002, host_port=8080)],
        network=NetworkConfig(network_name="test-net"),
        labels={"image": "test-image"}
    )

class TestDockerOrchestrator:
    def test_create_workspace_runtime_success(self, docker_orchestrator, sample_workspace, sample_context):
        # Arrange
        mock_container = MagicMock()
        mock_container.id = "container-123"
        mock_container.attrs = {"Created": "2023-01-01T00:00:00Z"}
        mock_container.ports = {"3002/tcp": [{"HostPort": "8080"}]}
        
        docker_orchestrator.client.containers.run.return_value = mock_container
        docker_orchestrator.client.containers.get.side_effect = docker.errors.NotFound("Not found")

        # Act
        info = docker_orchestrator.create_workspace_runtime(sample_workspace, sample_context)

        # Assert
        assert info.identifier == "container-123"
        assert info.status == RuntimeStatusType.RUNNING
        assert info.internal_url == "http://workspace-runtime-test-ws-123:3002"
        assert info.external_url == "http://localhost:8080"
        assert info.platform == "docker"
        assert info.extra_info["ports"]["3002/tcp"] == 8080
        
        docker_orchestrator.client.containers.run.assert_called_once()
        call_args = docker_orchestrator.client.containers.run.call_args[1]
        assert call_args["image"] == "test-image"
        assert call_args["environment"] == {"KEY": "VALUE"}
        assert call_args["network"] == "test-net"
        assert call_args["security_opt"] == ["seccomp=unconfined"]

    def test_create_workspace_runtime_removes_existing(self, docker_orchestrator, sample_workspace, sample_context):
        # Arrange
        mock_existing = MagicMock()
        mock_container = MagicMock()
        mock_container.ports = {"3002/tcp": [{"HostPort": "8080"}]}
        
        docker_orchestrator.client.containers.get.side_effect = [mock_existing, docker.errors.NotFound("Not found")] # First call finds existing, second call (reload?) or implicit logic
        # Actually logic is: try get -> remove -> run.
        # So first get returns existing.
        
        # We need to reset side_effect for run return value? No, run returns mock_container.
        docker_orchestrator.client.containers.run.return_value = mock_container
        
        # Act
        docker_orchestrator.create_workspace_runtime(sample_workspace, sample_context)

        # Assert
        mock_existing.remove.assert_called_once_with(force=True)

    def test_delete_workspace_runtime_success(self, docker_orchestrator, sample_workspace):
        # Arrange
        mock_container = MagicMock()
        docker_orchestrator.client.containers.get.return_value = mock_container

        # Act
        result = docker_orchestrator.delete_workspace_runtime(sample_workspace.id)

        # Assert
        assert result is True
        assert mock_container.remove.call_count == 3

    def test_delete_workspace_runtime_not_found(self, docker_orchestrator, sample_workspace):
        # Arrange
        docker_orchestrator.client.containers.get.side_effect = docker.errors.NotFound("Not found")

        # Act
        result = docker_orchestrator.delete_workspace_runtime(sample_workspace.id)

        # Assert
        assert result is True

    def test_get_runtime_status_running(self, docker_orchestrator, sample_workspace):
        # Arrange
        mock_container = MagicMock()
        mock_container.status = "running"
        mock_container.id = "c-123"
        docker_orchestrator.client.containers.get.return_value = mock_container

        # Act
        status = docker_orchestrator.get_runtime_status(sample_workspace.id)

        # Assert
        assert status.status == RuntimeStatusType.RUNNING
        assert status.container_id == "c-123"

    def test_get_runtime_status_not_found(self, docker_orchestrator, sample_workspace):
        # Arrange
        docker_orchestrator.client.containers.get.side_effect = docker.errors.NotFound("Not found")

        # Act
        status = docker_orchestrator.get_runtime_status(sample_workspace.id)

        # Assert
        assert status.status == RuntimeStatusType.STOPPED
