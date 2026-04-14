"""健康檢查 API 整合測試 (簡化版)"""

from __future__ import annotations

import pytest
from fastapi import status


class TestHealthAPI:
    """健康檢查 API 測試案例"""

    @pytest.mark.integration
    def test_hc_001_health_check_success(self, test_app):
        """HC-001 健康檢查成功"""
        client, _ = test_app

        response = client.get("/health")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # 驗證回應結構
        assert "status" in data
        assert "timestamp" in data
        assert "version" in data
        assert "service" in data

        # 驗證基本欄位
        assert data["status"] == "healthy"
        assert isinstance(data["timestamp"], str)
        assert isinstance(data["version"], str)
        assert data["service"] == "workspace-manager"

    @pytest.mark.integration
    def test_hc_002_health_check_content_type(self, test_app):
        """HC-002 回應內容類型檢查"""
        client, _ = test_app

        response = client.get("/health")

        assert response.status_code == status.HTTP_200_OK
        assert response.headers["content-type"] == "application/json"

        # 驗證可以正確解析 JSON
        data = response.json()
        assert isinstance(data, dict)

    @pytest.mark.integration
    def test_hc_003_health_check_response_time(self, test_app):
        """HC-003 健康檢查回應時間"""
        client, _ = test_app

        import time
        start_time = time.time()
        response = client.get("/health")
        end_time = time.time()

        response_time = (end_time - start_time) * 1000  # 轉換為毫秒

        assert response.status_code == status.HTTP_200_OK
        # 健康檢查應該快速回應（小於 1 秒）
        assert response_time < 1000, f"健康檢查回應時間過長: {response_time}ms"

    @pytest.mark.integration
    def test_hc_004_health_check_with_headers(self, test_app):
        """HC-004 帶請求標頭的健康檢查"""
        client, _ = test_app

        headers = {
            "User-Agent": "Test-Agent/1.0",
            "X-Request-ID": "test-request-123",
        }

        response = client.get("/health", headers=headers)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # 健康檢查應正常運作，不受標頭影響
        assert data["status"] == "healthy"

    @pytest.mark.integration
    def test_hc_005_health_check_method_not_allowed(self, test_app):
        """HC-005 錯誤方法處理"""
        client, _ = test_app

        # 測試無效的請求方法
        response = client.post("/health")

        # 健康檢查端點不支援 POST
        assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

    @pytest.mark.integration
    def test_hc_006_health_check_concurrent_requests(self, test_app):
        """HC-006 併發請求健康檢查"""
        import threading
        import time

        client, _ = test_app
        results = []
        errors = []

        def make_request():
            try:
                response = client.get("/health")
                results.append(response)
            except Exception as e:
                errors.append(e)

        # 創建多個併發請求
        threads = []
        for _ in range(5):
            thread = threading.Thread(target=make_request)
            threads.append(thread)

        # 同時啟動所有線程
        start_time = time.time()
        for thread in threads:
            thread.start()

        # 等待所有線程完成
        for thread in threads:
            thread.join()
        end_time = time.time()

        # 驗證結果
        assert len(errors) == 0, f"併發請求發生錯誤: {errors}"
        assert len(results) == 5, "應該收到 5 個回應"

        # 所有回應都應該成功
        for response in results:
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["status"] == "healthy"

        # 併發處理時間應該合理
        total_time = (end_time - start_time) * 1000
        assert total_time < 3000, f"併發處理時間過長: {total_time}ms"


@pytest.fixture
def mock_responses():
    """Mock 回應 fixture"""
    return None  # 簡化版本不需要 mock