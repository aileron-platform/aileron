"""AutomationService 單元測試"""

from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import MagicMock, Mock, patch
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from app.db import models as db_models
from app.models.automation import (
    JobCreateRequest,
    JobExecutionStatus,
    JobNotificationSettings,
    JobStatusUpdate,
    JobTrigger,
    JobUpdateRequest,
)
from app.services.automation_service import (
    AutomationService,
    JobDispatchError,
    JobNotFoundError,
    JobNotRunnableError,
)
from app.utils.datetime_utils import utcnow


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def db_session():
    """Mock 資料庫 Session"""
    session = MagicMock(spec=Session)
    session.execute = MagicMock()
    session.add = MagicMock()
    session.commit = MagicMock()
    session.refresh = MagicMock()
    session.delete = MagicMock()
    session.get = MagicMock()
    return session


@pytest.fixture
def automation_service(db_session):
    """AutomationService 實例"""
    return AutomationService(db=db_session)


@pytest.fixture
def sample_job_record():
    """範例自動化任務記錄"""
    now = utcnow()
    return db_models.AutomationJob(
        id="job-123",
        name="Test Job",
        description="Test Description",
        owner="test_owner",
        creator_user_id="user-123",
        workspace_id="ws-123",
        prompt="Test prompt",
        status="active",
        trigger="cron",
        schedule="0 0 * * *",
        tags=["test", "automation"],
        notifications={},
        task_metadata={},
        webhook_api_key=None,
        next_run_at=now + timedelta(days=1),
        created_at=now,
        updated_at=now,
        last_run_at=None,
        success_count=0,
        failure_count=0,
        total_duration=0,
        last_duration=None,
    )


@pytest.fixture
def sample_workspace_record():
    """範例工作區記錄"""
    return db_models.Workspace(
        id="ws-123",
        name="Test Workspace",
        description="Test workspace",
        owner_id="user-123",
        created_at=utcnow(),
        updated_at=utcnow(),
    )


@pytest.fixture
def sample_execution_record():
    """範例執行記錄"""
    now = utcnow()
    return db_models.JobExecution(
        id="exec-123",
        job_id="job-123",
        status="queued",
        trigger="manual",
        summary="Test execution",
        started_at=None,
        finished_at=None,
        duration=None,
        session_id=None,
        error_message=None,
        execution_metadata={},
        queue_position=None,
        queued_at=now,
    )


@pytest.fixture
def sample_job_create_request():
    """範例任務創建請求"""
    return JobCreateRequest(
        name="Test Job",
        description="Test Description",
        owner="test_owner",
        user_id="user-123",
        workspace_id="ws-123",
        prompt="Test prompt",
        status="active",
        trigger="cron",
        schedule="0 0 * * *",
        tags=["test"],
        notifications=JobNotificationSettings(on_success=False, on_failure=False),
        metadata={},
    )


# ============================================================================
# 任務 CRUD 測試
# ============================================================================

@pytest.mark.unit
class TestAutomationJobCRUD:
    """自動化任務 CRUD 測試"""

    def test_list_tasks_success(self, automation_service, db_session, sample_job_record, sample_workspace_record):
        """測試：查詢任務列表成功"""
        # Arrange
        mock_result = MagicMock()
        mock_result.all.return_value = [(sample_job_record, sample_workspace_record)]
        db_session.execute.return_value = mock_result

        # Act
        result = automation_service.list_tasks()

        # Assert
        assert result.total == 1
        assert len(result.items) == 1
        assert result.items[0].id == "job-123"
        assert result.items[0].name == "Test Job"
        assert result.items[0].workspace_name == "Test Workspace"

    def test_list_tasks_empty(self, automation_service, db_session):
        """測試：查詢空任務列表"""
        # Arrange
        mock_result = MagicMock()
        mock_result.all.return_value = []
        db_session.execute.return_value = mock_result

        # Act
        result = automation_service.list_tasks()

        # Assert
        assert result.total == 0
        assert len(result.items) == 0

    def test_get_job_exists(self, automation_service, db_session, sample_job_record):
        """測試：查詢現有任務成功"""
        # Arrange
        db_session.get.return_value = sample_job_record

        # Act
        result = automation_service.get_job("job-123")

        # Assert
        assert result is not None
        assert result.id == "job-123"
        assert result.name == "Test Job"
        db_session.get.assert_called_once_with(db_models.AutomationJob, "job-123")

    def test_get_job_not_found(self, automation_service, db_session):
        """測試：查詢不存在的任務返回 None"""
        # Arrange
        db_session.get.return_value = None

        # Act
        result = automation_service.get_job("nonexistent-job")

        # Assert
        assert result is None

    def test_create_job_success(self, automation_service, db_session, sample_job_create_request):
        """測試：建立新任務成功"""
        # Arrange
        def mock_refresh(obj):
            if isinstance(obj, db_models.AutomationJob):
                # 確保所有必要的字段都有值
                if not hasattr(obj, 'success_count') or obj.success_count is None:
                    obj.success_count = 0
                if not hasattr(obj, 'failure_count') or obj.failure_count is None:
                    obj.failure_count = 0
                if not hasattr(obj, 'total_duration') or obj.total_duration is None:
                    obj.total_duration = 0

        db_session.refresh.side_effect = mock_refresh

        # Act
        result = automation_service.create_job(sample_job_create_request)

        # Assert
        assert result is not None
        assert result.name == "Test Job"
        db_session.add.assert_called_once()
        db_session.commit.assert_called_once()

    def test_update_job_success(self, automation_service, db_session, sample_job_record):
        """測試：更新任務成功"""
        # Arrange
        db_session.get.return_value = sample_job_record
        update_request = JobUpdateRequest(
            name="Updated Job Name",
            description="Updated Description",
        )

        # Act
        result = automation_service.update_job("job-123", update_request)

        # Assert
        assert result is not None
        assert result.name == "Updated Job Name"
        assert result.description == "Updated Description"
        db_session.commit.assert_called_once()

    def test_update_job_not_found(self, automation_service, db_session):
        """測試：更新不存在的任務返回 None"""
        # Arrange
        db_session.get.return_value = None
        update_request = JobUpdateRequest(name="Updated Job Name")

        # Act
        result = automation_service.update_job("nonexistent-job", update_request)

        # Assert
        assert result is None
        db_session.commit.assert_not_called()

    def test_update_job_with_schedule_update(self, automation_service, db_session, sample_job_record):
        """測試：更新任務排程時重新計算下次執行時間"""
        # Arrange
        db_session.get.return_value = sample_job_record
        update_request = JobUpdateRequest(
            schedule="0 12 * * *"  # 改為每天中午 12 點
        )

        # Act
        result = automation_service.update_job("job-123", update_request)

        # Assert
        assert result is not None
        assert result.schedule == "0 12 * * *"
        assert result.next_run_at is not None
        db_session.commit.assert_called_once()

    def test_delete_job_success(self, automation_service, db_session, sample_job_record):
        """測試：刪除任務成功"""
        # Arrange
        db_session.get.return_value = sample_job_record

        # Act
        automation_service.delete_job("job-123")

        # Assert
        db_session.delete.assert_called_once_with(sample_job_record)
        db_session.commit.assert_called_once()

    def test_delete_job_not_found(self, automation_service, db_session):
        """測試：刪除不存在的任務不報錯"""
        # Arrange
        db_session.get.return_value = None

        # Act
        automation_service.delete_job("nonexistent-job")

        # Assert
        db_session.delete.assert_not_called()
        db_session.commit.assert_not_called()

    def test_update_task_status_success(self, automation_service, db_session, sample_job_record):
        """測試：更新任務狀態成功"""
        # Arrange
        db_session.get.return_value = sample_job_record
        status_update = JobStatusUpdate(status="paused")

        # Act
        result = automation_service.update_task_status("job-123", status_update)

        # Assert
        assert result is not None
        assert result.status == "paused"
        db_session.commit.assert_called_once()


# ============================================================================
# 任務執行測試
# ============================================================================

@pytest.mark.unit
class TestAutomationJobExecution:
    """自動化任務執行測試"""

    def test_execute_task_now_active_job(self, automation_service, db_session, sample_job_record, sample_execution_record):
        """測試：立即執行活動任務成功"""
        # Arrange
        db_session.get.side_effect = [sample_job_record, sample_execution_record]

        with patch('app.tasks.run_automation_job') as mock_task:
            mock_task.apply_async.return_value = MagicMock(id="celery-task-123")

            # Act
            result = automation_service.execute_task_now("job-123")

            # Assert
            assert result is not None
            assert result.job_id == "job-123"
            assert result.trigger == "manual"
            mock_task.apply_async.assert_called_once()

    def test_execute_task_now_paused_job(self, automation_service, db_session, sample_job_record, sample_execution_record):
        """測試：立即執行暫停任務成功"""
        # Arrange
        sample_job_record.status = "paused"
        db_session.get.side_effect = [sample_job_record, sample_execution_record]

        with patch('app.tasks.run_automation_job') as mock_task:
            mock_task.apply_async.return_value = MagicMock(id="celery-task-123")

            # Act
            result = automation_service.execute_task_now("job-123")

            # Assert
            assert result is not None
            assert result.trigger == "manual"

    def test_execute_task_now_not_found(self, automation_service, db_session):
        """測試：執行不存在的任務拋出異常"""
        # Arrange
        db_session.get.return_value = None

        # Act & Assert
        with pytest.raises(JobNotFoundError, match="不存在"):
            automation_service.execute_task_now("nonexistent-job")

    def test_execute_task_now_invalid_status(self, automation_service, db_session, sample_job_record):
        """測試：執行草稿狀態任務拋出異常"""
        # Arrange
        sample_job_record.status = "draft"
        db_session.get.return_value = sample_job_record

        # Act & Assert
        with pytest.raises(JobNotRunnableError, match="不可執行"):
            automation_service.execute_task_now("job-123")

    @patch('app.tasks.run_automation_job')
    def test_execute_task_now_dispatch_failure(self, mock_task, automation_service, db_session, sample_job_record, sample_execution_record):
        """測試：任務派送失敗拋出異常"""
        # Arrange
        from celery.exceptions import CeleryError
        db_session.get.side_effect = [sample_job_record, sample_execution_record, sample_execution_record]
        mock_task.apply_async.side_effect = CeleryError("Connection failed")

        # Act & Assert
        with pytest.raises(JobDispatchError, match="無法派送"):
            automation_service.execute_task_now("job-123")


# ============================================================================
# 執行記錄管理測試
# ============================================================================

@pytest.mark.unit
class TestJobExecutionManagement:
    """執行記錄管理測試"""

    def test_list_executions_all(self, automation_service, db_session, sample_execution_record):
        """測試：查詢所有執行記錄"""
        # Arrange
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [sample_execution_record]
        db_session.execute.return_value = mock_result

        # Act
        result = automation_service.list_executions()

        # Assert
        assert result.total == 1
        assert len(result.items) == 1
        assert result.items[0].id == "exec-123"

    def test_list_executions_by_job_id(self, automation_service, db_session, sample_execution_record):
        """測試：按任務 ID 查詢執行記錄"""
        # Arrange
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [sample_execution_record]
        db_session.execute.return_value = mock_result

        # Act
        result = automation_service.list_executions(job_id="job-123")

        # Assert
        assert result.total == 1
        assert result.items[0].job_id == "job-123"

    def test_list_executions_with_limit(self, automation_service, db_session):
        """測試：查詢執行記錄帶限制"""
        # Arrange
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        db_session.execute.return_value = mock_result

        # Act
        result = automation_service.list_executions(limit=10)

        # Assert
        assert result.total == 0

    def test_get_execution_record_exists(self, automation_service, db_session, sample_execution_record):
        """測試：獲取存在的執行記錄"""
        # Arrange
        db_session.get.return_value = sample_execution_record

        # Act
        result = automation_service.get_execution_record("exec-123")

        # Assert
        assert result is not None
        assert result.id == "exec-123"

    def test_get_execution_record_not_found(self, automation_service, db_session):
        """測試：獲取不存在的執行記錄返回 None"""
        # Arrange
        db_session.get.return_value = None

        # Act
        result = automation_service.get_execution_record("nonexistent-exec")

        # Assert
        assert result is None

    def test_get_stuck_executions(self, automation_service, db_session):
        """測試：獲取卡住的執行記錄"""
        # Arrange
        stuck_time = utcnow() - timedelta(hours=2)
        stuck_execution = db_models.JobExecution(
            id="stuck-exec-123",
            job_id="job-123",
            status="running",
            trigger="cron",
            started_at=stuck_time,
            summary="Stuck execution",
        )
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [stuck_execution]
        db_session.execute.return_value = mock_result

        # Act
        result = automation_service.get_stuck_executions(timeout_minutes=60)

        # Assert
        assert len(result) == 1
        assert result[0].id == "stuck-exec-123"
        assert result[0].status == "running"

    def test_enqueue_execution_success(self, automation_service, db_session, sample_job_record):
        """測試：創建排隊執行記錄成功"""
        # Arrange
        db_session.get.return_value = sample_job_record

        def mock_refresh(obj):
            if isinstance(obj, db_models.JobExecution) and not hasattr(obj, '_refreshed'):
                obj._refreshed = True
                obj.id = "new-exec-123"

        db_session.refresh.side_effect = mock_refresh

        # Act
        result = automation_service.enqueue_execution(
            job_id="job-123",
            trigger="manual",
            summary="Test execution"
        )

        # Assert
        assert result is not None
        assert result.status == "queued"
        assert result.trigger == "manual"
        db_session.add.assert_called_once()
        db_session.commit.assert_called_once()

    def test_enqueue_execution_job_not_found(self, automation_service, db_session):
        """測試：為不存在的任務創建執行記錄返回 None"""
        # Arrange
        db_session.get.return_value = None

        # Act
        result = automation_service.enqueue_execution(
            job_id="nonexistent-job",
            trigger="manual"
        )

        # Assert
        assert result is None

    def test_mark_execution_running_success(self, automation_service, db_session, sample_execution_record):
        """測試：標記執行記錄為運行中成功"""
        # Arrange
        db_session.get.return_value = sample_execution_record

        # Act
        result = automation_service.mark_execution_running(
            execution_id="exec-123",
            summary="Running now"
        )

        # Assert
        assert result is not None
        assert result.status == "running"
        assert result.started_at is not None
        assert result.summary == "Running now"

    def test_mark_execution_running_not_found(self, automation_service, db_session):
        """測試：標記不存在的執行記錄為運行中返回 None"""
        # Arrange
        db_session.get.return_value = None

        # Act
        result = automation_service.mark_execution_running("nonexistent-exec")

        # Assert
        assert result is None

    def test_complete_execution_success(self, automation_service, db_session, sample_job_record):
        """測試：完成執行記錄成功"""
        # Arrange
        execution = db_models.JobExecution(
            id="exec-123",
            job_id="job-123",
            status="running",
            trigger="manual",
            started_at=utcnow() - timedelta(seconds=30),
            summary="Running",
        )
        db_session.get.side_effect = [execution, sample_job_record]

        # Act
        result = automation_service.complete_execution(
            execution_id="exec-123",
            status="success",
            summary="Completed successfully",
            session_id="session-123"
        )

        # Assert
        assert result is not None
        assert result.status == "success"
        assert result.finished_at is not None
        assert result.duration is not None
        assert result.session_id == "session-123"

    def test_complete_execution_with_error(self, automation_service, db_session, sample_job_record):
        """測試：完成執行記錄（失敗）"""
        # Arrange
        execution = db_models.JobExecution(
            id="exec-123",
            job_id="job-123",
            status="running",
            trigger="manual",
            started_at=utcnow() - timedelta(seconds=30),
            summary="Running",
        )
        db_session.get.side_effect = [execution, sample_job_record]

        # Act
        result = automation_service.complete_execution(
            execution_id="exec-123",
            status="failed",
            summary="Failed with error",
            error_message="Test error message"
        )

        # Assert
        assert result is not None
        assert result.status == "failed"
        assert result.error_message == "Test error message"

    def test_mark_execution_waiting_success(self, automation_service, db_session, sample_execution_record):
        """測試：標記執行記錄為等待狀態成功"""
        # Arrange
        db_session.get.return_value = sample_execution_record

        # Act
        result = automation_service.mark_execution_waiting(
            execution_id="exec-123",
            position=3,
            summary="Waiting in queue"
        )

        # Assert
        assert result is not None
        assert result.status == "waiting"
        assert result.queue_position == 3
        assert result.queued_at is not None

    def test_cancel_execution_success(self, automation_service, db_session, sample_job_record):
        """測試：取消排隊執行記錄成功"""
        # Arrange
        execution = db_models.JobExecution(
            id="exec-123",
            job_id="job-123",
            status="waiting",
            trigger="manual",
            queued_at=utcnow() - timedelta(seconds=10),
            queue_position=2,
            summary="Waiting",
        )
        db_session.get.side_effect = [execution, sample_job_record]

        with patch('app.utils.automation_queue.get_queue_manager') as mock_queue:
            mock_manager = MagicMock()
            mock_queue.return_value = mock_manager

            # Act
            result = automation_service.cancel_execution("exec-123")

            # Assert
            assert result["cancelled"] is True
            assert result["status"] == "cancelled"
            mock_manager.cancel.assert_called_once()

    def test_cancel_execution_not_waiting(self, automation_service, db_session, sample_execution_record):
        """測試：取消非等待狀態的執行記錄失敗"""
        # Arrange
        sample_execution_record.status = "running"
        db_session.get.return_value = sample_execution_record

        # Act
        result = automation_service.cancel_execution("exec-123")

        # Assert
        assert result["cancelled"] is False
        assert "只能取消 waiting 狀態" in result["message"]


# ============================================================================
# 任務排程測試
# ============================================================================

@pytest.mark.unit
class TestJobScheduling:
    """任務排程測試"""

    def test_list_due_tasks(self, automation_service, db_session, sample_job_record):
        """測試：查詢到期任務"""
        # Arrange
        sample_job_record.next_run_at = utcnow() - timedelta(minutes=5)
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [sample_job_record]
        db_session.execute.return_value = mock_result

        # Act
        result = automation_service.list_due_tasks(limit=10)

        # Assert
        assert len(result) == 1
        assert result[0].id == "job-123"

    def test_estimate_next_run_cron(self, automation_service):
        """測試：計算 cron 任務的下次執行時間"""
        # Act
        result = automation_service._estimate_next_run(
            trigger="cron",
            schedule="0 0 * * *",  # 每天午夜
            timezone="Asia/Taipei",
            reference=datetime(2025, 1, 1, 12, 0, 0)
        )

        # Assert
        assert result is not None
        # 下次執行應該是第二天的午夜
        assert result.hour == 16  # UTC 時間 (午夜 CST = 16:00 UTC 前一天)

    def test_estimate_next_run_manual(self, automation_service):
        """測試：manual 觸發器不計算下次執行時間"""
        # Act
        result = automation_service._estimate_next_run(
            trigger="manual",
            schedule="",
            timezone="Asia/Taipei"
        )

        # Assert
        assert result is None

    def test_estimate_next_run_invalid_cron(self, automation_service):
        """測試：無效的 cron 表達式返回 None"""
        # Act
        result = automation_service._estimate_next_run(
            trigger="cron",
            schedule="invalid cron",
            timezone="Asia/Taipei"
        )

        # Assert
        assert result is None


# ============================================================================
# 統計與指標測試
# ============================================================================

@pytest.mark.unit
class TestMetricsAndStatistics:
    """統計與指標測試"""

    def test_get_metrics(self, automation_service, db_session):
        """測試：獲取自動化指標"""
        # Arrange
        # Mock execution stats
        exec_stats_result = MagicMock()
        exec_stats_result.all.return_value = [("success", 10), ("failed", 2)]

        # Mock各種計數查詢
        count_results = [
            exec_stats_result,  # exec_stats
            MagicMock(scalar_one=lambda: 5),   # active_count
            MagicMock(scalar_one=lambda: 2),   # paused_count
            MagicMock(scalar_one=lambda: 0),   # draft_count
            MagicMock(scalar_one=lambda: 1),   # running_executions
            MagicMock(scalar_one=lambda: 3),   # queued_executions
            MagicMock(scalar_one=lambda: 36000),  # total_duration
        ]

        db_session.execute.side_effect = count_results

        # Act
        result = automation_service.get_metrics()

        # Assert
        assert result.active_count == 5
        assert result.paused_count == 2
        assert result.failed_count == 2
        assert result.draft_count == 0
        assert result.running_executions == 1
        assert result.queued_executions == 3
        assert result.success_rate > 0.8  # 10/(10+2) = 0.833
        assert result.average_duration == 3000  # 36000/12

    def test_get_calendar_events(self, automation_service, db_session, sample_job_record):
        """測試：獲取行事曆事件"""
        # Arrange
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [sample_job_record]
        db_session.execute.return_value = mock_result

        # Act
        result = automation_service.get_calendar_events()

        # Assert
        assert result.total == 1
        assert len(result.items) == 1
        assert result.items[0].job_id == "job-123"
        assert result.items[0].title == "Test Job"
        assert result.items[0].start is not None
        assert result.items[0].end is not None

    def test_get_workspace_queue(self, automation_service, db_session, sample_execution_record):
        """測試：獲取工作區佇列資訊"""
        # Arrange
        sample_execution_record.status = "waiting"
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [sample_execution_record]
        db_session.execute.return_value = mock_result

        with patch('app.utils.automation_queue.get_queue_manager') as mock_queue:
            mock_manager = MagicMock()
            mock_manager.list_queued_executions.return_value = ["exec-123"]
            mock_queue.return_value = mock_manager

            # Act
            result = automation_service.get_workspace_queue("ws-123")

            # Assert
            assert result["workspace_id"] == "ws-123"
            assert result["queue_length"] == 1
            assert len(result["executions"]) == 1


# ============================================================================
# 錯誤處理測試
# ============================================================================

@pytest.mark.unit
class TestErrorHandling:
    """錯誤處理測試"""

    def test_create_execution_with_all_statuses(self, automation_service, db_session, sample_job_record):
        """測試：創建不同狀態的執行記錄"""
        # Arrange
        db_session.get.return_value = sample_job_record

        def mock_refresh(obj):
            if isinstance(obj, db_models.JobExecution):
                obj.id = "new-exec-123"

        db_session.refresh.side_effect = mock_refresh

        # Test queued status
        result = automation_service.create_execution(
            job_id="job-123",
            status="queued",
            trigger="manual",
            summary="Queued execution"
        )
        assert result is not None
        assert result.status == "queued"

    def test_mark_execution_dispatch_failed(self, automation_service, db_session, sample_job_record):
        """測試：標記執行記錄派送失敗"""
        # Arrange
        execution = db_models.JobExecution(
            id="exec-123",
            job_id="job-123",
            status="queued",
            trigger="manual",
            summary="Queued",
        )
        execution.job = sample_job_record
        db_session.get.return_value = sample_job_record

        # Act
        automation_service._mark_execution_dispatch_failed(
            execution,
            error_message="Celery connection failed"
        )

        # Assert
        assert execution.status == "failed"
        assert execution.error_message == "Celery connection failed"
        assert execution.duration == 0

    def test_update_task_statistics_success(self, automation_service, db_session, sample_job_record):
        """測試：更新任務統計（成功）"""
        # Arrange
        execution = db_models.JobExecution(
            id="exec-123",
            job_id="job-123",
            status="success",
            trigger="manual",
            started_at=utcnow() - timedelta(seconds=30),
            finished_at=utcnow(),
            duration=30,
        )

        # Act
        automation_service._update_task_statistics(sample_job_record, execution)

        # Assert
        assert sample_job_record.success_count == 1
        assert sample_job_record.last_duration == 30
        assert sample_job_record.total_duration == 30

    def test_update_task_statistics_failure(self, automation_service, db_session, sample_job_record):
        """測試：更新任務統計（失敗）"""
        # Arrange
        execution = db_models.JobExecution(
            id="exec-123",
            job_id="job-123",
            status="failed",
            trigger="manual",
            started_at=utcnow() - timedelta(seconds=20),
            finished_at=utcnow(),
            duration=20,
        )

        # Act
        automation_service._update_task_statistics(sample_job_record, execution)

        # Assert
        assert sample_job_record.failure_count == 1
        assert sample_job_record.last_duration == 20

    def test_get_job_record_exists(self, automation_service, db_session, sample_job_record):
        """測試：get_job_record 獲取存在的任務記錄"""
        # Arrange
        db_session.get.return_value = sample_job_record

        # Act
        result = automation_service.get_job_record("job-123")

        # Assert
        assert result is not None
        assert result.id == "job-123"
        db_session.get.assert_called_once_with(db_models.AutomationJob, "job-123")

    def test_get_job_record_not_found(self, automation_service, db_session):
        """測試：get_job_record 任務不存在"""
        # Arrange
        db_session.get.return_value = None

        # Act
        result = automation_service.get_job_record("nonexistent")

        # Assert
        assert result is None
        db_session.get.assert_called_once_with(db_models.AutomationJob, "nonexistent")

    def test_update_job_with_all_field_types(self, automation_service, db_session, sample_job_record):
        """測試：update_job 更新所有特殊欄位類型"""
        # Arrange
        db_session.get.return_value = sample_job_record

        update_payload = JobUpdateRequest(
            notifications=JobNotificationSettings(on_success=True, on_failure=False),
            tags=["new", "tags"],
            metadata={"key": "value"},
            workspace_id="new-ws-456",
            user_id="new-user-456",
            webhook_api_key="new-api-key"
        )

        # Act
        result = automation_service.update_job("job-123", update_payload)

        # Assert
        assert result is not None
        assert sample_job_record.workspace_id == "new-ws-456"
        assert sample_job_record.creator_user_id == "new-user-456"
        assert sample_job_record.webhook_api_key == "new-api-key"

    def test_update_task_status_not_found(self, automation_service, db_session):
        """測試：update_task_status 任務不存在"""
        # Arrange
        db_session.get.return_value = None
        payload = JobStatusUpdate(status="paused")

        # Act
        result = automation_service.update_task_status("nonexistent", payload)

        # Assert
        assert result is None

    def test_execute_task_now_enqueue_failure(self, automation_service, db_session, sample_job_record):
        """測試：execute_task_now 無法建立執行記錄"""
        # Arrange
        db_session.get.return_value = sample_job_record

        # Mock enqueue_execution to return None
        with patch.object(automation_service, 'enqueue_execution', return_value=None):
            # Act & Assert
            with pytest.raises(JobDispatchError, match="無法建立任務執行紀錄"):
                automation_service.execute_task_now("job-123")

    def test_create_execution_running_status(self, automation_service, db_session, sample_job_record):
        """測試：create_execution 創建 running 狀態的執行記錄"""
        # Arrange
        execution_record = db_models.JobExecution(
            id="exec-123",
            job_id="job-123",
            status="queued",
            trigger="manual",
            summary="Test",
        )

        db_session.get.return_value = sample_job_record

        with patch.object(automation_service, 'enqueue_execution', return_value=execution_record):
            with patch.object(automation_service, 'mark_execution_running', return_value=execution_record):
                # Act
                result = automation_service.create_execution(
                    job_id="job-123",
                    status="running",
                    trigger="manual",
                    summary="Running test"
                )

                # Assert
                assert result is not None

    def test_create_execution_success_status(self, automation_service, db_session, sample_job_record):
        """測試：create_execution 創建 success 狀態的執行記錄"""
        # Arrange
        execution_record = db_models.JobExecution(
            id="exec-123",
            job_id="job-123",
            status="queued",
            trigger="manual",
            summary="Test",
        )

        db_session.get.return_value = sample_job_record

        with patch.object(automation_service, 'enqueue_execution', return_value=execution_record):
            with patch.object(automation_service, 'mark_execution_running', return_value=execution_record):
                with patch.object(automation_service, 'complete_execution', return_value=execution_record):
                    # Act
                    result = automation_service.create_execution(
                        job_id="job-123",
                        status="success",
                        trigger="manual",
                        summary="Success test",
                        duration=100
                    )

                    # Assert
                    assert result is not None

    def test_create_execution_enqueue_failure(self, automation_service, db_session):
        """測試：create_execution 無法 enqueue"""
        # Arrange
        with patch.object(automation_service, 'enqueue_execution', return_value=None):
            # Act
            result = automation_service.create_execution(
                job_id="job-123",
                status="queued",
                trigger="manual",
                summary="Test"
            )

            # Assert
            assert result is None

    def test_create_execution_running_mark_failure(self, automation_service, db_session, sample_job_record):
        """測試：create_execution running 狀態但 mark_execution_running 失敗"""
        # Arrange
        execution_record = db_models.JobExecution(
            id="exec-123",
            job_id="job-123",
            status="queued",
            trigger="manual",
            summary="Test",
        )

        with patch.object(automation_service, 'enqueue_execution', return_value=execution_record):
            with patch.object(automation_service, 'mark_execution_running', return_value=None):
                # Act
                result = automation_service.create_execution(
                    job_id="job-123",
                    status="running",
                    trigger="manual",
                    summary="Test"
                )

                # Assert
                assert result is None

    def test_enqueue_execution_cron_trigger_next_run_warning(self, automation_service, db_session, sample_job_record):
        """測試：enqueue_execution cron trigger 但無法計算下次執行時間"""
        # Arrange
        sample_job_record.trigger = "cron"
        sample_job_record.schedule = "invalid cron"
        sample_job_record.next_run_at = utcnow()
        db_session.get.return_value = sample_job_record

        with patch.object(automation_service, '_estimate_next_run', return_value=None):
            # Act
            result = automation_service.enqueue_execution(
                job_id="job-123",
                trigger="cron",
                summary="Test"
            )

            # Assert
            assert result is not None
            # next_run_at should remain unchanged

    def test_complete_execution_not_found(self, automation_service, db_session):
        """測試：complete_execution 執行記錄不存在"""
        # Arrange
        db_session.get.return_value = None

        # Act
        result = automation_service.complete_execution(
            execution_id="nonexistent",
            status="success",
            summary="Test"
        )

        # Assert
        assert result is None

    def test_complete_execution_with_metadata(self, automation_service, db_session, sample_job_record):
        """測試：complete_execution 設置 metadata"""
        # Arrange
        execution = db_models.JobExecution(
            id="exec-123",
            job_id="job-123",
            status="running",
            trigger="manual",
            started_at=utcnow() - timedelta(seconds=30),
        )

        def get_side_effect(model_class, id_):
            if model_class == db_models.JobExecution:
                return execution
            elif model_class == db_models.AutomationJob:
                return sample_job_record
            return None

        db_session.get.side_effect = get_side_effect

        # Act
        result = automation_service.complete_execution(
            execution_id="exec-123",
            status="success",
            summary="Complete with metadata",
            metadata={"test_key": "test_value"}
        )

        # Assert
        assert result is not None
        assert execution.execution_metadata == {"test_key": "test_value"}

    def test_get_calendar_events_with_naive_datetime(self, automation_service, db_session):
        """測試：get_calendar_events 處理 naive datetime"""
        from zoneinfo import ZoneInfo

        # Arrange
        naive_datetime = datetime(2024, 1, 1, 12, 0, 0)  # naive datetime without tzinfo
        job = db_models.AutomationJob(
            id="job-123",
            name="Test Job",
            description="Test",
            owner="test",
            creator_user_id="user-123",
            workspace_id="ws-123",
            prompt="test",
            status="active",
            trigger="manual",
            schedule="",
            next_run_at=naive_datetime,  # naive datetime
            created_at=utcnow(),
            updated_at=utcnow(),
            success_count=0,
            failure_count=0,
            total_duration=0,
            last_duration=None,
        )

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [job]
        db_session.execute.return_value = mock_result

        # Act
        result = automation_service.get_calendar_events()

        # Assert
        assert result is not None
        assert len(result.items) == 1
        # Verify that naive datetime was handled and converted to UTC
        assert result.items[0].start.tzinfo is not None

    def test_update_task_statistics_non_final_status(self, automation_service, db_session, sample_job_record):
        """測試：_update_task_statistics 處理非最終狀態"""
        # Arrange
        execution = db_models.JobExecution(
            id="exec-123",
            job_id="job-123",
            status="running",  # non-final status
            trigger="manual",
            started_at=utcnow(),
        )

        initial_success_count = sample_job_record.success_count
        initial_failure_count = sample_job_record.failure_count

        # Act
        automation_service._update_task_statistics(sample_job_record, execution)

        # Assert - counts should not change
        assert sample_job_record.success_count == initial_success_count
        assert sample_job_record.failure_count == initial_failure_count

    def test_update_task_statistics_cron_trigger_update_next_run(self, automation_service, db_session, sample_job_record):
        """測試：_update_task_statistics 更新 cron trigger 的 next_run_at"""
        # Arrange
        past_time = utcnow() - timedelta(days=1)
        sample_job_record.trigger = "cron"
        sample_job_record.schedule = "0 0 * * *"
        sample_job_record.next_run_at = past_time

        execution = db_models.JobExecution(
            id="exec-123",
            job_id="job-123",
            status="success",
            trigger="cron",
            started_at=utcnow() - timedelta(seconds=30),
            finished_at=utcnow(),
            duration=30,
        )

        # Act
        automation_service._update_task_statistics(sample_job_record, execution)

        # Assert
        # next_run_at should be updated to a future time
        assert sample_job_record.next_run_at is not None
        # The new next_run_at should be different from the past time
        assert sample_job_record.next_run_at != past_time

    def test_update_task_statistics_non_cron_trigger_clears_next_run(self, automation_service, db_session, sample_job_record):
        """測試：_update_task_statistics 清除非 cron trigger 的 next_run_at"""
        # Arrange
        sample_job_record.trigger = "manual"
        sample_job_record.next_run_at = utcnow() + timedelta(days=1)

        execution = db_models.JobExecution(
            id="exec-123",
            job_id="job-123",
            status="success",
            trigger="manual",
            started_at=utcnow() - timedelta(seconds=30),
            finished_at=utcnow(),
            duration=30,
        )

        # Act
        automation_service._update_task_statistics(sample_job_record, execution)

        # Assert
        assert sample_job_record.next_run_at is None

    def test_mark_execution_waiting_not_found(self, automation_service, db_session):
        """測試：mark_execution_waiting 執行記錄不存在"""
        # Arrange
        db_session.get.return_value = None

        # Act
        result = automation_service.mark_execution_waiting(
            execution_id="nonexistent",
            position=1,
            summary="Test"
        )

        # Assert
        assert result is None

    def test_cancel_execution_not_found(self, automation_service, db_session):
        """測試：cancel_execution 執行記錄不存在"""
        # Arrange
        db_session.get.return_value = None

        # Act
        result = automation_service.cancel_execution("nonexistent")

        # Assert
        assert result["status"] == "not_found"
        assert result["cancelled"] is False
        assert "不存在" in result["message"]
