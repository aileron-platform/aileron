"""預覽模組服務 - 透過 HTTP 遠端控制 Next.js 獨立容器"""

from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin

import httpx

from .models import (
    NextJsRoute,
    NextJsRoutesResponse,
    PreviewSyncRequest,
    PreviewSyncResponse,
    PreviewSyncStatusResponse,
)

logger = logging.getLogger(__name__)

# Next.js 容器管理 API URL（由 workspace-manager 注入環境變數）
NEXTJS_API_URL = os.getenv("NEXTJS_API_URL", "http://localhost:3013")
NEXTJS_INTERNAL_URL = os.getenv("NEXTJS_INTERNAL_URL", "http://localhost:3003")


class PreviewService:
    """管理預覽同步與健康狀態（透過遠端 HTTP 呼叫 Next.js 容器）"""

    def __init__(self) -> None:
        self._workspace_base = Path("/workspace")
        self._nextjs_api_url = NEXTJS_API_URL
        self._nextjs_url = NEXTJS_INTERNAL_URL
        # 儲存同步操作狀態
        self._sync_operations: dict[str, PreviewSyncStatusResponse] = {}

    def scan_nextjs_routes(self, workspace_id: str) -> NextJsRoutesResponse:
        """從 Next.js 容器的管理 API 取得路由列表"""
        try:
            with httpx.Client(timeout=10.0) as client:
                resp = client.get(f"{self._nextjs_api_url}/routes")
                if resp.status_code == 200:
                    data = resp.json()
                    routes = [NextJsRoute(path=r["path"]) for r in data.get("routes", [])]
                    return NextJsRoutesResponse(
                        workspaceId=workspace_id,
                        routes=routes,
                        total=len(routes),
                        scannedAt=datetime.now(timezone.utc),
                    )
        except Exception as e:
            logger.warning(f"從 Next.js 容器取得路由失敗，回退到本地掃描: {e}")

        # 回退：從本地 /workspace/route.json 讀取
        return self._scan_routes_local(workspace_id)

    def _scan_routes_local(self, workspace_id: str) -> NextJsRoutesResponse:
        """回退方法：從本地檔案系統讀取路由"""
        route_json_path = self._workspace_base / "route.json"

        if not route_json_path.exists():
            return NextJsRoutesResponse(
                workspaceId=workspace_id,
                routes=[],
                total=0,
                scannedAt=datetime.now(timezone.utc),
            )

        try:
            with open(route_json_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            routes: list[NextJsRoute] = []
            for route_data in data.get("routes", []):
                path = route_data.get("path", "")
                if not path:
                    continue
                routes.append(NextJsRoute(path=path))

            return NextJsRoutesResponse(
                workspaceId=workspace_id,
                routes=routes,
                total=len(routes),
                scannedAt=datetime.now(timezone.utc),
            )
        except Exception as e:
            logger.error(f"讀取 route.json 失敗: {e}")
            return NextJsRoutesResponse(
                workspaceId=workspace_id,
                routes=[],
                total=0,
                scannedAt=datetime.now(timezone.utc),
            )

    def start_sync(
        self, workspace_id: str, payload: PreviewSyncRequest
    ) -> PreviewSyncResponse:
        """啟動預覽同步操作"""
        operation_id = f"sync-{uuid.uuid4().hex[:8]}"
        started_at = datetime.now(timezone.utc)

        # 創建操作狀態
        status = PreviewSyncStatusResponse(
            workspaceId=workspace_id,
            operationId=operation_id,
            status="pending",
            progress=0.0,
            message="準備重啟 Next.js 服務...",
            startedAt=started_at,
        )
        self._sync_operations[operation_id] = status

        logger.info(
            f"啟動預覽同步操作: {operation_id}, workspace: {workspace_id}, force: {payload.force}"
        )

        return PreviewSyncResponse(
            workspaceId=workspace_id,
            operationId=operation_id,
            status="pending",
            message="正在重啟 Next.js 服務...",
            startedAt=started_at,
        )

    def execute_sync(self, operation_id: str) -> None:
        """
        執行同步操作 (在背景任務中執行)

        透過 HTTP 呼叫 Next.js 容器的管理 API 重啟 dev server
        """
        if operation_id not in self._sync_operations:
            logger.error(f"找不到同步操作: {operation_id}")
            return

        status = self._sync_operations[operation_id]

        try:
            status.status = "running"
            status.progress = 0.3
            status.message = "正在通知 Next.js 容器重啟..."
            logger.info(f"[{operation_id}] 呼叫 Next.js 容器管理 API 重啟")

            # 呼叫 Next.js 容器的 restart API
            with httpx.Client(timeout=30.0) as client:
                resp = client.post(f"{self._nextjs_api_url}/restart")

                if resp.status_code == 200:
                    data = resp.json()
                    logger.info(f"[{operation_id}] Next.js 容器回應: {data}")
                    status.progress = 0.5
                    status.message = data.get("message", "Next.js 重啟中...")
                else:
                    logger.warning(f"[{operation_id}] Next.js 容器回應異常: {resp.status_code}")

            # 等待 Next.js 服務就緒
            status.progress = 0.7
            status.message = "等待 Next.js 服務啟動..."
            logger.info(f"[{operation_id}] 等待 Next.js 服務就緒...")

            self._wait_for_nextjs_ready(operation_id)

            status.status = "completed"
            status.progress = 1.0
            status.message = "同步完成"
            status.completed_at = datetime.now(timezone.utc)
            logger.info(f"[{operation_id}] 同步操作完成")

        except Exception as e:
            logger.error(f"[{operation_id}] 同步操作失敗: {e}", exc_info=True)
            status.status = "failed"
            status.message = f"同步失敗: {str(e)}"
            status.error = str(e)
            status.completed_at = datetime.now(timezone.utc)

    def _wait_for_nextjs_ready(self, operation_id: str) -> None:
        """等待 Next.js 容器的健康檢查回報 healthy"""
        import time

        max_wait = 60
        start_time = time.time()

        # 使用單一 Client 實例避免每次輪詢都建立新連線
        with httpx.Client(timeout=5.0) as client:
            while time.time() - start_time < max_wait:
                try:
                    resp = client.get(f"{self._nextjs_api_url}/health")
                    if resp.status_code == 200:
                        data = resp.json()
                        if data.get("status") == "healthy":
                            logger.info(f"[{operation_id}] Next.js 服務已就緒")
                            return
                        logger.debug(f"[{operation_id}] Next.js 狀態: {data.get('status')}")
                except Exception as e:
                    logger.debug(f"[{operation_id}] 健康檢查失敗: {e}")

                time.sleep(2)

        logger.warning(f"[{operation_id}] 等待 Next.js 就緒超時")

    def get_sync_status(self, operation_id: str) -> PreviewSyncStatusResponse:
        """取得同步操作狀態"""
        if operation_id not in self._sync_operations:
            raise ValueError(f"找不到同步操作: {operation_id}")
        return self._sync_operations[operation_id]

    def check_health(self, workspace_id: str) -> dict:
        """
        檢查預覽服務健康狀態（透過 Next.js 容器管理 API）

        返回:
        - status: "healthy" | "unhealthy" | "standby" | "starting" | "checking"
        - nextjs_running: Next.js 服務是否運行
        - port_available: 端口是否可用
        - message: 狀態訊息
        """
        try:
            with httpx.Client(timeout=5.0) as client:
                resp = client.get(f"{self._nextjs_api_url}/health")
                if resp.status_code == 200:
                    data = resp.json()
                    return {
                        "status": data.get("status", "checking"),
                        "nextjs_running": data.get("nextjs_running", False),
                        "port_available": data.get("port_available", False),
                        "message": data.get("message", ""),
                        "source": data.get("source"),
                    }
        except httpx.ConnectError:
            logger.debug("無法連接到 Next.js 容器管理 API")
            return {
                "status": "unhealthy",
                "nextjs_running": False,
                "port_available": False,
                "message": "Next.js 容器未運行或無法連接",
            }
        except Exception as e:
            logger.error(f"檢查 Next.js 健康狀態失敗: {e}", exc_info=True)
            return {
                "status": "unhealthy",
                "nextjs_running": False,
                "port_available": False,
                "message": f"檢查失敗: {str(e)}",
            }
