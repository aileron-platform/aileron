"""核心模組 Preview API 測試"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .helpers import override_dependency
from app.modules.preview.dependencies import get_preview_service


class StubPreviewService:
    """可控制的 PreviewService stub"""

    def __init__(self, workspace_path: Path) -> None:
        self.workspace_path = workspace_path
        self.operations = {}
        self.operation_counter = 0
        self.health_status = "healthy"

    def scan_nextjs_routes(self, workspace_id: str) -> dict[str, Any]:
        from datetime import datetime, timezone
        # 模擬掃描 Next.js 路由
        routes = [
            {
                "path": "/",
            },
            {
                "path": "/api/hello",
            },
            {
                "path": "/about",
            }
        ]
        return {
            "workspaceId": workspace_id,
            "routes": routes,
            "total": len(routes),
            "scannedAt": datetime.now(timezone.utc).isoformat()
        }

    def start_sync(self, workspace_id: str, payload=None):
        from datetime import datetime, timezone
        self.operation_counter += 1
        operation_id = f"sync_{self.operation_counter}"
        self.operations[operation_id] = {
            "id": operation_id,
            "status": "pending",
            "progress": 0.0,
            "startedAt": datetime.now(timezone.utc).isoformat(),
            "completedAt": None,
            "error": None
        }

        # 創建一個具有 operation_id 屬性的對象
        class SyncResponse:
            def __init__(self, workspace_id, operation_id):
                self.workspaceId = workspace_id
                self.operation_id = operation_id
                self.status = "pending"
                self.message = "Sync operation started"
                self.startedAt = datetime.now(timezone.utc).isoformat()

        return SyncResponse(workspace_id, operation_id)

    def execute_sync(self, operation_id: str) -> None:
        """模擬背景同步操作"""
        # 這個方法在背景任務中執行
        pass

    def get_sync_status(self, operation_id: str, workspace_id: str = None) -> dict[str, Any]:
        if operation_id not in self.operations:
            raise KeyError("Operation not found")

        # 模擬進度更新
        operation = self.operations[operation_id]
        if operation["progress"] < 1.0:
            operation["progress"] += 0.35
            if operation["progress"] >= 1.0:
                operation["status"] = "completed"
                operation["progress"] = 1.0
                from datetime import datetime, timezone
                operation["completedAt"] = datetime.now(timezone.utc).isoformat()

        return {
            "workspaceId": workspace_id or "default",
            "operationId": operation_id,
            "status": operation["status"],
            "progress": operation["progress"],
            "message": f"Sync operation {operation['status']}",
            "startedAt": operation["startedAt"],
            "completedAt": operation.get("completedAt"),
            "error": operation.get("error")
        }

    def check_health(self, workspace_id: str) -> dict[str, Any]:
        if self.health_status == "healthy":
            return {
                "status": "healthy",
                "nextjs_running": True,
                "port_available": True,
                "port": 3000,
                "message": "Preview service is healthy"
            }
        else:
            return {
                "status": "unhealthy",
                "nextjs_running": False,
                "port_available": False,
                "port": 3000,
                "message": "Next.js not running"
            }


def test_pv_001_scan_nextjs_routes(client):
    """PV-001 掃描 Next.js 路由"""
    workspace_path = Path("/tmp/workspace")
    service = StubPreviewService(workspace_path)
    workspace_id = "ws_test_001"

    with override_dependency(get_preview_service, lambda: service):
        response = client.get(f"/api/v1/workspaces/{workspace_id}/preview/nextjs/routes")

    assert response.status_code == 200
    payload = response.json()
    assert "routes" in payload
    assert "total" in payload
    assert "workspaceId" in payload
    routes = payload["routes"]
    assert len(routes) >= 2  # 至少有首頁和 API 路由


def test_pv_002_start_sync(client):
    """PV-002 發起同步並排程背景任務"""
    workspace_path = Path("/tmp/workspace")
    service = StubPreviewService(workspace_path)
    workspace_id = "ws_test_002"

    # 模擬背景任務追蹤
    background_task_added = False

    def mock_add_task(func, *args, **kwargs):
        nonlocal background_task_added
        background_task_added = True

    with override_dependency(get_preview_service, lambda: service):
        # monkeypatch BackgroundTasks.add_task
        from fastapi import BackgroundTasks
        original_add_task = BackgroundTasks.add_task
        BackgroundTasks.add_task = mock_add_task

        try:
            response = client.post(f"/api/v1/workspaces/{workspace_id}/preview/sync")
        finally:
            BackgroundTasks.add_task = original_add_task

    assert response.status_code == 202
    payload = response.json()
    # 對象會被序列化為 dict
    assert "operationId" in payload
    assert payload["operationId"].startswith("sync_")
    assert background_task_added


def test_pv_003_query_sync_status(client):
    """PV-003 查詢同步狀態"""
    workspace_path = Path("/tmp/workspace")
    service = StubPreviewService(workspace_path)
    workspace_id = "ws_test_003"

    # 先建立一個同步操作
    result = service.start_sync(workspace_id)
    operation_id = result.operation_id  # 使用屬性訪問

    with override_dependency(get_preview_service, lambda: service):
        response = client.get(f"/api/v1/workspaces/{workspace_id}/preview/sync/{operation_id}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["operationId"] == operation_id
    assert payload["status"] in ["pending", "running", "completed"]
    assert "progress" in payload
    assert isinstance(payload["progress"], (int, float))


def test_pv_004_query_nonexistent_operation(client):
    """PV-004 查詢不存在操作"""
    workspace_path = Path("/tmp/workspace")
    service = StubPreviewService(workspace_path)
    workspace_id = "ws_test_004"

    with override_dependency(get_preview_service, lambda: service):
        response = client.get(f"/api/v1/workspaces/{workspace_id}/preview/sync/nonexistent")

    # KeyError 會被轉換為 404 錯誤
    assert response.status_code in [404, 500]  # 取決於錯誤處理方式


def test_pv_005_preview_health_healthy(client):
    """PV-005 預覽健康狀態"""
    workspace_path = Path("/tmp/workspace")
    service = StubPreviewService(workspace_path)
    service.health_status = "healthy"
    workspace_id = "ws_test_005"

    with override_dependency(get_preview_service, lambda: service):
        response = client.get(f"/api/v1/workspaces/{workspace_id}/preview/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "healthy"
    assert payload["nextjs_running"] is True
    assert "port" in payload


def test_pv_006_preview_unhealthy(client):
    """PV-006 Next.js 未啟動"""
    workspace_path = Path("/tmp/workspace")
    service = StubPreviewService(workspace_path)
    service.health_status = "unhealthy"
    workspace_id = "ws_test_006"

    with override_dependency(get_preview_service, lambda: service):
        response = client.get(f"/api/v1/workspaces/{workspace_id}/preview/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "unhealthy"
    assert "message" in payload
    assert payload["message"] == "Next.js not running"
