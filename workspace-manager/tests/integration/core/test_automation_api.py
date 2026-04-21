"""自動化任務 API 整合測試。"""

from __future__ import annotations

import uuid
from unittest.mock import patch

import pytest
from fastapi import status

from app.services.automation_service import JobDispatchError, JobNotRunnableError


def _build_job_payload(user_id: str, **overrides):
    payload = {
        "name": "Test Automation Task",
        "description": "A test automation task",
        "owner": "test-owner",
        "userId": user_id,
        "workspaceId": str(uuid.uuid4()),
        "prompt": "執行自動化測試",
        "status": "active",
        "trigger": "manual",
        "schedule": "0 2 * * *",
        "tags": ["test"],
        "notifications": {
            "email": False,
            "slack": False,
            "webhook": False,
        },
        "metadata": {},
    }
    payload.update(overrides)
    return payload


class TestAutomationAPI:
    """僅保留不依賴外部 broker 的自動化 API 測試。"""

    @pytest.mark.integration
    def test_automation_001_create_task(self, authenticated_client):
        client, user = authenticated_client

        response = client.post(
            "/api/v1/automation/jobs",
            json=_build_job_payload(str(user.id)),
        )

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["name"] == "Test Automation Task"
        assert data["userId"] == str(user.id)
        assert data["status"] == "active"

    @pytest.mark.integration
    def test_automation_002_list_tasks(self, authenticated_client):
        client, _ = authenticated_client

        response = client.get("/api/v1/automation/jobs")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert isinstance(data["items"], list)
        assert isinstance(data["total"], int)

    @pytest.mark.integration
    def test_automation_003_get_task(self, authenticated_client):
        client, user = authenticated_client

        create_response = client.post(
            "/api/v1/automation/jobs",
            json=_build_job_payload(str(user.id), name="Task to Get"),
        )
        assert create_response.status_code == status.HTTP_201_CREATED
        job_id = create_response.json()["id"]

        response = client.get(f"/api/v1/automation/jobs/{job_id}")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["id"] == job_id
        assert data["name"] == "Task to Get"

    @pytest.mark.integration
    def test_automation_004_update_job_status(self, authenticated_client):
        client, user = authenticated_client

        create_response = client.post(
            "/api/v1/automation/jobs",
            json=_build_job_payload(str(user.id), name="Task for Status Update"),
        )
        assert create_response.status_code == status.HTTP_201_CREATED
        job_id = create_response.json()["id"]

        response = client.post(
            f"/api/v1/automation/jobs/{job_id}/status",
            json={"status": "paused"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["id"] == job_id
        assert data["status"] == "paused"

    @pytest.mark.integration
    def test_automation_005_create_execution(self, authenticated_client):
        client, user = authenticated_client

        create_response = client.post(
            "/api/v1/automation/jobs",
            json=_build_job_payload(str(user.id), name="Task for Execution Record"),
        )
        assert create_response.status_code == status.HTTP_201_CREATED
        job_id = create_response.json()["id"]

        response = client.post(
            f"/api/v1/automation/jobs/{job_id}/executions",
            json={
                "status": "success",
                "trigger": "manual",
                "summary": "手動執行成功",
                "duration": 120,
                "sessionId": str(uuid.uuid4()),
                "errorMessage": None,
            },
        )

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["jobId"] == job_id
        assert data["status"] == "success"
        assert data["duration"] == 120

    @pytest.mark.integration
    def test_automation_006_list_executions(self, authenticated_client):
        client, _ = authenticated_client

        response = client.get("/api/v1/automation/executions")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert isinstance(data["items"], list)
        assert isinstance(data["total"], int)

    @pytest.mark.integration
    def test_automation_007_get_metrics(self, authenticated_client):
        client, _ = authenticated_client

        response = client.get("/api/v1/automation/metrics")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        for field in [
            "activeCount",
            "pausedCount",
            "failedCount",
            "draftCount",
            "successRate",
            "runningExecutions",
            "queuedExecutions",
            "averageDuration",
        ]:
            assert field in data

    @pytest.mark.integration
    def test_automation_008_get_calendar(self, authenticated_client):
        client, _ = authenticated_client

        response = client.get("/api/v1/automation/calendar")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "items" in data
        assert "total" in data
        assert isinstance(data["items"], list)
        assert isinstance(data["total"], int)

    @pytest.mark.integration
    def test_automation_009_update_job(self, authenticated_client):
        client, user = authenticated_client

        create_response = client.post(
            "/api/v1/automation/jobs",
            json=_build_job_payload(str(user.id), name="Task to Update"),
        )
        assert create_response.status_code == status.HTTP_201_CREATED
        job_id = create_response.json()["id"]

        response = client.patch(
            f"/api/v1/automation/jobs/{job_id}",
            json={
                "name": "Updated Task Name",
                "description": "Updated description",
                "prompt": "更新後的提示",
                "schedule": "0 9 * * *",
                "tags": ["test", "updated"],
            },
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["id"] == job_id
        assert data["name"] == "Updated Task Name"
        assert data["description"] == "Updated description"
        assert "updated" in data["tags"]

    @pytest.mark.integration
    def test_automation_010_update_job_invalid_data(self, authenticated_client):
        client, user = authenticated_client

        create_response = client.post(
            "/api/v1/automation/jobs",
            json=_build_job_payload(str(user.id), name="Task for Invalid Update"),
        )
        assert create_response.status_code == status.HTTP_201_CREATED
        job_id = create_response.json()["id"]

        response = client.patch(
            f"/api/v1/automation/jobs/{job_id}",
            json={
                "status": "invalid_status",
                "trigger": "invalid_trigger",
            },
        )

        assert response.status_code in {
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_422_UNPROCESSABLE_ENTITY,
        }

    @pytest.mark.integration
    def test_automation_011_delete_job(self, authenticated_client):
        client, user = authenticated_client

        create_response = client.post(
            "/api/v1/automation/jobs",
            json=_build_job_payload(str(user.id), name="Task to Delete"),
        )
        assert create_response.status_code == status.HTTP_201_CREATED
        job_id = create_response.json()["id"]

        response = client.delete(f"/api/v1/automation/jobs/{job_id}")

        assert response.status_code == status.HTTP_204_NO_CONTENT
        get_response = client.get(f"/api/v1/automation/jobs/{job_id}")
        assert get_response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.integration
    def test_automation_012_delete_job_not_found(self, authenticated_client):
        client, _ = authenticated_client

        response = client.delete(f"/api/v1/automation/jobs/{uuid.uuid4()}")

        assert response.status_code == status.HTTP_404_NOT_FOUND

    @pytest.mark.integration
    def test_automation_013_execute_job_error_is_localized(self, authenticated_client):
        client, _ = authenticated_client
        job_id = str(uuid.uuid4())

        with patch(
            "app.routers.automation.AutomationService.execute_task_now",
            side_effect=JobNotRunnableError(
                f"自動化任務 {job_id} 目前狀態為 archived，不可執行",
                code="AUTOMATION_JOB_NOT_RUNNABLE",
                params={"jobId": job_id, "status": "archived"},
            ),
        ):
            en_response = client.post(f"/api/v1/automation/jobs/{job_id}/execute")
            assert en_response.status_code == status.HTTP_400_BAD_REQUEST
            assert en_response.json()["detail"] == f"Job {job_id} is in status archived and cannot be executed"

        client.headers.update({"Accept-Language": "zh-TW", "X-Language": "zh-TW"})
        with patch(
            "app.routers.automation.AutomationService.execute_task_now",
            side_effect=JobDispatchError("無法派送自動化任務至 Celery", code="AUTOMATION_DISPATCH_FAILED"),
        ):
            zh_response = client.post(f"/api/v1/automation/jobs/{job_id}/execute")
            assert zh_response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
            assert zh_response.json()["detail"] == "無法將自動化任務派送到 Celery"

    @pytest.mark.integration
    def test_automation_014_queue_and_cancel_generic_errors_are_localized(self, authenticated_client):
        client, _ = authenticated_client

        with patch(
            "app.routers.automation.AutomationService.get_workspace_queue",
            side_effect=RuntimeError("queue boom"),
        ):
            en_response = client.get(f"/api/v1/automation/workspaces/{uuid.uuid4()}/queue")
            assert en_response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
            assert en_response.json()["detail"] == "Failed to fetch workspace queue"

        client.headers.update({"Accept-Language": "zh-TW", "X-Language": "zh-TW"})
        with patch(
            "app.routers.automation.AutomationService.cancel_execution",
            side_effect=RuntimeError("cancel boom"),
        ):
            zh_response = client.post(f"/api/v1/automation/executions/{uuid.uuid4()}/cancel")
            assert zh_response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
            assert zh_response.json()["detail"] == "取消排隊任務失敗"
