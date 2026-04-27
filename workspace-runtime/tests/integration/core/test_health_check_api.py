"""Core module Health Check API tests"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional
from unittest.mock import AsyncMock

from .helpers import override_dependency
from app.modules.health.service import HealthCheckService


class StubWorkspace:
    """Controllable Workspace model stub"""

    def __init__(self, **kwargs) -> None:
        self._data = kwargs
        self._workspaces_dict = kwargs.get('_workspaces_dict', {})
        self.id = kwargs.get("id")
        self.runtime_status = kwargs.get("runtime_status")
        self.runtime_container_id = kwargs.get("runtime_container_id")
        self.runtime_last_seen = kwargs.get("runtime_last_seen")
        self.updated_at = kwargs.get("updated_at")

    def __getattr__(self, name):
        return self._data.get(name)

    def __setattr__(self, name, value):
        if name.startswith('_'):
            super().__setattr__(name, value)
        else:
            self._data[name] = value
            # Synchronously update corresponding instance attributes
            if name in ['runtime_status', 'runtime_container_id', 'runtime_last_seen', 'updated_at']:
                super().__setattr__(name, value)
                # If workspaces_dict reference exists, synchronously update
                if hasattr(self, '_workspaces_dict') and self.id in self._workspaces_dict:
                    self._workspaces_dict[self.id][name] = value


class StubQuery:
    """Controllable SQLAlchemy Query stub"""

    def __init__(self, results: list, workspaces_dict: dict = None) -> None:
        self.results = results
        self.workspaces_dict = workspaces_dict or {}

    def filter(self, *args, **kwargs):
        return self

    def first(self):
        return self.results[0] if self.results else None


class StubDatabaseService:
    """Controllable database service stub"""

    def __init__(self) -> None:
        self.should_fail = False
        self.workspaces = {}
        self._committed = False

    def query(self, model):
        """Simulate SQLAlchemy query method"""
        # Convert to Workspace objects
        workspace_objects = []
        for workspace_id, workspace_data in self.workspaces.items():
            if model.__name__ == "Workspace":
                # Pass workspaces_dict reference to StubWorkspace
                workspace_data_with_ref = {**workspace_data, '_workspaces_dict': self.workspaces}
                workspace_objects.append(StubWorkspace(**workspace_data_with_ref))

        return StubQuery(workspace_objects, self.workspaces)

    def commit(self) -> None:
        """Simulate database commit"""
        if self.should_fail:
            raise Exception("Database commit failed")
        self._committed = True

    def rollback(self) -> None:
        """Simulate database rollback"""
        self._committed = False


class StubRuntimeService:
    """Controllable RuntimeService stub"""

    def __init__(self) -> None:
        self.status = "running"
        self.container_id = "container_123"

    def get_status(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "containerId": self.container_id,
            "lastHeartbeat": datetime.now(timezone.utc).isoformat(),
        }

    def update_status(self, status: str, container_id: Optional[str] = None) -> None:
        self.status = status
        if container_id:
            self.container_id = container_id


def mock_get_db():
    """Mock get_db dependency"""
    return StubDatabaseService()


def test_hl_001_normal_status_update(client):
    """HL-001 Normal status update"""
    db_service = StubDatabaseService()
    runtime_service = StubRuntimeService()
    runtime_service.status = "starting"

    # Simulate workspace record in database (using actual WORKSPACE_ID)
    workspace_id = "default-workspace"
    db_service.workspaces[workspace_id] = {
        "id": workspace_id,
        "runtime_status": "stopped",  # Set to non-running/starting status to trigger update
        "runtime_container_id": "old_container_id",  # Set to different container ID to trigger update
        "runtime_last_seen": None,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    # Mock get_db dependency
    import app.database.session as db_session
    original_get_db = db_session.get_db

    def mock_get_db():
        return db_service

    with override_dependency(original_get_db, mock_get_db):
        response = client.get("/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "healthy"
    assert payload["updated"] is True

    # Verify Health Check API response
    assert "container_id" in payload
    assert payload["runtime_status"] == "running"
    assert payload["updated"] is True
    assert payload["terminal_service"]["status"] == "starting"
    assert payload["terminal_service"]["port"] == 3004


def test_hl_002_database_connection_failure(client):
    """HL-002 Database connection failure"""

    class FailingDatabaseService:
        def query(self, model):
            raise Exception("Database connection failed")

        def commit(self):
            pass

        def rollback(self):
            pass

    db_service = FailingDatabaseService()

    # Mock get_db dependency
    import app.database.session as db_session
    original_get_db = db_session.get_db

    def mock_get_db():
        return db_service

    with override_dependency(original_get_db, mock_get_db):
        response = client.get("/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "degraded"
    assert "error" in payload
    assert "Database connection failed" in payload["error"]
    assert payload["terminal_service"]["status"] == "starting"


def test_hl_003_workspace_not_found(client):
    """HL-003 Workspace not found"""
    db_service = StubDatabaseService()
    # Do not create any workspace records

    # Mock get_db dependency
    import app.database.session as db_session
    original_get_db = db_session.get_db

    def mock_get_db():
        return db_service

    with override_dependency(original_get_db, mock_get_db):
        response = client.get("/health")

    assert response.status_code == 200
    payload = response.json()
    # Even without workspace records, health check should report normally
    assert payload["status"] == "unhealthy"
    assert payload["terminal_service"]["status"] == "starting"


def test_hl_004_container_id_unavailable(client):
    """HL-004 Socket cannot get hostname"""

    class FailingSocketService:
        def gethostname(self):
            raise Exception("Container ID unavailable")

    # Mock socket.gethostname failure
    import socket
    original_gethostname = socket.gethostname
    socket.gethostname = FailingSocketService().gethostname

    try:
        db_service = StubDatabaseService()
        # Set up workspace record
        workspace_id = "default-workspace"
        db_service.workspaces[workspace_id] = {
            "id": workspace_id,
            "runtime_status": "running",
            "runtime_container_id": None,
            "runtime_last_seen": None,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

        # Mock get_db dependency
        import app.database.session as db_session
        original_get_db = db_session.get_db

        def mock_get_db():
            return db_service

        with override_dependency(original_get_db, mock_get_db):
            response = client.get("/health")

        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "healthy"  # socket.gethostname failure does not affect health check
        assert payload["container_id"] is None  # container_id will be None
        assert payload["terminal_service"]["status"] == "starting"

    finally:
        # Restore original socket.gethostname
        socket.gethostname = original_gethostname


def test_hl_005_database_operational_error(client):
    """HL-005 Database operational error"""
    db_service = StubDatabaseService()

    # Set up a workspace, but make commit method fail
    workspace_id = "default-workspace"
    db_service.workspaces[workspace_id] = {
        "id": workspace_id,
        "runtime_status": "stopped",
        "runtime_container_id": "old_container_id",
        "runtime_last_seen": None,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    db_service.should_fail = True  # Make commit fail

    # Mock get_db dependency
    import app.database.session as db_session
    original_get_db = db_session.get_db

    def mock_get_db():
        return db_service

    with override_dependency(original_get_db, mock_get_db):
        response = client.get("/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "degraded"
    assert "error" in payload
    assert "Database commit failed" in payload["error"]
