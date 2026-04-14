"""RuntimeProvisionService 單元測試"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
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
    settings.DOCKER_NETWORK = "workspace-network"
    settings.ENV = "testing"
    settings.DATABASE_URL = "postgresql://test:test@localhost/test"
    settings.REDIS_URL = "redis://localhost:6379/0"
    settings.PORT = 8000
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
    workspace.web_preview_internal_port = 3003
    workspace.web_preview_external_port = 8081
    workspace.terminal_external_port = 8082
    workspace.runtime_status = "pending"
    workspace.env_vars = [
        {"key": "NODE_ENV", "value": "production"},
    ]
    workspace.port_mappings = [
        {"container_port": 8000, "host_port": 9000, "protocol": "tcp"}
    ]
    workspace.setup_script = "#!/bin/bash\necho 'Setup complete'"
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

    def test_update_workspace_runtime(self, provision_service, sample_workspace):
        """測試：更新工作區信息"""
        # Arrange
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
        assert sample_workspace.web_preview_external_port == 8081
        assert sample_workspace.terminal_external_port == 8082
