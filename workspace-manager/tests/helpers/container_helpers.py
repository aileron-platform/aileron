"""容器測試輔助工具"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict

import pytest


class ContainerTestHelper:
    """容器測試輔助工具"""

    @staticmethod
    def create_container_config(
        image: str = "python:3.11-slim",
        command: str | None = None,
        environment: Dict[str, str] | None = None,
        ports: Dict[str, Any] | None = None,
        volumes: Dict[str, Any] | None = None,
        resources: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        """創建容器配置"""
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
        """創建容器資訊"""
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
        """取得容器狀態"""
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
        """模擬容器生命週期"""
        return {
            "created": {
                "status": "created",
                "message": "容器已創建",
                "container_id": None,
                "ports": {},
            },
            "starting": {
                "status": "starting",
                "message": "容器啟動中",
                "container_id": f"container_{uuid.uuid4().hex[:12]}",
                "ports": {},
            },
            "running": {
                "status": "running",
                "message": "容器運行中",
                "container_id": f"container_{uuid.uuid4().hex[:12]}",
                "ports": {"3000/tcp": {"HostPort": "3000"}},
            },
            "stopping": {
                "status": "stopping",
                "message": "容器停止中",
                "container_id": f"container_{uuid.uuid4().hex[:12]}",
                "ports": {"3000/tcp": {"HostPort": "3000"}},
            },
            "stopped": {
                "status": "exited",
                "message": "容器已停止",
                "container_id": None,
                "ports": {},
            },
            "error": {
                "status": "exited",
                "message": "容器發生錯誤",
                "container_id": None,
                "ports": {},
                "error": "Container failed to start",
            },
        }

    @staticmethod
    def create_container_stats() -> Dict[str, Any]:
        """創建容器統計資料"""
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
        """創建 Docker 映像資訊"""
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
    """Mock 容器物件"""

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
        """啟動容器"""
        self.status = "running"
        self.started_at = datetime.now(timezone.utc)
        self.ports = {"3000/tcp": {"HostPort": "3000", "ContainerPort": "3000"}}
        self.exit_code = None

    def stop(self) -> None:
        """停止容器"""
        self.status = "exited"
        self.finished_at = datetime.now(timezone.utc)
        self.exit_code = 0
        self.ports = {}

    def fail(self, error: str = "Container failed") -> None:
        """容器失敗"""
        self.status = "exited"
        self.finished_at = datetime.now(timezone.utc)
        self.exit_code = 1
        self.error = error
        self.ports = {}

    def to_dict(self) -> Dict[str, Any]:
        """轉換為字典"""
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
    """容器測試輔助工具 fixture"""
    return ContainerTestHelper()


@pytest.fixture
def mock_container():
    """Mock 容器 fixture"""
    return MockContainer()


@pytest.fixture
def running_container():
    """運行中的容器 fixture"""
    container = MockContainer()
    container.start()
    return container


@pytest.fixture
def stopped_container():
    """已停止的容器 fixture"""
    container = MockContainer(status="exited")
    container.stop()
    return container


@pytest.fixture
def failed_container():
    """失敗的容器 fixture"""
    container = MockContainer()
    container.fail("Test error")
    return container


@pytest.fixture
def container_lifecycle(container_helper: ContainerTestHelper):
    """容器生命週期 fixture"""
    return container_helper.simulate_container_lifecycle()


@pytest.fixture
def container_stats(container_helper: ContainerTestHelper):
    """容器統計資料 fixture"""
    return container_helper.create_container_stats()


@pytest.fixture
def docker_image_info(container_helper: ContainerTestHelper):
    """Docker 映像資訊 fixture"""
    return container_helper.create_docker_image_info(
        name="python",
        tag="3.11-slim",
    )


def assert_container_status(
    container_data: Dict[str, Any], expected_status: str
) -> None:
    """斷言容器狀態"""
    assert "status" in container_data, "容器資料缺少 status 欄位"
    assert container_data["status"] == expected_status, f"容器狀態不匹配: 期望 {expected_status}, 實際 {container_data['status']}"


def assert_container_ports(
    container_data: Dict[str, Any], expected_ports: Dict[str, Any]
) -> None:
    """斷言容器端口映射"""
    assert "ports" in container_data, "容器資料缺少 ports 欄位"
    ports = container_data["ports"]

    for port_key, expected_port in expected_ports.items():
        assert port_key in ports, f"容器端口缺少 {port_key}"
        assert ports[port_key] == expected_port, f"端口 {port_key} 映射不匹配"


def assert_container_stats(stats: Dict[str, Any]) -> None:
    """斷言容器統計資料格式"""
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
        assert field in stats, f"容器統計資料缺少 {field} 欄位"

    # 檢查數值範圍
    assert 0 <= stats["cpu_usage"] <= 100, "CPU 使用率應在 0-100 之間"
    assert stats["memory_usage"] >= 0, "記憶體使用量應為非負數"
    assert stats["network_rx"] >= 0, "網路接收應為非負數"
    assert stats["network_tx"] >= 0, "網路傳送應為非負數"
    assert stats["block_read"] >= 0, "區塊讀取應為非負數"
    assert stats["block_write"] >= 0, "區塊寫入應為非負數"
    assert stats["pids"] >= 0, "進程數應為非負數"
    assert stats["uptime"] >= 0, "運行時間應為非負數"


def assert_docker_image_info(image_info: Dict[str, Any]) -> None:
    """斷言 Docker 映像資訊格式"""
    required_fields = ["id", "repo_tags", "created", "size", "labels"]

    for field in required_fields:
        assert field in image_info, f"Docker 映像資訊缺少 {field} 欄位"

    assert len(image_info["repo_tags"]) > 0, "Docker 映像應至少有一個標籤"
    assert image_info["size"] > 0, "Docker 映像大小應大於 0"
    assert isinstance(image_info["labels"], dict), "Docker 映像標籤應為字典格式"