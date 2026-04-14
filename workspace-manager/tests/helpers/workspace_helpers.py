"""工作區測試輔助工具"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict

import pytest
from pydantic import BaseModel


class WorkspaceTestHelper:
    """工作區測試輔助工具"""

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
        """創建工作區配置"""
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
        template_id: uuid.UUID | None = None,
        config: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        """創建工作區創建 payload"""
        return {
            "name": name,
            "description": description,
            "team_id": str(team_id) if team_id else None,
            "template_id": str(template_id) if template_id else None,
            "config": config or WorkspaceTestHelper.create_workspace_config(),
        }

    @staticmethod
    def create_workspace_update_payload(
        name: str | None = None,
        description: str | None = None,
        config: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        """創建工作區更新 payload"""
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
        """創建工作區狀態 payload"""
        return {
            "status": status,
            "message": message,
            "details": details or {},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    @staticmethod
    def simulate_workspace_lifecycle() -> Dict[str, Any]:
        """模擬工作區生命週期"""
        return {
            "created": {
                "status": "created",
                "message": "工作區已創建",
                "container_id": None,
                "ports": [],
            },
            "starting": {
                "status": "starting",
                "message": "工作區啟動中",
                "container_id": "container_123",
                "ports": [],
            },
            "running": {
                "status": "running",
                "message": "工作區運行中",
                "container_id": "container_123",
                "ports": ["3000:3000", "8080:8080"],
            },
            "stopping": {
                "status": "stopping",
                "message": "工作區停止中",
                "container_id": "container_123",
                "ports": ["3000:3000", "8080:8080"],
            },
            "stopped": {
                "status": "stopped",
                "message": "工作區已停止",
                "container_id": None,
                "ports": [],
            },
            "error": {
                "status": "error",
                "message": "工作區發生錯誤",
                "container_id": None,
                "ports": [],
                "error": "Container failed to start",
            },
        }

    @staticmethod
    def create_workspace_metrics() -> Dict[str, Any]:
        """創建工作區指標"""
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
    """Mock 工作區物件"""

    def __init__(
        self,
        id: uuid.UUID | None = None,
        name: str = "Test Workspace",
        description: str = "A test workspace",
        owner_id: uuid.UUID | None = None,
        team_id: uuid.UUID | None = None,
        template_id: uuid.UUID | None = None,
        status: str = "stopped",
    ):
        self.id = id or uuid.uuid4()
        self.name = name
        self.description = description
        self.owner_id = owner_id or uuid.uuid4()
        self.team_id = team_id
        self.template_id = template_id
        self.status = status
        self.config = WorkspaceTestHelper.create_workspace_config()
        self.created_at = datetime.now(timezone.utc)
        self.updated_at = datetime.now(timezone.utc)
        self.container_id = None
        self.ports = []

    def to_dict(self) -> Dict[str, Any]:
        """轉換為字典"""
        return {
            "id": str(self.id),
            "name": self.name,
            "description": self.description,
            "owner_id": str(self.owner_id),
            "team_id": str(self.team_id) if self.team_id else None,
            "template_id": str(self.template_id) if self.template_id else None,
            "status": self.status,
            "config": self.config,
            "container_id": self.container_id,
            "ports": self.ports,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    def start(self) -> None:
        """啟動工作區"""
        self.status = "running"
        self.container_id = f"container_{uuid.uuid4().hex[:8]}"
        self.ports = ["3000:3000"]
        self.updated_at = datetime.now(timezone.utc)

    def stop(self) -> None:
        """停止工作區"""
        self.status = "stopped"
        self.container_id = None
        self.ports = []
        self.updated_at = datetime.now(timezone.utc)

    def update_config(self, config: Dict[str, Any]) -> None:
        """更新配置"""
        self.config.update(config)
        self.updated_at = datetime.now(timezone.utc)


@pytest.fixture
def workspace_helper():
    """工作區測試輔助工具 fixture"""
    return WorkspaceTestHelper()


@pytest.fixture
def mock_workspace():
    """Mock 工作區 fixture"""
    return MockWorkspace()


@pytest.fixture
def running_workspace():
    """運行中的工作區 fixture"""
    workspace = MockWorkspace()
    workspace.start()
    return workspace


@pytest.fixture
def workspace_payload(workspace_helper: WorkspaceTestHelper):
    """工作區創建 payload fixture"""
    return workspace_helper.create_workspace_payload(
        name="Test Workspace",
        description="A test workspace for testing",
    )


@pytest.fixture
def workspace_lifecycle(workspace_helper: WorkspaceTestHelper):
    """工作區生命週期 fixture"""
    return workspace_helper.simulate_workspace_lifecycle()


@pytest.fixture
def workspace_metrics(workspace_helper: WorkspaceTestHelper):
    """工作區指標 fixture"""
    return workspace_helper.create_workspace_metrics()


def assert_workspace_status(
    workspace_data: Dict[str, Any], expected_status: str
) -> None:
    """斷言工作區狀態"""
    assert "status" in workspace_data, "工作區資料缺少 status 欄位"
    assert workspace_data["status"] == expected_status, f"工作區狀態不匹配: 期望 {expected_status}, 實際 {workspace_data['status']}"


def assert_workspace_config(
    workspace_data: Dict[str, Any], expected_config: Dict[str, Any]
) -> None:
    """斷言工作區配置"""
    assert "config" in workspace_data, "工作區資料缺少 config 欄位"
    config = workspace_data["config"]

    for key, value in expected_config.items():
        assert key in config, f"工作區配置缺少 {key} 欄位"
        assert config[key] == value, f"工作區配置 {key} 不匹配: 期望 {value}, 實際 {config[key]}"


def assert_workspace_metrics(metrics: Dict[str, Any]) -> None:
    """斷言工作區指標格式"""
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
        assert field in metrics, f"工作區指標缺少 {field} 欄位"

    # 檢查數值範圍
    assert 0 <= metrics["cpu_usage"] <= 100, "CPU 使用率應在 0-100 之間"
    assert metrics["memory_usage"] >= 0, "記憶體使用量應為非負數"
    assert metrics["storage_usage"] >= 0, "儲存使用量應為非負數"
    assert metrics["uptime"] >= 0, "運行時間應為非負數"