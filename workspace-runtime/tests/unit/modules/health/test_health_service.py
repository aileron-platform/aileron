"""Health Service Unit Tests"""

from __future__ import annotations

import pytest
from unittest.mock import Mock, MagicMock, patch

from app.modules.health.service import HealthCheckService


@pytest.fixture
def mock_db():
    """Mock database session."""
    return MagicMock()


@pytest.fixture
def health_service(mock_db):
    """Health service fixture."""
    with patch("app.modules.health.service.get_settings") as mock_settings:
        mock_settings.return_value.WORKSPACE_ID = "test-workspace"
        return HealthCheckService(db=mock_db)


class TestGetContainerId:
    """Test getting container ID functionality."""

    def test_get_container_id_success(self, health_service):
        """Test successfully getting container ID."""
        # Act
        result = health_service.get_container_id()

        # Assert
        assert result is not None
        assert isinstance(result, str)

    @patch("app.modules.health.service.socket.gethostname")
    def test_get_container_id_exception(self, mock_hostname, health_service):
        """Test getting container ID exception."""
        # Arrange
        mock_hostname.side_effect = Exception("Test error")

        # Act
        result = health_service.get_container_id()

        # Assert
        assert result is None


class TestCheckAndUpdateWorkspaceStatus:
    """Test checking and updating workspace status functionality."""

    @patch("app.modules.health.service.utcnow")
    def test_check_workspace_not_found(self, mock_utcnow, health_service, mock_db):
        """Test workspace not found."""
        # Arrange
        from datetime import datetime, timezone
        mock_utcnow.return_value = datetime(2024, 1, 1, tzinfo=timezone.utc)
        mock_db.query.return_value.filter.return_value.first.return_value = None

        # Act
        result = health_service.check_and_update_workspace_status()

        # Assert
        assert result["status"] == "unhealthy"
        assert result["workspace_id"] == "test-workspace"

    @patch("app.modules.health.service.utcnow")
    def test_check_workspace_update_success(self, mock_utcnow, health_service, mock_db):
        """Test successfully updating workspace status."""
        # Arrange
        from datetime import datetime, timezone
        mock_utcnow.return_value = datetime(2024, 1, 1, tzinfo=timezone.utc)
        mock_workspace = Mock()
        mock_workspace.id = "test-workspace"
        mock_workspace.runtime_status = "running"
        mock_workspace.runtime_container_id = None
        mock_workspace.runtime_last_seen = None
        mock_db.query.return_value.filter.return_value.first.return_value = mock_workspace

        # Act
        result = health_service.check_and_update_workspace_status()

        # Assert
        assert result["status"] == "healthy"
        assert result["updated"] is True
        assert mock_db.commit.called


class TestServiceInitialization:
    """Test service initialization."""

    def test_service_init(self, mock_db):
        """Test service initialization."""
        # Arrange & Act
        with patch("app.modules.health.service.get_settings") as mock_settings:
            mock_settings.return_value.WORKSPACE_ID = "test-workspace"
            service = HealthCheckService(db=mock_db)

        # Assert
        assert service is not None
        assert service.db is mock_db
