"""核心模組 Health Check API 測試"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional
from unittest.mock import AsyncMock

from .helpers import override_dependency
from app.modules.health.service import HealthCheckService


class StubWorkspace:
    """可控制的 Workspace 模型 stub"""

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
            # 同步更新對應的實例屬性
            if name in ['runtime_status', 'runtime_container_id', 'runtime_last_seen', 'updated_at']:
                super().__setattr__(name, value)
                # 如果有 workspaces_dict 的引用，同步更新
                if hasattr(self, '_workspaces_dict') and self.id in self._workspaces_dict:
                    self._workspaces_dict[self.id][name] = value


class StubQuery:
    """可控制的 SQLAlchemy Query stub"""

    def __init__(self, results: list, workspaces_dict: dict = None) -> None:
        self.results = results
        self.workspaces_dict = workspaces_dict or {}

    def filter(self, *args, **kwargs):
        return self

    def first(self):
        return self.results[0] if self.results else None


class StubDatabaseService:
    """可控制的資料庫服務 stub"""

    def __init__(self) -> None:
        self.should_fail = False
        self.workspaces = {}
        self._committed = False

    def query(self, model):
        """模擬 SQLAlchemy query 方法"""
        # 將轉為 Workspace 對象
        workspace_objects = []
        for workspace_id, workspace_data in self.workspaces.items():
            if model.__name__ == "Workspace":
                # 傳遞 workspaces_dict 引用給 StubWorkspace
                workspace_data_with_ref = {**workspace_data, '_workspaces_dict': self.workspaces}
                workspace_objects.append(StubWorkspace(**workspace_data_with_ref))

        return StubQuery(workspace_objects, self.workspaces)

    def commit(self) -> None:
        """模擬資料庫提交"""
        if self.should_fail:
            raise Exception("Database commit failed")
        self._committed = True

    def rollback(self) -> None:
        """模擬資料庫回滾"""
        self._committed = False


class StubRuntimeService:
    """可控制的 RuntimeService stub"""

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
    """模擬 get_db 依賴"""
    return StubDatabaseService()


def test_hl_001_normal_status_update(client):
    """HL-001 正常狀態更新"""
    db_service = StubDatabaseService()
    runtime_service = StubRuntimeService()
    runtime_service.status = "starting"

    # 模擬資料庫中的工作區記錄 (使用實際的 WORKSPACE_ID)
    workspace_id = "default-workspace"
    db_service.workspaces[workspace_id] = {
        "id": workspace_id,
        "runtime_status": "stopped",  # 設為非 running/starting 狀態以觸發更新
        "runtime_container_id": "old_container_id",  # 設為不同容器 ID 以觸發更新
        "runtime_last_seen": None,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    # 模擬 get_db 依賴
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

    # 驗證 Health Check API 回應
    assert "container_id" in payload
    assert payload["runtime_status"] == "running"
    assert payload["updated"] is True
    assert payload["terminal_service"]["status"] == "starting"
    assert payload["terminal_service"]["port"] == 3004


def test_hl_002_database_connection_failure(client):
    """HL-002 資料庫連線失敗"""

    class FailingDatabaseService:
        def query(self, model):
            raise Exception("Database connection failed")

        def commit(self):
            pass

        def rollback(self):
            pass

    db_service = FailingDatabaseService()

    # 模擬 get_db 依賴
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
    """HL-003 工作區不存在"""
    db_service = StubDatabaseService()
    # 不建立任何工作區記錄

    # 模擬 get_db 依賴
    import app.database.session as db_session
    original_get_db = db_session.get_db

    def mock_get_db():
        return db_service

    with override_dependency(original_get_db, mock_get_db):
        response = client.get("/health")

    assert response.status_code == 200
    payload = response.json()
    # 即使沒有工作區記錄，健康檢查仍應回報正常
    assert payload["status"] == "unhealthy"
    assert payload["terminal_service"]["status"] == "starting"


def test_hl_004_container_id_unavailable(client):
    """HL-004 Socket 無法獲取主機名"""

    class FailingSocketService:
        def gethostname(self):
            raise Exception("Container ID unavailable")

    # 模擬 socket.gethostname 失敗
    import socket
    original_gethostname = socket.gethostname
    socket.gethostname = FailingSocketService().gethostname

    try:
        db_service = StubDatabaseService()
        # 設置 workspace 記錄
        workspace_id = "default-workspace"
        db_service.workspaces[workspace_id] = {
            "id": workspace_id,
            "runtime_status": "running",
            "runtime_container_id": None,
            "runtime_last_seen": None,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

        # 模擬 get_db 依賴
        import app.database.session as db_session
        original_get_db = db_session.get_db

        def mock_get_db():
            return db_service

        with override_dependency(original_get_db, mock_get_db):
            response = client.get("/health")

        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "healthy"  # socket.gethostname 失敗不會影響健康檢查
        assert payload["container_id"] is None  # container_id 會是 None
        assert payload["terminal_service"]["status"] == "starting"

    finally:
        # 恢復原始的 socket.gethostname
        socket.gethostname = original_gethostname


def test_hl_005_database_operational_error(client):
    """HL-005 資料庫操作錯誤"""
    db_service = StubDatabaseService()

    # 設置一個工作區，但讓 commit 方法失敗
    workspace_id = "default-workspace"
    db_service.workspaces[workspace_id] = {
        "id": workspace_id,
        "runtime_status": "stopped",
        "runtime_container_id": "old_container_id",
        "runtime_last_seen": None,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    db_service.should_fail = True  # 讓 commit 失敗

    # 模擬 get_db 依賴
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
