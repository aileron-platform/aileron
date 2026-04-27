"""Health Check Service Tests

Directly test health check service, avoiding dependency on other modules to prevent circular imports
"""

from __future__ import annotations

import socket
from datetime import datetime
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Import required modules directly, avoiding circular imports
import sys
from pathlib import Path

# Ensure app module can be imported
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent))

from app.database.models import Base, User, Workspace
from app.modules.health.service import HealthCheckService


@pytest.fixture
def test_db():
    """Create test database"""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    TestSessionLocal = sessionmaker(bind=engine)
    db = TestSessionLocal()
    
    # Create test user
    user = User(
        id="test-user-1",
        username="testuser",
        email="test@example.com",
        created_at=datetime.utcnow(),
    )
    db.add(user)
    
    # Create test workspace
    workspace = Workspace(
        id="test-workspace-1",
        name="Test Workspace",
        owner_id="test-user-1",
        runtime_status="stopped",
        runtime_container_id=None,
        runtime_last_seen=None,
        created_at=datetime.utcnow(),
    )
    db.add(workspace)
    db.commit()
    
    yield db
    
    db.close()
    Base.metadata.drop_all(engine)


class MockSettings:
    """Mock settings class"""
    WORKSPACE_ID = "test-workspace-1"
    DATABASE_URL = "sqlite:///:memory:"


@pytest.fixture
def mock_settings():
    """Mock settings"""
    settings = MockSettings()
    with patch("app.modules.health.service.get_settings", return_value=settings):
        yield settings


def test_get_container_id(test_db, mock_settings):
    """Test getting container ID"""
    service = HealthCheckService(test_db)
    container_id = service.get_container_id()

    # Should return hostname
    assert container_id == socket.gethostname()


def test_check_and_update_workspace_status_first_time(test_db, mock_settings):
    """Test status update on first health check"""
    service = HealthCheckService(test_db)
    
    with patch.object(service, "get_container_id", return_value="test-container-123"):
        result = service.check_and_update_workspace_status()
    
    # Check return result
    assert result["status"] == "healthy"
    assert result["workspace_id"] == "test-workspace-1"
    assert result["container_id"] == "test-container-123"
    assert result["runtime_status"] == "running"
    assert result["updated"] is True
    assert result["terminal_service"]["status"] == "starting"
    
    # Check database update
    workspace = test_db.query(Workspace).filter(Workspace.id == "test-workspace-1").first()
    assert workspace.runtime_status == "running"
    assert workspace.runtime_container_id == "test-container-123"
    assert workspace.runtime_last_seen is not None


def test_check_and_update_workspace_status_already_running(test_db, mock_settings):
    """Test health check when status is already running"""
    # Set to running first
    workspace = test_db.query(Workspace).filter(Workspace.id == "test-workspace-1").first()
    workspace.runtime_status = "running"
    workspace.runtime_container_id = "test-container-123"
    test_db.commit()

    service = HealthCheckService(test_db)

    with patch.object(service, "get_container_id", return_value="test-container-123"):
        result = service.check_and_update_workspace_status()

    # Check return result
    assert result["status"] == "healthy"
    assert result["runtime_status"] == "running"
    assert result["updated"] is True  # last_seen will still update
    assert result["terminal_service"]["status"] == "starting"


def test_check_and_update_workspace_status_container_id_changed(test_db, mock_settings):
    """Test health check when container ID changes"""
    # Set old container ID first
    workspace = test_db.query(Workspace).filter(Workspace.id == "test-workspace-1").first()
    workspace.runtime_status = "running"
    workspace.runtime_container_id = "old-container-123"
    test_db.commit()

    service = HealthCheckService(test_db)

    with patch.object(service, "get_container_id", return_value="new-container-456"):
        result = service.check_and_update_workspace_status()

    # Check return result
    assert result["status"] == "healthy"
    assert result["container_id"] == "new-container-456"
    assert result["updated"] is True
    assert result["terminal_service"]["status"] == "starting"

    # Check database update
    workspace = test_db.query(Workspace).filter(Workspace.id == "test-workspace-1").first()
    assert workspace.runtime_container_id == "new-container-456"


def test_check_and_update_workspace_status_workspace_not_found(test_db):
    """Test health check when workspace is not found"""
    settings = MockSettings()
    settings.WORKSPACE_ID = "non-existent-workspace"

    with patch("app.modules.health.service.get_settings", return_value=settings):
        service = HealthCheckService(test_db)
        result = service.check_and_update_workspace_status()

    # Check return result
    assert result["status"] == "unhealthy"
    assert "Workspace not found" in result["error"]
    assert result["terminal_service"]["status"] == "starting"


def test_check_and_update_workspace_status_database_error(test_db, mock_settings):
    """Test health check when database error occurs"""
    service = HealthCheckService(test_db)

    # Simulate database error
    with patch.object(test_db, "query", side_effect=Exception("Database connection failed")):
        result = service.check_and_update_workspace_status()

    # Check return result
    assert result["status"] == "degraded"
    assert "Database connection failed" in result["error"]
    assert result["terminal_service"]["status"] == "starting"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
