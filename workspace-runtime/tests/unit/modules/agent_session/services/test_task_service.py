"""TaskService 單元測試."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from app.modules.agent_session.services.task_service import (
    TaskService,
    InvalidStateTransitionError,
    TaskServiceError,
)
from app.modules.agent_session.domain.entities import Task
from app.modules.agent_session.domain.enums import TaskStatus


class TestTaskService:
    """TaskService 測試."""

    @pytest.fixture
    def mock_db(self):
        """建立 Mock DB Session."""
        return AsyncMock()

    @pytest.fixture
    def service(self, mock_db):
        """建立 Service 實例."""
        svc = TaskService(mock_db)
        # 建立完整的 AsyncMock repositories
        svc.task_repo = AsyncMock()
        svc.session_repo = AsyncMock()
        return svc

    def _create_mock_task_model(
        self,
        task_id: str = "task-123",
        session_id: str = "session-456",
        status: str = "created",
        **kwargs,
    ):
        """建立 Mock Task Model."""
        return {
            "task_id": task_id,
            "session_id": session_id,
            "status": status,
            "created_at": datetime.utcnow(),
            "started_at": kwargs.get("started_at"),
            "completed_at": kwargs.get("completed_at"),
            "created_by": kwargs.get("created_by", "user"),
            "data": kwargs.get("data", {}),
        }

    def _create_mock_task_entity(
        self,
        task_id: str = "task-123",
        session_id: str = "session-456",
        status: TaskStatus = TaskStatus.CREATED,
        **kwargs,
    ):
        """建立 Mock Task Entity."""
        return Task(
            id=task_id,
            session_id=session_id,
            status=status,
            created_at=datetime.utcnow(),
            created_by=kwargs.get("created_by", "user"),
            started_at=kwargs.get("started_at"),
            completed_at=kwargs.get("completed_at"),
            full_prompt=kwargs.get("full_prompt"),
            tool_use_count=kwargs.get("tool_use_count", 0),
        )

    @pytest.mark.asyncio
    async def test_create_task(self, service):
        """測試建立 Task."""
        mock_model = self._create_mock_task_model()
        mock_entity = self._create_mock_task_entity()

        service.task_repo.create.return_value = mock_model
        service.task_repo.to_entity = MagicMock(return_value=mock_entity)
        service.session_repo.add_task.return_value = None

        result = await service.create_task(
            session_id="session-456",
            full_prompt="Test prompt",
            created_by="test-user",
        )

        assert result is not None
        service.task_repo.create.assert_called_once()
        service.session_repo.add_task.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_task_found(self, service):
        """測試取得 Task - 找到."""
        mock_model = self._create_mock_task_model()
        mock_entity = self._create_mock_task_entity()

        service.task_repo.find_by_id.return_value = mock_model
        service.task_repo.to_entity = MagicMock(return_value=mock_entity)

        result = await service.get_task("task-123")

        assert result is not None
        assert result.id == "task-123"

    @pytest.mark.asyncio
    async def test_get_task_not_found(self, service):
        """測試取得 Task - 未找到."""
        service.task_repo.find_by_id.return_value = None

        result = await service.get_task("not-found")

        assert result is None

    @pytest.mark.asyncio
    async def test_start_task(self, service):
        """測試啟動 Task."""
        # get_task 需要的 mocks
        created_model = self._create_mock_task_model(status="created")
        created_entity = self._create_mock_task_entity(status=TaskStatus.CREATED)
        
        # start 後的 mocks
        running_model = self._create_mock_task_model(status="running", started_at=datetime.utcnow())
        running_entity = self._create_mock_task_entity(status=TaskStatus.RUNNING, started_at=datetime.utcnow())

        service.task_repo.find_by_id.return_value = created_model
        service.task_repo.start_task.return_value = running_model
        service.task_repo.to_entity = MagicMock(side_effect=[created_entity, running_entity])
        service.session_repo.update_status.return_value = None

        result = await service.start_task("task-123")

        assert result is not None
        assert result.status == TaskStatus.RUNNING
        service.task_repo.start_task.assert_called_once_with("task-123")

    @pytest.mark.asyncio
    async def test_complete_task(self, service):
        """測試完成 Task."""
        running_model = self._create_mock_task_model(status="running")
        running_entity = self._create_mock_task_entity(status=TaskStatus.RUNNING)
        
        completed_model = self._create_mock_task_model(status="completed", completed_at=datetime.utcnow())
        completed_entity = self._create_mock_task_entity(status=TaskStatus.COMPLETED, completed_at=datetime.utcnow())

        service.task_repo.find_by_id.return_value = running_model
        service.task_repo.complete_task.return_value = completed_model
        service.task_repo.to_entity = MagicMock(side_effect=[running_entity, completed_entity])
        service.session_repo.update_status.return_value = None

        raw_response = {"type": "claude", "usage": {"input_tokens": 100}}
        result = await service.complete_task("task-123", raw_response)

        assert result is not None
        assert result.status == TaskStatus.COMPLETED
        service.task_repo.complete_task.assert_called_once()

    @pytest.mark.asyncio
    async def test_fail_task(self, service):
        """測試失敗 Task."""
        running_model = self._create_mock_task_model(status="running")
        running_entity = self._create_mock_task_entity(status=TaskStatus.RUNNING)
        
        failed_model = self._create_mock_task_model(
            status="failed",
            data={"error_message": "Something went wrong"},
        )
        failed_entity = self._create_mock_task_entity(status=TaskStatus.FAILED)

        service.task_repo.find_by_id.return_value = running_model
        service.task_repo.fail_task.return_value = failed_model
        service.task_repo.to_entity = MagicMock(side_effect=[running_entity, failed_entity])
        service.session_repo.update_status.return_value = None

        result = await service.fail_task("task-123", "Something went wrong")

        assert result is not None
        assert result.status == TaskStatus.FAILED
        service.task_repo.fail_task.assert_called_once_with("task-123", "Something went wrong")

    @pytest.mark.asyncio
    async def test_stop_task(self, service):
        """測試停止 Task."""
        running_model = self._create_mock_task_model(status="running")
        running_entity = self._create_mock_task_entity(status=TaskStatus.RUNNING)
        
        stopped_model = self._create_mock_task_model(status="stopped")
        stopped_entity = self._create_mock_task_entity(status=TaskStatus.STOPPED)

        service.task_repo.find_by_id.return_value = running_model
        service.task_repo.update.return_value = None
        service.task_repo.stop_task.return_value = stopped_model
        service.task_repo.to_entity = MagicMock(side_effect=[running_entity, stopped_entity])
        service.session_repo.update_status.return_value = None

        result = await service.stop_task("task-123")

        assert result is not None
        assert result.status == TaskStatus.STOPPED

    @pytest.mark.asyncio
    async def test_stop_task_not_found(self, service):
        """測試停止 Task - 未找到."""
        service.task_repo.find_by_id.return_value = None

        with pytest.raises(TaskServiceError, match="Task not found"):
            await service.stop_task("not-found")

    @pytest.mark.asyncio
    async def test_stop_task_already_stopped(self, service):
        """測試停止 Task - 已停止的任務."""
        # Task 已經完成，但 stop_task 仍會嘗試停止
        completed_model = self._create_mock_task_model(status="completed")
        completed_entity = self._create_mock_task_entity(status=TaskStatus.COMPLETED)
        
        # 即使已完成，如果 repo 成功返回，也會正常完成
        stopped_model = self._create_mock_task_model(status="stopped")
        stopped_entity = self._create_mock_task_entity(status=TaskStatus.STOPPED)

        service.task_repo.find_by_id.return_value = completed_model
        service.task_repo.stop_task.return_value = stopped_model
        service.task_repo.to_entity = MagicMock(side_effect=[completed_entity, stopped_entity])
        service.session_repo.update_status.return_value = None

        result = await service.stop_task("task-123")
        
        # 方法會成功執行（不驗證狀態轉換）
        assert result is not None

    @pytest.mark.asyncio
    async def test_set_awaiting_permission(self, service):
        """測試設定等待權限."""
        running_model = self._create_mock_task_model(status="running")
        running_entity = self._create_mock_task_entity(status=TaskStatus.RUNNING)
        
        awaiting_model = self._create_mock_task_model(status="awaiting_permission")
        awaiting_entity = self._create_mock_task_entity(status=TaskStatus.AWAITING_PERMISSION)

        service.task_repo.find_by_id.return_value = running_model
        service.task_repo.set_awaiting_permission.return_value = awaiting_model
        service.task_repo.to_entity = MagicMock(side_effect=[running_entity, awaiting_entity])
        service.session_repo.update_status.return_value = None

        permission_request = {
            "request_id": "req-123",
            "tool_name": "bash",
            "tool_input": {"command": "ls"},
        }

        result = await service.set_awaiting_permission("task-123", permission_request)

        assert result is not None
        assert result.status == TaskStatus.AWAITING_PERMISSION

    @pytest.mark.asyncio
    async def test_resume_from_permission(self, service):
        """測試從權限等待恢復."""
        awaiting_model = self._create_mock_task_model(status="awaiting_permission")
        awaiting_entity = self._create_mock_task_entity(status=TaskStatus.AWAITING_PERMISSION)
        
        running_model = self._create_mock_task_model(status="running")
        running_entity = self._create_mock_task_entity(status=TaskStatus.RUNNING)

        service.task_repo.find_by_id.return_value = awaiting_model
        service.task_repo.update.return_value = running_model
        service.task_repo.to_entity = MagicMock(side_effect=[awaiting_entity, running_entity])
        service.session_repo.update_status.return_value = None

        result = await service.resume_from_permission("task-123")

        assert result is not None

    @pytest.mark.asyncio
    async def test_get_active_task(self, service):
        """測試取得活躍 Task."""
        mock_model = self._create_mock_task_model(status="running")
        mock_entity = self._create_mock_task_entity(status=TaskStatus.RUNNING)

        service.task_repo.find_active_by_session.return_value = mock_model
        service.task_repo.to_entity = MagicMock(return_value=mock_entity)

        result = await service.get_active_task("session-456")

        assert result is not None
        assert result.status == TaskStatus.RUNNING

    @pytest.mark.asyncio
    async def test_get_active_task_none(self, service):
        """測試取得活躍 Task - 無活躍任務."""
        service.task_repo.find_active_by_session.return_value = None

        result = await service.get_active_task("session-456")

        assert result is None


class TestTokenUsageExtraction:
    """Token Usage 提取測試."""

    def test_extract_claude_usage(self):
        """測試提取 Claude 格式的 token usage."""
        raw_response = {
            "type": "claude",
            "response": {
                "usage": {
                    "input_tokens": 1000,
                    "output_tokens": 500,
                    "cache_creation_input_tokens": 100,
                    "cache_read_input_tokens": 200,
                }
            }
        }

        usage = TaskService.extract_token_usage(raw_response)

        assert usage is not None
        assert usage.input_tokens == 1000
        assert usage.output_tokens == 500
        assert usage.cache_creation_input_tokens == 100
        assert usage.cache_read_input_tokens == 200

    def test_extract_claude_usage_from_root_usage_data(self):
        """測試提取 Claude root usageData 格式的 token usage."""
        raw_response = {
            "type": "claude",
            "usageData": {
                "inputTokens": 1200,
                "outputTokens": 345,
                "totalTokens": 1545,
                "cacheCreationTokens": 50,
                "cacheReadTokens": 75,
            },
            "usage": {
                "input_tokens": 1,
                "output_tokens": 2,
            },
        }

        usage = TaskService.extract_token_usage(raw_response)

        assert usage is not None
        assert usage.input_tokens == 1200
        assert usage.output_tokens == 345
        assert usage.total_tokens == 1545
        assert usage.cache_creation_input_tokens == 50
        assert usage.cache_read_input_tokens == 75

    def test_extract_codex_usage(self):
        """測試提取 Codex 格式的 token usage."""
        raw_response = {
            "type": "codex",
            "response": {
                "turn": {
                    "usage": {
                        "input_tokens": 800,
                        "output_tokens": 400,
                        "total_tokens": 1200,
                    }
                }
            }
        }

        usage = TaskService.extract_token_usage(raw_response)

        assert usage is not None
        assert usage.input_tokens == 800
        assert usage.output_tokens == 400

    def test_extract_gemini_usage(self):
        """測試提取 Gemini 格式的 token usage."""
        raw_response = {
            "type": "gemini",
            "response": {
                "usageMetadata": {
                    "promptTokenCount": 600,
                    "candidatesTokenCount": 300,
                    "totalTokenCount": 900,
                }
            }
        }

        usage = TaskService.extract_token_usage(raw_response)

        assert usage is not None
        assert usage.input_tokens == 600
        assert usage.output_tokens == 300

    def test_extract_no_usage(self):
        """測試無 usage 資料."""
        raw_response = {"type": "unknown"}

        usage = TaskService.extract_token_usage(raw_response)

        assert usage is None
