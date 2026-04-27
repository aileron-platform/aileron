"""健康Check API 整合Testing (簡化版)"""

from __future__ import annotations

from unittest.mock import Mock, patch

import httpx
import pytest
from fastapi import status


class TestHealthAPI:
    """健康Check API TestingCase"""

    @pytest.mark.integration
    def test_hc_001_health_check_success(self, test_app):
        """HC-001 健康CheckSuccessfully"""
        client, _ = test_app

        response = client.get("/health")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # VerifyingBack應Structure
        assert "status" in data
        assert "timestamp" in data
        assert "version" in data
        assert "service" in data

        # VerifyingBasic欄位
        assert data["status"] == "healthy"
        assert isinstance(data["timestamp"], str)
        assert isinstance(data["version"], str)
        assert data["service"] == "workspace-manager"

    @pytest.mark.integration
    def test_hc_002_health_check_content_type(self, test_app):
        """HC-002 Back應Within容TypeCheck"""
        client, _ = test_app

        response = client.get("/health")

        assert response.status_code == status.HTTP_200_OK
        assert response.headers["content-type"] == "application/json"

        # Verifying可以Correctly解析 JSON
        data = response.json()
        assert isinstance(data, dict)

    @pytest.mark.integration
    def test_hc_003_health_check_response_time(self, test_app):
        """HC-003 健康CheckBack應Time"""
        client, _ = test_app

        import time
        start_time = time.time()
        response = client.get("/health")
        end_time = time.time()

        response_time = (end_time - start_time) * 1000  # Convert為毫Second

        assert response.status_code == status.HTTP_200_OK
        # 健康Check應該Fast速Back應（SmallAt 1 Second）
        assert response_time < 1000, f"健康CheckBack應Time過Long: {response_time}ms"

    @pytest.mark.integration
    def test_hc_004_health_check_with_headers(self, test_app):
        """HC-004 BringingRequest標頭的健康Check"""
        client, _ = test_app

        headers = {
            "User-Agent": "Test-Agent/1.0",
            "X-Request-ID": "test-request-123",
        }

        response = client.get("/health", headers=headers)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # 健康Check應NormalOperate，不受標頭Impact
        assert data["status"] == "healthy"

    @pytest.mark.integration
    def test_hc_005_health_check_method_not_allowed(self, test_app):
        """HC-005 IncorrectlyMethodHandle"""
        client, _ = test_app

        # TestingInvalid的RequestMethod
        response = client.post("/health")

        # 健康Check端Point不Supporting POST
        assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

    @pytest.mark.integration
    def test_hc_006_health_check_concurrent_requests(self, test_app):
        """HC-006 併發Request健康Check"""
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

        # 創建Many個併發Request
        threads = []
        for _ in range(5):
            thread = threading.Thread(target=make_request)
            threads.append(thread)

        # WhileInitiatingAllLine程
        start_time = time.time()
        for thread in threads:
            thread.start()

        # WaitingAllLine程Complete
        for thread in threads:
            thread.join()
        end_time = time.time()

        # VerifyingResult
        assert len(errors) == 0, f"併發Request發生Incorrectly: {errors}"
        assert len(results) == 5, "應該收To 5 個Back應"

        # AllBack應都應該Successfully
        for response in results:
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["status"] == "healthy"

        # 併發HandleTime應該合理
        total_time = (end_time - start_time) * 1000
        assert total_time < 3000, f"併發HandleTime過Long: {total_time}ms"

    @pytest.mark.integration
    def test_hc_007_keycloak_health_skipped_is_localized(self, test_app):
        client, _ = test_app

        with patch(
            "app.routers.health.get_keycloak_config",
            return_value=Mock(enabled=False),
        ):
            en_response = client.get("/health/keycloak")
            assert en_response.status_code == status.HTTP_200_OK
            assert en_response.json()["message"] == "Authentication is not enabled"

        client.headers.update({"Accept-Language": "zh-TW", "X-Language": "zh-TW"})
        with patch(
            "app.routers.health.get_keycloak_config",
            return_value=Mock(enabled=False),
        ):
            zh_response = client.get("/health/keycloak")
            assert zh_response.status_code == status.HTTP_200_OK
            assert zh_response.json()["message"] == "未Enabled認證"

    @pytest.mark.integration
    def test_hc_008_keycloak_health_http_error_uses_simple_message(self, test_app):
        client, _ = test_app

        class _FailingAsyncClient:
            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return False

            async def get(self, url):
                raise httpx.HTTPError("boom")

        mock_config = Mock(
            enabled=True,
            server_url="https://keycloak.example.com/realms/test",
            realm="test",
        )

        with patch("app.routers.health.get_keycloak_config", return_value=mock_config), patch(
            "app.routers.health.httpx.AsyncClient",
            return_value=_FailingAsyncClient(),
        ):
            en_response = client.get("/health/keycloak")
            assert en_response.status_code == status.HTTP_200_OK
            assert en_response.json()["message"] == "Keycloak connection failed"

        client.headers.update({"Accept-Language": "zh-TW", "X-Language": "zh-TW"})
        with patch("app.routers.health.get_keycloak_config", return_value=mock_config), patch(
            "app.routers.health.httpx.AsyncClient",
            return_value=_FailingAsyncClient(),
        ):
            zh_response = client.get("/health/keycloak")
            assert zh_response.status_code == status.HTTP_200_OK
            assert zh_response.json()["message"] == "Keycloak 連LineUnsuccessfully"


@pytest.fixture
def mock_responses():
    """Mock Back應 fixture"""
    return None  # 簡化版本不Needing mock
