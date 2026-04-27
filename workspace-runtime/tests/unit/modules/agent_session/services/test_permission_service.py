"""PermissionService unit tests."""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime

from app.modules.agent_session.services.permission_service import (
    PermissionService,
    PermissionTimeoutError,
)
from app.modules.agent_session.domain.enums import (
    PermissionScope,
)
from app.modules.agent_session.schemas.session import PermissionDecisionRequest


class TestPermissionService:
    """PermissionService tests."""

    @pytest.fixture
    def mock_db(self):
        """Create Mock DB Session."""
        return AsyncMock()

    @pytest.fixture
    def service(self, mock_db):
        """Create Service instance."""
        svc = PermissionService(mock_db)
        svc.session_repo = AsyncMock()
        svc.task_repo = AsyncMock()
        svc.message_repo = AsyncMock()
        return svc

    def _create_mock_task_model(self, **kwargs):
        """Create Mock Task Model (with attributes)."""
        mock = MagicMock()
        mock.task_id = kwargs.get("task_id", "task-123")
        mock.session_id = kwargs.get("session_id", "session-456")
        mock.status = kwargs.get("status", "awaiting_permission")
        mock.created_at = datetime.utcnow()
        mock.data = kwargs.get("data", {})
        return mock

    @pytest.mark.asyncio
    async def test_create_permission_request(self, service):
        """Test creating permission request."""
        service.task_repo.set_awaiting_permission.return_value = self._create_mock_task_model()
        service.session_repo.update_status.return_value = None
        service.message_repo.create.return_value = {"message_id": "msg-123"}

        # Mock _create_permission_message
        service._create_permission_message = AsyncMock()

        request_id = await service.create_permission_request(
            session_id="session-456",
            task_id="task-123",
            tool_name="bash",
            tool_input={"command": "ls"},
        )

        assert request_id is not None
        service.task_repo.set_awaiting_permission.assert_called_once()
        service.session_repo.update_status.assert_called_once()

    @pytest.mark.asyncio
    async def test_resolve_decision_approve(self, service):
        """Test resolving permission decision - approve."""
        request_id = "req-approve"
        event = asyncio.Event()
        service._pending_decisions[request_id] = event

        service.task_repo.find_by_id.return_value = self._create_mock_task_model()
        service.task_repo.update.return_value = None
        service.session_repo.update_status.return_value = None

        # Mock _update_permission_message
        service._update_permission_message = AsyncMock()

        decision = PermissionDecisionRequest(
            request_id=request_id,
            task_id="task-123",
            allow=True,
            scope=PermissionScope.ONCE,
            decided_by="user-1",
        )

        result = await service.resolve_decision(decision)

        assert result is True
        assert event.is_set()

    @pytest.mark.asyncio
    async def test_resolve_decision_deny(self, service):
        """Test resolving permission decision - deny."""
        request_id = "req-deny"
        event = asyncio.Event()
        service._pending_decisions[request_id] = event

        service.task_repo.find_by_id.return_value = self._create_mock_task_model()
        service.task_repo.fail_task.return_value = None
        service.session_repo.update_status.return_value = None

        # Mock _update_permission_message
        service._update_permission_message = AsyncMock()

        decision = PermissionDecisionRequest(
            request_id=request_id,
            task_id="task-123",
            allow=False,
            decided_by="user-1",
            reason="Not allowed",
        )

        result = await service.resolve_decision(decision)

        assert result is True

    @pytest.mark.asyncio
    async def test_resolve_decision_task_not_found(self, service):
        """Test resolving permission decision - task not found."""
        from app.modules.agent_session.services.permission_service import PermissionServiceError

        service.task_repo.find_by_id.return_value = None

        decision = PermissionDecisionRequest(
            request_id="not-found",
            task_id="task-not-found",
            allow=True,
            decided_by="user-1",
        )

        with pytest.raises(PermissionServiceError):
            await service.resolve_decision(decision)

    @pytest.mark.asyncio
    async def test_cancel_request(self, service):
        """Test canceling permission request."""
        request_id = "req-cancel"
        event = asyncio.Event()
        service._pending_decisions[request_id] = event

        await service.cancel_request(request_id)

        # cancel_request 會設定 event 並儲存拒絕決策
        assert event.is_set()
        assert request_id in service._decision_results
        assert service._decision_results[request_id].allow is False
        assert service._decision_results[request_id].reason == "Request cancelled"

    @pytest.mark.asyncio
    async def test_wait_for_decision_timeout(self, service):
        """Test waiting for permission decision - timeout."""
        request_id = "req-timeout"
        event = asyncio.Event()
        service._pending_decisions[request_id] = event

        # Mock handle_timeout
        service.handle_timeout = AsyncMock()

        # 使用很短的超時時間
        with pytest.raises(PermissionTimeoutError):
            await service.wait_for_decision(request_id, timeout_seconds=0.01)


class TestPermissionServiceEdgeCases:
    """PermissionService edge case tests."""

    @pytest.fixture
    def mock_db(self):
        return AsyncMock()

    @pytest.fixture
    def service(self, mock_db):
        svc = PermissionService(mock_db)
        svc.session_repo = AsyncMock()
        svc.task_repo = AsyncMock()
        svc.message_repo = AsyncMock()
        return svc

    @pytest.mark.asyncio
    async def test_concurrent_requests(self, service):
        """Test concurrent requests."""
        # Create multiple concurrent requests
        request_ids = []
        for i in range(5):
            request_id = f"req-concurrent-{i}"
            service._pending_decisions[request_id] = asyncio.Event()
            request_ids.append(request_id)

        assert len(service._pending_decisions) == 5

        # Cancel all requests
        for request_id in request_ids:
            await service.cancel_request(request_id)

        # cancel_request will set event but not remove pending_decisions
        # Verify all events are set
        for request_id in request_ids:
            event = service._pending_decisions.get(request_id)
            assert event is not None
            assert event.is_set()
            assert request_id in service._decision_results
            assert service._decision_results[request_id].allow is False

    @pytest.mark.asyncio
    async def test_double_resolve(self, service):
        """Test resolving the same request twice."""
        request_id = "req-double"
        event = asyncio.Event()
        service._pending_decisions[request_id] = event

        mock_task = MagicMock()
        mock_task.task_id = "task-123"
        mock_task.session_id = "session-456"
        mock_task.status = "awaiting_permission"

        service.task_repo.find_by_id.return_value = mock_task
        service.task_repo.update.return_value = None
        service.session_repo.update_status.return_value = None
        service._update_permission_message = AsyncMock()

        decision1 = PermissionDecisionRequest(
            request_id=request_id,
            task_id="task-123",
            allow=True,
            decided_by="user-1",
        )

        result1 = await service.resolve_decision(decision1)
        assert result1 is True

        # Second resolution - will still succeed even if called again (because event is already set)
        # But in practice this should be avoided
        decision2 = PermissionDecisionRequest(
            request_id=request_id,
            task_id="task-123",
            allow=False,
            decided_by="user-1",
        )
        # This call will still succeed because the task still exists
        result2 = await service.resolve_decision(decision2)
        assert result2 is True  # Actually updates twice

    @pytest.mark.asyncio
    async def test_pending_decisions_state(self, service):
        """Test pending decision state management."""
        # Initial state
        assert len(service._pending_decisions) == 0
        assert len(service._decision_results) == 0

        # Simulate creating decision
        request_id = "test-req"
        event = asyncio.Event()
        service._pending_decisions[request_id] = event

        assert request_id in service._pending_decisions

        # Simulate resolving
        mock_task = MagicMock()
        mock_task.session_id = "session-1"

        service.task_repo.find_by_id.return_value = mock_task
        service._update_permission_message = AsyncMock()

        decision = PermissionDecisionRequest(
            request_id=request_id,
            task_id="task-1",
            allow=True,
            decided_by="user-1",
        )

        await service.resolve_decision(decision)

        # Check result is stored
        assert request_id in service._decision_results
        assert service._decision_results[request_id].allow is True
