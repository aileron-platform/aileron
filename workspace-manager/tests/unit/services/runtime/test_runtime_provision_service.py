"""RuntimeProvisionService 單元測試"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
import socket
from unittest.mock import MagicMock, Mock, patch
from uuid import uuid4

import pytest

from app.services.runtime_provision_service import RuntimeProvisionService
from app.services.orchestrator import (
    RuntimeContext,
    RuntimeInfo,
    RuntimeStatusType,
    VolumeMount,
    PortMapping,
    NetworkConfig
)
from app.db import models as db_models

# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_db_session():
    """Mock 資料庫 Session"""
    session = MagicMock()
    session.get = MagicMock(return_value=None)
    session.add = MagicMock()
    session.commit = MagicMock()
    session.rollback = MagicMock()
    session.flush = MagicMock()
    session.execute = MagicMock()
    session.scalar = MagicMock(return_value=None)
    return session

@pytest.fixture
def mock_settings():
    """Mock Settings"""
    settings = MagicMock()
    settings.RUNTIME_PROVISIONER = "docker"
    settings.RUNTIME_SCRIPT_ROOT = "/tmp/workspace-scripts"
    settings.HOST_WORKSPACES_DIR = "/tmp/workspaces"
    settings.HOST_WORKSPACE_SCRIPTS_DIR = "/tmp/workspace-scripts-host"
    settings.HOST_CLAUDE_DATA_DIR = "/tmp/claude-data"
    settings.HOST_KNOWLEDGE_BASES_DIR = "/tmp/knowledge-bases"
    settings.BROWSER_WEBRTC_RESERVED_UDP_RANGES = ["50000-52321"]
    settings.MANAGER_WORKSPACES_DIR = "/mnt/workspaces"
    settings.MANAGER_WORKSPACE_SCRIPTS_DIR = "/mnt/workspace-scripts"
    settings.MANAGER_CLAUDE_DATA_DIR = "/mnt/claude-data"
    settings.MANAGER_KNOWLEDGE_BASES_DIR = "/mnt/knowledge-bases"
    settings.DOCKER_NETWORK = "workspace-network"
    settings.ENV = "testing"
    settings.DATABASE_URL = "postgresql://test:test@localhost/test"
    settings.REDIS_URL = "redis://localhost:6379/0"
    settings.PORT = 8000
    settings.INTERNAL_API_TOKEN = "test-token"
    settings.KEYCLOAK_SERVER_URL = "http://localhost:8080"
    settings.KEYCLOAK_REALM = "aileron"
    settings.KEYCLOAK_CLIENT_ID = "aileron-web"
    return settings

@pytest.fixture
def mock_template_engine():
    """Mock ScriptTemplateEngine"""
    engine = MagicMock()
    engine.render_to_file.return_value = Path("/tmp/startup.sh")
    return engine

@pytest.fixture
def sample_workspace():
    """範例工作區"""
    workspace = Mock(spec=db_models.Workspace)
    workspace.id = "workspace-123"
    workspace.owner_id = "user-123"
    workspace.name = "Test Workspace"
    workspace.git_url = "https://github.com/test/repo.git"
    workspace.branch = "main"
    workspace.runtime = "python:3.9"
    workspace.runtime_internal_port = 3002
    workspace.runtime_external_port = 8080
    workspace.canvas_internal_port = 3003
    workspace.canvas_external_port = 8081
    workspace.terminal_external_port = 8082
    workspace.runtime_status = "pending"
    workspace.env_vars = [
        {"key": "NODE_ENV", "value": "production"},
    ]
    workspace.port_mappings = [
        {"container_port": 8000, "host_port": 9000, "protocol": "tcp"}
    ]
    workspace.setup_script = "#!/bin/bash\necho 'Setup complete'"
    workspace.knowledge_base_attachments = []
    return workspace

@pytest.fixture
def provision_service(mock_db_session, mock_settings, mock_template_engine):
    """RuntimeProvisionService 實例"""
    with patch("app.services.runtime_provision_service.get_settings", return_value=mock_settings):
        with patch("app.services.runtime_provision_service.ScriptTemplateEngine", return_value=mock_template_engine):
            service = RuntimeProvisionService(mock_db_session)
            service.template_engine = mock_template_engine
            return service

@pytest.fixture
def mock_orchestrator():
    """Mock ContainerOrchestrator"""
    orchestrator = MagicMock()
    return orchestrator

# ============================================================================
# Tests
# ============================================================================

@pytest.mark.unit
class TestRuntimeProvisionService:
    
    def test_execute_runtime_provision_success(
        self, provision_service, mock_db_session, sample_workspace, mock_orchestrator
    ):
        """測試：成功執行佈建流程"""
        # Arrange
        mock_db_session.get.return_value = sample_workspace
        
        # Mock OrchestratorFactory
        with patch("app.services.runtime_provision_service.OrchestratorFactory") as mock_factory:
            mock_factory.get_orchestrator.return_value = mock_orchestrator
            
            # Mock create_workspace_runtime return value
            mock_orchestrator.create_workspace_runtime.return_value = RuntimeInfo(
                identifier="container-123",
                workspace_id=sample_workspace.id,
                status=RuntimeStatusType.RUNNING,
                internal_url="http://internal:3002",
                external_url="http://localhost:8080",
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
                platform="docker",
                extra_info={
                    "container_name": "ws-123",
                    "ports": {
                        "3002/tcp": 8080,
                        "3003/tcp": 8081,
                        "3004/tcp": 8082
                    }
                }
            )
            
            # Act
            provision_service.execute_runtime_provision("workspace-123")
            
            # Assert
            # 1. Job created
            assert mock_db_session.add.call_count >= 2 # Job + Logs
            
            # 2. Orchestrator called
            mock_orchestrator.create_workspace_runtime.assert_called_once()
            call_args = mock_orchestrator.create_workspace_runtime.call_args
            assert call_args[0][0] == sample_workspace
            assert isinstance(call_args[0][1], RuntimeContext)
            
            # 3. Workspace updated
            assert sample_workspace.runtime_id == "container-123"
            assert sample_workspace.runtime_status == "running"
            assert sample_workspace.runtime_external_url == "http://localhost:8080"
            assert sample_workspace.terminal_external_url == "http://localhost:8082"

    def test_build_runtime_context(self, provision_service, sample_workspace, mock_template_engine):
        """測試：構建 RuntimeContext"""
        # Arrange
        with patch("app.services.container_image_service.get_container_image_service") as mock_image_service_getter:
            mock_image_service = MagicMock()
            mock_image_service.get_docker_image_name.return_value = "workspace-image:latest"
            mock_image_service_getter.return_value = mock_image_service
            
            # Act
            context = provision_service._build_runtime_context(sample_workspace)
            
            # Assert
            assert isinstance(context, RuntimeContext)
            assert context.labels["image"] == "workspace-image:latest"
            
            # Environment
            assert context.environment["WORKSPACE_ID"] == "workspace-123"
            assert context.environment["NODE_ENV"] == "production"
            
            # Volumes
            assert len(context.volumes) >= 3 # workspace, scripts, docker.sock
            assert any(v.target == "/workspace" for v in context.volumes)
            
            # Ports
            # 目前 runtime context 只包含主服務、終端機與自訂映射
            assert len(context.ports) == 3
            
            # Template rendered
            mock_template_engine.render_to_file.assert_called_once()

    def test_build_volumes_uses_workspace_scripts_and_claude_roots(
        self, provision_service, sample_workspace, mock_settings, tmp_path: Path
    ):
        mock_settings.HOST_WORKSPACES_DIR = str(tmp_path / "workspaces")
        mock_settings.HOST_WORKSPACE_SCRIPTS_DIR = str(tmp_path / "workspace-scripts")
        mock_settings.HOST_CLAUDE_DATA_DIR = str(tmp_path / "claude-data")
        mock_settings.HOST_KNOWLEDGE_BASES_DIR = str(tmp_path / "knowledge-bases")
        mock_settings.MANAGER_WORKSPACES_DIR = str(tmp_path / "mounted-workspaces")
        mock_settings.MANAGER_WORKSPACE_SCRIPTS_DIR = str(tmp_path / "mounted-workspace-scripts")
        mock_settings.MANAGER_CLAUDE_DATA_DIR = str(tmp_path / "mounted-claude-data")
        mock_settings.MANAGER_KNOWLEDGE_BASES_DIR = str(tmp_path / "mounted-knowledge-bases")

        volumes = provision_service._build_volumes(sample_workspace)

        sources = {volume.target: volume.source for volume in volumes}
        assert sources["/workspace"] == str(tmp_path / "workspaces" / "workspace_123")
        assert sources["/scripts"] == str(tmp_path / "workspace-scripts" / "workspace_123")
        assert sources["/home/developer/.claude"] == str(tmp_path / "claude-data" / "workspace_123")
        assert (tmp_path / "mounted-workspace-scripts" / "workspace_123" / "custom-setup.sh").is_file()

    def test_build_volumes_adds_knowledge_base_mounts(
        self, provision_service, sample_workspace, mock_settings, tmp_path: Path
    ):
        mock_settings.HOST_WORKSPACES_DIR = str(tmp_path / "workspaces")
        mock_settings.HOST_WORKSPACE_SCRIPTS_DIR = str(tmp_path / "workspace-scripts")
        mock_settings.HOST_CLAUDE_DATA_DIR = str(tmp_path / "claude-data")
        mock_settings.HOST_KNOWLEDGE_BASES_DIR = str(tmp_path / "knowledge-bases")
        mock_settings.MANAGER_WORKSPACES_DIR = str(tmp_path / "mounted-workspaces")
        mock_settings.MANAGER_WORKSPACE_SCRIPTS_DIR = str(tmp_path / "mounted-workspace-scripts")
        mock_settings.MANAGER_CLAUDE_DATA_DIR = str(tmp_path / "mounted-claude-data")
        mock_settings.MANAGER_KNOWLEDGE_BASES_DIR = str(tmp_path / "mounted-knowledge-bases")
        sample_workspace.setup_script = None
        sample_workspace.knowledge_base_attachments = [
            Mock(
                kb_id="kb-1",
                mount_alias="docs",
                mode="rw",
                knowledge_base=Mock(id="kb-1"),
            ),
            Mock(
                kb_id="kb-2",
                mount_alias="readonly-docs",
                mode="ro",
                knowledge_base=Mock(id="kb-2"),
            ),
        ]

        volumes = provision_service._build_volumes(sample_workspace)

        kb_mounts = {volume.target: volume for volume in volumes if volume.target.startswith("/knowledge/")}
        assert kb_mounts["/knowledge/docs"].source == str(tmp_path / "knowledge-bases" / "kb-1")
        assert kb_mounts["/knowledge/docs"].read_only is False
        assert kb_mounts["/knowledge/readonly-docs"].source == str(tmp_path / "knowledge-bases" / "kb-2")
        assert kb_mounts["/knowledge/readonly-docs"].read_only is True
        assert (tmp_path / "mounted-knowledge-bases" / "kb-1").is_dir()
        assert (tmp_path / "mounted-knowledge-bases" / "kb-2").is_dir()

    def test_find_available_port_uses_requested_protocol(self, provision_service, monkeypatch: pytest.MonkeyPatch):
        socket_types: list[int] = []
        ports_tried: list[int] = []

        class FakeSocket:
            def __init__(self, family: int, socket_type: int) -> None:
                socket_types.append(socket_type)

            def __enter__(self) -> "FakeSocket":
                return self

            def __exit__(self, exc_type, exc, tb) -> bool:
                return False

            def bind(self, address: tuple[str, int]) -> None:
                ports_tried.append(address[1])
                if address[1] == 41001:
                    raise OSError("port unavailable")

        candidate_ports = iter([41001, 41002])
        monkeypatch.setattr("app.services.runtime_provision_service.random.randint", lambda _a, _b: next(candidate_ports))
        monkeypatch.setattr("app.services.runtime_provision_service.socket.socket", FakeSocket)

        port = provision_service._find_available_port(protocol="udp")

        assert port == 41002
        assert socket_types == [socket.SOCK_DGRAM, socket.SOCK_DGRAM]
        assert ports_tried == [41001, 41002]

    def test_build_browser_runtime_context_requests_udp_port(
        self, provision_service, sample_workspace
    ):
        sample_workspace.runtime_external_port = 3002
        sample_workspace.canvas_external_port = 3003
        sample_workspace.terminal_external_port = 3004
        sample_workspace.browser_webrtc_external_port = 52330
        sample_workspace.browser_cdp_external_port = 9223

        with patch("app.services.container_image_service.get_container_image_service") as mock_image_service_getter:
            mock_image_service = MagicMock()
            mock_image_service.get_browser_image_name.return_value = "workspace-browser:latest"
            mock_image_service_getter.return_value = mock_image_service
            context = provision_service._build_browser_runtime_context(sample_workspace)

        assert context.environment["NEKO_WEBRTC_UDPMUX"] == "52330"
        assert context.environment["NEKO_WEBRTC_NAT1TO1"] == "127.0.0.1"
        assert any(port.protocol == "udp" and port.host_port == 52330 for port in context.ports)
        assert any(port.protocol == "udp" and port.container_port == 52330 for port in context.ports)

    def test_allocate_ports_uses_shared_browser_webrtc_port_for_tcp_and_udp(
        self, provision_service, sample_workspace
    ) -> None:
        sample_workspace.runtime_external_port = None
        sample_workspace.canvas_external_port = None
        sample_workspace.terminal_external_port = None
        sample_workspace.browser_webrtc_external_port = None
        sample_workspace.browser_cdp_external_port = None
        sample_workspace.canvas_external_port = None
        sample_workspace.canvas_api_external_port = None

        ports = iter([31002, 31003, 31004, 52330, 39223, 33003, 33013])
        with patch.object(provision_service, "_find_available_port", side_effect=lambda *args, **kwargs: next(ports)):
            with patch.object(
                provision_service,
                "_find_available_browser_webrtc_port",
                return_value=52330,
            ) as mock_browser_port:
                provision_service._allocate_ports_if_needed(sample_workspace)

        mock_browser_port.assert_called_once()
        assert sample_workspace.browser_webrtc_external_port == 52330
        assert sample_workspace.browser_webrtc_external_url == "http://localhost:52330"

    def test_find_available_browser_webrtc_port_checks_tcp_udp_and_reserved_ranges(
        self, provision_service, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        candidate_ports = iter([50010, 52330, 52331])
        checks: list[tuple[int, str]] = []

        monkeypatch.setattr(
            "app.services.runtime_provision_service.random.randint",
            lambda _a, _b: next(candidate_ports),
        )

        def fake_is_port_available(port: int, protocol: str) -> bool:
            checks.append((port, protocol))
            return not (port == 52330 and protocol == "udp")

        monkeypatch.setattr(provision_service, "_is_port_available", fake_is_port_available)

        port = provision_service._find_available_browser_webrtc_port(exclude={52329})

        assert port == 52331
        assert (50010, "tcp") not in checks
        assert (52330, "tcp") in checks
        assert (52330, "udp") in checks
        assert (52331, "tcp") in checks
        assert (52331, "udp") in checks

    def test_reserved_browser_webrtc_udp_ranges_ignore_invalid_entries(
        self, provision_service
    ) -> None:
        provision_service.settings.BROWSER_WEBRTC_RESERVED_UDP_RANGES = [
            "50000-50010",
            "bad",
            "60000-59000",
            "abc-def",
        ]

        ranges = provision_service._get_reserved_browser_webrtc_udp_ranges()

        assert ranges == ((50000, 50010),)

    def test_handle_failure(self, provision_service, mock_db_session, sample_workspace):
        """測試：處理失敗"""
        # Arrange
        job = Mock(spec=db_models.WorkspaceRuntimeJob)
        error = Exception("Test Error")
        
        # Act
        provision_service._handle_failure(sample_workspace, job, error)
        
        # Assert
        assert job.status == "failed"
        assert job.error_message == "Test Error"
        assert sample_workspace.runtime_status == "error"

    def test_update_workspace_runtime(self, provision_service, sample_workspace, mock_db_session):
        """測試：更新工作區信息"""
        # Arrange
        mock_db_session.get.return_value = sample_workspace
        sample_workspace.knowledge_base_attachments = [
            Mock(
                kb_id="kb-1",
                mount_alias="docs",
                mode="rw",
                knowledge_base=Mock(id="kb-1", tombstoned_at=None),
            )
        ]
        info = RuntimeInfo(
            identifier="c-123",
            workspace_id="ws-123",
            status=RuntimeStatusType.RUNNING,
            internal_url="http://internal:3002",
            external_url="http://localhost:8080",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            platform="docker",
            extra_info={
                "container_name": "ws-123",
                "ports": {
                    "3002/tcp": 8080,
                    "3003/tcp": 8081,
                    "3004/tcp": 8082
                }
            }
        )
        
        # Act
        provision_service._update_workspace_runtime(sample_workspace, info)
        
        # Assert
        assert sample_workspace.runtime_id == "c-123"
        assert sample_workspace.runtime_external_port == 8080
        assert sample_workspace.canvas_external_port == 8081
        assert sample_workspace.terminal_external_port == 8082
        assert isinstance(sample_workspace.runtime_mounted_kb_signature, str)
        assert len(sample_workspace.runtime_mounted_kb_signature) == 64
