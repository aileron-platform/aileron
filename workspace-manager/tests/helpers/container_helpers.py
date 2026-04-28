"""Container Testing Helper Functions"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict

import pytest


class ContainerTestHelper:
    """Container Testing Helper Functions"""

    @staticmethod
    def create_container_config(
        image: str = "python:3.11-slim",
        command: str | None = None,
        environment: Dict[str, str] | None = None,
        ports: Dict[str, Any] | None = None,
        volumes: Dict[str, Any] | None = None,
        resources: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        """Create container configuration"""
        return {
            "image": image,
            "command": command or "python -m http.server 3000",
            "environment": environment or {
                "NODE_ENV": "development",
                "PYTHONPATH": "/workspace",
                "DEBUG": "true",
            },
            "ports": ports or {"3000/tcp": 3000},
            "volumes": volumes or {"/workspace": {"bind": "/workspace", "mode": "rw"}},
            "resources": resources or {
                "cpu_limit": 2,
                "memory_limit": "4Gi",
                "storage_limit": "10Gi",
            },
            "restart_policy": {"name": "unless-stopped"},
            "network_mode": "bridge",
        }

    @staticmethod
    def create_container_info(
        container_id: str | None = None,
        name: str | None = None,
        status: str = "running",
        image: str = "python:3.11-slim",
        ports: Dict[str, Any] | None = None,
        created_at: datetime | None = None,
    ) -> Dict[str, Any]:
        """Create container information"""
        return {
            "id": container_id or f"container_{uuid.uuid4().hex[:12]}",
            "name": name or f"test-container-{uuid.uuid4().hex[:8]}",
            "status": status,
            "image": image,
            "ports": ports or {"3000/tcp": {"HostPort": "3000", "ContainerPort": "3000"}},
            "created": created_at or datetime.now(timezone.utc),
            "state": ContainerTestHelper._get_container_state(status),
        }

    @staticmethod
    def _get_container_state(status: str) -> Dict[str, Any]:
        """Get container state"""
        states = {
            "running": {
                "status": "running",
                "running": True,
                "paused": False,
                "restarting": False,
                "oom_killed": False,
                "dead": False,
                "pid": 12345,
                "exit_code": 0,
                "error": "",
                "started_at": datetime.now(timezone.utc),
                "finished_at": None,
            },
            "stopped": {
                "status": "exited",
                "running": False,
                "paused": False,
                "restarting": False,
                "oom_killed": False,
                "dead": False,
                "pid": 0,
                "exit_code": 0,
                "error": "",
                "started_at": datetime.now(timezone.utc),
                "finished_at": datetime.now(timezone.utc),
            },
            "error": {
                "status": "exited",
                "running": False,
                "paused": False,
                "restarting": False,
                "oom_killed": False,
                "dead": True,
                "pid": 0,
                "exit_code": 1,
                "error": "Container failed to start",
                "started_at": datetime.now(timezone.utc),
                "finished_at": datetime.now(timezone.utc),
            },
        }
        return states.get(status, states["stopped"])

    @staticmethod
    def simulate_container_lifecycle() -> Dict[str, Any]:
        """Simulate container lifecycle"""
        return {
            "created": {
                "status": "created",
                "message": "Container created",
                "container_id": None,
                "ports": {},
            },
            "starting": {
                "status": "starting",
                "message": "Container starting",
                "container_id": f"container_{uuid.uuid4().hex[:12]}",
                "ports": {},
            },
            "running": {
                "status": "running",
                "message": "Container running",
                "container_id": f"container_{uuid.uuid4().hex[:12]}",
                "ports": {"3000/tcp": {"HostPort": "3000"}},
            },
            "stopping": {
                "status": "stopping",
                "message": "Container stopping",
                "container_id": f"container_{uuid.uuid4().hex[:12]}",
                "ports": {"3000/tcp": {"HostPort": "3000"}},
            },
            "stopped": {
                "status": "exited",
                "message": "Container stopped",
                "container_id": None,
                "ports": {},
            },
            "error": {
                "status": "exited",
                "message": "Container error occurred",
                "container_id": None,
                "ports": {},
                "error": "Container failed to start",
            },
        }

    @staticmethod
    def create_container_stats() -> Dict[str, Any]:
        """Create container statistics"""
        return {
            "cpu_usage": 15.5,
            "memory_usage": 512,
            "memory_limit": 4096,
            "network_rx": 524288,
            "network_tx": 262144,
            "block_read": 1048576,
            "block_write": 2097152,
            "pids": 5,
            "uptime": 1800,
            "last_updated": datetime.now(timezone.utc).isoformat(),
        }

    @staticmethod
    def create_docker_image_info(
        name: str,
        tag: str = "latest",
        size: int = 500000000,
        created: datetime | None = None,
    ) -> Dict[str, Any]:
        """Create Docker image information"""
        return {
            "id": f"sha256:{uuid.uuid4().hex}",
            "repo_tags": [f"{name}:{tag}"],
            "created": created or datetime.now(timezone.utc),
            "size": size,
            "virtual_size": size,
            "labels": {
                "maintainer": "Aileron",
                "version": tag,
            },
        }


class MockContainer:
    """Mock container object"""

    def __init__(
        self,
        container_id: str | None = None,
        name: str = "test-container",
        image: str = "python:3.11-slim",
        status: str = "created",
    ):
        self.id = container_id or f"container_{uuid.uuid4().hex[:12]}"
        self.name = name
        self.image = image
        self.status = status
        self.config = ContainerTestHelper.create_container_config()
        self.created_at = datetime.now(timezone.utc)
        self.started_at = None
        self.finished_at = None
        self.ports = {}
        self.exit_code = None

    def start(self) -> None:
        """Start container"""
        self.status = "running"
        self.started_at = datetime.now(timezone.utc)
        self.ports = {"3000/tcp": {"HostPort": "3000", "ContainerPort": "3000"}}
        self.exit_code = None

    def stop(self) -> None:
        """Stop container"""
        self.status = "exited"
        self.finished_at = datetime.now(timezone.utc)
        self.exit_code = 0
        self.ports = {}

    def fail(self, error: str = "Container failed") -> None:
        """Container failure"""
        self.status = "exited"
        self.finished_at = datetime.now(timezone.utc)
        self.exit_code = 1
        self.error = error
        self.ports = {}

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return ContainerTestHelper.create_container_info(
            container_id=self.id,
            name=self.name,
            status=self.status,
            image=self.image,
            ports=self.ports,
            created_at=self.created_at,
        )


@pytest.fixture
def container_helper():
    """Container testing helper fixture"""
    return ContainerTestHelper()


@pytest.fixture
def mock_container():
    """Mock container fixture"""
    return MockContainer()


@pytest.fixture
def running_container():
    """Running container fixture"""
    container = MockContainer()
    container.start()
    return container


@pytest.fixture
def stopped_container():
    """Stopped container fixture"""
    container = MockContainer(status="exited")
    container.stop()
    return container


@pytest.fixture
def failed_container():
    """Failed container fixture"""
    container = MockContainer()
    container.fail("Test error")
    return container


@pytest.fixture
def container_lifecycle(container_helper: ContainerTestHelper):
    """Container lifecycle fixture"""
    return container_helper.simulate_container_lifecycle()


@pytest.fixture
def container_stats(container_helper: ContainerTestHelper):
    """Container statistics fixture"""
    return container_helper.create_container_stats()


@pytest.fixture
def docker_image_info(container_helper: ContainerTestHelper):
    """Docker image information fixture"""
    return container_helper.create_docker_image_info(
        name="python",
        tag="3.11-slim",
    )


def assert_container_status(
    container_data: Dict[str, Any], expected_status: str
) -> None:
    """Assert container status"""
    assert "status" in container_data, "Container data missing status field"
    assert container_data["status"] == expected_status, f"Container status mismatch: expected {expected_status}, actual {container_data['status']}"


def assert_container_ports(
    container_data: Dict[str, Any], expected_ports: Dict[str, Any]
) -> None:
    """Assert container port mappings"""
    assert "ports" in container_data, "Container data missing ports field"
    ports = container_data["ports"]

    for port_key, expected_port in expected_ports.items():
        assert port_key in ports, f"Container port missing {port_key}"
        assert ports[port_key] == expected_port, f"Port {port_key} mapping mismatch"


def assert_container_stats(stats: Dict[str, Any]) -> None:
    """Assert container statistics format"""
    required_fields = [
        "cpu_usage",
        "memory_usage",
        "memory_limit",
        "network_rx",
        "network_tx",
        "block_read",
        "block_write",
        "pids",
        "uptime",
        "last_updated",
    ]

    for field in required_fields:
        assert field in stats, f"Container statistics missing {field} field"

    # Check value ranges
    assert 0 <= stats["cpu_usage"] <= 100, "CPU usage should be between 0-100"
    assert stats["memory_usage"] >= 0, "Memory usage should be non-negative"
    assert stats["network_rx"] >= 0, "Network receive should be non-negative"
    assert stats["network_tx"] >= 0, "Network transmit should be non-negative"
    assert stats["block_read"] >= 0, "Block read should be non-negative"
    assert stats["block_write"] >= 0, "Block write should be non-negative"
    assert stats["pids"] >= 0, "Process count should be non-negative"
    assert stats["uptime"] >= 0, "Uptime should be non-negative"


def assert_docker_image_info(image_info: Dict[str, Any]) -> None:
    """Assert Docker image information format"""
    required_fields = ["id", "repo_tags", "created", "size", "labels"]

    for field in required_fields:
        assert field in image_info, f"Docker image information missing {field} field"

    assert len(image_info["repo_tags"]) > 0, "Docker image should have at least one tag"
    assert image_info["size"] > 0, "Docker image size should be greater than 0"
    assert isinstance(image_info["labels"], dict), "Docker image labels should be in dictionary format"