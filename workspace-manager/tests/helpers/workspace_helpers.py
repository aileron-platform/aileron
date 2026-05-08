"""Workspace Testing Helper Functions"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict

import pytest
from pydantic import BaseModel


class WorkspaceTestHelper:
    """Workspace Testing Helper Functions"""

    @staticmethod
    def create_workspace_config(
        cpu_limit: str = "2",
        memory_limit: str = "4Gi",
        storage_limit: str = "10Gi",
        docker_image: str = "python:3.11-slim",
        environment: Dict[str, str] | None = None,
        ports: list[str] | None = None,
        volumes: list[str] | None = None,
    ) -> Dict[str, Any]:
        """Create workspace configuration"""
        return {
            "cpu_limit": cpu_limit,
            "memory_limit": memory_limit,
            "storage_limit": storage_limit,
            "docker_image": docker_image,
            "environment": environment or {
                "NODE_ENV": "development",
                "PYTHONPATH": "/workspace",
                "DEBUG": "true",
            },
            "ports": ports or ["3000:3000"],
            "volumes": volumes or ["/workspace"],
            "network_mode": "bridge",
            "restart_policy": "unless-stopped",
        }

    @staticmethod
    def create_workspace_payload(
        name: str,
        description: str = "",
        team_id: uuid.UUID | None = None,
        config: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        """Create workspace creation payload"""
        return {
            "name": name,
            "description": description,
            "team_id": str(team_id) if team_id else None,
            "config": config or WorkspaceTestHelper.create_workspace_config(),
        }

    @staticmethod
    def create_workspace_update_payload(
        name: str | None = None,
        description: str | None = None,
        config: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        """Create workspace update payload"""
        payload: Dict[str, Any] = {}
        if name is not None:
            payload["name"] = name
        if description is not None:
            payload["description"] = description
        if config is not None:
            payload["config"] = config
        return payload

    @staticmethod
    def create_workspace_status_payload(
        status: str,
        message: str = "",
        details: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        """Create workspace status payload"""
        return {
            "status": status,
            "message": message,
            "details": details or {},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    @staticmethod
    def simulate_workspace_lifecycle() -> Dict[str, Any]:
        """Simulate workspace lifecycle"""
        return {
            "created": {
                "status": "created",
                "message": "Workspace created",
                "container_id": None,
                "ports": [],
            },
            "starting": {
                "status": "starting",
                "message": "Workspace starting",
                "container_id": "container_123",
                "ports": [],
            },
            "running": {
                "status": "running",
                "message": "Workspace running",
                "container_id": "container_123",
                "ports": ["3000:3000", "8080:8080"],
            },
            "stopping": {
                "status": "stopping",
                "message": "Workspace stopping",
                "container_id": "container_123",
                "ports": ["3000:3000", "8080:8080"],
            },
            "stopped": {
                "status": "stopped",
                "message": "Workspace stopped",
                "container_id": None,
                "ports": [],
            },
            "error": {
                "status": "error",
                "message": "Workspace error occurred",
                "container_id": None,
                "ports": [],
                "error": "Container failed to start",
            },
        }

    @staticmethod
    def create_workspace_metrics() -> Dict[str, Any]:
        """Create workspace metrics"""
        return {
            "cpu_usage": 25.5,
            "memory_usage": 1024,
            "memory_limit": 4096,
            "storage_usage": 2048,
            "storage_limit": 10240,
            "network_rx": 1048576,
            "network_tx": 524288,
            "uptime": 3600,
            "container_status": "running",
            "last_updated": datetime.now(timezone.utc).isoformat(),
        }


class MockWorkspace:
    """Mock workspace object"""

    def __init__(
        self,
        id: uuid.UUID | None = None,
        name: str = "Test Workspace",
        description: str = "A test workspace",
        owner_id: uuid.UUID | None = None,
        team_id: uuid.UUID | None = None,
        status: str = "stopped",
    ):
        self.id = id or uuid.uuid4()
        self.name = name
        self.description = description
        self.owner_id = owner_id or uuid.uuid4()
        self.team_id = team_id
        self.status = status
        self.config = WorkspaceTestHelper.create_workspace_config()
        self.created_at = datetime.now(timezone.utc)
        self.updated_at = datetime.now(timezone.utc)
        self.container_id = None
        self.ports = []

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "id": str(self.id),
            "name": self.name,
            "description": self.description,
            "owner_id": str(self.owner_id),
            "team_id": str(self.team_id) if self.team_id else None,
            "status": self.status,
            "config": self.config,
            "container_id": self.container_id,
            "ports": self.ports,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    def start(self) -> None:
        """Start workspace"""
        self.status = "running"
        self.container_id = f"container_{uuid.uuid4().hex[:8]}"
        self.ports = ["3000:3000"]
        self.updated_at = datetime.now(timezone.utc)

    def stop(self) -> None:
        """Stop workspace"""
        self.status = "stopped"
        self.container_id = None
        self.ports = []
        self.updated_at = datetime.now(timezone.utc)

    def update_config(self, config: Dict[str, Any]) -> None:
        """Update configuration"""
        self.config.update(config)
        self.updated_at = datetime.now(timezone.utc)


@pytest.fixture
def workspace_helper():
    """Workspace testing helper fixture"""
    return WorkspaceTestHelper()


@pytest.fixture
def mock_workspace():
    """Mock workspace fixture"""
    return MockWorkspace()


@pytest.fixture
def running_workspace():
    """Running workspace fixture"""
    workspace = MockWorkspace()
    workspace.start()
    return workspace


@pytest.fixture
def workspace_payload(workspace_helper: WorkspaceTestHelper):
    """Workspace creation payload fixture"""
    return workspace_helper.create_workspace_payload(
        name="Test Workspace",
        description="A test workspace for testing",
    )


@pytest.fixture
def workspace_lifecycle(workspace_helper: WorkspaceTestHelper):
    """Workspace lifecycle fixture"""
    return workspace_helper.simulate_workspace_lifecycle()


@pytest.fixture
def workspace_metrics(workspace_helper: WorkspaceTestHelper):
    """Workspace metrics fixture"""
    return workspace_helper.create_workspace_metrics()


def assert_workspace_status(
    workspace_data: Dict[str, Any], expected_status: str
) -> None:
    """Assert workspace status"""
    assert "status" in workspace_data, "Workspace data missing status field"
    assert workspace_data["status"] == expected_status, f"Workspace status mismatch: expected {expected_status}, actual {workspace_data['status']}"


def assert_workspace_config(
    workspace_data: Dict[str, Any], expected_config: Dict[str, Any]
) -> None:
    """Assert workspace configuration"""
    assert "config" in workspace_data, "Workspace data missing config field"
    config = workspace_data["config"]

    for key, value in expected_config.items():
        assert key in config, f"Workspace config missing {key} field"
        assert config[key] == value, f"Workspace config {key} mismatch: expected {value}, actual {config[key]}"


def assert_workspace_metrics(metrics: Dict[str, Any]) -> None:
    """Assert workspace metrics format"""
    required_fields = [
        "cpu_usage",
        "memory_usage",
        "memory_limit",
        "storage_usage",
        "storage_limit",
        "network_rx",
        "network_tx",
        "uptime",
        "container_status",
        "last_updated",
    ]

    for field in required_fields:
        assert field in metrics, f"Workspace metrics missing {field} field"

    # Check value ranges
    assert 0 <= metrics["cpu_usage"] <= 100, "CPU usage should be between 0-100"
    assert metrics["memory_usage"] >= 0, "Memory usage should be non-negative"
    assert metrics["storage_usage"] >= 0, "Storage usage should be non-negative"
    assert metrics["uptime"] >= 0, "Uptime should be non-negative"
